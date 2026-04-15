import base64
import asyncio
import httpx
import xmltodict
import json
from sqlalchemy import text
from app.core.database import AsyncSessionLocal
from app.services.storage_service import download_file, upload_file
from app.services.mail_service import mail_service
from app.services.notifier_service import notificar_cambio_estado

URLS_SRI = {
    "1": {
        "recepcion": "https://celcer.sri.gob.ec/comprobantes-electronicos-ws/RecepcionComprobantesOffline?wsdl",
        "autorizacion": "https://celcer.sri.gob.ec/comprobantes-electronicos-ws/AutorizacionComprobantesOffline?wsdl"
    },
    "2": {
        "recepcion": "https://cel.sri.gob.ec/comprobantes-electronicos-ws/RecepcionComprobantesOffline?wsdl",
        "autorizacion": "https://cel.sri.gob.ec/comprobantes-electronicos-ws/AutorizacionComprobantesOffline?wsdl"
    }
}

# ─── HELPER: Reintento Automático ──────────────────────────────────────────────
async def httpx_with_retry(url: str, content: str, headers: dict, max_retries: int = 3):
    async with httpx.AsyncClient(timeout=10.0) as client:
        for intento in range(1, max_retries + 1):
            try:
                return await client.post(url, content=content, headers=headers)
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout) as err:
                if intento < max_retries:
                    espera = intento * 2  # 2s, 4s, 6s...
                    print(f"[SRI] ⚠️ Intento {intento}/{max_retries} fallido. Reintentando en {espera}s...")
                    await asyncio.sleep(espera)
                else:
                    raise err

# ─── JOB 1: Recepción ──────────────────────────────────────────────────────────
async def job_enviar_facturas():
    async with AsyncSessionLocal() as db:
        try:
            query = text("""
                SELECT 
                    i.id, i.xml_path, i.clave_acceso,
                    e.ambiente, e.id as emisor_db_id,
                    p.id as user_uid
                FROM invoices i
                JOIN emisores e ON i.emisor_id = e.id
                JOIN profiles p ON e.id = p.emisor_id
                WHERE i.estado = 'FIRMADO'
                AND (i.retry_count < 5 OR i.retry_count IS NULL)
                ORDER BY i.created_at ASC
                LIMIT 10
            """)
            result = await db.execute(query)
            facturas = result.fetchall()

            if not facturas:
                return

            for factura in facturas:
                try:
                    print(f"[SRI Job1] Enviando clave: {factura.clave_acceso}")
                    
                    # 1. Descargar XML de MinIO
                    bucket_xml, *path_xml_parts = factura.xml_path.split('/')
                    xml_bytes = download_file(bucket_xml, '/'.join(path_xml_parts))
                    xml_base64 = base64.b64encode(xml_bytes).decode('utf-8')
                    
                    # 2. Enviar al SRI
                    urls = URLS_SRI[factura.ambiente]
                    soap_body = f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ec="http://ec.gob.sri.ws.recepcion"><soapenv:Body><ec:validarComprobante><xml>{xml_base64}</xml></ec:validarComprobante></soapenv:Body></soapenv:Envelope>"""
                    
                    res = await httpx_with_retry(urls["recepcion"], soap_body, {'Content-Type': 'text/xml'})
                    
                    # 3. Parsear respuesta (xmltodict convierte XML a Diccionario Python)
                    json_res = xmltodict.parse(res.text)
                    try:
                        resp_recepcion = json_res['soap:Envelope']['soap:Body']['ns2:validarComprobanteResponse']['RespuestaRecepcionComprobante']
                    except KeyError:
                        continue

                    # Preparamos el dict para notificar
                    fac_dict = dict(factura._mapping)

                    if resp_recepcion.get('estado') == 'RECIBIDA':
                        await db.execute(text("UPDATE invoices SET estado = 'RECIBIDA', fecha_envio_sri = NOW() WHERE id = :id"), {"id": factura.id})
                        await db.commit()
                        print(f"[SRI Job1] ✅ RECIBIDA: {factura.clave_acceso}")
                        await notificar_cambio_estado(fac_dict, 'RECIBIDA')
                    else:
                        error_msg = json.dumps(resp_recepcion.get('comprobantes', resp_recepcion))
                        await db.execute(text("UPDATE invoices SET estado = 'DEVUELTA', mensajes_sri = :msg, fecha_envio_sri = NOW() WHERE id = :id"), {"msg": error_msg, "id": factura.id})
                        # REEMBOLSO
                        await db.execute(text("UPDATE user_credits SET balance = balance + 1 WHERE emisor_id = :eid"), {"eid": factura.emisor_db_id})
                        await db.commit()
                        print(f"[SRI Job1] ⚠️ DEVUELTA: {factura.clave_acceso} | Crédito devuelto.")
                        await notificar_cambio_estado(fac_dict, 'DEVUELTA', resp_recepcion)

                except Exception as err:
                    await db.rollback()
                    print(f"[SRI Job1] ❌ Error Recepción ({factura.clave_acceso}): {str(err)}")
                    
        except Exception as e:
            print(f"[SRI Job1] ❌ Error Crítico: {str(e)}")


# ─── JOB 2: Autorización ───────────────────────────────────────────────────────
async def job_autorizar_facturas():
    async with AsyncSessionLocal() as db:
        try:
            # ⚠️ AÑADIMOS CAMPOS IMPORTANTES AL SELECT (ruc, pdf_path, etc.)
            query = text("""
                SELECT i.id, i.clave_acceso, i.pdf_path, i.email_comprador, i.secuencial,
                       e.ambiente, e.ruc, e.razon_social, e.contribuyente_especial, e.id as emisor_db_id
                FROM invoices i
                JOIN emisores e ON i.emisor_id = e.id
                WHERE i.estado = 'ENVIADO' 
                OR (i.estado = 'RECIBIDO' AND i.fecha_autorizacion IS NULL)
                LIMIT 10
            """)
            result = await db.execute(query)
            facturas = result.fetchall()

            if not facturas:
                return

            # URL de tu microservicio de Node para generar el PDF
            NODE_PDF_URL = "http://localhost:3000/api/pdf"

            for factura in facturas:
                try:
                    urls = URLS_SRI[factura.ambiente]
                    soap_body = f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ec="http://ec.gob.sri.ws.autorizacion"><soapenv:Body><ec:autorizacionComprobante><claveAccesoComprobante>{factura.clave_acceso}</claveAccesoComprobante></ec:autorizacionComprobante></soapenv:Body></soapenv:Envelope>"""
                    
                    res = await httpx_with_retry(urls["autorizacion"], soap_body, {'Content-Type': 'text/xml'})
                    json_res = xmltodict.parse(res.text)
                    
                    try:
                        resp_auth = json_res['soap:Envelope']['soap:Body']['ns2:autorizacionComprobanteResponse']['RespuestaAutorizacionComprobante']
                    except KeyError:
                        continue

                    if int(resp_auth.get('numeroComprobantes', 0)) > 0:
                        autorizaciones = resp_auth['autorizaciones']['autorizacion']
                        autorizacion = autorizaciones[0] if isinstance(autorizaciones, list) else autorizaciones

                        fac_dict = dict(factura._mapping)

                        if autorizacion.get('estado') == 'AUTORIZADO':
                            xml_autorizado = autorizacion['comprobante']
                            fecha_auth = autorizacion['fechaAutorizacion']
                            xml_auth_path = f"authorized/{factura.ruc}/{factura.clave_acceso}.xml"
                            
                            # Subir XML autorizado
                            upload_file('invoices', xml_auth_path, xml_autorizado.encode('utf-8'), 'text/xml')

                            # ------------------------------------------------------------------
                            # 🚀 NUEVO: PEDIR EL PDF AUTORIZADO A NODE.JS
                            # ------------------------------------------------------------------
                            pdf_bytes = None
                            try:
                                async with httpx.AsyncClient() as client_node:
                                    res_node = await client_node.post(
                                        NODE_PDF_URL,
                                        json={
                                            "xmlAutorizado": xml_autorizado,
                                            "emisor": {"contribuyente_especial": factura.contribuyente_especial},
                                            "fechaAutorizacion": fecha_auth
                                        },
                                        timeout=15.0
                                    )
                                    if res_node.status_code == 200 and res_node.json().get("ok"):
                                        pdf_bytes = base64.b64decode(res_node.json()["pdfBase64"])
                                        # Sobreescribir el PDF en MinIO
                                        upload_file('invoices', factura.pdf_path.replace('invoices/', ''), pdf_bytes, 'application/pdf')
                            except Exception as e_pdf:
                                print(f"[SRI Job2] ⚠️ Error generando PDF en Node: {str(e_pdf)}")
                                # Si falla Node, hacemos un fallback al viejo PDF
                                pdf_bytes = download_file('invoices', factura.pdf_path.replace('invoices/', ''))
                            # ------------------------------------------------------------------

                            await db.execute(text("UPDATE invoices SET estado = 'AUTORIZADO', xml_path = :path, fecha_autorizacion = :fecha WHERE id = :id"), 
                                             {"path": f"invoices/{xml_auth_path}", "fecha": fecha_auth, "id": factura.id})
                            await db.commit()
                            
                            print(f"[SRI Job2] ✅ AUTORIZADO: {factura.clave_acceso}")
                            await notificar_cambio_estado(fac_dict, 'AUTORIZADO')

                            # Enviar Correo
                            if factura.email_comprador:
                                await mail_service.send_mail(
                                    to=factura.email_comprador,
                                    subject=f"Factura Electrónica - {factura.razon_social} - {factura.secuencial}",
                                    html_content="Su factura ha sido autorizada.",
                                    attachments=[
                                        {"filename": f"Factura_{factura.clave_acceso}.xml", "content": xml_autorizado.encode('utf-8'), "maintype": "text", "subtype": "xml"},
                                        {"filename": f"Factura_{factura.clave_acceso}.pdf", "content": pdf_bytes, "maintype": "application", "subtype": "pdf"}
                                    ]
                                )

                        elif autorizacion.get('estado') in ['RECHAZADO', 'NO AUTORIZADO']:
                            estado_final = 'RECHAZADO' if autorizacion.get('estado') == 'NO AUTORIZADO' else autorizacion.get('estado')
                            msg = json.dumps(autorizacion.get('mensajes', {}))
                            
                            await db.execute(text("UPDATE invoices SET estado = :est, mensajes_sri = :msg WHERE id = :id"), {"est": estado_final, "msg": msg, "id": factura.id})
                            await db.execute(text("UPDATE user_credits SET balance = balance + 1 WHERE emisor_id = :eid"), {"eid": factura.emisor_db_id})
                            await db.commit()
                            
                            print(f"[SRI Job2] ⚠️ {estado_final}: {factura.clave_acceso} | Crédito devuelto.")
                            await notificar_cambio_estado(fac_dict, estado_final, autorizacion.get('mensajes'))

                except Exception as err:
                    await db.rollback()
                    print(f"[SRI Job2] ❌ Error Autorización ({factura.clave_acceso}): {str(err)}")
                    
        except Exception as e:
            print(f"[SRI Job2] ❌ Error Crítico: {str(e)}")