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
    """
    Parsea un XML autorizado por el SRI y devuelve los datos estructurados.

    Retorna:
    {
        "tipo_doc": "FAC",
        "cod_doc": "01",
        "clave_acceso": "...",
        "numero_doc": "001-001-000000001",
        "fecha_emision": "2026-01-15",
        "fecha_autorizacion": "2026-01-15T...",
        "ruc_proveedor": "...",
        "razon_social_proveedor": "...",
        "importe_total": 115.00,
        "items_detalle": [...],
        "impuestos_detalle": [...],
        "datos": {...},  # XML completo parseado
        "errores": [],
    }
    """
    errores = []

    try:
        doc = xmltodict.parse(xml_str, force_list=("detalle", "impuesto", "campoAdicional"))
    except Exception as e:
        return {"errores": [f"XML inválido: {str(e)}"]}

    # ── Detectar si es XML autorizado (con wrapper) o solo comprobante ────────
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

    # ── Detectar tipo de comprobante ──────────────────────────────────────────
    TIPO_MAP = {
        "factura":             ("FAC", "01"),
        "liquidacionCompra":   ("LIQ", "03"),
        "notaCredito":         ("NCR", "04"),
        "notaDebito":          ("NDB", "05"),
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
    trib         = comprobante.get("infoTributaria", {})
    clave_acceso = trib.get("claveAcceso", "")
    estab        = trib.get("estab", "001")
    pto_emi      = trib.get("ptoEmi", "001")
    secuencial   = trib.get("secuencial", "000000000")
    numero_doc   = f"{estab}-{pto_emi}-{secuencial}"
    ruc_proveedor         = trib.get("ruc", "")
    razon_social_proveedor = trib.get("razonSocial", "")

    # ── Info del comprobante según tipo ───────────────────────────────────────
    info = (
        comprobante.get("infoFactura") or
        comprobante.get("infoLiquidacionCompra") or
        comprobante.get("infoNotaCredito") or
        comprobante.get("infoNotaDebito") or
        {}
    )

    fecha_emision  = _parse_fecha(info.get("fechaEmision"))
    importe_total  = float(info.get("importeTotal") or info.get("valorTotal") or 0)

    # ── Ítems ─────────────────────────────────────────────────────────────────
    detalles_raw = _to_array(
        comprobante.get("detalles", {}).get("detalle") or
        comprobante.get("motivos", {}).get("motivo")
    )

    items_detalle = []
    for det in detalles_raw:
        descripcion    = det.get("descripcion", "")
        cantidad       = float(det.get("cantidad", 1))
        precio_unit    = float(det.get("precioUnitario") or det.get("precioUnitario") or 0)
        descuento      = float(det.get("descuento", 0))
        subtotal       = float(det.get("precioTotalSinImpuesto") or 0)

        # NDB usa "razon" y "valor" en vez de detalle
        if not descripcion and det.get("razon"):
            descripcion = det.get("razon", "")
            subtotal    = float(det.get("valor", 0))
            cantidad    = 1
            precio_unit = subtotal

        # Impuestos del ítem
        impuestos_item = _to_array(det.get("impuestos", {}).get("impuesto"))
        tarifa_iva  = 0.0
        valor_iva   = 0.0

        for imp in impuestos_item:
            if str(imp.get("codigo", "")) == "2":  # IVA
                tarifa_iva = float(imp.get("tarifa", 0))
                valor_iva  = float(imp.get("valor", 0))
                break

        total = round(subtotal + valor_iva, 2)

        # Clasificación automática inicial
        tiene_iva = tarifa_iva > 0

        items_detalle.append({
            "descripcion":            descripcion,
            "cantidad":               cantidad,
            "precio_unitario":        round(precio_unit, 4),
            "descuento":              round(descuento, 2),
            "subtotal":               round(subtotal, 2),
            "tarifa_iva":             tarifa_iva,
            "valor_iva":              round(valor_iva, 2),
            "total":                  total,
            "deducible_renta":        True,   # ← usuario puede cambiar
            "credito_tributario_iva": tiene_iva,  # ← true si tiene IVA
        })

    # ── Impuestos totales por tarifa ──────────────────────────────────────────
    impuestos_totales_raw = _to_array(
        info.get("totalConImpuestos", {}).get("totalImpuesto")
    )

    impuestos_detalle = []
    for imp in impuestos_totales_raw:
        if str(imp.get("codigo", "")) == "2":  # Solo IVA
            tarifa       = float(imp.get("tarifa", 0))
            base         = float(imp.get("baseImponible", 0))
            valor        = float(imp.get("valor", 0))
            tiene_credito = tarifa > 0

            impuestos_detalle.append({
                "tarifa":                 tarifa,
                "baseImponible":          round(base, 2),
                "valor":                  round(valor, 2),
                "aplicaCredito":          tiene_credito,
            })

    # ── Resumen clasificación global ──────────────────────────────────────────
    deducible_renta        = True
    credito_tributario_iva = any(i["credito_tributario_iva"] for i in items_detalle)

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
        "impuestos_detalle":      impuestos_detalle,
        "deducible_renta":        deducible_renta,
        "credito_tributario_iva": credito_tributario_iva,
        "datos":                  comprobante,
        "errores":                errores,
    }