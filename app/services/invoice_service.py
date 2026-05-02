from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

async def obtener_historial_core(emisor_id: int, db: AsyncSession):
    query = text("""
        SELECT id, clave_acceso, estado, importe_total, created_at, pdf_path 
        FROM invoices_emitidas 
        WHERE emisor_id = :eid 
        ORDER BY created_at DESC LIMIT 50
    """)
    res = await db.execute(query, {"eid": emisor_id})
    facturas = res.fetchall()

    return {
        "ok": True, 
        "data": [dict(f._mapping) for f in facturas]
    }