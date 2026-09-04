# app/core/cache.py
"""
Servicio de caché Redis para Kipu.
- Conexión lazy (se crea al primer uso)
- TTLs centralizados para consistencia
- Helpers tipados: get_json / set_json / delete / clear_prefix
"""
import json
import logging
from typing import Any, Optional
import redis.asyncio as aioredis
from app.core.config import settings

logger = logging.getLogger(__name__)

# ── TTLs (segundos) ────────────────────────────────────────────────────────────
class TTL:
    EMISOR_PERFIL     = 300   # 5 min  — datos del emisor (RUC, firma, WS config)
    DASHBOARD         = 120   # 2 min  — métricas del dashboard
    CLIENTES_LISTA    = 180   # 3 min  — listado de clientes
    CLIENTE_DETALLE   = 300   # 5 min  — detalle + historial de un cliente
    ESTRUCTURA        = 600   # 10 min — establecimientos y puntos (cambian poco)
    API_KEYS          = 300   # 5 min  — lista de API Keys del emisor
    STATUS_INTEGRACION= 180   # 3 min  — estado del emisor vía API externa
    FACTURA_DETALLE   = 300
    HISTORIAL         = 360
    CUENTAS_LISTA   = 120   # 2 min — lista global de cuentas
    CUENTAS_CLIENTE = 180   # 3 min — cuentas por cliente
    PROFORMAS_LISTA  = 180   # 3 min
    PROFORMA_DETALLE = 300   # 5 min

# ── Prefijos de clave ──────────────────────────────────────────────────────────
class CK:
    """Cache Keys — prefijos estandarizados."""
    EMISOR          = "emisor:{eid}"
    DASHBOARD       = "dashboard:{eid}:{fi}:{ff}:{sb}"
    CLIENTES        = "clientes:{eid}"
    CLIENTE_DETALLE = "cliente:{eid}:{cid}"
    ESTRUCTURA      = "estructura:{eid}"
    API_KEYS        = "apikeys:{eid}"
    STATUS          = "status:{eid}"
    FACTURA         = "factura:{eid}:{fid}"
    HISTORIAL       = "historial:{eid}:{fi}:{ff}"
    CUENTAS_LISTA   = "cuentas:{eid}"
    CUENTAS_CLIENTE = "cuentas:{eid}:{cid}"
    PROFORMAS_LISTA  = "proformas:{eid}"
    PROFORMA_DETALLE = "proforma:{eid}:{pid}"

    @staticmethod
    def fmt(template: str, **kwargs) -> str:
        return template.format(**kwargs)


# ── Conexión singleton ─────────────────────────────────────────────────────────
_redis_client: Optional[aioredis.Redis] = None

async def get_redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=None,  # ← Sin timeout para soportar BRPOP blocking
        )
    return _redis_client


async def close_redis():
    global _redis_client
    if _redis_client:
        await _redis_client.aclose()
        _redis_client = None


# ── Helpers públicos ───────────────────────────────────────────────────────────

async def cache_get(key: str) -> Optional[Any]:
    """Devuelve el valor deserializado o None si no existe / falla Redis."""
    try:
        r = await get_redis()
        raw = await r.get(key)
        return json.loads(raw) if raw is not None else None
    except Exception as e:
        logger.warning(f"[CACHE] GET error ({key}): {e}")
        return None


async def cache_set(key: str, value: Any, ttl: int) -> bool:
    """Serializa y guarda el valor. Retorna True si OK."""
    try:
        r = await get_redis()
        await r.set(key, json.dumps(value, default=str), ex=ttl)
        return True
    except Exception as e:
        logger.warning(f"[CACHE] SET error ({key}): {e}")
        return False


async def cache_delete(*keys: str) -> int:
    """Elimina una o más claves. Retorna el número borrado."""
    try:
        r = await get_redis()
        return await r.delete(*keys)
    except Exception as e:
        logger.warning(f"[CACHE] DELETE error {keys}: {e}")
        return 0


async def cache_clear_prefix(prefix: str) -> int:
    """
    Borra todas las claves que empiecen con 'prefix*'.
    Usa SCAN para no bloquear Redis en producción.
    """
    try:
        r = await get_redis()
        deleted = 0
        async for key in r.scan_iter(f"{prefix}*"):
            await r.delete(key)
            deleted += 1
        return deleted
    except Exception as e:
        logger.warning(f"[CACHE] CLEAR PREFIX error ({prefix}*): {e}")
        return 0


async def invalidate_emisor(emisor_id: int):
    """
    Invalida TODO el cache relacionado a un emisor.
    Llamar después de cualquier mutación (PATCH config, subir firma, etc.)
    """
    await cache_clear_prefix(f"emisor:{emisor_id}")
    await cache_clear_prefix(f"dashboard:{emisor_id}")
    await cache_clear_prefix(f"dashboard_header:{emisor_id}")
    await cache_clear_prefix(f"clientes:{emisor_id}")
    await cache_clear_prefix(f"estructura:{emisor_id}")
    await cache_clear_prefix(f"apikeys:{emisor_id}")
    await cache_clear_prefix(f"status:{emisor_id}")
    await cache_clear_prefix(f"factura:{emisor_id}")
    await cache_clear_prefix(f"historial:{emisor_id}")
    await cache_clear_prefix(f"cuentas:{emisor_id}")
    await cache_clear_prefix(f"proformas:{emisor_id}")
    await cache_clear_prefix(f"proforma:{emisor_id}")
