# app/services/declaraciones/snapshots.py
#
# Lectura y escritura de reportes_tributarios (la "foto" guardada de un cálculo).
#
# Correcciones respecto a la versión anterior:
#   - Una fila creada solo para guardar campos manuales (desglose vacío) ya no
#     cuenta como reporte en caché. Antes servía un reporte vacío para siempre.
#   - La ruta del XML del ATS (xml_path, nombre_zip) se conserva al recalcular,
#     y generar el XML ya no pisa el resumen del reporte.

import json
from datetime import date
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def leer(db: AsyncSession, emisor_id: int, tipo: str, periodo_db: date):
    """Reporte guardado con contenido real, o None."""
    res = await db.execute(text("""
        SELECT id, casilleros, preguntas, desglose, resumen,
               campos_manuales_valores,
               total_doc_emitidos, total_doc_recibidos,
               generado_at, regenerado_at
        FROM reportes_tributarios
        WHERE emisor_id = :eid
          AND tipo      = :tipo
          AND periodo   = :periodo
          AND desglose <> '{}'::jsonb
    """), {"eid": emisor_id, "tipo": tipo, "periodo": periodo_db})
    return res.fetchone()


async def guardar(
    db: AsyncSession, *,
    emisor_id: int, tipo: str, tipo_periodo: str, periodo_db: date,
    casilleros: dict, preguntas: dict, desglose: dict, resumen: dict,
    doc_emitidos_ids, doc_recibidos_ids, profile_id, regenerar: bool,
) -> None:
    """Upsert del reporte. Hace commit; si falla, hace rollback y lo registra (no rompe la respuesta)."""
    try:
        await db.execute(text("""
            INSERT INTO reportes_tributarios (
                emisor_id, tipo, tipo_periodo, periodo,
                casilleros, preguntas, desglose, resumen,
                doc_emitidos_ids, doc_recibidos_ids,
                total_doc_emitidos, total_doc_recibidos,
                generado_por
            ) VALUES (
                :eid, :tipo, :tipo_periodo, :periodo,
                CAST(:casilleros AS jsonb), CAST(:preguntas AS jsonb),
                CAST(:desglose   AS jsonb), CAST(:resumen   AS jsonb),
                CAST(:doc_e AS jsonb), CAST(:doc_r AS jsonb),
                :total_e, :total_r, :pid
            )
            ON CONFLICT (emisor_id, tipo, periodo) DO UPDATE SET
                tipo_periodo        = EXCLUDED.tipo_periodo,
                casilleros          = EXCLUDED.casilleros,
                preguntas           = EXCLUDED.preguntas,
                desglose            = EXCLUDED.desglose,
                -- conserva la ruta del XML del ATS si ya existía
                resumen             = EXCLUDED.resumen || jsonb_strip_nulls(jsonb_build_object(
                                          'xml_path',   reportes_tributarios.resumen->'xml_path',
                                          'nombre_zip', reportes_tributarios.resumen->'nombre_zip'
                                      )),
                doc_emitidos_ids    = EXCLUDED.doc_emitidos_ids,
                doc_recibidos_ids   = EXCLUDED.doc_recibidos_ids,
                total_doc_emitidos  = EXCLUDED.total_doc_emitidos,
                total_doc_recibidos = EXCLUDED.total_doc_recibidos,
                regenerado_at       = CASE WHEN :regenerar THEN NOW() ELSE reportes_tributarios.regenerado_at END,
                regenerado_por      = CASE WHEN :regenerar THEN :pid  ELSE reportes_tributarios.regenerado_por END
        """), {
            "eid":          emisor_id,
            "tipo":         tipo,
            "tipo_periodo": tipo_periodo,
            "periodo":      periodo_db,
            "casilleros":   json.dumps(casilleros),
            "preguntas":    json.dumps(preguntas),
            "desglose":     json.dumps(desglose),
            "resumen":      json.dumps(resumen),
            "doc_e":        json.dumps(list(doc_emitidos_ids)),
            "doc_r":        json.dumps(list(doc_recibidos_ids)),
            "total_e":      len(doc_emitidos_ids),
            "total_r":      len(doc_recibidos_ids),
            "pid":          str(profile_id) if profile_id else None,
            "regenerar":    regenerar,
        })
        await db.commit()
    except Exception as e:
        print(f"[{tipo}] ⚠️ Error guardando reporte: {e}")
        await db.rollback()


async def guardar_archivo_ats(
    db: AsyncSession, *, emisor_id: int, periodo_db: date,
    xml_path: str, nombre_zip: str, total_e: int, total_r: int, profile_id,
) -> None:
    """Registra la ruta del XML del ATS sin tocar el resto del reporte."""
    try:
        await db.execute(text("""
            INSERT INTO reportes_tributarios (
                emisor_id, tipo, tipo_periodo, periodo,
                casilleros, preguntas, desglose, resumen,
                doc_emitidos_ids, doc_recibidos_ids,
                total_doc_emitidos, total_doc_recibidos,
                generado_por
            ) VALUES (
                :eid, 'ATS', 'MENSUAL', :periodo,
                '{}', '{}', '{}', CAST(:archivo AS jsonb),
                '[]', '[]', :total_e, :total_r, :pid
            )
            ON CONFLICT (emisor_id, tipo, periodo) DO UPDATE SET
                resumen        = reportes_tributarios.resumen || CAST(:archivo AS jsonb),
                regenerado_at  = NOW(),
                regenerado_por = :pid
        """), {
            "eid":     emisor_id,
            "periodo": periodo_db,
            "archivo": json.dumps({"xml_path": xml_path, "nombre_zip": nombre_zip}),
            "total_e": total_e,
            "total_r": total_r,
            "pid":     str(profile_id) if profile_id else None,
        })
        await db.commit()
    except Exception as e:
        print(f"[ATS] ⚠️ Error guardando archivo: {e}")
        await db.rollback()


async def leer_campos_manuales(db: AsyncSession, emisor_id: int, periodo_db: date) -> dict:
    try:
        res = await db.execute(text("""
            SELECT campos_manuales_valores
            FROM reportes_tributarios
            WHERE emisor_id = :eid AND tipo = 'IVA' AND periodo = :periodo
        """), {"eid": emisor_id, "periodo": periodo_db})
        row = res.fetchone()
        return (row.campos_manuales_valores or {}) if row else {}
    except Exception:
        return {}


async def guardar_campos_manuales(
    db: AsyncSession, *, emisor_id: int, periodo_db: date, tipo_periodo: str,
    valores: dict, profile_id,
) -> None:
    """No hace commit (el endpoint lo hace después del audit_log)."""
    await db.execute(text("""
        INSERT INTO reportes_tributarios (
            emisor_id, tipo, tipo_periodo, periodo,
            casilleros, preguntas, desglose, resumen,
            campos_manuales_valores,
            doc_emitidos_ids, doc_recibidos_ids,
            total_doc_emitidos, total_doc_recibidos,
            generado_por
        ) VALUES (
            :eid, 'IVA', :tipo_periodo, :periodo,
            '{}', '{}', '{}', '{}',
            CAST(:valores AS jsonb),
            '[]', '[]', 0, 0, :pid
        )
        ON CONFLICT (emisor_id, tipo, periodo) DO UPDATE SET
            campos_manuales_valores = CAST(:valores AS jsonb)
    """), {
        "eid":          emisor_id,
        "periodo":      periodo_db,
        "tipo_periodo": tipo_periodo,
        "valores":      json.dumps(valores),
        "pid":          str(profile_id) if profile_id else None,
    })


async def listar(db: AsyncSession, emisor_id: int, tipo: str, anio: int) -> list[dict]:
    res = await db.execute(text("""
        SELECT tipo, periodo, tipo_periodo,
               total_doc_emitidos, total_doc_recibidos,
               generado_at, regenerado_at, resumen
        FROM reportes_tributarios
        WHERE emisor_id = :eid
          AND tipo      = :tipo
          AND EXTRACT(YEAR FROM periodo) = :anio
          AND desglose <> '{}'::jsonb
        ORDER BY periodo DESC
    """), {"eid": emisor_id, "tipo": tipo, "anio": anio})
    return [
        {
            "tipo":                r.tipo,
            "periodo":             r.periodo.isoformat(),
            "tipo_periodo":        r.tipo_periodo,
            "total_doc_emitidos":  r.total_doc_emitidos,
            "total_doc_recibidos": r.total_doc_recibidos,
            "generado_at":         r.generado_at.isoformat() if r.generado_at else None,
            "regenerado_at":       r.regenerado_at.isoformat() if r.regenerado_at else None,
            "resumen":             r.resumen or {},
        }
        for r in res.fetchall()
    ]