# app/services/invoice_service.py — OPTIMIZADO con cache
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.cache import cache_get, cache_set, cache_clear_prefix


async def obtener_historial_core(emisor_id: int, db: AsyncSession):
    """
    Últimas 50 facturas del emisor.
    TTL corto (60s) — cambia con cada emisión.
    Se invalida desde emitir_factura_core vía cache_clear_prefix.
    """
    cache_key = f"historial:{emisor_id}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    # OPTIMIZACIÓN: traemos solo columnas necesarias para el listado
    # datos_factura (JSONB pesado) se excluye — solo se carga en el detalle
    query = text("""
        SELECT
            id,
            clave_acceso,
            numero_factura,
            estado,
            importe_total,
            fecha_emision,
            created_at,
            pdf_path
        FROM invoices_emitidas
        WHERE emisor_id = :eid
        ORDER BY created_at DESC
        LIMIT 50
    """)

    res     = await db.execute(query, {"eid": emisor_id})
    facturas = res.mappings().fetchall()

    data = []
    for f in facturas:
        d = dict(f)
        d["id"] = str(d["id"])
        data.append(d)

    result = {"ok": True, "data": data}
    await cache_set(cache_key, result, 60)  # 60s — datos recientes, TTL corto
    return result
