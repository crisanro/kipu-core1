# app/api/v1/admin/integraciones.py
import json
import random
from fastapi import APIRouter, Depends, HTTPException, Request, Body, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import verify_n8n_service, verify_whatsapp_service
from app.core.rate_limit import RateLimit, RateLimitScope
from app.schemas.seguridad import RequestPinSchema
from app.utils.sri_service import emitir_factura_core
from app.services.mail_service import mail_service

router = APIRouter()


# ── Buscar emisor por email ────────────────────────────────────────────────────
@router.get("/search-by-email", summary="Buscar emisor por email")
async def search_by_email(
    email: str = Query(...),
    auth: dict = Depends(verify_n8n_service),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(text("""
        SELECT
            e.id AS emisor_id, e.ruc, e.razon_social, e.ambiente,
            c.balance_emision, c.balance_recepcion,
            p.email, p.full_name, p.whatsapp_number, p.firebase_uid
        FROM profiles p
        LEFT JOIN emisor_usuarios eu ON eu.profile_id = p.id
        LEFT JOIN emisores e         ON e.id = eu.emisor_id
        LEFT JOIN user_credits c     ON c.emisor_id = e.id
        WHERE LOWER(p.email) = LOWER(:email)
        LIMIT 1
    """), {"email": email.strip()})
    row = res.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="USUARIO NO ENCONTRADO.")
    return {
        "ok": True,
        "data": {
            "emisor_id":        row.emisor_id,
            "ruc":              row.ruc,
            "razon_social":     row.razon_social,
            "ambiente":         row.ambiente,
            "balance_emision":  row.balance_emision,
            "balance_recepcion": row.balance_recepcion,
            "email":            row.email,
            "full_name":        row.full_name,
            "whatsapp_number":  row.whatsapp_number,
            "firebase_uid":     row.firebase_uid,
        }
    }


# ── Topup de créditos ──────────────────────────────────────────────────────────
@router.post("/topup", summary="Agregar créditos a un emisor")
async def topup_credits(
    data: dict = Body(...),
    auth: dict = Depends(verify_n8n_service),
    db: AsyncSession = Depends(get_db),
):
    emisor_id = data.get("emisor_id")
    cantidad  = data.get("cantidad", 0)
    tipo      = data.get("tipo", "emision")

    if not emisor_id or cantidad <= 0:
        raise HTTPException(status_code=400, detail="emisor_id y cantidad son obligatorios.")

    campo = "balance_emision" if tipo == "emision" else "balance_recepcion"

    await db.execute(text(f"""
        UPDATE user_credits SET {campo} = {campo} + :cantidad WHERE emisor_id = :eid
    """), {"cantidad": cantidad, "eid": emisor_id})

    await db.execute(text("""
        INSERT INTO credit_transactions (emisor_id, tipo, cantidad, descripcion)
        VALUES (:eid, 'recarga', :cantidad, :desc)
    """), {"eid": emisor_id, "cantidad": cantidad, "desc": f"Recarga manual via n8n — {tipo}"})

    await db.commit()
    return {"ok": True, "mensaje": f"{cantidad} créditos de {tipo} agregados."}


# ── Factura por WhatsApp ───────────────────────────────────────────────────────
@router.post("/invoice-whatsapp", summary="Emitir factura vía WhatsApp (n8n)")
async def admin_invoice_whatsapp(
    factura_data: dict = Body(...),
    auth: dict = Depends(verify_whatsapp_service),
    db: AsyncSession = Depends(get_db),
    _rl: None = Depends(RateLimit(RateLimitScope.INVOICE)),
):
    return await emitir_factura_core(factura_data, auth["emisor_id"], db)


# ── Request PIN — envío por email ──────────────────────────────────────────────
@router.post("/request-pin", summary="Generar y enviar PIN de 2FA por email")
async def request_pin(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _rl: None = Depends(RateLimit(RateLimitScope.PIN, use_ip=True)),
):
    body_bytes = await request.body()
    try:
        data_dict = json.loads(body_bytes.decode())
        data      = RequestPinSchema(**data_dict)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Error en estructura: {str(e)}")

    if data.tipo_accion in ["VALIDAR_WS", "VALIDACION_GENERAL", "CREAR_TOKEN",
                             "ELIMINAR_TOKEN", "ACTIVAR_PRODUCCION", "EXPORTAR_DATOS", "NUKE"]:
        if not data.email:
            raise HTTPException(status_code=400, detail="El email es obligatorio.")
        query = text("""
            SELECT p.id, eu.emisor_id, p.email
            FROM profiles p
            LEFT JOIN emisor_usuarios eu ON eu.profile_id = p.id
            WHERE LOWER(p.email) = LOWER(:val)
            LIMIT 1
        """)
        param = {"val": data.email}
    else:
        raise HTTPException(status_code=400, detail=f"TIPO DE ACCIÓN NO RECONOCIDO: {data.tipo_accion}")

    res  = await db.execute(query, param)
    user = res.fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="USUARIO NO ENCONTRADO.")

    # Rate limit por email — 1 minuto
    res_rate = await db.execute(text("""
        SELECT last_sent FROM email_rate_limits
        WHERE email = :email AND last_sent > NOW() - INTERVAL '1 minute'
    """), {"email": user.email})
    if res_rate.fetchone():
        raise HTTPException(status_code=429, detail="Ya enviamos un PIN. Espera 1 minuto antes de solicitar otro.")


    res_check = await db.execute(text("""
        SELECT pin FROM auth_challenges
        WHERE emisor_id = :eid AND tipo_accion = :tipo AND expires_at > NOW()
        LIMIT 1
    """), {"eid": user.emisor_id, "tipo": data.tipo_accion})
    challenge = res_check.fetchone()

    if challenge:
        pin = challenge.pin  # Reutilizar el PIN existente
    else:
        pin = f"{random.randint(100000, 999999)}"
        await db.execute(text("""
            INSERT INTO auth_challenges (email, pin, tipo_accion, extra_data, emisor_id, expires_at)
            VALUES (:email, :pin, :tipo, CAST(:meta AS jsonb), :eid, NOW() + INTERVAL '10 minutes')
        """), {
            "email": user.email,
            "pin":   pin,
            "tipo":  data.tipo_accion,
            "meta":  json.dumps(data.metadata) if hasattr(data, 'metadata') and data.metadata else "{}",
            "eid":   user.emisor_id
        })
        await db.commit()   
 

    # Rate limit DB
    await db.execute(text("""
        INSERT INTO email_rate_limits (email, last_sent)
        VALUES (:email, NOW())
        ON CONFLICT (email) DO UPDATE SET last_sent = NOW()
    """), {"email": user.email})

    await db.commit()

    # Email
    accion_label = {
        "CREAR_TOKEN":        "crear una API Key",
        "ELIMINAR_TOKEN":     "revocar una API Key",
        "ACTIVAR_PRODUCCION": "activar el ambiente de producción",
        "EXPORTAR_DATOS":     "exportar tus facturas",
        "NUKE":               "eliminar tu cuenta",
        "VALIDAR_WS":         "validar tu configuración",
        "VALIDACION_GENERAL": "confirmar esta acción",
    }.get(data.tipo_accion, "confirmar esta acción")

    html = f"""
        <div style="font-family:sans-serif;max-width:480px;margin:0 auto;padding:24px;">
          <h2 style="color:#4F46E5;margin-bottom:8px;">Código de verificación</h2>
          <p style="color:#555;font-size:14px;">
            Recibimos una solicitud para <strong>{accion_label}</strong> en tu cuenta de Kipu.
          </p>
          <div style="background:#f5f5f5;border-radius:12px;padding:24px;text-align:center;margin:24px 0;">
            <p style="font-size:36px;font-weight:bold;letter-spacing:8px;color:#111;margin:0;">
              {pin}
            </p>
          </div>
          <p style="color:#888;font-size:12px;">
            Este código expira en <strong>10 minutos</strong>.<br>
            ¿No lo ves? Busca un correo de <strong>no-reply@kipu.ec</strong> en spam o no deseado.<br>
            Si no solicitaste esto, ignora este correo.
          </p>
        </div>
    """

    await mail_service.send_mail(
        to=user.email,
        subject=f"Kipu — Tu código de verificación: {pin}",
        html_content=html
    )

    return {"ok": True, "mensaje": "PIN enviado a tu correo electrónico."}


# ── Gestión de API Keys internas ───────────────────────────────────────────────
@router.post("/apikeys/set-unlimited", summary="Activar/desactivar unlimited en una API key")
async def set_api_key_unlimited(
    data: dict = Body(...),
    auth: dict = Depends(verify_n8n_service),
    db: AsyncSession = Depends(get_db),
):
    api_key_id = data.get("api_key_id")
    unlimited  = data.get("unlimited", False)
    tipo       = data.get("tipo", "internal")

    if not api_key_id:
        raise HTTPException(status_code=400, detail="api_key_id es obligatorio.")

    res = await db.execute(text("""
        UPDATE api_keys
        SET unlimited = :unlimited, tipo = :tipo
        WHERE id = :id
        RETURNING id, nombre, emisor_id, unlimited, tipo
    """), {"unlimited": unlimited, "tipo": tipo, "id": api_key_id})
    row = res.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="API Key no encontrada.")

    await db.commit()
    return {
        "ok":         True,
        "api_key_id": row.id,
        "nombre":     row.nombre,
        "emisor_id":  row.emisor_id,
        "unlimited":  row.unlimited,
        "tipo":       row.tipo
    }


@router.get("/apikeys", summary="Listar todas las API keys")
async def listar_api_keys(
    emisor_id: int = Query(None),
    auth: dict = Depends(verify_n8n_service),
    db: AsyncSession = Depends(get_db),
):
    query = """
        SELECT ak.id, ak.nombre, ak.tipo, ak.unlimited,
               ak.revoked, ak.created_at, ak.last_used_at,
               e.razon_social, e.ruc
        FROM api_keys ak
        JOIN emisores e ON ak.emisor_id = e.id
        WHERE ak.revoked = false
    """
    params = {}
    if emisor_id:
        query += " AND ak.emisor_id = :eid"
        params["eid"] = emisor_id

    query += " ORDER BY ak.created_at DESC"
    res  = await db.execute(text(query), params)
    rows = res.fetchall()

    return {
        "ok":   True,
        "data": [
            {
                "id":           r.id,
                "nombre":       r.nombre,
                "razon_social": r.razon_social,
                "ruc":          r.ruc,
                "tipo":         r.tipo,
                "unlimited":    r.unlimited,
                "last_used_at": str(r.last_used_at) if r.last_used_at else None,
                "created_at":   str(r.created_at)
            }
            for r in rows
        ]
    }