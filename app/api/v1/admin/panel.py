# app/api/v1/admin/panel.py
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional
from app.core.database import get_db
from app.core.security import verify_firebase_token
from app.services.notification_service import crear_notificacion, notificar_todos_emisores

router = APIRouter()

# ── Guard superadmin ───────────────────────────────────────────────────────────
async def verify_superadmin(auth_data: dict = Depends(verify_firebase_token)):
    if auth_data.get("role") != "superadmin":
        raise HTTPException(status_code=403, detail="Acceso restringido.")
    return auth_data

# ── Schemas ────────────────────────────────────────────────────────────────────
class NotificacionMasivaRequest(BaseModel):
    titulo:     str
    mensaje:    str
    tipo:       str = "SISTEMA"
    referencia: Optional[str] = None
    emisor_id:  Optional[int] = None  # None = todos

# ── GET /emisores — listar todos ───────────────────────────────────────────────
@router.get("/emisores", summary="Listar todos los emisores")
async def listar_emisores(
    auth_data: dict         = Depends(verify_superadmin),
    db:        AsyncSession = Depends(get_db),
):
    res = await db.execute(text("""
        SELECT 
            e.id, e.ruc, e.razon_social, e.nombre_comercial,
            e.ambiente, e.created_at,
            c.balance_emision, c.balance_recepcion,
            COUNT(DISTINCT eu.profile_id) as total_usuarios,
            COUNT(DISTINCT i.id) as total_facturas
        FROM emisores e
        LEFT JOIN user_credits c ON c.emisor_id = e.id
        LEFT JOIN emisor_usuarios eu ON eu.emisor_id = e.id
        LEFT JOIN invoices_emitidas i ON i.emisor_id = e.id AND i.estado = 'AUTORIZADO'
        GROUP BY e.id, c.balance_emision, c.balance_recepcion
        ORDER BY e.created_at DESC
    """))
    rows = res.fetchall()
    return {
        "ok":   True,
        "data": [dict(r._mapping) for r in rows]
    }

# ── POST /notificar — enviar notificación ──────────────────────────────────────
@router.post("/notificar", summary="Enviar notificación masiva o individual")
async def enviar_notificacion(
    data:      NotificacionMasivaRequest,
    auth_data: dict         = Depends(verify_superadmin),
    db:        AsyncSession = Depends(get_db),
):
    if data.emisor_id:
        # Individual
        await crear_notificacion(
            db        = db,
            emisor_id = data.emisor_id,
            tipo      = data.tipo,
            titulo    = data.titulo,
            mensaje   = data.mensaje,
            referencia = data.referencia,
        )
        return {"ok": True, "mensaje": f"Notificación enviada al emisor {data.emisor_id}."}
    else:
        # Masiva
        await notificar_todos_emisores(
            db             = db,
            tipo           = data.tipo,
            titulo         = data.titulo,
            mensaje        = data.mensaje,
            referencia     = data.referencia,
            solo_produccion = True,
        )
        return {"ok": True, "mensaje": "Notificación enviada a todos los emisores en producción."}

# ── GET /stats — estadísticas globales ────────────────────────────────────────
@router.get("/stats", summary="Estadísticas globales de Kipu")
async def stats_globales(
    auth_data: dict         = Depends(verify_superadmin),
    db:        AsyncSession = Depends(get_db),
):
    res = await db.execute(text("""
        SELECT
            COUNT(DISTINCT e.id)                                          AS total_emisores,
            COUNT(DISTINCT CASE WHEN e.ambiente = 2 THEN e.id END)        AS en_produccion,
            COUNT(DISTINCT CASE WHEN e.ambiente = 1 THEN e.id END)        AS en_pruebas,
            COUNT(DISTINCT i.id)                                          AS total_facturas,
            COALESCE(SUM(i.importe_total), 0)                             AS monto_total,
            COUNT(DISTINCT CASE WHEN i.estado = 'AUTORIZADO' THEN i.id END) AS autorizadas,
            SUM(c.balance_emision)                                        AS creditos_totales
        FROM emisores e
        LEFT JOIN invoices_emitidas i ON i.emisor_id = e.id
        LEFT JOIN user_credits c ON c.emisor_id = e.id
    """))
    row = res.fetchone()
    return {"ok": True, "data": dict(row._mapping)}


# ── GET /emisores/{id} — detalle completo ─────────────────────────────────────
@router.get("/emisores/{emisor_id}", summary="Detalle de un emisor")
async def detalle_emisor(
    emisor_id: int,
    auth_data: dict         = Depends(verify_superadmin),
    db:        AsyncSession = Depends(get_db),
):
    # Emisor base
    res = await db.execute(text("""
        SELECT e.*, c.balance_emision, c.balance_recepcion,
               e.p12_path IS NOT NULL as firma_ok
        FROM emisores e
        LEFT JOIN user_credits c ON c.emisor_id = e.id
        WHERE e.id = :eid
    """), {"eid": emisor_id})
    emisor = res.fetchone()
    if not emisor:
        raise HTTPException(status_code=404, detail="Emisor no encontrado.")

    # Usuarios
    res_u = await db.execute(text("""
        SELECT p.id as profile_id, p.email, p.full_name as nombre, eu.rol
        FROM emisor_usuarios eu
        JOIN profiles p ON p.id = eu.profile_id
        WHERE eu.emisor_id = :eid
        ORDER BY eu.created_at ASC
    """), {"eid": emisor_id})
    usuarios = [dict(r._mapping) for r in res_u.fetchall()]

    # Últimas 20 facturas
    res_f = await db.execute(text("""
        SELECT id, numero_factura, estado, importe_total,
               razon_social_comprador, fecha_emision, cod_doc
        FROM invoices_emitidas
        WHERE emisor_id = :eid
        ORDER BY created_at DESC
        LIMIT 20
    """), {"eid": emisor_id})
    facturas = [dict(r._mapping) for r in res_f.fetchall()]

    # Conteos
    res_cnt = await db.execute(text("""
        SELECT COUNT(*) as total_facturas
        FROM invoices_emitidas
        WHERE emisor_id = :eid
    """), {"eid": emisor_id})
    cnt = res_cnt.fetchone()

    data = dict(emisor._mapping)
    data["usuarios"]       = usuarios
    data["facturas"]       = facturas
    data["total_facturas"] = cnt.total_facturas
    data["total_usuarios"] = len(usuarios)

    return {"ok": True, "data": data}


# ── POST /topup — recargar créditos ───────────────────────────────────────────
@router.post("/topup", summary="Recargar créditos a un emisor")
async def topup_creditos(
    data:      dict         = Body(...),
    auth_data: dict         = Depends(verify_superadmin),
    db:        AsyncSession = Depends(get_db),
):
    emisor_id = data.get("emisor_id")
    cantidad  = data.get("cantidad", 0)
    notas     = data.get("notas", "Recarga manual admin")

    if not emisor_id or cantidad <= 0:
        raise HTTPException(status_code=400, detail="emisor_id y cantidad son requeridos.")

    await db.execute(text("""
        UPDATE user_credits
        SET balance_emision = balance_emision + :qty, last_updated = NOW()
        WHERE emisor_id = :eid
    """), {"qty": cantidad, "eid": emisor_id})

    await db.execute(text("""
        INSERT INTO credit_transactions
            (emisor_id, tipo, cantidad, precio_total, metodo_pago, notas)
        VALUES (:eid, 'RECARGA', :qty, 0.00, 'ADMIN', :notas)
    """), {"eid": emisor_id, "qty": cantidad, "notas": notas})

    await db.commit()
    return {"ok": True, "mensaje": f"{cantidad} créditos agregados al emisor {emisor_id}."}