# app/api/v1/app/clientes.py
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi import Query as QueryParam
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import verify_firebase_token
from app.core.permisos import verificar_permiso
from app.schemas.cliente import ClienteCreate, ClienteBusquedaMasiva, ClienteUpdate
from app.services.cliente_service import (
    crear_cliente_core,
    consultar_cliente_por_identificacion_core,
    consultar_clientes_bulk_core,
    verificar_existencia_cliente_core,
    consultar_todos_clientes_core,
    consultar_detalle_cliente_core,
    actualizar_cliente_core,
    buscar_clientes_core
)
from app.services.audit_service import audit_log

router = APIRouter()

@router.post("")
async def crear_cliente(
    cliente_data: ClienteCreate,
    request:      Request,
    auth_data:    dict         = Depends(verify_firebase_token),
    db:           AsyncSession = Depends(get_db)
):
    verificar_permiso(auth_data, "clientes")
    result = await crear_cliente_core(auth_data["emisor_id"], cliente_data, db)
    await audit_log(
        db        = db,
        auth_data = auth_data,
        accion    = "CREATE",
        entidad   = "cliente",
        entidad_id = result.get("data", {}).get("id") if result.get("data") else None,
        detalle   = {
            "identificacion": cliente_data.identificacion,
            "razon_social":   cliente_data.razon_social,
        },
        request   = request,
    )
    await db.commit()
    return result

@router.get("")
async def listar_todos_los_clientes(
    auth_data: dict = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db),
    q:         str  = QueryParam(None),
):
    verificar_permiso(auth_data, "clientes")
    if q:
        return await buscar_clientes_core(auth_data["emisor_id"], q, db)
    return await consultar_todos_clientes_core(auth_data["emisor_id"], db)

@router.post("/buscar")
async def buscar_clientes_masivo(
    busqueda:  ClienteBusquedaMasiva,
    auth_data: dict         = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db)
):
    verificar_permiso(auth_data, "clientes")
    return await consultar_clientes_bulk_core(auth_data["emisor_id"], busqueda.terminos, db)

@router.get("/verificar-cliente/{identificacion}")
async def verificar_cliente(
    identificacion: str,
    auth_data:      dict         = Depends(verify_firebase_token),
    db:             AsyncSession = Depends(get_db)
):
    verificar_permiso(auth_data, "clientes")
    return await verificar_existencia_cliente_core(auth_data["emisor_id"], identificacion, db)

@router.get("/detalle/{cliente_id}")
async def consultar_detalle_cliente(
    cliente_id: str,
    auth_data:  dict         = Depends(verify_firebase_token),
    db:         AsyncSession = Depends(get_db)
):
    verificar_permiso(auth_data, "clientes")
    return await consultar_detalle_cliente_core(auth_data["emisor_id"], cliente_id, db)

@router.get("/{identificacion}")
async def consultar_cliente(
    identificacion: str,
    auth_data:      dict         = Depends(verify_firebase_token),
    db:             AsyncSession = Depends(get_db)
):
    verificar_permiso(auth_data, "clientes")
    return await consultar_cliente_por_identificacion_core(auth_data["emisor_id"], identificacion, db)

@router.patch("/{cliente_id}", summary="Actualizar datos de un cliente")
async def actualizar_cliente(
    cliente_id:   str,
    cliente_data: ClienteUpdate,
    request:      Request,
    auth_data:    dict         = Depends(verify_firebase_token),
    db:           AsyncSession = Depends(get_db)
):
    emisor_id = auth_data.get("emisor_id")
    if not emisor_id:
        raise HTTPException(status_code=400, detail="EL USUARIO NO TIENE UN EMISOR VINCULADO.")
    verificar_permiso(auth_data, "clientes")

    result = await actualizar_cliente_core(emisor_id, cliente_id, cliente_data, db)
    await audit_log(
        db        = db,
        auth_data = auth_data,
        accion    = "UPDATE",
        entidad   = "cliente",
        entidad_id = cliente_id,
        detalle   = cliente_data.model_dump(exclude_none=True),
        request   = request,
    )
    await db.commit()
    return result