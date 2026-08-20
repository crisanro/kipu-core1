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


# =============================================================================
# GUARD SUPERADMIN
# =============================================================================

async def verify_superadmin(auth_data: dict = Depends(verify_firebase_token)):
    if auth_data.get("role") != "superadmin":
        raise HTTPException(status_code=403, detail="Acceso restringido.")
    return auth_data


# =============================================================================
# SCHEMAS
# =============================================================================

class NotificacionMasivaRequest(BaseModel):
    titulo:     str
    mensaje:    str
    tipo:       str          = "SISTEMA"
    referencia: Optional[str] = None
    emisor_id:  Optional[int] = None


# =============================================================================
# GET /emisores
# =============================================================================

@router.get("/emisores", summary="Listar todos los emisores")
async def listar_emisores(
    auth_data: dict         = Depends(verify_superadmin),
    db:        AsyncSession = Depends(get_db),
):
    res = await db.execute(text("""
        SELECT
            e.id, e.ruc, e.razon_social, e.nombre_comercial,
            e.ambiente, e.tipo_emisor, e.created_at,
            COALESCE(uc.balance, 0)  AS balance_api,
            s.estado                 AS sub_estado,
            s.plan                   AS sub_plan,
            COUNT(DISTINCT eu.profile_id)                              AS total_usuarios,
            COUNT(DISTINCT CASE WHEN d.estado_sri = 'AUTORIZADO'
                                 AND d.tipo_doc IN ('FAC','LIQ')
                            THEN d.id END)                             AS total_documentos
        FROM emisores e
        LEFT JOIN user_credits  uc ON uc.emisor_id = e.id
        LEFT JOIN subscriptions s  ON s.emisor_id  = e.id
        LEFT JOIN emisor_usuarios eu ON eu.emisor_id = e.id
        LEFT JOIN documentos_emitidos d ON d.emisor_id = e.id
        GROUP BY e.id, uc.balance, s.estado, s.plan
        ORDER BY e.created_at DESC
    """))
    rows = res.fetchall()
    return {
        "ok":   True,
        "data": [dict(r._mapping) for r in rows],
    }


# =============================================================================
# POST /notificar
# =============================================================================

@router.post("/notificar", summary="Enviar notificación masiva o individual")
async def enviar_notificacion(
    data:      NotificacionMasivaRequest,
    auth_data: dict         = Depends(verify_superadmin),
    db:        AsyncSession = Depends(get_db),
):
    if data.emisor_id:
        await crear_notificacion(
            db         = db,
            emisor_id  = data.emisor_id,
            tipo       = data.tipo,
            titulo     = data.titulo,
            mensaje    = data.mensaje,
            referencia = data.referencia,
        )
        return {"ok": True, "mensaje": f"Notificación enviada al emisor {data.emisor_id}."}
    else:
        await notificar_todos_emisores(
            db              = db,
            tipo            = data.tipo,
            titulo          = data.titulo,
            mensaje         = data.mensaje,
            referencia      = data.referencia,
            solo_produccion = True,
        )
        return {"ok": True, "mensaje": "Notificación enviada a todos los emisores en producción."}


# =============================================================================
# GET /stats
# =============================================================================

@router.get("/stats", summary="Estadísticas globales de Kipu")
async def stats_globales(
    auth_data: dict         = Depends(verify_superadmin),
    db:        AsyncSession = Depends(get_db),
):
    res = await db.execute(text("""
        SELECT
            COUNT(DISTINCT e.id)                                                AS total_emisores,
            COUNT(DISTINCT CASE WHEN e.ambiente = 2 THEN e.id END)              AS en_produccion,
            COUNT(DISTINCT CASE WHEN e.ambiente = 1 THEN e.id END)              AS en_pruebas,
            COUNT(DISTINCT CASE WHEN s.estado IN ('ACTIVO','TRIAL') THEN e.id END) AS con_suscripcion,
            COUNT(DISTINCT d.id)                                                AS total_documentos,
            COALESCE(SUM(d.importe_total), 0)                                   AS monto_total,
            COUNT(DISTINCT CASE WHEN d.estado_sri = 'AUTORIZADO' THEN d.id END) AS autorizados,
            COALESCE(SUM(uc.balance), 0)                                        AS creditos_api_totales
        FROM emisores e
        LEFT JOIN documentos_emitidos d ON d.emisor_id = e.id
                                       AND d.tipo_doc IN ('FAC', 'LIQ')
        LEFT JOIN user_credits  uc ON uc.emisor_id = e.id
        LEFT JOIN subscriptions s  ON s.emisor_id  = e.id
    """))
    row = res.fetchone()
    return {"ok": True, "data": dict(row._mapping)}


# =============================================================================
# GET /emisores/{id}
# =============================================================================

@router.get("/emisores/{emisor_id}", summary="Detalle de un emisor")
async def detalle_emisor(
    emisor_id: int,
    auth_data: dict         = Depends(verify_superadmin),
    db:        AsyncSession = Depends(get_db),
):
    # Emisor base
    res = await db.execute(text("""
        SELECT
            e.*,
            e.p12_path IS NOT NULL      AS firma_ok,
            COALESCE(uc.balance, 0)     AS balance_api,
            s.estado                    AS sub_estado,
            s.plan                      AS sub_plan,
            s.periodo                   AS sub_periodo,
            s.current_period_end        AS sub_period_end,
            s.cancel_at_period_end
        FROM emisores e
        LEFT JOIN user_credits  uc ON uc.emisor_id = e.id
        LEFT JOIN subscriptions s  ON s.emisor_id  = e.id
        WHERE e.id = :eid
    """), {"eid": emisor_id})
    emisor = res.fetchone()
    if not emisor:
        raise HTTPException(status_code=404, detail="Emisor no encontrado.")

    # Usuarios
    res_u = await db.execute(text("""
        SELECT p.id AS profile_id, p.email, p.full_name AS nombre, eu.rol
        FROM emisor_usuarios eu
        JOIN profiles p ON p.id = eu.profile_id
        WHERE eu.emisor_id = :eid
        ORDER BY eu.created_at ASC
    """), {"eid": emisor_id})
    usuarios = [dict(r._mapping) for r in res_u.fetchall()]

    # Últimos 20 documentos
    res_d = await db.execute(text("""
        SELECT id, numero_doc, tipo_doc, estado_sri,
               importe_total, fecha_emision
        FROM documentos_emitidos
        WHERE emisor_id = :eid
        ORDER BY created_at DESC
        LIMIT 20
    """), {"eid": emisor_id})
    documentos = [dict(r._mapping) for r in res_d.fetchall()]

    # Conteos
    res_cnt = await db.execute(text("""
        SELECT
            COUNT(*)                                                           AS total_documentos,
            COUNT(CASE WHEN estado_sri = 'AUTORIZADO' THEN 1 END)             AS autorizados,
            COUNT(CASE WHEN tipo_doc = 'FAC' THEN 1 END)                      AS facturas,
            COUNT(CASE WHEN tipo_doc = 'RET' THEN 1 END)                      AS retenciones
        FROM documentos_emitidos
        WHERE emisor_id = :eid
    """), {"eid": emisor_id})
    cnt = res_cnt.fetchone()

    data                  = dict(emisor._mapping)
    data["usuarios"]      = usuarios
    data["documentos"]    = documentos
    data["conteos"]       = dict(cnt._mapping)
    data["total_usuarios"] = len(usuarios)

    return {"ok": True, "data": data}


# =============================================================================
# POST /topup
# =============================================================================

@router.post("/topup", summary="Recargar créditos API a un emisor")
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
        SET balance = balance + :qty, last_updated = NOW()
        WHERE emisor_id = :eid
    """), {"qty": cantidad, "eid": emisor_id})

    await db.execute(text("""
        INSERT INTO credit_transactions
            (emisor_id, tipo, cantidad, precio_total, metodo_pago, notas)
        VALUES
            (:eid, 'BONO', :qty, 0.00, 'ADMIN', :notas)
    """), {"eid": emisor_id, "qty": cantidad, "notas": notas})

    await db.commit()
    return {"ok": True, "mensaje": f"{cantidad} créditos API agregados al emisor {emisor_id}."}


# =============================================================================
# POST /suscripcion/forzar — activar/cancelar suscripción manualmente
# =============================================================================

@router.post("/suscripcion/forzar", summary="Forzar estado de suscripción")
async def forzar_suscripcion(
    data:      dict         = Body(...),
    auth_data: dict         = Depends(verify_superadmin),
    db:        AsyncSession = Depends(get_db),
):
    """Para casos de soporte — activar trial, cancelar, etc."""
    emisor_id = data.get("emisor_id")
    estado    = data.get("estado")  # ACTIVO | TRIAL | CANCELADO | VENCIDO
    plan      = data.get("plan", "NATURAL")
    periodo   = data.get("periodo", "MENSUAL")

    if not emisor_id or not estado:
        raise HTTPException(status_code=400, detail="emisor_id y estado son requeridos.")

    await db.execute(text("""
        INSERT INTO subscriptions
            (emisor_id, plan, periodo, estado)
        VALUES
            (:eid, :plan, :periodo, :estado)
        ON CONFLICT (emisor_id) DO UPDATE SET
            estado     = EXCLUDED.estado,
            plan       = EXCLUDED.plan,
            periodo    = EXCLUDED.periodo,
            updated_at = NOW()
    """), {
        "eid":     emisor_id,
        "plan":    plan,
        "periodo": periodo,
        "estado":  estado,
    })
    await db.commit()

    return {"ok": True, "mensaje": f"Suscripción del emisor {emisor_id} → {estado}."}