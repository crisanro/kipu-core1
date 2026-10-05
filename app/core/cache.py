# app/core/cache.py
"""
Servicio de caché Redis para Kipu.
- Conexión lazy (se crea al primer uso)
- TTLs centralizados para consistencia
- Helpers tipados: get_json / set_json / delete / clear_prefix
- Invalidación por emisor eficiente: SCAN por familia (no SCAN *)
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
    DOCUMENTOS_EMITIDOS = 180   # 3 min — historial de emitidos
    DOCUMENTOS_RECIBIDOS = 180  # 3 min — historial de recibidos
    RESUMEN_FISCAL       = 300  # 5 min — resumen por tipo / totales
    DECLARACION_IVA = 300  # 5 minutos

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
    DOCS_EMITIDOS = "documentos_emitidos:{eid}:{fi}:{ff}:{sb}:{tipo}:{estado}:{q}:{page}:{limit}"
    DOCS_RECIBIDOS = "documentos_recibidos:{eid}:{fi}:{ff}:{tipo}:{estado}:{q}:{page}:{limit}"
    RESUMEN_EMITIDOS = "resumen_emitidos:{eid}:{fi}:{ff}"
    RESUMEN_RECIBIDOS = "resumen_recibidos:{eid}:{fi}:{ff}:{tipo}:{estado}:{q}"
    DECLARACION_IVA = "declaracion:iva:{eid}:{periodo}"

    @staticmethod
    def fmt(template: str, **kwargs) -> str:
        return template.format(**kwargs)


# Familias de claves que pertenecen a un emisor.
# Cada familia genera un SCAN "familia:emisor_id:*" — mucho más eficiente que SCAN *.
_FAMILIAS_EMISOR = (
    "emisor",
    "dashboard",
    "dashboard_header",
    "dashboard_docs",
    "clientes",
    "cliente",
    "estructura",
    "apikeys",
    "status",
    "factura",
    "historial",
    "cuentas",
    "proformas",
    "proforma",
    "notificaciones",
    "productos",
    "empresa",
    "documentos_emitidos",
    "documentos_recibidos",
    "resumen_emitidos",
    "resumen_recibidos",
    "declaracion",
)

_LOTE_BORRADO = 500


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


# ── Helpers internos ───────────────────────────────────────────────────────────

async def _unlink_en_lotes(r: aioredis.Redis, keys: list[str]) -> int:
    """UNLINK no bloquea Redis (libera memoria en segundo plano)."""
    total = 0
    for i in range(0, len(keys), _LOTE_BORRADO):
        total += await r.unlink(*keys[i:i + _LOTE_BORRADO])
    return total


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
    if not keys:
        return 0
    try:
        r = await get_redis()
        return await r.delete(*keys)
    except Exception as e:
        logger.warning(f"[CACHE] DELETE error {keys}: {e}")
        return 0


async def cache_clear_prefix(prefix: str) -> int:
    """
    Borra todas las claves que empiecen con 'prefix*'.
    Usa SCAN para no bloquear Redis y UNLINK en lotes.
    OJO: termina el prefijo con ':' si no quieres que 'x:1' borre también 'x:10'.
    """
    try:
        r    = await get_redis()
        keys = [k async for k in r.scan_iter(match=f"{prefix}*", count=500)]
        if not keys:
            return 0
        return await _unlink_en_lotes(r, keys)
    except Exception as e:
        logger.warning(f"[CACHE] CLEAR PREFIX error ({prefix}*): {e}")
        return 0


async def invalidate_emisor(emisor_id: int) -> int:
    """
    Invalida TODO el caché relacionado a un emisor.

    En lugar de SCAN * (recorre TODAS las keys de Redis), hace un SCAN por
    cada familia con el patrón "familia:emisor_id:*". Redis filtra del lado
    del servidor, lo que es órdenes de magnitud más rápido cuando hay
    muchas keys de otros emisores.

    Coincidencia exacta del ID: invalidar el emisor 1 NO toca el 10 ni el 100
    porque el patrón es "familia:1:*" (requiere ":" después del ID).

    Llamar después de cualquier mutación (PATCH config, subir firma, pagos, etc.)
    """
    try:
        eid = int(emisor_id)
        r   = await get_redis()
        keys_to_delete: list[str] = []

        for familia in _FAMILIAS_EMISOR:
            # Patrón exacto: "dashboard:42:*" — Redis filtra server-side
            patron = f"{familia}:{eid}:*"
            async for k in r.scan_iter(match=patron, count=500):
                keys_to_delete.append(k)

            # También la key exacta sin sufijo: "emisor:42", "estructura:42"
            patron_exacto = f"{familia}:{eid}"
            if await r.exists(patron_exacto):
                keys_to_delete.append(patron_exacto)

        # Además, el patrón legacy de comprobante_estado_service
        async for k in r.scan_iter(match=f"kipu:cache:*:{eid}:*", count=500):
            keys_to_delete.append(k)

        if not keys_to_delete:
            return 0

        # Deduplicar (una key puede matchear en dos patrones)
        keys_to_delete = list(set(keys_to_delete))
        borradas = await _unlink_en_lotes(r, keys_to_delete)
        logger.info(f"[CACHE] Emisor {eid}: {borradas} claves invalidadas")
        return borradas

    except Exception as e:
        logger.warning(f"[CACHE] INVALIDATE EMISOR error ({emisor_id}): {e}")
        return 0