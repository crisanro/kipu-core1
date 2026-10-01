# app/services/notification_service.py
import asyncio
import time
import httpx
from typing import Optional
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.cache import cache_delete

FCM_URL          = f"https://fcm.googleapis.com/v1/projects/{settings.FIREBASE_PROJECT_ID}/messages:send"
FCM_CONCURRENCIA = 10   # envíos simultáneos a FCM

# ── Cache del access token Google ─────────────────────────────────────────────
_token_cache: dict = {"token": None, "expires_at": 0}

# Referencias a tareas en segundo plano (evita que el GC las mate a mitad)
_tareas_bg: set = set()


def _lanzar_bg(coro):
    tarea = asyncio.create_task(coro)
    _tareas_bg.add(tarea)
    tarea.add_done_callback(_tareas_bg.discard)
    return tarea


# ── Token de acceso Google ────────────────────────────────────────────────────
def _refrescar_credenciales_sync():
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
    credentials.refresh(google.auth.transport.requests.Request())
    return credentials


async def _get_access_token() -> str:
    if _token_cache["token"] and time.time() < _token_cache["expires_at"] - 300:
        return _token_cache["token"]
    # refresh() es bloqueante (HTTP síncrono) → a un hilo
    credentials = await asyncio.to_thread(_refrescar_credenciales_sync)
    _token_cache["token"]      = credentials.token
    _token_cache["expires_at"] = credentials.expiry.timestamp()
    print(f"[FCM] 🔑 Token OAuth renovado — válido hasta {credentials.expiry.strftime('%H:%M:%S')}")
    return credentials.token


# ── Helpers FCM ───────────────────────────────────────────────────────────────
def _payload(token: str, titulo: str, cuerpo: str, url: Optional[str], tipo: Optional[str]) -> dict:
    """
    Mensaje SOLO DE DATOS: el service worker decide cómo mostrarlo.
    - Evita notificaciones duplicadas (SDK + onBackgroundMessage).
    - Evita fcm_options.link, que exige URL HTTPS absoluta.
    Todos los valores de 'data' deben ser strings.
    """
    return {
        "message": {
            "token": token,
            "data": {
                "title": titulo or "Kipu",
                "body":  cuerpo or "",
                "url":   url or "/dashboard",
                "tipo":  tipo or "",
            },
            "webpush": {
                "headers": {
                    "Urgency": "high",
                    "TTL":     "86400",   # 24 h si el dispositivo está apagado
                },
            },
        }
    }


def _error_code(res: httpx.Response) -> str:
    try:
        err = res.json().get("error", {})
        for d in err.get("details", []) or []:
            if d.get("errorCode"):
                return d["errorCode"]
        return err.get("status", "") or str(res.status_code)
    except Exception:
        return str(res.status_code)


async def _borrar_tokens(engine, tokens: list[str]):
    if not tokens or engine is None:
        return
    try:
        async with AsyncSession(engine) as s:
            await s.execute(
                text("DELETE FROM fcm_tokens WHERE token = ANY(:tokens)"),
                {"tokens": list(tokens)},
            )
            await s.commit()
        print(f"[FCM] 🗑️ {len(tokens)} token(s) muertos eliminados")
    except Exception as e:
        print(f"[FCM] ⚠️ Error eliminando tokens: {e}")


async def _enviar_push(
    tokens:  list[str],
    titulo:  str,
    cuerpo:  str,
    url:     Optional[str] = None,
    tipo:    Optional[str] = None,
    engine           = None,
) -> dict:
    tokens = list(dict.fromkeys(t for t in tokens if t))   # únicos, sin vacíos
    resumen = {"enviados": 0, "fallidos": 0, "eliminados": 0}
    if not tokens:
        return resumen

    try:
        access_token = await _get_access_token()
    except Exception as e:
        print(f"[FCM] ❌ No se pudo obtener token OAuth: {e}")
        resumen["fallidos"] = len(tokens)
        return resumen

    sem     = asyncio.Semaphore(FCM_CONCURRENCIA)
    muertos: list[str] = []
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type":  "application/json",
    }

    async with httpx.AsyncClient(timeout=10.0) as client:

        async def enviar_uno(token: str):
            async with sem:
                try:
                    res = await client.post(FCM_URL, json=_payload(token, titulo, cuerpo, url, tipo), headers=headers)
                except Exception as e:
                    resumen["fallidos"] += 1
                    print(f"[FCM] ⚠️ Error de red: {e}")
                    return

            if res.status_code == 200:
                resumen["enviados"] += 1
                return

            resumen["fallidos"] += 1
            code = _error_code(res)
            # SOLO UNREGISTERED (o 404) significa que el token está muerto.
            # INVALID_ARGUMENT suele ser un problema del payload: NO borrar.
            if code == "UNREGISTERED" or res.status_code == 404:
                muertos.append(token)
            else:
                print(f"[FCM] ⚠️ {res.status_code} {code}: {res.text[:300]}")

        await asyncio.gather(*(enviar_uno(t) for t in tokens))

    if muertos:
        resumen["eliminados"] = len(muertos)
        await _borrar_tokens(engine, muertos)

    print(f"[FCM] 📤 '{titulo}' → {resumen['enviados']} ok · {resumen['fallidos']} fallidos · {resumen['eliminados']} eliminados")
    return resumen


# ── Función principal ─────────────────────────────────────────────────────────
async def crear_notificacion(
    db:         AsyncSession,
    emisor_id:  int,
    tipo:       str,
    titulo:     str,
    mensaje:    str,
    referencia: str = None,
) -> bool:
    """
    Crea notificación en DB, invalida cache y envía push en segundo plano.
    Tipos: DECLARACION | FACTURA | CREDITOS | SISTEMA
    Retorna True si la notificación quedó guardada.

    COMPATIBILIDAD (temporal): si quien llama tiene cambios pendientes en su
    sesión, se confirman aquí (igual que antes). Lo que YA NO pasa: si la
    notificación falla, NO se hace rollback de la transacción de quien llama.
    """
    engine = db.bind

    # 0. Compatibilidad: confirmar lo pendiente del llamador (comportamiento previo)
    if db.in_transaction():
        try:
            await db.commit()
        except Exception as e:
            print(f"[Notif] ❌ Commit de la sesión del llamador falló (emisor {emisor_id}): {e}")
            return False

    tokens: list[str] = []

    # 1. Guardar en DB + buscar tokens (sesión propia)
    try:
        async with AsyncSession(engine) as s:
            await s.execute(text("""
                INSERT INTO notificaciones (emisor_id, tipo, titulo, mensaje, referencia, leida)
                VALUES (:eid, :tipo, :titulo, :mensaje, :ref, false)
            """), {
                "eid":     emisor_id,
                "tipo":    tipo,
                "titulo":  titulo,
                "mensaje": mensaje,
                "ref":     referencia,
            })
            res = await s.execute(text("""
                SELECT DISTINCT token FROM fcm_tokens WHERE emisor_id = :eid
            """), {"eid": emisor_id})
            tokens = [r.token for r in res.fetchall()]
            await s.commit()
        print(f"[Notif] 📥 {tipo} → emisor {emisor_id}: {titulo}")
    except Exception as e:
        print(f"[Notif] ❌ Error guardando notificación (emisor {emisor_id}): {e}")
        return False

    # 2. Invalidar cache para que el frontend vea la nueva notificación
    await cache_delete(f"notificaciones:{emisor_id}")

    # 3. Push en segundo plano — no retrasa la respuesta del endpoint
    if tokens:
        _lanzar_bg(_enviar_push(tokens, titulo, mensaje, referencia, tipo, engine))

    return True

# ── Notificar a todos los emisores ────────────────────────────────────────────
async def notificar_todos_emisores(
    db:              AsyncSession,
    tipo:            str,
    titulo:          str,
    mensaje:         str,
    referencia:      str  = None,
    solo_produccion: bool = True,
) -> int:
    """
    Inserta la notificación para todos los emisores en UNA sentencia
    y manda el push en segundo plano. Un dispositivo recibe un solo push
    aunque su usuario esté en varias empresas. Retorna # de emisores notificados.
    """
    engine = db.bind
    filtro = "AND e.ambiente = 2" if solo_produccion else ""
    emisor_ids: list[int] = []
    tokens:     list[str] = []

    try:
        async with AsyncSession(engine) as s:
            res = await s.execute(text(f"""
                INSERT INTO notificaciones (emisor_id, tipo, titulo, mensaje, referencia, leida)
                SELECT e.id, :tipo, :titulo, :mensaje, :ref, false
                FROM emisores e
                WHERE EXISTS (SELECT 1 FROM emisor_usuarios eu WHERE eu.emisor_id = e.id)
                {filtro}
                RETURNING emisor_id
            """), {
                "tipo":    tipo,
                "titulo":  titulo,
                "mensaje": mensaje,
                "ref":     referencia,
            })
            emisor_ids = [r.emisor_id for r in res.fetchall()]

            if emisor_ids:
                res_t = await s.execute(text("""
                    SELECT DISTINCT token FROM fcm_tokens WHERE emisor_id = ANY(:ids)
                """), {"ids": emisor_ids})
                tokens = [r.token for r in res_t.fetchall()]

            await s.commit()
    except Exception as e:
        print(f"[Notif] ❌ Error notificando a todos: {e}")
        return 0

    print(f"[Notif] 📢 '{titulo}' → {len(emisor_ids)} emisores · {len(tokens)} dispositivos")

    if emisor_ids:
        await cache_delete(*[f"notificaciones:{eid}" for eid in emisor_ids])
    if tokens:
        _lanzar_bg(_enviar_push(tokens, titulo, mensaje, referencia, tipo, engine))

    return len(emisor_ids)



# ── Notificaciones diferidas (para usar DENTRO de una transacción) ────────────
# Se encolan en la sesión y se envían SOLO después del commit.
# Si hay rollback, se descartan: nunca se avisa de algo que no quedó guardado.

_CLAVE_PENDIENTES = "kipu_notifs_pendientes"


def encolar_notificacion(
    db:         AsyncSession,
    emisor_id:  int,
    tipo:       str,
    titulo:     str,
    mensaje:    str,
    referencia: str = None,
) -> None:
    """No escribe nada todavía. Deduplica por (emisor, título) dentro de la misma transacción."""
    pendientes = db.info.setdefault(_CLAVE_PENDIENTES, [])
    if any(n["emisor_id"] == emisor_id and n["titulo"] == titulo for n in pendientes):
        return
    pendientes.append({
        "emisor_id":  emisor_id,
        "tipo":       tipo,
        "titulo":     titulo,
        "mensaje":    mensaje,
        "referencia": referencia,
    })


def descartar_notificaciones(db: AsyncSession) -> int:
    """Llamar junto a cada rollback."""
    pendientes = db.info.pop(_CLAVE_PENDIENTES, None) or []
    if pendientes:
        print(f"[Notif] 🗑️ {len(pendientes)} notificación(es) descartadas por rollback")
    return len(pendientes)


async def despachar_notificaciones(db: AsyncSession) -> int:
    """Llamar justo DESPUÉS del commit. Retorna cuántas se enviaron."""
    pendientes = db.info.pop(_CLAVE_PENDIENTES, None) or []
    enviadas = 0
    for n in pendientes:
        if await crear_notificacion(db, **n):
            enviadas += 1
    return enviadas