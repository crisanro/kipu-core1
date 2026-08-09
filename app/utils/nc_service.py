# app/utils/nc_service.py
import json
from datetime import datetime
from decimal import Decimal
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from app.utils.calculadora import calcular_totales_e_impuestos
from app.utils.crypto import generar_clave_acceso
from app.utils.sri_core import (
    construir_campos_adicionales,
    firmar_xml,
    guardar_y_encolar,
)
import pytz

MOTIVOS_VALIDOS = [
    "DEVOLUCION DE BIEN",
    "ANULACION DE COMPROBANTE",
    "REBAJA DE PRECIO",
    "DESCUENTO COMERCIAL",
    "OTROS",
]

async def emitir_nota_credito_core(
    nc_data:    dict,
    emisor_id:  int,
    db:         AsyncSession,
    api_key_id: int  = None,
    unlimited:  bool = False,
) -> dict:

    factura_id = nc_data.get("factura_id")
    motivo     = nc_data.get("motivo", "").strip().upper()
    items_raw  = nc_data.get("items", [])

    if not factura_id:
        raise HTTPException(status_code=400, detail="El campo 'factura_id' es requerido.")
    if not motivo:
        raise HTTPException(status_code=400, detail="El campo 'motivo' es requerido.")
    if not items_raw:
        raise HTTPException(status_code=400, detail="Debe incluir al menos un ítem.")

    try:
        # ─────────────────────────────────────────────────────────────
        # BLOQUE 0: Cargar factura original
        # ─────────────────────────────────────────────────────────────
        res_fac = await db.execute(text("""
            SELECT i.id, i.numero_factura, i.clave_acceso, i.fecha_emision,
                   i.identificacion_comprador, i.razon_social_comprador,
                   i.email_comprador, i.datos_factura,
                   i.punto_emision_id, i.cliente_emisor_id,
                   e.id as emisor_db_id, e.ruc, e.razon_social, e.nombre_comercial,
                   e.direccion_matriz, e.ambiente, e.p12_path, e.p12_pass,
                   e.obligado_contabilidad, e.contribuyente_especial,
                   c.balance_emision,
                   p.codigo as punto_codigo, p.secuencial_actual,
                   est.codigo as estab_codigo, est.direccion as direccion_est,
                   est.nombre_comercial as nombre_est
            FROM invoices_emitidas i
            JOIN emisores e ON i.emisor_id = e.id
            JOIN user_credits c ON e.id = c.emisor_id
            JOIN puntos_emision p ON i.punto_emision_id = p.id
            JOIN establecimientos est ON p.establecimiento_id = est.id
            WHERE i.id = :fid
              AND i.emisor_id = :eid
              AND i.estado = 'AUTORIZADO'
            FOR UPDATE
        """), {"fid": factura_id, "eid": emisor_id})
        factura = res_fac.fetchone()

        if not factura:
            raise HTTPException(
                status_code=404,
                detail="Factura no encontrada, no autorizada o no pertenece a este emisor."
            )
        if not unlimited and factura.balance_emision <= 0:
            raise HTTPException(status_code=402, detail="Créditos insuficientes.")

        # ─────────────────────────────────────────────────────────────
        # BLOQUE 1: Calcular totales y reservar secuencial (Transaccional)
        # ─────────────────────────────────────────────────────────────
        # Extraer datos de la factura original
        datos_fac    = factura.datos_factura or {}
        info_factura = datos_fac.get("infoFactura", {})
        tipo_id_comp = info_factura.get("tipoIdentificacionComprador", "05")
        obligado     = info_factura.get("obligadoContabilidad", "NO")

        # Completar items
        items_completos = []
        for item in items_raw:
            codigo_raw = item.get("codigo")
            items_completos.append({
                "codigo":          str(codigo_raw) if codigo_raw and str(codigo_raw) != "None" else "S/C",
                "descripcion":     item.get("descripcion", ""),
                "cantidad":        float(item.get("cantidad", 1)),
                "precio_unitario": float(item.get("precio_unitario", 0)),
                "descuento":        float(item.get("descuento", 0)),
                "tipo_iva":        str(item.get("tipo_iva", "15")),
                "unidad_medida":   item.get("unidad_medida", "UNIDAD"),
            })

        calculos = calcular_totales_e_impuestos(items_completos)

        # NC usa codigoInterno en vez de codigoPrincipal (Ficha técnica SRI para NC)
        detalles_nc = []
        for detalle in calculos["detallesXml"]:
            det = dict(detalle)
            codigo = det.pop("codigoPrincipal", "S/C")
            det_nc = {}
            if codigo and codigo != "S/C":
                det_nc["codigoInterno"] = codigo
            det_nc["descripcion"]            = det.get("descripcion", "")
            det_nc["cantidad"]               = det.get("cantidad", "1.000000")
            det_nc["precioUnitario"]         = det.get("precioUnitario", "0.000000")
            det_nc["descuento"]              = det.get("descuento", "0.00")
            det_nc["precioTotalSinImpuesto"] = det.get("precioTotalSinImpuesto", "0.00")
            det_nc["impuestos"]              = det.get("impuestos", {})
            detalles_nc.append(det_nc)

        # Fechas
        tz            = pytz.timezone("America/Guayaquil")
        ahora_ecuador = datetime.now(tz)
        fecha_clave   = ahora_ecuador.strftime("%Y-%m-%d")
        fecha_sri     = ahora_ecuador.strftime("%d/%m/%Y")
        fecha_fac_str = factura.fecha_emision.strftime("%d/%m/%Y")

        # Incrementar secuencial (mantiene el bloqueo dentro de la misma transacción)
        res_sec = await db.execute(text("""
            UPDATE puntos_emision
            SET secuencial_actual = secuencial_actual + 1
            WHERE id = :pto_id
            RETURNING secuencial_actual
        """), {"pto_id": factura.punto_emision_id})
        secuencial = str(res_sec.scalar()).zfill(9)

        # Clave de acceso
        clave_acceso = generar_clave_acceso(
            fecha=fecha_clave,
            tipo_comprobante="04",
            ruc=factura.ruc,
            ambiente=factura.ambiente,
            serie=f"{factura.estab_codigo}{factura.punto_codigo}",
            secuencial=secuencial,
        )

        nombre_comercial   = factura.nombre_est or factura.nombre_comercial or factura.razon_social
        direccion_est      = factura.direccion_est or factura.direccion_matriz
        valor_modificacion = calculos["totales"]["importeTotal"]

        # XML Nota de Crédito — orden exacto según ficha técnica SRI v2.26
        xml_obj = {
            "notaCredito": {
                "@id":      "comprobante",
                "@version": "1.1.0",
                "infoTributaria": {
                    "ambiente":        factura.ambiente,
                    "tipoEmision":     "1",
                    "razonSocial":     factura.razon_social,
                    "nombreComercial": nombre_comercial,
                    "ruc":             factura.ruc,
                    "claveAcceso":     clave_acceso,
                    "codDoc":          "04",
                    "estab":           factura.estab_codigo,
                    "ptoEmi":           factura.punto_codigo,
                    "secuencial":       secuencial,
                    "dirMatriz":       factura.direccion_matriz,
                },
                "infoNotaCredito": {
                    "fechaEmision":                fecha_sri,
                    "dirEstablecimiento":          direccion_est,
                    "tipoIdentificacionComprador": tipo_id_comp,
                    "razonSocialComprador":        factura.razon_social_comprador,
                    "identificacionComprador":     factura.identificacion_comprador,
                    "obligadoContabilidad":        obligado,
                    "codDocModificado":            "01",
                    "numDocModificado":            factura.numero_factura,
                    "fechaEmisionDocSustento":     fecha_fac_str,
                    "totalSinImpuestos":          calculos["totales"]["totalSinImpuestos"],
                    "valorModificacion":          valor_modificacion,
                    "totalConImpuestos": {
                        "totalImpuesto": calculos["totalConImpuestosXml"]
                    },
                    "motivo": motivo,
                },
                "detalles": {"detalle": detalles_nc},
                "infoAdicional": {
                    "campoAdicional": construir_campos_adicionales(nc_data)
                },
            }
        }

        # ─────────────────────────────────────────────────────────────
        # BLOQUE 2: Firma Electrónica
        # ─────────────────────────────────────────────────────────────
        xml_firmado_str = await firmar_xml(xml_obj, factura)

        # ─────────────────────────────────────────────────────────────
        # BLOQUE 3: Persistencia, R2 y Encolado
        # ─────────────────────────────────────────────────────────────
        xml_path_rel = f"{factura.ruc}/notas_credito/{clave_acceso}.xml"
        origen       = "api" if api_key_id else nc_data.get("origen", "web")

        class PuntoEmisionProxy:
            punto_id     = factura.punto_emision_id
            estab_codigo = factura.estab_codigo
            punto_codigo = factura.punto_codigo

        cliente_final = {
            "identificacion": factura.identificacion_comprador,
            "razon_social":   factura.razon_social_comprador,
            "email":          factura.email_comprador,
            "direccion":      direccion_est,
            "telefono":       "",
            "tipo_id":        tipo_id_comp,
        }

        datos_nc_json = {
            **xml_obj["notaCredito"],
            "resumenImpuestos":   calculos["resumenImpuestos"],
            "factura_referencia": str(factura_id),
        }

        nc_id = await guardar_y_encolar(
            xml_firmado_str   = xml_firmado_str,
            xml_path_rel      = xml_path_rel,
            datos_fac_json    = datos_nc_json,
            calculos          = calculos,
            emisor_id         = emisor_id,
            punto_emision     = PuntoEmisionProxy(),
            cliente_final     = cliente_final,
            cliente_emisor_id = factura.cliente_emisor_id,
            secuencial        = secuencial,
            clave_acceso      = clave_acceso,
            ahora_ecuador     = ahora_ecuador,
            api_key_id        = api_key_id,
            unlimited         = unlimited,
            origen            = origen,
            db                = db,
            cod_doc           = "04",
            doc_referencia_id = str(factura_id),
        )

        # COMMIT ÚNICO: Se confirma la reserva del secuencial y la nota de crédito
        # únicamente tras completar exitosamente la firma y el guardado.
        await db.commit()

        return {
            "ok":          True,
            "id":          nc_id,
            "claveAcceso": clave_acceso,
            "estado":      "FIRMADO",
            "mensaje":     "Nota de crédito en proceso de autorización.",
        }

    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error generando nota de crédito: {str(e)}")