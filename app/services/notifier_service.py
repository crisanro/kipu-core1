import httpx
from datetime import datetime, timezone
from app.core.config import settings

async def notificar_cambio_estado(factura: dict, estado: str, detalle: dict = None):
    """
    Envía una notificación vía Webhook cuando una factura cambia de estado 
    (ej: de ENVIADO a AUTORIZADO).
    """
    webhook_url = settings.WEB_HOOK_NOTIFICACIONES
    if not webhook_url:
        # Si no hay URL configurada, ignoramos silenciosamente
        return

    # AJUSTE: Usamos datetime.now(timezone.utc) porque utcnow() está marcada como obsoleta (deprecated)
    payload = {
        "user_id": str(factura.get("user_uid")), # Aseguramos que el UUID sea string para el JSON
        "invoice_id": str(factura.get("id")),   # Aseguramos string
        "clave_acceso": factura.get("clave_acceso"),
        "estado": estado,
        "mensaje_sri": detalle,
        "fecha": datetime.now(timezone.utc).isoformat()
    }

    try:
        # AJUSTE: En lugar de crear un cliente en cada petición, lo ideal sería tener un cliente global,
        # pero para notificaciones puntuales, esta forma es segura y correcta.
        async with httpx.AsyncClient() as client:
            # Añadimos un timeout razonable para que un webhook lento no nos afecte
            response = await client.post(webhook_url, json=payload, timeout=5.0)
            
            # Opcional: Podrías verificar si el webhook respondió con error
            if response.status_code >= 400:
                print(f"⚠️ [Webhook Warning]: El servidor respondió con status {response.status_code}")
                
    except httpx.ConnectError:
        print(f"❌ [Webhook Error]: No se pudo conectar con la URL: {webhook_url}")
    except Exception as e:
        print(f"❌ [Webhook Error]: {str(e)}")