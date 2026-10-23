# app/services/documentos/helpers.py
#
# Constantes y utilidades compartidas por todos los módulos de emisión.

import pytz
from decimal import Decimal

TZ_EC = pytz.timezone("America/Guayaquil")

TIPO_DOC_MAP = {
    "FAC": {"cod_doc": "01", "xml_root": "factura",              "xml_version": "1.1.0"},
    "LIQ": {"cod_doc": "03", "xml_root": "liquidacionCompra",    "xml_version": "1.1.0"},
    "NCR": {"cod_doc": "04", "xml_root": "notaCredito",          "xml_version": "1.1.0"},
    "NDB": {"cod_doc": "05", "xml_root": "notaDebito",           "xml_version": "1.0.0"},
    "RET": {"cod_doc": "07", "xml_root": "comprobanteRetencion", "xml_version": "2.0.0"},
}

# Regla tributaria EC: >= $500 debe usar sistema financiero (no efectivo "01")
LIMITE_EFECTIVO = Decimal("500.00")
COD_EFECTIVO    = "01"

MOTIVOS_NCR_VALIDOS = [
    "DEVOLUCION DE BIEN",
    "ANULACION DE COMPROBANTE",
    "REBAJA DE PRECIO",
    "DESCUENTO COMERCIAL",
    "OTROS",
]


def carpeta_por_tipo(tipo_doc: str) -> str:
    return {
        "FAC": "facturas",
        "LIQ": "liquidaciones",
        "NCR": "notas_credito",
        "NDB": "notas_debito",
        "RET": "retenciones",
    }.get(tipo_doc, "documentos")


def preparar_items_desde_raw(items_raw: list) -> list:
    from fastapi import HTTPException

    resultado = []
    for item in items_raw:
        codigo_raw = item.get("codigo")
        resultado.append({
            "codigo":          str(codigo_raw) if codigo_raw and str(codigo_raw) != "None" else "S/C",
            "descripcion":     item.get("descripcion", ""),
            "cantidad":        float(item.get("cantidad", 1)),
            "precio_unitario": float(item.get("precio_unitario", 0)),
            "descuento":       float(item.get("descuento", 0)),
            "tipo_iva":        str(item.get("tipo_iva", "15")),
            "unidad_medida":   item.get("unidad_medida", "UNIDAD"),
        })
    if not resultado:
        raise HTTPException(status_code=400, detail="Se requiere al menos un ítem.")
    return resultado


def adaptar_detalles_nc(detalles_xml: list) -> list:
    resultado = []
    for det in detalles_xml:
        d      = dict(det)
        codigo = d.pop("codigoPrincipal", "S/C")
        det_nc = {}
        if codigo and codigo != "S/C":
            det_nc["codigoInterno"] = codigo
        det_nc["descripcion"]            = d.get("descripcion", "")
        det_nc["cantidad"]               = d.get("cantidad", "1.000000")
        det_nc["precioUnitario"]         = d.get("precioUnitario", "0.000000")
        det_nc["descuento"]              = d.get("descuento", "0.00")
        det_nc["precioTotalSinImpuesto"] = d.get("precioTotalSinImpuesto", "0.00")
        det_nc["impuestos"]              = d.get("impuestos", {})
        resultado.append(det_nc)
    return resultado


def tarifa_a_codigo_porcentaje(tarifa: str) -> str:
    """Convierte tarifa IVA a codigoPorcentaje según Tabla 17 ficha técnica."""
    MAPA = {
        "0":  "0",
        "5":  "5",
        "12": "2",
        "13": "10",
        "14": "3",
        "15": "4",
    }
    return MAPA.get(str(tarifa).split(".")[0], "0")


def toArray_py(v):
    """Normaliza a lista — equivalente al toArray de helpers.js"""
    if not v:
        return []
    return v if isinstance(v, list) else [v]