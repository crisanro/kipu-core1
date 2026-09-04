# app/api/v1/app/emisor.py
import time
import httpx
import base64
from datetime import datetime, date
from fastapi import APIRouter, Depends, Form, UploadFile, File, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import verify_firebase_token, validar_y_quemar_pin
from app.schemas.emisor import OnboardingRequest, EmisorUpdate
from app.services.storage_service import upload_file, delete_folder
from app.utils.crypto import encrypt_password
from app.utils.texto import mayusculas
from app.utils.validacion_sri import validar_ruc_ecuador
from app.core.cache import cache_get, cache_set, invalidate_emisor, CK, TTL
from app.core.rate_limit import RateLimit, RateLimitScope
from app.core.config import settings
from app.core.permisos import verificar_permiso, verificar_admin
from app.services.audit_service import audit_log

router = APIRouter()
NODE_VALIDATOR_URL = f"{settings.NODE_SIGNER_URL}/api/validar-p12"

# ── Helpers — sin cambios ──────────────────────────────────────────────────────

async def _vincular_usuario_invitado(data: OnboardingRequest, auth_data: dict, db: AsyncSession):
    uid = auth_data["uid"]
    res_empresa = await db.execute(text("""
        SELECT id, razon_social FROM emisores WHERE id = :eid
    """), {"eid": data.emisor_id})
    empresa = res_empresa.fetchone()
    if not empresa:
        raise HTTPException(status_code=404, detail="La empresa no existe o la invitación es inválida.")
    res_profile = await db.execute(text("""
        SELECT id FROM profiles WHERE firebase_uid = :uid
    """), {"uid": uid})
    perfil = res_profile.fetchone()
    if not perfil:
        res_new = await db.execute(text("""
            INSERT INTO profiles (firebase_uid, email, full_name, role)
            VALUES (:uid, :email, :fname, 'admin')
            RETURNING id
        """), {
            "uid":   uid,
            "email": auth_data["email"].lower(),
            "fname": mayusculas(data.full_name) or auth_data["email"].split("@")[0].upper(),
        })
        profile_id = res_new.scalar()
    else:
        profile_id = perfil.id
    res_dup = await db.execute(text("""
        SELECT id FROM emisor_usuarios WHERE profile_id = :pid AND emisor_id = :eid
    """), {"pid": str(profile_id), "eid": data.emisor_id})
    if res_dup.fetchone():
        raise HTTPException(status_code=400, detail="Ya perteneces a esta empresa.")
    rol = data.rol if data.rol in ("admin", "emisor") else "emisor"
    await db.execute(text("""
        INSERT INTO emisor_usuarios (emisor_id, profile_id, rol)
        VALUES (:eid, :pid, :rol)
    """), {"eid": data.emisor_id, "pid": str(profile_id), "rol": rol})
    await db.commit()
    return {
        "ok":        True,
        "mensaje":   f"Te has unido a {empresa.razon_social} correctamente.",
        "emisor_id": data.emisor_id,
        "modo":      "VINCULACION",
    }

# ── POST /onboarding ───────────────────────────────────────────────────────────
@router.post("/onboarding", summary="Registro inicial / Nueva empresa", status_code=201)
async def onboarding(
    data:      OnboardingRequest,
    auth_data: dict         = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db),
    _rl:       None         = Depends(RateLimit(RateLimitScope.AUTH, use_ip=True)),
):
    from firebase_admin import auth as firebase_auth
    try:
        user_record = firebase_auth.get_user(auth_data["uid"])
        if not user_record.email_verified:
            raise HTTPException(status_code=403, detail="Debes verificar tu correo electrónico antes de continuar.")
    except HTTPException:
        raise
    except Exception:
        pass

    if data.emisor_id:
        return await _vincular_usuario_invitado(data, auth_data, db)

    if not data.ruc or not data.razon_social or not data.direccion_matriz:
        raise HTTPException(status_code=400, detail="RUC, razón social y dirección son obligatorios.")

    es_valido, mensaje_error = validar_ruc_ecuador(data.ruc)
    if not es_valido:
        raise HTTPException(status_code=400, detail=mensaje_error)

    try:
        res_profile = await db.execute(
            text("SELECT id FROM profiles WHERE firebase_uid = :uid"),
            {"uid": auth_data["uid"]}
        )
        perfil = res_profile.fetchone()
        if perfil:
            profile_id = perfil.id
            res_pruebas = await db.execute(text("""
                SELECT COUNT(*) FROM emisor_usuarios eu
                JOIN emisores e ON e.id = eu.emisor_id
                WHERE eu.profile_id = :pid AND e.ambiente = 1
            """), {"pid": str(profile_id)})
            if res_pruebas.scalar() > 0:
                raise HTTPException(status_code=400, detail="Ya tienes una empresa en modo pruebas.")
        else:
            profile_id = None

        tipo_emisor = "JURIDICO" if data.ruc[2] == "9" else "NATURAL"
        res_emisor = await db.execute(text("""
            INSERT INTO emisores (
                ruc, razon_social, nombre_comercial,
                direccion_matriz, obligado_contabilidad, contribuyente_especial, ambiente, tipo_emisor
            ) VALUES (:ruc, :rs, :nc, :dir, :obl, :ce, 1, :tipo)
            RETURNING id
        """), {
            "ruc":  data.ruc,
            "rs":   mayusculas(data.razon_social),
            "nc":   mayusculas(data.nombre_comercial),
            "dir":  mayusculas(data.direccion_matriz),
            "obl":  (data.obligado_contabilidad or "NO").upper(),
            "ce":   (data.contribuyente_especial or "").upper(),
            "tipo": tipo_emisor,
        })
        new_emisor_id = res_emisor.scalar()

        if not profile_id:
            res_new = await db.execute(text("""
                INSERT INTO profiles (firebase_uid, email, full_name, role)
                VALUES (:uid, :email, :fname, 'admin')
                RETURNING id
            """), {
                "uid":   auth_data["uid"],
                "email": auth_data["email"].lower(),
                "fname": mayusculas(data.full_name or data.razon_social),
            })
            profile_id = res_new.scalar()

        await db.execute(
            text("INSERT INTO emisor_usuarios (emisor_id, profile_id, rol) VALUES (:eid, :pid, 'admin')"),
            {"eid": new_emisor_id, "pid": str(profile_id)}
        )
        await db.execute(
            text("INSERT INTO user_credits (emisor_id, balance) VALUES (:eid, 10)"),
            {"eid": new_emisor_id}
        )
        await db.execute(text("""
            INSERT INTO credit_transactions (emisor_id, tipo, cantidad, precio_total, metodo_pago, notas)
            VALUES (:eid, 'BONO', 10, 0.00, 'SISTEMA', 'REGALO POR APERTURA DE CUENTA')
        """), {"eid": new_emisor_id})
        await db.commit()

        try:
            res_tokens = await db.execute(text("""
                SELECT DISTINCT token, device_id FROM fcm_tokens WHERE profile_id = :pid
            """), {"pid": str(profile_id)})
            tokens = res_tokens.fetchall()
            for t in tokens:
                await db.execute(text("""
                    INSERT INTO fcm_tokens (profile_id, emisor_id, token, device_id, updated_at)
                    VALUES (:pid, :eid, :token, :did, NOW())
                    ON CONFLICT (profile_id, emisor_id, device_id)
                    DO UPDATE SET token = :token, updated_at = NOW()
                """), {"pid": str(profile_id), "eid": new_emisor_id, "token": t.token, "did": t.device_id or "default"})
            if tokens:
                await db.commit()
        except Exception as e:
            print(f"[FCM] ⚠️ Error heredando tokens: {e}")

        return {"ok": True, "mensaje": "EMPRESA CONFIGURADA CORRECTAMENTE.", "emisor_id": new_emisor_id}

    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        import traceback; traceback.print_exc()
        err = str(e).lower()
        if "23505" in err or "unique" in err:
            if "emisores_ruc_key" in str(e):
                raise HTTPException(status_code=400, detail="EL RUC YA ESTÁ REGISTRADO EN KIPU.")
            raise HTTPException(status_code=400, detail="YA EXISTE UN REGISTRO CON ESOS DATOS.")
        raise HTTPException(status_code=500, detail="ERROR INTERNO AL PROCESAR EL REGISTRO.")

# ── GET /info/{emisor_id} ──────────────────────────────────────────────────────
@router.get("/info/{emisor_id}", summary="Info pública de una empresa por ID")
async def info_emisor_publico(
    emisor_id: int,
    auth_data: dict         = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db),
):
    res = await db.execute(text("""
        SELECT razon_social, nombre_comercial FROM emisores WHERE id = :eid
    """), {"eid": emisor_id})
    empresa = res.fetchone()
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa no encontrada.")
    return {
        "ok":               True,
        "razon_social":     empresa.razon_social,
        "nombre_comercial": empresa.nombre_comercial or empresa.razon_social,
    }

# ── POST /firma ────────────────────────────────────────────────────────────────
@router.post("/firma", summary="Subir firma electrónica (P12)")
async def upload_p12(
    request:   Request,
    password:  str          = Form(...),
    file:      UploadFile   = File(...),
    auth_data: dict         = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db),
    _rl:       None         = Depends(RateLimit(RateLimitScope.AUTH)),
):
    emisor_id = auth_data.get("emisor_id")
    if not emisor_id:
        raise HTTPException(status_code=400, detail="EL USUARIO NO TIENE UN EMISOR VINCULADO.")
    verificar_permiso(auth_data, "configuracion")

    res_emisor = await db.execute(
        text("SELECT ruc, p12_path FROM emisores WHERE id = :eid"), {"eid": emisor_id}
    )
    emisor = res_emisor.fetchone()
    if not emisor:
        raise HTTPException(status_code=404, detail="EMISOR NO ENCONTRADO.")
    if not file.filename.lower().endswith(".p12"):
        raise HTTPException(status_code=400, detail="EL ARCHIVO DEBE SER UN FORMATO .P12 VÁLIDO.")

    file_bytes = await file.read()
    p12_base64 = base64.b64encode(file_bytes).decode("utf-8")

    async with httpx.AsyncClient() as client:
        try:
            res_node = await client.post(
                NODE_VALIDATOR_URL,
                json={"p12Base64": p12_base64, "password": password, "ruc": emisor.ruc},
                timeout=20.0
            )
            val = res_node.json()
        except Exception as e:
            print(f"❌ Error conexión Node.js: {e}")
            raise HTTPException(status_code=500, detail="ERROR AL CONECTAR CON EL VALIDADOR.")

    if not val.get("ok"):
        raise HTTPException(status_code=400, detail=val.get("mensaje", "CERTIFICADO INVÁLIDO.").upper())

    try:
        if emisor.p12_path:
            try:
                delete_folder(f"{emisor.ruc}/firmas/")
            except:
                pass

        p12_filename = f"firma_{emisor.ruc}_{int(time.time())}.p12"
        p12_path     = f"{emisor.ruc}/firmas/{p12_filename}"
        upload_file(p12_path, file_bytes, "application/x-pkcs12")
        pass_enc  = encrypt_password(password)
        raw_exp   = (val.get("expiracion") or val.get("expiration") or val.get("datos", {}).get("vence"))
        if not raw_exp:
            raise ValueError("No se encontró la fecha de expiración.")
        fecha_exp = datetime.strptime(str(raw_exp)[:10], "%Y-%m-%d").date()

        await db.execute(text("""
            UPDATE emisores
            SET p12_path = :path, p12_pass = :pass, p12_expiration = :exp, updated_at = NOW()
            WHERE id = :eid
        """), {"path": p12_path, "pass": pass_enc, "exp": fecha_exp, "eid": emisor_id})

        await audit_log(
            db        = db,
            auth_data = auth_data,
            accion    = "UPDATE",
            entidad   = "firma",
            entidad_id = str(emisor_id),
            detalle   = {
                "archivo":    file.filename,
                "expiracion": str(fecha_exp),
                "ruc":        emisor.ruc,
            },
            request   = request,
        )
        await db.commit()
        await invalidate_emisor(emisor_id)
        return {"ok": True, "mensaje": "FIRMA ELECTRÓNICA CONFIGURADA CORRECTAMENTE.", "expiracion": str(fecha_exp)}

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        print(f"❌ ERROR: {e}")
        raise HTTPException(status_code=500, detail="ERROR AL GUARDAR LA FIRMA.")

# ── DELETE /firma ──────────────────────────────────────────────────────────────
@router.delete("/firma", summary="Eliminar firma electrónica")
async def remove_p12(
    request:   Request,
    auth_data: dict         = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db),
):
    emisor_id = auth_data.get("emisor_id")
    if not emisor_id:
        raise HTTPException(status_code=400, detail="EL USUARIO NO TIENE UN EMISOR VINCULADO.")
    verificar_permiso(auth_data, "configuracion")

    res    = await db.execute(text("SELECT ruc, p12_path FROM emisores WHERE id = :eid"), {"eid": emisor_id})
    emisor = res.fetchone()
    if not emisor:
        raise HTTPException(status_code=404, detail="EMISOR NO ENCONTRADO.")

    try:
        if emisor.p12_path:
            try:
                delete_folder(f"{emisor.ruc}/firmas/")
            except Exception as e:
                print(f"⚠️ No se pudo eliminar carpeta firmas: {e}")

        await db.execute(text("""
            UPDATE emisores
            SET p12_path = NULL, p12_pass = NULL, p12_expiration = NULL, updated_at = NOW()
            WHERE id = :eid
        """), {"eid": emisor_id})

        await audit_log(
            db        = db,
            auth_data = auth_data,
            accion    = "DELETE",
            entidad   = "firma",
            entidad_id = str(emisor_id),
            detalle   = {"ruc": emisor.ruc},
            request   = request,
        )
        await db.commit()
        await invalidate_emisor(emisor_id)
        return {"ok": True, "mensaje": "FIRMA ELECTRÓNICA ELIMINADA CORRECTAMENTE."}

    except Exception as e:
        await db.rollback()
        print(f"❌ ERROR AL ELIMINAR FIRMA: {e}")
        raise HTTPException(status_code=500, detail="ERROR AL ELIMINAR LA FIRMA.")

# ── GET /config ────────────────────────────────────────────────────────────────
@router.get("/config", summary="Obtener configuración fiscal y de firma")
async def get_config(
    auth_data: dict         = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db),
):
    emisor_id = auth_data.get("emisor_id")
    if not emisor_id:
        return {"ok": True, "configurado": False, "mensaje": "Pendiente de configuración inicial."}
    verificar_permiso(auth_data, "configuracion")

    cache_key = CK.fmt(CK.EMISOR, eid=emisor_id)
    cached    = await cache_get(cache_key)
    if cached:
        return cached

    res = await db.execute(text("""
        SELECT
            e.ruc, e.razon_social, e.nombre_comercial, e.direccion_matriz,
            e.contribuyente_especial, e.obligado_contabilidad, e.ambiente,
            e.p12_path, e.p12_expiration, e.created_at,
            COALESCE(uc.balance, 0) AS balance_api,
            s.estado                AS sub_estado,
            s.plan                  AS sub_plan,
            s.current_period_end    AS sub_vence
        FROM emisores e
        LEFT JOIN user_credits  uc ON uc.emisor_id = e.id
        LEFT JOIN subscriptions s  ON s.emisor_id  = e.id
        WHERE e.id = :eid
    """), {"eid": emisor_id})
    data = res.fetchone()
    if not data:
        raise HTTPException(status_code=404, detail="EMISOR NO ENCONTRADO.")

    expiracion   = data.p12_expiration
    nombre_firma = data.p12_path.split("/")[-1] if data.p12_path else "No configurada"
    firma_info   = {
        "configurada":         bool(data.p12_path),
        "nombre":              nombre_firma,
        "expiracion":          str(expiracion) if expiracion else None,
        "estado":              "PENDIENTE",
        "mensaje_vencimiento": "Firma no cargada",
    }
    if expiracion:
        hoy            = datetime.utcnow().date()
        dias_restantes = (expiracion - hoy).days
        fecha_fmt      = expiracion.strftime("%d/%m/%Y")
        if dias_restantes <= 0:
            firma_info.update({"estado": "EXPIRADA",  "mensaje_vencimiento": f"Expirada el {fecha_fmt}"})
        elif dias_restantes <= 30:
            firma_info.update({"estado": "ALERTA",    "mensaje_vencimiento": f"Próxima a vencer ({dias_restantes} días)"})
        else:
            firma_info.update({"estado": "VIGENTE",   "mensaje_vencimiento": f"Vigente hasta el {fecha_fmt}"})

    excluir    = {"p12_path", "p12_expiration"}
    legal_data = {k: v for k, v in data._mapping.items() if k not in excluir}

    response = {
        "ok":          True,
        "configurado": True,
        "data": {
            "legal":    legal_data,
            "firma":    firma_info,
            "whatsapp": {"configurado": False},
            "creditos": {
                "balance_api": data.balance_api,
                "sub_estado":  data.sub_estado,
                "sub_plan":    data.sub_plan,
                "sub_vence":   str(data.sub_vence) if data.sub_vence else None,
            },
        }
    }
    await cache_set(cache_key, response, TTL.EMISOR_PERFIL)
    return response

# ── PATCH /config ──────────────────────────────────────────────────────────────
@router.patch("/config", summary="Actualizar configuración del emisor")
async def update_config(
    data:      EmisorUpdate,
    request:   Request,
    auth_data: dict         = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db),
):
    emisor_id = auth_data.get("emisor_id")
    if not emisor_id:
        raise HTTPException(status_code=400, detail="EL USUARIO NO TIENE UN EMISOR VINCULADO.")
    verificar_permiso(auth_data, "configuracion")

    update_data = {
        k: (mayusculas(v) if isinstance(v, str) else v)
        for k, v in data.model_dump().items()
        if v is not None
    }
    if not update_data:
        return {"ok": True, "mensaje": "NO SE DETECTARON CAMBIOS."}

    set_clause         = ", ".join([f"{k} = :{k}" for k in update_data])
    update_data["eid"] = emisor_id

    try:
        await db.execute(
            text(f"UPDATE emisores SET {set_clause}, updated_at = NOW() WHERE id = :eid"),
            update_data
        )
        await audit_log(
            db        = db,
            auth_data = auth_data,
            accion    = "UPDATE",
            entidad   = "config",
            entidad_id = str(emisor_id),
            detalle   = data.model_dump(exclude_none=True),
            request   = request,
        )
        await db.commit()
        await invalidate_emisor(emisor_id)
        return {"ok": True, "mensaje": "CONFIGURACIÓN ACTUALIZADA CORRECTAMENTE."}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail="ERROR INTERNO AL ACTUALIZAR.")

# ── POST /produccion ───────────────────────────────────────────────────────────
@router.post("/produccion", summary="Activar ambiente de producción")
async def activar_produccion(
    pin:       str,
    request:   Request,
    auth_data: dict         = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db),
):
    emisor_id = auth_data.get("emisor_id")
    if not emisor_id:
        raise HTTPException(status_code=400, detail="EL USUARIO NO TIENE UN EMISOR VINCULADO.")
    verificar_admin(auth_data)

    res = await db.execute(text("""
        SELECT ruc, ambiente, p12_path, p12_expiration FROM emisores WHERE id = :eid
    """), {"eid": emisor_id})
    emisor = res.fetchone()
    if not emisor:
        raise HTTPException(status_code=404, detail="EMISOR NO ENCONTRADO.")
    if emisor.ambiente == 2:
        raise HTTPException(status_code=400, detail="TU CUENTA YA ESTÁ EN PRODUCCIÓN.")
    if not emisor.p12_path:
        raise HTTPException(status_code=400, detail="CONFIGURA TU FIRMA ANTES DE PASAR A PRODUCCIÓN.")
    if not emisor.p12_expiration or emisor.p12_expiration <= date.today():
        raise HTTPException(status_code=400, detail="TU FIRMA ELECTRÓNICA ESTÁ VENCIDA O NO VERIFICADA.")

    await validar_y_quemar_pin(db, emisor_id, pin, "ACTIVAR_PRODUCCION")

    try:
        from app.workers.declaraciones_worker import calcular_vencimiento

        await db.execute(text("""
            UPDATE user_credits SET balance = 25, last_updated = NOW() WHERE emisor_id = :eid
        """), {"eid": emisor_id})
        await db.execute(text("""
            INSERT INTO credit_transactions (emisor_id, tipo, cantidad, precio_total, metodo_pago, notas)
            VALUES (:eid, 'BONO', 25, 0.00, 'SISTEMA', 'BONO DE BIENVENIDA A PRODUCCIÓN')
        """), {"eid": emisor_id})
        await db.execute(text("""
            UPDATE emisores SET ambiente = 2, updated_at = NOW() WHERE id = :eid
        """), {"eid": emisor_id})

        hoy            = date.today()
        periodo_inicio = date(hoy.year, hoy.month, 1)
        vencimiento    = calcular_vencimiento(emisor.ruc, periodo_inicio)
        await db.execute(text("""
            INSERT INTO declaraciones_sri (emisor_id, tipo, periodo, vencimiento, declarado)
            VALUES (:eid, '104', :periodo, :vencimiento, false)
            ON CONFLICT (emisor_id, tipo, periodo) DO NOTHING
        """), {"eid": emisor_id, "periodo": periodo_inicio, "vencimiento": vencimiento})

        await audit_log(
            db        = db,
            auth_data = auth_data,
            accion    = "ACTIVATE",
            entidad   = "config",
            entidad_id = str(emisor_id),
            detalle   = {
                "ambiente_anterior": 1,
                "ambiente_nuevo":    2,
                "ruc":               emisor.ruc,
            },
            request   = request,
        )
        await db.commit()
        await invalidate_emisor(emisor_id)

        try:
            from app.services.notification_service import crear_notificacion
            await crear_notificacion(
                db        = db,
                emisor_id = emisor_id,
                tipo      = "SISTEMA",
                titulo    = "🎉 ¡Bienvenido a Producción!",
                mensaje   = f"Tu cuenta está lista. Tienes 25 créditos y tu primera declaración vence el {vencimiento.strftime('%d de %B')}.",
                referencia = "/dashboard",
            )
        except Exception as e:
            print(f"[PRODUCCION] ⚠️ No se pudo notificar: {e}")

    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail="ERROR AL ACTIVAR PRODUCCIÓN.")

    return {
        "ok":      True,
        "mensaje": "¡BIENVENIDO A PRODUCCIÓN! TU CUENTA ESTÁ LISTA PARA EMITIR FACTURAS REALES.",
        "data":    {"ambiente": 2, "balance_api": 25}
    }