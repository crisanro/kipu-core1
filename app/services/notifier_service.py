import httpx
from datetime import datetime
from app.core.config import settings

async def notificar_cambio_estado(factura: dict, estado: str, detalle: dict = None):
    webhook_url = settings.WEB_HOOK_NOTIFICACIONES
    if not webhook_url:
        return

    payload = {
        "user_id": factura.get("user_uid"),
        "invoice_id": factura.get("id"),
        "clave_acceso": factura.get("clave_acceso"),
        "estado": estado,
        "mensaje_sri": detalle,
        "fecha": datetime.utcnow().isoformat() + "Z"
    }

    try:
        # Usamos httpx asíncrono para no bloquear el servidor
        async with httpx.AsyncClient() as client:
            await client.post(webhook_url, json=payload, timeout=5.0)
    except Exception as e:
        print(f"[Webhook Error]: {str(e)}")