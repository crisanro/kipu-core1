# app/utils/calculadora.py

# Mapeo de códigos SRI actualizado al 2026
# Importante: El código 4 para 15% y 5 para 5% son los oficiales según ficha técnica
CODIGOS_IVA = {
    0:  {"codigo": "2", "codigoPorcentaje": "0"}, # 0%
    12: {"codigo": "2", "codigoPorcentaje": "2"}, # 12%
    15: {"codigo": "2", "codigoPorcentaje": "4"}, # 15% 
    5:  {"codigo": "2", "codigoPorcentaje": "5"}  # 5% (Construcción / Otros)
}

def calcular_totales_e_impuestos(items: list) -> dict:
    total_sin_impuestos = 0.0
    total_descuento = 0.0
    impuestos_acumulados = {}
    detalles_xml = []

    for item in items:
        # Extracción segura
        cantidad = float(item.get("cantidad", 0))
        precio_unitario = float(item.get("precioUnitario", item.get("precio", 0)))
        descuento = float(item.get("descuento", 0))

        # Precio Total del ítem (Base para el impuesto)
        # AJUSTE: Redondeo a 2 decimales en cada paso para evitar errores de coma flotante
        precio_total_sin_impuesto = round((cantidad * precio_unitario) - descuento, 2)
        
        total_sin_impuestos += precio_total_sin_impuesto
        total_descuento += descuento

        # --- LÓGICA DE TARIFA ---
        tarifa_raw = 0.0
        if "tarifaIva" in item:
            tarifa_raw = float(item["tarifaIva"])
        elif item.get("impuestos") and len(item["impuestos"]) > 0:
            tarifa_raw = float(item["impuestos"][0].get("tarifa", 0))

        # Normalización (0.15 -> 15)
        tarifa = (tarifa_raw * 100) if (0 < tarifa_raw < 1) else tarifa_raw
        tarifa_int = int(round(tarifa)) # Redondeo al entero más cercano por si viene 14.99

        info_sri = CODIGOS_IVA.get(tarifa_int, CODIGOS_IVA[0])
        
        # AJUSTE: El valor del impuesto se redondea a 2 decimales por ítem
        valor_impuesto = round(precio_total_sin_impuesto * (tarifa_int / 100.0), 2)

        # Acumular para el bloque <totalConImpuestos>
        if tarifa_int not in impuestos_acumulados:
            impuestos_acumulados[tarifa_int] = {
                "codigo": info_sri["codigo"],
                "codigoPorcentaje": info_sri["codigoPorcentaje"],
                "baseImponible": 0.0,
                "valor": 0.0,
                "tarifa": tarifa_int
            }
        
        impuestos_acumulados[tarifa_int]["baseImponible"] = round(impuestos_acumulados[tarifa_int]["baseImponible"] + precio_total_sin_impuesto, 2)
        impuestos_acumulados[tarifa_int]["valor"] = round(impuestos_acumulados[tarifa_int]["valor"] + valor_impuesto, 2)

        # Detalle para el XML
        detalles_xml.append({
            "codigoPrincipal": str(item.get("codigoPrincipal", item.get("codigo", "S/C"))),
            "descripcion": item.get("descripcion", item.get("nombre", "PRODUCTO SIN NOMBRE")).strip().upper(),
            "cantidad": f"{cantidad:.2f}",
            "precioUnitario": f"{precio_unitario:.2f}",
            "descuento": f"{descuento:.2f}",
            "precioTotalSinImpuesto": f"{precio_total_sin_impuesto:.2f}",
            "impuestos": {
                "impuesto": {
                    "codigo": info_sri["codigo"],
                    "codigoPorcentaje": info_sri["codigoPorcentaje"],
                    "tarifa": str(tarifa_int),
                    "baseImponible": f"{precio_total_sin_impuesto:.2f}",
                    "valor": f"{valor_impuesto:.2f}"
                }
            }
        })

    # Totales Finales
    total_con_impuestos_xml = []
    subtotal_0 = 0.0
    subtotal_iva = 0.0
    total_iva_general = 0.0

    for imp in impuestos_acumulados.values():
        total_con_impuestos_xml.append({
            "codigo": imp["codigo"],
            "codigoPorcentaje": imp["codigoPorcentaje"],
            "baseImponible": f"{imp['baseImponible']:.2f}",
            "valor": f"{imp['valor']:.2f}"
        })
        total_iva_general += imp["valor"]
        
        if imp["tarifa"] == 0:
            subtotal_0 += imp["baseImponible"]
        else:
            subtotal_iva += imp["baseImponible"]

    # AJUSTE: El importe total final debe ser la suma de los redondeados
    importe_total = round(total_sin_impuestos + total_iva_general, 2)

    return {
        "detallesXml": detalles_xml,
        "totalConImpuestosXml": total_con_impuestos_xml,
        "totales": {
            "totalSinImpuestos": f"{total_sin_impuestos:.2f}",
            "totalDescuento": f"{total_descuento:.2f}",
            "importeTotal": f"{importe_total:.2f}",
            "totalIva": f"{total_iva_general:.2f}",
            "subtotal_0": f"{subtotal_0:.2f}",
            "subtotal_iva": f"{subtotal_iva:.2f}"
        }
    }