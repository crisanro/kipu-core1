# app/services/admin_service.py — OPTIMIZADO con invalidación de cache
import random
from datetime import datetime, timedelta
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from app.schemas.admin import TopupRequest, RequestPin
from app.core.cache import invalidate_emisor
import pytz


async def recargar_creditos_core(data: TopupRequest, db: AsyncSession):
    try:
        if data.tipo == "emision":
            # Compra emisión — regala la mitad en recepción
            bonus_recepcion = data.amount // 2

            res_update = await db.execute(text("""
                UPDATE user_credits uc
                SET balance_emision   = balance_emision   + :amount,
                    balance_recepcion = balance_recepcion + :bonus,
                    last_updated      = NOW()
                FROM emisores e
                WHERE uc.emisor_id = e.id AND e.ruc = :ruc
                RETURNING uc.emisor_id, uc.balance_emision, uc.balance_recepcion
            """), {"amount": data.amount, "bonus": bonus_recepcion, "ruc": data.ruc})

        else:
            # Solo recepción — sin bonus
            bonus_recepcion = 0

            res_update = await db.execute(text("""
                UPDATE user_credits uc
                SET balance_recepcion = balance_recepcion + :amount,
                    last_updated      = NOW()
                FROM emisores e
                WHERE uc.emisor_id = e.id AND e.ruc = :ruc
                RETURNING uc.emisor_id, uc.balance_emision, uc.balance_recepcion
            """), {"amount": data.amount, "ruc": data.ruc})

        row = res_update.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Emisor con RUC {data.ruc} no encontrado.")

        emisor_id = row.emisor_id

        # Registrar transacción principal
        await db.execute(text("""
            INSERT INTO credit_transactions
                (emisor_id, tipo, cantidad, precio_total, metodo_pago, notas)
            VALUES (:eid, 'RECARGA', :amount, 0.00, 'STRIPE', :desc)
        """), {
            "eid":    emisor_id,
            "amount": data.amount,
            "desc":   f"Recarga {data.tipo.upper()} — Ref: {data.reference_id or 'N/A'}"
        })

        # Registrar bonus si aplica
        if bonus_recepcion > 0:
            await db.execute(text("""
                INSERT INTO credit_transactions
                    (emisor_id, tipo, cantidad, precio_total, metodo_pago, notas)
                VALUES (:eid, 'BONO', :bonus, 0.00, 'SISTEMA', 'BONUS RECEPCIÓN POR COMPRA DE EMISIÓN')
            """), {"eid": emisor_id, "bonus": bonus_recepcion})

        await db.commit()
        await invalidate_emisor(emisor_id)

        return {
            "ok":               True,
            "mensaje":          "RECARGA EXITOSA.",
            "tipo":             data.tipo,
            "recargado":        data.amount,
            "bonus_recepcion":  bonus_recepcion,
            "balance_emision":  row.balance_emision,
            "balance_recepcion": row.balance_recepcion
        }

    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


async def solicitar_pin_core(data: RequestPin, db: AsyncSession):
    email_fmt = data.email.lower().strip()

    try:
        res_user = await db.execute(
            text("SELECT emisor_id FROM profiles WHERE email = :email"),
            {"email": email_fmt}
        )
        user_row = res_user.fetchone()
        if not user_row:
            raise HTTPException(status_code=404, detail="Email no registrado.")

        # Anti-spam
        res_spam = await db.execute(text("""
            SELECT created_at FROM auth_challenges
            WHERE email = :email AND created_at > NOW() - INTERVAL '1 minute'
        """), {"email": email_fmt})
        if res_spam.fetchone():
            raise HTTPException(status_code=429, detail="Demasiadas solicitudes. Espera 60s.")

        # Validación teléfono único
        if data.tipo_accion == 'VALIDAR_WS':
            res_phone = await db.execute(text("""
                SELECT email FROM profiles WHERE whatsapp_number = :phone AND email != :email
            """), {"phone": data.whatsapp_number, "email": email_fmt})
            if res_phone.fetchone():
                raise HTTPException(status_code=409, detail="Este número ya está vinculado a otra cuenta.")

        # Limpiar PINs viejos + insertar nuevo en una sola transacción
        await db.execute(
            text("DELETE FROM auth_challenges WHERE email = :email OR whatsapp_number = :phone"),
            {"email": email_fmt, "phone": data.whatsapp_number}
        )

        pin = str(random.randint(100000, 999999))
        tz  = pytz.timezone('America/Guayaquil')
        expires_at = datetime.now(tz) + timedelta(minutes=10)

        await db.execute(text("""
            INSERT INTO auth_challenges (emisor_id, email, whatsapp_number, pin, tipo_accion, expires_at, created_at)
            VALUES (:eid, :email, :phone, :pin, :accion, :exp, NOW())
        """), {
            "eid":   user_row.emisor_id,
            "email": email_fmt,
            "phone": data.whatsapp_number,
            "pin":   pin,
            "accion": data.tipo_accion,
            "exp":   expires_at
        })

        await db.commit()
        return {"ok": True, "pin": pin, "mensaje": "PIN generado e invalidado el anterior."}

    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


async def chequear_estado_ws_core(whatsapp_number: str, db: AsyncSession):
    try:
        # OPTIMIZACIÓN: todo en una sola query con JOIN
        # Incluye verificación del punto de emisión WS configurado en emisores
        query = text("""
            SELECT
                p.email, p.full_name,
                e.id AS emisor_id, e.razon_social, e.ruc,
                e.ws_establecimiento, e.ws_punto_emision,
                c.balance_emision,
                EXISTS (
                    SELECT 1
                    FROM puntos_emision pe
                    JOIN establecimientos est ON pe.establecimiento_id = est.id
                    WHERE est.emisor_id = e.id
                      AND est.codigo   = e.ws_establecimiento
                      AND pe.codigo    = e.ws_punto_emision
                      AND est.is_active = true
                      AND pe.is_active  = true
                ) AS punto_ws_activo
            FROM profiles p
            JOIN emisores e     ON p.emisor_id  = e.id
            JOIN user_credits c ON c.emisor_id  = e.id
            WHERE p.whatsapp_number = :phone
        """)
        res  = await db.execute(query, {"phone": whatsapp_number})
        data = res.mappings().fetchone()

        if not data:
            return {
                "ok": False,
                "codigo_error": "USER_NOT_FOUND",
                "mensaje_cliente": "❌ Tu número no está vinculado a ninguna cuenta de Kipu."
            }

        # Verificar canal WS configurado
        if not data["ws_establecimiento"] or not data["ws_punto_emision"]:
            return {
                "ok": True,
                "codigo_error": "POINT_NOT_CONFIGURED",
                "mensaje_cliente": f"⚠️ Hola {data['razon_social']}, para facturar por WhatsApp debes configurar tu punto de emisión WhatsApp."
            }

        if not data["punto_ws_activo"]:
            return {
                "ok": True,
                "codigo_error": "POINT_NOT_CONFIGURED",
                "mensaje_cliente": f"⚠️ Hola {data['razon_social']}, el punto WhatsApp configurado está inactivo."
            }

        if data["balance_emision"] <= 0:
            return {
                "ok": True,
                "has_credits": False,
                "codigo_error": "USER_NOT_CREDITS",
                "data": {"nombre": data["full_name"], "empresa": data["razon_social"]},
                "mensaje_cliente": f"⚠️ Hola {data['razon_social']}, no tienes créditos disponibles."
            }

        return {
            "ok": True,
            "has_credits": True,
            "data": {
                "emisor_id":      data["emisor_id"],
                "nombre":         data["full_name"],
                "empresa":        data["razon_social"],
                "ruc":            data["ruc"],
                "balance":        data["balance_emision"],
                "establecimiento": data["ws_establecimiento"],
                "punto_emision":  data["ws_punto_emision"]
            },
            "mensaje_cliente": f"✅ Hola {data['full_name']}, estás listo para facturar ({data['ws_establecimiento']}-{data['ws_punto_emision']}). Tienes {data['balance_emision']} créditos."
        }

    except Exception as e:
        import traceback; traceback.print_exc()
        print(f"[Check WS Error] {str(e)}")
        return {"ok": False, "mensaje_cliente": "❌ Error técnico al verificar cuenta."}
