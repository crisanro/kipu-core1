# app/utils/calculadora.py
from decimal import Decimal, ROUND_HALF_UP

# Mapeo de códigos SRI actualizado al 2026
CODIGOS_IVA = {
    0:  {"codigo": "2", "codigoPorcentaje": "0"},
    5:  {"codigo": "2", "codigoPorcentaje": "5"},
    8:  {"codigo": "2", "codigoPorcentaje": "8"},   # por si acaso
    12: {"codigo": "2", "codigoPorcentaje": "2"},
    15: {"codigo": "2", "codigoPorcentaje": "4"},
}

def r2(valor) -> Decimal:
    """Redondea a 2 decimales con ROUND_HALF_UP — estándar SRI."""
    return Decimal(str(valor)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

def calcular_totales_e_impuestos(items: list) -> dict:
    total_sin_impuestos   = Decimal('0.00')
    total_descuento       = Decimal('0.00')
    impuestos_acumulados  = {}
    detalles_xml          = []

    for item in items:
        cantidad        = r2(item.get("cantidad", 0))
        precio_unitario = r2(item.get("precio_unitario", item.get("precioUnitario", item.get("precio", 0))))
        descuento       = r2(item.get("descuento", 0))  # siempre en dólares

        # Subtotal del ítem antes de impuestos
        subtotal_item              = r2(cantidad * precio_unitario)
        precio_total_sin_impuesto  = r2(subtotal_item - descuento)

        total_sin_impuestos += precio_total_sin_impuesto
        total_descuento     += descuento

        # Tarifa IVA
        tarifa_raw = Decimal('0')
        if "tipo_iva" in item:
            tarifa_raw = Decimal(str(item["tipo_iva"]))
        elif "tarifaIva" in item:
            tarifa_raw = Decimal(str(item["tarifaIva"]))
        elif item.get("impuestos") and len(item["impuestos"]) > 0:
            tarifa_raw = Decimal(str(item["impuestos"][0].get("tarifa", 0)))

        # Normalizar (0.15 → 15)
        if Decimal('0') < tarifa_raw < Decimal('1'):
            tarifa_raw = tarifa_raw * Decimal('100')

        tarifa_int = int(tarifa_raw.quantize(Decimal('1'), rounding=ROUND_HALF_UP))
        info_sri   = CODIGOS_IVA.get(tarifa_int, CODIGOS_IVA[0])

        # IVA del ítem — redondeado a 2 decimales
        valor_impuesto = r2(precio_total_sin_impuesto * Decimal(str(tarifa_int)) / Decimal('100'))

        # Acumular por tarifa
        if tarifa_int not in impuestos_acumulados:
            impuestos_acumulados[tarifa_int] = {
                "codigo":            info_sri["codigo"],
                "codigoPorcentaje":  info_sri["codigoPorcentaje"],
                "baseImponible":     Decimal('0.00'),
                "valor":             Decimal('0.00'),
                "tarifa":            tarifa_int
            }

        impuestos_acumulados[tarifa_int]["baseImponible"] = r2(
            impuestos_acumulados[tarifa_int]["baseImponible"] + precio_total_sin_impuesto
        )
        impuestos_acumulados[tarifa_int]["valor"] = r2(
            impuestos_acumulados[tarifa_int]["valor"] + valor_impuesto
        )

        # Detalle XML
        detalles_xml.append({
            "codigoPrincipal":        str(item.get("codigoPrincipal", item.get("codigo", "S/C"))),
            "descripcion":            item.get("descripcion", item.get("nombre", "PRODUCTO SIN NOMBRE")).strip().upper(),
            "cantidad":               f"{cantidad:.6f}",
            "precioUnitario":         f"{precio_unitario:.6f}",
            "descuento":              f"{descuento:.2f}",
            "precioTotalSinImpuesto": f"{precio_total_sin_impuesto:.2f}",
            "impuestos": {
                "impuesto": {
                    "codigo":            info_sri["codigo"],
                    "codigoPorcentaje":  info_sri["codigoPorcentaje"],
                    "tarifa":            str(tarifa_int),
                    "baseImponible":     f"{precio_total_sin_impuesto:.2f}",
                    "valor":             f"{valor_impuesto:.2f}"
                }
            }
        })

    # Totales finales
    total_con_impuestos_xml = []
    subtotal_0              = Decimal('0.00')
    subtotal_iva            = Decimal('0.00')
    total_iva_general       = Decimal('0.00')

    for imp in impuestos_acumulados.values():
        total_con_impuestos_xml.append({
            "codigo":               imp["codigo"],
            "codigoPorcentaje":     imp["codigoPorcentaje"],
            "baseImponible":        f"{imp['baseImponible']:.2f}",
            "valor":                f"{imp['valor']:.2f}",
        })
        total_iva_general += imp["valor"]

        if imp["tarifa"] == 0:
            subtotal_0   += imp["baseImponible"]
        else:
            subtotal_iva += imp["baseImponible"]

    importe_total = r2(total_sin_impuestos + total_iva_general)

    return {
        "detallesXml":          detalles_xml,
        "totalConImpuestosXml": total_con_impuestos_xml,  # va al XML — sin tarifa
        "resumenImpuestos":     [                          # solo para DB/frontend
            {
                "tarifa":       str(imp["tarifa"]),
                "baseImponible": f"{imp['baseImponible']:.2f}",
                "valor":        f"{imp['valor']:.2f}",
            }
            for imp in impuestos_acumulados.values()
        ],
        "totales": {
            "totalSinImpuestos": f"{total_sin_impuestos:.2f}",
            "totalDescuento":    f"{total_descuento:.2f}",
            "importeTotal":      f"{importe_total:.2f}",
            "totalIva":          f"{total_iva_general:.2f}",
            "subtotal_0":        f"{subtotal_0:.2f}",
            "subtotal_iva":      f"{subtotal_iva:.2f}"
        }
    }