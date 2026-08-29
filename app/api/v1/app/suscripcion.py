# app/api/v1/app/suscripcion.py
#
# Endpoints para gestión de suscripción via Stripe.
# Separado de creditos.py — maneja planes mensuales/anuales.

import stripe
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone

from app.core.database import get_db
from app.core.security import verify_firebase_token
from app.core.config import settings
from app.core.rate_limit import RateLimit, RateLimitScope

stripe.api_key = settings.STRIPE_SECRET_KEY
router = APIRouter()

# Precios de Stripe por plan y período
# Estos IDs vienen de tu dashboard de Stripe
STRIPE_PRICES = {
    "NATURAL": {
        "MENSUAL": settings.STRIPE_PRICE_NATURAL_MENSUAL,
        "ANUAL":   settings.STRIPE_PRICE_NATURAL_ANUAL,
    },
    "JURIDICO": {
        "MENSUAL": settings.STRIPE_PRICE_JURIDICO_MENSUAL,
        "ANUAL":   settings.STRIPE_PRICE_JURIDICO_ANUAL,
    },
}


# =============================================================================
# SCHEMAS
# =============================================================================

class CheckoutSuscripcionRequest(BaseModel):
    plan:    str  # NATURAL | JURIDICO
    periodo: str  # MENSUAL | ANUAL


class CambiarPlanRequest(BaseModel):
    plan:    str
    periodo: str


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get("/estado", summary="Estado actual de la suscripción")
async def estado_suscripcion(
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db),
):
    emisor_id = auth_data.get("emisor_id")
    if not emisor_id:
        raise HTTPException(status_code=400, detail="Emisor no vinculado.")

    res = await db.execute(text("""
        SELECT
            s.plan, s.periodo, s.estado,
            s.current_period_start, s.current_period_end,
            s.trial_end, s.cancel_at_period_end,
            s.stripe_subscription_id
        FROM subscriptions s
        WHERE s.emisor_id = :eid
    """), {"eid": emisor_id})

    sub = res.fetchone()

    if not sub:
        return {
            "ok":    True,
            "tiene_suscripcion": False,
            "data":  None,
        }

    ahora = datetime.now(timezone.utc)
    activa = sub.estado in ("ACTIVO", "TRIAL")

    return {
        "ok":               True,
        "tiene_suscripcion": activa,
        "data": {
            "plan":               sub.plan,
            "periodo":            sub.periodo,
            "estado":             sub.estado,
            "activa":             activa,
            "period_start":       str(sub.current_period_start) if sub.current_period_start else None,
            "period_end":         str(sub.current_period_end) if sub.current_period_end else None,
            "trial_end":          str(sub.trial_end) if sub.trial_end else None,
            "cancel_at_period_end": sub.cancel_at_period_end,
            "dias_restantes":     (sub.current_period_end - ahora).days if sub.current_period_end else None,
        }
    }


@router.post("/checkout", summary="Crear sesión de checkout para suscripción")
async def crear_checkout_suscripcion(
    data:      CheckoutSuscripcionRequest,
    auth_data: dict = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db),
    _rl:       None = Depends(RateLimit(RateLimitScope.GENERAL)),
):
    emisor_id = auth_data.get("emisor_id")
    if not emisor_id:
        raise HTTPException(status_code=400, detail="Emisor no vinculado.")

    plan    = data.plan.upper()
    periodo = data.periodo.upper()

    if plan not in ("NATURAL", "JURIDICO"):
        raise HTTPException(status_code=400, detail="Plan inválido. Usa NATURAL o JURIDICO.")
    if periodo not in ("MENSUAL", "ANUAL"):
        raise HTTPException(status_code=400, detail="Período inválido. Usa MENSUAL o ANUAL.")

    price_id = STRIPE_PRICES.get(plan, {}).get(periodo)
    if not price_id:
        raise HTTPException(status_code=400, detail=f"Precio no configurado para {plan} {periodo}.")

    # Verificar que no tenga ya una suscripción activa
    res_sub = await db.execute(text("""
        SELECT estado, stripe_subscription_id FROM subscriptions
        WHERE emisor_id = :eid
    """), {"eid": emisor_id})
    sub_actual = res_sub.fetchone()

    if sub_actual and sub_actual.estado in ("ACTIVO", "TRIAL"):
        raise HTTPException(
            status_code=400,
            detail="Ya tienes una suscripción activa. Usa el portal para cambiar de plan."
        )

    # Obtener o crear customer en Stripe
    stripe_customer_id = await _obtener_o_crear_customer(emisor_id, db)

    try:
        session = stripe.checkout.Session.create(
            customer              = stripe_customer_id,
            mode                  = "subscription",
            line_items            = [{"price": price_id, "quantity": 1}],
            success_url           = f"{settings.FRONTEND_URL}/planes/exitoso?tipo=suscripcion&plan={plan}&periodo={periodo}",
            cancel_url            = f"{settings.FRONTEND_URL}/planes?pago=cancelado",
            allow_promotion_codes = True,
            metadata              = {
                "emisor_id": str(emisor_id),
                "tipo":      "SUSCRIPCION",
                "plan":      plan,
                "periodo":   periodo,
            },
            subscription_data = {
                "metadata": {
                    "emisor_id": str(emisor_id),
                    "plan":      plan,
                    "periodo":   periodo,
                }
            },
            invoice_creation = None,  # Kipu emite su propia factura
        )
    except stripe.StripeError as e:
        raise HTTPException(status_code=500, detail=f"Error Stripe: {str(e)}")

    return {
        "ok":           True,
        "checkout_url": session.url,
        "session_id":   session.id,
    }


@router.post("/portal", summary="Abrir portal de cliente Stripe")
async def portal_cliente(
    auth_data: dict = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db),
):
    """
    Genera un link al Customer Portal de Stripe donde el usuario puede:
    - Cambiar método de pago
    - Cancelar suscripción
    - Ver historial de facturas Stripe
    """
    emisor_id = auth_data.get("emisor_id")
    if not emisor_id:
        raise HTTPException(status_code=400, detail="Emisor no vinculado.")

    res = await db.execute(text("""
        SELECT stripe_customer_id FROM emisores WHERE id = :eid
    """), {"eid": emisor_id})
    emisor = res.fetchone()

    if not emisor or not emisor.stripe_customer_id:
        raise HTTPException(status_code=404, detail="No tienes una cuenta de facturación configurada.")

    try:
        session = stripe.billing_portal.Session.create(
            customer   = emisor.stripe_customer_id,
            return_url = f"{settings.FRONTEND_URL}/configuracion?tab=suscripcion",
        )
    except stripe.StripeError as e:
        raise HTTPException(status_code=500, detail=f"Error Stripe: {str(e)}")

    return {
        "ok":         True,
        "portal_url": session.url,
    }


@router.post("/cancelar", summary="Cancelar suscripción al fin del período")
async def cancelar_suscripcion(
    auth_data: dict = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db),
):
    """
    Marca la suscripción para cancelar al fin del período actual.
    El acceso se mantiene hasta la fecha de vencimiento.
    """
    emisor_id = auth_data.get("emisor_id")
    if not emisor_id:
        raise HTTPException(status_code=400, detail="Emisor no vinculado.")

    res = await db.execute(text("""
        SELECT stripe_subscription_id, estado FROM subscriptions
        WHERE emisor_id = :eid
    """), {"eid": emisor_id})
    sub = res.fetchone()

    if not sub or not sub.stripe_subscription_id:
        raise HTTPException(status_code=404, detail="No tienes una suscripción activa.")

    if sub.estado not in ("ACTIVO", "TRIAL"):
        raise HTTPException(status_code=400, detail="Tu suscripción no está activa.")

    try:
        stripe.Subscription.modify(
            sub.stripe_subscription_id,
            cancel_at_period_end=True,
        )
    except stripe.StripeError as e:
        raise HTTPException(status_code=500, detail=f"Error Stripe: {str(e)}")

    await db.execute(text("""
        UPDATE subscriptions
        SET cancel_at_period_end = true, updated_at = NOW()
        WHERE emisor_id = :eid
    """), {"eid": emisor_id})
    await db.commit()

    return {
        "ok":      True,
        "mensaje": "Tu suscripción se cancelará al finalizar el período actual. Seguirás teniendo acceso hasta entonces.",
    }


@router.post("/reactivar", summary="Reactivar suscripción cancelada")
async def reactivar_suscripcion(
    auth_data: dict = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db),
):
    """Reactiva una suscripción marcada para cancelar."""
    emisor_id = auth_data.get("emisor_id")
    if not emisor_id:
        raise HTTPException(status_code=400, detail="Emisor no vinculado.")

    res = await db.execute(text("""
        SELECT stripe_subscription_id, cancel_at_period_end FROM subscriptions
        WHERE emisor_id = :eid AND estado = 'ACTIVO'
    """), {"eid": emisor_id})
    sub = res.fetchone()

    if not sub:
        raise HTTPException(status_code=404, detail="No tienes una suscripción activa.")

    if not sub.cancel_at_period_end:
        raise HTTPException(status_code=400, detail="Tu suscripción no está programada para cancelarse.")

    try:
        stripe.Subscription.modify(
            sub.stripe_subscription_id,
            cancel_at_period_end=False,
        )
    except stripe.StripeError as e:
        raise HTTPException(status_code=500, detail=f"Error Stripe: {str(e)}")

    await db.execute(text("""
        UPDATE subscriptions
        SET cancel_at_period_end = false, updated_at = NOW()
        WHERE emisor_id = :eid
    """), {"eid": emisor_id})
    await db.commit()

    return {
        "ok":      True,
        "mensaje": "Tu suscripción ha sido reactivada correctamente.",
    }


# =============================================================================
# HELPER
# =============================================================================

async def _obtener_o_crear_customer(emisor_id: int, db: AsyncSession) -> str:
    """Obtiene el stripe_customer_id del emisor o lo crea si no existe."""
    res = await db.execute(text("""
        SELECT e.stripe_customer_id, e.ruc, e.razon_social, p.email
        FROM emisores e
        JOIN emisor_usuarios eu ON eu.emisor_id = e.id
        JOIN profiles p ON p.id = eu.profile_id
        WHERE e.id = :eid
        ORDER BY eu.created_at ASC
        LIMIT 1
    """), {"eid": emisor_id})
    emisor = res.fetchone()

    if not emisor:
        raise HTTPException(status_code=404, detail="Emisor no encontrado.")

    if emisor.stripe_customer_id:
        return emisor.stripe_customer_id

    # Crear customer en Stripe
    customer = stripe.Customer.create(
        email    = emisor.email,
        name     = emisor.razon_social,
        metadata = {
            "emisor_id": str(emisor_id),
            "ruc":       emisor.ruc,
        }
    )

    await db.execute(text("""
        UPDATE emisores SET stripe_customer_id = :cid WHERE id = :eid
    """), {"cid": customer.id, "eid": emisor_id})
    await db.commit()

    return customer.id