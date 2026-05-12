import random
from datetime import datetime, timedelta
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from app.schemas.admin import TopupRequest, RequestPin
import pytz

async def recargar_creditos_core(data: TopupRequest, db: AsyncSession):
    try:
        # 1. Obtener ID del emisor por RUC
        query_emisor = text("SELECT id FROM emisores WHERE ruc = :ruc")
        res_emisor = await db.execute(query_emisor, {"ruc": data.ruc})
        emisor_row = res_emisor.fetchone()

        if not emisor_row:
            raise HTTPException(status_code=404, detail=f"Emisor con RUC {data.ruc} no encontrado")
        
        emisor_id = emisor_row.id

        # 2. Incrementar balance
        # AJUSTE: Cambiamos 'balance' por 'balance_emision' (que es el campo real ahora)
        query_update = text("""
            UPDATE user_credits 
            SET balance_emision = balance_emision + :amount, last_updated = NOW() 
            WHERE emisor_id = :eid 
            RETURNING balance_emision
        """)
        res_update = await db.execute(query_update, {"amount": data.amount, "eid": emisor_id})
        nuevo_balance = res_update.scalar()

        # 3. Registrar Log
        query_log = text("""
            INSERT INTO transaction_logs (target_emisor_id, amount, action_type, description, created_at)
            VALUES (:eid, :amount, 'STRIPE_RECHARGE', :desc, NOW())
        """)
        desc = f"Recarga n8n - Ref: {data.reference_id or 'N/A'}"
        await db.execute(query_log, {"eid": emisor_id, "amount": data.amount, "desc": desc})

        await db.commit()
        return {"ok": True, "mensaje": "Recarga exitosa", "nuevo_balance": nuevo_balance}

    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


async def solicitar_pin_core(data: RequestPin, db: AsyncSession):
    email_fmt = data.email.lower().strip()
    
    try:
        # 1. Verificar existencia
        res_user = await db.execute(text("SELECT emisor_id FROM profiles WHERE email = :email"), {"email": email_fmt})
        user_row = res_user.fetchone()
        if not user_row:
            raise HTTPException(status_code=404, detail="Email no registrado.")
        
        # 2. Anti-Spam (1 minuto)
        res_spam = await db.execute(text("""
            SELECT created_at FROM auth_challenges 
            WHERE email = :email AND created_at > NOW() - INTERVAL '1 minute'
        """), {"email": email_fmt})
        
        if res_spam.fetchone():
            raise HTTPException(status_code=429, detail="Demasiadas solicitudes. Espera 60s.")

        # 3. Validación Teléfono Único
        if data.tipo_accion == 'VALIDAR_WS':
            res_phone = await db.execute(text("""
                SELECT email FROM profiles WHERE whatsapp_number = :phone AND email != :email
            """), {"phone": data.whatsapp_number, "email": email_fmt})
            
            if res_phone.fetchone():
                raise HTTPException(status_code=409, detail="Este número ya está vinculado a otra cuenta.")

        # 4. Eliminar pines viejos
        await db.execute(text("DELETE FROM auth_challenges WHERE email = :email OR whatsapp_number = :phone"), 
                         {"email": email_fmt, "phone": data.whatsapp_number})

        # 5. Generar e Insertar
        pin = str(random.randint(100000, 999999))
        
        # AJUSTE: Para evitar líos de zona horaria entre Python y Postgres, 
        # a veces es mejor dejar que la DB maneje el tiempo o asegurar UTC.
        tz = pytz.timezone('America/Guayaquil')
        expires_at = datetime.now(tz) + timedelta(minutes=10)

        await db.execute(text("""
            INSERT INTO auth_challenges (emisor_id, email, whatsapp_number, pin, tipo_accion, expires_at, created_at)
            VALUES (:eid, :email, :phone, :pin, :accion, :exp, NOW())
        """), {"eid": user_row.emisor_id, "email": email_fmt, "phone": data.whatsapp_number, 
               "pin": pin, "accion": data.tipo_accion, "exp": expires_at})

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
        query = text("""
            SELECT p.email, p.full_name, e.id as emisor_id, e.razon_social, e.ruc, c.balance_emision
            FROM profiles p
            JOIN emisores e ON p.emisor_id = e.id
            JOIN user_credits c ON e.id = c.emisor_id
            WHERE p.whatsapp_number = :phone
        """)
        res = await db.execute(query, {"phone": whatsapp_number})
        
        # AJUSTE: Usamos .mappings() para evitar errores de acceso por atributo en algunas versiones de SQLAlchemy
        data = res.mappings().fetchone()

        if not data:
            return {
                "ok": False, "codigo_error": "USER_NOT_FOUND",
                "mensaje_cliente": "❌ Tu número no está vinculado a ninguna cuenta de Kipu."
            }

        # Check Punto de Emisión 333
        query_pto = text("""
            SELECT p.id 
            FROM puntos_emision p
            JOIN establecimientos e ON p.establecimiento_id = e.id
            WHERE e.emisor_id = :eid AND e.codigo = '001' AND p.codigo = '333'
        """)
        res_pto = await db.execute(query_pto, {"eid": data["emisor_id"]})
        
        if not res_pto.fetchone():
            return {
                "ok": True, "codigo_error": "POINT_NOT_CONFIGURED",
                "mensaje_cliente": f"⚠️ Hola {data['razon_social']}, para facturar por WhatsApp debes tener habilitado el Establecimiento 001 - Punto de Emisión 333."
            }

        # Check Créditos
        # AJUSTE: Referencia a 'balance_emision'
        if data["balance_emision"] <= 0:
            return {
                "ok": True, "has_credits": False, "codigo_error": "USER_NOT_CREDITS",
                "data": {"nombre": data["full_name"], "empresa": data["razon_social"]},
                "mensaje_cliente": f"⚠️ Hola {data['razon_social']}, no tienes créditos disponibles."
            }

        return {
            "ok": True, "has_credits": True,
            "data": {
                "emisor_id": data["emisor_id"], "nombre": data["full_name"], "empresa": data["razon_social"],
                "ruc": data["ruc"], "balance": data["balance_emision"], "establecimiento": "001", "punto_emision": "333"
            },
            "mensaje_cliente": f"✅ Hola {data['full_name']}, estás listo para facturar (Punto 001-333). Tienes {data['balance_emision']} créditos."
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[Check WS Error] {str(e)}")
        return {"ok": False, "mensaje_cliente": "❌ Error técnico al verificar cuenta."}