import json
import base64
import httpx
import asyncio
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from app.schemas.cliente import ClienteCreate
from app.services.cliente_service import crear_cliente_core
from app.utils.calculadora import calcular_totales_e_impuestos
from app.utils.crypto import generar_clave_acceso, decrypt_password
from app.services.storage_service import upload_file, download_file, delete_file
from app.services.mail_service import mail_service
from app.services.notifier_service import notificar_cambio_estado
from app.core.config import settings

import pytz

URLS_SRI = {
    "1": {
        "recepcion":    "https://celcer.sri.gob.ec/comprobantes-electronicos-ws/RecepcionComprobantesOffline?wsdl",
        "autorizacion": "https://celcer.sri.gob.ec/comprobantes-electronicos-ws/AutorizacionComprobantesOffline?wsdl"
    },
    "2": {
        "recepcion":    "https://cel.sri.gob.ec/comprobantes-electronicos-ws/RecepcionComprobantesOffline?wsdl",
        "autorizacion": "https://cel.sri.gob.ec/comprobantes-electronicos-ws/AutorizacionComprobantesOffline?wsdl"
    }
}
NODE_SIGNER_URL = f"{settings.NODE_SIGNER_URL}/api/firmar"

async def emitir_factura_core(factura_data: dict, emisor_id: int, db: AsyncSession):
    if not factura_data.get("establecimiento") or not factura_data.get("punto_emision"):
        raise HTTPException(status_code=400, detail="Los campos 'establecimiento' y 'punto_emision' son requeridos.")

    # ─────────────────────────────────────────────────────────────
    # BLOQUE 0: Resolución de Identidad del Cliente
    # ─────────────────────────────────────────────────────────────
    cliente_id  = factura_data.get("cliente_id")
    cliente_obj = factura_data.get("cliente")
    cliente_emisor_id = None
    cliente_final = {
        "identificacion": None, "razon_social": None, "email": None,
        "direccion": "S/N", "telefono": "", "tipo_id": "05"
    }

    if cliente_id and str(cliente_id).strip().lower() == "consumidor_final":
        cliente_final = {
            "identificacion": "9999999999999", "razon_social": "CONSUMIDOR FINAL",
            "email": None, "direccion": "S/N", "telefono": "", "tipo_id": "07"
        }
        cliente_emisor_id = None

    elif cliente_id and str(cliente_id).strip() != "":
        res_cli = await db.execute(text("""
            SELECT id, tipo_identificacion_sri, identificacion, razon_social, direccion, email, telefono 
            FROM clientes_emisor WHERE id = :cid AND emisor_id = :eid
        """), {"cid": cliente_id, "eid": emisor_id})
        row_cli = res_cli.fetchone()
        if row_cli:
            cliente_emisor_id               = row_cli.id
            cliente_final["identificacion"] = row_cli.identificacion
            cliente_final["razon_social"]   = row_cli.razon_social
            cliente_final["email"]          = row_cli.email
            cliente_final["direccion"]      = row_cli.direccion
            cliente_final["telefono"]       = row_cli.telefono
            cliente_final["tipo_id"]        = row_cli.tipo_identificacion_sri
        else:
            raise HTTPException(status_code=404, detail="El 'cliente_id' proporcionado no existe.")

    elif cliente_obj:
        identificacion = cliente_obj.get("identificacion")
        tipo_id        = cliente_obj.get("tipoId") or cliente_obj.get("tipo_id") or "05"
        razon_social   = cliente_obj.get("razonSocial") or cliente_obj.get("nombre")
        email          = cliente_obj.get("email")
        direccion      = cliente_obj.get("direccion", "S/N")
        telefono       = cliente_obj.get("telefono", "")
        cliente_final.update({
            "identificacion": identificacion, "razon_social": razon_social,
            "email": email, "direccion": direccion, "telefono": telefono, "tipo_id": tipo_id
        })
        if tipo_id in ("04", "05") and identificacion:
            try:
                res_existente = await db.execute(text("""
                    SELECT id, razon_social, email, direccion, telefono, tipo_identificacion_sri
                    FROM clientes_emisor WHERE emisor_id = :eid AND identificacion = :id
                """), {"eid": emisor_id, "id": identificacion})
                existente = res_existente.fetchone()
                if existente:
                    cliente_emisor_id               = existente.id
                    cliente_final["razon_social"]   = existente.razon_social
                    cliente_final["email"]          = existente.email or email
                    cliente_final["direccion"]      = existente.direccion or direccion
                    cliente_final["telefono"]       = existente.telefono or telefono
                    cliente_final["tipo_id"]        = existente.tipo_identificacion_sri
                else:
                    nuevo_cliente = ClienteCreate(
                        tipo_identificacion_sri=tipo_id, identificacion=identificacion,
                        razon_social=razon_social, direccion=direccion,
                        email=email or "", telefono=telefono or ""
                    )
                    res_creacion  = await crear_cliente_core(emisor_id, nuevo_cliente, db, lanzar_error_si_existe=False)
                    cliente_emisor_id = res_creacion.get("uid")
            except Exception as e_cli:
                print(f"⚠️ Cliente no persistido, modo invitado: {e_cli}")

    if not cliente_final["identificacion"]:
        raise HTTPException(status_code=400, detail="Debe proporcionar un 'cliente_id' válido o un objeto 'cliente' completo.")

    # ─────────────────────────────────────────────────────────────
    # BLOQUE 1: Base de Datos y Generación de Datos
    # ─────────────────────────────────────────────────────────────
    try:
        res_emisor = await db.execute(text("""
            SELECT e.*, c.balance_emision 
            FROM emisores e JOIN user_credits c ON e.id = c.emisor_id 
            WHERE e.id = :emisor_id FOR UPDATE
        """), {"emisor_id": emisor_id})
        emisor = res_emisor.fetchone()
        if not emisor or emisor.balance_emision <= 0:
            raise HTTPException(status_code=402, detail="Créditos insuficientes.")

        res_pto = await db.execute(text("""
            SELECT p.id as punto_id, p.codigo as punto_codigo, e.codigo as estab_codigo,
                   e.direccion as direccion_establecimiento, e.nombre_comercial as nombre_establecimiento
            FROM puntos_emision p JOIN establecimientos e ON p.establecimiento_id = e.id
            WHERE e.codigo = :estab AND p.codigo = :pto AND e.emisor_id = :emisor_id
        """), {
            "estab": str(factura_data["establecimiento"]).zfill(3),
            "pto":   str(factura_data["punto_emision"]).zfill(3),
            "emisor_id": emisor_id
        })
        punto_emision = res_pto.fetchone()
        if not punto_emision:
            raise HTTPException(status_code=404, detail="Establecimiento y Punto no existen o no te pertenecen.")

        res_sec = await db.execute(text("""
            UPDATE puntos_emision SET secuencial_actual = secuencial_actual + 1
            WHERE id = :pto_id RETURNING secuencial_actual
        """), {"pto_id": punto_emision.punto_id})
        secuencial = str(res_sec.scalar()).zfill(9)

        tz                  = pytz.timezone('America/Guayaquil')
        ahora_ecuador       = datetime.now(tz)
        fecha_formato_clave = ahora_ecuador.strftime('%Y-%m-%d')
        fecha_formato_sri   = ahora_ecuador.strftime('%d/%m/%Y')
        calculos            = calcular_totales_e_impuestos(factura_data.get("items", []))

        if cliente_final["tipo_id"] == "07":
            importe = float(calculos["totales"]["importeTotal"])
            if importe > 50.00:
                raise HTTPException(
                    status_code=400,
                    detail=f"Las facturas a Consumidor Final no pueden superar $50.00 (total: ${importe:.2f})."
                )

        clave_acceso = generar_clave_acceso(
            fecha=fecha_formato_clave, tipo_comprobante='01', ruc=emisor.ruc,
            ambiente=emisor.ambiente,
            serie=f"{punto_emision.estab_codigo}{punto_emision.punto_codigo}",
            secuencial=secuencial
        )
        nombre_comercial_final = punto_emision.nombre_establecimiento or emisor.nombre_comercial or emisor.razon_social
        direccion_est_final    = punto_emision.direccion_establecimiento or emisor.direccion_matriz

        xml_obj = {
            "factura": {
                "@id": "comprobante", "@version": "1.1.0",
                "infoTributaria": {
                    "ambiente": emisor.ambiente, "tipoEmision": "1",
                    "razonSocial": emisor.razon_social, "nombreComercial": nombre_comercial_final,
                    "ruc": emisor.ruc, "claveAcceso": clave_acceso, "codDoc": "01",
                    "estab": punto_emision.estab_codigo, "ptoEmi": punto_emision.punto_codigo,
                    "secuencial": secuencial, "dirMatriz": emisor.direccion_matriz
                },
                "infoFactura": {
                    "fechaEmision": fecha_formato_sri, "dirEstablecimiento": direccion_est_final,
                    "obligadoContabilidad": getattr(emisor, 'obligado_contabilidad', 'NO'),
                    "tipoIdentificacionComprador": cliente_final["tipo_id"],
                    "razonSocialComprador": cliente_final["razon_social"],
                    "identificacionComprador": cliente_final["identificacion"],
                    "totalSinImpuestos": calculos["totales"]["totalSinImpuestos"],
                    "totalDescuento": calculos["totales"]["totalDescuento"],
                    "totalConImpuestos": {"totalImpuesto": calculos["totalConImpuestosXml"]},
                    "propina": "0.00", "importeTotal": calculos["totales"]["importeTotal"],
                    "moneda": "DOLAR",
                    "pagos": {
                        "pago": [{
                            "formaPago":    p.get("forma_pago", p.get("formaPago", "01")),
                            "total":        f"{float(p['total']):.2f}",
                            "plazo":        p.get("plazo", "0"),
                            "unidadTiempo": p.get("unidad_tiempo", p.get("unidadTiempo", "dias"))
                        } for p in factura_data.get("pagos", [])]
                    }
                },
                "detalles": {"detalle": calculos["detallesXml"]}
            }
        }
        await db.commit()

    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Bloque 1 Error: {str(e)}")

    # ─────────────────────────────────────────────────────────────
    # BLOQUE 2: Microservicio Node.js — firma
    # ─────────────────────────────────────────────────────────────
    try:
        p12_bytes  = download_file(emisor.p12_path)
        p12_base64 = base64.b64encode(p12_bytes).decode('utf-8')
        async with httpx.AsyncClient() as client:
            res_node = await client.post(
                NODE_SIGNER_URL,
                json={
                    "xmlObj": xml_obj,
                    "emisor": {
                        "p12_pass":     decrypt_password(emisor.p12_pass),
                        "ruc":          emisor.ruc,
                        "razon_social": emisor.razon_social,
                        "ambiente":     emisor.ambiente
                    },
                    "p12Base64": p12_base64
                },
                timeout=25.0
            )
        signer_data = res_node.json()
        if not signer_data.get("ok"):
            raise ValueError(f"Node Error: {signer_data.get('error')}")
        xml_firmado_str = signer_data["xmlFirmado"]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Falla técnica en firma: {str(e)}")

    # ─────────────────────────────────────────────────────────────
    # BLOQUE 3: Guardar XML firmado en R2 e Insertar Factura
    # ─────────────────────────────────────────────────────────────
    try:
        # Solo XML — sin PDF
        xml_path_rel = f"{emisor.ruc}/facturas/{clave_acceso}.xml"
        upload_file(xml_path_rel, xml_firmado_str.encode('utf-8'), "text/xml")

        await db.execute(
            text("UPDATE user_credits SET balance_emision = balance_emision - 1 WHERE emisor_id = :eid"),
            {"eid": emisor_id}
        )

        res_insert = await db.execute(text("""
            INSERT INTO invoices_emitidas (
                emisor_id, punto_emision_id, cliente_emisor_id, secuencial, fecha_emision,
                clave_acceso, numero_factura, estado,
                identificacion_comprador, razon_social_comprador, email_comprador,
                importe_total, subtotal_iva, subtotal_0, valor_iva,
                xml_path, datos_factura
            ) VALUES (
                :emisor_id, :pto_id, :cliente_emisor_id, :sec, :fecha,
                :clave, :num_fac, 'FIRMADO',
                :id_comp, :razon_comp, :email_comp,
                :total, :sub_iva, :sub_0, :val_iva,
                :xml_path, CAST(:datos_fac AS jsonb)
            ) RETURNING id
        """), {
            "emisor_id":         emisor_id,
            "pto_id":            punto_emision.punto_id,
            "cliente_emisor_id": cliente_emisor_id,
            "sec":               secuencial,
            "fecha":             ahora_ecuador.date(),
            "clave":             clave_acceso,
            "num_fac":           f"{punto_emision.estab_codigo}-{punto_emision.punto_codigo}-{secuencial}",
            "id_comp":           cliente_final["identificacion"],
            "razon_comp":        cliente_final["razon_social"],
            "email_comp":        cliente_final["email"],
            "total":             calculos["totales"]["importeTotal"],
            "sub_iva":           calculos["totales"]["subtotal_iva"],
            "sub_0":             calculos["totales"]["subtotal_0"],
            "val_iva":           calculos["totales"]["totalIva"],
            "xml_path":          xml_path_rel,
            "datos_fac":         json.dumps(xml_obj["factura"])
        })
        factura_id = res_insert.scalar()
        await db.commit()

    except Exception as e:
        await db.rollback()
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

    # ─────────────────────────────────────────────────────────────
    # BLOQUE 4: Fast-Track al SRI
    # ─────────────────────────────────────────────────────────────
    urls       = URLS_SRI[str(emisor.ambiente)]
    xml_base64 = base64.b64encode(xml_firmado_str.encode('utf-8')).decode('utf-8')
    factura_notificar = {
        "id":                     str(factura_id),
        "clave_acceso":           clave_acceso,
        "email_comprador":        cliente_final["email"],
        "razon_social_comprador": cliente_final["razon_social"],
        "secuencial":             secuencial,
        "importe_total":          calculos["totales"]["importeTotal"],
        "xml_path":               xml_path_rel,
        "ambiente":               emisor.ambiente,
        "ruc":                    emisor.ruc,
        "emisor_db_id":           str(emisor_id),
        "razon_social":           emisor.razon_social
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client_sri:
            soap_rec = f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ec="http://ec.gob.sri.ws.recepcion"><soapenv:Body><ec:validarComprobante><xml>{xml_base64}</xml></ec:validarComprobante></soapenv:Body></soapenv:Envelope>"""
            res_rec  = await client_sri.post(urls["recepcion"], content=soap_rec, headers={"Content-Type": "text/xml"})

            if "RECIBIDA" in res_rec.text:
                await db.execute(
                    text("UPDATE invoices_emitidas SET estado = 'RECIBIDA', fecha_envio_sri = NOW() WHERE id = :fid"),
                    {"fid": factura_id}
                )
                await db.commit()
                await notificar_cambio_estado(factura_notificar, "RECIBIDA")

                soap_auth = f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ec="http://ec.gob.sri.ws.autorizacion"><soapenv:Body><ec:autorizacionComprobante><claveAccesoComprobante>{clave_acceso}</claveAccesoComprobante></ec:autorizacionComprobante></soapenv:Body></soapenv:Envelope>"""

                for pausa in [1.2, 1.8, 2.5]:
                    await asyncio.sleep(pausa)
                    try:
                        res_auth = await client_sri.post(urls["autorizacion"], content=soap_auth, headers={"Content-Type": "text/xml"})
                        if "AUTORIZADO" in res_auth.text and "NO AUTORIZADO" not in res_auth.text:
                            import xml.etree.ElementTree as ET
                            root_auth      = ET.fromstring(res_auth.text)
                            auth_node      = root_auth.find(".//autorizacion")
                            fecha_auth     = None
                            xml_autorizado = xml_firmado_str  # fallback

                            if auth_node is not None:
                                fecha_auth     = auth_node.findtext("fechaAutorizacion")
                                xml_autorizado = auth_node.findtext("comprobante") or xml_firmado_str

                            # Sobreescribir XML firmado con XML autorizado en R2
                            upload_file(xml_path_rel, xml_autorizado.encode('utf-8'), "text/xml")

                            # Generar PDF on-demand para el email — no se guarda en R2
                            pdf_para_email = None
                            try:
                                res_pdf = await client_sri.post(
                                    NODE_SIGNER_URL.replace("/firmar", "/pdf"),
                                    json={
                                        "xmlAutorizado":    xml_autorizado,
                                        "emisor":           {"contribuyente_especial": getattr(emisor, 'contribuyente_especial', '')},
                                        "fechaAutorizacion": fecha_auth
                                    },
                                    timeout=15.0
                                )
                                if res_pdf.status_code == 200 and res_pdf.json().get("ok"):
                                    pdf_para_email = base64.b64decode(res_pdf.json()["pdfBase64"])
                            except Exception as e_pdf:
                                print(f"[FAST-TRACK] ⚠️ Error generando PDF para email: {e_pdf}")

                            await db.execute(
                                text("UPDATE invoices_emitidas SET estado = 'AUTORIZADO', fecha_autorizacion = NOW() WHERE id = :fid"),
                                {"fid": factura_id}
                            )
                            await db.commit()
                            await notificar_cambio_estado(factura_notificar, "AUTORIZADO")

                            # Email con XML autorizado + PDF generado on-demand
                            if factura_notificar["email_comprador"]:
                                attachments = [
                                    {"filename": f"{clave_acceso}.xml", "content": xml_autorizado.encode('utf-8'), "maintype": "text", "subtype": "xml"}
                                ]
                                if pdf_para_email:
                                    attachments.append(
                                        {"filename": f"{clave_acceso}.pdf", "content": pdf_para_email, "maintype": "application", "subtype": "pdf"}
                                    )
                                await mail_service.send_mail(
                                    to=factura_notificar["email_comprador"],
                                    subject=f"Factura Electrónica - {emisor.razon_social} - {secuencial}",
                                    html_content=f"Su factura {secuencial} ha sido autorizada por el SRI.",
                                    attachments=attachments
                                )
                            print(f"[FAST-TRACK] ⭐ ÉXITO: {clave_acceso}")
                            break
                    except Exception:
                        continue

            elif "DEVUELTA" in res_rec.text:
                import xml.etree.ElementTree as ET
                root_res      = ET.fromstring(res_rec.text)
                lista_errores = []
                for msg in root_res.findall(".//mensaje"):
                    lista_errores.append({
                        "identificador":        msg.findtext("identificador"),
                        "mensaje":              msg.findtext("mensaje"),
                        "informacionAdicional": msg.findtext("informacionAdicional"),
                        "tipo":                 msg.findtext("tipo")
                    })
                await db.execute(text("""
                    UPDATE invoices_emitidas 
                    SET estado = 'DEVUELTA', mensajes_sri = CAST(:msg AS jsonb)
                    WHERE id = :fid
                """), {"msg": json.dumps(lista_errores), "fid": factura_id})
                await db.execute(
                    text("UPDATE user_credits SET balance_emision = balance_emision + 1 WHERE emisor_id = :eid"),
                    {"eid": emisor_id}
                )
                await db.commit()
                await notificar_cambio_estado(factura_notificar, "DEVUELTA")

    except Exception as e:
        print(f"[FAST-TRACK] ℹ️ SRI asíncrono o timeout para {clave_acceso}: {str(e)}")

    final_state_res = await db.execute(
        text("SELECT estado FROM invoices_emitidas WHERE id = :fid"), {"fid": factura_id}
    )
    estado_final = final_state_res.scalar()
    return {
        "ok":          True,
        "id":          factura_id,
        "claveAcceso": clave_acceso,
        "estado":      estado_final,
        "mensaje":     "Factura autorizada exitosamente." if estado_final == 'AUTORIZADO' else "Comprobante en proceso."
    }