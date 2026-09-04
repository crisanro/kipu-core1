# app/api/v1/app/proformas.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import verify_firebase_token
from app.core.permisos import verificar_permiso
from pydantic import BaseModel
from typing import Optional, List
from datetime import date

router = APIRouter()

# ── Schemas ────────────────────────────────────────────────────────────────────
class ItemProforma(BaseModel):
    descripcion:     str
    cantidad:        float = 1
    precio_unitario: float
    tipo_iva:        int   = 15   # 0 | 8 | 15

class ProformaCreate(BaseModel):
    cliente_id:    Optional[str]  = None
    fecha_emision: Optional[date] = None
    fecha_validez: Optional[date] = None
    items:         List[ItemProforma]
    notas:         Optional[str]  = None

class FacturarProforma(BaseModel):
    documento_emitido_id: str


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("")
async def crear_proforma(
    datos:     ProformaCreate,
    auth_data: dict         = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db),
):
    verificar_permiso(auth_data, "emitir")
    from app.services.proforma_service import crear_proforma_core
    return await crear_proforma_core(
        auth_data["emisor_id"],
        datos.model_dump(),
        db
    )


@router.get("")
async def listar_proformas(
    auth_data: dict         = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db),
):
    verificar_permiso(auth_data, "emitir")
    from app.services.proforma_service import listar_proformas_core
    return await listar_proformas_core(auth_data["emisor_id"], db)


@router.get("/{proforma_id}")
async def detalle_proforma(
    proforma_id: str,
    auth_data:   dict         = Depends(verify_firebase_token),
    db:          AsyncSession = Depends(get_db),
):
    verificar_permiso(auth_data, "emitir")
    from app.services.proforma_service import detalle_proforma_core
    return await detalle_proforma_core(auth_data["emisor_id"], proforma_id, db)


@router.patch("/{proforma_id}/facturar")
async def facturar_proforma(
    proforma_id: str,
    datos:       FacturarProforma,
    auth_data:   dict         = Depends(verify_firebase_token),
    db:          AsyncSession = Depends(get_db),
):
    verificar_permiso(auth_data, "emitir")
    from app.services.proforma_service import facturar_proforma_core
    return await facturar_proforma_core(
        auth_data["emisor_id"],
        proforma_id,
        datos.documento_emitido_id,
        db
    )


@router.delete("/{proforma_id}")
async def eliminar_proforma(
    proforma_id: str,
    auth_data:   dict         = Depends(verify_firebase_token),
    db:          AsyncSession = Depends(get_db),
):
    verificar_permiso(auth_data, "emitir")
    from app.services.proforma_service import eliminar_proforma_core
    return await eliminar_proforma_core(auth_data["emisor_id"], proforma_id, db)