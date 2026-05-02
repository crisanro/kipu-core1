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
        query_update = text("""
            UPDATE user_credits 
            SET balance_emision = balance_emision + :amount, last_updated = NOW() 
            WHERE emisor_id = :eid 
            RETURNING balance
        """)
        res_update = await db.execute(query_update, {"amount": data.amount, "eid": emisor_id})
        nuevo_balance = res_update.scalar()

        # 3. Registrar Log
        query_log = text("""
            INSERT INTO transaction_logs (target_emisor_id, amount, action_type, description)
            VALUES (:eid, :amount, 'STRIPE_RECHARGE', :desc)
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
        tz = pytz.timezone('America/Guayaquil')
        expires_at = datetime.now(tz) + timedelta(minutes=10)

        await db.execute(text("""
            INSERT INTO auth_challenges (emisor_id, email, whatsapp_number, pin, tipo_accion, expires_at)
            VALUES (:eid, :email, :phone, :pin, :accion, :exp)
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
        # 1. Buscar perfil y emisor (todo en public)
        query = text("""
            SELECT p.email, p.full_name, e.id as emisor_id, e.razon_social, e.ruc, c.balance_emision
            FROM profiles p
            JOIN emisores e ON p.emisor_id = e.id
            JOIN user_credits c ON e.id = c.emisor_id
            WHERE p.whatsapp_number = :phone
        """)
        res  = await db.execute(query, {"phone": whatsapp_number})
        data = res.fetchone()

        if not data:
            return {
                "ok": False, "codigo_error": "USER_NOT_FOUND",
                "mensaje_cliente": "❌ Tu número no está vinculado a ninguna cuenta de Kipu."
            }

        # 2. Resolver tenant del emisor y setear search_path
        res_tenant = await db.execute(text("""
            SELECT tenant_schema FROM public.emisor_tenant_map
            WHERE emisor_id = :eid
        """), {"eid": data.emisor_id})
        tenant_row = res_tenant.fetchone()

        if not tenant_row:
            return {
                "ok": False, "codigo_error": "TENANT_NOT_FOUND",
                "mensaje_cliente": "❌ Error de configuración. Contacta soporte."
            }

        await db.execute(text(f"SET search_path TO {tenant_row.tenant_schema}, public"))

        # 3. Check Punto de Emisión 333 (ahora sí encuentra la tabla)
        res_pto = await db.execute(text("""
            SELECT p.id 
            FROM puntos_emision p
            JOIN establecimientos e ON p.establecimiento_id = e.id
            WHERE e.emisor_id = :eid AND e.codigo = '001' AND p.codigo = '333'
        """), {"eid": data.emisor_id})

        if not res_pto.fetchone():
            return {
                "ok": False, "codigo_error": "POINT_NOT_CONFIGURED",
                "mensaje_cliente": f"⚠️ Hola {data.razon_social}, para facturar por WhatsApp debes tener habilitado el Establecimiento 001 - Punto de Emisión 333."
            }

        # 4. Check Créditos
        if data.balance_emision <= 0:
            return {
                "ok": True, "has_credits": False, "codigo_error": "USER_NOT_CREDITS",
                "data": {"nombre": data.full_name, "empresa": data.razon_social},
                "mensaje_cliente": f"⚠️ Hola {data.razon_social}, no tienes créditos disponibles."
            }

        return {
            "ok": True, "has_credits": True,
            "data": {
                "emisor_id":      data.emisor_id,
                "nombre":         data.full_name,
                "empresa":        data.razon_social,
                "ruc":            data.ruc,
                "balance":        data.balance_emision,
                "establecimiento": "001",
                "punto_emision":  "333"
            },
            "mensaje_cliente": f"✅ Hola {data.full_name}, estás listo para facturar (Punto 001-333). Tienes {data.balance_emision} créditos."
        }

    except Exception as e:
        print(f"[Check WS Error] {str(e)}")
        return {"ok": False, "mensaje_cliente": "❌ Error técnico al verificar cuenta."}