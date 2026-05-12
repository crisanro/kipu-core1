#app/api/v1/app/auth.py
import os
import random
import json
import hashlib
import zipfile
import io
import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from firebase_admin import auth

from app.core.database import get_db
from app.core.security import verify_firebase_token
from app.services.storage_service import  delete_folder, download_file
from app.services.mail_service import mail_service
from app.schemas.seguridad import ResetPasswordRequest, VerifyPinRequest, RequestPinSchema # Asegúrate de tener este schema

router = APIRouter()


async def validar_y_quemar_pin(db: AsyncSession, emisor_id: int, pin: str, tipo_accion: str):
    """
    Busca el PIN en auth_challenges. Si es válido, lo elimina y retorna True.
    Si no, lanza una excepción 403.
    """
    query = text("""
        DELETE FROM auth_challenges 
        WHERE emisor_id = :eid 
          AND pin = :pin 
          AND tipo_accion = :tipo 
          AND expires_at > NOW()
        RETURNING id
    """)
    
    result = await db.execute(query, {
        "eid": emisor_id,
        "pin": pin,
        "tipo": tipo_accion
    })
    
    if not result.fetchone():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="PIN incorrecto, expirado o ya utilizado. Solicite uno nuevo."
        )
    


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

    query = text("""
        SELECT id, whatsapp_number, tipo_accion, extra_data 
        FROM auth_challenges 
        WHERE LOWER(email) = LOWER(:email) AND pin = :pin AND expires_at > NOW()
        FOR UPDATE
    """)
    res = await db.execute(query, {"email": email, "pin": data.pin})
    challenge = res.fetchone()
    if not challenge:
        raise HTTPException(status_code=400, detail="PIN incorrecto o expirado.")

    if challenge.tipo_accion in ['VALIDACION_GENERAL', 'VALIDAR_WS']:
        await db.execute(
            text("UPDATE profiles SET whatsapp_number = :phone WHERE emisor_id = :eid"), 
            {"phone": challenge.whatsapp_number, "eid": emisor_id}
        )
    elif challenge.tipo_accion == 'ELIMINAR_TOKEN':
        if challenge.extra_data and 'key_id' in challenge.extra_data:
            await db.execute(
                text("UPDATE api_keys SET revoked = true WHERE id = :kid AND emisor_id = :eid"),  # revoked_at no existe en schema
                {"kid": challenge.extra_data['key_id'], "eid": emisor_id}
            )

    await db.execute(text("DELETE FROM auth_challenges WHERE id = :id"), {"id": challenge.id})
    await db.commit()
    return {"ok": True, "accion": challenge.tipo_accion}


@router.get("/exportar-facturas", summary="Exportar XMLs de facturas autorizadas")
async def exportar_facturas(
    pin: str,
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db)
):
    emisor_id = auth_data.get("emisor_id")
    if not emisor_id:
        raise HTTPException(status_code=400, detail="EL USUARIO NO TIENE UN EMISOR VINCULADO.")

    # 1. Validar y quemar PIN
    await validar_y_quemar_pin(db, emisor_id, pin, "EXPORTAR_DATOS")

    # 2. Obtener RUC y todas las facturas autorizadas con su xml_path
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
        raise HTTPException(
            status_code=404,
            detail="NO TIENES FACTURAS AUTORIZADAS PARA EXPORTAR."
        )

    # 3. Generar ZIP en memoria
    zip_buffer = io.BytesIO()
    errores    = []

    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zip_file:
        for factura in facturas:
            try:
                xml_bytes = download_file(factura.xml_path)
                # Nombre del archivo: numero_factura_fecha.xml
                nombre = f"{factura.numero_factura}_{factura.fecha_emision}.xml".replace("-", "")
                zip_file.writestr(nombre, xml_bytes)
            except Exception as e:
                errores.append(factura.clave_acceso)
                print(f"[EXPORTAR] ⚠️ Error descargando {factura.xml_path}: {e}")

    zip_buffer.seek(0)

    if errores:
        print(f"[EXPORTAR] ⚠️ {len(errores)} XMLs no pudieron descargarse: {errores}")

    # 4. Retornar ZIP como descarga directa
    ruc        = facturas[0].ruc
    fecha_hoy  = datetime.now().strftime("%Y%m%d")
    nombre_zip = f"facturas_{ruc}_{fecha_hoy}.zip"

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={nombre_zip}"}
    )


@router.delete("/nuke")
async def nuke_account(
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db),
    pin: str = None  # Solo requerido en producción
):
    emisor_id = auth_data.get("emisor_id")
    uid       = auth_data["uid"]

    # ─── 1. Obtener datos completos del emisor ────────────────────────────────
    res = await db.execute(text("""
        SELECT 
            e.id, e.ruc, e.razon_social, e.ambiente, e.created_at,
            p.email, p.full_name,
            c.balance_emision, c.balance_recepcion,
            (SELECT COUNT(*) FROM invoices_emitidas  WHERE emisor_id = e.id) AS total_emitidas,
            (SELECT COUNT(*) FROM invoices_recibidas WHERE emisor_id = e.id) AS total_recibidas
        FROM profiles p
        LEFT JOIN emisores e     ON p.emisor_id  = e.id
        LEFT JOIN user_credits c ON c.emisor_id  = e.id
        WHERE p.firebase_uid = :uid
    """), {"uid": uid})
    row = res.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="USUARIO NO ENCONTRADO.")

    # ─── 2. Validar PIN si está en producción ────────────────────────────────
    if emisor_id and row.ambiente == 2:
        if not pin:
            raise HTTPException(
                status_code=400,
                detail="EN MODO PRODUCCIÓN SE REQUIERE UN PIN DE CONFIRMACIÓN. SOLICÍTALO POR WHATSAPP."
            )
        await validar_y_quemar_pin(db, emisor_id, pin, "NUKE")

    # ─── 3. Guardar lead antes de borrar ─────────────────────────────────────
    try:
        if emisor_id and row.ruc:
            await db.execute(text("""
                INSERT INTO leads_ex_usuarios (
                    ruc, razon_social, email, full_name,
                    ultimo_balance_emision, ultimo_balance_recepcion,
                    total_facturas_emitidas, total_facturas_recibidas,
                    fecha_registro_original, fecha_eliminacion
                ) VALUES (
                    :ruc, :razon_social, :email, :full_name,
                    :bal_emi, :bal_rec,
                    :total_emi, :total_rec,
                    :fecha_reg, NOW()
                )
            """), {
                "ruc":          row.ruc,
                "razon_social": row.razon_social,
                "email":        row.email,
                "full_name":    row.full_name,
                "bal_emi":      row.balance_emision   or 0,
                "bal_rec":      row.balance_recepcion or 0,
                "total_emi":    row.total_emitidas    or 0,
                "total_rec":    row.total_recibidas   or 0,
                "fecha_reg":    row.created_at,
            })

        # ─── 4. Borrar profile → cascada borra emisor y todo lo demás ────────
        await db.execute(
            text("DELETE FROM profiles WHERE firebase_uid = :uid"),
            {"uid": uid}
        )

        # ─── 5. Borrar emisor → cascada borra TODO (invoices, credits, etc) ──
        if emisor_id:
            await db.execute(
                text("DELETE FROM emisores WHERE id = :eid"),
                {"eid": emisor_id}
            )

        await db.commit()

    except Exception as e:
        await db.rollback()
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail="ERROR AL ELIMINAR LA CUENTA EN BASE DE DATOS.")

    # ─── 6. Borrar Firebase — fuera de transacción DB ────────────────────────
    try:
        auth.delete_user(uid)
        print(f"[NUKE] 🔥 Firebase eliminado: {uid}")
    except Exception as e_fb:
        print(f"[NUKE] ⚠️ Error eliminando Firebase (no crítico): {e_fb}")

    # ─── 7. Borrar R2 — fuera de transacción DB ───────────────────────────────
    if emisor_id and row.ruc:
        try:
            delete_folder(f"{row.ruc}/")
            print(f"[NUKE] 🗑️ R2 eliminado para RUC: {row.ruc}")
        except Exception as e_r2:
            print(f"[NUKE] ⚠️ Error eliminando R2 (no crítico): {e_r2}")

    print(f"[NUKE] 🧨 Completado para UID: {uid}")
    return {
        "ok":      True,
        "mensaje": "TU CUENTA, ARCHIVOS Y REGISTROS HAN SIDO ELIMINADOS PERMANENTEMENTE."
    }