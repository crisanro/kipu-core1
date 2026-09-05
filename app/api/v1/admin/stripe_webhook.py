# app/api/v1/admin/stripe_webhook.py
import stripe
import json
from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import AsyncSessionLocal
from app.core.config import settings
from app.services.notification_service import crear_notificacion
from app.services.documento_service import emitir_documento_core
from app.services.audit_service import audit_log

stripe.api_key = settings.STRIPE_SECRET_KEY
router         = APIRouter()

# auth_data sintético para audit_log desde webhook — no hay usuario autenticado
def _auth_stripe(emisor_id: int) -> dict:
    return {
        "emisor_id":  emisor_id,
        "profile_id": None,
        "emisor_rol": "sistema",
    }

# =============================================================================
# ENTRY POINT
# =============================================================================
@router.post("/webhook", summary="Webhook de Stripe")
async def stripe_webhook(request: Request):
    payload    = await request.body()
    sig_header = request.headers.get("stripe-signature")
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
        event = event.to_dict() if hasattr(event, "to_dict") else dict(event)
    except stripe.errors.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Firma inválida.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    tipo = event["type"]
    obj  = event["data"]["object"]
    print(f"[Stripe] 📩 Evento recibido: {tipo}")

    async with AsyncSessionLocal() as db:
        try:
            if tipo == "checkout.session.completed":
                await _handle_checkout(obj, db)
            elif tipo == "customer.subscription.updated":
                await _handle_subscription_updated(obj, db)
            elif tipo == "customer.subscription.deleted":
                await _handle_subscription_deleted(obj, db)
            elif tipo == "invoice.paid":
                await _handle_invoice_paid(obj, db)
            elif tipo == "invoice.payment_failed":
                await _handle_invoice_payment_failed(obj, db)
            else:
                print(f"[Stripe] ℹ️ Evento ignorado: {tipo}")
        except Exception as e:
            await db.rollback()
            print(f"[Stripe] ❌ Error procesando {tipo}: {e}")
            import traceback; traceback.print_exc()
            return JSONResponse({"ok": False, "error": str(e)})

    return JSONResponse({"ok": True})

# =============================================================================
# HANDLERS
# =============================================================================
async def _handle_checkout(session: dict, db: AsyncSession):
    metadata  = session.get("metadata") or {}
    emisor_id = metadata.get("emisor_id")
    tipo      = metadata.get("tipo")

    if not emisor_id:
        print("[Stripe] ⚠️ Checkout sin emisor_id en metadata.")
        return

    emisor_id = int(emisor_id)
    if tipo == "SUSCRIPCION":
        await _activar_suscripcion(session, emisor_id, metadata, db)
    elif tipo == "CREDITOS":
        await _acreditar_creditos(session, emisor_id, metadata, db)
    else:
        print(f"[Stripe] ⚠️ Checkout con tipo desconocido: {tipo}")

async def _handle_subscription_updated(sub: dict, db: AsyncSession):
    stripe_sub_id = sub.get("id")
    if not stripe_sub_id:
        return

    estado = _mapear_estado_stripe(sub.get("status"))
    await db.execute(text("""
        UPDATE subscriptions SET
            estado               = :estado,
            stripe_price_id      = :price_id,
            current_period_start = :period_start,
            current_period_end   = :period_end,
            cancel_at_period_end = :cancel_at_end,
            updated_at           = NOW()
        WHERE stripe_subscription_id = :sub_id
    """), {
        "estado":        estado,
        "price_id":      sub.get("items", {}).get("data", [{}])[0].get("price", {}).get("id"),
        "period_start":  datetime.fromtimestamp(sub["current_period_start"], tz=timezone.utc) if sub.get("current_period_start") else None,
        "period_end":    datetime.fromtimestamp(sub["current_period_end"], tz=timezone.utc) if sub.get("current_period_end") else None,
        "cancel_at_end": sub.get("cancel_at_period_end", False),
        "sub_id":        stripe_sub_id,
    })

    res = await db.execute(text("""
        SELECT emisor_id, plan, periodo FROM subscriptions
        WHERE stripe_subscription_id = :sub_id
    """), {"sub_id": stripe_sub_id})
    row = res.fetchone()

    if row:
        await audit_log(
            db        = db,
            auth_data = _auth_stripe(row.emisor_id),
            accion    = "UPDATE",
            entidad   = "suscripcion",
            entidad_id = str(row.emisor_id),
            detalle   = {
                "origen":          "stripe_webhook",
                "evento":          "subscription.updated",
                "stripe_sub_id":   stripe_sub_id,
                "estado_nuevo":    estado,
                "plan":            row.plan,
                "periodo":         row.periodo,
                "cancel_at_end":   sub.get("cancel_at_period_end", False),
            },
        )

    await db.commit()

    if row and estado == "CANCELADO":
        await crear_notificacion(
            db        = db,
            emisor_id = row.emisor_id,
            tipo      = "SUSCRIPCION",
            titulo    = "⚠️ Tu suscripción fue cancelada",
            mensaje   = "Tu suscripción a Kipu ha sido cancelada. Puedes reactivarla desde Configuración.",
            referencia = "/configuracion?tab=suscripcion",
        )
    print(f"[Stripe] 🔄 Suscripción actualizada: {stripe_sub_id} → {estado}")

async def _handle_subscription_deleted(sub: dict, db: AsyncSession):
    stripe_sub_id = sub.get("id")
    if not stripe_sub_id:
        return

    res = await db.execute(text("""
        UPDATE subscriptions SET estado = 'VENCIDO', updated_at = NOW()
        WHERE stripe_subscription_id = :sub_id
        RETURNING emisor_id, plan, periodo
    """), {"sub_id": stripe_sub_id})
    row = res.fetchone()

    if row:
        await audit_log(
            db        = db,
            auth_data = _auth_stripe(row.emisor_id),
            accion    = "UPDATE",
            entidad   = "suscripcion",
            entidad_id = str(row.emisor_id),
            detalle   = {
                "origen":        "stripe_webhook",
                "evento":        "subscription.deleted",
                "stripe_sub_id": stripe_sub_id,
                "estado_nuevo":  "VENCIDO",
                "plan":          row.plan,
                "periodo":       row.periodo,
            },
        )

    await db.commit()

    if row:
        await crear_notificacion(
            db        = db,
            emisor_id = row.emisor_id,
            tipo      = "SUSCRIPCION",
            titulo    = "❌ Suscripción vencida",
            mensaje   = "Tu suscripción a Kipu ha vencido. Renuévala para seguir emitiendo comprobantes.",
            referencia = "/configuracion?tab=suscripcion",
        )
        print(f"[Stripe] ❌ Suscripción vencida: {stripe_sub_id} — emisor {row.emisor_id}")

async def _handle_invoice_paid(invoice: dict, db: AsyncSession):
    stripe_sub_id = invoice.get("subscription")
    if not stripe_sub_id:
        return

    try:
        sub = stripe.Subscription.retrieve(stripe_sub_id)
    except Exception as e:
        print(f"[Stripe] ⚠️ No se pudo recuperar suscripción {stripe_sub_id}: {e}")
        return

    res = await db.execute(text("""
        UPDATE subscriptions SET
            estado               = 'ACTIVO',
            current_period_start = :period_start,
            current_period_end   = :period_end,
            updated_at           = NOW()
        WHERE stripe_subscription_id = :sub_id
        RETURNING emisor_id, plan, periodo
    """), {
        "period_start": datetime.fromtimestamp(sub["current_period_start"], tz=timezone.utc),
        "period_end":   datetime.fromtimestamp(sub["current_period_end"], tz=timezone.utc),
        "sub_id":       stripe_sub_id,
    })
    row = res.fetchone()

    if row:
        await audit_log(
            db        = db,
            auth_data = _auth_stripe(row.emisor_id),
            accion    = "UPDATE",
            entidad   = "suscripcion",
            entidad_id = str(row.emisor_id),
            detalle   = {
                "origen":        "stripe_webhook",
                "evento":        "invoice.paid",
                "stripe_sub_id": stripe_sub_id,
                "estado_nuevo":  "ACTIVO",
                "plan":          row.plan,
                "periodo":       row.periodo,
                "monto":         float(invoice.get("amount_paid", 0)) / 100,
            },
        )

    await db.commit()

    if row:
        await _emitir_factura_kipu(invoice, row.emisor_id, db)
        print(f"[Stripe] ✅ Renovación procesada: {stripe_sub_id} — emisor {row.emisor_id}")

async def _handle_invoice_payment_failed(invoice: dict, db: AsyncSession):
    stripe_sub_id = invoice.get("subscription")
    if not stripe_sub_id:
        return

    res = await db.execute(text("""
        SELECT emisor_id, plan, periodo FROM subscriptions
        WHERE stripe_subscription_id = :sub_id
    """), {"sub_id": stripe_sub_id})
    row = res.fetchone()

    if row:
        await audit_log(
            db        = db,
            auth_data = _auth_stripe(row.emisor_id),
            accion    = "UPDATE",
            entidad   = "suscripcion",
            entidad_id = str(row.emisor_id),
            detalle   = {
                "origen":        "stripe_webhook",
                "evento":        "invoice.payment_failed",
                "stripe_sub_id": stripe_sub_id,
                "plan":          row.plan,
                "periodo":       row.periodo,
                "monto":         float(invoice.get("amount_due", 0)) / 100,
            },
        )
        await db.commit()

        await crear_notificacion(
            db        = db,
            emisor_id = row.emisor_id,
            tipo      = "SUSCRIPCION",
            titulo    = "⚠️ Pago fallido",
            mensaje   = "No pudimos procesar el pago de tu suscripción. Verifica tu método de pago en Configuración.",
            referencia = "/configuracion?tab=suscripcion",
        )
        print(f"[Stripe] ⚠️ Pago fallido: {stripe_sub_id} — emisor {row.emisor_id}")

# =============================================================================
# SUB-HANDLERS
# =============================================================================
async def _activar_suscripcion(session: dict, emisor_id: int, metadata: dict, db: AsyncSession):
    stripe_sub_id = session.get("subscription")
    plan          = metadata.get("plan", "PROFESIONAL")
    periodo       = metadata.get("periodo", "MENSUAL")

    if not stripe_sub_id:
        print("[Stripe] ⚠️ Checkout de suscripción sin subscription ID.")
        return

    res_dup = await db.execute(text("""
        SELECT id FROM subscriptions WHERE stripe_subscription_id = :sub_id
    """), {"sub_id": stripe_sub_id})
    if res_dup.fetchone():
        print(f"[Stripe] ⚠️ Suscripción ya procesada: {stripe_sub_id}")
        return

    try:
        sub          = stripe.Subscription.retrieve(stripe_sub_id)
        period_start = datetime.fromtimestamp(sub["current_period_start"], tz=timezone.utc)
        period_end   = datetime.fromtimestamp(sub["current_period_end"], tz=timezone.utc)
        price_id     = sub["items"]["data"][0]["price"]["id"]
    except Exception as e:
        print(f"[Stripe] ⚠️ Error obteniendo suscripción: {e}")
        period_start = period_end = price_id = None

    await db.execute(text("""
        INSERT INTO subscriptions (
            emisor_id, plan, periodo, estado,
            stripe_subscription_id, stripe_price_id,
            current_period_start, current_period_end
        ) VALUES (
            :eid, :plan, :periodo, 'ACTIVO',
            :sub_id, :price_id, :period_start, :period_end
        )
        ON CONFLICT (emisor_id) DO UPDATE SET
            plan                   = EXCLUDED.plan,
            periodo                = EXCLUDED.periodo,
            estado                 = 'ACTIVO',
            stripe_subscription_id = EXCLUDED.stripe_subscription_id,
            stripe_price_id        = EXCLUDED.stripe_price_id,
            current_period_start   = EXCLUDED.current_period_start,
            current_period_end     = EXCLUDED.current_period_end,
            updated_at             = NOW()
    """), {
        "eid": emisor_id, "plan": plan, "periodo": periodo,
        "sub_id": stripe_sub_id, "price_id": price_id,
        "period_start": period_start, "period_end": period_end,
    })

    await audit_log(
        db        = db,
        auth_data = _auth_stripe(emisor_id),
        accion    = "CREATE",
        entidad   = "suscripcion",
        entidad_id = str(emisor_id),
        detalle   = {
            "origen":        "stripe_webhook",
            "evento":        "checkout.completed",
            "stripe_sub_id": stripe_sub_id,
            "plan":          plan,
            "periodo":       periodo,
            "monto":         float(session.get("amount_total", 0)) / 100,
        },
    )
    await db.commit()

    await crear_notificacion(
        db        = db,
        emisor_id = emisor_id,
        tipo      = "SUSCRIPCION",
        titulo    = "✅ Suscripción activada",
        mensaje   = f"Tu suscripción {plan} ({periodo}) está activa. ¡Bienvenido a Kipu!",
        referencia = "/dashboard",
    )

    monto = float(session.get("amount_total", 0)) / 100
    await _emitir_factura_kipu(session, emisor_id, db, monto=monto, descripcion=f"Suscripción Kipu {plan} — {periodo}")
    print(f"[Stripe] ✅ Suscripción activada: {stripe_sub_id} — emisor {emisor_id}")

async def _acreditar_creditos(session: dict, emisor_id: int, metadata: dict, db: AsyncSession):
    cantidad   = int(metadata.get("cantidad", 0))
    plan_id    = metadata.get("plan_id")
    monto      = float(session.get("amount_total", 0)) / 100
    payment_id = session.get("payment_intent") or session.get("id") or ""

    if not cantidad:
        print("[Stripe] ⚠️ Compra de créditos sin cantidad en metadata.")
        return

    res_dup = await db.execute(text("""
        SELECT id FROM credit_transactions
        WHERE metodo_pago = 'STRIPE' AND referencia_pago = :pid
    """), {"pid": payment_id})
    if res_dup.fetchone():
        print(f"[Stripe] ⚠️ Créditos ya procesados: {payment_id}")
        return

    await db.execute(text("""
        UPDATE user_credits SET balance = balance + :qty, last_updated = NOW()
        WHERE emisor_id = :eid
    """), {"qty": cantidad, "eid": emisor_id})

    await db.execute(text("""
        INSERT INTO credit_transactions
            (emisor_id, tipo, cantidad, precio_total, metodo_pago, referencia_pago, notas)
        VALUES (:eid, 'COMPRA', :qty, :monto, 'STRIPE', :pid, :notas)
    """), {
        "eid": emisor_id, "qty": cantidad, "monto": monto,
        "pid": payment_id, "notas": f"plan_id={plan_id}",
    })

    await audit_log(
        db        = db,
        auth_data = _auth_stripe(emisor_id),
        accion    = "CREATE",
        entidad   = "creditos",
        entidad_id = str(emisor_id),
        detalle   = {
            "origen":     "stripe_webhook",
            "evento":     "checkout.completed",
            "payment_id": payment_id,
            "cantidad":   cantidad,
            "monto":      monto,
            "plan_id":    plan_id,
        },
    )
    await db.commit()

    await crear_notificacion(
        db        = db,
        emisor_id = emisor_id,
        tipo      = "CREDITOS",
        titulo    = f"✅ {cantidad} créditos acreditados",
        mensaje   = f"Tu pago de ${monto:.2f} fue procesado. Ya tienes {cantidad} créditos API disponibles.",
        referencia = "/configuracion?tab=creditos",
    )

    await _emitir_factura_kipu(session, emisor_id, db, monto=monto, descripcion=f"Recarga {cantidad} créditos API — Kipu")
    print(f"[Stripe] ✅ {cantidad} créditos acreditados — emisor {emisor_id}")

async def _emitir_factura_kipu(obj: dict, emisor_id: int, db: AsyncSession, monto: float = None, descripcion: str = None):
    if not settings.KIPU_EMISOR_ID or not settings.KIPU_ESTABLECIMIENTO or not settings.KIPU_PUNTO_EMISION:
        print("[Stripe] ⚠️ KIPU_EMISOR_ID no configurado — factura omitida.")
        return
    try:
        res = await db.execute(text("""
            SELECT e.ruc, e.razon_social, p.email
            FROM emisores e
            JOIN emisor_usuarios eu ON eu.emisor_id = e.id
            JOIN profiles p ON p.id = eu.profile_id
            WHERE e.id = :eid
            ORDER BY eu.created_at ASC LIMIT 1
        """), {"eid": emisor_id})
        cliente = res.fetchone()
        if not cliente:
            print("[Stripe] ⚠️ Cliente no encontrado para facturar.")
            return

        if not monto:
            monto = float(obj.get("amount_total", 0)) / 100
        subtotal = round(monto / (1 + settings.IVA_RATE), 2)

        factura_data = {
            "establecimiento": settings.KIPU_ESTABLECIMIENTO,
            "punto_emision":   settings.KIPU_PUNTO_EMISION,
            "cliente": {
                "tipo_id":        "04",
                "nombre":         cliente.razon_social,
                "identificacion": cliente.ruc,
                "email":          cliente.email,
            },
            "items": [{
                "descripcion":     descripcion or "Servicio Kipu",
                "cantidad":        1,
                "precio_unitario": subtotal,
                "tipo_iva":        "15",
            }],
            "pagos": [{"forma_pago": "16", "total": monto}],
            "origen": "web",
        }
        result = await emitir_documento_core(
            tipo_doc  = "FAC",
            data      = factura_data,
            emisor_id = settings.KIPU_EMISOR_ID,
            db        = db,
        )
        print(f"[Stripe] 🧾 Factura emitida: {result.get('claveAcceso', '?')}")
    except Exception as e:
        print(f"[Stripe] ⚠️ Error emitiendo factura: {e}")

# =============================================================================
# HELPERS
# =============================================================================
def _mapear_estado_stripe(status: str) -> str:
    return {
        "active":   "ACTIVO",
        "trialing": "TRIAL",
        "past_due": "ACTIVO",
        "canceled": "CANCELADO",
        "unpaid":   "VENCIDO",
        "paused":   "CANCELADO",
    }.get(status, "VENCIDO")