import random
from fastapi import APIRouter, Depends, Query, Body, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import verify_n8n_service, verify_whatsapp_service
from app.schemas.admin import TopupRequest, RequestPin
from app.services.admin_service import recargar_creditos_core, solicitar_pin_core, chequear_estado_ws_core
from app.utils.sri_service import emitir_factura_core
from sqlalchemy import text
from app.schemas.seguridad import RequestPinSchema # Asegúrate de tener este schema



router = APIRouter()

@router.post("/topup", summary="Recargar créditos a emisor (Exclusivo n8n)")
async def admin_topup(
    request: TopupRequest, 
    auth: dict = Depends(verify_n8n_service), 
    db: AsyncSession = Depends(get_db)
):
    return await recargar_creditos_core(request, db)

@router.post("/request-pin", summary="Generar PIN de 2FA")
async def request_pin(request: Request, db: AsyncSession = Depends(get_db)):
    # 1. Extraer y validar body
    body_bytes = await request.body()
    body_str   = body_bytes.decode()

    print("--------------------------------------------------")
    print(f"🔍 [DEBUG] BODY RECIBIDO: {body_str}")
    print("--------------------------------------------------")

    try:
        import json
        data_dict = json.loads(body_str)
        data      = RequestPinSchema(**data_dict)
    except Exception as e:
        print(f"❌ [DEBUG] ERROR DE VALIDACIÓN: {e}")
        raise HTTPException(status_code=422, detail=f"Error en estructura: {str(e)}")

    # 2. Buscar usuario según tipo de acción
    # Acciones que usan email
    if data.tipo_accion in ["VALIDAR_WS", "VALIDACION_GENERAL", "EXPORTAR_DATOS"]:
        if not data.email:
            raise HTTPException(status_code=400, detail="El email es obligatorio para esta acción.")
        query = text("SELECT emisor_id, email, whatsapp_number FROM profiles WHERE LOWER(email) = LOWER(:val)")
        param = {"val": data.email}

    # Acciones que usan WhatsApp — solo disponibles en producción
    elif data.tipo_accion in ["NUKE", "CREAR_TOKEN", "ELIMINAR_TOKEN"]:
        if not data.whatsapp_number:
            raise HTTPException(status_code=400, detail="El número de WhatsApp es obligatorio para esta acción.")
        query = text("SELECT emisor_id, email, whatsapp_number FROM profiles WHERE whatsapp_number = :val")
        param = {"val": data.whatsapp_number}

    else:
        raise HTTPException(status_code=400, detail=f"TIPO DE ACCIÓN NO RECONOCIDO: {data.tipo_accion}")

    res  = await db.execute(query, param)
    user = res.fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="USUARIO NO ENCONTRADO O NO AUTORIZADO.")

    # 3. Validaciones específicas por acción
    if data.tipo_accion == "NUKE":
        # NUKE solo disponible si tiene WhatsApp vinculado (producción)
        if not user.whatsapp_number:
            raise HTTPException(
                status_code=400,
                detail="SOLO PUEDES ELIMINAR TU CUENTA DESDE WHATSAPP UNA VEZ EN PRODUCCIÓN."
            )

    # 4. Verificar si ya existe un PIN activo del mismo tipo — evita spam
    res_check = await db.execute(text("""
        SELECT expires_at FROM auth_challenges
        WHERE emisor_id   = :eid
          AND tipo_accion  = :tipo
          AND expires_at   > NOW()
        LIMIT 1
    """), {"eid": user.emisor_id, "tipo": data.tipo_accion})
    existing = res_check.fetchone()
    if existing:
        raise HTTPException(
            status_code=429,
            detail=f"YA TIENES UN PIN ACTIVO PARA ESTA ACCIÓN. ESPERA A QUE EXPIRE E INTENTA NUEVAMENTE."
        )

    # 5. Generar PIN y guardar challenge
    pin = f"{random.randint(100000, 999999)}"

    await db.execute(text("""
        INSERT INTO auth_challenges (email, whatsapp_number, pin, tipo_accion, extra_data, emisor_id, expires_at)
        VALUES (:email, :ws, :pin, :tipo, CAST(:meta AS jsonb), :eid, NOW() + INTERVAL '10 minutes')
    """), {
        "email": user.email,
        "ws":    data.whatsapp_number,
        "pin":   pin,
        "tipo":  data.tipo_accion,
        "meta":  json.dumps(data.metadata) if hasattr(data, 'metadata') and data.metadata else "{}",
        "eid":   user.emisor_id
    })
    await db.commit()

    return {"ok": True, "pin": pin}

@router.get("/check-status", summary="Verificar estado de cuenta WhatsApp")
async def admin_check_status(
    whatsapp_number: str = Query(..., description="Número de WhatsApp"), 
    auth: dict = Depends(verify_n8n_service), 
    db: AsyncSession = Depends(get_db)
):
    return await chequear_estado_ws_core(whatsapp_number, db)

# 👇 LA JOYA DE LA CORONA: EMISIÓN VÍA WHATSAPP
@router.post("/invoice-whatsapp", summary="Emitir factura vía WhatsApp (n8n)")
async def admin_invoice_whatsapp(
    factura_data: dict = Body(...), # Aquí el body puede ser cualquier dict por ahora
    auth: dict = Depends(verify_whatsapp_service), # <--- Aquí extrae el emisor_id del número!
    db: AsyncSession = Depends(get_db)
):
    # Consumimos el servicio "Core" de facturación que creaste antes
    return await emitir_factura_core(factura_data, auth["emisor_id"], db)