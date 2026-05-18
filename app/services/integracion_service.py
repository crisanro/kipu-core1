# app/services/integracion_service.py — OPTIMIZADO con cache
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from datetime import datetime, timezone, date
from app.core.cache import cache_get, cache_set, CK, TTL


async def validar_estructura_core(emisor_id: int, estab_codigo: str, punto_codigo: str, db: AsyncSession):
    """Valida que exista la combinación establecimiento/punto. Sin cache — es una validación puntual."""
    query = text("""
        SELECT p.id, p.secuencial_actual, e.direccion
        FROM puntos_emision p
        JOIN establecimientos e ON p.establecimiento_id = e.id
        WHERE e.emisor_id = :eid
          AND e.codigo    = :estab
          AND p.codigo    = :punto
          AND e.is_active = true
          AND p.is_active = true
    """)
    res = await db.execute(query, {"eid": emisor_id, "estab": estab_codigo, "punto": punto_codigo})
    row = res.fetchone()

    if not row:
        raise HTTPException(
            status_code=404,
            detail="La combinación de establecimiento y punto de emisión no existe o está inactiva."
        )
    return {"ok": True, "mensaje": "Estructura válida", "data": dict(row._mapping)}


async def obtener_status_core(emisor_id: int, db: AsyncSession):
    """
    Resumen completo del estado del emisor para integraciones externas.
    CON CACHE — TTL 3 min. Se invalida cuando cambia el emisor.
    """
    cache_key = CK.fmt(CK.STATUS, eid=emisor_id)
    cached = await cache_get(cache_key)
    if cached:
        return cached

    # OPTIMIZACIÓN: subquery de últimas facturas embebida en el SELECT principal
    # Evita una segunda roundtrip a la DB
    query = text("""
        SELECT
            e.ruc,
            e.razon_social,
            e.nombre_comercial,
            e.ambiente,
            e.p12_expiration,
            COALESCE(c.balance_emision, 0) AS creditos_disponibles,
            (
                SELECT json_agg(last_docs)
                FROM (
                    SELECT
                        id, fecha_emision, estado,
                        identificacion_comprador, razon_social_comprador,
                        importe_total AS total, clave_acceso, created_at
                    FROM invoices_emitidas
                    WHERE emisor_id = e.id
                    ORDER BY created_at DESC
                    LIMIT 20
                ) last_docs
            ) AS ultimas_facturas
        FROM emisores e
        LEFT JOIN user_credits c ON e.id = c.emisor_id
        WHERE e.id = :eid
    """)

    res = await db.execute(query, {"eid": emisor_id})
    row = res.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Emisor no encontrado")

    data = row._mapping

    expiracion  = data["p12_expiration"]
    firma_valida = False

    if expiracion:
        if isinstance(expiracion, date) and not isinstance(expiracion, datetime):
            expiracion = datetime.combine(expiracion, datetime.min.time())
        if expiracion.tzinfo is None:
            expiracion = expiracion.replace(tzinfo=timezone.utc)
        firma_valida = expiracion > datetime.now(timezone.utc)

    dias_restantes = (expiracion - datetime.now(timezone.utc)).days if expiracion else 0

    result = {
        "ok": True,
        "emisor": {
            "ruc":             data["ruc"],
            "razon_social":    data["razon_social"],
            "nombre_comercial": data["nombre_comercial"],
            "ambiente":        "PRUEBAS" if data["ambiente"] == 1 else "PRODUCCIÓN",
            "firma": {
                "valida":          firma_valida,
                "vencimiento":     expiracion.isoformat() if expiracion else None,
                "dias_restantes":  dias_restantes
            },
        },
        "creditos": data["creditos_disponibles"],
        "historial": data["ultimas_facturas"] or [],
    }

    await cache_set(cache_key, result, TTL.STATUS_INTEGRACION)
    return result
