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



@router.post("/request-pin", summary="Generar PIN de 2FA")
async def request_pin(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _rl: None = Depends(RateLimit(RateLimitScope.PIN, use_ip=True)),
):
    body_bytes = await request.body()
    body_str   = body_bytes.decode()
    try:
        data_dict = json.loads(body_str)
        data      = RequestPinSchema(**data_dict)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Error en estructura: {str(e)}")

    # ── Acciones que usan EMAIL ───────────────────────────────────────────────
    if data.tipo_accion in ["VALIDAR_WS", "VALIDACION_GENERAL"]:
        if not data.email:
            raise HTTPException(status_code=400, detail="El email es obligatorio para esta acción.")
        query = text("SELECT emisor_id, email, whatsapp_number FROM profiles WHERE LOWER(email) = LOWER(:val)")
        param = {"val": data.email}

    # ── Acciones que usan WHATSAPP ────────────────────────────────────────────
    elif data.tipo_accion in ["NUKE", "CREAR_TOKEN", "ELIMINAR_TOKEN", "ACTIVAR_PRODUCCION", "EXPORTAR_DATOS"]:
        if not data.whatsapp_number:
            raise HTTPException(status_code=400, detail="El número de WhatsApp es obligatorio para esta acción.")
        query = text("SELECT emisor_id, email, whatsapp_number FROM profiles WHERE whatsapp_number = :val")
        param = {"val": data.whatsapp_number}

    else:
        raise HTTPException(status_code=400, detail=f"TIPO DE ACCIÓN NO RECONOCIDO: {data.tipo_accion}")

    res  = await db.execute(query, param)
    user = res.fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="USUARIO NO ENCONTRADO O NO AUTORIZADO.")

    if data.tipo_accion == "NUKE" and not user.whatsapp_number:
        raise HTTPException(
            status_code=400,
            detail="SOLO PUEDES ELIMINAR TU CUENTA DESDE WHATSAPP UNA VEZ EN PRODUCCIÓN."
        )

    # Anti-spam a nivel DB
    res_check = await db.execute(text("""
        SELECT expires_at FROM auth_challenges
        WHERE emisor_id  = :eid
          AND tipo_accion = :tipo
          AND expires_at  > NOW()
        LIMIT 1
    """), {"eid": user.emisor_id, "tipo": data.tipo_accion})
    if res_check.fetchone():
        raise HTTPException(
            status_code=429,
            detail="YA TIENES UN PIN ACTIVO PARA ESTA ACCIÓN. ESPERA A QUE EXPIRE."
        )

    pin = f"{random.randint(100000, 999999)}"

    await db.execute(text("""
        INSERT INTO auth_challenges (email, whatsapp_number, pin, tipo_accion, extra_data, emisor_id, expires_at)
        VALUES (:email, :ws, :pin, :tipo, CAST(:meta AS jsonb), :eid, NOW() + INTERVAL '10 minutes')
    """), {
        "email": user.email,
        "ws":    data.whatsapp_number,
        "pin":   pin,
        "tipo":  data.tipo_accion,
        "meta":  json.dumps(data.metadata) if hasattr(data, 'metadata') and data.metadata else "{}",
        "eid":   user.emisor_id
    })
    await db.commit()
    return {"ok": True, "pin": pin}



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
        LEFT JOIN emisores e     ON p.emisor_id = e.id
        LEFT JOIN user_credits c ON c.emisor_id = e.id
        WHERE LOWER(p.email) = LOWER(:email)
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