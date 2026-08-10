# app/api/v1/app/invoices.py — CON IDEMPOTENCY KEY
from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


from app.core.database import get_db
from app.core.security import verify_firebase_token
from app.schemas.factura import FacturaCreate
from app.utils.factura_service import emitir_factura_core
from app.services.invoice_service import obtener_historial_core
from app.core.rate_limit import RateLimit, RateLimitScope
from app.core.idempotency import verificar_idempotency, guardar_idempotency

router = APIRouter()


@router.post("/emit", summary="Emitir una factura electrónica (App Web)")
async def emitir_factura_app(
    factura_data: FacturaCreate,
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db),
    _rl: None = Depends(RateLimit(RateLimitScope.INVOICE)),
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
):
    emisor_id = auth_data["emisor_id"]

    # ── Verificar si ya fue procesado ─────────────────────────────────────────
    cached = await verificar_idempotency(emisor_id, x_idempotency_key)
    if cached:
        return cached

    # ── Procesar ──────────────────────────────────────────────────────────────
    result = await emitir_factura_core(factura_data.model_dump(), emisor_id, db)

    # ── Guardar solo si fue exitoso ───────────────────────────────────────────
    if result.get("ok"):
        await guardar_idempotency(emisor_id, x_idempotency_key, result)

    return result


@router.get("/history", summary="Obtener historial de facturas")
async def historial_facturas(
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db),
    fecha_inicio: Optional[str] = None,
    fecha_fin: Optional[str] = None,
    _rl: None = Depends(RateLimit(RateLimitScope.GENERAL)),
):
    return await obtener_historial_core(
        auth_data["emisor_id"], db, fecha_inicio, fecha_fin
    )


@router.post("/{factura_id}/reintentar", summary="Reintentar envío al SRI")
async def reintentar_factura(
    factura_id: str,
    auth_data:  dict        = Depends(verify_firebase_token),
    db:         AsyncSession = Depends(get_db),
):
    emisor_id = auth_data.get("emisor_id")
    if not emisor_id:
        raise HTTPException(status_code=400, detail="EMISOR NO VINCULADO.")

    # Verificar que la factura existe, pertenece al emisor y está en estado reintentable
    res = await db.execute(text("""
        SELECT id, estado, clave_acceso FROM invoices_emitidas
        WHERE id = :id AND emisor_id = :eid
    """), {"id": factura_id, "eid": emisor_id})
    factura = res.fetchone()

    if not factura:
        raise HTTPException(status_code=404, detail="Factura no encontrada.")

    if factura.estado not in ("DEVUELTA", "RECHAZADO", "FIRMADO"):
        raise HTTPException(
            status_code=400,
            detail=f"No se puede reintentar una factura en estado {factura.estado}."
        )

    # Resetear estado a FIRMADO y encolar de nuevo
    await db.execute(text("""
        UPDATE invoices_emitidas
        SET estado = 'FIRMADO', mensajes_sri = NULL, updated_at = NOW()
        WHERE id = :id AND emisor_id = :eid
    """), {"id": factura_id, "eid": emisor_id})
    await db.commit()

    # Encolar
    from app.core.cache import get_redis
    redis = await get_redis()
    await redis.lpush("kipu:queue:emision", str(factura_id))

    print(f"[Reintento] 🔄 {factura.clave_acceso} → reencola")

    return {
        "ok":      True,
        "mensaje": "Factura reencolada para reintento.",
        "estado":  "FIRMADO",
    }