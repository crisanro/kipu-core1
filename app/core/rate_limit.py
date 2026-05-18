# app/core/rate_limit.py
"""
Rate limiting por sliding window usando Redis.
Diseño:
  - Clave:  "rl:{scope}:{identifier}"
  - Scope:  nombre del endpoint o grupo (ej: "invoice", "pin", "auth")
  - Identifier: emisor_id (autenticado) o IP (público)
  - Algoritmo: token bucket aproximado con INCR + EXPIRE

Uso en endpoint:
    from app.core.rate_limit import RateLimit, RateLimitScope

    @router.post("/emit")
    async def emitir(..., _rl=Depends(RateLimit(RateLimitScope.INVOICE))):
        ...
"""
import time
import logging
from enum import Enum
from typing import Optional
from fastapi import Depends, HTTPException, Request, status
import redis.asyncio as aioredis

from app.core.cache import get_redis

logger = logging.getLogger(__name__)


# ── Configuración de límites por scope ────────────────────────────────────────
class RateLimitScope(str, Enum):
    # (requests, ventana_segundos)
    INVOICE      = "invoice"      # emisión de facturas
    PIN          = "pin"          # solicitud de PINs 2FA
    AUTH         = "auth"         # endpoints de auth / reset
    RESET        = "reset"       # reset de contraseña
    EXPORT       = "export"       # exportar XMLs (ZIP)
    PUBLIC_CHECK = "public_check" # consulta pública de facturas
    GENERAL      = "general"      # fallback genérico


_LIMITS: dict[str, tuple[int, int]] = {
    # scope            -> (max_requests, window_seconds)
    RateLimitScope.INVOICE:      (25,  60),   # 30 facturas/min por emisor
    RateLimitScope.PIN:          (5,   300),  # 5 PINs cada 5 min
    RateLimitScope.AUTH:         (5,  60),   # 10 req/min en auth
    RateLimitScope.RESET:        (1,   60),
    RateLimitScope.EXPORT:       (3,   300),  # 3 exports cada 5 min
    RateLimitScope.PUBLIC_CHECK: (20,  60),   # 20 consultas/min por IP
    RateLimitScope.GENERAL:      (60,  60),   # 60 req/min genérico
}


# ── Core del rate limiter ──────────────────────────────────────────────────────

async def _check_rate_limit(
    redis_client: aioredis.Redis,
    scope: str,
    identifier: str,
) -> tuple[bool, int, int]:
    """
    Retorna (permitido, requests_restantes, retry_after_segundos).
    Usa INCR + EXPIRE atómico (safe bajo concurrencia normal).
    """
    max_req, window = _LIMITS.get(scope, _LIMITS[RateLimitScope.GENERAL])
    key = f"rl:{scope}:{identifier}"

    try:
        count = await redis_client.incr(key)
        if count == 1:
            # Primera petición en la ventana — establecer expiración
            await redis_client.expire(key, window)

        remaining = max(0, max_req - count)
        ttl = await redis_client.ttl(key)
        retry_after = ttl if ttl > 0 else window

        if count > max_req:
            return False, 0, retry_after

        return True, remaining, retry_after

    except Exception as e:
        # Si Redis falla, dejamos pasar (fail-open) para no afectar el servicio
        logger.warning(f"[RATE LIMIT] Redis error, fail-open: {e}")
        return True, -1, 0


# ── Dependencia FastAPI ────────────────────────────────────────────────────────

class RateLimit:
    """
    Dependencia reutilizable. Extrae el identificador del auth_data o de la IP.

    Uso:
        Depends(RateLimit(RateLimitScope.INVOICE))
        Depends(RateLimit(RateLimitScope.PIN, use_ip=True))
    """
    def __init__(self, scope: RateLimitScope, use_ip: bool = False):
        self.scope  = scope
        self.use_ip = use_ip

    async def __call__(self, request: Request) -> None:
        identifier = self._get_identifier(request)
        r = await get_redis()
        allowed, remaining, retry_after = await _check_rate_limit(r, self.scope, identifier)

        # Headers informativos (útiles para el frontend / Postman)
        request.state.rl_remaining   = remaining
        request.state.rl_retry_after = retry_after

        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"DEMASIADAS SOLICITUDES. INTENTA DE NUEVO EN {retry_after} SEGUNDOS.",
                headers={"Retry-After": str(retry_after)},
            )

    def _get_identifier(self, request: Request) -> str:
        if self.use_ip:
            # Leer IP real detrás de Cloudflare/proxy
            cf_ip      = request.headers.get("CF-Connecting-IP")       # Cloudflare
            forwarded  = request.headers.get("X-Forwarded-For", "")    # Proxy genérico
            real_ip    = request.headers.get("X-Real-IP")              # Nginx

            ip = cf_ip or real_ip or (forwarded.split(",")[0].strip() if forwarded else None) or request.client.host or "unknown"
            return ip

        emisor_id = getattr(request.state, "emisor_id", None)
        if emisor_id:
            return str(emisor_id)

        return request.client.host or "unknown"

# ── Decoradores de conveniencia ────────────────────────────────────────────────

def invoice_limit():
    return Depends(RateLimit(RateLimitScope.INVOICE))

def pin_limit():
    return Depends(RateLimit(RateLimitScope.PIN, use_ip=True))

def auth_limit():
    return Depends(RateLimit(RateLimitScope.AUTH, use_ip=True))

def export_limit():
    return Depends(RateLimit(RateLimitScope.EXPORT))

def public_check_limit():
    return Depends(RateLimit(RateLimitScope.PUBLIC_CHECK, use_ip=True))
