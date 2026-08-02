# app/api/v1/app/creditos.py
#
# Endpoints para recarga de créditos via Stripe.
# El webhook de Stripe va directo a n8n — n8n se encarga de:
#   1. Verificar el pago
#   2. Llamar a /admin/topup para acreditar créditos
#   3. Emitir factura electrónica
#   4. Enviar email de confirmación

import stripe
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.core.database import get_db
from app.core.security import verify_firebase_token
from app.core.config import settings
from app.core.rate_limit import RateLimit, RateLimitScope

stripe.api_key = settings.STRIPE_SECRET_KEY

router = APIRouter()


class CheckoutRequest(BaseModel):
    plan_id: int


@router.post("/stripe/checkout", summary="Crear sesión de pago Stripe")
async def crear_checkout(
    data: CheckoutRequest,
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db),
    _rl: None = Depends(RateLimit(RateLimitScope.GENERAL)),
):
    emisor_id = auth_data.get("emisor_id")
    if not emisor_id:
        raise HTTPException(status_code=400, detail="El usuario no tiene una empresa vinculada.")

    # ── Obtener el plan ────────────────────────────────────────────────────
    res_plan = await db.execute(text("""
        SELECT id, nombre, descripcion, cantidad, precio
        FROM planes_creditos
        WHERE id = :pid AND activo = true AND tipo = 'emision'
    """), {"pid": data.plan_id})
    plan = res_plan.fetchone()

    if not plan:
        raise HTTPException(status_code=404, detail="Plan no encontrado.")

    # ── Obtener o crear customer en Stripe ─────────────────────────────────
    res_emisor = await db.execute(text("""
        SELECT e.ruc, e.razon_social, e.stripe_customer_id, p.email
        FROM emisores e
        JOIN emisor_usuarios eu ON eu.emisor_id = e.id
        JOIN profiles p ON p.id = eu.profile_id
        WHERE e.id = :eid
        LIMIT 1
    """), {"eid": emisor_id})
    emisor = res_emisor.fetchone()

    if not emisor:
        raise HTTPException(status_code=404, detail="Emisor no encontrado.")

    # Si ya tiene customer_id en Stripe lo usamos, si no lo creamos
    stripe_customer_id = emisor.stripe_customer_id

    if not stripe_customer_id:
        customer = stripe.Customer.create(
            email=emisor.email,
            name=emisor.razon_social,
            metadata={
                "emisor_id": str(emisor_id),
                "ruc":       emisor.ruc,
            }
        )
        stripe_customer_id = customer.id

        # Guardar en DB
        await db.execute(text("""
            UPDATE emisores SET stripe_customer_id = :cid WHERE id = :eid
        """), {"cid": stripe_customer_id, "eid": emisor_id})
        await db.commit()

    # ── Crear sesión de checkout ───────────────────────────────────────────
    try:
        session = stripe.checkout.Session.create(
            customer=stripe_customer_id,
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency":     "usd",
                    "unit_amount": int(float(plan.precio) * (1 + settings.IVA_RATE)), # Stripe usa centavos
                    "product_data": {
                        "name":        f"Kipu — {plan.nombre}",
                        "description": f"{plan.cantidad} créditos de emisión · {plan.descripcion or ''}",
                    },
                },
                "quantity": 1,
            }],
            mode="payment",
            success_url=f"{settings.FRONTEND_URL}/configuracion?tab=creditos&pago=exitoso",
            cancel_url=f"{settings.FRONTEND_URL}/configuracion?tab=creditos&pago=cancelado",
            metadata={
                "emisor_id": str(emisor_id),
                "plan_id":   str(plan.id),
                "cantidad":  str(plan.cantidad),
                "ruc":       emisor.ruc,
            },
            invoice_creation={"enabled": False},  # La factura la emite Kipu, no Stripe
        )
    except stripe.StripeError as e:
        raise HTTPException(status_code=500, detail=f"Error al crear sesión de pago: {str(e)}")

    return {
        "ok":          True,
        "checkout_url": session.url,
        "session_id":  session.id,
    }