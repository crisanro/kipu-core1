from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date
from app.core.database import get_db
from app.core.security import verify_firebase_token
from app.services.dashboard_service import obtener_dashboard_core, consultar_detalle_factura_core

router = APIRouter()

@router.get("/", summary="Obtener datos globales del Dashboard")
async def get_dashboard(
    fecha_inicio: date = Query(..., description="Fecha inicial (YYYY-MM-DD)"),
    fecha_fin: date = Query(..., description="Fecha final (YYYY-MM-DD)"),
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db)
):
    """
    Retorna el estado de salud del emisor (firma, créditos, configuración), 
    resumen de ventas y las últimas 50 facturas en el rango de fechas.
    """
    # Extraemos tanto el ID del emisor como el email desde Firebase
    return await obtener_dashboard_core(
        emisor_id=auth_data.get("emisor_id"), 
        email_usuario=auth_data.get("email"), 
        fecha_inicio=fecha_inicio, 
        fecha_fin=fecha_fin, 
        db=db
    )


@router.get("/factura/{factura_id}", summary="Obtener detalles de una factura específica")
async def get_detalle_factura(
    factura_id: str,
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db)
):
    """
    Retorna toda la información de una factura (ítems, pagos, totales) 
    junto con los datos del cliente asociado.
    """
    return await consultar_detalle_factura_core(
        emisor_id=auth_data["emisor_id"], 
        factura_id=factura_id, 
        db=db
    )