#app/api/v1/admin/clientes_n8n.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import verify_whatsapp_service, get_tenant_db_whatsapp # 🔒 Seguridad n8n
from app.schemas.cliente import ClienteCreate, ClienteBusquedaMasiva
from app.services.cliente_service import (
    crear_cliente_core, 
    consultar_cliente_por_identificacion_core, 
    consultar_clientes_bulk_core, 
    verificar_existencia_cliente_core
)

router = APIRouter()

@router.post("/")
async def crear_cliente(
    cliente_data: ClienteCreate, 
    auth_data: dict = Depends(verify_whatsapp_service), 
    db: AsyncSession = Depends(get_tenant_db_whatsapp)
):
    return await crear_cliente_core(auth_data["emisor_id"], cliente_data, db)

@router.post("/buscar")
async def buscar_clientes_masivo(
    busqueda: ClienteBusquedaMasiva, 
    auth_data: dict = Depends(verify_whatsapp_service), 
    db: AsyncSession = Depends(get_tenant_db_whatsapp)
):
    return await consultar_clientes_bulk_core(auth_data["emisor_id"], busqueda.terminos, db)

@router.get("/{identificacion}")
async def consultar_cliente(
    identificacion: str, 
    auth_data: dict = Depends(verify_whatsapp_service), 
    db: AsyncSession = Depends(get_tenant_db_whatsapp)
):
    # ¡Corregido! Ahora llama a la función con el nombre correcto
    return await consultar_cliente_por_identificacion_core(auth_data["emisor_id"], identificacion, db)