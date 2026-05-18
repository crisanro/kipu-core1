# app/api/v1/public/integraciones.py — CON IDEMPOTENCY KEY
from typing import Optional
from fastapi import APIRouter, Depends, Body, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import verify_api_key
from app.schemas.integracion import ValidatePuntoRequest
from app.services.integracion_service import validar_estructura_core, obtener_status_core
from app.utils.sri_service import emitir_factura_core
from app.core.idempotency import verificar_idempotency, guardar_idempotency

router = APIRouter()


@router.post("/validate", summary="Validar establecimiento y punto de emisión")
async def api_validate_structure(
    request: ValidatePuntoRequest,
    auth: dict = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    return await validar_estructura_core(auth["emisor_id"], request.estab_codigo, request.punto_codigo, db)


@router.get("/status", summary="Resumen completo del estado del emisor")
async def api_get_status(
    auth: dict = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    return await obtener_status_core(auth["emisor_id"], db)


@router.post("/invoice", summary="Emitir una factura electrónica (API Externa)")
async def api_invoice(
    factura_data: dict = Body(...),
    auth: dict = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
):
    emisor_id = auth["emisor_id"]

    # ── Verificar si ya fue procesado ─────────────────────────────────────────
    cached = await verificar_idempotency(emisor_id, x_idempotency_key)
    if cached:
        return cached

    # ── Procesar ──────────────────────────────────────────────────────────────
    result = await emitir_factura_core(factura_data, emisor_id, db)

    # ── Guardar solo si fue exitoso ───────────────────────────────────────────
    if result.get("ok"):
        await guardar_idempotency(emisor_id, x_idempotency_key, result)

    return result