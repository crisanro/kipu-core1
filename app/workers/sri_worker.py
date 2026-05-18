import base64
import asyncio
import httpx
import xmltodict
import json
import uuid 
from datetime import datetime
from sqlalchemy import text
from app.core.database import AsyncSessionLocal
from app.services.storage_service import download_file, upload_file
from app.services.mail_service import mail_service
from app.services.notifier_service import notificar_cambio_estado
from app.core.config import settings

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

NODE_PDF_URL = f"{settings.NODE_SIGNER_URL}/api/pdf"

# ─── HELPER: Reintento Automático ─────────────────────────────────────────────
async def httpx_with_retry(url: str, content: str, headers: dict, max_retries: int = 3):
    async with httpx.AsyncClient(timeout=15.0) as client:
        for intento in range(1, max_retries + 1):
            try:
                return await client.post(url, content=content, headers=headers)
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout) as err:
                if intento < max_retries:
                    espera = intento * 2
                    print(f"[SRI] ⚠️ Intento {intento}/{max_retries} fallido. Reintentando en {espera}s...")
                    await asyncio.sleep(espera)
                else:
                    raise err

# ─── JOB 1: Recepción ─────────────────────────────────────────────────────────
async def job_enviar_facturas():
    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(text("""
                SELECT 
                    i.id, i.xml_path, i.clave_acceso,
                    e.ambiente, e.id as emisor_db_id
                FROM invoices_emitidas i
                JOIN emisores e ON i.emisor_id = e.id
                WHERE i.estado = 'FIRMADO'
                  AND (i.retry_count < 5 OR i.retry_count IS NULL)
                ORDER BY i.created_at ASC
                LIMIT 10
            """))
            facturas = result.fetchall()
            if not facturas:
                return

            for factura in facturas:
                try:
                    print(f"[SRI Job1] Enviando: {factura.clave_acceso}")

                    xml_bytes  = download_file(factura.xml_path)
                    xml_base64 = base64.b64encode(xml_bytes).decode('utf-8')

                    urls      = URLS_SRI[str(factura.ambiente)]
                    soap_body = f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ec="http://ec.gob.sri.ws.recepcion"><soapenv:Body><ec:validarComprobante><xml>{xml_base64}</xml></ec:validarComprobante></soapenv:Body></soapenv:Envelope>"""
                    res       = await httpx_with_retry(urls["recepcion"], soap_body, {'Content-Type': 'text/xml'})

                    json_res       = xmltodict.parse(res.text)
                    body           = json_res.get('soap:Envelope', {}).get('soap:Body', {})
                    resp_recepcion = body.get('ns2:validarComprobanteResponse', {}).get('RespuestaRecepcionComprobante')
                    fac_dict       = {k: (str(v) if isinstance(v, uuid.UUID) else v) for k, v in factura._mapping.items()}

                    if resp_recepcion and resp_recepcion.get('estado') == 'RECIBIDA':
                        await db.execute(
                            text("UPDATE invoices_emitidas SET estado = 'RECIBIDA', fecha_envio_sri = NOW() WHERE id = :id"),
                            {"id": factura.id}
                        )
                        await db.commit()
                        print(f"[SRI Job1] ✅ RECIBIDA: {factura.clave_acceso}")
                        await notificar_cambio_estado(fac_dict, 'RECIBIDA')
                    else:
                        await db.execute(text("""
                            UPDATE invoices_emitidas 
                            SET estado = 'DEVUELTA', mensajes_sri = CAST(:msg AS jsonb)
                            WHERE id = :id
                        """), {"msg": json.dumps(resp_recepcion), "id": factura.id})
                        await db.execute(
                            text("UPDATE user_credits SET balance_emision = balance_emision + 1 WHERE emisor_id = :eid"),
                            {"eid": factura.emisor_db_id}
                        )
                        await db.commit()
                        print(f"[SRI Job1] ⚠️ DEVUELTA: {factura.clave_acceso} | Crédito devuelto.")
                        await notificar_cambio_estado(fac_dict, 'DEVUELTA', resp_recepcion)

                except Exception as err:
                    await db.rollback()
                    await db.execute(
                        text("UPDATE invoices_emitidas SET retry_count = COALESCE(retry_count, 0) + 1, last_retry = NOW() WHERE id = :id"),
                        {"id": factura.id}
                    )
                    await db.commit()
                    print(f"[SRI Job1] ❌ Error ({factura.clave_acceso}): {str(err)}")

        except Exception as e:
            print(f"[SRI Job1] ❌ Error Crítico: {str(e)}")


# ─── JOB 2: Autorización ──────────────────────────────────────────────────────
async def job_autorizar_facturas():
    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(text("""
                SELECT 
                    i.id, i.clave_acceso, i.xml_path,
                    i.email_comprador, i.secuencial,
                    e.ambiente, e.ruc, e.razon_social, 
                    e.contribuyente_especial, e.id as emisor_db_id
                FROM invoices_emitidas i
                JOIN emisores e ON i.emisor_id = e.id
                WHERE i.estado = 'RECIBIDA' AND i.fecha_autorizacion IS NULL
                LIMIT 10
            """))
            facturas = result.fetchall()
            if not facturas:
                return

            for factura in facturas:
                try:
                    urls      = URLS_SRI[str(factura.ambiente)]
                    soap_body = f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ec="http://ec.gob.sri.ws.autorizacion"><soapenv:Body><ec:autorizacionComprobante><claveAccesoComprobante>{factura.clave_acceso}</claveAccesoComprobante></ec:autorizacionComprobante></soapenv:Body></soapenv:Envelope>"""
                    res       = await httpx_with_retry(urls["autorizacion"], soap_body, {'Content-Type': 'text/xml'})

                    json_res  = xmltodict.parse(res.text)
                    body      = json_res.get('soap:Envelope', {}).get('soap:Body', {})
                    resp_auth = body.get('ns2:autorizacionComprobanteResponse', {}).get('RespuestaAutorizacionComprobante')

                    if not resp_auth or int(resp_auth.get('numeroComprobantes', 0)) == 0:
                        continue

                    autorizaciones = resp_auth['autorizaciones']['autorizacion']
                    autorizacion   = autorizaciones[0] if isinstance(autorizaciones, list) else autorizaciones
                    fac_dict       = {k: (str(v) if isinstance(v, uuid.UUID) else v) for k, v in factura._mapping.items()}

                    if autorizacion.get('estado') == 'AUTORIZADO':
                        xml_autorizado = autorizacion['comprobante']
                        fecha_auth_str = autorizacion['fechaAutorizacion']
                        fecha_auth_obj = datetime.fromisoformat(fecha_auth_str.replace('Z', '+00:00'))

                        # Sobreescribir el XML firmado con el XML autorizado — mismo path
                        upload_file(factura.xml_path, xml_autorizado.encode('utf-8'), 'text/xml')

                        # Generar PDF on-demand solo para el email — no se guarda en R2
                        pdf_para_email = None
                        try:
                            async with httpx.AsyncClient(timeout=20.0) as client_node:
                                res_node = await client_node.post(
                                    NODE_PDF_URL,
                                    json={
                                        "xmlAutorizado":     xml_autorizado,
                                        "emisor":            {"contribuyente_especial": factura.contribuyente_especial},
                                        "fechaAutorizacion": fecha_auth_str
                                    }
                                )
                                if res_node.status_code == 200 and res_node.json().get("ok"):
                                    pdf_para_email = base64.b64decode(res_node.json()["pdfBase64"])
                        except Exception as e_pdf:
                            print(f"[SRI Job2] ⚠️ Error generando PDF: {e_pdf}")

                        await db.execute(
                            text("UPDATE invoices_emitidas SET estado = 'AUTORIZADO', fecha_autorizacion = :fecha WHERE id = :id"),
                            {"fecha": fecha_auth_obj, "id": factura.id}
                        )
                        await db.commit()
                        print(f"[SRI Job2] ✅ AUTORIZADO: {factura.clave_acceso}")
                        await notificar_cambio_estado(fac_dict, 'AUTORIZADO')

                        # Email — XML autorizado + PDF en memoria
                        if factura.email_comprador:
                            attachments = [
                                {"filename": f"{factura.clave_acceso}.xml", "content": xml_autorizado.encode('utf-8'), "maintype": "text", "subtype": "xml"}
                            ]
                            if pdf_para_email:
                                attachments.append(
                                    {"filename": f"{factura.clave_acceso}.pdf", "content": pdf_para_email, "maintype": "application", "subtype": "pdf"}
                                )
                            await mail_service.send_mail(
                                to=factura.email_comprador,
                                subject=f"Factura Electrónica - {factura.razon_social} - {factura.secuencial}",
                                html_content=f"Adjuntamos su comprobante {factura.secuencial} autorizado por el SRI.",
                                attachments=attachments
                            )

                    elif autorizacion.get('estado') in ['RECHAZADO', 'NO AUTORIZADO']:
                        await db.execute(text("""
                            UPDATE invoices_emitidas 
                            SET estado = 'RECHAZADO', mensajes_sri = CAST(:msg AS jsonb)
                            WHERE id = :id
                        """), {"msg": json.dumps(autorizacion.get('mensajes')), "id": factura.id})
                        await db.execute(
                            text("UPDATE user_credits SET balance_emision = balance_emision + 1 WHERE emisor_id = :eid"),
                            {"eid": factura.emisor_db_id}
                        )
                        await db.commit()
                        print(f"[SRI Job2] ⚠️ RECHAZADO: {factura.clave_acceso}")
                        await notificar_cambio_estado(fac_dict, 'RECHAZADO', autorizacion.get('mensajes'))

                except Exception as err:
                    await db.rollback()
                    print(f"[SRI Job2] ❌ Error ({factura.clave_acceso}): {str(err)}")

        except Exception as e:
            print(f"[SRI Job2] ❌ Error Crítico: {str(e)}")

