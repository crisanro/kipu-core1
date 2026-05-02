
# app/core/database.py

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import text
from app.core.config import settings
import redis.asyncio as aioredis
import logging

logger = logging.getLogger(__name__)

# =============================================================================
# POSTGRESQL
# =============================================================================

db_url = (
    settings.DATABASE_URL
    .replace("postgres://", "postgresql+asyncpg://")
    .replace("postgresql://", "postgresql+asyncpg://")
)

engine = create_async_engine(
    db_url,
    pool_size=10,
    max_overflow=5,
    pool_timeout=30.0,
    pool_recycle=1800,
    pool_pre_ping=True,
    echo=False,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# =============================================================================
# TENANT RESOLVER
# =============================================================================

_tenant_cache: dict[int, str] = {}


async def get_tenant_schema(emisor_id: int, session: AsyncSession) -> str:
    if emisor_id in _tenant_cache:
        return _tenant_cache[emisor_id]

    result = await session.execute(
        text("SELECT tenant_schema FROM public.emisor_tenant_map WHERE emisor_id = :id"),
        {"id": emisor_id},
    )
    row = result.fetchone()
    if not row:
        raise ValueError(f"Emisor {emisor_id} no tiene tenant asignado.")

    _tenant_cache[emisor_id] = row[0]
    return row[0]


def invalidate_tenant_cache(emisor_id: int) -> None:
    _tenant_cache.pop(emisor_id, None)


async def get_db_for_tenant(emisor_id: int):
    """
    Sesión con search_path apuntando al tenant del emisor.
    Usar en rutas del canal /app y /public que operan sobre invoices,
    clientes, establecimientos y puntos de emisión.
    """
    async with AsyncSessionLocal() as session:
        tenant_schema = await get_tenant_schema(emisor_id, session)
        await session.execute(
            text(f"SET search_path TO {tenant_schema}, public")
        )
        yield session


async def get_db():
    """
    Sesión estándar sobre schema public.
    Usar en: auth, registro de emisores, créditos, api_keys, admin.
    """
    async with AsyncSessionLocal() as session:
        await session.execute(text("SET search_path TO public"))
        yield session


# =============================================================================
# REDIS
# =============================================================================

_redis_pool: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=20,
        )
    return _redis_pool


async def close_redis():
    global _redis_pool
    if _redis_pool:
        await _redis_pool.aclose()
        _redis_pool = None


# =============================================================================
# CACHE HELPERS
# =============================================================================
#
# Keys:
#   kipu:{emisor_id}:invoices:list
#   kipu:{emisor_id}:invoices:{id}
#   kipu:{emisor_id}:clientes:list
#   kipu:{emisor_id}:clientes:{id}
#   kipu:{emisor_id}:dashboard
#   kipu:{emisor_id}:estructura
#   kipu:core:sujetos:{identificacion}
#
# TTLs recomendados:
#   invoices list/detail  → 300s  / 900s
#   clientes              → 1800s
#   dashboard             → 600s
#   estructura            → 3600s
#   sujetos_global        → 86400s


class CacheKeys:
    @staticmethod
    def invoice_list(emisor_id: int) -> str:
        return f"kipu:{emisor_id}:invoices:list"

    @staticmethod
    def invoice_detail(emisor_id: int, invoice_id: str) -> str:
        return f"kipu:{emisor_id}:invoices:{invoice_id}"

    @staticmethod
    def clientes_list(emisor_id: int) -> str:
        return f"kipu:{emisor_id}:clientes:list"

    @staticmethod
    def cliente_detail(emisor_id: int, cliente_id: str) -> str:
        return f"kipu:{emisor_id}:clientes:{cliente_id}"

    @staticmethod
    def dashboard(emisor_id: int) -> str:
        return f"kipu:{emisor_id}:dashboard"

    @staticmethod
    def estructura(emisor_id: int) -> str:
        return f"kipu:{emisor_id}:estructura"

    @staticmethod
    def sujeto_global(identificacion: str) -> str:
        return f"kipu:core:sujetos:{identificacion}"

    @staticmethod
    def emisor_pattern(emisor_id: int) -> str:
        return f"kipu:{emisor_id}:*"


async def cache_get(redis: aioredis.Redis, key: str) -> str | None:
    try:
        return await redis.get(key)
    except Exception as e:
        logger.warning(f"Cache GET error ({key}): {e}")
        return None


async def cache_set(redis: aioredis.Redis, key: str, value: str, ttl: int = 300) -> None:
    try:
        await redis.setex(key, ttl, value)
    except Exception as e:
        logger.warning(f"Cache SET error ({key}): {e}")


async def cache_invalidate_emisor(redis: aioredis.Redis, emisor_id: int) -> None:
    """Invalida TODAS las keys del emisor. Llamar en POST/PUT/PATCH/DELETE."""
    try:
        pattern = CacheKeys.emisor_pattern(emisor_id)
        keys = await redis.keys(pattern)
        if keys:
            await redis.delete(*keys)
    except Exception as e:
        logger.warning(f"Cache INVALIDATE error (emisor {emisor_id}): {e}")


async def cache_invalidate_key(redis: aioredis.Redis, key: str) -> None:
    try:
        await redis.delete(key)
    except Exception as e:
        logger.warning(f"Cache DELETE error ({key}): {e}")

SEMAFORO_KEY = "kipu:semaforo:facturas_activas"
MAX_FACTURAS_SIMULTANEAS = 10  # ajusta según tu servidor

async def semaforo_adquirir(redis: aioredis.Redis) -> bool:
    """
    Intenta adquirir un slot. 
    Retorna True si hay capacidad, False si está saturado.
    """
    activas = await redis.incr(SEMAFORO_KEY)
    if activas > MAX_FACTURAS_SIMULTANEAS:
        await redis.decr(SEMAFORO_KEY)  # liberar el incremento
        return False
    # Auto-expirar por si un request muere sin liberar
    await redis.expire(SEMAFORO_KEY, 60)
    return True

async def semaforo_liberar(redis: aioredis.Redis) -> None:
    """Libera el slot al terminar."""
    await redis.decr(SEMAFORO_KEY)