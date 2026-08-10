# app/api/v1/public/integraciones.py
from typing import Optional
from fastapi import APIRouter, Depends, Body, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import verify_api_key
from app.core.config import settings
from app.schemas.integracion import ValidatePuntoRequest
from app.services.integracion_service import validar_estructura_core, obtener_status_core
from app.utils.factura_service import emitir_factura_core
from app.core.idempotency import verificar_idempotency, guardar_idempotency

router = APIRouter()

@router.post("/validate", summary="Validar establecimiento y punto de emisión")
async def api_validate_structure(
    request: ValidatePuntoRequest,
    auth:    dict         = Depends(verify_api_key),
    db:      AsyncSession = Depends(get_db),
):
    return await validar_estructura_core(auth["emisor_id"], request.estab_codigo, request.punto_codigo, db)


@router.get("/status", summary="Resumen completo del estado del emisor")
async def api_get_status(
    auth: dict         = Depends(verify_api_key),
    db:   AsyncSession = Depends(get_db),
):
    return await obtener_status_core(auth["emisor_id"], db)


@router.post("/invoice", summary="Emitir una factura electrónica (API Externa)")
async def api_invoice(
    request:           Request,
    factura_data:      dict          = Body(...),
    db:                AsyncSession  = Depends(get_db),
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    x_api_key:         Optional[str] = Header(None, alias="X-Api-Key"),
    x_internal_key:    Optional[str] = Header(None, alias="X-Internal-Key"),
):
    # ── Autenticar — clave interna tiene prioridad ─────────────────────────────
    if x_internal_key:
        if x_internal_key != settings.INTERNAL_API_KEY:
            raise HTTPException(status_code=403, detail="Clave interna inválida.")
        auth = {
            "emisor_id":  settings.KIPU_EMISOR_ID,
            "unlimited":  True,
            "api_key_id": None,
        }
    elif x_api_key:
        auth = await verify_api_key(x_api_key, db)
    else:
        raise HTTPException(status_code=401, detail="Autenticación requerida.")

    emisor_id = auth["emisor_id"]

    # ── Idempotencia ───────────────────────────────────────────────────────────
    cached = await verificar_idempotency(emisor_id, x_idempotency_key)
    if cached:
        return cached

    # ── Emitir ─────────────────────────────────────────────────────────────────
    result = await emitir_factura_core(
        factura_data,
        emisor_id,
        db,
        api_key_id = auth.get("api_key_id"),
        unlimited  = auth.get("unlimited", False),
    )

    if result.get("ok"):
        await guardar_idempotency(emisor_id, x_idempotency_key, result)

    return result