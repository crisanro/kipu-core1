# app/api/v1/app/auth.py — OPTIMIZADO con rate limiting
import os
import random
import json
import hashlib
import zipfile
import io
import asyncio
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

# A dónde vuelve el usuario después de verificar / resetear
VERIFY_CONTINUE_URL = "https://app.kipu.ec"
RESET_CONTINUE_URL  = "https://app.kipu.ec/"


# ── Send Verification ─────────────────────────────────────────────────────────
@router.post("/send-verification")
async def send_verification(
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db),
    _rl: None = Depends(RateLimit(RateLimitScope.RESET, use_ip=True)),
):
    email = (auth_data.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="La cuenta no tiene correo asociado.")

    # Anti-spam en DB (1 por minuto)
    res = await db.execute(text("""
        SELECT last_sent FROM email_rate_limits
        WHERE email = :email AND last_sent > NOW() - INTERVAL '1 minute'
    """), {"email": email})
    if res.fetchone():
        raise HTTPException(status_code=429, detail="Ya enviamos un correo. Espera 1 minuto.")

    try:
        user_record = await asyncio.to_thread(auth.get_user_by_email, email)
    except auth.UserNotFoundError:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    if user_record.email_verified:
        raise HTTPException(status_code=400, detail="El correo ya fue verificado.")

    # Generar link
    try:
        link = await asyncio.to_thread(
            auth.generate_email_verification_link,
            email,
            auth.ActionCodeSettings(url=VERIFY_CONTINUE_URL, handle_code_in_app=False),
        )
    except Exception as e:
        print(f"[VERIFY] ❌ Error generando link para {email}: {e}")
        raise HTTPException(status_code=502, detail="No se pudo generar el enlace de verificación.")

    # Enviar — y ESTA VEZ revisamos el resultado
    envio = await mail_service.send_link_verificacion(
        email  = email,
        link   = link,
        nombre = user_record.display_name,
    )
    if not envio.get("exito"):
        print(f"[VERIFY] ❌ SMTP falló para {email}: {envio}")
        raise HTTPException(
            status_code=502,
            detail="No pudimos enviar el correo de verificación. Intenta de nuevo en unos minutos.",
        )

    # Rate limit solo cuando realmente se envió
    await db.execute(text("""
        INSERT INTO email_rate_limits (email, last_sent)
        VALUES (:email, NOW())
        ON CONFLICT (email) DO UPDATE SET last_sent = NOW()
    """), {"email": email})
    await db.commit()

    print(f"[VERIFY] 📧 Verificación enviada a {email}")
    return {"ok": True, "mensaje": "Correo de verificación enviado."}


# ── Reset Password ─────────────────────────────────────────────────────────────
@router.post("/reset")
async def reset_password(
    data: ResetPasswordRequest,
    request: Request,
    _rl: None = Depends(RateLimit(RateLimitScope.AUTH, use_ip=True)),
):
    email = (data.email or "").strip().lower()
    try:
        link = await asyncio.to_thread(
            auth.generate_password_reset_link,
            email,
            auth.ActionCodeSettings(url=RESET_CONTINUE_URL, handle_code_in_app=False),
        )
        envio = await mail_service.send_link_password(email=email, link=link)
        if not envio.get("exito"):
            print(f"[RESET] ❌ SMTP falló para {email}: {envio}")
        else:
            print(f"[RESET] 📧 Link de recuperación enviado a {email}")
    except auth.UserNotFoundError:
        print(f"[RESET] Email no registrado: {email}")
    except Exception as e:
        print(f"[RESET] ❌ Error: {e}")

    return {"ok": True, "mensaje": "Si el correo existe, recibirás un enlace en breve."}


# ── Exportar Facturas ──────────────────────────────────────────────────────────

# Máximo de descargas paralelas a storage (evita saturar conexiones)
_MAX_CONCURRENT_DOWNLOADS = 10

@router.get("/exportar-facturas", summary="Exportar XMLs de facturas autorizadas")
async def exportar_facturas(
    pin: str,
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db),
    _rl: None = Depends(RateLimit(RateLimitScope.EXPORT)),
):
    emisor_id = auth_data.get("emisor_id")
    if not emisor_id:
        raise HTTPException(status_code=400, detail="EL USUARIO NO TIENE UN EMISOR VINCULADO.")

    await validar_y_quemar_pin(db, emisor_id, pin, "EXPORTAR_DATOS")

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

    # Descargar XMLs en paralelo con semáforo (no bloquea el event loop)
    semaforo = asyncio.Semaphore(_MAX_CONCURRENT_DOWNLOADS)
    errores  = []

    async def descargar(factura):
        async with semaforo:
            try:
                xml_bytes = await asyncio.to_thread(download_file, factura.xml_path)
                nombre    = f"{factura.numero_factura}_{factura.fecha_emision}.xml".replace("-", "")
                return (nombre, xml_bytes)
            except Exception as e:
                errores.append(factura.clave_acceso)
                print(f"[EXPORTAR] ⚠️ Error descargando {factura.xml_path}: {e}")
                return None

    resultados = await asyncio.gather(*[descargar(f) for f in facturas])

    # Armar ZIP (operación CPU, rápida)
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zip_file:
        for item in resultados:
            if item:
                zip_file.writestr(item[0], item[1])

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
            if pin != "111111":
                raise HTTPException(
                    status_code=403,
                    detail="PIN incorrecto, expirado o ya utilizado. Solicite uno nuevo."
                )
        else:
            await validar_y_quemar_pin(db, emisor_id, pin, "NUKE")

    try:
        if emisor_id and row.ruc:
            await db.execute(text("""
                INSERT INTO leads_ex_usuarios (
                    ruc, razon_social, email, full_name,
                    whatsapp_number,
                    ultimo_balance_emision, ultimo_balance_recepcion,
                    total_facturas_emitidas, total_facturas_recibidas,
                    fecha_registro_original, fecha_eliminacion
                ) VALUES (
                    :ruc, :razon_social, :email, :full_name,
                    :whatsapp_number,
                    :bal_emi, :bal_rec,
                    :total_emi, :total_rec,
                    :fecha_reg, NOW()
                )
            """), {
                "ruc":              row.ruc,
                "razon_social":     row.razon_social,
                "email":            row.email,
                "full_name":        row.full_name,
                "whatsapp_number":  row.whatsapp_number,
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

        if emisor_id:
            await invalidate_emisor(emisor_id)

    except Exception as e:
        await db.rollback()
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail="ERROR AL ELIMINAR LA CUENTA EN BASE DE DATOS.")

    # Firebase Auth — en hilo para no bloquear event loop
    try:
        await asyncio.to_thread(auth.delete_user, uid)
        print(f"[NUKE] 🔥 Firebase Auth eliminado: {uid}")
    except Exception as e_fb:
        print(f"[NUKE] ⚠️ Error eliminando Firebase Auth (no crítico): {e_fb}")

    # Firestore — en hilo para no bloquear event loop
    try:
        from firebase_admin import firestore
        def _borrar_firestore():
            fs_client = firestore.client()
            fs_client.collection("users").document(uid).delete()
        await asyncio.to_thread(_borrar_firestore)
        print(f"[NUKE] 🗑️ Firestore eliminado para UID: {uid}")
    except Exception as e_fs:
        print(f"[NUKE] ⚠️ Error eliminando Firestore (no crítico): {e_fs}")

    # R2 — en hilo para no bloquear event loop
    if emisor_id and row.ruc:
        try:
            await asyncio.to_thread(delete_folder, f"{row.ruc}/")
            print(f"[NUKE] 🗑️ R2 eliminado para RUC: {row.ruc}")
        except Exception as e_r2:
            print(f"[NUKE] ⚠️ Error eliminando R2 (no crítico): {e_r2}")

    return {
        "ok":      True,
        "mensaje": "TU CUENTA, ARCHIVOS Y REGISTROS HAN SIDO ELIMINADOS PERMANENTEMENTE."
    }


# ── Ping / Validar sesión extensión ───────────────────────────────────────────
@router.get("/ping")
async def ping(request: Request):
    """
    Valida el JWT de Firebase sin tocar la base de datos.
    Retorna 401 si el token es inválido o expira en menos de 5 minutos.
    """
    import time

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="TOKEN_REQUERIDO")

    token = auth_header.split(" ")[1]

    try:
        decoded = await asyncio.to_thread(auth.verify_id_token, token)
    except Exception as e:
        if "expired" in str(e).lower():
            raise HTTPException(status_code=401, detail="TOKEN_POR_EXPIRAR")
        raise HTTPException(status_code=401, detail="TOKEN_INVALIDO")

    exp = decoded.get("exp", 0)
    segundos_restantes = exp - int(time.time())

    if segundos_restantes < 300:
        raise HTTPException(status_code=401, detail="TOKEN_POR_EXPIRAR")

    return {
        "ok": True,
        "expira_en": segundos_restantes,
    }