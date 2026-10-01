# app/services/declaraciones/renta_102.py
#
# Impuesto a la Renta anual.
#
# FASE 1: fórmulas y numeración movidas SIN CAMBIOS desde el router.
# Pendiente fase 3 (validado contra una declaración real 2025):
#   - numeración real del 102 para persona natural no obligada:
#     611/612/613 ingresos, 631 gastos, 749/832 base, 839 causado,
#     845 retenciones, 855/856, 868 a pagar, 869 saldo a favor
#   - LIQ emitidas no son ingresos
#   - tabla IR por año (hoy fija 2025)
#   - gastos personales 773–777 y rebaja 828
#   - saldo a favor con vencimiento de 3 años (art. 47 LRTI)

from datetime import date
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Tabla progresiva IR personas naturales 2025 (SRI)
TABLA_IR = [
    {"desde": 0,       "hasta": 11902,  "base": 0,     "porcentaje": 0},
    {"desde": 11902,   "hasta": 15159,  "base": 0,     "porcentaje": 5},
    {"desde": 15159,   "hasta": 19682,  "base": 163,   "porcentaje": 10},
    {"desde": 19682,   "hasta": 26031,  "base": 615,   "porcentaje": 12},
    {"desde": 26031,   "hasta": 34255,  "base": 1377,  "porcentaje": 15},
    {"desde": 34255,   "hasta": 45407,  "base": 2611,  "porcentaje": 20},
    {"desde": 45407,   "hasta": 60450,  "base": 4841,  "porcentaje": 25},
    {"desde": 60450,   "hasta": 80605,  "base": 8602,  "porcentaje": 30},
    {"desde": 80605,   "hasta": 107199, "base": 14648, "porcentaje": 35},
    {"desde": 107199,  "hasta": float("inf"), "base": 23957, "porcentaje": 37},
]


async def calcular_renta_102(db: AsyncSession, emisor_id: int, anio: int) -> dict:
    """
    Devuelve:
      preguntas, casilleros, desglose, resumen, doc_emitidos_ids, doc_recibidos_ids
    """
    fi = date(anio, 1, 1)
    ff = date(anio, 12, 31)

    # INGRESOS — FAC + LIQ autorizados del año
    res_ingresos = await db.execute(text("""
        SELECT
            d.id,
            (imp->>'tarifa')::numeric                 AS tarifa,
            SUM((imp->>'baseImponible')::numeric)     AS subtotal,
            SUM(d.importe_total)                      AS total
        FROM documentos_emitidos d,
             jsonb_array_elements(
                 CASE
                     WHEN jsonb_typeof(d.datos->'resumenImpuestos') = 'array'
                     THEN d.datos->'resumenImpuestos'
                     ELSE '[]'::jsonb
                 END
             ) AS imp
        WHERE d.emisor_id     = :eid
          AND d.estado_sri    = 'AUTORIZADO'
          AND d.fecha_emision BETWEEN :fi AND :ff
          AND d.es_sandbox    = false
          AND d.tipo_doc      IN ('FAC', 'LIQ')
        GROUP BY d.id, (imp->>'tarifa')::numeric
    """), {"eid": emisor_id, "fi": fi, "ff": ff})

    ingresos_brutos  = 0.0
    doc_emitidos_ids = set()
    for r in res_ingresos.fetchall():
        doc_emitidos_ids.add(str(r.id))
        ingresos_brutos += float(r.subtotal or 0)

    # NCR emitidas — reducen ingresos
    res_ncr = await db.execute(text("""
        SELECT
            d.id,
            SUM((imp->>'baseImponible')::numeric) AS subtotal
        FROM documentos_emitidos d,
             jsonb_array_elements(
                 CASE
                     WHEN jsonb_typeof(d.datos->'resumenImpuestos') = 'array'
                     THEN d.datos->'resumenImpuestos'
                     ELSE '[]'::jsonb
                 END
             ) AS imp
        WHERE d.emisor_id     = :eid
          AND d.estado_sri    = 'AUTORIZADO'
          AND d.fecha_emision BETWEEN :fi AND :ff
          AND d.es_sandbox    = false
          AND d.tipo_doc      = 'NCR'
        GROUP BY d.id
    """), {"eid": emisor_id, "fi": fi, "ff": ff})

    ncr_total = 0.0
    for r in res_ncr.fetchall():
        doc_emitidos_ids.add(str(r.id))
        ncr_total += float(r.subtotal or 0)

    ingresos_netos = round(ingresos_brutos - ncr_total, 2)

    # GASTOS DEDUCIBLES — columnas desnormalizadas
    res_gastos = await db.execute(text("""
        SELECT id, subtotal_base AS subtotal
        FROM documentos_recibidos
        WHERE emisor_id       = :eid
          AND fecha_emision   BETWEEN :fi AND :ff
          AND deducible_renta = true
          AND tipo_doc        IN ('FAC', 'LIQ')
    """), {"eid": emisor_id, "fi": fi, "ff": ff})

    gastos_deducibles = 0.0
    doc_recibidos_ids = set()
    for r in res_gastos.fetchall():
        doc_recibidos_ids.add(str(r.id))
        gastos_deducibles += float(r.subtotal or 0)
    gastos_deducibles = round(gastos_deducibles, 2)

    # RETENCIONES DE RENTA recibidas — items_detalle
    res_ret_renta = await db.execute(text("""
        SELECT
            d.id,
            SUM((item->>'total')::numeric) AS valor
        FROM documentos_recibidos d,
             jsonb_array_elements(d.items_detalle) AS item
        WHERE d.emisor_id     = :eid
          AND d.fecha_emision BETWEEN :fi AND :ff
          AND d.tipo_doc      = 'RET'
          AND jsonb_array_length(COALESCE(d.items_detalle, '[]'::jsonb)) > 0
          AND (item->>'codigo_impuesto') = '1'
        GROUP BY d.id
    """), {"eid": emisor_id, "fi": fi, "ff": ff})

    retenciones_renta = 0.0
    for r in res_ret_renta.fetchall():
        doc_recibidos_ids.add(str(r.id))
        retenciones_renta += float(r.valor or 0)
    retenciones_renta = round(retenciones_renta, 2)

    # CALCULAR
    base_imponible = max(round(ingresos_netos - gastos_deducibles, 2), 0.0)

    impuesto_causado = 0.0
    tramo_aplicado   = None
    for tramo in TABLA_IR:
        if base_imponible > tramo["desde"]:
            exceso           = min(base_imponible, tramo["hasta"]) - tramo["desde"]
            impuesto_causado = tramo["base"] + (exceso * tramo["porcentaje"] / 100)
            tramo_aplicado   = tramo
    impuesto_causado = round(impuesto_causado, 2)

    impuesto_a_pagar = round(max(impuesto_causado - retenciones_renta, 0), 2)
    saldo_a_favor    = round(max(retenciones_renta - impuesto_causado, 0), 2)

    casilleros = {
        "501": round(ingresos_brutos, 2),
        "502": round(ncr_total, 2),
        "503": ingresos_netos,
        "601": gastos_deducibles,
        "699": base_imponible,
        "701": base_imponible,
        "801": impuesto_causado,
        "841": retenciones_renta,
        "859": impuesto_a_pagar,
        "869": saldo_a_favor,
    }

    preguntas = {
        "tiene_ingresos":          ingresos_netos > 0,
        "tiene_gastos_deducibles": gastos_deducibles > 0,
        "tiene_retenciones":       retenciones_renta > 0,
        "debe_pagar":              impuesto_a_pagar > 0,
        "tiene_saldo_favor":       saldo_a_favor > 0,
        "supera_fraccion_basica":  base_imponible > TABLA_IR[0]["hasta"],
    }

    desglose = {
        "ingresos": {
            "brutos": round(ingresos_brutos, 2),
            "ncr":    round(ncr_total, 2),
            "netos":  ingresos_netos,
        },
        "gastos": {"deducibles": gastos_deducibles},
        "base_imponible": base_imponible,
        "tabla_ir": {
            "tramo":      tramo_aplicado,
            "tabla_anio": anio,
            "nota":       "Tabla personas naturales — verificar con resolución SRI vigente",
        },
    }

    resumen = {
        "casilleros": casilleros,
        "campos_manuales": [
            {"casillero": "504", "descripcion": "Otros ingresos (arrendamientos, intereses, etc.)"},
            {"casillero": "602", "descripcion": "Gastos personales (salud, educación, alimentación, vivienda, vestimenta)"},
            {"casillero": "603", "descripcion": "Rebaja por tercera edad o discapacidad"},
            {"casillero": "842", "descripcion": "Anticipo pagado año anterior"},
            {"casillero": "843", "descripcion": "Crédito tributario de años anteriores"},
        ],
        "resultado": {
            "impuesto_causado": impuesto_causado,
            "retenciones":      retenciones_renta,
            "a_pagar":          impuesto_a_pagar,
            "saldo_favor":      saldo_a_favor,
        },
    }

    return {
        "preguntas":         preguntas,
        "casilleros":        casilleros,
        "desglose":          desglose,
        "resumen":           resumen,
        "doc_emitidos_ids":  doc_emitidos_ids,
        "doc_recibidos_ids": doc_recibidos_ids,
    }