# app/services/documentos/secuencial.py
#
# Bloque 2 — Reservar secuencial del punto de emisión.

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException


async def reservar_secuencial(data: dict, emisor_id: int, tipo_doc: str, db: AsyncSession, es_sandbox: bool = False):
    """Reserva el siguiente secuencial del punto de emisión por tipo de documento y ambiente."""
    estab = str(data.get("establecimiento", "001")).zfill(3)
    pto   = str(data.get("punto_emision",   "001")).zfill(3)

    res = await db.execute(text("""
        SELECT
            p.id as punto_id,
            p.codigo as punto_codigo,
            p.secuenciales,
            est.codigo as estab_codigo,
            est.direccion as direccion_est,
            est.nombre_comercial as nombre_est
        FROM puntos_emision p
        JOIN establecimientos est ON p.establecimiento_id = est.id
        WHERE est.codigo    = :estab
          AND p.codigo      = :pto
          AND est.emisor_id = :eid
          AND p.is_active   = true
    """), {"estab": estab, "pto": pto, "eid": emisor_id})

    punto = res.fetchone()
    if not punto:
        raise HTTPException(status_code=404, detail="Establecimiento o punto de emisión no encontrado.")

    rama = "pruebas" if es_sandbox else "produccion"

    res_sec = await db.execute(text("""
        UPDATE puntos_emision
        SET secuenciales = jsonb_set(
            secuenciales,
            ARRAY[:rama, :tipo_doc],
            ((COALESCE((secuenciales->:rama->>:tipo_doc)::int, 0) + 1)::text)::jsonb
        )
        WHERE id = :pid
        RETURNING (secuenciales->:rama->>:tipo_doc)::int AS sec
    """), {"pid": punto.punto_id, "tipo_doc": tipo_doc, "rama": rama})

    secuencial = str(res_sec.scalar()).zfill(9)
    return punto, secuencial