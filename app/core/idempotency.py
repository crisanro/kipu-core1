# app/core/idempotency.py
"""
Idempotency Key middleware para endpoints críticos de emisión de facturas.
- Clave Redis: idem:{emisor_id}:{uuid_cliente}
- TTL: 24 horas
- Fail-open: si Redis cae, deja pasar el request
"""
import json
import logging
from fastapi import Header, HTTPException, Request, status
from typing import Optional
from app.core.cache import cache_get, cache_set

logger = logging.getLogger(__name__)

IDEM_TTL = 86400  # 24 horas en segundos


def _clave(emisor_id: int, key: str) -> str:
    return f"idem:{emisor_id}:{key}"


async def verificar_idempotency(
    emisor_id: int,
    idempotency_key: Optional[str],
) -> Optional[dict]:
    """
    Verifica si el key ya fue procesado.
    - Retorna la respuesta cacheada si ya existe
    - Retorna None si es un request nuevo
    - Retorna None (fail-open) si Redis falla
    """
    if not idempotency_key:
        return None

    # Validar formato básico del key
    idempotency_key = idempotency_key.strip()
    if len(idempotency_key) < 8 or len(idempotency_key) > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="IDEMPOTENCY-KEY inválido. Debe ser un UUID v4 (entre 8 y 100 caracteres)."
        )

    try:
        clave = _clave(emisor_id, idempotency_key)
        cached = await cache_get(clave)
        if cached:
            logger.info(f"[IDEM] Hit para emisor {emisor_id} key {idempotency_key[:8]}...")
            return cached
    except Exception as e:
        # Fail-open — si Redis falla, dejamos pasar
        logger.warning(f"[IDEM] Redis error, fail-open: {e}")

    return None


async def guardar_idempotency(
    emisor_id: int,
    idempotency_key: Optional[str],
    response: dict,
) -> None:
    """
    Guarda la respuesta en Redis con TTL de 24h.
    Silencia errores — fail-open.
    """
    if not idempotency_key:
        return

    try:
        clave = _clave(emisor_id, idempotency_key.strip())
        await cache_set(clave, response, IDEM_TTL)
        logger.info(f"[IDEM] Guardado para emisor {emisor_id} key {idempotency_key[:8]}...")
    except Exception as e:
        logger.warning(f"[IDEM] Error guardando key, fail-open: {e}")