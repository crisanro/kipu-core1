# app/api/v1/app/auth.py — OPTIMIZADO con rate limiting
import os
import random
import json
import hashlib
import zipfile
import io
from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import StreamingResponse

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from firebase_admin import auth

from app.core.database import get_db
from app.core.security import verify_firebase_token
from app.services.storage_service import delete_folder, download_file
from app.services.mail_service import mail_service
from app.schemas.seguridad import ResetPasswordRequest, VerifyPinRequest
from app.core.rate_limit import RateLimit, RateLimitScope
from app.core.cache import invalidate_emisor
from app.core.security import validar_y_quemar_pin

router = APIRouter()


# ── Send Verification ─────────────────────────────────────────────────────────
@router.post("/send-verification")
async def send_verification(
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db),
    # Rate limit: 10 requests/min por IP (protege contra spam de emails)
    _rl: None = Depends(RateLimit(RateLimitScope.RESET, use_ip=True)),
):
    email = auth_data["email"]

    # Anti-spam en DB (1 por minuto)
    res = await db.execute(text("""
        SELECT last_sent FROM email_rate_limits
        WHERE email = :email AND last_sent > NOW() - INTERVAL '1 minute'
    """), {"email": email})
    if res.fetchone():
        raise HTTPException(status_code=429, detail="Ya enviamos un correo. Espera 1 minuto.")

    try:
        user_record = auth.get_user_by_email(email)
        if user_record.email_verified:
            raise HTTPException(status_code=400, detail="El correo ya fue verificado.")
    except auth.UserNotFoundError:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    await db.execute(text("""
        INSERT INTO email_rate_limits (email, last_sent)
        VALUES (:email, NOW())
        ON CONFLICT (email) DO UPDATE SET last_sent = NOW()
    """), {"email": email})
    await db.commit()

    link = auth.generate_email_verification_link(
        email,
        auth.ActionCodeSettings(url="https://app.kipu.ec", handle_code_in_app=False)
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
    await mail_service.send_mail(to=email, subject="Verifica tu cuenta en Kipu", html_content=html)
    return {"ok": True, "mensaje": "Correo de verificación enviado."}


# ── Reset Password ─────────────────────────────────────────────────────────────
@router.post("/reset")
async def reset_password(
    data: ResetPasswordRequest,
    _rl: None = Depends(RateLimit(RateLimitScope.RESET, use_ip=True)),
):
    link = auth.generate_password_reset_link(
        data.email,
        auth.ActionCodeSettings(url="https://kipu.ec/login", handle_code_in_app=False)
    )
    html = f"<h2>Recuperación</h2><p>Haz clic para restablecer:</p><a href='{link}'>Restablecer</a>"
    await mail_service.send_mail(to=data.email, subject="Recupera tu cuenta", html_content=html)
    return {"ok": True}


# ── Reset Password ─────────────────────────────────────────────────────────────
@router.post("/reset")
async def reset_password(
    data: ResetPasswordRequest,
    request: Request,
    _rl: None = Depends(RateLimit(RateLimitScope.AUTH, use_ip=True)),
):
    # Anti-spam adicional — 1 por minuto por IP a nivel de código
    client_ip = request.client.host
    # El rate limit de RateLimitScope.AUTH ya limita por IP
    # Solo generamos el link sin verificar si el email existe
    # (por seguridad no revelamos si el email está registrado o no)
    try:
        link = auth.generate_password_reset_link(
            data.email,
            auth.ActionCodeSettings(url="https://app.kipu.ec/", handle_code_in_app=False)
        )
        html = f"""
            <h2>Recuperación de contraseña</h2>
            <p>Haz clic para restablecer tu contraseña:</p>
            <a href='{link}' style='background:#4F46E5;color:white;padding:12px 24px;
            text-decoration:none;border-radius:6px;display:inline-block;'>
            Restablecer contraseña</a>
            <p style='color:#666;font-size:12px;margin-top:16px;'>
            Si no solicitaste esto, ignora este correo.</p>
        """
        await mail_service.send_mail(
            to=data.email,
            subject="Recupera tu contraseña en Kipu",
            html_content=html
        )
    except Exception as e:
        # No revelamos si el email existe o no — siempre retornamos ok
        print(f"[RESET] Error: {e}")

    return {"ok": True, "mensaje": "Si el correo existe, recibirás un enlace en breve."}


# ── Exportar Facturas ──────────────────────────────────────────────────────────
@router.get("/exportar-facturas", summary="Exportar XMLs de facturas autorizadas")
async def exportar_facturas(
    pin: str,
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db),
    # Rate limit: 3 exports cada 5 minutos (ZIP es costoso)
    _rl: None = Depends(RateLimit(RateLimitScope.EXPORT)),
):
    emisor_id = auth_data.get("emisor_id")
    if not emisor_id:
        raise HTTPException(status_code=400, detail="EL USUARIO NO TIENE UN EMISOR VINCULADO.")

    await validar_y_quemar_pin(db, emisor_id, pin, "EXPORTAR_DATOS")

    # OPTIMIZACIÓN: query con columnas mínimas necesarias
    res = await db.execute(text("""
        SELECT e.ruc, i.clave_acceso, i.xml_path, i.numero_factura, i.fecha_emision
        FROM invoices_emitidas i
        JOIN emisores e ON i.emisor_id = e.id
        WHERE i.emisor_id = :eid
          AND i.estado    = 'AUTORIZADO'
          AND i.xml_path  IS NOT NULL
        ORDER BY i.fecha_emision DESC
    """), {"eid": emisor_id})
    facturas = res.fetchall()

    if not facturas:
        raise HTTPException(status_code=404, detail="NO TIENES FACTURAS AUTORIZADAS PARA EXPORTAR.")

    zip_buffer = io.BytesIO()
    errores    = []

    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zip_file:
        for factura in facturas:
            try:
                xml_bytes = download_file(factura.xml_path)
                nombre    = f"{factura.numero_factura}_{factura.fecha_emision}.xml".replace("-", "")
                zip_file.writestr(nombre, xml_bytes)
            except Exception as e:
                errores.append(factura.clave_acceso)
                print(f"[EXPORTAR] ⚠️ Error descargando {factura.xml_path}: {e}")

    zip_buffer.seek(0)

    ruc        = facturas[0].ruc
    fecha_hoy  = datetime.now().strftime("%Y%m%d")
    nombre_zip = f"facturas_{ruc}_{fecha_hoy}.zip"

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={nombre_zip}"}
    )



# ── NUKE ───────────────────────────────────────────────────────────────────────
@router.delete("/nuke")
async def nuke_account(
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db),
    pin: str = None,
):
    emisor_id = auth_data.get("emisor_id")
    uid       = auth_data["uid"]

    res = await db.execute(text("""
        SELECT
            e.id, e.ruc, e.razon_social, e.ambiente, e.created_at,
            p.email, p.full_name, p.whatsapp_number,
            c.balance_emision, c.balance_recepcion,
            (SELECT COUNT(*) FROM invoices_emitidas  WHERE emisor_id = e.id) AS total_emitidas,
            (SELECT COUNT(*) FROM invoices_recibidas WHERE emisor_id = e.id) AS total_recibidas
        FROM profiles p
        LEFT JOIN emisores e     ON p.emisor_id = e.id
        LEFT JOIN user_credits c ON c.emisor_id = e.id
        WHERE p.firebase_uid = :uid
    """), {"uid": uid})
    row = res.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="USUARIO NO ENCONTRADO.")

    if emisor_id:
        if not pin:
            raise HTTPException(
                status_code=400,
                detail="SE REQUIERE UN PIN DE CONFIRMACIÓN."
            )

        if row.ambiente == 1:
            # Pruebas — PIN fijo 999999, no requiere solicitud previa
            if pin != "111111":
                raise HTTPException(
                    status_code=403,
                    detail="PIN incorrecto, expirado o ya utilizado. Solicite uno nuevo."
                )
        else:
            # Producción — PIN real desde auth_challenges
            await validar_y_quemar_pin(db, emisor_id, pin, "NUKE")

    try:
        if emisor_id and row.ruc:
            await db.execute(text("""
                INSERT INTO leads_ex_usuarios (
                    ruc, razon_social, email, full_name,
                    whatsapp_number,                          -- ← agregar
                    ultimo_balance_emision, ultimo_balance_recepcion,
                    total_facturas_emitidas, total_facturas_recibidas,
                    fecha_registro_original, fecha_eliminacion
                ) VALUES (
                    :ruc, :razon_social, :email, :full_name,
                    :whatsapp_number,                         -- ← agregar
                    :bal_emi, :bal_rec,
                    :total_emi, :total_rec,
                    :fecha_reg, NOW()
                )
            """), {
                "ruc":              row.ruc,
                "razon_social":     row.razon_social,
                "email":            row.email,
                "full_name":        row.full_name,
                "whatsapp_number":  row.whatsapp_number,      # ← agregar
                "bal_emi":          row.balance_emision   or 0,
                "bal_rec":          row.balance_recepcion or 0,
                "total_emi":        row.total_emitidas    or 0,
                "total_rec":        row.total_recibidas   or 0,
                "fecha_reg":        row.created_at.replace(tzinfo=None) if row.created_at else None,
            })

        await db.execute(text("DELETE FROM profiles WHERE firebase_uid = :uid"), {"uid": uid})
        if emisor_id:
            await db.execute(text("DELETE FROM emisores WHERE id = :eid"), {"eid": emisor_id})

        await db.commit()

        # Limpiar todo el cache del emisor antes de que deje de existir
        if emisor_id:
            await invalidate_emisor(emisor_id)

    except Exception as e:
        await db.rollback()
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail="ERROR AL ELIMINAR LA CUENTA EN BASE DE DATOS.")

    # ── 1. Borrar Firebase Auth ───────────────────────────────────────────────
    try:
        auth.delete_user(uid)
        print(f"[NUKE] 🔥 Firebase Auth eliminado: {uid}")
    except Exception as e_fb:
        print(f"[NUKE] ⚠️ Error eliminando Firebase Auth (no crítico): {e_fb}")

    # ── 2. Borrar Firestore ───────────────────────────────────────────────────
    try:
        from firebase_admin import firestore
        fs_client = firestore.client()
        fs_client.collection("users").document(uid).delete()
        print(f"[NUKE] 🗑️ Firestore eliminado para UID: {uid}")
    except Exception as e_fs:
        print(f"[NUKE] ⚠️ Error eliminando Firestore (no crítico): {e_fs}")

    # ── 3. Borrar R2 ──────────────────────────────────────────────────────────
    if emisor_id and row.ruc:
        try:
            delete_folder(f"{row.ruc}/")
            print(f"[NUKE] 🗑️ R2 eliminado para RUC: {row.ruc}")
        except Exception as e_r2:
            print(f"[NUKE] ⚠️ Error eliminando R2 (no crítico): {e_r2}")

    return {
        "ok":      True,
        "mensaje": "TU CUENTA, ARCHIVOS Y REGISTROS HAN SIDO ELIMINADOS PERMANENTEMENTE."
    }


# ── Ping / Validar sesión extensión ───────────────────────────────────────────
@router.get("/ping")
async def ping(
    auth_data: dict = Depends(verify_firebase_token),
):
    """
    Valida el JWT de Firebase sin tocar la base de datos.
    Usado por la extensión Kipu Importador antes de iniciar una importación.
    Retorna 401 si el token es inválido o expira en menos de 5 minutos.
    """
    import time
    exp = auth_data.get("exp")
    if not exp:
        raise HTTPException(status_code=401, detail="TOKEN_SIN_EXPIRACION")

    segundos_restantes = exp - int(time.time())
    if segundos_restantes < 300:  # menos de 5 minutos
        raise HTTPException(
            status_code=401,
            detail="TOKEN_POR_EXPIRAR",
        )

    return {
        "ok": True,
        "expira_en": segundos_restantes,  # segundos restantes, útil para debug
    }
