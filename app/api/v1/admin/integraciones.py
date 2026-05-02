#app/api/v1/admin/integraciones.py
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
    # 1. Extraer el body manualmente
    body_bytes = await request.body()
    body_str = body_bytes.decode()
    
    # 🔍 ESTO SÍ O SÍ APARECERÁ EN TU CONSOLA
    print("--------------------------------------------------")
    print(f"🔍 [DEBUG] BODY RECIBIDO: {body_str}")
    print("--------------------------------------------------")

    # 2. Intentar validar manualmente
    try:
        import json
        data_dict = json.loads(body_str)
        data = RequestPinSchema(**data_dict)
    except Exception as e:
        # ❌ AQUÍ VERÁS EL ERROR EXACTO DE PYDANTIC
        print(f"❌ [DEBUG] ERROR DE VALIDACIÓN: {e}")
        raise HTTPException(
            status_code=422, 
            detail=f"Error en estructura: {str(e)}"
        )

    # 3. Lógica normal (ahora usando el objeto 'data' validado)
    if data.tipo_accion in ["VALIDAR_WS", "VALIDACION_GENERAL"]:
        if not data.email:
            raise HTTPException(status_code=400, detail="El email es obligatorio.")
        query = text("SELECT emisor_id, email FROM profiles WHERE LOWER(email) = LOWER(:val)")
        param = {"val": data.email}
    else:
        query = text("SELECT emisor_id, email FROM profiles WHERE whatsapp_number = :val")
        param = {"val": data.whatsapp_number}

    res = await db.execute(query, param)
    user = res.fetchone()

    if not user:
        raise HTTPException(status_code=404, detail="Usuario no autorizado o no encontrado.")

    # 2. Generar PIN de 6 dígitos
    pin = f"{random.randint(100000, 999999)}"
    
    # 3. Guardar el challenge
    import json # Asegúrate de tener este import arriba

    query_insert = text("""
        INSERT INTO auth_challenges (email, whatsapp_number, pin, tipo_accion, metadata, emisor_id, expires_at)
        VALUES (:email, :ws, :pin, :tipo, :meta, :eid, NOW() + INTERVAL '10 minutes')
    """)

    await db.execute(query_insert, {
        "email": user.email,
        "ws": data.whatsapp_number, 
        "pin": pin, 
        "tipo": data.tipo_accion, 
        # 🔥 EL CAMBIO AQUÍ: Convertir dict a JSON string
        "meta": json.dumps(data.metadata) if data.metadata else "{}", 
        "eid": user.emisor_id
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
    factura_data: dict = Body(...),
    auth: dict = Depends(verify_whatsapp_service),
    db: AsyncSession = Depends(get_db)
):
    emisor_id = auth["emisor_id"]

    res_tenant = await db.execute(text("""
        SELECT tenant_schema FROM public.emisor_tenant_map
        WHERE emisor_id = :eid
    """), {"eid": emisor_id})
    tenant_row = res_tenant.fetchone()

    if not tenant_row:
        raise HTTPException(status_code=500, detail="Tenant no encontrado.")

    await db.execute(text(f"SET search_path TO {tenant_row.tenant_schema}, public"))

    return await emitir_factura_core(factura_data, emisor_id, db)
