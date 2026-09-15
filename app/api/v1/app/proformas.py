# app/api/v1/app/proformas.py
from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.permisos import verificar_permiso
from app.core.security import verify_firebase_token
from app.services.audit_service import audit_log
from app.services.proforma_service import (
    crear_proforma_core,
    detalle_proforma_core,
    eliminar_proforma_core,
    facturar_proforma_core,
    listar_proformas_core,
)

router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────────────────────
class ItemProforma(BaseModel):
    descripcion: str
    cantidad: float = 1
    precio_unitario: float
    tipo_iva: int = 15  # 0 | 8 | 15


class ProformaCreate(BaseModel):
    cliente_id: Optional[str] = None
    fecha_emision: Optional[date] = None
    fecha_validez: Optional[date] = None
    items: List[ItemProforma]
    notas: Optional[str] = None


class FacturarProforma(BaseModel):
    documento_emitido_id: str


# ── Endpoints ──────────────────────────────────────────────────────────────────


@router.post("")
async def crear_proforma(
    datos: ProformaCreate,
    request: Request,
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db),
):
    verificar_permiso(auth_data, "emitir")

    # ── Validar suscripción activa ────────────────────────────────────────────
    res_sub = await db.execute(
        text("""
        SELECT s.estado FROM subscriptions s
        WHERE s.emisor_id = :eid AND s.estado IN ('ACTIVO', 'TRIAL')
        LIMIT 1
    """),
        {"eid": auth_data["emisor_id"]},
    )
    if not res_sub.fetchone():
        raise HTTPException(
            status_code=402,
            detail="LAS PROFORMAS REQUIEREN UNA SUSCRIPCIÓN ACTIVA.",
        )

    result = await crear_proforma_core(
        auth_data["emisor_id"], datos.model_dump(), db
    )

    await audit_log(
        db,
        auth_data,
        "CREATE",
        "proforma",
        result.get("id") if isinstance(result, dict) else None,
        {"items": len(datos.items), "notas": datos.notas},
        request,
    )
    await db.commit()

    return result


@router.get("")
async def listar_proformas(
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db),
):
    verificar_permiso(auth_data, "emitir")
    return await listar_proformas_core(auth_data["emisor_id"], db)


@router.get("/{proforma_id}")
async def detalle_proforma(
    proforma_id: str,
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db),
):
    verificar_permiso(auth_data, "emitir")
    return await detalle_proforma_core(auth_data["emisor_id"], proforma_id, db)


@router.patch("/{proforma_id}/facturar")
async def facturar_proforma(
    proforma_id: str,
    datos: FacturarProforma,
    request: Request,
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db),
):
    verificar_permiso(auth_data, "emitir")
    result = await facturar_proforma_core(
        auth_data["emisor_id"], proforma_id, datos.documento_emitido_id, db
    )

    await audit_log(
        db,
        auth_data,
        "UPDATE",
        "proforma",
        proforma_id,
        {
            "accion": "facturar",
            "documento_emitido_id": datos.documento_emitido_id,
        },
        request,
    )
    await db.commit()

    return result


@router.delete("/{proforma_id}")
async def eliminar_proforma(
    proforma_id: str,
    request: Request,
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db),
):
    verificar_permiso(auth_data, "emitir")
    result = await eliminar_proforma_core(
        auth_data["emisor_id"], proforma_id, db
    )

    await audit_log(
        db, auth_data, "DELETE", "proforma", proforma_id, None, request
    )
    await db.commit()

    return result