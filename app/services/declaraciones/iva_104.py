# app/services/declaraciones/iva_104.py
#
# Formulario 104 — IVA. Única fuente de verdad del cálculo: la usan el reporte,
# el widget del dashboard, /actual, /totales y el worker.
#
# Estructura (igual al formulario del SRI):
#
#   1. VENTAS            FAC + ND emitidas − NC emitidas                 → 401…429
#   2. COMPRAS           FAC + ND recibidas + LIQ EMITIDAS − NC recib.  → 500…529
#   3. PROPORCIONALIDAD  (ventas gravadas / ventas totales) × crédito   → 563, 564, 565
#   4. LIQUIDACIÓN       IVA ventas − crédito                            → 601 (causado) / 602 (a favor)
#   5. SALDOS            − saldo anterior por compras (605)
#                        − saldo anterior por retenciones (606)
#                        − retenciones que TE hicieron (609)            → 620 / saldo siguiente 615, 617
#                        − ajuste por crédito caducado > 5 años (625)
#   6. AGENTE RETENCIÓN  + retenciones que TÚ hiciste (721…731)        → 801
#                                                               TOTAL A PAGAR → 859

from datetime import date
from decimal import Decimal
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from . import periodos as per
from . import snapshots

CAMPOS_MANUALES_104 = [
    {"casillero": "605", "descripcion": "Saldo crédito tributario mes anterior (adquisiciones)"},
    {"casillero": "606", "descripcion": "Saldo crédito tributario mes anterior (retenciones)"},
    {"casillero": "625", "descripcion": "Ajuste por crédito tributario caducado (superior a 5 años)"},
    {"casillero": "402", "descripcion": "Ventas de activos fijos gravadas tarifa ≠ 0"},
    {"casillero": "501", "descripcion": "Adquisiciones de activos fijos con crédito tributario"},
    {"casillero": "504", "descripcion": "Importaciones de bienes gravados tarifa ≠ 0"},
]
CASILLEROS_MANUALES_PERMITIDOS = {c["casillero"] for c in CAMPOS_MANUALES_104}

_IMPUESTOS_EMITIDO = """
    CASE
        WHEN jsonb_typeof(d.datos->'resumenImpuestos') = 'array'
             AND jsonb_array_length(d.datos->'resumenImpuestos') > 0
            THEN d.datos->'resumenImpuestos'
        WHEN jsonb_typeof(d.datos->'infoNotaDebito'->'impuestos'->'impuesto') = 'array'
            THEN d.datos->'infoNotaDebito'->'impuestos'->'impuesto'
        WHEN jsonb_typeof(d.datos->'infoNotaDebito'->'impuestos'->'impuesto') = 'object'
            THEN jsonb_build_array(d.datos->'infoNotaDebito'->'impuestos'->'impuesto')
        ELSE '[]'::jsonb
    END
"""


def _r(n: float) -> float:
    return round(float(n or 0) + 0.0, 2)


def _grupo(tarifa: float) -> str:
    """Casilleros del formulario según la tarifa."""
    if tarifa == 0:
        return "0"
    if tarifa == 5:
        return "5"       # materiales de construcción
    if tarifa == 8:
        return "var"     # tarifa variable (turismo)
    return "gen"         # tarifa general (15%, 12%…)


def _acumular(dic: dict, clave, base: float, iva: float, doc_id=None) -> None:
    item = dic.setdefault(clave, {"base": 0.0, "iva": 0.0, "docs": set()})
    item["base"] += float(base or 0)
    item["iva"]  += float(iva or 0)
    if doc_id is not None:
        item["docs"].add(doc_id)


def _val(dic: dict, clave, campo: str) -> float:
    return dic.get(clave, {}).get(campo, 0.0)


# =============================================================================
# CÁLCULO DE UN PERIODO
# =============================================================================
async def calcular_iva_104(
    db: AsyncSession, emisor_id: int, fi: date, ff: date,
    saldo_605: float = 0.0, saldo_606: float = 0.0, saldo_625_manual: float | None = None,
) -> dict:
    """
    Calcula el 104 de un rango, con los saldos del periodo anterior ya resueltos.
    Devuelve: preguntas, casilleros, desglose, resumen, doc_emitidos_ids,
              doc_recibidos_ids, total_doc_emitidos, total_doc_recibidos
    """
    params = {"eid": emisor_id, "fi": fi, "ff": ff}
    doc_emitidos_ids:  set[str] = set()
    doc_recibidos_ids: set[str] = set()

    # ── Comprobantes EMITIDOS: ventas (FAC, ND), NC y liquidaciones (compras) ──
    res = await db.execute(text(f"""
        SELECT d.id, d.tipo_doc,
               COALESCE((imp->>'tarifa')::numeric, 0)                  AS tarifa,
               SUM(COALESCE((imp->>'baseImponible')::numeric, 0)) AS base,
               SUM(COALESCE((imp->>'valor')::numeric, 0))          AS iva
        FROM documentos_emitidos d,
             jsonb_array_elements({_IMPUESTOS_EMITIDO}) AS imp
        WHERE d.emisor_id     = :eid
          AND d.estado_sri    = 'AUTORIZADO'
          AND d.es_sandbox    = false
          AND d.fecha_emision BETWEEN :fi AND :ff
          AND d.tipo_doc      IN ('FAC', 'NDB', 'NCR', 'LIQ')
        GROUP BY d.id, d.tipo_doc, COALESCE((imp->>'tarifa')::numeric, 0)
    """), params)

    ventas, ncr_emit, liq = {}, {}, {}
    liq_ids: set[str] = set()
    for r in res.fetchall():
        doc_emitidos_ids.add(str(r.id))
        t = float(r.tarifa)
        if r.tipo_doc in ("FAC", "NDB"):
            _acumular(ventas, t, r.base, r.iva, str(r.id))
        elif r.tipo_doc == "NCR":
            _acumular(ncr_emit, t, r.base, r.iva)
        else:  # LIQ: la emites tú, pero es una COMPRA
            _acumular(liq, t, r.base, r.iva)
            liq_ids.add(str(r.id))

    # ── Comprobantes RECIBIDOS ──
    res = await db.execute(text("""
        SELECT d.id, d.tipo_doc,
               COALESCE((item->>'tarifa_iva')::numeric, 0)                    AS tarifa,
               COALESCE((item->>'credito_tributario_iva')::boolean, false)    AS credito,
               COALESCE((item->>'subtotal')::numeric, 0)                      AS base,
               COALESCE((item->>'valor_iva')::numeric, 0)                      AS iva
        FROM documentos_recibidos d,
             jsonb_array_elements(
                 CASE WHEN jsonb_typeof(d.items_detalle) = 'array' THEN d.items_detalle ELSE '[]'::jsonb END
             ) AS item
        WHERE d.emisor_id     = :eid
          AND d.fecha_emision BETWEEN :fi AND :ff
          AND d.tipo_doc      IN ('FAC', 'NDB', 'NCR')

        UNION ALL

        SELECT d.id, d.tipo_doc,
               CASE WHEN COALESCE(d.subtotal_base, 0) > 0 AND COALESCE(d.valor_iva_total, 0) > 0
                    THEN ROUND(d.valor_iva_total / d.subtotal_base * 100)
                    ELSE 0 END                                                AS tarifa,
               COALESCE(d.credito_tributario_iva, false)                      AS credito,
               COALESCE(d.subtotal_base, 0)                                   AS base,
               COALESCE(d.valor_iva_total, 0)                                 AS iva
        FROM documentos_recibidos d
        WHERE d.emisor_id     = :eid
          AND d.fecha_emision BETWEEN :fi AND :ff
          AND d.tipo_doc      IN ('FAC', 'NDB', 'NCR')
          AND (jsonb_typeof(d.items_detalle) IS DISTINCT FROM 'array'
               OR jsonb_array_length(d.items_detalle) = 0)
    """), params)

    compras_cc, compras_sc, ncr_recib = {}, {}, {}
    recibidos_venta: set[str] = set()
    for r in res.fetchall():
        doc_recibidos_ids.add(str(r.id))
        t = float(r.tarifa)
        if r.tipo_doc == "NCR":
            _acumular(ncr_recib, t, r.base, r.iva)
        else:
            recibidos_venta.add(str(r.id))
            destino = compras_cc if (r.credito or t == 0) else compras_sc
            _acumular(destino, t, r.base, r.iva)

    # Las LIQ emitidas entran como compras con derecho a crédito
    for t, v in liq.items():
        _acumular(compras_cc, t, v["base"], v["iva"])

    # ── Retenciones de IVA que TE hicieron (Casillero 609) ──
    res = await db.execute(text("""
        SELECT d.id, 
               COALESCE((item->>'valor_iva')::numeric, (item->>'total')::numeric, (item->>'valorRetenido')::numeric, 0) AS valor
        FROM documentos_recibidos d,
             jsonb_array_elements(
                 CASE WHEN jsonb_typeof(d.items_detalle) = 'array' THEN d.items_detalle ELSE '[]'::jsonb END
             ) AS item
        WHERE d.emisor_id = :eid AND d.tipo_doc = 'RET'
          AND d.fecha_emision BETWEEN :fi AND :ff
          AND (item->>'codigo_impuesto' = '2' OR item->>'codigo' = '2')

        UNION ALL

        SELECT d.id, COALESCE(d.valor_iva_total, 0) AS valor
        FROM documentos_recibidos d
        WHERE d.emisor_id = :eid AND d.tipo_doc = 'RET'
          AND d.fecha_emision BETWEEN :fi AND :ff
          AND (jsonb_typeof(d.items_detalle) IS DISTINCT FROM 'array'
               OR jsonb_array_length(d.items_detalle) = 0)
    """), params)
    c609 = 0.0
    for r in res.fetchall():
        doc_recibidos_ids.add(str(r.id))
        c609 += float(r.valor)
    c609 = _r(c609)

    # ── Retenciones de IVA que TÚ hiciste (Casilleros 721–731 y 799) ──
    # Soporta esquemas v1.0 y v2.0 del SRI en JSONB
    res = await db.execute(text("""
        SELECT d.id,
               COALESCE((imp->>'porcentajeRetener')::numeric, 0)  AS pct,
               SUM(COALESCE((imp->>'valorRetenido')::numeric, 0)) AS valor
        FROM documentos_emitidos d,
             jsonb_array_elements(
                 CASE
                     -- Esquema v2.0 SRI (docsSustento -> docSustento -> retenciones -> retencion)
                     WHEN d.datos->'docsSustento'->'docSustento'->'retenciones'->'retencion' IS NOT NULL THEN
                         CASE 
                             WHEN jsonb_typeof(d.datos->'docsSustento'->'docSustento'->'retenciones'->'retencion') = 'array'
                             THEN d.datos->'docsSustento'->'docSustento'->'retenciones'->'retencion'
                             ELSE jsonb_build_array(d.datos->'docsSustento'->'docSustento'->'retenciones'->'retencion')
                         END
                     -- Esquema v1.0 SRI (impuestos -> impuesto)
                     WHEN d.datos->'impuestos'->'impuesto' IS NOT NULL THEN
                         CASE
                             WHEN jsonb_typeof(d.datos->'impuestos'->'impuesto') = 'array'
                             THEN d.datos->'impuestos'->'impuesto'
                             ELSE jsonb_build_array(d.datos->'impuestos'->'impuesto')
                         END
                     ELSE '[]'::jsonb
                 END
             ) AS imp
        WHERE d.emisor_id     = :eid
          AND d.estado_sri    = 'AUTORIZADO'
          AND d.es_sandbox    = false
          AND d.fecha_emision BETWEEN :fi AND :ff
          AND d.tipo_doc      = 'RET'
          AND (imp->>'codigo') = '2' -- 2 = IVA
        GROUP BY d.id, COALESCE((imp->>'porcentajeRetener')::numeric, 0)
    """), params)

    PCT_CAS = {10: "721", 20: "723", 30: "725", 50: "727", 70: "729", 100: "731"}
    cas_ret = {c: 0.0 for c in PCT_CAS.values()}
    ret_e_desglose: dict[float, float] = {}
    for r in res.fetchall():
        doc_emitidos_ids.add(str(r.id))
        pct, valor = float(r.pct), float(r.valor)
        cas = PCT_CAS.get(int(pct))
        if cas:
            cas_ret[cas] += valor
        ret_e_desglose[pct] = ret_e_desglose.get(pct, 0.0) + valor
    cas_ret = {k: _r(v) for k, v in cas_ret.items()}

    # ── Conteo de comprobantes ──
    res = await db.execute(text("""
        SELECT COUNT(*) FILTER (WHERE estado_sri <> 'ANULADO' AND tipo_doc IN ('FAC', 'NDB', 'NCR')) AS emitidos,
               COUNT(*) FILTER (WHERE estado_sri =  'ANULADO' AND tipo_doc IN ('FAC', 'NDB', 'NCR')) AS anulados
        FROM documentos_emitidos
        WHERE emisor_id = :eid AND es_sandbox = false
          AND fecha_emision BETWEEN :fi AND :ff
    """), params)
    cnt = res.fetchone()

    # ═════════════════════════════════════════════════════════════════════════
    # 1. VENTAS
    # ═════════════════════════════════════════════════════════════════════════
    def por_grupo(dic: dict, grupo: str, campo: str) -> float:
        return sum(v[campo] for t, v in dic.items() if _grupo(t) == grupo)

    def neto_ventas(grupo: str, campo: str) -> float:
        return por_grupo(ventas, grupo, campo) - por_grupo(ncr_emit, grupo, campo)

    c401, c411, c421 = _r(por_grupo(ventas, "gen", "base")), _r(neto_ventas("gen", "base")), _r(neto_ventas("gen", "iva"))
    c410, c420, c430 = _r(por_grupo(ventas, "var", "base")), _r(neto_ventas("var", "base")), _r(neto_ventas("var", "iva"))
    c425, c435, c445 = _r(por_grupo(ventas, "5", "base")),   _r(neto_ventas("5", "base")),   _r(neto_ventas("5", "iva"))
    c403, c413       = _r(por_grupo(ventas, "0", "base")),   _r(neto_ventas("0", "base"))

    c409 = _r(c401 + c410 + c425 + c403)
    c419 = _r(c411 + c420 + c435 + c413)
    c429 = _r(c421 + c430 + c445)

    c480 = _r(c411 + c420 + c435)
    c481 = 0.0
    c482 = c429
    c483 = 0.0
    c484 = c429
    c485 = 0.0
    c499 = _r(c483 + c484)

    ventas_desglose = []
    for t in sorted(set(ventas) | set(ncr_emit)):
        bruto, iva_b = _val(ventas, t, "base"), _val(ventas, t, "iva")
        nc_b, nc_i   = _val(ncr_emit, t, "base"), _val(ncr_emit, t, "iva")
        ventas_desglose.append({
            "tarifa":    t,
            "bruto":     _r(bruto),
            "ncr":       _r(nc_b),
            "neto":      _r(bruto - nc_b),
            "iva_bruto": _r(iva_b),
            "iva_neto":  _r(iva_b - nc_i),
            "num_docs":  len(ventas.get(t, {}).get("docs", ())),
        })

    # ═════════════════════════════════════════════════════════════════════════
    # 2. COMPRAS
    # ═════════════════════════════════════════════════════════════════════════
    def neto_compras(grupo: str, campo: str) -> float:
        return por_grupo(compras_cc, grupo, campo) - por_grupo(ncr_recib, grupo, campo)

    c500, c510, c520 = _r(por_grupo(compras_cc, "gen", "base")), _r(neto_compras("gen", "base")), _r(neto_compras("gen", "iva"))
    c530, c533, c534 = _r(por_grupo(compras_cc, "var", "base")), _r(neto_compras("var", "base")), _r(neto_compras("var", "iva"))
    c540, c550, c560 = _r(por_grupo(compras_cc, "5", "base")),   _r(neto_compras("5", "base")),   _r(neto_compras("5", "iva"))
    c502 = _r(sum(v["base"] for t, v in compras_sc.items() if t > 0))
    c512 = c502
    c522 = _r(sum(v["iva"] for t, v in compras_sc.items() if t > 0))
    c507, c517 = _r(por_grupo(compras_cc, "0", "base")), _r(neto_compras("0", "base"))

    c509 = _r(c500 + c530 + c540 + c502 + c507)
    c519 = _r(c510 + c533 + c550 + c512 + c517)
    c529 = _r(c520 + c534 + c560 + c522)

    compras_desglose = []
    for t in sorted(t for t in set(compras_cc) | set(compras_sc) | set(ncr_recib) if t > 0):
        cc_b, cc_i = _val(compras_cc, t, "base"), _val(compras_cc, t, "iva")
        sc_b, sc_i = _val(compras_sc, t, "base"), _val(compras_sc, t, "iva")
        nc_b, nc_i = _val(ncr_recib, t, "base"), _val(ncr_recib, t, "iva")
        compras_desglose.append({
            "tarifa":          t,
            "con_credito":     _r(cc_b),
            "sin_credito":     _r(sc_b),
            "ncr":             _r(nc_b),
            "neto":            _r(cc_b + sc_b - nc_b),
            "iva_credito":     _r(cc_i - nc_i),
            "iva_sin_credito": _r(sc_i),
            "iva_neto":        _r(cc_i + sc_i - nc_i),
        })

    # ═════════════════════════════════════════════════════════════════════════
    # 3. FACTOR DE PROPORCIONALIDAD
    # ═════════════════════════════════════════════════════════════════════════
    ventas_con_derecho = c411 + c420 + c435
    c563 = round(ventas_con_derecho / c419, 4) if c419 > 0 else 1.0
    credito_bruto = c520 + c534 + c560
    c564 = _r(credito_bruto * c563)
    c565 = _r(credito_bruto - c564)

    # ═════════════════════════════════════════════════════════════════════════
    # 4. LIQUIDACIÓN
    # ═════════════════════════════════════════════════════════════════════════
    dif  = _r(c499 - c564)
    c601 = dif if dif > 0 else 0.0
    c602 = _r(-dif) if dif < 0 else 0.0

    # ═════════════════════════════════════════════════════════════════════════
    # 5. SALDOS ANTERIORES, CADUCIDAD (>5 AÑOS) Y RETENCIONES
    # ═════════════════════════════════════════════════════════════════════════
    c605 = _r(saldo_605)
    c606 = _r(saldo_606)

    # Consulta de sugerencia automática para el Casillero 625 (Lotes > 5 años)
    if saldo_625_manual is None:
        res_625 = await db.execute(text("""
            SELECT COALESCE(SUM(monto_disponible), 0)
            FROM credito_tributario_lotes
            WHERE emisor_id = :eid
              AND monto_disponible > 0
              AND fecha_caducidad <= :ff
        """), {"eid": emisor_id, "ff": ff})
        c625 = _r(res_625.scalar() or 0.0)
    else:
        c625 = _r(saldo_625_manual)

    credito_retenciones = _r(c606 + c609)

    if c601 > 0:
        usa_605   = min(c605, c601)
        restante  = _r(c601 - usa_605)
        usa_ret   = min(credito_retenciones, restante)
        c620      = _r(restante - usa_ret)
        c615      = max(_r(c605 - usa_605 - c625), 0.0)
        c617      = _r(credito_retenciones - usa_ret)
    else:
        c620 = 0.0
        c615 = max(_r(c605 + c602 - c625), 0.0)
        c617 = credito_retenciones

    c621 = 0.0
    c699 = _r(c620 + c621)

    # ═════════════════════════════════════════════════════════════════════════
    # 6. AGENTE DE RETENCIÓN
    # ═════════════════════════════════════════════════════════════════════════
    c799 = _r(sum(cas_ret.values()))
    c800 = 0.0
    c802 = 0.0
    c801 = _r(c799 - c800 - c802)
    c859 = _r(c699 + c801)

    # ═════════════════════════════════════════════════════════════════════════
    preguntas = {
        "requiere_informar":        c409 > 0 or c509 > 0 or c605 > 0 or c606 > 0,
        "credito_tributario_renta": c522 > 0,
        "comercio_exterior":        False,
        "notas_credito":            bool(ncr_emit) or bool(ncr_recib),
        "tarifa_turismo":            c410 > 0,
        "ha_realizado_ventas":      c409 > 0,
        "ventas_tarifa_0":          c403 > 0,
        "ventas_activos_fijos":     False,
        "ventas_tarifa_nz":         c401 + c410 + c425 > 0,
        "ha_realizado_compras":     c509 > 0,
        "importaciones":            False,
        "compras_activos_fijos":    False,
        "ha_realizado_retenciones": c799 > 0 or c609 > 0,
        "materiales_construccion":  c425 > 0 or c540 > 0,
    }

    casilleros = {
        "ventas": {
            "401": c401, "411": c411, "421": c421,
            "410": c410, "420": c420, "430": c430,
            "425": c425, "435": c435, "445": c445,
            "403": c403, "413": c413,
            "409": c409, "419": c419, "429": c429,
            "480": c480, "481": c481, "482": c482, "483": c483, "484": c484, "485": c485, "499": c499,
            "111": int(cnt.emitidos or 0), "113": int(cnt.anulados or 0),
        },
        "compras": {
            "500": c500, "510": c510, "520": c520,
            "530": c530, "533": c533, "534": c534,
            "540": c540, "550": c550, "560": c560,
            "502": c502, "512": c512, "522": c522,
            "507": c507, "517": c517,
            "509": c509, "519": c519, "529": c529,
            "563": c563, "564": c564, "565": c565,
            "115": len(recibidos_venta), "119": len(liq_ids),
        },
        "ret_emit":  {**cas_ret, "799": c799, "800": c800, "802": c802, "801": c801},
        "ret_recib": {"609": c609},
        "resumen": {
            "499": c499, "563": c563, "564": c564, "565": c565,
            "601": c601, "602": c602,
            "605": c605, "606": c606, "609": c609, "625": c625,
            "615": c615, "617": c617,
            "620": c620, "621": c621, "699": c699,
            "799": c799, "801": c801, "859": c859,
        },
    }

    desglose = {
        "ventas":                {"desglose": ventas_desglose,  "casilleros": casilleros["ventas"]},
        "compras":               {"desglose": compras_desglose, "casilleros": casilleros["compras"]},
        "retenciones_emitidas":  {
            "desglose":   [{"porcentaje": p, "valor": _r(v)} for p, v in sorted(ret_e_desglose.items())],
            "casilleros": casilleros["ret_emit"],
        },
        "retenciones_recibidas": {"casilleros": casilleros["ret_recib"]},
    }

    resumen = {
        "casilleros":      casilleros["resumen"],
        "campos_manuales": CAMPOS_MANUALES_104,
        "resultado": {
            "impuesto_causado": c601,
            "a_pagar":          c859,
            "saldo_favor":      _r(c615 + c617),
        },
    }

    return {
        "preguntas":           preguntas,
        "casilleros":          casilleros,
        "desglose":            desglose,
        "resumen":             resumen,
        "doc_emitidos_ids":    doc_emitidos_ids,
        "doc_recibidos_ids":    doc_recibidos_ids,
        "total_doc_emitidos":  len(doc_emitidos_ids),
        "total_doc_recibidos": len(doc_recibidos_ids),
    }


# =============================================================================
# CADENA DE CRÉDITOS ENTRE PERIODOS
# =============================================================================
def periodo_anterior(p: per.Periodo) -> per.Periodo:
    meses = 6 if p.tipo_periodo == "SEMESTRAL" else 1
    return per.crear_periodo(p.tipo, p.tipo_periodo, per.sumar_meses(p.inicio, -meses))


async def _declarado(db: AsyncSession, emisor_id: int, p: per.Periodo) -> bool:
    res = await db.execute(text("""
        SELECT declarado FROM declaraciones_sri
        WHERE emisor_id = :eid AND tipo = '104' AND periodo = :periodo
    """), {"eid": emisor_id, "periodo": p.inicio})
    fila = res.fetchone()
    return bool(fila and fila.declarado)


def _desde_snapshot(snap) -> dict:
    return {
        "preguntas":           snap.preguntas,
        "casilleros":          snap.casilleros,
        "desglose":            snap.desglose,
        "resumen":             snap.resumen,
        "doc_emitidos_ids":    None,
        "doc_recibidos_ids":    None,
        "total_doc_emitidos":  snap.total_doc_emitidos,
        "total_doc_recibidos": snap.total_doc_recibidos,
        "congelado":           True,
        "generado_at":         snap.generado_at.isoformat() if snap.generado_at else None,
        "regenerado_at":       snap.regenerado_at.isoformat() if snap.regenerado_at else None,
    }


async def saldos_anteriores(db: AsyncSession, obl, p: per.Periodo, memo: dict, profundidad: int = 0) -> dict:
    """
    605/606/625 del periodo p, en este orden de prioridad:
      1. Lo que el usuario ingresó a mano para p.
      2. El 615/617 del periodo anterior calculado por Kipu.
      3. Cero, si el periodo anterior es previo a su inicio en Kipu.
    """
    manual = await snapshots.leer_campos_manuales(db, obl.emisor_id, p.inicio)
    c605_m = manual.get("605")
    c606_m = manual.get("606")
    c625_m = float(manual["625"]) if "625" in manual else None

    if c605_m is not None or c606_m is not None:
        return {
            "605": float(c605_m or 0),
            "606": float(c606_m or 0),
            "625": c625_m,
            "origen": "MANUAL",
            "periodo_anterior": None,
        }

    ant = periodo_anterior(p)
    if not ant.existe_para(obl.inicio, per.hoy_ec()) or profundidad >= 36:
        return {
            "605": 0.0,
            "606": 0.0,
            "625": c625_m,
            "origen": "SIN_HISTORIAL",
            "periodo_anterior": ant.nombre,
        }

    calc_ant = await resultado_periodo(db, obl, ant, memo, profundidad=profundidad + 1)
    res_ant  = calc_ant["casilleros"].get("resumen", {})
    return {
        "605": float(res_ant.get("615", 0)),
        "606": float(res_ant.get("617", 0)),
        "625": c625_m,
        "origen": "KIPU",
        "periodo_anterior": ant.nombre,
    }


async def resultado_periodo(
    db: AsyncSession, obl, p: per.Periodo, memo: dict | None = None,
    *, forzar: bool = False, profundidad: int = 0,
) -> dict:
    """
    104 de un periodo con la cadena de saldos resuelta.
    - Declarado: devuelve la foto congelada (salvo forzar=True, para sustitutivas).
    - No declarado: se calcula en vivo.
    """
    memo = {} if memo is None else memo
    if p.inicio in memo and not forzar:
        return memo[p.inicio]

    if not forzar and await _declarado(db, obl.emisor_id, p):
        snap = await snapshots.leer(db, obl.emisor_id, "IVA", p.inicio)
        if snap and "615" in (snap.casilleros or {}).get("resumen", {}):
            memo[p.inicio] = _desde_snapshot(snap)
            return memo[p.inicio]

    saldos = await saldos_anteriores(db, obl, p, memo, profundidad)
    calc   = await calcular_iva_104(
        db, obl.emisor_id, p.inicio, p.fin,
        saldo_605=saldos["605"],
        saldo_606=saldos["606"],
        saldo_625_manual=saldos["625"]
    )
    calc["resumen"]["saldos"] = {
        "origen":           saldos["origen"],
        "periodo_anterior": saldos["periodo_anterior"],
    }
    calc["congelado"] = False
    memo[p.inicio] = calc
    return calc


# =============================================================================
# FORMATO COMPATIBLE (widget, /actual, /totales, worker)
# =============================================================================
def resumen_iva(calc: dict) -> dict:
    v = calc["casilleros"]["ventas"]
    c = calc["casilleros"]["compras"]
    r = calc["casilleros"]["resumen"]
    return {
        "ventas": {
            "total":          _r(v["419"] + v["429"]),
            "base_imponible": v["419"],
            "iva_cobrado":    r["499"],
        },
        "compras": {
            "total":              _r(c["519"] + c["529"]),
            "total_deducible":    c["519"],
            "credito_tributario": r["564"],
        },
        "retenciones_recibidas": r["609"],
        "resumen_iva": {
            "iva_cobrado":        r["499"],
            "credito_tributario": r["564"],
            "iva_causado":        r["601"],
            "retenciones":        r["609"],
            "iva_a_pagar":        r["859"],
            "saldo_a_favor":      _r(r["615"] + r["617"]),
        },
    }