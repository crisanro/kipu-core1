# app/workers/sri_worker.py
#
# Worker de emisión y autorización de comprobantes electrónicos.
# Cola: kipu:queue:emision → SRI recepción → kipu:queue:autorizacion → SRI autorización
#
# Cambios vs versión anterior:
#   - Tabla: invoices_emitidas → documentos_emitidos
#   - Campo: estado → estado_sri
#   - Campo: datos_factura → datos
#   - Campo: email_comprador → datos JSONB (legacy_email_comprador)
#   - Eliminado: ak.unlimited → lógica por origen (web=suscripción, api=créditos)
#   - Evento webhook: factura.* → documento.*
#   - Notificaciones con soporte para etiquetas Sandbox.

import hmac
import hashlib
import base64
import asyncio
import httpx
import xmltodict
import json
import uuid
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import AsyncSessionLocal
from app.core.cache import get_redis
from app.services.storage_service import download_file, upload_file
from app.services.mail_service import mail_service
from app.services.notifier_service import notificar_cambio_estado
from app.core.config import settings
from app.services.notification_service import crear_notificacion

QUEUE_EMISION      = "kipu:queue:emision"
QUEUE_AUTORIZACION = "kipu:queue:autorizacion"
QUEUE_PROC_EMISION = "kipu:queue:proc:emision"
QUEUE_PROC_AUTH    = "kipu:queue:proc:auth"

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

TIPO_DOC_LABEL = {
    "FAC": "Factura",
    "LIQ": "Liquidación",
    "NCR": "Nota de Crédito",
    "NDB": "Nota de Débito",
    "RET": "Retención",
}

NODE_PDF_URL   = f"{settings.NODE_SIGNER_URL}/api/pdf"
MAX_CONCURRENT = 3
BRPOP_TIMEOUT  = 5
_sri_semaphore = asyncio.Semaphore(MAX_CONCURRENT)


# =============================================================================
# RECOVERY AL ARRANCAR
# =============================================================================

async def recovery_al_arrancar():
    print("[Recovery] 🔍 Buscando comprobantes pendientes en DB...")
    redis = await get_redis()

    async with AsyncSessionLocal() as db:
        res_emision = await db.execute(text("""
            SELECT id FROM documentos_emitidos
            WHERE estado_sri = 'FIRMADO'
            AND es_sandbox = false
            ORDER BY created_at ASC
        """))
        ids_emision = res_emision.fetchall()

        res_auth = await db.execute(text("""
            SELECT id FROM documentos_emitidos
            WHERE estado_sri = 'RECIBIDA'
            AND fecha_autorizacion IS NULL
            AND es_sandbox = false
            ORDER BY created_at ASC
        """))
        ids_auth = res_auth.fetchall()

    await redis.delete(QUEUE_PROC_EMISION)
    await redis.delete(QUEUE_PROC_AUTH)

    if ids_emision:
        for row in ids_emision:
            await redis.lpush(QUEUE_EMISION, str(row.id))
        print(f"[Recovery] ✅ {len(ids_emision)} comprobantes FIRMADO → cola emisión")

    if ids_auth:
        for row in ids_auth:
            await redis.lpush(QUEUE_AUTORIZACION, str(row.id))
        print(f"[Recovery] ✅ {len(ids_auth)} comprobantes RECIBIDA → cola autorización")

    if not ids_emision and not ids_auth:
        print("[Recovery] ✅ Sin pendientes.")


# =============================================================================
# HELPERS
# =============================================================================

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


async def _invalidar_cache(emisor_id: int):
    try:
        redis   = await get_redis()
        pattern = f"kipu:cache:*:{emisor_id}:*"
        keys    = await redis.keys(pattern)
        if keys:
            await redis.delete(*keys)
    except Exception as e:
        print(f"[Cache] ⚠️ No invalidado: {e}")


def _email_desde_datos(datos: dict) -> str | None:
    """Extrae el email del comprador desde el JSONB datos."""
    if not datos:
        return None
    email = datos.get("legacy_email_comprador")
    if email:
        return email
    info = datos.get("infoFactura") or datos.get("infoLiquidacionCompra") or {}
    return info.get("emailComprador") or info.get("email")


def _es_origen_api(origen: str) -> bool:
    return origen == "api"


# =============================================================================
# PROCESADOR DE EMISIÓN
# =============================================================================

async def procesar_emision(doc_id: str):
    async with _sri_semaphore:
        async with AsyncSessionLocal() as db:
            try:
                res = await db.execute(text("""
                    SELECT
                        d.id, d.xml_path, d.clave_acceso, d.numero_doc,
                        d.api_key_id, d.origen, d.datos,
                        d.tipo_doc, d.es_sandbox,
                        e.ambiente, e.id as emisor_id,
                        e.contribuyente_especial
                    FROM documentos_emitidos d
                    JOIN emisores e ON d.emisor_id = e.id
                    WHERE d.id = :did AND d.estado_sri = 'FIRMADO'
                """), {"did": doc_id})
                doc = res.fetchone()
                if not doc:
                    print(f"[Emisión] ℹ️ {doc_id} ya no está en FIRMADO, se omite.")
                    return

                xml_bytes  = download_file(doc.xml_path)
                xml_base64 = base64.b64encode(xml_bytes).decode("utf-8")
                ambiente_efectivo = "1" if doc.es_sandbox else str(doc.ambiente)
                urls = URLS_SRI[ambiente_efectivo]

                soap_body = (
                    f'<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" '
                    f'xmlns:ec="http://ec.gob.sri.ws.recepcion">'
                    f'<soapenv:Body><ec:validarComprobante><xml>{xml_base64}</xml>'
                    f'</ec:validarComprobante></soapenv:Body></soapenv:Envelope>'
                )

                res_sri  = await httpx_with_retry(urls["recepcion"], soap_body, {"Content-Type": "text/xml"})
                json_res = xmltodict.parse(res_sri.text)
                body     = json_res.get("soap:Envelope", {}).get("soap:Body", {})

                if body.get("soap:Fault"):
                    fault_msg = body["soap:Fault"].get("faultstring", "Error desconocido")
                    print(f"[Emisión] ⚠️ SRI Fault — esperando 30s: {fault_msg}")
                    await asyncio.sleep(30)
                    raise Exception(f"SRI Fault: {fault_msg}")

                resp = body.get("ns2:validarComprobanteResponse", {}).get("RespuestaRecepcionComprobante")
                doc_dict = {k: (str(v) if isinstance(v, uuid.UUID) else v) for k, v in doc._mapping.items()}

                if resp and resp.get("estado") == "RECIBIDA":
                    await db.execute(text("""
                        UPDATE documentos_emitidos
                        SET estado_sri = 'RECIBIDA', fecha_envio_sri = NOW()
                        WHERE id = :id
                    """), {"id": doc.id})
                    await db.commit()

                    redis = await get_redis()
                    await redis.lpush(QUEUE_AUTORIZACION, str(doc.id))

                else:
                    await db.execute(text("""
                        UPDATE documentos_emitidos
                        SET estado_sri = 'DEVUELTA',
                            mensajes_sri = CAST(:msg AS jsonb)
                        WHERE id = :id
                    """), {"msg": json.dumps(resp), "id": doc.id})

                    if _es_origen_api(doc.origen):
                        await db.execute(text("""
                            UPDATE user_credits
                            SET balance = balance + 1, last_updated = NOW()
                            WHERE emisor_id = :eid
                        """), {"eid": doc.emisor_id})

                    await db.commit()

                    await _devolver_stock_si_aplica(doc, db)
                    await _invalidar_cache(doc.emisor_id)
                    await notificar_cambio_estado(doc_dict, "DEVUELTA", resp)

                    tipo_label = TIPO_DOC_LABEL.get(doc.tipo_doc, "Comprobante")
                    numero     = doc.numero_doc or doc.clave_acceso[-10:]
                    prefijo    = "🧪 [SANDBOX] " if doc.es_sandbox else ""

                    await crear_notificacion(
                        db         = db,
                        emisor_id = doc.emisor_id,
                        tipo      = "DOCUMENTO",
                        titulo    = f"{prefijo}⚠️ {tipo_label} devuelto por el SRI",
                        mensaje   = f"{prefijo}{tipo_label} {numero} fue devuelto. Revisa los errores en el detalle.",
                        referencia = f"/documentos/{doc.id}",
                    )
                    print(f"[Emisión] ⚠️ DEVUELTA: {doc.clave_acceso}")

            except Exception as err:
                await db.rollback()
                async with AsyncSessionLocal() as db2:
                    res2 = await db2.execute(text("""
                        UPDATE documentos_emitidos
                        SET retry_count = CASE
                            WHEN last_retry < NOW() - INTERVAL '1 hour' THEN 1
                            ELSE COALESCE(retry_count, 0) + 1
                        END,
                        last_retry = NOW()
                        WHERE id = :id
                        RETURNING retry_count
                    """), {"id": doc_id})
                    nuevo_retry = res2.scalar()
                    await db2.commit()

                espera = min(2 ** nuevo_retry * 10, 300)
                print(f"[Emisión] ❌ Error ({doc_id}): {str(err)} — retry #{nuevo_retry}, esperando {espera}s")
                await asyncio.sleep(espera)

                redis = await get_redis()
                await redis.lpush(QUEUE_EMISION, doc_id)


# =============================================================================
# PROCESADOR DE AUTORIZACIÓN
# =============================================================================

async def procesar_autorizacion(doc_id: str):
    async with _sri_semaphore:
        async with AsyncSessionLocal() as db:
            try:
                res = await db.execute(text("""
                    SELECT
                        d.id, d.clave_acceso, d.xml_path, d.numero_doc,
                        d.api_key_id, d.origen, d.datos,
                        d.tipo_doc, d.secuencial, d.es_sandbox,
                        e.ambiente, e.ruc, e.razon_social,
                        e.contribuyente_especial, e.id as emisor_id
                    FROM documentos_emitidos d
                    JOIN emisores e ON d.emisor_id = e.id
                    WHERE d.id = :did
                      AND d.estado_sri = 'RECIBIDA'
                      AND d.fecha_autorizacion IS NULL
                """), {"did": doc_id})

                doc = res.fetchone()
                if not doc:
                    print(f"[Auth] ℹ️ {doc_id} ya no está en RECIBIDA, se omite.")
                    return

                ambiente_efectivo = "1" if doc.es_sandbox else str(doc.ambiente)
                urls = URLS_SRI[ambiente_efectivo]
                soap_body = (
                    f'<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" '
                    f'xmlns:ec="http://ec.gob.sri.ws.autorizacion">'
                    f'<soapenv:Body><ec:autorizacionComprobante>'
                    f'<claveAccesoComprobante>{doc.clave_acceso}</claveAccesoComprobante>'
                    f'</ec:autorizacionComprobante></soapenv:Body></soapenv:Envelope>'
                )

                res_sri   = await httpx_with_retry(urls["autorizacion"], soap_body, {"Content-Type": "text/xml"})
                json_res  = xmltodict.parse(res_sri.text)
                body      = json_res.get("soap:Envelope", {}).get("soap:Body", {})
                resp_auth = body.get("ns2:autorizacionComprobanteResponse", {}).get("RespuestaAutorizacionComprobante")
                doc_dict  = {k: (str(v) if isinstance(v, uuid.UUID) else v) for k, v in doc._mapping.items()}

                if not resp_auth or int(resp_auth.get("numeroComprobantes", 0)) == 0:
                    await asyncio.sleep(10)
                    redis = await get_redis()
                    await redis.lpush(QUEUE_AUTORIZACION, doc_id)
                    return

                autorizaciones = resp_auth["autorizaciones"]["autorizacion"]
                autorizacion   = autorizaciones[0] if isinstance(autorizaciones, list) else autorizaciones

                tipo_label = TIPO_DOC_LABEL.get(doc.tipo_doc, "Comprobante")
                numero     = doc.numero_doc or doc.clave_acceso[-10:]
                prefijo    = "🧪 [SANDBOX] " if doc.es_sandbox else ""

                if autorizacion.get("estado") == "AUTORIZADO":
                    xml_autorizado = autorizacion["comprobante"]
                    fecha_auth_str = autorizacion["fechaAutorizacion"]
                    fecha_auth_obj = datetime.fromisoformat(fecha_auth_str.replace("Z", "+00:00"))

                    upload_file(doc.xml_path, xml_autorizado.encode("utf-8"), "text/xml")
                    pdf_bytes = await _generar_pdf(xml_autorizado, doc, fecha_auth_str)

                    await db.execute(text("""
                        UPDATE documentos_emitidos
                        SET estado_sri = 'AUTORIZADO',
                            fecha_autorizacion = :fecha
                        WHERE id = :id
                    """), {"fecha": fecha_auth_obj, "id": doc.id})
                    await db.commit()

                    await _invalidar_cache(doc.emisor_id)
                    await disparar_webhooks(doc.id, doc.emisor_id, "documento.autorizado", doc_dict)

                    await crear_notificacion(
                        db         = db,
                        emisor_id = doc.emisor_id,
                        tipo      = "DOCUMENTO",
                        titulo    = f"{prefijo}✅ {tipo_label} autorizado",
                        mensaje   = f"{prefijo}{tipo_label} {numero} autorizado por el SRI{' de pruebas' if doc.es_sandbox else ''}.",
                        referencia = f"/documentos/{doc.id}",
                    )

                    if doc.tipo_doc in ("FAC", "LIQ"):
                        if doc.es_sandbox:
                            res_owner = await db.execute(text("""
                                SELECT p.email, p.full_name FROM profiles p
                                JOIN emisor_usuarios eu ON eu.profile_id = p.id
                                WHERE eu.emisor_id = :eid
                                ORDER BY eu.created_at ASC
                                LIMIT 1
                            """), {"eid": doc.emisor_id})
                            owner = res_owner.fetchone()
                            if owner:
                                await _enviar_email_comprobante(
                                    email        = owner.email,
                                    razon_social = f"[SANDBOX] {doc.razon_social}",
                                    secuencial   = doc.secuencial,
                                    clave_acceso = doc.clave_acceso,
                                    xml_str      = xml_autorizado,
                                    pdf_bytes    = pdf_bytes,
                                )
                        else:
                            email_comprador = _email_desde_datos(doc.datos)
                            if email_comprador:
                                await _enviar_email_comprobante(
                                    email        = email_comprador,
                                    razon_social = doc.razon_social,
                                    secuencial   = doc.secuencial,
                                    clave_acceso = doc.clave_acceso,
                                    xml_str      = xml_autorizado,
                                    pdf_bytes    = pdf_bytes,
                                )

                elif autorizacion.get("estado") in ("RECHAZADO", "NO AUTORIZADO"):
                    await db.execute(text("""
                        UPDATE documentos_emitidos
                        SET estado_sri = 'RECHAZADO',
                            mensajes_sri = CAST(:msg AS jsonb)
                        WHERE id = :id
                    """), {"msg": json.dumps(autorizacion.get("mensajes")), "id": doc.id})

                    if _es_origen_api(doc.origen):
                        await db.execute(text("""
                            UPDATE user_credits
                            SET balance = balance + 1, last_updated = NOW()
                            WHERE emisor_id = :eid
                        """), {"eid": doc.emisor_id})

                    await db.commit()

                    await _devolver_stock_si_aplica(doc, db)
                    await _invalidar_cache(doc.emisor_id)
                    await notificar_cambio_estado(doc_dict, "RECHAZADO", autorizacion.get("mensajes"))
                    
                    await crear_notificacion(
                        db         = db,
                        emisor_id = doc.emisor_id,
                        tipo      = "DOCUMENTO",
                        titulo    = f"{prefijo}❌ {tipo_label} rechazado por el SRI",
                        mensaje   = f"{prefijo}{tipo_label} {numero} fue rechazado. Revisa los errores en el detalle.",
                        referencia = f"/documentos/{doc.id}",
                    )
                    await disparar_webhooks(doc.id, doc.emisor_id, "documento.rechazado", doc_dict)
                    print(f"[Auth] ⚠️ RECHAZADO: {doc.clave_acceso}")

            except Exception as err:
                await db.rollback()
                print(f"[Auth] ❌ Error ({doc_id}): {str(err)}")
                await asyncio.sleep(30)
                redis = await get_redis()
                await redis.lpush(QUEUE_AUTORIZACION, doc_id)


# =============================================================================
# WEBHOOKS
# =============================================================================

async def disparar_webhooks(doc_id, emisor_id: int, evento: str, payload: dict):
    async with AsyncSessionLocal() as db:
        try:
            res = await db.execute(text("""
                SELECT url, secret FROM webhooks
                WHERE emisor_id = :eid
                  AND activo = true
                  AND eventos @> CAST(:evento AS jsonb)
            """), {"eid": emisor_id, "evento": json.dumps([evento])})
            webhooks = res.fetchall()
            if not webhooks:
                return

            body = json.dumps({
                "evento":     evento,
                "doc_id":     str(doc_id),
                "timestamp":  datetime.utcnow().isoformat(),
                "data":       payload,
            }, default=str)

            async with httpx.AsyncClient(timeout=10.0) as client:
                for wh in webhooks:
                    try:
                        headers = {"Content-Type": "application/json"}
                        if wh.secret:
                            firma = hmac.new(wh.secret.encode(), body.encode(), hashlib.sha256).hexdigest()
                            headers["X-Kipu-Signature"] = f"sha256={firma}"
                        await client.post(wh.url, content=body, headers=headers)
                    except Exception as e:
                        print(f"[Webhook] ⚠️ Error enviando a {wh.url}: {e}")
        except Exception as e:
            print(f"[Webhook] ❌ Error crítico: {e}")


# =============================================================================
# HELPERS INTERNOS
# =============================================================================

async def _generar_pdf(xml_autorizado: str, doc, fecha_auth_str: str) -> bytes | None:
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            res = await client.post(NODE_PDF_URL, json={
                "xmlAutorizado":     xml_autorizado,
                "emisor":            {"contribuyente_especial": doc.contribuyente_especial or ""},
                "fechaAutorizacion": fecha_auth_str,
            })
            if res.status_code == 200 and res.json().get("ok"):
                return base64.b64decode(res.json()["pdfBase64"])
    except Exception as e:
        print(f"[Auth] ⚠️ Error generando PDF: {e}")
    return None


async def _enviar_email_comprobante(
    email: str, razon_social: str, secuencial: str,
    clave_acceso: str, xml_str: str, pdf_bytes: bytes | None,
):
    try:
        attachments = [{
            "filename": f"{clave_acceso}.xml",
            "content":  xml_str.encode("utf-8"),
            "maintype": "text",
            "subtype":  "xml",
        }]
        if pdf_bytes:
            attachments.append({
                "filename": f"{clave_acceso}.pdf",
                "content":  pdf_bytes,
                "maintype": "application",
                "subtype":  "pdf",
            })
        await mail_service.send_mail(
            to           = email,
            subject      = f"Comprobante Electrónico — {razon_social} — {secuencial}",
            html_content = f"Adjuntamos su comprobante {secuencial} autorizado por el SRI.",
            attachments  = attachments,
        )
    except Exception as e:
        print(f"[Auth] ⚠️ Error enviando email: {e}")


async def _devolver_stock_si_aplica(doc, db: AsyncSession):
    if doc.tipo_doc not in ("FAC", "LIQ"):
        return
    try:
        datos    = doc.datos or {}
        detalles = datos.get("detalles", {}).get("detalle", [])
        if not isinstance(detalles, list):
            detalles = [detalles]
        for det in detalles:
            codigo = det.get("codigoPrincipal") or det.get("codigoAuxiliar")
            if not codigo or codigo == "S/C":
                continue
            cantidad = float(det.get("cantidad", 0))
            await db.execute(text("""
                UPDATE catalogo_items
                SET stock = stock + :qty, updated_at = NOW()
                WHERE emisor_id = :eid AND stock != -1 AND codigo = :cod
            """), {"qty": int(cantidad), "eid": doc.emisor_id, "cod": codigo})
        await db.commit()
        print(f"[Stock] ↩️ Stock devuelto para documento {doc.id}")
    except Exception as e:
        print(f"[Stock] ⚠️ Error devolviendo stock: {e}")


# =============================================================================
# LOOPS
# =============================================================================

async def loop_emision():
    print("[Worker] 🚀 Loop de emisión iniciado.")
    redis = await get_redis()
    while True:
        try:
            resultado = await redis.brpop(QUEUE_EMISION, timeout=BRPOP_TIMEOUT)
            if resultado is None:
                continue
            doc_id = resultado[1]
            asyncio.create_task(_procesar_y_limpiar_emision(doc_id, redis))
        except (asyncio.TimeoutError, TimeoutError):
            continue
        except Exception as e:
            print(f"[Worker Emisión] ❌ Error en loop: {e}")
            await asyncio.sleep(3)
            try:
                redis = await get_redis()
            except Exception:
                pass


async def _procesar_y_limpiar_emision(doc_id: str, redis):
    try:
        await procesar_emision(doc_id)
    finally:
        await redis.lrem(QUEUE_PROC_EMISION, 1, doc_id)


async def loop_autorizacion():
    print("[Worker] 🚀 Loop de autorización iniciado.")
    redis = await get_redis()
    while True:
        try:
            resultado = await redis.brpop(QUEUE_AUTORIZACION, timeout=BRPOP_TIMEOUT)
            if resultado is None:
                continue
            doc_id = resultado[1]
            asyncio.create_task(_procesar_y_limpiar_auth(doc_id, redis))
        except (asyncio.TimeoutError, TimeoutError):
            continue
        except Exception as e:
            print(f"[Worker Auth] ❌ Error en loop: {e}")
            await asyncio.sleep(3)
            try:
                redis = await get_redis()
            except Exception:
                pass


async def _procesar_y_limpiar_auth(doc_id: str, redis):
    try:
        await procesar_autorizacion(doc_id)
    finally:
        await redis.lrem(QUEUE_PROC_AUTH, 1, doc_id)


async def iniciar_workers():
    await recovery_al_arrancar()
    await asyncio.gather(
        loop_emision(),
        loop_autorizacion(),
    )