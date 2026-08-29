# app/api/v1/public/integraciones.py
from typing import Optional
from fastapi import APIRouter, Depends, Body, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import verify_api_key
from app.core.config import settings
from app.schemas.integracion import ValidatePuntoRequest
from app.services.integracion_service import validar_estructura_core, obtener_status_core
from app.services.documento_service import emitir_documento_core
from app.core.idempotency import verificar_idempotency, guardar_idempotency
from app.core.rate_limit import RateLimit, RateLimitScope

router = APIRouter()

# =============================================================================
# POST /validate
# =============================================================================
@router.post("/validate", summary="Validar establecimiento y punto de emisión")
async def api_validate_structure(
    request: ValidatePuntoRequest,
    auth:    dict         = Depends(verify_api_key),
    db:      AsyncSession = Depends(get_db),
):
    return await validar_estructura_core(
        auth["emisor_id"], request.estab_codigo, request.punto_codigo, db
    )

# =============================================================================
# GET /status
# =============================================================================
@router.get("/status", summary="Resumen completo del estado del emisor")
async def api_get_status(
    auth: dict         = Depends(verify_api_key),
    db:   AsyncSession = Depends(get_db),
):
    return await obtener_status_core(auth["emisor_id"], db)

# =============================================================================
# POST /emit — Emitir cualquier tipo de comprobante
# =============================================================================
@router.post("/emit", summary="Emitir comprobante electrónico (API Externa)")
async def api_emit(
    request:           Request,
    data:              dict          = Body(...),
    db:                AsyncSession  = Depends(get_db),
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    x_api_key:         Optional[str] = Header(None, alias="X-Api-Key"),
    x_internal_key:    Optional[str] = Header(None, alias="X-Internal-Key"),
    _rl:               None          = Depends(RateLimit(RateLimitScope.INVOICE)),
):
    # ── Idempotency obligatoria ───────────────────────────────────────────────
    if not x_idempotency_key:
        raise HTTPException(
            status_code=400,
            detail="Se requiere el header X-Idempotency-Key. Usa un UUID v4 único por comprobante."
        )

    # ── Auth ──────────────────────────────────────────────────────────────────
    es_interno = False
    if x_internal_key and x_internal_key == settings.INTERNAL_API_KEY:
        if not x_api_key:
            raise HTTPException(
                status_code=401,
                detail="Servicios internos requieren X-Api-Key para identificar el emisor."
            )
        auth       = await verify_api_key(x_api_key, db)
        es_interno = True
    elif x_api_key:
        auth = await verify_api_key(x_api_key, db)
    else:
        raise HTTPException(
            status_code=401,
            detail="Autenticación requerida. Usa X-Api-Key o X-Internal-Key + X-Api-Key."
        )

    emisor_id  = auth["emisor_id"]
    api_key_id = auth.get("api_key_id") if not es_interno else None
    es_sandbox = auth.get("es_sandbox", False)

    # ── Idempotencia ──────────────────────────────────────────────────────────
    cached = await verificar_idempotency(emisor_id, x_idempotency_key)
    if cached:
        return cached

    # ── Tipo de documento ─────────────────────────────────────────────────────
    tipo_doc = data.pop("tipo_doc", "FAC").upper()
    if tipo_doc not in ("FAC", "LIQ", "NCR", "NDB", "RET"):
        raise HTTPException(
            status_code=400,
            detail=f"tipo_doc inválido: {tipo_doc}. Válidos: FAC, LIQ, NCR, NDB, RET."
        )

    # ── Emitir ────────────────────────────────────────────────────────────────
    result = await emitir_documento_core(
        tipo_doc   = tipo_doc,
        data       = data,
        emisor_id  = emisor_id,
        db         = db,
        api_key_id = api_key_id,
        es_sandbox = es_sandbox,
    )

    if result.get("ok"):
        await guardar_idempotency(emisor_id, x_idempotency_key, result)

    return result

# =============================================================================
# POST /invoice — Legacy, redirige a /emit (backwards compat)
# =============================================================================
@router.post("/invoice", summary="[Deprecado] Usar /emit con tipo_doc=FAC")
async def api_invoice_legacy(
    request:           Request,
    data:              dict          = Body(...),
    db:                AsyncSession  = Depends(get_db),
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    x_api_key:         Optional[str] = Header(None, alias="X-Api-Key"),
    x_internal_key:    Optional[str] = Header(None, alias="X-Internal-Key"),
    _rl:               None          = Depends(RateLimit(RateLimitScope.INVOICE)),
):
    """Mantiene compatibilidad con integraciones existentes."""
    data["tipo_doc"] = "FAC"
    return await api_emit(
        request           = request,
        data              = data,
        db                = db,
        x_idempotency_key = x_idempotency_key,
        x_api_key         = x_api_key,
        x_internal_key    = x_internal_key,
        _rl               = None,
    )