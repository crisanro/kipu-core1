#app/api/v1/app/clientes.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import verify_firebase_token, get_tenant_db
from app.schemas.cliente import ClienteCreate, ClienteBusquedaMasiva, ClienteUpdate

from app.services.cliente_service import (
    crear_cliente_core, 
    consultar_cliente_por_identificacion_core, 
    consultar_clientes_bulk_core, 
    verificar_existencia_cliente_core,
    consultar_todos_clientes_core,
    consultar_detalle_cliente_core,
    actualizar_cliente_core
)

router = APIRouter()

@router.post("/")
async def crear_cliente(
    cliente_data: ClienteCreate, 
    auth_data: dict = Depends(verify_firebase_token), 
    db: AsyncSession = Depends(get_tenant_db)
):
    # Crea un cliente nuevo en la base del emisor
    return await crear_cliente_core(auth_data["emisor_id"], cliente_data, db)


# 2. Agrega este endpoint (ponlo justo debajo del POST de crear_cliente, por ejemplo):
@router.get("/")
async def listar_todos_los_clientes(
    auth_data: dict = Depends(verify_firebase_token), 
    db: AsyncSession = Depends(get_tenant_db)
):
    """
    Devuelve la lista completa de clientes asociados a este emisor.
    Ideal para llenar la tabla principal de clientes en el Dashboard.
    """
    return await consultar_todos_clientes_core(auth_data["emisor_id"], db)


@router.post("/buscar")
async def buscar_clientes_masivo(
    busqueda: ClienteBusquedaMasiva, 
    auth_data: dict = Depends(verify_firebase_token), 
    db: AsyncSession = Depends(get_tenant_db)
):
    # Búsqueda masiva (ideal para tablas o listados) + Consumidor Final
    return await consultar_clientes_bulk_core(auth_data["emisor_id"], busqueda.terminos, db)

@router.get("/verificar-cliente/{identificacion}")
async def verificar_cliente(
    identificacion: str, 
    auth_data: dict = Depends(verify_firebase_token), 
    db: AsyncSession = Depends(get_tenant_db)
):
    # Devuelve TODAS las coincidencias locales (útil por si hay pasaportes repetidos)
    return await verificar_existencia_cliente_core(auth_data["emisor_id"], identificacion, db)

@router.get("/{identificacion}")
async def consultar_cliente(
    identificacion: str, 
    auth_data: dict = Depends(verify_firebase_token), 
    db: AsyncSession = Depends(get_tenant_db)
):
    # Busca 1 cliente específico. Si no lo tiene el emisor, busca en la global para sugerir el nombre
    return await consultar_cliente_por_identificacion_core(auth_data["emisor_id"], identificacion, db)

@router.patch("/{cliente_id}", summary="Actualizar datos de un cliente")
async def actualizar_cliente(
    cliente_id: str,
    cliente_data: ClienteUpdate,
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_tenant_db)
):
    """
    Actualiza la Razón Social, Dirección, Email o Teléfono de un cliente.
    Todos los datos de texto se guardarán automáticamente en MAYÚSCULAS.
    La identificación no es editable.
    """
    emisor_id = auth_data.get("emisor_id")
    
    if not emisor_id:
        raise HTTPException(status_code=400, detail="EL USUARIO NO TIENE UN EMISOR VINCULADO.")    
    return await actualizar_cliente_core(emisor_id, cliente_id, cliente_data, db)


@router.get("/detalle/{cliente_id}")
async def consultar_detalle_cliente(
    cliente_id: str, 
    auth_data: dict = Depends(verify_firebase_token), 
    db: AsyncSession = Depends(get_tenant_db)
):
    """
    Devuelve la información completa del cliente por su UID,
    incluyendo su historial de facturas y la suma total facturada.
    """
    return await consultar_detalle_cliente_core(auth_data["emisor_id"], cliente_id, db)


