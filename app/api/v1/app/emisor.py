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

# ── Helpers ──────────────────────────────────────────────────────────────────

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
    if not texto or not texto.strip():
        return None
    texto = unicodedata.normalize("NFD", texto.strip().upper())
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
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
    es_valido, mensaje_error = validar_ruc_ecuador(data.ruc)
    if not es_valido:
        raise HTTPException(status_code=400, detail=mensaje_error)

    try:
        # Verificar si el perfil existe y si ya tiene una empresa en pruebas
        res_profile = await db.execute(text("SELECT id FROM profiles WHERE firebase_uid = :uid"), {"uid": auth_data["uid"]})
        perfil = res_profile.fetchone()

        if perfil:
            profile_id = perfil.id
            # VALIDACIÓN: Solo una empresa en modo pruebas (ambiente = 1)
            res_pruebas = await db.execute(text("""
                SELECT COUNT(*) FROM emisor_usuarios eu
                JOIN emisores e ON e.id = eu.emisor_id
                WHERE eu.profile_id = :pid AND e.ambiente = 1
            """), {"pid": str(profile_id)})
            if res_pruebas.scalar() > 0:
                raise HTTPException(status_code=400, detail="Ya tienes una empresa en modo pruebas. Solo puedes tener una en este ambiente.")
        else:
            profile_id = None

        razon_social_up     = mayusculas(data.razon_social)
        nombre_comercial_up = mayusculas(data.nombre_comercial)
        direccion_up        = mayusculas(data.direccion_matriz)

        res_emisor = await db.execute(text("""
            INSERT INTO emisores (ruc, razon_social, nombre_comercial, direccion_matriz, obligado_contabilidad, contribuyente_especial, ambiente)
            VALUES (:ruc, :rs, :nc, :dir, :obl, :ce, 1)
            RETURNING id
        """), {
            "ruc": data.ruc, "rs": razon_social_up, "nc": nombre_comercial_up,
            "dir": direccion_up, "obl": (data.obligado_contabilidad or 'NO').upper(),
            "ce":  (data.contribuyente_especial or '').upper(),
        })
        new_emisor_id = res_emisor.scalar()

        if not profile_id:
            res_new_profile = await db.execute(text("""
                INSERT INTO profiles (firebase_uid, email, full_name, role)
                VALUES (:uid, :email, :fname, 'admin') RETURNING id
            """), {
                "uid": auth_data["uid"], "email": auth_data["email"].lower(),
                "fname": mayusculas(data.full_name or data.razon_social),
            })
            profile_id = res_new_profile.scalar()

        await db.execute(text("INSERT INTO emisor_usuarios (emisor_id, profile_id, rol) VALUES (:eid, :pid, 'admin')"), 
                         {"eid": new_emisor_id, "pid": str(profile_id)})

        await db.execute(text("INSERT INTO user_credits (emisor_id, balance_emision, balance_recepcion) VALUES (:eid, 10, 0)"), {"eid": new_emisor_id})
        await db.execute(text("INSERT INTO credit_transactions (emisor_id, tipo, cantidad, precio_total, metodo_pago, notas) VALUES (:eid, 'BONO', 10, 0.00, 'SISTEMA', 'REGALO POR APERTURA')"), {"eid": new_emisor_id})

        await db.commit()
        return {"ok": True, "mensaje": "EMPRESA Y PERFIL CONFIGURADOS.", "emisor_id": new_emisor_id}

    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail="ERROR AL PROCESAR EL REGISTRO.")

# ── POST /invitar (NUEVO) ──────────────────────────────────────────────────────

@router.post("/invitar", summary="Invitar usuario a empresa en producción")
async def invitar_usuario(
    email: str,
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db),
):
    emisor_id = auth_data.get("emisor_id")
    if not emisor_id:
        raise HTTPException(status_code=400, detail="USUARIO SIN EMPRESA.")

    # VALIDACIÓN: Solo invitar si está en producción (ambiente = 2)
    res_amb = await db.execute(text("SELECT ambiente FROM emisores WHERE id = :eid"), {"eid": emisor_id})
    if res_amb.scalar() != 2:
        raise HTTPException(status_code=400, detail="Solo puedes invitar usuarios cuando la empresa esté en producción.")

    # ... (Aquí iría tu lógica de creación de invitación en la tabla `invitaciones`)
    return {"ok": True, "mensaje": "Invitación enviada."}

# ── DELETE /usuario/{profile_id} (PROTECCIÓN DE ADMIN) ──────────────────────────

@router.delete("/usuario/{pid}", summary="Remover usuario de la empresa")
async def remover_usuario(
    pid: str,
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db),
):
    emisor_id = auth_data.get("emisor_id")
    
    # Verificar rol del usuario a eliminar
    res_target = await db.execute(text("SELECT rol FROM emisor_usuarios WHERE emisor_id = :eid AND profile_id = :pid"), 
                                 {"eid": emisor_id, "pid": pid})
    target = res_target.fetchone()
    
    if not target:
        raise HTTPException(status_code=404, detail="Usuario no encontrado en esta empresa.")

    if target.rol == 'admin':
        # VALIDACIÓN: No remover el único administrador
        res_admins = await db.execute(text("SELECT COUNT(*) FROM emisor_usuarios WHERE emisor_id = :eid AND rol = 'admin'"), 
                                     {"eid": emisor_id})
        if res_admins.scalar() <= 1:
            raise HTTPException(status_code=400, detail="No puedes remover el único administrador.")

    await db.execute(text("DELETE FROM emisor_usuarios WHERE emisor_id = :eid AND profile_id = :pid"), {"eid": emisor_id, "pid": pid})
    await db.commit()
    return {"ok": True, "mensaje": "Usuario removido."}

# ── (Resto de métodos existentes: /firma, /config, /produccion...) ───────────

@router.post("/firma", summary="Subir firma electrónica (P12)")
async def upload_p12(password: str = Form(...), file: UploadFile = File(...), auth_data: dict = Depends(verify_firebase_token), db: AsyncSession = Depends(get_db)):
    emisor_id = auth_data.get("emisor_id")
    if not emisor_id: raise HTTPException(status_code=400, detail="EMISOR NO VINCULADO.")
    
    res_emisor = await db.execute(text("SELECT ruc, p12_path FROM emisores WHERE id = :eid"), {"eid": emisor_id})
    emisor = res_emisor.fetchone()
    if not emisor: raise HTTPException(status_code=404, detail="EMISOR NO ENCONTRADO.")
    
    if not file.filename.lower().endswith('.p12'): raise HTTPException(status_code=400, detail="FORMATO .P12 INVÁLIDO.")
    
    file_bytes = await file.read()
    p12_base64 = base64.b64encode(file_bytes).decode('utf-8')

    async with httpx.AsyncClient() as client:
        res_node = await client.post(NODE_VALIDATOR_URL, json={"p12Base64": p12_base64, "password": password, "ruc": emisor.ruc}, timeout=20.0)
        val = res_node.json()

    if not val.get("ok"): raise HTTPException(status_code=400, detail=val.get("mensaje", "CERTIFICADO INVÁLIDO.").upper())

    try:
        if emisor.p12_path: delete_folder(f"{emisor.ruc}/firmas/")
        p12_filename = f"firma_{emisor.ruc}_{int(time.time())}.p12"
        p12_path = f"{emisor.ruc}/firmas/{p12_filename}"
        upload_file(p12_path, file_bytes, "application/x-pkcs12")
        
        pass_enc = encrypt_password(password)
        raw_exp = val.get("expiracion") or val.get("expiration") or val.get("datos", {}).get("vence")
        fecha_exp = datetime.strptime(str(raw_exp)[:10], '%Y-%m-%d').date()

        await db.execute(text("UPDATE emisores SET p12_path = :path, p12_pass = :pass, p12_expiration = :exp WHERE id = :eid"), 
                         {"path": p12_path, "pass": pass_enc, "exp": fecha_exp, "eid": emisor_id})
        await db.commit()
        await invalidate_emisor(emisor_id)
        return {"ok": True, "mensaje": "FIRMA CONFIGURADA."}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail="ERROR AL GUARDAR FIRMA.")