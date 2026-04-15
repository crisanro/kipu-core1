from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import verify_api_key # 🔒 Seguridad API Key
from app.schemas.cliente import ClienteCreate, ClienteBusquedaMasiva
from app.services.cliente_service import (
    crear_cliente_core, 
    consultar_cliente_por_identificacion_core, 
    consultar_clientes_bulk_core,
    verificar_existencia_cliente_core # Lo dejo importado por si en el futuro quieres añadir el endpoint de verificar aquí también
)

router = APIRouter()

@router.post("/")
async def crear_cliente(
    cliente_data: ClienteCreate, 
    auth_data: dict = Depends(verify_api_key), 
    db: AsyncSession = Depends(get_db)
):
    return await crear_cliente_core(auth_data["emisor_id"], cliente_data, db)

@router.post("/buscar")
async def buscar_clientes_masivo(
    busqueda: ClienteBusquedaMasiva, 
    auth_data: dict = Depends(verify_api_key), 
    db: AsyncSession = Depends(get_db)
):
    return await consultar_clientes_bulk_core(auth_data["emisor_id"], busqueda.terminos, db)

@router.get("/{identificacion}")
async def consultar_cliente(
    identificacion: str, 
    auth_data: dict = Depends(verify_api_key), 
    db: AsyncSession = Depends(get_db)
):
    # ¡Corregido! Ahora usa la nueva función core
    return await consultar_cliente_por_identificacion_core(auth_data["emisor_id"], identificacion, db)