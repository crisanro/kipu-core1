# app/utils/xml_parser_recibidos.py
#
# Parser de XML SRI para documentos recibidos.
# Extrae ítems, impuestos y datos del proveedor.

import xmltodict
from decimal import Decimal
from datetime import datetime


def _to_array(val) -> list:
    """Normaliza a lista — el parser devuelve dict si hay 1 elemento."""
    if not val:
        return []
    return val if isinstance(val, list) else [val]


def _parse_fecha(fecha_str: str | None) -> str | None:
    """Convierte dd/mm/yyyy → yyyy-mm-dd."""
    if not fecha_str:
        return None
    try:
        return datetime.strptime(fecha_str.strip(), "%d/%m/%Y").strftime("%Y-%m-%d")
    except ValueError:
        return fecha_str


def parsear_xml_recibido(xml_str: str) -> dict:
    errores = []
    try:
        doc = xmltodict.parse(xml_str, force_list=("detalle", "impuesto", "campoAdicional"))
    except Exception as e:
        return {"errores": [f"XML inválido: {str(e)}"]}

    datos = doc
    fecha_autorizacion = None
    if "autorizacion" in doc:
        auth = doc["autorizacion"]
        fecha_autorizacion = auth.get("fechaAutorizacion")
        try:
            comprobante_str = auth.get("comprobante", "")
            datos = xmltodict.parse(
                comprobante_str,
                force_list=("detalle", "impuesto", "campoAdicional")
            )
        except Exception:
            errores.append("No se pudo parsear el comprobante interno.")

    # ── Detectar tipo ─────────────────────────────────────────────────────────
    TIPO_MAP = {
        "factura":              ("FAC", "01"),
        "liquidacionCompra":    ("LIQ", "03"),
        "notaCredito":          ("NCR", "04"),
        "notaDebito":           ("NDB", "05"),
        "comprobanteRetencion": ("RET", "07"),
    }

    tipo_doc = cod_doc = None
    comprobante = None
    for tag, (tipo, cod) in TIPO_MAP.items():
        if tag in datos:
            tipo_doc    = tipo
            cod_doc     = cod
            comprobante = datos[tag]
            break

    if not comprobante:
        return {"errores": ["No se reconoce el tipo de comprobante."]}

    # ── Info tributaria ───────────────────────────────────────────────────────
    trib                   = comprobante.get("infoTributaria", {})
    clave_acceso           = trib.get("claveAcceso", "")
    estab                  = trib.get("estab", "001")
    pto_emi                = trib.get("ptoEmi", "001")
    secuencial             = trib.get("secuencial", "000000000")
    numero_doc             = f"{estab}-{pto_emi}-{secuencial}"
    ruc_proveedor          = trib.get("ruc", "")
    razon_social_proveedor = trib.get("razonSocial", "")

    # ── RET — flujo separado ──────────────────────────────────────────────────
    if tipo_doc == "RET":
        info_ret      = comprobante.get("infoCompRetencion", {})
        fecha_emision = _parse_fecha(info_ret.get("fechaEmision"))
        ruc_comprador = info_ret.get("identificacionSujetoRetenido", "")

        impuestos_raw = _to_array(
            comprobante.get("impuestos", {}).get("impuesto")
        )

        items_detalle   = []
        subtotal_base   = 0.0
        valor_iva_total = 0.0

        for imp in impuestos_raw:
            codigo            = str(imp.get("codigo", ""))
            codigo_retencion  = str(imp.get("codigoRetencion", ""))
            base              = float(imp.get("baseImponible",    0) or 0)
            porcentaje        = float(imp.get("porcentajeRetener", 0) or 0)
            retenido          = float(imp.get("valorRetenido",    0) or 0)
            cod_doc_sustento  = str(imp.get("codDocSustento",     "") or "")
            num_doc_sustento  = str(imp.get("numDocSustento",     "") or "")
            fecha_sustento    = _parse_fecha(imp.get("fechaEmisionDocSustento"))

            # Omitir líneas completamente vacías
            if retenido == 0 and base == 0:
                continue

            es_iva = codigo == "2"
            es_isd = codigo == "6"

            if es_iva:
                descripcion            = f"Retención IVA {porcentaje:.0f}%"
                credito_tributario_iva = True
                valor_iva_total       += retenido
            elif es_isd:
                descripcion            = f"Retención ISD {porcentaje:.2f}%"
                credito_tributario_iva = False
            else:  # codigo == "1" Renta
                descripcion            = f"Retención Renta {porcentaje:.2f}%"
                credito_tributario_iva = False

            subtotal_base += base

            items_detalle.append({
                "descripcion":            descripcion,
                "cantidad":               1,
                "precio_unitario":        round(base, 2),
                "descuento":              0.0,
                "subtotal":               round(base, 2),
                "tarifa_iva":             0.0,
                "valor_iva":              0.0,
                "total":                  round(retenido, 2),
                "deducible_renta":        False,
                "credito_tributario_iva": credito_tributario_iva,
                # Trazabilidad — a qué doc aplica esta retención
                "codigo_retencion":       codigo_retencion,
                "codigo_impuesto":        codigo,      # 1=Renta 2=IVA 6=ISD
                "porcentaje":             porcentaje,
                "cod_doc_sustento":       cod_doc_sustento,
                "num_doc_sustento":       num_doc_sustento,
                "fecha_doc_sustento":     str(fecha_sustento) if fecha_sustento else None,
            })

        return {
            "tipo_doc":               "RET",
            "cod_doc":                "07",
            "clave_acceso":           clave_acceso,
            "numero_doc":             numero_doc,
            "fecha_emision":          fecha_emision,
            "fecha_autorizacion":     fecha_autorizacion,
            "ruc_proveedor":          ruc_proveedor,
            "razon_social_proveedor": razon_social_proveedor,
            "importe_total":          round(valor_iva_total, 2),
            "items_detalle":          items_detalle,
            "deducible_renta":        False,
            "credito_tributario_iva": valor_iva_total > 0,
            "ruc_comprador":          ruc_comprador,
            "errores":                errores,
        }

    # ── FAC / LIQ / NCR / NDB ─────────────────────────────────────────────────
    info = (
        comprobante.get("infoFactura") or
        comprobante.get("infoLiquidacionCompra") or
        comprobante.get("infoNotaCredito") or
        comprobante.get("infoNotaDebito") or
        {}
    )
    fecha_emision = _parse_fecha(info.get("fechaEmision"))
    importe_total = float(info.get("importeTotal") or info.get("valorTotal") or 0)
    ruc_comprador = (
        info.get("identificacionComprador") or
        info.get("identificacionProveedor") or
        ""
    )

    # ── Ítems ─────────────────────────────────────────────────────────────────
    detalles_raw = _to_array(
        comprobante.get("detalles", {}).get("detalle") or
        comprobante.get("motivos", {}).get("motivo")
    )
    items_detalle = []
    for det in detalles_raw:
        descripcion = det.get("descripcion", "")
        cantidad    = float(det.get("cantidad", 1))
        precio_unit = float(det.get("precioUnitario") or 0)
        descuento   = float(det.get("descuento", 0))
        subtotal    = float(det.get("precioTotalSinImpuesto") or 0)

        # NDB usa razon/valor
        if not descripcion and det.get("razon"):
            descripcion = det.get("razon", "")
            subtotal    = float(det.get("valor", 0))
            cantidad    = 1
            precio_unit = subtotal

        impuestos_item = _to_array(det.get("impuestos", {}).get("impuesto"))
        tarifa_iva = 0.0
        valor_iva  = 0.0
        for imp in impuestos_item:
            if str(imp.get("codigo", "")) == "2":
                tarifa_iva = float(imp.get("tarifa", 0))
                valor_iva  = float(imp.get("valor",  0))
                break

        tiene_iva = tarifa_iva > 0
        items_detalle.append({
            "descripcion":            descripcion,
            "cantidad":               cantidad,
            "precio_unitario":        round(precio_unit, 4),
            "descuento":              round(descuento, 2),
            "subtotal":               round(subtotal, 2),
            "tarifa_iva":             tarifa_iva,
            "valor_iva":              round(valor_iva, 2),
            "total":                  round(subtotal + valor_iva, 2),
            "deducible_renta":        True,
            "credito_tributario_iva": tiene_iva,
        })

    return {
        "tipo_doc":               tipo_doc,
        "cod_doc":                cod_doc,
        "clave_acceso":           clave_acceso,
        "numero_doc":             numero_doc,
        "fecha_emision":          fecha_emision,
        "fecha_autorizacion":     fecha_autorizacion,
        "ruc_proveedor":          ruc_proveedor,
        "razon_social_proveedor": razon_social_proveedor,
        "importe_total":          importe_total,
        "items_detalle":          items_detalle,
        "deducible_renta":        True,
        "credito_tributario_iva": any(i["credito_tributario_iva"] for i in items_detalle),
        "ruc_comprador":          ruc_comprador,
        "errores":                errores,
    }