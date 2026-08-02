# app/api/v1/admin/integraciones.py — OPTIMIZADO con rate limiting en PINs
import random
import json
from fastapi import APIRouter, Depends, Query, Body, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.core.database import get_db
from app.core.security import verify_n8n_service, verify_whatsapp_service
from app.schemas.admin import TopupRequest
from app.services.admin_service import recargar_creditos_core, chequear_estado_ws_core
from app.utils.sri_service import emitir_factura_core
from app.schemas.seguridad import RequestPinSchema
from app.services.mail_service import mail_service
from app.core.rate_limit import RateLimit, RateLimitScope
from app.schemas.cliente import ClienteCreate, ClienteBusquedaMasiva
from app.services.cliente_service import (
    crear_cliente_core,
    consultar_clientes_bulk_core,
)


router = APIRouter()


@router.post("/topup", summary="Recargar créditos a emisor (Exclusivo n8n)")
async def admin_topup(
    request: TopupRequest,
    auth: dict = Depends(verify_n8n_service),
    db: AsyncSession = Depends(get_db),
):
    return await recargar_creditos_core(request, db)


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

    # Buscar usuario por email o WhatsApp según la acción
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

    # ── Rate limit por email — 1 minuto ───────────────────────────────────
    res_rate = await db.execute(text("""
        SELECT last_sent FROM email_rate_limits
        WHERE email = :email AND last_sent > NOW() - INTERVAL '1 minute'
    """), {"email": user.email})
    if res_rate.fetchone():
        raise HTTPException(status_code=429, detail="Ya enviamos un PIN. Espera 1 minuto antes de solicitar otro.")

    # ── Verificar que no haya PIN activo ──────────────────────────────────
    res_check = await db.execute(text("""
        SELECT expires_at FROM auth_challenges
        WHERE emisor_id = :eid AND tipo_accion = :tipo AND expires_at > NOW()
        LIMIT 1
    """), {"eid": user.emisor_id, "tipo": data.tipo_accion})
    if res_check.fetchone():
        raise HTTPException(status_code=429, detail="YA TIENES UN PIN ACTIVO. ESPERA A QUE EXPIRE.")

    # ── Generar PIN ───────────────────────────────────────────────────────
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

    # ── Rate limit DB ─────────────────────────────────────────────────────
    await db.execute(text("""
        INSERT INTO email_rate_limits (email, last_sent)
        VALUES (:email, NOW())
        ON CONFLICT (email) DO UPDATE SET last_sent = NOW()
    """), {"email": user.email})

    await db.commit()

    # ── Enviar email con PIN ──────────────────────────────────────────────
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


@router.get("/check-status", summary="Verificar estado de cuenta WhatsApp")
async def admin_check_status(
    whatsapp_number: str = Query(..., description="Número de WhatsApp"),
    auth: dict = Depends(verify_n8n_service),
    db: AsyncSession = Depends(get_db),
):
    return await chequear_estado_ws_core(whatsapp_number, db)


@router.post("/invoice-whatsapp", summary="Emitir factura vía WhatsApp (n8n)")
async def admin_invoice_whatsapp(
    factura_data: dict = Body(...),
    auth: dict = Depends(verify_whatsapp_service),
    db: AsyncSession = Depends(get_db),
    _rl: None = Depends(RateLimit(RateLimitScope.INVOICE)),
):
    return await emitir_factura_core(factura_data, auth["emisor_id"], db)


# ── Clientes (antes en clientes_n8n.py) ───────────────────────────────────────

@router.post("/clientes", summary="Crear cliente desde WhatsApp")
async def crear_cliente_ws(
    cliente_data: ClienteCreate,
    auth: dict = Depends(verify_whatsapp_service),
    db: AsyncSession = Depends(get_db),
):
    return await crear_cliente_core(auth["emisor_id"], cliente_data, db)


@router.post("/clientes/buscar", summary="Búsqueda masiva de clientes")
async def buscar_clientes_ws(
    busqueda: ClienteBusquedaMasiva,
    auth: dict = Depends(verify_whatsapp_service),
    db: AsyncSession = Depends(get_db),
):
    return await consultar_clientes_bulk_core(auth["emisor_id"], busqueda.terminos, db)


@router.get("/clientes/{identificacion}", summary="Buscar cliente por identificación")
async def consultar_cliente_ws(
    identificacion: str,
    auth: dict = Depends(verify_whatsapp_service),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(text("""
        SELECT id, tipo_identificacion_sri, identificacion, razon_social,
               email, telefono, direccion
        FROM clientes_emisor
        WHERE emisor_id = :eid AND identificacion = :ident
    """), {"eid": auth["emisor_id"], "ident": identificacion})
    row = res.fetchone()
    if not row:
        return {"existe": False}
    return {
        "existe":                  True,
        "uid":                     str(row.id),
        "tipo_identificacion_sri": row.tipo_identificacion_sri,
        "identificacion":          row.identificacion,
        "razon_social":            row.razon_social,
        "email":                   row.email or "",
        "telefono":                row.telefono or "",
        "direccion":               row.direccion or "",
    }


# ── Search by Email ────────────────────────────────────────────────────────────
@router.get("/search-by-email", summary="Buscar emisor por email")
async def search_by_email(
    email: str = Query(..., description="Email del usuario"),
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
        "ok":   True,
        "data": {
            "emisor_id":         row.emisor_id,
            "ruc":               row.ruc,
            "razon_social":      row.razon_social,
            "ambiente":          row.ambiente,
            "balance_emision":   row.balance_emision or 0,
            "balance_recepcion": row.balance_recepcion or 0,
            "email":             row.email,
            "full_name":         row.full_name,
            "whatsapp_number":   row.whatsapp_number,
            "firebase_uid":      row.firebase_uid,
        }
    }


# ── Crear Notificación ─────────────────────────────────────────────────────────
@router.post("/notificaciones", summary="Crear notificación para un emisor")
async def crear_notificacion(
    data: dict = Body(...),
    auth: dict = Depends(verify_n8n_service),
    db: AsyncSession = Depends(get_db),
):
    emisor_id = data.get("emisor_id")
    tipo      = data.get("tipo", "INFO").upper()
    titulo    = data.get("titulo", "").strip()
    mensaje   = data.get("mensaje", "").strip()

    if not emisor_id or not titulo or not mensaje:
        raise HTTPException(status_code=400, detail="emisor_id, titulo y mensaje son obligatorios.")

    referencia = data.get("referencia", None)

    res = await db.execute(text("""
        INSERT INTO notificaciones (emisor_id, tipo, titulo, mensaje, referencia)
        VALUES (:eid, :tipo, :titulo, :mensaje, :ref)
        RETURNING id, created_at
    """), {"eid": emisor_id, "tipo": tipo, "titulo": titulo, "mensaje": mensaje, "ref": referencia})
    row = res.fetchone()
    await db.commit()

    return {
        "ok":         True,
        "mensaje":    "NOTIFICACIÓN CREADA.",
        "id":         row.id,
        "created_at": row.created_at
    }


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
    emisor_id: int = Query(None, description="Filtrar por emisor"),
    auth: dict = Depends(verify_n8n_service),
    db: AsyncSession = Depends(get_db),
):
    query = """
        SELECT ak.id, ak.nombre, ak.emisor_id, ak.tipo, ak.unlimited,
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
                "emisor_id":    r.emisor_id,
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