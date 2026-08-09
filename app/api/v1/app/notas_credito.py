# app/api/v1/app/notas_credito.py
from typing import Optional
from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from app.core.database import get_db
from app.core.security import verify_firebase_token
from app.core.rate_limit import RateLimit, RateLimitScope
from app.core.idempotency import verificar_idempotency, guardar_idempotency
from app.utils.nc_service import emitir_nota_credito_core

router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────────────────────

class ItemNC(BaseModel):
    codigo:          Optional[str]   = None
    descripcion:     str             = Field(..., min_length=2)
    cantidad:        float           = Field(..., gt=0)
    precio_unitario: float           = Field(..., ge=0)
    descuento:       float           = Field(0.0, ge=0)
    tipo_iva:        Optional[str]   = Field("15")
    unidad_medida:   Optional[str]   = Field("UNIDAD")


class NotaCreditoCreate(BaseModel):
    factura_id: str  = Field(..., description="UUID de la factura autorizada a anular/ajustar")
    motivo:     str  = Field(..., min_length=5, max_length=300)
    items:      list[ItemNC] = Field(..., min_length=1)


# ── POST / — Emitir nota de crédito ───────────────────────────────────────────

@router.post(
    "",
    summary="Emitir nota de crédito electrónica",
    status_code=201,
)
async def emitir_nota_credito(
    nc_data: NotaCreditoCreate,
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db),
    _rl: None = Depends(RateLimit(RateLimitScope.INVOICE)),
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
):
    emisor_id = auth_data["emisor_id"]

    # Idempotencia
    cached = await verificar_idempotency(emisor_id, x_idempotency_key)
    if cached:
        return cached

    result = await emitir_nota_credito_core(
        nc_data   = nc_data.model_dump(),
        emisor_id = emisor_id,
        db        = db,
    )

    if result.get("ok"):
        await guardar_idempotency(emisor_id, x_idempotency_key, result)

    return result


# ── GET /{id} — Detalle de una nota de crédito ────────────────────────────────

@router.get(
    "/{nc_id}",
    summary="Obtener detalle de una nota de crédito",
)
async def detalle_nota_credito(
    nc_id: str,
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import text
    emisor_id = auth_data["emisor_id"]

    res = await db.execute(text("""
        SELECT id, numero_factura, clave_acceso, fecha_emision, estado,
               razon_social_comprador, identificacion_comprador,
               importe_total, datos_factura, mensajes_sri,
               fecha_autorizacion, created_at
        FROM invoices_emitidas
        WHERE id = :id
          AND emisor_id = :eid
          AND datos_factura->>'codDoc' = '04'
    """), {"id": nc_id, "eid": emisor_id})
    row = res.fetchone()

    if not row:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Nota de crédito no encontrada.")

    return {
        "ok": True,
        "data": {
            "id":                      str(row.id),
            "numero_factura":          row.numero_factura,
            "clave_acceso":            row.clave_acceso,
            "fecha_emision":           str(row.fecha_emision),
            "estado":                  row.estado,
            "razon_social_comprador":  row.razon_social_comprador,
            "identificacion_comprador": row.identificacion_comprador,
            "importe_total":           float(row.importe_total),
            "datos_factura":           row.datos_factura,
            "mensajes_sri":            row.mensajes_sri,
            "fecha_autorizacion":      str(row.fecha_autorizacion) if row.fecha_autorizacion else None,
            "created_at":              str(row.created_at),
        }
    }