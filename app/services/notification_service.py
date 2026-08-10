# app/services/notification_service.py
#
# Servicio para crear notificaciones en DB y enviarlas por FCM v1.
# Usado por workers y endpoints del backend.

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings

FCM_URL = f"https://fcm.googleapis.com/v1/projects/{settings.FIREBASE_PROJECT_ID}/messages:send"

# ── Token de acceso Google ─────────────────────────────────────────────────────
async def _get_access_token() -> str:
    import google.auth.transport.requests
    from google.oauth2 import service_account

    sa_info = {
        "type":                        "service_account",
        "project_id":                  settings.FIREBASE_PROJECT_ID,
        "private_key_id":              settings.FIREBASE_PRIVATE_KEY_ID,
        "private_key":                 settings.FIREBASE_PRIVATE_KEY.replace("\\n", "\n"),
        "client_email":                settings.FIREBASE_CLIENT_EMAIL,
        "client_id":                   "",
        "auth_uri":                    "https://accounts.google.com/o/oauth2/auth",
        "token_uri":                   "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url":        f"https://www.googleapis.com/robot/v1/metadata/x509/{settings.FIREBASE_CLIENT_EMAIL}",
    }

    credentials = service_account.Credentials.from_service_account_info(
        sa_info,
        scopes=["https://www.googleapis.com/auth/firebase.messaging"],
    )
    request = google.auth.transport.requests.Request()
    credentials.refresh(request)
    return credentials.token

# ── Enviar push a lista de tokens ──────────────────────────────────────────────
async def _enviar_push(tokens: list[str], titulo: str, cuerpo: str, url: str = None):
    if not tokens:
        return
    try:
        access_token = await _get_access_token()
        async with httpx.AsyncClient(timeout=10.0) as client:
            for token in tokens:
                payload = {
                    "message": {
                        "token": token,
                        "notification": {
                            "title": titulo,
                            "body":  cuerpo,
                        },
                        "data": {
                            "url": url or "/dashboard",
                        },
                        "webpush": {
                            "notification": {
                                "title": titulo,
                                "body":  cuerpo,
                                "icon":  "/icon-192.png",
                                "badge": "/icon-192.png",
                            },
                            "fcm_options": {
                                "link": url or "/dashboard",
                            }
                        }
                    }
                }
                res = await client.post(
                    FCM_URL,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type":  "application/json",
                    },
                )
                if res.status_code == 200:
                    print(f"[FCM] ✅ Push enviado")
                else:
                    print(f"[FCM] ⚠️ Error: {res.text[:200]}")

    except Exception as e:
        print(f"[FCM] ❌ Error enviando push: {e}")

# ── Función principal ──────────────────────────────────────────────────────────
async def crear_notificacion(
    db:         AsyncSession,
    emisor_id:  int,
    tipo:       str,
    titulo:     str,
    mensaje:    str,
    referencia: str = None,
):
    """
    Crea notificación en DB y la envía por FCM a todos los tokens del emisor.

    Tipos sugeridos:
      - DECLARACION   → recordatorio de declaración SRI
      - FACTURA       → factura autorizada/rechazada
      - CREDITOS      → créditos bajos o recargados
      - SISTEMA       → mensajes generales del sistema
    """
    try:
        # 1. Guardar en DB
        await db.execute(text("""
            INSERT INTO notificaciones (emisor_id, tipo, titulo, mensaje, referencia, leida)
            VALUES (:eid, :tipo, :titulo, :mensaje, :ref, false)
        """), {
            "eid":    emisor_id,
            "tipo":   tipo,
            "titulo": titulo,
            "mensaje": mensaje,
            "ref":    referencia,
        })
        await db.commit()
        print(f"[Notif] 📥 {tipo} → emisor {emisor_id}: {titulo}")

    except Exception as e:
        print(f"[Notif] ❌ Error guardando en DB: {e}")
        await db.rollback()
        return

    # 2. Buscar tokens FCM del emisor
    try:
        res = await db.execute(text("""
            SELECT DISTINCT token FROM fcm_tokens
            WHERE emisor_id = :eid
        """), {"eid": emisor_id})
        tokens = [r.token for r in res.fetchall()]
    except Exception as e:
        print(f"[Notif] ⚠️ Error buscando tokens: {e}")
        return

    # 3. Enviar push
    await _enviar_push(tokens, titulo, mensaje, referencia)


# ── Notificar a todos los emisores ────────────────────────────────────────────
async def notificar_todos_emisores(
    db:         AsyncSession,
    tipo:       str,
    titulo:     str,
    mensaje:    str,
    referencia: str = None,
    solo_produccion: bool = True,
):
    """
    Crea y envía notificación a todos los emisores activos.
    Usado por workers (declaraciones, recordatorios, etc.)
    """
    try:
        filtro = "AND e.ambiente = 2" if solo_produccion else ""
        res = await db.execute(text(f"""
            SELECT DISTINCT e.id
            FROM emisores e
            JOIN emisor_usuarios eu ON eu.emisor_id = e.id
            WHERE 1=1 {filtro}
        """))
        emisor_ids = [r.id for r in res.fetchall()]
        print(f"[Notif] 📢 Notificando {len(emisor_ids)} emisores: {titulo}")

        for emisor_id in emisor_ids:
            await crear_notificacion(db, emisor_id, tipo, titulo, mensaje, referencia)

    except Exception as e:
        print(f"[Notif] ❌ Error notificando todos: {e}")