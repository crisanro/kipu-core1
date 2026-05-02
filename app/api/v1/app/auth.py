#app/api/v1/app/auth.py
import os
import random
import json
import hashlib
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from firebase_admin import auth

from app.core.database import get_db
from app.core.security import verify_firebase_token
from app.services.storage_service import  delete_folder
from app.services.mail_service import mail_service
from app.schemas.seguridad import ResetPasswordRequest, VerifyPinRequest, RequestPinSchema # Asegúrate de tener este schema

router = APIRouter()

# --- ENDPOINTS DE CORREO Y CUENTA ---

@router.post("/send-verification")
async def send_verification(
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db)
):
    email = auth_data["email"]

    # 1. Anti-spam: máximo 1 solicitud por minuto
    res = await db.execute(text("""
        SELECT last_sent FROM email_rate_limits
        WHERE email = :email AND last_sent > NOW() - INTERVAL '1 minute'
    """), {"email": email})

    if res.fetchone():
        raise HTTPException(
            status_code=429,
            detail="Ya enviamos un correo. Espera 1 minuto antes de solicitar otro."
        )

    # 2. Verificar estado en Firebase
    try:
        user_record = auth.get_user_by_email(email)
        if user_record.email_verified:
            raise HTTPException(status_code=400, detail="El correo ya fue verificado.")
    except auth.UserNotFoundError:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    # 3. Registrar intento ANTES de enviar
    await db.execute(text("""
        INSERT INTO email_rate_limits (email, last_sent)
        VALUES (:email, NOW())
        ON CONFLICT (email) DO UPDATE SET last_sent = NOW()
    """), {"email": email})
    await db.commit()

    # 4. Generar y enviar
    link = auth.generate_email_verification_link(
        email,
        auth.ActionCodeSettings(url="https://kipu.ec/login", handle_code_in_app=False)
    )
    html = f"""
        <h2>Bienvenido a Kipu 👋</h2>
        <p>Haz clic para verificar tu cuenta:</p>
        <a href='{link}' style='background:#4F46E5;color:white;padding:12px 24px;
        text-decoration:none;border-radius:6px;display:inline-block;'>
        Verificar cuenta</a>
        <p style='color:#666;font-size:12px;margin-top:16px;'>
        Si no solicitaste esto, ignora este correo.</p>
    """
    await mail_service.send_mail(
        to=email,
        subject="Verifica tu cuenta en Kipu",
        html_content=html
    )

    return {"ok": True, "mensaje": "Correo de verificación enviado."}


@router.post("/reset")
async def reset_password(data: ResetPasswordRequest):
    link = auth.generate_password_reset_link(data.email, auth.ActionCodeSettings(url="https://kipu.ec/login", handle_code_in_app=False))
    html = f"<h2>Recuperación</h2><p>Haz clic para restablecer:</p><a href='{link}'>Restablecer</a>"
    await mail_service.send_mail(to=data.email, subject="Recupera tu cuenta", html_content=html)
    return {"ok": True}

    
@router.post("/verify-pin")
async def verify_pin(data: VerifyPinRequest, auth_data: dict = Depends(verify_firebase_token), db: AsyncSession = Depends(get_db)):
    email = auth_data["email"]
    emisor_id = auth_data["emisor_id"]

    # FOR UPDATE para evitar race conditions
    query = text("""
        SELECT id, whatsapp_number, tipo_accion, metadata 
        FROM auth_challenges 
        WHERE LOWER(email) = LOWER(:email) AND pin = :pin AND expires_at > NOW()
        FOR UPDATE
    """)
    res = await db.execute(query, {"email": email, "pin": data.pin})
    challenge = res.fetchone()

    if not challenge:
        raise HTTPException(status_code=400, detail="PIN incorrecto o expirado.")

    # Lógica según acción
    if challenge.tipo_accion in ['VALIDACION_GENERAL', 'VALIDAR_WS']:
        await db.execute(text("UPDATE profiles SET whatsapp_number = :phone WHERE emisor_id = :eid"), 
                         {"phone": challenge.whatsapp_number, "eid": emisor_id})
    
    elif challenge.tipo_accion == 'ELIMINAR_TOKEN':
        if challenge.metadata and 'key_id' in challenge.metadata:
            await db.execute(text("UPDATE api_keys SET revoked = true, revoked_at = NOW() WHERE id = :kid AND emisor_id = :eid"), 
                             {"kid": challenge.metadata['key_id'], "eid": emisor_id})

    # Borrar PIN usado
    await db.execute(text("DELETE FROM auth_challenges WHERE id = :id"), {"id": challenge.id})
    await db.commit()

    return {"ok": True, "accion": challenge.tipo_accion}

# --- ELIMINACIÓN TOTAL (NUKE) ---

@router.delete("/nuke")
async def nuke_account(auth_data: dict = Depends(verify_firebase_token), db: AsyncSession = Depends(get_db)):
    eid = auth_data.get("emisor_id")
    uid = auth_data["uid"]
    
    try:
        if eid:
            # 1. Recuperar el RUC antes de borrar nada (Lo necesitamos para MinIO)
            res_emisor = await db.execute(
                text("SELECT ruc FROM emisores WHERE id = :eid"), 
                {"eid": eid}
            )
            emisor = res_emisor.fetchone()

            if emisor and emisor.ruc:
                ruc = emisor.ruc
                print(f"🧹 Iniciando barrido total en MinIO para el RUC: {ruc}")
                
                # 2. ELIMINAR CARPETAS EN MINIO (P12, Facturas, Firmadas, Autorizadas)
                delete_folder(f"{ruc}/")

        # 3. EL GRAN BORRADO EN DB (REACCIÓN EN CADENA)
        # Al borrar el profile, SQL borra Emisor -> Invoices -> Credits -> Transactions automáticamente.
        await db.execute(text("DELETE FROM profiles WHERE firebase_uid = :uid"), {"uid": uid})
        
        # 4. BORRADO EN FIREBASE
        auth.delete_user(uid)
        
        # Confirmamos todos los borrados
        await db.commit()
        
        print(f"🧨 Nuke completado exitosamente para UID: {uid}")
        return {"ok": True, "mensaje": "Cuenta, archivos y registros eliminados por completo."}
        
    except Exception as e:
        await db.rollback()
        print(f"❌ Error crítico en nuke: {str(e)}")
        raise HTTPException(status_code=500, detail="Error al eliminar la cuenta y los archivos.")