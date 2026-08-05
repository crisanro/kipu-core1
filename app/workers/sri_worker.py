# app/services/sri_worker.py
import base64
import asyncio
import httpx
import xmltodict
import json
import uuid
from datetime import datetime
from sqlalchemy import text
from app.core.database import AsyncSessionLocal
from app.core.cache import get_redis
from app.services.storage_service import download_file, upload_file
from app.services.mail_service import mail_service
from app.services.notifier_service import notificar_cambio_estado
from app.core.config import settings
from app.utils.sri_service import _devolver_stock

QUEUE_EMISION       = "kipu:queue:emision"
QUEUE_AUTORIZACION  = "kipu:queue:autorizacion"
QUEUE_PROC_EMISION  = "kipu:queue:proc:emision"
QUEUE_PROC_AUTH     = "kipu:queue:proc:auth"

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

NODE_PDF_URL    = f"{settings.NODE_SIGNER_URL}/api/pdf"
MAX_CONCURRENT  = 3
BRPOP_TIMEOUT   = 5

_sri_semaphore = asyncio.Semaphore(MAX_CONCURRENT)


async def recovery_al_arrancar():
    print("[Recovery] 🔍 Buscando facturas pendientes en DB...")
    redis = await get_redis()

    async with AsyncSessionLocal() as db:
        result_emision = await db.execute(text("""
            SELECT id FROM invoices_emitidas
            WHERE estado = 'FIRMADO'
            ORDER BY created_at ASC
        """))
        ids_emision = result_emision.fetchall()

        result_auth = await db.execute(text("""
            SELECT id FROM invoices_emitidas
            WHERE estado = 'RECIBIDA' AND fecha_autorizacion IS NULL
            ORDER BY created_at ASC
        """))
        ids_auth = result_auth.fetchall()

    await redis.delete(QUEUE_PROC_EMISION)
    await redis.delete(QUEUE_PROC_AUTH)

    if ids_emision:
        for row in ids_emision:
            await redis.lpush(QUEUE_EMISION, str(row.id))
        print(f"[Recovery] ✅ {len(ids_emision)} facturas FIRMADO → cola de emisión")

    if ids_auth:
        for row in ids_auth:
            await redis.lpush(QUEUE_AUTORIZACION, str(row.id))
        print(f"[Recovery] ✅ {len(ids_auth)} facturas RECIBIDA → cola de autorización")

    if not ids_emision and not ids_auth:
        print("[Recovery] ✅ Sin pendientes. Todo al día.")


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


def es_unlimited(unlimited) -> bool:
    return bool(unlimited)


async def procesar_emision(factura_id: str):
    async with _sri_semaphore:
        async with AsyncSessionLocal() as db:
            try:
                result = await db.execute(text("""
                    SELECT i.id, i.xml_path, i.clave_acceso, i.api_key_id,
                           e.ambiente, e.id as emisor_db_id, ak.unlimited
                    FROM invoices_emitidas i
                    JOIN emisores e ON i.emisor_id = e.id
                    LEFT JOIN api_keys ak ON i.api_key_id = ak.id
                    WHERE i.id = :fid AND i.estado = 'FIRMADO'
                """), {"fid": factura_id})
                factura = result.fetchone()

                if not factura:
                    print(f"[Emisión] ℹ️ {factura_id} ya no está en FIRMADO, se omite.")
                    return

                print(f"[Emisión] 📤 Enviando: {factura.clave_acceso}")
                xml_bytes  = download_file(factura.xml_path)
                xml_base64 = base64.b64encode(xml_bytes).decode('utf-8')
                urls       = URLS_SRI[str(factura.ambiente)]

                soap_body = (
                    f'<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" '
                    f'xmlns:ec="http://ec.gob.sri.ws.recepcion">'
                    f'<soapenv:Body><ec:validarComprobante><xml>{xml_base64}</xml>'
                    f'</ec:validarComprobante></soapenv:Body></soapenv:Envelope>'
                )
                res = await httpx_with_retry(urls["recepcion"], soap_body, {"Content-Type": "text/xml"})

                json_res = xmltodict.parse(res.text)
                body     = json_res.get("soap:Envelope", {}).get("soap:Body", {})

                if body.get("soap:Fault"):
                    fault_msg = body['soap:Fault'].get('faultstring', 'Error desconocido')
                    print(f"[Emisión] ⚠️ SRI Fault — esperando 30s antes de reintentar: {fault_msg}")
                    await asyncio.sleep(30)
                    raise Exception(f"SRI Fault: {fault_msg}")

                resp_recepcion = body.get("ns2:validarComprobanteResponse", {}).get("RespuestaRecepcionComprobante")
                fac_dict       = {k: (str(v) if isinstance(v, uuid.UUID) else v) for k, v in factura._mapping.items()}

                if resp_recepcion and resp_recepcion.get("estado") == "RECIBIDA":
                    await db.execute(
                        text("UPDATE invoices_emitidas SET estado = 'RECIBIDA', fecha_envio_sri = NOW() WHERE id = :id"),
                        {"id": factura.id}
                    )
                    await db.commit()
                    print(f"[Emisión] ✅ RECIBIDA: {factura.clave_acceso}")
                    await notificar_cambio_estado(fac_dict, "RECIBIDA")
                    redis = await get_redis()
                    await redis.lpush(QUEUE_AUTORIZACION, str(factura.id))

                else:
                    # DEVUELTA por SRI — devolver stock
                    await db.execute(text("""
                        UPDATE invoices_emitidas
                        SET estado = 'DEVUELTA', mensajes_sri = CAST(:msg AS jsonb)
                        WHERE id = :id
                    """), {"msg": json.dumps(resp_recepcion), "id": factura.id})
                    if not es_unlimited(factura.unlimited):
                        await db.execute(
                            text("UPDATE user_credits SET balance_emision = balance_emision + 1 WHERE emisor_id = :eid"),
                            {"eid": factura.emisor_db_id}
                        )
                    await db.commit()
                    print(f"[Emisión] ⚠️ DEVUELTA: {factura.clave_acceso}")

                    # ── Devolver stock ──────────────────────────
                    await _devolver_stock(str(factura.id), factura.emisor_db_id, db)

                    try:
                        from app.core.cache import cache_clear_prefix
                        await cache_clear_prefix(f"dashboard:{factura.emisor_db_id}")
                        await cache_clear_prefix(f"factura:{factura.emisor_db_id}")
                    except Exception as e_cache:
                        print(f"[Emisión] ⚠️ Cache no invalidado: {e_cache}")
                    await notificar_cambio_estado(fac_dict, "DEVUELTA", resp_recepcion)

            except Exception as err:
                await db.rollback()
                async with AsyncSessionLocal() as db2:
                    result2 = await db2.execute(
                        text("""
                            UPDATE invoices_emitidas
                            SET retry_count = CASE
                                WHEN last_retry < NOW() - INTERVAL '1 hour' THEN 1
                                ELSE COALESCE(retry_count, 0) + 1
                            END,
                            last_retry = NOW()
                            WHERE id = :id
                            RETURNING retry_count
                        """),
                        {"id": factura_id}
                    )
                    nuevo_retry = result2.scalar()
                    await db2.commit()
                print(f"[Emisión] ❌ Error ({factura_id}): {str(err)} — retry #{nuevo_retry}")
                espera = min(2 ** nuevo_retry * 10, 300)
                print(f"[Emisión] ⏳ Esperando {espera}s antes del reintento #{nuevo_retry + 1}")
                await asyncio.sleep(espera)
                redis = await get_redis()
                await redis.lpush(QUEUE_EMISION, factura_id)


async def procesar_autorizacion(factura_id: str):
    async with _sri_semaphore:
        async with AsyncSessionLocal() as db:
            try:
                result = await db.execute(text("""
                    SELECT i.id, i.clave_acceso, i.xml_path, i.email_comprador, i.secuencial,
                           i.api_key_id, e.ambiente, e.ruc, e.razon_social,
                           e.contribuyente_especial, e.id as emisor_db_id, ak.unlimited
                    FROM invoices_emitidas i
                    JOIN emisores e ON i.emisor_id = e.id
                    LEFT JOIN api_keys ak ON i.api_key_id = ak.id
                    WHERE i.id = :fid AND i.estado = 'RECIBIDA' AND i.fecha_autorizacion IS NULL
                """), {"fid": factura_id})
                factura = result.fetchone()

                if not factura:
                    print(f"[Auth] ℹ️ {factura_id} ya no está en RECIBIDA, se omite.")
                    return

                print(f"[Auth] 🔍 Consultando autorización: {factura.clave_acceso}")
                urls      = URLS_SRI[str(factura.ambiente)]
                soap_body = (
                    f'<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" '
                    f'xmlns:ec="http://ec.gob.sri.ws.autorizacion">'
                    f'<soapenv:Body><ec:autorizacionComprobante>'
                    f'<claveAccesoComprobante>{factura.clave_acceso}</claveAccesoComprobante>'
                    f'</ec:autorizacionComprobante></soapenv:Body></soapenv:Envelope>'
                )
                res = await httpx_with_retry(urls["autorizacion"], soap_body, {"Content-Type": "text/xml"})

                json_res  = xmltodict.parse(res.text)
                body      = json_res.get("soap:Envelope", {}).get("soap:Body", {})
                resp_auth = body.get("ns2:autorizacionComprobanteResponse", {}).get("RespuestaAutorizacionComprobante")
                fac_dict  = {k: (str(v) if isinstance(v, uuid.UUID) else v) for k, v in factura._mapping.items()}

                if not resp_auth or int(resp_auth.get("numeroComprobantes", 0)) == 0:
                    await asyncio.sleep(10)
                    redis = await get_redis()
                    await redis.lpush(QUEUE_AUTORIZACION, factura_id)
                    return

                autorizaciones = resp_auth["autorizaciones"]["autorizacion"]
                autorizacion   = autorizaciones[0] if isinstance(autorizaciones, list) else autorizaciones

                if autorizacion.get("estado") == "AUTORIZADO":
                    xml_autorizado = autorizacion["comprobante"]
                    fecha_auth_str = autorizacion["fechaAutorizacion"]
                    fecha_auth_obj = datetime.fromisoformat(fecha_auth_str.replace("Z", "+00:00"))

                    upload_file(factura.xml_path, xml_autorizado.encode("utf-8"), "text/xml")

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
                        print(f"[Auth] ⚠️ Error generando PDF: {e_pdf}")

                    await db.execute(
                        text("UPDATE invoices_emitidas SET estado = 'AUTORIZADO', fecha_autorizacion = :fecha WHERE id = :id"),
                        {"fecha": fecha_auth_obj, "id": factura.id}
                    )
                    await db.commit()
                    # Stock ya fue descontado al firmar — no hacer nada aquí
                    print(f"[Auth] ✅ AUTORIZADO: {factura.clave_acceso}")

                    try:
                        from app.core.cache import cache_clear_prefix
                        await cache_clear_prefix(f"dashboard:{factura.emisor_db_id}")
                        await cache_clear_prefix(f"factura:{factura.emisor_db_id}")
                    except Exception as e_cache:
                        print(f"[Auth] ⚠️ Cache no invalidado: {e_cache}")

                    await notificar_cambio_estado(fac_dict, "AUTORIZADO")
                    await disparar_webhooks(factura.id, factura.emisor_db_id, "factura.autorizada", fac_dict)

                    if factura.email_comprador:
                        attachments = [{"filename": f"{factura.clave_acceso}.xml", "content": xml_autorizado.encode("utf-8"), "maintype": "text", "subtype": "xml"}]
                        if pdf_para_email:
                            attachments.append({"filename": f"{factura.clave_acceso}.pdf", "content": pdf_para_email, "maintype": "application", "subtype": "pdf"})
                        await mail_service.send_mail(
                            to=factura.email_comprador,
                            subject=f"Factura Electrónica - {factura.razon_social} - {factura.secuencial}",
                            html_content=f"Adjuntamos su comprobante {factura.secuencial} autorizado por el SRI.",
                            attachments=attachments
                        )

                elif autorizacion.get("estado") in ["RECHAZADO", "NO AUTORIZADO"]:
                    await db.execute(text("""
                        UPDATE invoices_emitidas
                        SET estado = 'RECHAZADO', mensajes_sri = CAST(:msg AS jsonb)
                        WHERE id = :id
                    """), {"msg": json.dumps(autorizacion.get("mensajes")), "id": factura.id})
                    if not es_unlimited(factura.unlimited):
                        await db.execute(
                            text("UPDATE user_credits SET balance_emision = balance_emision + 1 WHERE emisor_id = :eid"),
                            {"eid": factura.emisor_db_id}
                        )
                    await db.commit()
                    print(f"[Auth] ⚠️ RECHAZADO: {factura.clave_acceso}")

                    # ── Devolver stock si SRI rechaza ───────────
                    await _devolver_stock(str(factura.id), factura.emisor_db_id, db)

                    try:
                        from app.core.cache import cache_clear_prefix
                        await cache_clear_prefix(f"dashboard:{factura.emisor_db_id}")
                        await cache_clear_prefix(f"factura:{factura.emisor_db_id}")
                    except Exception as e_cache:
                        print(f"[Auth] ⚠️ Cache no invalidado: {e_cache}")

                    await notificar_cambio_estado(fac_dict, "RECHAZADO", autorizacion.get("mensajes"))
                    await disparar_webhooks(factura.id, factura.emisor_db_id, "factura.rechazada", fac_dict)

            except Exception as err:
                await db.rollback()
                print(f"[Auth] ❌ Error ({factura_id}): {str(err)}")
                await asyncio.sleep(30)
                redis = await get_redis()
                await redis.lpush(QUEUE_AUTORIZACION, factura_id)


async def disparar_webhooks(factura_id, emisor_id: int, evento: str, payload: dict):
    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(text("""
                SELECT url, secret FROM webhooks
                WHERE emisor_id = :eid AND activo = true
                  AND eventos @> CAST(:evento AS jsonb)
            """), {"eid": emisor_id, "evento": json.dumps([evento])})
            webhooks = result.fetchall()
            if not webhooks:
                return

            import hmac, hashlib
            body = json.dumps({"evento": evento, "factura_id": str(factura_id), "timestamp": datetime.utcnow().isoformat(), "data": payload}, default=str)

            async with httpx.AsyncClient(timeout=10.0) as client:
                for wh in webhooks:
                    try:
                        headers = {"Content-Type": "application/json"}
                        if wh.secret:
                            firma = hmac.new(wh.secret.encode(), body.encode(), hashlib.sha256).hexdigest()
                            headers["X-Kipu-Signature"] = f"sha256={firma}"
                        await client.post(wh.url, content=body, headers=headers)
                        print(f"[Webhook] ✅ {evento} → {wh.url}")
                    except Exception as e_wh:
                        print(f"[Webhook] ⚠️ Error enviando a {wh.url}: {e_wh}")
        except Exception as e:
            print(f"[Webhook] ❌ Error crítico: {e}")


async def loop_emision():
    print("[Worker] 🚀 Loop de emisión iniciado.")
    redis = await get_redis()
    while True:
        try:
            resultado = await redis.brpop(QUEUE_EMISION, timeout=BRPOP_TIMEOUT)
            if resultado is None:
                continue
            factura_id = resultado[1]
            asyncio.create_task(_procesar_y_limpiar_emision(factura_id, redis))
        except (asyncio.TimeoutError, TimeoutError):
            continue
        except Exception as e:
            print(f"[Worker Emisión] ❌ Error en loop: {e}")
            await asyncio.sleep(3)
            try:
                redis = await get_redis()
            except Exception:
                pass


async def _procesar_y_limpiar_emision(factura_id: str, redis):
    try:
        await procesar_emision(factura_id)
    finally:
        await redis.lrem(QUEUE_PROC_EMISION, 1, factura_id)


async def loop_autorizacion():
    print("[Worker] 🚀 Loop de autorización iniciado.")
    redis = await get_redis()
    while True:
        try:
            resultado = await redis.brpop(QUEUE_AUTORIZACION, timeout=BRPOP_TIMEOUT)
            if resultado is None:
                continue
            factura_id = resultado[1]
            asyncio.create_task(_procesar_y_limpiar_auth(factura_id, redis))
        except (asyncio.TimeoutError, TimeoutError):
            continue
        except Exception as e:
            print(f"[Worker Auth] ❌ Error en loop: {e}")
            await asyncio.sleep(3)
            try:
                redis = await get_redis()
            except Exception:
                pass


async def _procesar_y_limpiar_auth(factura_id: str, redis):
    try:
        await procesar_autorizacion(factura_id)
    finally:
        await redis.lrem(QUEUE_PROC_AUTH, 1, factura_id)


async def iniciar_workers():
    await recovery_al_arrancar()
    await asyncio.gather(
        loop_emision(),
        loop_autorizacion()
    )