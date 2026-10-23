# app/services/documentos/acceso.py
#
# Bloque 0 — Verificar acceso (suscripción, créditos API, firma electrónica).

from datetime import datetime, date
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from app.core.cache import get_redis
from .helpers import TZ_EC


async def verificar_acceso(emisor_id: int, api_key_id: int, es_sandbox: bool, db: AsyncSession):
    # ── Validar firma electrónica ─────────────────────────────────────────────
    res_firma = await db.execute(text("""
        SELECT p12_path, p12_expiration
        FROM emisores WHERE id = :eid
    """), {"eid": emisor_id})
    firma = res_firma.fetchone()
    if not firma or not firma.p12_path:
        raise HTTPException(
            status_code=402,
            detail="Debes cargar tu firma electrónica antes de emitir."
        )
    if not firma.p12_expiration or firma.p12_expiration <= date.today():
        raise HTTPException(
            status_code=402,
            detail="Tu firma electrónica está vencida. Actualízala para continuar."
        )

    # ── Sandbox ───────────────────────────────────────────────────────────────
    if es_sandbox:
        res = await db.execute(text("""
            SELECT e.* FROM emisores e WHERE e.id = :eid
        """), {"eid": emisor_id})
        emisor = res.fetchone()
        if not emisor:
            raise HTTPException(status_code=404, detail="Emisor no encontrado.")
        redis    = await get_redis()
        hoy      = datetime.now(TZ_EC).strftime("%Y-%m-%d")
        key_sand = f"kipu:usage:sandbox:{emisor_id}:{hoy}"
        uso_hoy_raw = await redis.get(key_sand)
        if uso_hoy_raw is None:
            res_count = await db.execute(text("""
                SELECT COUNT(*) FROM documentos_emitidos
                WHERE emisor_id  = :eid
                  AND es_sandbox = true
                  AND DATE(created_at AT TIME ZONE 'America/Guayaquil') = CURRENT_DATE
            """), {"eid": emisor_id})
            uso_hoy = res_count.scalar() or 0
            await redis.set(key_sand, uso_hoy, ex=86400)
        else:
            uso_hoy = int(uso_hoy_raw)
        if uso_hoy >= 100:
            raise HTTPException(
                status_code=429,
                detail="Límite de 100 documentos de prueba por día alcanzado."
            )
        return emisor, {"tipo": "sandbox", "descontar_credito": False, "redis_key": key_sand, "redis_ttl": 1}

    # ── Producción ────────────────────────────────────────────────────────────
    res = await db.execute(text("""
        SELECT e.*,
               COALESCE(uc.balance, 0) AS balance,
               s.estado                AS sub_estado,
               s.current_period_end,
               s.api_limit_mensual
        FROM emisores e
        LEFT JOIN user_credits  uc ON e.id = uc.emisor_id
        LEFT JOIN subscriptions s  ON e.id = s.emisor_id
        WHERE e.id = :eid
    """), {"eid": emisor_id})
    emisor = res.fetchone()
    if not emisor:
        raise HTTPException(status_code=404, detail="Emisor no encontrado.")
    sub_estado = getattr(emisor, "sub_estado", None)
    balance    = getattr(emisor, "balance", 0) or 0
    tiene_sub  = sub_estado in ("ACTIVO", "TRIAL")
    if not tiene_sub and balance <= 0:
        raise HTTPException(
            status_code=402,
            detail="Se requiere suscripción activa o créditos API para emitir."
        )

    # ── Suscriptor — verificar límite mensual ─────────────────────────────────
    if tiene_sub:
        limite   = getattr(emisor, "api_limit_mensual", 200) or 200
        redis    = await get_redis()
        mes      = datetime.now(TZ_EC).strftime("%Y-%m")
        key_prod = f"kipu:usage:prod:{emisor_id}:{mes}"
        uso_mes_raw = await redis.get(key_prod)
        if uso_mes_raw is None:
            res_count = await db.execute(text("""
                SELECT COUNT(*) FROM documentos_emitidos
                WHERE emisor_id  = :eid
                  AND es_sandbox = false
                  AND DATE_TRUNC('month', created_at AT TIME ZONE 'America/Guayaquil')
                    = DATE_TRUNC('month', NOW() AT TIME ZONE 'America/Guayaquil')
            """), {"eid": emisor_id})
            uso_mes = res_count.scalar() or 0
            await redis.set(key_prod, uso_mes, ex=35 * 86400)
        else:
            uso_mes = int(uso_mes_raw)
        if uso_mes >= limite:
            raise HTTPException(
                status_code=429,
                detail=f"Límite de {limite} documentos por mes alcanzado. Adquiere créditos adicionales para continuar."
            )
        tipo = "api" if api_key_id else "web"
        return emisor, {"tipo": tipo, "descontar_credito": False, "redis_key": key_prod, "redis_ttl": 35}

    # ── Sin suscripción — usa créditos ────────────────────────────────────────
    await db.execute(text("""
        SELECT emisor_id FROM user_credits WHERE emisor_id = :eid FOR UPDATE
    """), {"eid": emisor_id})
    tipo = "api" if api_key_id else "credito"
    return emisor, {"tipo": tipo, "descontar_credito": True, "redis_key": None}