# app/api/v1/app/invoices.py — CON IDEMPOTENCY KEY
from typing import Optional
from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import verify_firebase_token
from app.schemas.factura import FacturaCreate
from app.utils.sri_service import emitir_factura_core
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
    _rl: None = Depends(RateLimit(RateLimitScope.GENERAL)),
):
    return await obtener_historial_core(auth_data["emisor_id"], db)