# app/services/declaraciones/ats.py
#
# Anexo Transaccional Simplificado: cálculo del detalle y generación del XML.
#
# FASE 1: lógica movida SIN CAMBIOS desde el router. Pendiente fase 4:
#   - LIQ emitidas van en compras, no en ventas
#   - codSustento, tpIdProv, bases 0% y NCR con valores reales
#   - validación contra el XSD del SRI

import io
import zipfile
from datetime import date
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _t(parent, tag: str, valor: str):
    el = SubElement(parent, tag)
    el.text = valor
    return el


def _fmt2(n) -> str:
    return f"{float(n or 0):.2f}"


# =============================================================================
# CÁLCULO
# =============================================================================
async def calcular_ats(db: AsyncSession, emisor, emisor_id: int, fi: date, ff: date) -> dict:
    """
    emisor: fila con ruc, razon_social, obligado_contabilidad.
    Devuelve: preguntas, desglose, resumen, doc_emitidos_ids, doc_recibidos_ids
    """
    # VENTAS — detalle por comprobante emitido
    res_ventas = await db.execute(text("""
        SELECT
            d.id,
            d.tipo_doc,
            d.cod_doc,
            d.numero_doc,
            d.clave_acceso,
            d.fecha_emision,
            d.importe_total,
            d.datos->'infoFactura'->>'identificacionComprador'    AS id_comprador_fac,
            d.datos->'infoFactura'->>'razonSocialComprador'        AS razon_fac,
            d.datos->'infoFactura'->>'tipoIdentificacionComprador' AS tipo_id_fac,
            d.datos->'infoLiquidacionCompra'->>'identificacionProveedor'   AS id_comprador_liq,
            d.datos->'infoLiquidacionCompra'->>'razonSocialProveedor'       AS razon_liq,
            d.datos->>'legacy_id_comprador'    AS id_legacy,
            d.datos->>'legacy_razon_comprador' AS razon_legacy,
            d.datos->'resumenImpuestos'        AS resumen_impuestos
        FROM documentos_emitidos d
        WHERE d.emisor_id     = :eid
          AND d.estado_sri    = 'AUTORIZADO'
          AND d.fecha_emision BETWEEN :fi AND :ff
          AND d.es_sandbox    = false
          AND d.tipo_doc      IN ('FAC', 'LIQ', 'NCR', 'NDB')
        ORDER BY d.fecha_emision, d.numero_doc
    """), {"eid": emisor_id, "fi": fi, "ff": ff})

    ventas_detalle   = []
    doc_emitidos_ids = set()
    totales_ventas   = {
        "base_iva_diferente_0": 0.0,
        "base_iva_0":           0.0,
        "iva":                  0.0,
        "total":                0.0,
        "num_docs":             0,
    }

    for r in res_ventas.fetchall():
        doc_emitidos_ids.add(str(r.id))
        id_comp = r.id_comprador_fac or r.id_comprador_liq or r.id_legacy or "9999999999999"
        razon   = r.razon_fac or r.razon_liq or r.razon_legacy or "CONSUMIDOR FINAL"
        tipo_id = r.tipo_id_fac or "07"

        impuestos = r.resumen_impuestos or []
        if not isinstance(impuestos, list):
            impuestos = [impuestos] if impuestos else []

        base_nz = 0.0
        base_0  = 0.0
        iva     = 0.0
        for imp in impuestos:
            if not isinstance(imp, dict):
                continue
            tarifa = float(imp.get("tarifa", 0) or 0)
            base   = float(imp.get("baseImponible", 0) or 0)
            valor  = float(imp.get("valor", 0) or 0)
            if tarifa == 0:
                base_0  += base
            else:
                base_nz += base
                iva     += valor

        ventas_detalle.append({
            "tipo_doc":       r.tipo_doc,
            "cod_doc":        r.cod_doc,
            "numero_doc":     r.numero_doc,
            "clave_acceso":   r.clave_acceso,
            "fecha_emision":  str(r.fecha_emision),
            "tipo_id":        tipo_id,
            "identificacion": id_comp,
            "razon_social":   razon,
            "base_iva_nz":    round(base_nz, 2),
            "base_iva_0":     round(base_0,  2),
            "iva":            round(iva,     2),
            "total":          float(r.importe_total),
        })

        totales_ventas["base_iva_diferente_0"] += base_nz
        totales_ventas["base_iva_0"]           += base_0
        totales_ventas["iva"]                  += iva
        totales_ventas["total"]                += float(r.importe_total)
        totales_ventas["num_docs"]             += 1

    # Retenciones emitidas
    res_ret_e = await db.execute(text("""
        SELECT
            d.id,
            d.numero_doc,
            d.clave_acceso,
            d.fecha_emision,
            d.datos->'infoCompRetencion'->>'identificacionSujetoRetenido' AS id_retenido,
            d.datos->'infoCompRetencion'->>'razonSocialSujetoRetenido'     AS razon_retenido,
            d.datos->'infoCompRetencion'->>'periodoFiscal'                 AS periodo_fiscal,
            d.datos->'impuestos'                                           AS impuestos
        FROM documentos_emitidos d
        WHERE d.emisor_id     = :eid
          AND d.estado_sri    = 'AUTORIZADO'
          AND d.fecha_emision BETWEEN :fi AND :ff
          AND d.es_sandbox    = false
          AND d.tipo_doc      = 'RET'
        ORDER BY d.fecha_emision, d.numero_doc
    """), {"eid": emisor_id, "fi": fi, "ff": ff})

    retenciones_emitidas = []
    for r in res_ret_e.fetchall():
        doc_emitidos_ids.add(str(r.id))
        impuestos = r.impuestos or {}
        imp_list  = impuestos.get("impuesto", [])
        if not isinstance(imp_list, list):
            imp_list = [imp_list] if imp_list else []

        lineas = []
        for imp in imp_list:
            if not isinstance(imp, dict):
                continue
            lineas.append({
                "codigo":           imp.get("codigo"),
                "codigo_retencion": imp.get("codigoRetencion"),
                "base_imponible":   float(imp.get("baseImponible", 0) or 0),
                "porcentaje":       float(imp.get("porcentajeRetener", 0) or 0),
                "valor_retenido":   float(imp.get("valorRetenido", 0) or 0),
            })

        retenciones_emitidas.append({
            "numero_doc":     r.numero_doc,
            "clave_acceso":   r.clave_acceso,
            "fecha_emision":  str(r.fecha_emision),
            "identificacion": r.id_retenido,
            "razon_social":   r.razon_retenido,
            "periodo_fiscal": r.periodo_fiscal,
            "impuestos":      lineas,
        })

    # COMPRAS — detalle por comprobante recibido
    res_compras = await db.execute(text("""
        SELECT
            d.id,
            d.tipo_doc,
            d.cod_doc,
            d.numero_doc,
            d.clave_acceso,
            d.fecha_emision,
            d.importe_total,
            d.ruc_proveedor,
            d.razon_social_proveedor,
            d.deducible_renta,
            d.credito_tributario_iva,
            d.fuente,
            d.subtotal_base,
            d.valor_iva_total
        FROM documentos_recibidos d
        WHERE d.emisor_id     = :eid
          AND d.fecha_emision BETWEEN :fi AND :ff
          AND d.tipo_doc      IN ('FAC', 'LIQ', 'NCR', 'NDB')
        ORDER BY d.fecha_emision, d.numero_doc
    """), {"eid": emisor_id, "fi": fi, "ff": ff})

    compras_detalle   = []
    doc_recibidos_ids = set()
    totales_compras   = {
        "base_iva_diferente_0": 0.0,
        "base_iva_0":           0.0,
        "iva_con_credito":      0.0,
        "iva_sin_credito":      0.0,
        "total":                0.0,
        "num_docs":             0,
    }

    for r in res_compras.fetchall():
        doc_recibidos_ids.add(str(r.id))

        base_nz      = float(r.subtotal_base    or 0)
        base_0       = 0.0
        iva_credito  = float(r.valor_iva_total or 0) if r.credito_tributario_iva else 0.0
        iva_sin_cred = float(r.valor_iva_total or 0) if not r.credito_tributario_iva else 0.0

        compras_detalle.append({
            "tipo_doc":        r.tipo_doc,
            "cod_doc":         r.cod_doc,
            "numero_doc":      r.numero_doc,
            "clave_acceso":    r.clave_acceso or f"FISICO-{r.id}",
            "fecha_emision":   str(r.fecha_emision),
            "ruc_proveedor":   r.ruc_proveedor,
            "razon_proveedor": r.razon_social_proveedor,
            "fuente":          r.fuente,
            "base_iva_nz":     round(base_nz,      2),
            "base_iva_0":      round(base_0,       2),
            "iva_credito":     round(iva_credito,  2),
            "iva_sin_credito": round(iva_sin_cred, 2),
            "total":           float(r.importe_total),
            "deducible_renta": r.deducible_renta,
        })

        totales_compras["base_iva_diferente_0"] += base_nz
        totales_compras["base_iva_0"]           += base_0
        totales_compras["iva_con_credito"]      += iva_credito
        totales_compras["iva_sin_credito"]      += iva_sin_cred
        totales_compras["total"]                += float(r.importe_total)
        totales_compras["num_docs"]             += 1

    # Retenciones recibidas
    res_ret_r = await db.execute(text("""
        SELECT
            d.id,
            d.numero_doc,
            d.clave_acceso,
            d.fecha_emision,
            d.ruc_proveedor,
            d.razon_social_proveedor,
            d.items_detalle
        FROM documentos_recibidos d
        WHERE d.emisor_id     = :eid
          AND d.fecha_emision BETWEEN :fi AND :ff
          AND d.tipo_doc      = 'RET'
        ORDER BY d.fecha_emision
    """), {"eid": emisor_id, "fi": fi, "ff": ff})

    retenciones_recibidas = []
    for r in res_ret_r.fetchall():
        doc_recibidos_ids.add(str(r.id))
        items  = r.items_detalle or []
        lineas = []
        for item in items:
            if not isinstance(item, dict):
                continue
            lineas.append({
                "codigo_impuesto":  item.get("codigo_impuesto"),
                "codigo_retencion": item.get("codigo_retencion"),
                "descripcion":      item.get("descripcion"),
                "base_imponible":   float(item.get("subtotal", 0) or 0),
                "porcentaje":       float(item.get("porcentaje", 0) or 0),
                "valor":            float(item.get("total", 0) or 0),
                "aplica_credito":   item.get("credito_tributario_iva", False),
                "num_doc_sustento": item.get("num_doc_sustento"),
                "cod_doc_sustento": item.get("cod_doc_sustento"),
            })
        retenciones_recibidas.append({
            "numero_doc":    r.numero_doc,
            "clave_acceso":  r.clave_acceso,
            "fecha_emision": str(r.fecha_emision),
            "ruc_agente":    r.ruc_proveedor,
            "razon_agente":  r.razon_social_proveedor,
            "impuestos":     lineas,
        })

    for k in totales_ventas:
        if k != "num_docs":
            totales_ventas[k] = round(totales_ventas[k], 2)
    for k in totales_compras:
        if k != "num_docs":
            totales_compras[k] = round(totales_compras[k], 2)

    desglose = {
        "ventas": {
            "detalle":     ventas_detalle,
            "retenciones": retenciones_emitidas,
            "totales":     totales_ventas,
        },
        "compras": {
            "detalle":     compras_detalle,
            "retenciones": retenciones_recibidas,
            "totales":     totales_compras,
        },
    }

    resumen = {
        "emisor": {
            "ruc":                   emisor.ruc,
            "razon_social":          emisor.razon_social,
            "obligado_contabilidad": emisor.obligado_contabilidad,
        },
        "periodo":             str(fi),
        "totales_ventas":      totales_ventas,
        "totales_compras":     totales_compras,
        "total_ret_emitidas":  len(retenciones_emitidas),
        "total_ret_recibidas": len(retenciones_recibidas),
    }

    preguntas = {
        "tiene_ventas":                totales_ventas["num_docs"] > 0,
        "tiene_compras":               totales_compras["num_docs"] > 0,
        "tiene_retenciones_emitidas":  len(retenciones_emitidas) > 0,
        "tiene_retenciones_recibidas": len(retenciones_recibidas) > 0,
        "obligado_contabilidad":       emisor.obligado_contabilidad == "SI",
    }

    return {
        "preguntas":         preguntas,
        "desglose":          desglose,
        "resumen":           resumen,
        "doc_emitidos_ids":  doc_emitidos_ids,
        "doc_recibidos_ids": doc_recibidos_ids,
    }


# =============================================================================
# XML
# =============================================================================
async def generar_xml_ats(db: AsyncSession, emisor, emisor_id: int, anio: int, mes: int, fi: date, ff: date) -> dict:
    """
    Arma el XML del ATS y lo comprime.
    Devuelve: zip_bytes, nombre_zip, total_ventas, total_compras
    """
    res_compras = await db.execute(text("""
        SELECT
            d.id, d.tipo_doc, d.cod_doc, d.numero_doc, d.clave_acceso,
            d.fecha_emision, d.importe_total, d.ruc_proveedor,
            d.razon_social_proveedor, d.fuente, d.subtotal_base,
            d.valor_iva_total, d.credito_tributario_iva, d.items_detalle, d.datos
        FROM documentos_recibidos d
        WHERE d.emisor_id     = :eid
          AND d.fecha_emision BETWEEN :fi AND :ff
          AND d.tipo_doc      IN ('FAC', 'LIQ', 'NCR', 'NDB')
        ORDER BY d.fecha_emision, d.numero_doc
    """), {"eid": emisor_id, "fi": fi, "ff": ff})
    compras = res_compras.fetchall()

    res_ret = await db.execute(text("""
        SELECT
            d.id, d.numero_doc, d.clave_acceso, d.fecha_emision,
            d.datos->'infoCompRetencion'->>'identificacionSujetoRetenido' AS id_retenido,
            d.datos->'impuestos' AS impuestos
        FROM documentos_emitidos d
        WHERE d.emisor_id     = :eid
          AND d.estado_sri    = 'AUTORIZADO'
          AND d.fecha_emision BETWEEN :fi AND :ff
          AND d.es_sandbox    = false
          AND d.tipo_doc      = 'RET'
        ORDER BY d.fecha_emision
    """), {"eid": emisor_id, "fi": fi, "ff": ff})
    retenciones = res_ret.fetchall()

    res_ventas = await db.execute(text("""
        SELECT
            d.id, d.tipo_doc, d.cod_doc, d.numero_doc, d.clave_acceso,
            d.fecha_emision, d.importe_total,
            d.datos->'infoFactura'->>'identificacionComprador'     AS id_comprador,
            d.datos->'infoFactura'->>'tipoIdentificacionComprador' AS tipo_id,
            d.datos->'resumenImpuestos'                            AS resumen_impuestos
        FROM documentos_emitidos d
        WHERE d.emisor_id     = :eid
          AND d.estado_sri    = 'AUTORIZADO'
          AND d.fecha_emision BETWEEN :fi AND :ff
          AND d.es_sandbox    = false
          AND d.tipo_doc      IN ('FAC', 'LIQ', 'NCR', 'NDB')
        ORDER BY d.fecha_emision, d.numero_doc
    """), {"eid": emisor_id, "fi": fi, "ff": ff})
    ventas = res_ventas.fetchall()

    root = Element("iva")
    _t(root, "TipoIDInformante", "R")
    _t(root, "IdInformante",     emisor.ruc)
    _t(root, "razonSocial",      emisor.razon_social)
    _t(root, "Anio",             str(anio))
    _t(root, "Mes",              str(mes).zfill(2))

    total_ventas = sum(float(v.importe_total or 0) for v in ventas)
    _t(root, "totalVentas",     _fmt2(total_ventas))
    _t(root, "codigoOperativo", "IVA")

    # ── COMPRAS ──
    if compras:
        compras_el = SubElement(root, "compras")
        for c in compras:
            det = SubElement(compras_el, "detalleCompras")

            if "-" in (c.numero_doc or ""):
                p = c.numero_doc.split("-")
                estab      = p[0] if len(p) > 0 else "001"
                punto      = p[1] if len(p) > 1 else "001"
                secuencial = p[2] if len(p) > 2 else "000000001"
            else:
                estab = "001"; punto = "001"; secuencial = "000000001"

            autorizacion = c.clave_acceso or secuencial
            base_grav = float(c.subtotal_base or 0)
            base_0    = 0.0
            monto_iva = float(c.valor_iva_total or 0)

            _t(det, "codSustento",       "01")
            _t(det, "tpIdProv",          "01")
            _t(det, "idProv",            c.ruc_proveedor or "9999999999999")
            _t(det, "tipoComprobante",   c.cod_doc or "01")
            _t(det, "parteRel",          "NO")
            _t(det, "fechaRegistro",     c.fecha_emision.strftime("%d/%m/%Y"))
            _t(det, "establecimiento",   estab)
            _t(det, "puntoEmision",      punto)
            _t(det, "secuencial",        secuencial.lstrip("0") or "1")
            _t(det, "fechaEmision",      c.fecha_emision.strftime("%d/%m/%Y"))
            _t(det, "autorizacion",      autorizacion)
            _t(det, "baseNoGraIva",      _fmt2(0))
            _t(det, "baseImponible",     _fmt2(base_0))
            _t(det, "baseImpGrav",       _fmt2(base_grav))
            _t(det, "baseImpExe",        _fmt2(0))
            _t(det, "montoIce",          _fmt2(0))
            _t(det, "montoIva",          _fmt2(monto_iva))
            _t(det, "valRetBien10",      _fmt2(0))
            _t(det, "valRetServ20",      _fmt2(0))
            _t(det, "valorRetBienes",    _fmt2(0))
            _t(det, "valRetServ50",      _fmt2(0))
            _t(det, "valorRetServicios", _fmt2(0))
            _t(det, "valRetServ100",     _fmt2(0))
            _t(det, "valorRetencionNc",  _fmt2(0))
            _t(det, "totbasesImpReemb",  _fmt2(0))

            pago_ext = SubElement(det, "pagoExterior")
            _t(pago_ext, "pagoLocExt",         "01")
            _t(pago_ext, "paisEfecPago",       "NA")
            _t(pago_ext, "aplicConvDobTrib",   "NA")
            _t(pago_ext, "pagExtSujRetNorLeg", "NA")

            # air — retenciones de renta cruzando con num_doc_sustento
            ret_renta_doc = []
            for r in retenciones:
                imp_list = (r.impuestos or {}).get("impuesto", [])
                if not isinstance(imp_list, list):
                    imp_list = [imp_list] if imp_list else []
                for imp in imp_list:
                    if not isinstance(imp, dict):
                        continue
                    if str(imp.get("codigo", "")) == "1":
                        num_sustento = str(imp.get("numDocSustento", "")).replace("-", "")
                        num_compra   = str(c.numero_doc or "").replace("-", "")
                        if num_sustento and num_compra and (num_sustento in num_compra or num_compra in num_sustento):
                            ret_renta_doc.append({
                                "codigo_retencion": str(imp.get("codigoRetencion", "332")),
                                "base_imponible":   float(imp.get("baseImponible", 0) or 0),
                                "porcentaje":       float(imp.get("porcentajeRetener", 0) or 0),
                                "valor_retenido":   float(imp.get("valorRetenido", 0) or 0),
                            })

            air_el = SubElement(det, "air")
            if ret_renta_doc:
                for item in ret_renta_doc:
                    det_air = SubElement(air_el, "detalleAir")
                    _t(det_air, "codRetAir",     item["codigo_retencion"])
                    _t(det_air, "baseImpAir",    _fmt2(item["base_imponible"]))
                    _t(det_air, "porcentajeAir", _fmt2(item["porcentaje"]))
                    _t(det_air, "valRetAir",     _fmt2(item["valor_retenido"]))
            else:
                det_air = SubElement(air_el, "detalleAir")
                _t(det_air, "codRetAir",     "332")
                _t(det_air, "baseImpAir",    _fmt2(0))
                _t(det_air, "porcentajeAir", _fmt2(0))
                _t(det_air, "valRetAir",     _fmt2(0))

    # ── VENTAS ──
    if ventas:
        ventas_el = SubElement(root, "ventas")
        for v in ventas:
            det = SubElement(ventas_el, "detalleVentas")

            impuestos = v.resumen_impuestos or []
            if not isinstance(impuestos, list):
                impuestos = [impuestos] if impuestos else []

            base_grav = sum(float(i.get("baseImponible", 0) or 0) for i in impuestos if float(i.get("tarifa", 0) or 0) > 0)
            base_0    = sum(float(i.get("baseImponible", 0) or 0) for i in impuestos if float(i.get("tarifa", 0) or 0) == 0)
            monto_iva = sum(float(i.get("valor", 0) or 0)         for i in impuestos if float(i.get("tarifa", 0) or 0) > 0)

            _t(det, "tpIdCliente",        v.tipo_id or "07")
            _t(det, "idCliente",          v.id_comprador or "9999999999999")
            _t(det, "parteRel",           "NO")
            _t(det, "tipoComprobante",    v.cod_doc or "01")
            _t(det, "tipoEm",             "E")
            _t(det, "numeroComprobantes", "1")
            _t(det, "baseNoGraIva",       _fmt2(0))
            _t(det, "baseImponible",      _fmt2(base_0))
            _t(det, "baseImpGrav",        _fmt2(base_grav))
            _t(det, "baseImpExe",         _fmt2(0))
            _t(det, "montoIce",           _fmt2(0))
            _t(det, "montoIva",           _fmt2(monto_iva))
            _t(det, "valorRetIva",        _fmt2(0))
            _t(det, "valorRetRenta",      _fmt2(0))

    xml_str   = minidom.parseString(tostring(root, encoding="unicode")).toprettyxml(indent="  ", encoding=None)
    xml_bytes = xml_str.encode("utf-8")

    nombre_xml = f"AT-{str(mes).zfill(2)}{anio}.xml"
    nombre_zip = f"AT-{str(mes).zfill(2)}{anio}-{emisor.ruc}.zip"

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(nombre_xml, xml_bytes)

    return {
        "zip_bytes":     buffer.getvalue(),
        "nombre_zip":    nombre_zip,
        "total_ventas":  len(ventas),
        "total_compras": len(compras),
    }