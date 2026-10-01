# app/services/declaraciones/renta_102.py
#
# Consolidado Anual Informativo para Impuesto a la Renta.
# Muestra las cifras acumuladas de la facturación electrónica del año
# sin asumir responsabilidades de cálculo completo de personas naturales.

from datetime import date
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def calcular_renta_102(db: AsyncSession, emisor_id: int, anio: int) -> dict:
    """
    Consolidado Anual Informativo para Impuesto a la Renta.
    Extrae los totales de comprobantes emitidos y recibidos del año.
    Devuelve la estructura completa necesaria para el router y la UI.
    """
    fi = date(anio, 1, 1)
    ff = date(anio, 12, 31)
    params = {"eid": emisor_id, "fi": fi, "ff": ff}

    doc_emitidos_ids = set()
    doc_recibidos_ids = set()

    # 1. VENTAS EMITIDAS (FAC + NDB)
    res_vta = await db.execute(text("""
        SELECT id, COALESCE(importe_total, 0) AS bruto
        FROM documentos_emitidos
        WHERE emisor_id     = :eid
          AND estado_sri    = 'AUTORIZADO'
          AND es_sandbox    = false
          AND fecha_emision BETWEEN :fi AND :ff
          AND tipo_doc      IN ('FAC', 'NDB')
    """), params)
    
    ventas_brutas = 0.0
    for r in res_vta.fetchall():
        doc_emitidos_ids.add(str(r.id))
        ventas_brutas += float(r.bruto or 0)

    # 2. NOTAS DE CRÉDITO EMITIDAS
    res_ncr = await db.execute(text("""
        SELECT id, COALESCE(importe_total, 0) AS ncr
        FROM documentos_emitidos
        WHERE emisor_id     = :eid
          AND estado_sri    = 'AUTORIZADO'
          AND es_sandbox    = false
          AND fecha_emision BETWEEN :fi AND :ff
          AND tipo_doc      = 'NCR'
    """), params)
    
    ncr_emitidas = 0.0
    for r in res_ncr.fetchall():
        doc_emitidos_ids.add(str(r.id))
        ncr_emitidas += float(r.ncr or 0)
        
    ventas_netas = round(max(ventas_brutas - ncr_emitidas, 0.0), 2)

    # 3. COMPRAS RECIBIDAS (Deducibles)
    res_compras = await db.execute(text("""
        SELECT id, COALESCE(subtotal_base, 0) AS deducibles
        FROM documentos_recibidos
        WHERE emisor_id       = :eid
          AND fecha_emision   BETWEEN :fi AND :ff
          AND deducible_renta = true
          AND tipo_doc        IN ('FAC', 'LIQ', 'NDB')
    """), params)
    
    compras_recibidas = 0.0
    for r in res_compras.fetchall():
        doc_recibidos_ids.add(str(r.id))
        compras_recibidas += float(r.deducibles or 0)

    # 4. LIQUIDACIONES DE COMPRA EMITIDAS (Son gastos/compras de la empresa)
    res_liq = await db.execute(text("""
        SELECT id, COALESCE(importe_total, 0) AS total
        FROM documentos_emitidos
        WHERE emisor_id     = :eid
          AND estado_sri    = 'AUTORIZADO'
          AND es_sandbox    = false
          AND fecha_emision BETWEEN :fi AND :ff
          AND tipo_doc      = 'LIQ'
    """), params)
    
    liquidaciones_emitidas = 0.0
    for r in res_liq.fetchall():
        doc_emitidos_ids.add(str(r.id))
        liquidaciones_emitidas += float(r.total or 0)
        
    gastos_deducibles_totales = round(compras_recibidas + liquidaciones_emitidas, 2)

    # 5. RETENCIONES DE RENTA RECIBIDAS (De tus clientes - Crédito Tributario)
    res_ret_rec = await db.execute(text("""
        SELECT d.id, COALESCE(
            CASE 
                WHEN tipo_doc = 'RET' THEN subtotal_base
                ELSE COALESCE((item->>'valorRetenido')::numeric, 0)
            END, 0) AS total
        FROM documentos_recibidos d
        LEFT JOIN LATERAL jsonb_array_elements(
            CASE WHEN jsonb_typeof(d.items_detalle) = 'array' THEN d.items_detalle ELSE '[]'::jsonb END
        ) AS item ON true
        WHERE d.emisor_id     = :eid
          AND d.tipo_doc      = 'RET'
          AND d.fecha_emision BETWEEN :fi AND :ff
          AND (item->>'codigo_impuesto' = '1' OR item->>'codigo' = '1' OR d.tipo_doc = 'RET')
    """), params)
    
    retenciones_recibidas = 0.0
    for r in res_ret_rec.fetchall():
        doc_recibidos_ids.add(str(r.id))
        retenciones_recibidas += float(r.total or 0)
    retenciones_recibidas = round(retenciones_recibidas, 2)

    # 6. RETENCIONES DE RENTA EMITIDAS (A tus proveedores)
    res_ret_emi = await db.execute(text("""
        SELECT d.id, COALESCE(SUM(COALESCE((imp->>'valorRetenido')::numeric, 0)), 0) AS total
        FROM documentos_emitidos d,
             jsonb_array_elements(
                 CASE
                     WHEN d.datos->'docsSustento'->'docSustento'->'retenciones'->'retencion' IS NOT NULL THEN
                         CASE WHEN jsonb_typeof(d.datos->'docsSustento'->'docSustento'->'retenciones'->'retencion') = 'array'
                              THEN d.datos->'docsSustento'->'docSustento'->'retenciones'->'retencion'
                              ELSE jsonb_build_array(d.datos->'docsSustento'->'docSustento'->'retenciones'->'retencion') END
                     WHEN d.datos->'impuestos'->'impuesto' IS NOT NULL THEN
                         CASE WHEN jsonb_typeof(d.datos->'impuestos'->'impuesto') = 'array'
                              THEN d.datos->'impuestos'->'impuesto'
                              ELSE jsonb_build_array(d.datos->'impuestos'->'impuesto') END
                     ELSE '[]'::jsonb
                 END
             ) AS imp
        WHERE d.emisor_id     = :eid
          AND d.estado_sri    = 'AUTORIZADO'
          AND d.es_sandbox    = false
          AND d.fecha_emision BETWEEN :fi AND :ff
          AND d.tipo_doc      = 'RET'
          AND (imp->>'codigo') = '1'
        GROUP BY d.id
    """), params)
    
    retenciones_emitidas = 0.0
    for r in res_ret_emi.fetchall():
        doc_emitidos_ids.add(str(r.id))
        retenciones_emitidas += float(r.total or 0)
    retenciones_emitidas = round(retenciones_emitidas, 2)

    # Base Informativa
    base_informativa = round(max(ventas_netas - gastos_deducibles_totales, 0.0), 2)

    # Casilleros formateados para evitar KeyError en el router
    casilleros = {
        "501": round(ventas_brutas, 2),
        "502": round(ncr_emitidas, 2),
        "503": ventas_netas,
        "601": gastos_deducibles_totales,
        "699": base_informativa,
        "849": base_informativa,
        "855": retenciones_recibidas,
        "841": retenciones_recibidas,
        "859": 0.0,
    }

    preguntas = {
        "tiene_ingresos": ventas_netas > 0,
        "tiene_gastos_deducibles": gastos_deducibles_totales > 0,
        "tiene_retenciones": retenciones_recibidas > 0,
    }

    desglose = {
        "ingresos": {
            "brutos": round(ventas_brutas, 2),
            "ncr": round(ncr_emitidas, 2),
            "netos": ventas_netas,
        },
        "gastos": {
            "deducibles": compras_recibidas,
            "liquidaciones": liquidaciones_emitidas,
            "total_deducibles": gastos_deducibles_totales,
        },
        "base_imponible": base_informativa,
        "retenciones": {
            "recibidas": retenciones_recibidas,
            "emitidas": retenciones_emitidas,
        }
    }

    resumen = {
        "casilleros": casilleros,
        "resumen_anual": {
            "ventas_brutas": round(ventas_brutas, 2),
            "notas_credito_emitidas": round(ncr_emitidas, 2),
            "ventas_netas": ventas_netas,
            "compras_deducibles": round(compras_recibidas, 2),
            "liquidaciones_compras": round(liquidaciones_emitidas, 2),
            "total_gastos_deducibles": gastos_deducibles_totales,
            "retenciones_renta_recibidas": retenciones_recibidas,
            "retenciones_renta_emitidas": retenciones_emitidas,
        },
        "resultado": {
            "impuesto_causado": 0.0,
            "retenciones": retenciones_recibidas,
            "a_pagar": 0.0,
            "saldo_favor": 0.0,
        },
    }

    return {
        "anio": anio,
        "preguntas": preguntas,
        "casilleros": casilleros,
        "desglose": desglose,
        "resumen": resumen,
        "doc_emitidos_ids": doc_emitidos_ids,
        "doc_recibidos_ids": doc_recibidos_ids,
        "total_doc_emitidos": len(doc_emitidos_ids),
        "total_doc_recibidos": len(doc_recibidos_ids),
    }