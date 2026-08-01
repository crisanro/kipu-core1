# app/api/v1/app/emisor.py
import time
import httpx
import base64
import os
import re
import unicodedata
from datetime import datetime, date
from fastapi import APIRouter, Depends, Form, UploadFile, File, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import verify_firebase_token
from app.schemas.emisor import OnboardingRequest, EmisorUpdate
from app.services.storage_service import upload_file, delete_folder
from app.utils.crypto import encrypt_password
from app.core.cache import cache_get, cache_set, cache_delete, invalidate_emisor, CK, TTL
from app.core.rate_limit import RateLimit, RateLimitScope
from app.core.security import validar_y_quemar_pin
from app.core.config import settings


router = APIRouter()

NODE_VALIDATOR_URL = f"{settings.NODE_SIGNER_URL}/api/validar-p12"


# ── Validación RUC ─────────────────────────────────────────────────────────────

def validar_ruc_ecuador(ruc: str):
    ruc = ruc.strip()
    if not ruc.isdigit() or len(ruc) != 13:
        return False, "El RUC debe tener exactamente 13 dígitos numéricos."
    if not ruc.endswith("001"):
        return False, "El RUC debe terminar en 001."
    provincia = int(ruc[0:2])
    if provincia < 1 or provincia > 24:
        return False, "Los dos primeros dígitos (provincia) son inválidos."
    tercer_digito = int(ruc[2])

    if tercer_digito < 6:
        coeficientes = [2, 1, 2, 1, 2, 1, 2, 1, 2]
        digitos = [int(x) for x in ruc[:9]]
        suma = 0
        for i, d in enumerate(digitos):
            p = d * coeficientes[i]
            suma += p if p < 10 else p - 9
        verificador = 0 if suma % 10 == 0 else 10 - (suma % 10)
        if verificador != int(ruc[9]):
            return False, "El número de cédula base del RUC es incorrecto."
    elif tercer_digito == 9:
        coeficientes = [4, 3, 2, 7, 6, 5, 4, 3, 2]
        digitos = [int(x) for x in ruc[:9]]
        suma = sum(d * coeficientes[i] for i, d in enumerate(digitos))
        verificador = 0 if suma % 11 == 0 else 11 - (suma % 11)
        if verificador != int(ruc[9]):
            return False, "El RUC jurídico no supera la validación de módulo 11."
    elif tercer_digito == 6:
        coeficientes = [3, 2, 7, 6, 5, 4, 3, 2]
        digitos = [int(x) for x in ruc[:8]]
        suma = sum(d * coeficientes[i] for i, d in enumerate(digitos))
        verificador = 0 if suma % 11 == 0 else 11 - (suma % 11)
        if verificador != int(ruc[8]):
            return False, "El RUC público no supera la validación de módulo 11."
    else:
        return False, "El tercer dígito del RUC es inválido."
    return True, ""


def mayusculas(texto: str | None) -> str | None:
    """Convierte a mayúsculas, elimina tildes y caracteres especiales."""
    if not texto or not texto.strip():
        return None
    # Normalizar y eliminar diacríticos
    texto = unicodedata.normalize("NFD", texto.strip().upper())
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    # Solo letras, números y símbolos básicos permitidos por SRI
    texto = re.sub(r"[^A-Z0-9\s\.\,\-\/\#\&]", "", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto if texto else None

# ── POST /onboarding ───────────────────────────────────────────────────────────

@router.post("/onboarding", summary="Registro inicial (Onboarding)", status_code=201)
async def onboarding(
    data: OnboardingRequest,
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db),
    _rl: None = Depends(RateLimit(RateLimitScope.AUTH, use_ip=True)),
):
    if auth_data.get("emisor_id"):
        return {"ok": False, "mensaje": "Tu cuenta ya tiene una empresa vinculada."}

    es_valido, mensaje_error = validar_ruc_ecuador(data.ruc)
    if not es_valido:
        raise HTTPException(status_code=400, detail=mensaje_error)

    try:
        razon_social_up     = mayusculas(data.razon_social)
        nombre_comercial_up = mayusculas(data.nombre_comercial)
        direccion_up        = mayusculas(data.direccion_matriz)

        res_emisor = await db.execute(text("""
            INSERT INTO emisores (
                ruc, razon_social, nombre_comercial,
                direccion_matriz, obligado_contabilidad, contribuyente_especial, ambiente
            )
            VALUES (:ruc, :rs, :nc, :dir, :obl, :ce, 1)
            RETURNING id
        """), {
            "ruc": data.ruc, "rs": razon_social_up, "nc": nombre_comercial_up,
            "dir": direccion_up, "obl": (data.obligado_contabilidad or 'NO').upper(),
            "ce":  (data.contribuyente_especial or '').upper(),
        })
        new_emisor_id = res_emisor.scalar()

        full_name_up = mayusculas(data.full_name or data.razon_social)
        
        # Verificar si ya tiene perfil (puede venir de una invitación)
        res_profile = await db.execute(text("""
            SELECT id FROM profiles WHERE firebase_uid = :uid
        """), {"uid": auth_data["uid"]})
        perfil = res_profile.fetchone()

        if perfil:
            profile_id = perfil.id
        else:
            res_new_profile = await db.execute(text("""
                INSERT INTO profiles (firebase_uid, email, full_name, role)
                VALUES (:uid, :email, :fname, 'admin')
                RETURNING id
            """), {
                "uid":   auth_data["uid"],
                "email": auth_data["email"].lower(),
                "fname": full_name_up,
            })
            profile_id = res_new_profile.scalar()

        # Vincular profile con empresa
        await db.execute(text("""
            INSERT INTO emisor_usuarios (emisor_id, profile_id, rol)
            VALUES (:eid, :pid, 'admin')
        """), {"eid": new_emisor_id, "pid": str(profile_id)})

        # Asignar créditos iniciales y registrar transacción
        await db.execute(text("""
            INSERT INTO user_credits (emisor_id, balance_emision, balance_recepcion)
            VALUES (:eid, 10, 0)
        """), {"eid": new_emisor_id})

        await db.execute(text("""
            INSERT INTO credit_transactions
                (emisor_id, tipo, cantidad, precio_total, metodo_pago, notas)
            VALUES (:eid, 'BONO', 10, 0.00, 'SISTEMA', 'REGALO POR APERTURA DE CUENTA')
        """), {"eid": new_emisor_id})

        await db.commit()
        return {"ok": True, "mensaje": "EMPRESA Y PERFIL CONFIGURADOS CORRECTAMENTE.", "emisor_id": new_emisor_id}

    except Exception as e:
        await db.rollback()
        import traceback; traceback.print_exc()
        error_str = str(e).lower()
        if "unique" in error_str or "duplicate" in error_str or "23505" in error_str:
            if "emisores_ruc_key" in str(e):
                raise HTTPException(status_code=400, detail="EL RUC INGRESADO YA ESTÁ REGISTRADO EN KIPU.")
            if "profiles_firebase_uid" in str(e):
                raise HTTPException(status_code=400, detail="ESTE USUARIO YA TIENE UNA CUENTA CONFIGURADA.")
            raise HTTPException(status_code=400, detail="YA EXISTE UN REGISTRO CON ESOS DATOS.")
        raise HTTPException(status_code=500, detail="ERROR INTERNO AL PROCESAR EL REGISTRO.")
# ── POST /firma ────────────────────────────────────────────────────────────────

@router.post("/firma", summary="Subir firma electrónica (P12)")
async def upload_p12(
    password: str = Form(...),
    file: UploadFile = File(...),
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db),
    _rl: None = Depends(RateLimit(RateLimitScope.AUTH)),
):
    emisor_id = auth_data.get("emisor_id")
    if not emisor_id:
        raise HTTPException(status_code=400, detail="EL USUARIO NO TIENE UN EMISOR VINCULADO.")

    res_emisor = await db.execute(
        text("SELECT ruc, p12_path FROM emisores WHERE id = :eid"), {"eid": emisor_id}
    )
    emisor = res_emisor.fetchone()
    if not emisor:
        raise HTTPException(status_code=404, detail="EMISOR NO ENCONTRADO.")

    if not file.filename.lower().endswith('.p12'):
        raise HTTPException(status_code=400, detail="EL ARCHIVO DEBE SER UN FORMATO .P12 VÁLIDO.")

    file_bytes = await file.read()
    p12_base64 = base64.b64encode(file_bytes).decode('utf-8')

    async with httpx.AsyncClient() as client:
        try:
            res_node = await client.post(
                NODE_VALIDATOR_URL,
                json={"p12Base64": p12_base64, "password": password, "ruc": emisor.ruc},
                timeout=20.0
            )
            val = res_node.json()
        except Exception as e:
            print(f"❌ Error conexión Node.js: {str(e)}")
            raise HTTPException(status_code=500, detail="ERROR AL CONECTAR CON EL VALIDADOR.")

    if not val.get("ok"):
        raise HTTPException(status_code=400, detail=val.get("mensaje", "CERTIFICADO INVÁLIDO.").upper())

    try:
        if emisor.p12_path:
            try:
                delete_folder(f"{emisor.ruc}/firmas/")
            except:
                pass

        # Nombre con timestamp para evitar conflictos de caché en R2
        p12_filename      = f"firma_{emisor.ruc}_{int(time.time())}.p12"
        p12_path_completo = f"{emisor.ruc}/firmas/{p12_filename}"
        upload_file(p12_path_completo, file_bytes, "application/x-pkcs12")

        pass_enc = encrypt_password(password)

        # Manejo robusto de fecha — el validador puede retornar en diferentes campos
        raw_exp = val.get("expiracion") or val.get("expiration") or val.get("datos", {}).get("vence")
        if not raw_exp:
            raise ValueError("No se encontró la fecha de expiración en la respuesta del validador.")
        fecha_objeto = datetime.strptime(str(raw_exp)[:10], '%Y-%m-%d').date()

        await db.execute(text("""
            UPDATE emisores
            SET p12_path = :path, p12_pass = :pass, p12_expiration = :exp, updated_at = NOW()
            WHERE id = :eid
        """), {"path": p12_path_completo, "pass": pass_enc, "exp": fecha_objeto, "eid": emisor_id})

        await db.commit()
        await invalidate_emisor(emisor_id)

        return {"ok": True, "mensaje": "FIRMA ELECTRÓNICA CONFIGURADA CORRECTAMENTE.", "expiracion": str(fecha_objeto)}

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        print(f"❌ ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail="ERROR AL GUARDAR LA FIRMA.")


# ── DELETE /firma ──────────────────────────────────────────────────────────────

@router.delete("/firma", summary="Eliminar firma electrónica")
async def remove_p12(
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db),
):
    emisor_id = auth_data.get("emisor_id")
    if not emisor_id:
        raise HTTPException(status_code=400, detail="EL USUARIO NO TIENE UN EMISOR VINCULADO.")

    res = await db.execute(
        text("SELECT ruc, p12_path FROM emisores WHERE id = :eid"), {"eid": emisor_id}
    )
    emisor = res.fetchone()
    if not emisor:
        raise HTTPException(status_code=404, detail="EMISOR NO ENCONTRADO.")

    try:
        if emisor.p12_path:
            try:
                delete_folder(f"{emisor.ruc}/firmas/")
                print(f"🗑️ Carpeta firmas eliminada para RUC: {emisor.ruc}")
            except Exception as e:
                print(f"⚠️ No se pudo eliminar carpeta firmas: {str(e)}")

        await db.execute(text("""
            UPDATE emisores
            SET p12_path = NULL, p12_pass = NULL, p12_expiration = NULL, updated_at = NOW()
            WHERE id = :eid
        """), {"eid": emisor_id})
        await db.commit()
        await invalidate_emisor(emisor_id)

        return {"ok": True, "mensaje": "LA FIRMA ELECTRÓNICA Y SUS DATOS HAN SIDO ELIMINADOS CORRECTAMENTE."}

    except Exception as e:
        await db.rollback()
        print(f"❌ ERROR AL ELIMINAR FIRMA: {str(e)}")
        raise HTTPException(status_code=500, detail="ERROR INTERNO AL INTENTAR ELIMINAR LOS DATOS DE LA FIRMA.")


# ── GET /config — CON CACHE ────────────────────────────────────────────────────

@router.get("/config", summary="Obtener configuración fiscal y de firma")
async def get_config(
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db),
):
    emisor_id = auth_data.get("emisor_id")
    if not emisor_id:
        return {"ok": True, "configurado": False, "mensaje": "Pendiente de configuración inicial (Onboarding)."}

    # ── Cache hit ──
    cache_key = CK.fmt(CK.EMISOR, eid=emisor_id)
    cached = await cache_get(cache_key)
    if cached:
        return cached

    # JOIN con user_credits en una sola query
    res = await db.execute(text("""
        SELECT
            e.ruc, e.razon_social, e.nombre_comercial, e.direccion_matriz,
            e.contribuyente_especial, e.obligado_contabilidad, e.ambiente,
            e.p12_path, e.p12_expiration, e.created_at,
            e.ws_establecimiento, e.ws_punto_emision,
            c.balance_emision, c.balance_recepcion
        FROM emisores e
        LEFT JOIN user_credits c ON c.emisor_id = e.id
        WHERE e.id = :eid
    """), {"eid": emisor_id})
    data = res.fetchone()
    if not data:
        raise HTTPException(status_code=404, detail="EMISOR NO ENCONTRADO.")

    expiracion   = data.p12_expiration
    nombre_firma = data.p12_path.split('/')[-1] if data.p12_path else 'No configurada'
    firma_info   = {
        "configurada":         bool(data.p12_path),
        "nombre":              nombre_firma,
        "expiracion":          expiracion,
        "estado":              'PENDIENTE',
        "mensaje_vencimiento": 'Firma no cargada'
    }
    if expiracion:
        hoy            = datetime.utcnow().date()
        dias_restantes = (expiracion - hoy).days
        fecha_fmt      = expiracion.strftime("%d/%m/%Y")
        if dias_restantes <= 0:
            firma_info.update({"estado": 'EXPIRADA',  "mensaje_vencimiento": f"Expirada el {fecha_fmt}"})
        elif dias_restantes <= 30:
            firma_info.update({"estado": 'ALERTA',    "mensaje_vencimiento": f"Próxima a vencer ({dias_restantes} días)"})
        else:
            firma_info.update({"estado": 'VIGENTE',   "mensaje_vencimiento": f"Vigente hasta el {fecha_fmt}"})

    ws_configurado = bool(data.ws_establecimiento and data.ws_punto_emision)
    whatsapp_info  = {
        "configurado":     ws_configurado,
        "establecimiento": data.ws_establecimiento if ws_configurado else None,
        "punto_emision":   data.ws_punto_emision   if ws_configurado else None,
    }

    _excluir = {"p12_path", "p12_expiration", "ws_establecimiento", "ws_punto_emision"}
    legal_data = {k: v for k, v in data._mapping.items() if k not in _excluir}

    response = {
        "ok":          True,
        "configurado": True,
        "data": {
            "legal":    legal_data,
            "firma":    firma_info,
            "whatsapp": whatsapp_info,
            "creditos": {
                "balance_emision":   data.balance_emision,
                "balance_recepcion": data.balance_recepcion,
            }
        }
    }

    await cache_set(cache_key, response, TTL.EMISOR_PERFIL)
    return response


# ── PATCH /config ──────────────────────────────────────────────────────────────

@router.patch("/config", summary="Actualizar configuración del emisor")
async def update_config(
    data: EmisorUpdate,
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db),
):
    emisor_id = auth_data.get("emisor_id")
    if not emisor_id:
        raise HTTPException(status_code=400, detail="EL USUARIO NO TIENE UN EMISOR VINCULADO.")

    update_data = {}
    for k, v in data.model_dump().items():
        if v is None:
            continue
        update_data[k] = mayusculas(v) if isinstance(v, str) else v

    if not update_data:
        return {"ok": True, "mensaje": "NO SE DETECTARON CAMBIOS POR APLICAR."}

    set_clause = ", ".join([f"{k} = :{k}" for k in update_data.keys()])
    update_data["eid"] = emisor_id

    try:
        await db.execute(
            text(f"UPDATE emisores SET {set_clause}, updated_at = NOW() WHERE id = :eid"),
            update_data
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
    pin: str,
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db),
):
    emisor_id = auth_data.get("emisor_id")
    if not emisor_id:
        raise HTTPException(status_code=400, detail="EL USUARIO NO TIENE UN EMISOR VINCULADO.")

    res = await db.execute(text("""
        SELECT ruc, ambiente, p12_path, p12_expiration FROM emisores WHERE id = :eid
    """), {"eid": emisor_id})
    emisor = res.fetchone()

    if not emisor:
        raise HTTPException(status_code=404, detail="EMISOR NO ENCONTRADO.")
    if emisor.ambiente == 2:
        raise HTTPException(status_code=400, detail="TU CUENTA YA ESTÁ EN AMBIENTE DE PRODUCCIÓN. ESTA ACCIÓN NO SE PUEDE REVERTIR.")
    if not emisor.p12_path:
        raise HTTPException(status_code=400, detail="DEBES CONFIGURAR TU FIRMA ELECTRÓNICA ANTES DE PASAR A PRODUCCIÓN.")
    if not emisor.p12_expiration:
        raise HTTPException(status_code=400, detail="NO SE PUDO VERIFICAR LA VIGENCIA DE TU FIRMA ELECTRÓNICA.")
    if emisor.p12_expiration <= date.today():
        raise HTTPException(status_code=400, detail="TU FIRMA ELECTRÓNICA ESTÁ VENCIDA. RENUÉVALA ANTES DE PASAR A PRODUCCIÓN.")

    # ── Validar PIN de WhatsApp — siempre obligatorio ─────────────────────────
    await validar_y_quemar_pin(db, emisor_id, pin, "ACTIVAR_PRODUCCION")

    try:
        await db.execute(text("DELETE FROM invoices_emitidas WHERE emisor_id = :eid"), {"eid": emisor_id})
        await db.execute(text("UPDATE puntos_emision SET secuencial_actual = 0 WHERE emisor_id = :eid"), {"eid": emisor_id})
        await db.execute(text("""
            UPDATE user_credits SET balance_emision = 25, balance_recepcion = 0, last_updated = NOW()
            WHERE emisor_id = :eid
        """), {"eid": emisor_id})
        await db.execute(text("""
            INSERT INTO credit_transactions (emisor_id, tipo, cantidad, precio_total, metodo_pago, notas)
            VALUES (:eid, 'BONO', 25, 0.00, 'SISTEMA', 'BONO DE BIENVENIDA A PRODUCCIÓN — CRÉDITOS DE EMISIÓN')
        """), {"eid": emisor_id})
        await db.execute(text("UPDATE emisores SET ambiente = 2, updated_at = NOW() WHERE id = :eid"), {"eid": emisor_id})
        await db.commit()
        await invalidate_emisor(emisor_id)

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail="ERROR AL ACTIVAR PRODUCCIÓN. INTENTA NUEVAMENTE.")

    try:
        delete_folder(f"{emisor.ruc}/facturas/")
        print(f"[PRODUCCION] 🗑️ Carpeta facturas eliminada para RUC: {emisor.ruc}")
    except Exception as e_r2:
        print(f"[PRODUCCION] ⚠️ No se pudo limpiar R2 (no crítico): {e_r2}")

    return {
        "ok":      True,
        "mensaje": "¡BIENVENIDO A PRODUCCIÓN! TU CUENTA ESTÁ LISTA PARA EMITIR FACTURAS REALES.",
        "data":    {"ambiente": 2, "balance_emision": 25, "balance_recepcion": 0}
    }