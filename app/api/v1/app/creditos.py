# app/api/v1/app/creditos.py
#
# Endpoints para gestión de créditos API via Stripe.
# Los créditos son exclusivos para consumo de la API REST externa.
# Los suscriptores no necesitan créditos para usar la app web.

import stripe
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional

from app.core.database import get_db
from app.core.security import verify_firebase_token
from app.core.config import settings
from app.core.rate_limit import RateLimit, RateLimitScope
from app.api.v1.app.suscripcion import _obtener_o_crear_customer

stripe.api_key = settings.STRIPE_SECRET_KEY
router = APIRouter()


# =============================================================================
# SCHEMAS
# =============================================================================

class CheckoutCreditosRequest(BaseModel):
    plan_id: int


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get("/balance", summary="Balance actual de créditos API")
async def balance_creditos(
    auth_data: dict = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db),
):
    emisor_id = auth_data.get("emisor_id")
    if not emisor_id:
        raise HTTPException(status_code=400, detail="Emisor no vinculado.")

    res = await db.execute(text("""
        SELECT balance, last_updated FROM user_credits
        WHERE emisor_id = :eid
    """), {"eid": emisor_id})
    credits = res.fetchone()

    return {
        "ok":           True,
        "balance":      credits.balance if credits else 0,
        "last_updated": str(credits.last_updated) if credits else None,
    }


@router.get("/planes", summary="Planes de créditos disponibles")
async def listar_planes(
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(text("""
        SELECT id, nombre, descripcion, cantidad, precio
        FROM planes_creditos
        WHERE activo = true
        ORDER BY cantidad ASC
    """))
    planes = res.fetchall()

    return {
        "ok":   True,
        "data": [
            {
                "id":          p.id,
                "nombre":      p.nombre,
                "descripcion": p.descripcion,
                "cantidad":    p.cantidad,
                "precio":      float(p.precio),
                "precio_por_credito": round(float(p.precio) / p.cantidad, 4),
            }
            for p in planes
        ]
    }


@router.post("/checkout", summary="Crear sesión de pago para créditos API")
async def crear_checkout_creditos(
    data:      CheckoutCreditosRequest,
    auth_data: dict = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db),
    _rl:       None = Depends(RateLimit(RateLimitScope.GENERAL)),
):
    emisor_id = auth_data.get("emisor_id")
    if not emisor_id:
        raise HTTPException(status_code=400, detail="Emisor no vinculado.")

    # Obtener plan
    res_plan = await db.execute(text("""
        SELECT id, nombre, descripcion, cantidad, precio
        FROM planes_creditos
        WHERE id = :pid AND activo = true
    """), {"pid": data.plan_id})
    plan = res_plan.fetchone()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan no encontrado.")

    # Obtener o crear customer
    stripe_customer_id = await _obtener_o_crear_customer(emisor_id, db)

    # Extraer subtotal sin IVA
    subtotal = round(float(plan.precio) / (1 + settings.IVA_RATE), 2)

    try:
        session = stripe.checkout.Session.create(
            customer    = stripe_customer_id,
            mode        = "payment",
            line_items  = [{
                "price_data": {
                    "currency":     "usd",
                    "unit_amount":  int(subtotal * 100),
                    "product_data": {
                        "name":        f"Kipu API — {plan.nombre}",
                        "description": f"{plan.cantidad} créditos · {plan.descripcion or ''}",
                    },
                },
                "quantity":  1,
            }],
            success_url      = f"{settings.FRONTEND_URL}/planes/exitoso?tipo=creditos&cantidad={plan.cantidad}&plan={plan.nombre}",
            cancel_url       = f"{settings.FRONTEND_URL}/planes?pago=cancelado",
            metadata         = {
                "emisor_id": str(emisor_id),
                "tipo":      "CREDITOS",
                "plan_id":   str(plan.id),
                "cantidad":  str(plan.cantidad),
            },
            invoice_creation = {"enabled": False},
        )
    except stripe.StripeError as e:
        raise HTTPException(status_code=500, detail=f"Error Stripe: {str(e)}")

    return {
        "ok":           True,
        "checkout_url": session.url,
        "session_id":   session.id,
    }


@router.get("/historial", summary="Historial de transacciones de créditos")
async def historial_creditos(
    auth_data: dict = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db),
    limit:     int  = 20,
    offset:    int  = 0,
):
    emisor_id = auth_data.get("emisor_id")
    if not emisor_id:
        raise HTTPException(status_code=400, detail="Emisor no vinculado.")

    res = await db.execute(text("""
        SELECT
            id, tipo, cantidad, precio_total,
            metodo_pago, referencia_pago, notas, created_at
        FROM credit_transactions
        WHERE emisor_id = :eid
        ORDER BY created_at DESC
        LIMIT :limit OFFSET :offset
    """), {"eid": emisor_id, "limit": limit, "offset": offset})

    rows = res.fetchall()

    return {
        "ok":   True,
        "data": [
            {
                "id":             str(r.id),
                "tipo":           r.tipo,
                "cantidad":       r.cantidad,
                "precio_total":   float(r.precio_total or 0),
                "metodo_pago":    r.metodo_pago,
                "referencia_pago": r.referencia_pago,
                "notas":          r.notas,
                "created_at":     str(r.created_at),
            }
            for r in rows
        ]
    }