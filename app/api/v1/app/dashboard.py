# app/api/v1/app/dashboard.py — OPTIMIZADO con cache
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date
from app.core.database import get_db
from app.core.security import verify_firebase_token
from app.services.dashboard_service import obtener_dashboard_core, consultar_detalle_factura_core
from app.core.cache import cache_get, cache_set, CK, TTL

router = APIRouter()


@router.get("/", summary="Obtener datos globales del Dashboard")
async def get_dashboard(
    fecha_inicio: date = Query(..., description="Fecha inicial (YYYY-MM-DD)"),
    fecha_fin:    date = Query(..., description="Fecha final (YYYY-MM-DD)"),
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db),
):
    emisor_id = auth_data.get("emisor_id")

    # Cache por emisor + rango de fechas
    cache_key = CK.fmt(CK.DASHBOARD, eid=emisor_id, fi=fecha_inicio, ff=fecha_fin)
    cached = await cache_get(cache_key)
    if cached:
        return cached

    result = await obtener_dashboard_core(
        emisor_id=emisor_id,
        email_usuario=auth_data.get("email"),
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        db=db,
    )

    # TTL corto (2 min) — el dashboard muestra datos recientes
    await cache_set(cache_key, result, TTL.DASHBOARD)
    return result


@router.get("/factura/{factura_id}", summary="Obtener detalles de una factura específica")
async def get_detalle_factura(
    factura_id: str,
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db),
):
    # El detalle de una factura es inmutable una vez AUTORIZADA — TTL largo
    cache_key = f"factura_detalle:{auth_data['emisor_id']}:{factura_id}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    result = await consultar_detalle_factura_core(
        emisor_id=auth_data["emisor_id"],
        factura_id=factura_id,
        db=db,
    )

    # Solo cachear si la factura está autorizada (estado final)
    estado = result.get("factura", {}).get("estado", "")
    if estado == "AUTORIZADO":
        await cache_set(cache_key, result, 3600)  # 1 hora — estado inmutable

    return result
