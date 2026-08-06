# app/utils/factura_service.py
import json
from datetime import datetime
from decimal import Decimal
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from app.utils.calculadora import calcular_totales_e_impuestos
from app.utils.crypto import generar_clave_acceso
from app.utils.sri_core import (
    resolver_cliente,
    completar_items_catalogo,
    resolver_pagos,
    construir_campos_adicionales,
    firmar_xml,
    guardar_y_encolar,
)
from app.core.config import settings
import pytz


async def emitir_factura_core(
    factura_data: dict,
    emisor_id:    int,
    db:           AsyncSession,
    api_key_id:   int  = None,
    unlimited:    bool = False,
) -> dict:

    if not factura_data.get("establecimiento") or not factura_data.get("punto_emision"):
        raise HTTPException(status_code=400, detail="Los campos 'establecimiento' y 'punto_emision' son requeridos.")

    # ─────────────────────────────────────────────────────────────
    # BLOQUE 0: Cliente
    # ─────────────────────────────────────────────────────────────
    cliente_final, cliente_emisor_id = await resolver_cliente(factura_data, emisor_id, db)

    # ─────────────────────────────────────────────────────────────
    # BLOQUE 1: Datos base
    # ─────────────────────────────────────────────────────────────
    try:
        # Emisor + créditos
        res_emisor = await db.execute(text("""
            SELECT e.*, c.balance_emision
            FROM emisores e JOIN user_credits c ON e.id = c.emisor_id
            WHERE e.id = :eid FOR UPDATE
        """), {"eid": emisor_id})
        emisor = res_emisor.fetchone()

        if not unlimited and (not emisor or emisor.balance_emision <= 0):
            raise HTTPException(status_code=402, detail="Créditos insuficientes.")

        # Establecimiento y punto
        res_pto = await db.execute(text("""
            SELECT p.id as punto_id, p.codigo as punto_codigo,
                   e.codigo as estab_codigo,
                   e.direccion as direccion_establecimiento,
                   e.nombre_comercial as nombre_establecimiento
            FROM puntos_emision p
            JOIN establecimientos e ON p.establecimiento_id = e.id
            WHERE e.codigo = :estab AND p.codigo = :pto AND e.emisor_id = :eid
        """), {
            "estab": str(factura_data["establecimiento"]).zfill(3),
            "pto":   str(factura_data["punto_emision"]).zfill(3),
            "eid":   emisor_id,
        })
        punto_emision = res_pto.fetchone()
        if not punto_emision:
            raise HTTPException(status_code=404, detail="Establecimiento y Punto no existen o no te pertenecen.")

        # Secuencial
        res_sec = await db.execute(text("""
            UPDATE puntos_emision SET secuencial_actual = secuencial_actual + 1
            WHERE id = :pto_id RETURNING secuencial_actual
        """), {"pto_id": punto_emision.punto_id})
        secuencial = str(res_sec.scalar()).zfill(9)

        # Fecha Ecuador
        tz            = pytz.timezone("America/Guayaquil")
        ahora_ecuador = datetime.now(tz)
        fecha_clave   = ahora_ecuador.strftime("%Y-%m-%d")
        fecha_sri     = ahora_ecuador.strftime("%d/%m/%Y")

        # Completar items desde catálogo
        items_raw      = factura_data.get("items", [])
        items_completos = await completar_items_catalogo(items_raw, emisor_id, db)

        # Calcular totales
        calculos = calcular_totales_e_impuestos(items_completos)

        # Validación consumidor final
        if cliente_final["tipo_id"] == "07":
            importe = float(calculos["totales"]["importeTotal"])
            if importe > 50.00:
                raise HTTPException(
                    status_code=400,
                    detail=f"Las facturas a Consumidor Final no pueden superar $50.00 (total: ${importe:.2f})."
                )

        # Clave de acceso
        clave_acceso = generar_clave_acceso(
            fecha=fecha_clave,
            tipo_comprobante="01",
            ruc=emisor.ruc,
            ambiente=emisor.ambiente,
            serie=f"{punto_emision.estab_codigo}{punto_emision.punto_codigo}",
            secuencial=secuencial,
        )

        # Resolver pagos
        importe_total = Decimal(str(calculos["totales"]["importeTotal"]))
        pagos_xml     = resolver_pagos(factura_data.get("pagos", []), importe_total)
        propina_valor = Decimal(str(factura_data.get("propina", 0) or 0)).quantize(Decimal("0.01"))


        # Datos del establecimiento
        nombre_comercial = punto_emision.nombre_establecimiento or emisor.nombre_comercial or emisor.razon_social
        direccion_est    = punto_emision.direccion_establecimiento or emisor.direccion_matriz

        # XML de la factura
        xml_obj = {
            "factura": {
                "@id":      "comprobante",
                "@version": "1.1.0",
                "infoTributaria": {
                    "ambiente":       emisor.ambiente,
                    "tipoEmision":    "1",
                    "razonSocial":    emisor.razon_social,
                    "nombreComercial": nombre_comercial,
                    "ruc":            emisor.ruc,
                    "claveAcceso":    clave_acceso,
                    "codDoc":         "01",
                    "estab":          punto_emision.estab_codigo,
                    "ptoEmi":         punto_emision.punto_codigo,
                    "secuencial":     secuencial,
                    "dirMatriz":      emisor.direccion_matriz,
                },
                "infoFactura": {
                    "fechaEmision":                fecha_sri,
                    "dirEstablecimiento":          direccion_est,
                    "obligadoContabilidad":        getattr(emisor, "obligado_contabilidad", "NO"),
                    "tipoIdentificacionComprador": cliente_final["tipo_id"],
                    "razonSocialComprador":        cliente_final["razon_social"],
                    "identificacionComprador":     cliente_final["identificacion"],
                    "totalSinImpuestos":           calculos["totales"]["totalSinImpuestos"],
                    "totalDescuento":              calculos["totales"]["totalDescuento"],
                    "totalConImpuestos":           {"totalImpuesto": calculos["totalConImpuestosXml"]},
                    "propina":                     f"{propina_valor:.2f}",
                    "importeTotal":                f"{(importe_total + propina_valor):.2f}",
                    "moneda":                      "DOLAR",
                    "pagos":                       {"pago": pagos_xml},
                },
                "detalles": {"detalle": calculos["detallesXml"]},
                "infoAdicional": {
                    "campoAdicional": construir_campos_adicionales(factura_data)
                },
            }
        }

        await db.commit()

    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error generando factura: {str(e)}")

    # ─────────────────────────────────────────────────────────────
    # BLOQUE 2: Firma
    # ─────────────────────────────────────────────────────────────
    xml_firmado_str = await firmar_xml(xml_obj, emisor)

    # ─────────────────────────────────────────────────────────────
    # BLOQUE 3: Guardar y encolar
    # ─────────────────────────────────────────────────────────────
    xml_path_rel = f"{emisor.ruc}/facturas/{clave_acceso}.xml"
    origen       = "api" if api_key_id else factura_data.get("origen", "web")

    datos_fac_json = {
        **xml_obj["factura"],
        "resumenImpuestos": calculos["resumenImpuestos"],
    }

    factura_id = await guardar_y_encolar(
        xml_firmado_str   = xml_firmado_str,
        xml_path_rel      = xml_path_rel,
        datos_fac_json    = datos_fac_json,
        calculos          = calculos,
        emisor_id         = emisor_id,
        punto_emision     = punto_emision,
        cliente_final     = cliente_final,
        cliente_emisor_id = cliente_emisor_id,
        secuencial        = secuencial,
        clave_acceso      = clave_acceso,
        ahora_ecuador     = ahora_ecuador,
        api_key_id        = api_key_id,
        unlimited         = unlimited,
        origen            = origen,
        db                = db,
    )

    return {
        "ok":          True,
        "id":          factura_id,
        "claveAcceso": clave_acceso,
        "estado":      "FIRMADO",
        "mensaje":     "Factura en proceso de autorización.",
    }