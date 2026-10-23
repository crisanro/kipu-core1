# app/services/documentos/xml_builder.py
#
# Bloque 3 — Construir XML según tipo de documento.

from datetime import datetime
from decimal import Decimal
from fastapi import HTTPException
from app.utils.sri_core import resolver_pagos, construir_campos_adicionales
from .helpers import TZ_EC, toArray_py, tarifa_a_codigo_porcentaje, adaptar_detalles_nc


async def construir_xml(
    tipo_doc, tipo_info, data, emisor, punto_emision,
    cliente_final, calculos, clave_acceso, secuencial,
    fecha_sri, nombre_comercial, direccion_est,
    doc_origen_emitido, doc_origen_recibido, importe_total,
    ambiente_efectivo: int = None,
) -> dict:

    info_tributaria = {
        "ambiente":        ambiente_efectivo or emisor.ambiente,
        "tipoEmision":     "1",
        "razonSocial":      emisor.razon_social,
        "nombreComercial": nombre_comercial,
        "ruc":             emisor.ruc,
        "claveAcceso":     clave_acceso,
        "codDoc":          tipo_info["cod_doc"],
        "estab":           punto_emision.estab_codigo,
        "ptoEmi":          punto_emision.punto_codigo,
        "secuencial":      secuencial,
        "dirMatriz":       emisor.direccion_matriz,
    }

    # ══ Leyendas SRI — Ficha Técnica v2.34 ══════════════════════════════════
    if getattr(emisor, "agente_retencion", None):
        info_tributaria["agenteRetencion"] = emisor.agente_retencion
    if getattr(emisor, "regimen_rimpe", None):
        info_tributaria["contribuyenteRimpe"] = emisor.regimen_rimpe

    # ══ Campos adicionales (infoAdicional) ══════════════════════════════════
    campos_adicionales = construir_campos_adicionales(data)
    if getattr(emisor, "gran_contribuyente_resolucion", None):
        campos_adicionales.insert(-1, {
            "@nombre": "Gran Contribuyente",
            "#text":   emisor.gran_contribuyente_resolucion,
        })

    builders = {
        "FAC": _build_factura,
        "LIQ": _build_liquidacion,
        "NCR": _build_nota_credito,
        "NDB": _build_nota_debito,
        "RET": _build_retencion,
    }
    builder = builders[tipo_doc]
    return builder(
        tipo_info=tipo_info,
        data=data,
        emisor=emisor,
        punto_emision=punto_emision,
        cliente_final=cliente_final,
        calculos=calculos,
        info_tributaria=info_tributaria,
        campos_adicionales=campos_adicionales,
        fecha_sri=fecha_sri,
        direccion_est=direccion_est,
        doc_origen_emitido=doc_origen_emitido,
        doc_origen_recibido=doc_origen_recibido,
        importe_total=importe_total,
    )


# ─── FAC ──────────────────────────────────────────────────────────────────────
def _build_factura(*, tipo_info, data, emisor, cliente_final, calculos,
                   info_tributaria, campos_adicionales, fecha_sri,
                   direccion_est, importe_total, **_):
    propina   = Decimal(str(data.get("propina", 0) or 0)).quantize(Decimal("0.01"))
    pagos_xml = resolver_pagos(data.get("pagos", []), importe_total)

    info_fac = {
        "fechaEmision":                fecha_sri,
        "dirEstablecimiento":          direccion_est,
        **({"contribuyenteEspecial": emisor.contribuyente_especial} if emisor.contribuyente_especial else {}),
        "obligadoContabilidad":        getattr(emisor, "obligado_contabilidad", "NO"),
        "tipoIdentificacionComprador": cliente_final["tipo_id"],
        "razonSocialComprador":        cliente_final["razon_social"],
        "identificacionComprador":     cliente_final["identificacion"],
        "totalSinImpuestos":           calculos["totales"]["totalSinImpuestos"],
        "totalDescuento":              calculos["totales"]["totalDescuento"],
        "totalConImpuestos":           {"totalImpuesto": calculos["totalConImpuestosXml"]},
        "propina":                      f"{propina:.2f}",
        "importeTotal":                f"{importe_total:.2f}",
        "moneda":                      "DOLAR",
        "pagos":                       {"pago": pagos_xml},
    }

    return {
        "factura": {
            "@id":            "comprobante",
            "@version":        tipo_info["xml_version"],
            "infoTributaria": info_tributaria,
            "infoFactura":    info_fac,
            "detalles":       {"detalle": calculos["detallesXml"]},
            "infoAdicional":  {"campoAdicional": campos_adicionales},
        }
    }


# ─── LIQ ──────────────────────────────────────────────────────────────────────
def _build_liquidacion(*, tipo_info, data, emisor, cliente_final, calculos,
                       info_tributaria, campos_adicionales, fecha_sri,
                       direccion_est, importe_total, **_):
    pagos_xml = resolver_pagos(data.get("pagos", []), importe_total)

    info_liq = {
        "fechaEmision":                 fecha_sri,
        "dirEstablecimiento":           direccion_est,
        **({"contribuyenteEspecial": emisor.contribuyente_especial} if emisor.contribuyente_especial else {}),
        "obligadoContabilidad":         getattr(emisor, "obligado_contabilidad", "NO"),
        "tipoIdentificacionProveedor":  cliente_final["tipo_id"],
        "razonSocialProveedor":         cliente_final["razon_social"],
        "identificacionProveedor":      cliente_final["identificacion"],
        "direccionProveedor":           cliente_final.get("direccion", "S/N"),
        "totalSinImpuestos":            calculos["totales"]["totalSinImpuestos"],
        "totalDescuento":               calculos["totales"]["totalDescuento"],
        "totalConImpuestos":            {"totalImpuesto": calculos["totalConImpuestosXml"]},
        "importeTotal":                 f"{importe_total:.2f}",
        "moneda":                       "DOLAR",
        "pagos":                        {"pago": pagos_xml},
    }

    return {
        "liquidacionCompra": {
            "@id":                   "comprobante",
            "@version":               tipo_info["xml_version"],
            "infoTributaria":        info_tributaria,
            "infoLiquidacionCompra": info_liq,
            "detalles":              {"detalle": calculos["detallesXml"]},
            "infoAdicional":         {"campoAdicional": campos_adicionales},
        }
    }


# ─── NCR ──────────────────────────────────────────────────────────────────────
def _build_nota_credito(*, tipo_info, data, emisor, cliente_final, calculos,
                        info_tributaria, campos_adicionales, fecha_sri,
                        direccion_est, doc_origen_emitido, **_):
    motivo = data.get("motivo", "OTROS").strip().upper()
    if not motivo:
        motivo = "OTROS"

    datos_origen = doc_origen_emitido.datos or {}
    info_origen  = datos_origen.get("infoFactura") or datos_origen.get("infoLiquidacionCompra") or {}
    fecha_origen = doc_origen_emitido.fecha_emision.strftime("%d/%m/%Y")
    detalles_nc  = adaptar_detalles_nc(calculos["detallesXml"])

    info_nc = {
        "fechaEmision":                fecha_sri,
        "dirEstablecimiento":          direccion_est,
        "tipoIdentificacionComprador": cliente_final["tipo_id"],
        "razonSocialComprador":        cliente_final["razon_social"],
        "identificacionComprador":     cliente_final["identificacion"],
        **({"contribuyenteEspecial": emisor.contribuyente_especial} if emisor.contribuyente_especial else {}),
        "obligadoContabilidad":        info_origen.get("obligadoContabilidad", "NO"),
        "codDocModificado":            doc_origen_emitido.cod_doc,
        "numDocModificado":            doc_origen_emitido.numero_doc,
        "fechaEmisionDocSustento":     fecha_origen,
        "totalSinImpuestos":           calculos["totales"]["totalSinImpuestos"],
        "valorModificacion":           calculos["totales"]["importeTotal"],
        "totalConImpuestos":           {"totalImpuesto": calculos["totalConImpuestosXml"]},
        "motivo":                      motivo,
    }

    return {
        "notaCredito": {
            "@id":              "comprobante",
            "@version":        tipo_info["xml_version"],
            "infoTributaria":  info_tributaria,
            "infoNotaCredito": info_nc,
            "detalles":        {"detalle": detalles_nc},
            "infoAdicional":   {"campoAdicional": campos_adicionales},
        }
    }


# ─── NDB ──────────────────────────────────────────────────────────────────────
def _build_nota_debito(*, tipo_info, data, emisor, cliente_final,
                       info_tributaria, campos_adicionales, fecha_sri,
                       direccion_est, doc_origen_emitido, importe_total, **_):
    motivos_raw = data.get("motivos", [])
    if not motivos_raw:
        raise HTTPException(status_code=400, detail="Se requiere al menos un motivo.")

    datos_origen = doc_origen_emitido.datos or {}
    info_origen  = datos_origen.get("infoFactura") or datos_origen.get("infoLiquidacionCompra") or {}
    fecha_origen = doc_origen_emitido.fecha_emision.strftime("%d/%m/%Y")

    total_ndb = sum(Decimal(str(m.get("valor", 0))) for m in motivos_raw)

    motivos_xml = [
        {
            "razon": m.get("razon", ""),
            "valor": f"{Decimal(str(m.get('valor', 0))):.2f}",
        }
        for m in motivos_raw
    ]

    impuestos_ndb_raw = data.get("impuestos", [])
    if impuestos_ndb_raw:
        impuestos_ndb_xml = [
            {
                "codigo":           str(i.get("codigo", "2")),
                "codigoPorcentaje": str(i.get("codigoPorcentaje", "4")),
                "tarifa":           str(i.get("tarifa", "15")),
                "baseImponible":    f"{Decimal(str(i.get('baseImponible', 0))):.2f}",
                "valor":            f"{Decimal(str(i.get('valor', 0))):.2f}",
            }
            for i in impuestos_ndb_raw
        ]
    else:
        impuestos_ndb_xml = [{
            "codigo":           "2",
            "codigoPorcentaje": "0",
            "tarifa":           "0",
            "baseImponible":    f"{total_ndb:.2f}",
            "valor":            "0.00",
        }]

    total_iva_ndb = sum(Decimal(str(i.get('valor', 0))) for i in impuestos_ndb_raw) if impuestos_ndb_raw else Decimal('0')
    valor_total_ndb = total_ndb + total_iva_ndb

    pagos_xml = resolver_pagos(data.get("pagos", []), valor_total_ndb)

    info_ndb = {
        "fechaEmision":                fecha_sri,
        "dirEstablecimiento":          direccion_est,
        "tipoIdentificacionComprador": cliente_final["tipo_id"],
        "razonSocialComprador":        cliente_final["razon_social"],
        "identificacionComprador":     cliente_final["identificacion"],
        **({"contribuyenteEspecial": emisor.contribuyente_especial} if emisor.contribuyente_especial else {}),
        "obligadoContabilidad":        info_origen.get("obligadoContabilidad", "NO"),
        "codDocModificado":            doc_origen_emitido.cod_doc,
        "numDocModificado":            doc_origen_emitido.numero_doc,
        "fechaEmisionDocSustento":     fecha_origen,
        "totalSinImpuestos":           f"{total_ndb:.2f}",
        "impuestos":                   {"impuesto": impuestos_ndb_xml},
        "valorTotal":                  f"{valor_total_ndb:.2f}",
        "pagos":                       {"pago": pagos_xml},
    }

    return {
        "notaDebito": {
            "@id":            "comprobante",
            "@version":        tipo_info["xml_version"],
            "infoTributaria": info_tributaria,
            "infoNotaDebito": info_ndb,
            "motivos":        {"motivo": motivos_xml},
            "infoAdicional":  {"campoAdicional": campos_adicionales},
        }
    }


# ─── RET v2.0.0 ──────────────────────────────────────────────────────────────
def _build_retencion(*, tipo_info, data, emisor, cliente_final,
                     info_tributaria, campos_adicionales, fecha_sri,
                     direccion_est, doc_origen_emitido, doc_origen_recibido,
                     importe_total, **_):
    impuestos_ret = data.get("impuestos_ret") or data.get("impuestos") or []
    if not impuestos_ret:
        raise HTTPException(status_code=400, detail="Se requiere al menos un impuesto.")

    doc_ret = doc_origen_recibido or doc_origen_emitido
    if not doc_ret:
        raise HTTPException(status_code=400, detail="Se requiere documento origen para la retención.")

    fecha_origen = doc_ret.fecha_emision.strftime("%d/%m/%Y")

    # ── Datos del documento sustento ──────────────────────────────────
    cod_sustento      = data.get("cod_sustento", "01")
    pago_loc_ext      = data.get("pago_loc_ext", "01")
    forma_pago_sust   = data.get("forma_pago_sustento", "01")
    cod_doc_sustento  = str(getattr(doc_ret, "cod_doc", None) or "01")
    num_doc_sustento  = (getattr(doc_ret, "numero_doc", "") or "").replace("-", "").zfill(15)

    num_aut = data.get("num_aut_doc_sustento") or getattr(doc_ret, "clave_acceso", None) or ""

    total_sin_imp_sust = Decimal(str(
        data.get("total_sin_impuestos_sustento")
        or getattr(doc_ret, "subtotal_base", None)
        or 0
    ))
    importe_total_sust = Decimal(str(
        data.get("importe_total_sustento")
        or getattr(doc_ret, "importe_total", None)
        or 0
    ))

    # ── Impuestos del doc sustento ───────────────────────────────────
    imp_doc_sust_raw = data.get("impuestos_doc_sustento") or []

    if not imp_doc_sust_raw and hasattr(doc_ret, "datos") and doc_ret.datos:
        datos_origen = doc_ret.datos or {}
        resumen = datos_origen.get("resumenImpuestos", [])
        if not resumen:
            info_doc = (
                datos_origen.get("infoFactura")
                or datos_origen.get("infoLiquidacionCompra")
                or {}
            )
            total_imp = info_doc.get("totalConImpuestos", {}).get("totalImpuesto", [])
            resumen = toArray_py(total_imp)

        for imp in toArray_py(resumen):
            tarifa  = str(imp.get("tarifa", "0"))
            cod_pct = str(imp.get("codigoPorcentaje", "")) or tarifa_a_codigo_porcentaje(tarifa)
            imp_doc_sust_raw.append({
                "codImpuestoDocSustento": str(imp.get("codigo", "2")),
                "codigoPorcentaje":       cod_pct,
                "baseImponible":          str(imp.get("baseImponible", "0")),
                "tarifa":                 tarifa,
                "valorImpuesto":          str(imp.get("valor", "0")),
            })

        if total_sin_imp_sust == 0:
            info_doc = (
                datos_origen.get("infoFactura")
                or datos_origen.get("infoLiquidacionCompra")
                or {}
            )
            total_sin_imp_sust = Decimal(str(info_doc.get("totalSinImpuestos", 0)))
        if importe_total_sust == 0:
            info_doc = (
                datos_origen.get("infoFactura")
                or datos_origen.get("infoLiquidacionCompra")
                or {}
            )
            importe_total_sust = Decimal(str(info_doc.get("importeTotal", 0)))

    impuestos_doc_xml = [
        {
            "codImpuestoDocSustento": str(i.get("codImpuestoDocSustento", i.get("codigo", "2"))),
            "codigoPorcentaje":       str(i.get("codigoPorcentaje", "0")),
            "baseImponible":          f"{Decimal(str(i.get('baseImponible', 0))):.2f}",
            "tarifa":                 str(i.get("tarifa", "0")),
            "valorImpuesto":          f"{Decimal(str(i.get('valorImpuesto', i.get('valor', 0)))):.2f}",
        }
        for i in imp_doc_sust_raw
    ]

    # ── Retenciones ──────────────────────────────────────────────────
    retenciones_xml = [
        {
            "codigo":            str(i.get("codigo", "1")),
            "codigoRetencion":   str(i.get("codigoRetencion", "")),
            "baseImponible":     f"{Decimal(str(i.get('baseImponible', 0))):.2f}",
            "porcentajeRetener": str(i.get("porcentajeRetener", i.get("tarifa", ""))),
            "valorRetenido":     f"{Decimal(str(i.get('valorRetenido', i.get('valor', 0)))):.2f}",
        }
        for i in impuestos_ret
    ]

    # ── docSustento ──────────────────────────────────────────────────
    doc_sustento = {
        "codSustento":              cod_sustento,
        "codDocSustento":           cod_doc_sustento,
        **({"numDocSustento": num_doc_sustento} if num_doc_sustento.strip("0") else {}),
        "fechaEmisionDocSustento":  fecha_origen,
        **({"numAutDocSustento": num_aut} if num_aut else {}),
        "pagoLocExt":               pago_loc_ext,
        **({"tipoRegi":            data.get("tipo_regi", "01")}             if pago_loc_ext == "02" else {}),
        **({"paisEfecPago":        data.get("pais_efec_pago", "593")}       if pago_loc_ext == "02" else {}),
        **({"aplicConvDobTrib":    data.get("aplic_conv_dob_trib", "NO")}   if pago_loc_ext == "02" else {}),
        **({"pagExtSujRetNorLeg":  data.get("pag_ext_suj_ret_nor_leg", "SI")} if pago_loc_ext == "02" and data.get("aplic_conv_dob_trib", "NO") == "NO" else {}),
        **({"pagoRegFis":          data.get("pago_reg_fis", "NO")}          if pago_loc_ext == "02" else {}),
        "totalSinImpuestos":        f"{total_sin_imp_sust:.2f}",
        "importeTotal":             f"{importe_total_sust:.2f}",
        "impuestosDocSustento":     {"impuestoDocSustento": impuestos_doc_xml},
        "retenciones":              {"retencion": retenciones_xml},
        "pagos":                    {"pago": [{
            "formaPago": forma_pago_sust,
            "total":     f"{importe_total_sust:.2f}",
        }]},
    }

    # ── Info retención ───────────────────────────────────────────────
    info_ret = {
        "fechaEmision":                         fecha_sri,
        "dirEstablecimiento":                   direccion_est,
        **({"contribuyenteEspecial": emisor.contribuyente_especial} if emisor.contribuyente_especial else {}),
        "obligadoContabilidad":                 getattr(emisor, "obligado_contabilidad", "NO"),
        "tipoIdentificacionSujetoRetenido":     cliente_final["tipo_id"],
        **({"tipoSujetoRetenido": data.get("tipo_sujeto_retenido", "01")} if cliente_final["tipo_id"] == "08" else {}),
        "parteRel":                             data.get("parte_rel", "NO"),
        "razonSocialSujetoRetenido":            cliente_final["razon_social"],
        "identificacionSujetoRetenido":         cliente_final["identificacion"],
        "periodoFiscal":                        data.get("periodo_fiscal", datetime.now(TZ_EC).strftime("%m/%Y")),
    }

    return {
        "comprobanteRetencion": {
            "@id":               "comprobante",
            "@version":          "2.0.0",
            "infoTributaria":    info_tributaria,
            "infoCompRetencion": info_ret,
            "docsSustento":      {"docSustento": doc_sustento},
            "infoAdicional":     {"campoAdicional": campos_adicionales},
        }
    }