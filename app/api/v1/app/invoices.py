from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import verify_firebase_token
from app.schemas.factura import FacturaCreate
from app.utils.sri_service import emitir_factura_core
from app.services.invoice_service import obtener_historial_core

router = APIRouter()

@router.post("/emit", summary="Emitir una factura electrónica (App Web)")
async def emitir_factura_app(
    factura_data: FacturaCreate, 
    auth_data: dict = Depends(verify_firebase_token), 
    db: AsyncSession = Depends(get_db)
):
    """
    Genera, firma, almacena y registra una factura electrónica en formato SRI. 
    Utiliza el token de Firebase del usuario actual.
    """
    # model_dump() convierte el objeto Pydantic a un diccionario limpio de Python
    return await emitir_factura_core(factura_data.model_dump(), auth_data["emisor_id"], db)

@router.get("/history", summary="Obtener historial de facturas")
async def historial_facturas(
    auth_data: dict = Depends(verify_firebase_token), 
    db: AsyncSession = Depends(get_db)
):
    """
    Retorna el listado de las últimas 50 facturas emitidas por el emisor, 
    ordenadas por fecha de creación descendente.
    """
    return await obtener_historial_core(auth_data["emisor_id"], db)