# app/api/v1/app/emisor.py
import time
import httpx
import base64
import os
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Form, UploadFile, File, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from firebase_admin import auth

from app.core.database import get_db
from app.core.security import verify_firebase_token
from app.schemas.emisor import OnboardingRequest, EmisorUpdate
from app.services.storage_service import upload_file, delete_file, path_firma
from app.utils.crypto import encrypt_password

router = APIRouter()

#NODE_VALIDATOR_URL = os.getenv("NODE_VALIDATOR_URL", "http://localhost:3000/api/validar-p12")
NODE_VALIDATOR_URL = "http://localhost:3000/api/validar-p12"


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


# =============================================================================
# ONBOARDING
# =============================================================================

@router.post("/onboarding", summary="Registro inicial (Onboarding)", status_code=201)
async def onboarding(
    data: OnboardingRequest,
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db)
):
    if auth_data.get("emisor_id"):
        return {"ok": False, "mensaje": "Tu cuenta ya tiene una empresa vinculada."}

    # Verificar que el email esté verificado en Firebase
    try:
        user_record = auth.get_user_by_email(auth_data["email"])
        if not user_record.email_verified:
            raise HTTPException(
                status_code=403,
                detail="Debes verificar tu correo electrónico antes de completar el registro."
            )
    except auth.UserNotFoundError:
        raise HTTPException(status_code=404, detail="Usuario no encontrado en Firebase.")

    es_valido, mensaje_error = validar_ruc_ecuador(data.ruc)
    if not es_valido:
        raise HTTPException(status_code=400, detail=mensaje_error)

    try:
        razon_social_up     = data.razon_social.upper()
        nombre_comercial_up = (data.nombre_comercial or data.razon_social).upper()
        direccion_up        = data.direccion_matriz.upper()

        # 1. Crear emisor
        res_emisor = await db.execute(text("""
            INSERT INTO emisores (
                ruc, razon_social, nombre_comercial,
                direccion_matriz, obligado_contabilidad, contribuyente_especial, ambiente
            )
            VALUES (:ruc, :rs, :nc, :dir, :obl, :ce, 1)
            RETURNING id
        """), {
            "ruc": data.ruc,
            "rs":  razon_social_up,
            "nc":  nombre_comercial_up,
            "dir": direccion_up,
            "obl": (data.obligado_contabilidad or 'NO').upper(),
            "ce":  (data.contribuyente_especial or '').upper()
        })
        new_emisor_id = res_emisor.scalar()

        # 2. Crear perfil
        full_name_up = (data.full_name if data.full_name else data.razon_social).upper()
        await db.execute(text("""
            INSERT INTO profiles (firebase_uid, emisor_id, email, full_name, role)
            VALUES (:uid, :eid, :email, :fname, 'admin')
        """), {
            "uid":   auth_data["uid"],
            "eid":   new_emisor_id,
            "email": auth_data["email"].lower(),
            "fname": full_name_up
        })

        # 3. Determinar tenant
        # Paso 1: buscar cualquier tenant registrado con espacio (< 200 emisores)
        res_tenant = await db.execute(text("""
            SELECT tenant_schema, COUNT(*) as total
            FROM public.emisor_tenant_map
            GROUP BY tenant_schema
            HAVING COUNT(*) < 200
            ORDER BY tenant_schema ASC
            LIMIT 1
        """))
        tenant_row = res_tenant.fetchone()

        if tenant_row:
            # Hay espacio en un tenant existente — asignar directamente
            tenant_schema = tenant_row.tenant_schema

        else:
            # Paso 2: ninguno disponible — calcular el siguiente número
            res_ultimo = await db.execute(text("""
                SELECT tenant_schema
                FROM public.emisor_tenant_map
                GROUP BY tenant_schema
                ORDER BY tenant_schema DESC
                LIMIT 1
            """))
            ultimo = res_ultimo.fetchone()

            if ultimo:
                ultimo_num    = int(ultimo.tenant_schema.replace('tenant_', ''))
                tenant_schema = f'tenant_{str(ultimo_num + 1).zfill(3)}'
            else:
                tenant_schema = 'tenant_001'

            # Paso 3: verificar si el schema existe físicamente en Postgres
            res_existe = await db.execute(text("""
                SELECT schema_name FROM information_schema.schemata
                WHERE schema_name = :schema
            """), {"schema": tenant_schema})

            if res_existe.fetchone():
                # El schema existe pero no está en el mapa — reutilizar
                print(f"ℹ️ Tenant {tenant_schema} existe, reutilizando.")
            else:
                # No existe — crear schema con todas sus tablas
                await db.execute(text(f"SELECT kipu_create_tenant('{tenant_schema}')"))
                print(f"✅ Nuevo tenant creado: {tenant_schema}")

        # 4. Registrar emisor en el mapa de tenants
        await db.execute(text("""
            INSERT INTO public.emisor_tenant_map (emisor_id, tenant_schema)
            VALUES (:eid, :schema)
        """), {"eid": new_emisor_id, "schema": tenant_schema})

        # 5. Créditos de bienvenida: 10 emisión + 5 recepción
        await db.execute(text("""
            INSERT INTO public.user_credits (emisor_id, balance_emision, balance_recepcion)
            VALUES (:eid, 10, 5)
        """), {"eid": new_emisor_id})

        await db.execute(text("""
            INSERT INTO public.credit_transactions
                (emisor_id, tipo, cantidad, precio_total, metodo_pago, notas)
            VALUES
                (:eid, 'BONUS_EMISION',    10, 0.00, 'SISTEMA', 'REGALO POR APERTURA DE CUENTA'),
                (:eid, 'BONUS_RECEPCION',   5, 0.00, 'SISTEMA', 'BONO BIENVENIDA RECEPCIÓN')
        """), {"eid": new_emisor_id})

        await db.commit()

        return {
            "ok":        True,
            "mensaje":   "EMPRESA Y PERFIL CONFIGURADOS CORRECTAMENTE.",
            "emisor_id": new_emisor_id,
            "tenant":    tenant_schema
        }

    except Exception as e:
        await db.rollback()
        if "23505" in str(e):
            raise HTTPException(status_code=400, detail="EL RUC INGRESADO YA ESTÁ REGISTRADO.")
        raise HTTPException(status_code=500, detail="ERROR INTERNO AL PROCESAR EL REGISTRO.")
    

# =============================================================================
# FIRMA ELECTRÓNICA
# =============================================================================

@router.post("/firma", summary="Subir firma electrónica (P12)")
async def upload_p12(
    password: str = Form(...),
    file: UploadFile = File(...),
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db)
):
    emisor_id = auth_data.get("emisor_id")
    if not emisor_id:
        raise HTTPException(status_code=400, detail="EL USUARIO NO TIENE UN EMISOR VINCULADO.")

    res_emisor = await db.execute(
        text("SELECT ruc, p12_path FROM emisores WHERE id = :eid"),
        {"eid": emisor_id}
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

    p12_path_completo = None

    try:
        if emisor.p12_path:
            try:
                path_parts = emisor.p12_path.split('/')
                delete_file(path_parts[0], "/".join(path_parts[1:]))
            except:
                pass

        file_name = f"{emisor.ruc}/CERTIFICADO_{int(time.time()*1000)}.p12"
        p12_path_completo = upload_file(path_firma(emisor.ruc), file_bytes, 'application/x-pkcs12')

        pass_enc = encrypt_password(password)

        raw_exp = val.get("expiration") or val.get("datos", {}).get("vence")
        if not raw_exp:
            raise ValueError("No se encontró la fecha de expiración en la respuesta.")

        fecha_objeto = datetime.strptime(str(raw_exp)[:10], '%Y-%m-%d').date()

        await db.execute(text("""
            UPDATE public.emisores
            SET p12_path = :path, p12_pass = :pass, p12_expiration = :exp, updated_at = NOW()
            WHERE id = :eid
        """), {
            "path": p12_path_completo,
            "pass": pass_enc,
            "exp":  fecha_objeto,
            "eid":  emisor_id
        })

        await db.commit()
        return {"ok": True, "mensaje": "FIRMA VINCULADA CORRECTAMENTE."}

    except Exception as e:
        await db.rollback()
        print(f"❌ ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail="ERROR AL GUARDAR EN BASE DE DATOS.")


@router.delete("/firma", summary="Eliminar firma electrónica")
async def remove_p12(
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db)
):
    emisor_id = auth_data.get("emisor_id")
    if not emisor_id:
        raise HTTPException(status_code=400, detail="EL USUARIO NO TIENE UN EMISOR VINCULADO.")

    res = await db.execute(
        text("SELECT ruc, p12_path FROM emisores WHERE id = :eid"),
        {"eid": emisor_id}
    )
    emisor = res.fetchone()
    if not emisor:
        raise HTTPException(status_code=404, detail="EMISOR NO ENCONTRADO.")

    try:
        if emisor.p12_path:
            try:
                path_parts = emisor.p12_path.split('/')
                delete_file(path_parts[0], "/".join(path_parts[1:]))
                print(f"🗑️ Archivo P12 eliminado para el RUC: {emisor.ruc}")
            except Exception as e:
                print(f"⚠️ No se pudo eliminar el archivo físico: {str(e)}")

        await db.execute(text("""
            UPDATE emisores
            SET p12_path = NULL, p12_pass = NULL, p12_expiration = NULL, updated_at = NOW()
            WHERE id = :eid
        """), {"eid": emisor_id})

        await db.commit()
        return {"ok": True, "mensaje": "LA FIRMA ELECTRÓNICA Y SUS DATOS HAN SIDO ELIMINADOS CORRECTAMENTE."}

    except Exception as e:
        await db.rollback()
        print(f"❌ ERROR AL ELIMINAR FIRMA: {str(e)}")
        raise HTTPException(status_code=500, detail="ERROR INTERNO AL INTENTAR ELIMINAR LOS DATOS DE LA FIRMA.")


# =============================================================================
# CONFIGURACIÓN
# =============================================================================

@router.get("/config", summary="Obtener configuración fiscal y de firma")
async def get_config(
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db)
):
    # Usuario nuevo sin onboarding
    emisor_id = auth_data.get("emisor_id")
    if not emisor_id:
        return {"ok": True, "configurado": False, "mensaje": "Pendiente de configuración inicial (Onboarding)."}

    res = await db.execute(text("""
        SELECT ruc, razon_social, nombre_comercial, direccion_matriz, contribuyente_especial,
               obligado_contabilidad, ambiente, p12_path, p12_expiration, created_at
        FROM emisores WHERE id = :eid
    """), {"eid": emisor_id})
    data = res.fetchone()

    # Emisor_id existe en token pero no en DB
    if not data:
        return {"ok": True, "configurado": False, "mensaje": "Emisor no encontrado. Contacta soporte."}

    expiracion   = data.p12_expiration
    nombre_firma = data.p12_path.split('/')[-1] if data.p12_path else 'No configurada'

    firma_info = {
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

    return {
        "ok": True,
        "configurado": True,
        "data": {
            "legal": dict(data._mapping),
            "firma": firma_info
        }
    }


@router.patch("/config", summary="Actualizar configuración del emisor")
async def update_config(
    data: EmisorUpdate,
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db)
):
    emisor_id = auth_data.get("emisor_id")
    if not emisor_id:
        raise HTTPException(status_code=400, detail="EL USUARIO NO TIENE UN EMISOR VINCULADO.")

    update_data = {}
    for k, v in data.model_dump().items():
        if v is not None:
            update_data[k] = v.upper() if isinstance(v, str) else v

    if not update_data:
        return {"ok": True, "mensaje": "NO SE DETECTARON CAMBIOS POR APLICAR."}

    set_clause          = ", ".join([f"{k} = :{k}" for k in update_data.keys()])
    update_data["eid"]  = emisor_id

    try:
        await db.execute(
            text(f"UPDATE emisores SET {set_clause}, updated_at = NOW() WHERE id = :eid"),
            update_data
        )
        await db.commit()
        return {"ok": True, "mensaje": "CONFIGURACIÓN ACTUALIZADA CORRECTAMENTE."}

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail="ERROR INTERNO AL ACTUALIZAR.")