# app/workers/sri_worker.py

import base64
import asyncio
import httpx
import xmltodict
import json
import uuid
from datetime import datetime
from sqlalchemy import text
from app.core.database import AsyncSessionLocal
from app.services.storage_service import download_file, upload_file, delete_file
from app.services.mail_service import mail_service
from app.services.notifier_service import notificar_cambio_estado


# =============================================================================
# CONFIGURACIÓN
# =============================================================================

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

NODE_PDF_URL = "http://kipu_signer_node:3000/api/pdf"


# =============================================================================
# HELPERS
# =============================================================================

async def get_tenant_schemas(db) -> list[str]:
    """Retorna todos los schemas tenant activos."""
    result = await db.execute(
        text("SELECT DISTINCT tenant_schema FROM public.emisor_tenant_map")
    )
    return [row[0] for row in result.fetchall()]


async def httpx_with_retry(url: str, content: str, headers: dict, max_retries: int = 3):
    """Ejecuta un POST con reintentos automáticos."""
    async with httpx.AsyncClient(timeout=10.0) as client:
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


# =============================================================================
# JOB 1: Recepción — envía XMLs firmados al SRI
# =============================================================================

async def job_enviar_facturas():
    async with AsyncSessionLocal() as db:
        try:
            schemas = await get_tenant_schemas(db)
            if not schemas:
                return

            for schema in schemas:
                await db.execute(text(f"SET search_path TO {schema}, public"))

                result = await db.execute(text("""
                    SELECT
                        i.id, i.xml_path, i.clave_acceso,
                        e.ambiente, e.id as emisor_db_id,
                        p.id as user_uid
                    FROM invoices_emitidas i
                    JOIN public.emisores e ON i.emisor_id = e.id
                    JOIN public.profiles p ON e.id = p.emisor_id
                    WHERE i.estado = 'FIRMADO'
                    AND (i.retry_count < 5 OR i.retry_count IS NULL)
                    ORDER BY i.created_at ASC
                    LIMIT 10
                """))
                facturas = result.fetchall()

                if not facturas:
                    continue

                for factura in facturas:
                    try:
                        print(f"[SRI Job1] Enviando clave: {factura.clave_acceso}")

                        # Descargar XML firmado de R2 — path directo sin bucket
                        xml_bytes  = download_file(factura.xml_path)
                        xml_base64 = base64.b64encode(xml_bytes).decode('utf-8')

                        urls     = URLS_SRI[str(factura.ambiente)]
                        soap_body = (
                            f'<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" '
                            f'xmlns:ec="http://ec.gob.sri.ws.recepcion">'
                            f'<soapenv:Body><ec:validarComprobante><xml>{xml_base64}</xml>'
                            f'</ec:validarComprobante></soapenv:Body></soapenv:Envelope>'
                        )

                        res      = await httpx_with_retry(urls["recepcion"], soap_body, {'Content-Type': 'text/xml'})
                        json_res = xmltodict.parse(res.text)

                        try:
                            body           = json_res.get('soap:Envelope', {}).get('soap:Body', {})
                            resp_recepcion = body.get('ns2:validarComprobanteResponse', {}).get('RespuestaRecepcionComprobante')
                            if not resp_recepcion:
                                raise ValueError("Estructura inesperada del SRI.")
                        except Exception as parse_err:
                            raise Exception(f"Fallo al leer XML del SRI: {str(parse_err)}")

                        fac_dict = dict(factura._mapping)
                        for key, value in fac_dict.items():
                            if isinstance(value, uuid.UUID):
                                fac_dict[key] = str(value)

                        if resp_recepcion.get('estado') == 'RECIBIDA':
                            await db.execute(text("""
                                UPDATE invoices_emitidas
                                SET estado = 'RECIBIDA', fecha_envio_sri = NOW()
                                WHERE id = :id
                            """), {"id": factura.id})
                            await db.commit()
                            print(f"[SRI Job1] ✅ RECIBIDA: {factura.clave_acceso}")
                            await notificar_cambio_estado(fac_dict, 'RECIBIDA')

                        else:
                            error_msg = json.dumps(resp_recepcion.get('comprobantes', resp_recepcion))
                            await db.execute(text("""
                                UPDATE invoices_emitidas
                                SET estado = 'DEVUELTA', mensajes_sri = :msg, fecha_envio_sri = NOW()
                                WHERE id = :id
                            """), {"msg": error_msg, "id": factura.id})
                            await db.execute(text("""
                                UPDATE public.user_credits
                                SET balance_emision = balance_emision + 1
                                WHERE emisor_id = :eid
                            """), {"eid": factura.emisor_db_id})

                            # Eliminar XML firmado — no sirve si fue devuelto
                            try:
                                delete_file(factura.xml_path)
                            except Exception:
                                pass

                            await db.commit()
                            print(f"[SRI Job1] ⚠️ DEVUELTA: {factura.clave_acceso} | Crédito devuelto.")
                            await notificar_cambio_estado(fac_dict, 'DEVUELTA', resp_recepcion)

                    except Exception as err:
                        await db.rollback()
                        await db.execute(text("""
                            UPDATE invoices_emitidas
                            SET retry_count = COALESCE(retry_count, 0) + 1
                            WHERE id = :id
                        """), {"id": factura.id})
                        await db.commit()
                        print(f"[SRI Job1] ❌ Error Recepción ({factura.clave_acceso}): {str(err)}")

        except Exception as e:
            print(f"[SRI Job1] ❌ Error Crítico: {str(e)}")


# =============================================================================
# JOB 2: Autorización — autoriza comprobantes ya recibidos por el SRI
# =============================================================================

async def job_autorizar_facturas():
    async with AsyncSessionLocal() as db:
        try:
            schemas = await get_tenant_schemas(db)
            if not schemas:
                return

            for schema in schemas:
                await db.execute(text(f"SET search_path TO {schema}, public"))

                result = await db.execute(text("""
                    SELECT
                        i.id, i.clave_acceso, i.xml_path, i.email_comprador, i.secuencial,
                        e.ambiente, e.ruc, e.razon_social, e.contribuyente_especial, e.id as emisor_db_id
                    FROM invoices_emitidas i
                    JOIN public.emisores e ON i.emisor_id = e.id
                    WHERE i.estado = 'ENVIADO'
                       OR (i.estado = 'RECIBIDA' AND i.fecha_autorizacion IS NULL)
                    LIMIT 10
                """))
                facturas = result.fetchall()

                if not facturas:
                    continue

                for factura in facturas:
                    try:
                        urls      = URLS_SRI[str(factura.ambiente)]
                        soap_body = (
                            f'<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" '
                            f'xmlns:ec="http://ec.gob.sri.ws.autorizacion">'
                            f'<soapenv:Body><ec:autorizacionComprobante>'
                            f'<claveAccesoComprobante>{factura.clave_acceso}</claveAccesoComprobante>'
                            f'</ec:autorizacionComprobante></soapenv:Body></soapenv:Envelope>'
                        )

                        res      = await httpx_with_retry(urls["autorizacion"], soap_body, {'Content-Type': 'text/xml'})
                        json_res = xmltodict.parse(res.text)

                        try:
                            body      = json_res.get('soap:Envelope', {}).get('soap:Body', {})
                            resp_auth = body.get('ns2:autorizacionComprobanteResponse', {}).get('RespuestaAutorizacionComprobante')
                            if not resp_auth:
                                raise ValueError("Estructura inesperada del SRI.")
                        except Exception as parse_err:
                            raise Exception(f"Fallo al leer XML del SRI: {str(parse_err)}")

                        if int(resp_auth.get('numeroComprobantes', 0)) > 0:
                            autorizaciones = resp_auth['autorizaciones']['autorizacion']
                            autorizacion   = autorizaciones[0] if isinstance(autorizaciones, list) else autorizaciones

                            fac_dict = dict(factura._mapping)
                            for key, value in fac_dict.items():
                                if isinstance(value, uuid.UUID):
                                    fac_dict[key] = str(value)

                            if autorizacion.get('estado') == 'AUTORIZADO':
                                xml_autorizado = autorizacion['comprobante']
                                fecha_auth_str = autorizacion['fechaAutorizacion']
                                fecha_auth_obj = datetime.fromisoformat(fecha_auth_str)

                                # Path del XML autorizado en R2 — reemplaza al firmado
                                ahora          = datetime.now()
                                xml_auth_path  = (
                                    f"{factura.ruc}/facturas/"
                                    f"{ahora.year}/{ahora.month:02d}/"
                                    f"{factura.clave_acceso}.xml"
                                )

                                # Subir XML autorizado a R2
                                upload_file(xml_auth_path, xml_autorizado.encode('utf-8'), 'text/xml')

                                # Eliminar XML firmado — ya no sirve
                                if factura.xml_path:
                                    try:
                                        delete_file(factura.xml_path)
                                    except Exception:
                                        pass

                                # Actualizar DB — sin pdf_path, PDF bajo demanda
                                await db.execute(text("""
                                    UPDATE invoices_emitidas
                                    SET estado             = 'AUTORIZADO',
                                        xml_path          = :path,
                                        pdf_path          = NULL,
                                        fecha_autorizacion = :fecha
                                    WHERE id = :id
                                """), {"path": xml_auth_path, "fecha": fecha_auth_obj, "id": factura.id})
                                await db.commit()

                                print(f"[SRI Job2] ✅ AUTORIZADO: {factura.clave_acceso}")
                                fac_dict['fecha_autorizacion'] = fecha_auth_str
                                await notificar_cambio_estado(fac_dict, 'AUTORIZADO')

                                # Enviar correo con link — sin adjuntar PDF
                                if factura.email_comprador:
                                    try:
                                        await mail_service.send_mail(
                                            to=factura.email_comprador,
                                            subject=f"Factura Electrónica - {factura.razon_social} - {factura.secuencial}",
                                            html_content=(
                                                f"<h2>Su factura ha sido autorizada ✅</h2>"
                                                f"<p>Su comprobante <strong>{factura.secuencial}</strong> "
                                                f"ha sido autorizado por el SRI.</p>"
                                                f"<p><a href='https://kipu.ec/facturas/{factura.clave_acceso}'>"
                                                f"Ver y descargar factura</a></p>"
                                            )
                                        )
                                    except Exception as mail_err:
                                        print(f"[SRI Job2] ⚠️ Error enviando correo: {str(mail_err)}")

                            elif autorizacion.get('estado') in ['RECHAZADO', 'NO AUTORIZADO']:
                                estado_final = 'RECHAZADO' if autorizacion.get('estado') == 'NO AUTORIZADO' else autorizacion.get('estado')
                                msg          = json.dumps(autorizacion.get('mensajes', {}))

                                await db.execute(text("""
                                    UPDATE invoices_emitidas
                                    SET estado       = :est,
                                        mensajes_sri = :msg,
                                        xml_path     = NULL
                                    WHERE id = :id
                                """), {"est": estado_final, "msg": msg, "id": factura.id})

                                await db.execute(text("""
                                    UPDATE public.user_credits
                                    SET balance_emision = balance_emision + 1
                                    WHERE emisor_id = :eid
                                """), {"eid": factura.emisor_db_id})

                                # Eliminar XML firmado — no sirve
                                if factura.xml_path:
                                    try:
                                        delete_file(factura.xml_path)
                                    except Exception:
                                        pass

                                await db.commit()
                                print(f"[SRI Job2] ⚠️ {estado_final}: {factura.clave_acceso} | Crédito devuelto.")
                                await notificar_cambio_estado(fac_dict, estado_final, autorizacion.get('mensajes'))

                    except Exception as err:
                        await db.rollback()
                        print(f"[SRI Job2] ❌ Error Autorización ({factura.clave_acceso}): {str(err)}")

        except Exception as e:
            print(f"[SRI Job2] ❌ Error Crítico: {str(e)}")