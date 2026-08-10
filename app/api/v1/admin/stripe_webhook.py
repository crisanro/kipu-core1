# app/api/v1/admin/stripe_webhook.py
#
# Webhook de Stripe — recibe eventos de pago y acredita créditos.
# Flujo: checkout.session.completed → acreditar → facturar → notificar

import stripe
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import AsyncSessionLocal
from app.core.config import settings
from app.services.notification_service import crear_notificacion
from app.utils.factura_service import emitir_factura_core

stripe.api_key = settings.STRIPE_SECRET_KEY
router         = APIRouter()

# ── POST /webhook ──────────────────────────────────────────────────────────────
@router.post("/webhook", summary="Webhook de Stripe")
async def stripe_webhook(request: Request):
    payload    = await request.body()
    sig_header = request.headers.get("stripe-signature")

    # ── Verificar firma ────────────────────────────────────────────────────────
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
        # Convertir evento a dict para un acceso seguro a claves mediante .get()
        event = event.to_dict() if hasattr(event, "to_dict") else dict(event)
    except stripe.errors.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Firma inválida.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # ── Solo procesar pagos completados ───────────────────────────────────────
    if event["type"] != "checkout.session.completed":
        return JSONResponse({"ok": True, "mensaje": "Evento ignorado."})

    session  = event["data"]["object"]
    metadata = session.get("metadata") or {}

    emisor_id = metadata.get("emisor_id")
    plan_id   = metadata.get("plan_id")
    cantidad  = metadata.get("cantidad")

    if not emisor_id or not cantidad:
        print(f"[Stripe] ⚠️ Metadata incompleto: {metadata}")
        return JSONResponse({"ok": True, "mensaje": "Metadata incompleto."})

    emisor_id  = int(emisor_id)
    cantidad   = int(cantidad)
    monto      = float(session.get("amount_total") or 0) / 100  # centavos → USD
    payment_id = session.get("payment_intent") or session.get("id") or ""

    print(f"[Stripe] 💳 Pago recibido — emisor {emisor_id}, {cantidad} créditos, ${monto}")

    async with AsyncSessionLocal() as db:
        try:
            # ── 1. Verificar idempotencia ──────────────────────────────────────
            res_dup = await db.execute(text("""
                SELECT id FROM credit_transactions
                WHERE metodo_pago = 'STRIPE' AND notas LIKE :pid
            """), {"pid": f"%{payment_id}%"})
            if res_dup.fetchone():
                print(f"[Stripe] ⚠️ Pago ya procesado: {payment_id}")
                return JSONResponse({"ok": True, "mensaje": "Ya procesado."})

            # ── 2. Acreditar créditos ──────────────────────────────────────────
            await db.execute(text("""
                UPDATE user_credits
                SET balance_emision = balance_emision + :qty,
                    last_updated    = NOW()
                WHERE emisor_id = :eid
            """), {"qty": cantidad, "eid": emisor_id})

            await db.execute(text("""
                INSERT INTO credit_transactions
                    (emisor_id, tipo, cantidad, precio_total, metodo_pago, notas)
                VALUES (:eid, 'RECARGA', :qty, :monto, 'STRIPE', :notas)
            """), {
                "eid":   emisor_id,
                "qty":   cantidad,
                "monto": monto,
                "notas": f"Stripe payment_intent={payment_id} plan_id={plan_id}",
            })
            await db.commit()
            print(f"[Stripe] ✅ {cantidad} créditos acreditados al emisor {emisor_id}")

            # ── 3. Obtener datos del emisor para facturar ──────────────────────
            res_emisor = await db.execute(text("""
                SELECT
                    e.ruc, e.razon_social, e.nombre_comercial,
                    e.ws_establecimiento, e.ws_punto_emision,
                    p.email
                FROM emisores e
                JOIN emisor_usuarios eu ON eu.emisor_id = e.id
                JOIN profiles p         ON p.id = eu.profile_id
                WHERE e.id = :eid
                ORDER BY eu.created_at ASC
                LIMIT 1
            """), {"eid": emisor_id})
            emisor = res_emisor.fetchone()

            # ── 4. Emitir factura electrónica ──────────────────────────────────
            if emisor and emisor.ws_establecimiento and emisor.ws_punto_emision:
                try:
                    # Precio sin IVA
                    subtotal = round(monto / (1 + settings.IVA_RATE), 2)

                    factura_data = {
                        "establecimiento": emisor.ws_establecimiento,
                        "punto_emision":   emisor.ws_punto_emision,
                        "cliente": {
                            "tipo_id":       "04",
                            "nombre":        emisor.razon_social,
                            "identificacion": emisor.ruc,
                            "email":         emisor.email,
                        },
                        "items": [{
                            "descripcion":    f"Recarga de {cantidad} créditos de emisión — Kipu",
                            "cantidad":       1,
                            "precio_unitario": subtotal,
                            "tipo_iva":       "15",
                        }],
                        "pagos": [{
                            "forma_pago": "16",  # 16 = tarjeta de crédito
                            "total":      monto,
                        }],
                        "campos_adicionales": [
                            {"nombre": "Plan",      "valor": f"{cantidad} créditos"},
                            {"nombre": "Referencia", "valor": payment_id[:20]},
                        ],
                    }

                    result = await emitir_factura_core(
                        factura_data = factura_data,
                        emisor_id    = emisor_id,
                        db           = db,
                        api_key_id   = None,
                        unlimited    = True,  # ← no consumir créditos por esta factura
                    )
                    print(f"[Stripe] 🧾 Factura emitida: {result.get('secuencial', '?')}")

                except Exception as e:
                    # No crítico — los créditos ya fueron acreditados
                    print(f"[Stripe] ⚠️ Error emitiendo factura: {e}")
            else:
                print(f"[Stripe] ⚠️ Emisor sin estructura configurada — factura omitida")

            # ── 5. Notificar al usuario ────────────────────────────────────────
            await crear_notificacion(
                db        = db,
                emisor_id = emisor_id,
                tipo      = "CREDITOS",
                titulo    = f"✅ {cantidad} créditos acreditados",
                mensaje   = f"Tu pago de ${monto:.2f} fue procesado. Ya tienes {cantidad} créditos nuevos disponibles.",
                referencia = "/creditos",
            )

        except Exception as e:
            await db.rollback()
            print(f"[Stripe] ❌ Error procesando webhook: {e}")
            import traceback; traceback.print_exc()
            # Retornar 200 para que Stripe no reintente
            return JSONResponse({"ok": False, "error": str(e)})

    return JSONResponse({"ok": True, "mensaje": "Pago procesado correctamente."})