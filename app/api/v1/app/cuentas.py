# app/api/v1/app/cuentas.py
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import verify_firebase_token
from app.core.permisos import verificar_permiso
from pydantic import BaseModel, Field
from typing import Optional
from datetime import date

from app.services.cuentas_service import anular_cuenta_core
from app.services.cuentas_service import crear_cuenta_core
from app.services.cuentas_service import listar_cuentas_core
from app.services.cuentas_service import listar_cuentas_cliente_core
from app.services.cuentas_service import detalle_cuenta_core
from app.services.cuentas_service import registrar_abono_core

router = APIRouter()

# ── Schemas inline (simples, no ameritan archivo separado) ─────────────────────
class CuentaCreate(BaseModel):
    cliente_id:            str
    tipo:                  str                    # COBRAR | PAGAR
    concepto:              str
    monto_total:           float
    fecha_emision:         Optional[date] = None
    fecha_vencimiento:     Optional[date] = None
    documento_emitido_id:  Optional[str]  = None
    documento_recibido_id: Optional[str]  = None
    notas:                 Optional[str]  = None

class AbonoCreate(BaseModel):
    monto:      float
    fecha:      Optional[date] = None
    forma_pago: Optional[str]  = None   # EFECTIVO | TRANSFERENCIA | CHEQUE | TARJETA | OTRO
    notas:      Optional[str]  = None


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("")
async def crear_cuenta(
    datos:     CuentaCreate,
    auth_data: dict         = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db),
):
    verificar_permiso(auth_data, "clientes")
    # ── Validar suscripción ───────────────────────────────────────────────────
    res_sub = await db.execute(text("""
        SELECT estado FROM subscriptions WHERE emisor_id = :eid
    """), {"eid": auth_data["emisor_id"]})
    sub = res_sub.fetchone()
    if not sub or sub.estado not in ("ACTIVO", "TRIAL"):
        raise HTTPException(status_code=402, detail="LAS CUENTAS REQUIEREN UNA SUSCRIPCIÓN ACTIVA.")
    return await crear_cuenta_core(auth_data["emisor_id"], datos.model_dump(), db)


@router.get("")
async def listar_cuentas(
    tipo:      Optional[str] = Query(None),
    estado:    Optional[str] = Query(None),
    auth_data: dict          = Depends(verify_firebase_token),
    db:        AsyncSession  = Depends(get_db),
):
    verificar_permiso(auth_data, "clientes")
    return await listar_cuentas_core(auth_data["emisor_id"], tipo, estado, db)


@router.get("/cliente/{cliente_id}")
async def cuentas_por_cliente(
    cliente_id: str,
    auth_data:  dict         = Depends(verify_firebase_token),
    db:         AsyncSession = Depends(get_db),
):
    verificar_permiso(auth_data, "clientes")
    return await listar_cuentas_cliente_core(auth_data["emisor_id"], cliente_id, db)


@router.get("/{cuenta_id}")
async def detalle_cuenta(
    cuenta_id: str,
    auth_data: dict         = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db),
):
    verificar_permiso(auth_data, "clientes")
    return await detalle_cuenta_core(auth_data["emisor_id"], cuenta_id, db)


@router.post("/{cuenta_id}/abonos")
async def registrar_abono(
    cuenta_id: str,
    datos:     AbonoCreate,
    auth_data: dict         = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db),
):
    verificar_permiso(auth_data, "clientes")
    # ── Validar suscripción ───────────────────────────────────────────────────
    res_sub = await db.execute(text("""
        SELECT estado FROM subscriptions WHERE emisor_id = :eid
    """), {"eid": auth_data["emisor_id"]})
    sub = res_sub.fetchone()
    if not sub or sub.estado not in ("ACTIVO", "TRIAL"):
        raise HTTPException(status_code=402, detail="LAS CUENTAS REQUIEREN UNA SUSCRIPCIÓN ACTIVA.")
    return await registrar_abono_core(auth_data["emisor_id"], cuenta_id, datos.model_dump(), db)


@router.patch("/{cuenta_id}/anular")
async def anular_cuenta(
    cuenta_id: str,
    auth_data: dict         = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db),
):
    verificar_permiso(auth_data, "clientes")
    # ── Validar suscripción ───────────────────────────────────────────────────
    res_sub = await db.execute(text("""
        SELECT estado FROM subscriptions WHERE emisor_id = :eid
    """), {"eid": auth_data["emisor_id"]})
    sub = res_sub.fetchone()
    if not sub or sub.estado not in ("ACTIVO", "TRIAL"):
        raise HTTPException(status_code=402, detail="LAS CUENTAS REQUIEREN UNA SUSCRIPCIÓN ACTIVA.")
    return await anular_cuenta_core(auth_data["emisor_id"], cuenta_id, db)