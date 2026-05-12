from fastapi import APIRouter, Depends, Body
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import verify_api_key
from app.schemas.integracion import ValidatePuntoRequest
from app.services.integracion_service import validar_estructura_core, obtener_status_core
from app.utils.sri_service import emitir_factura_core

router = APIRouter()

@router.post("/validate", summary="Validar establecimiento y punto de emisión")
async def api_validate_structure(
    request: ValidatePuntoRequest, 
    auth: dict = Depends(verify_api_key), 
    db: AsyncSession = Depends(get_db)
):
    """
    Verifica si una combinación de códigos de establecimiento y punto 
    existe y pertenece al emisor de la API Key.
    """
    return await validar_estructura_core(auth["emisor_id"], request.estab_codigo, request.punto_codigo, db)


@router.get("/status", summary="Resumen completo del estado del emisor")
async def api_get_status(
    auth: dict = Depends(verify_api_key), 
    db: AsyncSession = Depends(get_db)
):
    """
    Devuelve información fiscal del emisor, estado de la firma electrónica, 
    saldo de créditos y las últimas 20 facturas emitidas.
    """
    return await obtener_status_core(auth["emisor_id"], db)


@router.post("/invoice", summary="Emitir una factura electrónica (API Externa)")
async def api_invoice(
    factura_data: dict = Body(...), # Aquí irá el schema JSON de tu factura
    auth: dict = Depends(verify_api_key), 
    db: AsyncSession = Depends(get_db)
):
    """
    Genera, firma, almacena y registra una factura electrónica en formato SRI. 
    Este proceso descuenta 1 crédito del saldo del emisor.
    """
    # 💥 Aquí consumimos la función CORE que armamos para n8n y la App
    return await emitir_factura_core(factura_data, auth["emisor_id"], db)