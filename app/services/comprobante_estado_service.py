# app/services/comprobante_estado_service.py
#
# Transiciones de estado de un comprobante emitido. Una sola lógica para:
#   - el worker de emisión/autorización
#   - la conciliación periódica
#   - el botón "Consultar en el SRI"
#
# Estados:
#   FIRMADO      en cola para enviarse
#   RECIBIDA     el SRI lo recibió, falta la autorización
#   AUTORIZADO   autorizado por el SRI
#   DEVUELTA     el SRI lo rechazó en recepción (con mensajes del SRI)
#   RECHAZADO    el SRI no lo autorizó (con mensajes del SRI)
#   EN_REVISION  falla técnica sin resolver: NO es un rechazo del SRI
#
# Stock y crédito de API solo se revierten ante un rechazo REAL del SRI, y se
# reaplican si después resulta que el SRI sí lo autorizó.
#
# Notificaciones push:
#   - AUTORIZADO: solo si se corrigió un falso rechazo o si tardó más de 60s
#   - EN_REVISION: nunca (el sistema lo resuelve solo)
#   - DEVUELTA / RECHAZADO: siempre
#
# Invalidación de caché:
#   Usa invalidate_emisor de app.core.cache — la fuente única de verdad.

import base64
import hashlib
import hmac
import json
import time
import uuid
from datetime import datetime, timezone

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import get_redis, invalidate_emisor
from app.core.config import settings
from app.services import sri_client as sri
from app.services import stock_service
from app.services.mail_service import mail_service
from app.services.notification_service import crear_notificacion
from app.services.notifier_service import notificar_cambio_estado
from app.services.storage_service import upload_file

QUEUE_EMISION      = "kipu:queue:emision"
QUEUE_AUTORIZACION = "kipu:queue:autorizacion"
QUEUE_DIFERIDA     = "kipu:queue:diferida"     # ZSET: miembro "cola|doc_id", score = cuándo

NODE_PDF_URL = f"{settings.NODE_SIGNER_URL}/api/pdf"

TIPO_DOC_LABEL = {
    "FAC": "Factura",
    "LIQ": "Liquidación",
    "NCR": "Nota de Crédito",
    "NDB": "Nota de Débito",
    "RET": "Retención",
}

UMBRAL_NOTIF_AUTORIZADO = 60  # segundos desde created_at para notificar AUTORIZADO


# =============================================================================
# CARGA Y COLAS
# =============================================================================
_SELECT_DOC = """
    SELECT
        d.id, d.clave_acceso, d.xml_path, d.numero_doc, d.secuencial,
        d.api_key_id, d.origen, d.datos, d.tipo_doc, d.es_sandbox,
        d.email_comprador, d.estado_sri, d.retry_count, d.fecha_envio_sri,
        d.stock_estado, d.credito_estado, d.created_at,
        e.ambiente, e.ruc, e.razon_social, e.contribuyente_especial, e.id AS emisor_id
    FROM documentos_emitidos d
    JOIN emisores e ON d.emisor_id = e.id
    WHERE d.id = :did
"""


async def cargar_documento(db: AsyncSession, doc_id, bloquear: bool = False):
    sql = _SELECT_DOC + (" FOR UPDATE OF d" if bloquear else "")
    res = await db.execute(text(sql), {"did": str(doc_id)})
    return res.fetchone()


def ambiente_efectivo(doc) -> str:
    return "1" if doc.es_sandbox else str(doc.ambiente)


def _doc_dict(doc) -> dict:
    return {k: (str(v) if isinstance(v, uuid.UUID) else v) for k, v in doc._mapping.items()}


def _tardo_mucho(doc) -> bool:
    """True si el doc lleva más de UMBRAL_NOTIF_AUTORIZADO seg desde que se creó."""
    ref = doc.created_at
    if not ref:
        return False
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - ref).total_seconds() > UMBRAL_NOTIF_AUTORIZADO


async def programar(cola: str, doc_id, segundos: float) -> None:
    """Reintento diferido sin bloquear al worker. Si ya estaba programado, se reprograma."""
    redis = await get_redis()
    await redis.zadd(QUEUE_DIFERIDA, {f"{cola}|{doc_id}": time.time() + max(segundos, 0)})


async def encolar(cola: str, doc_id) -> None:
    redis = await get_redis()
    await redis.lpush(cola, str(doc_id))


async def invalidar_cache(emisor_id: int) -> None:
    """Wrapper para mantener compatibilidad con imports existentes.
    Delega a invalidate_emisor de app.core.cache."""
    await invalidate_emisor(emisor_id)


# =============================================================================
# CRÉDITO DE API (solo lo que realmente se cobró)
# =============================================================================
async def _revertir_credito(db: AsyncSession, doc) -> None:
    if doc.credito_estado != "COBRADO":
        return
    await db.execute(text("""
        UPDATE user_credits SET balance = balance + 1, last_updated = NOW() WHERE emisor_id = :eid
    """), {"eid": doc.emisor_id})
    await db.execute(text("UPDATE documentos_emitidos SET credito_estado = 'DEVUELTO' WHERE id = :did"),
                     {"did": str(doc.id)})


async def _reaplicar_credito(db: AsyncSession, doc) -> None:
    if doc.credito_estado != "DEVUELTO":
        return
    await db.execute(text("""
        UPDATE user_credits SET balance = balance - 1, last_updated = NOW() WHERE emisor_id = :eid
    """), {"eid": doc.emisor_id})
    await db.execute(text("UPDATE documentos_emitidos SET credito_estado = 'COBRADO' WHERE id = :did"),
                     {"did": str(doc.id)})


# =============================================================================
# TRANSICIONES
# =============================================================================
async def marcar_recibida(db: AsyncSession, doc) -> None:
    await db.execute(text("""
        UPDATE documentos_emitidos
        SET estado_sri = 'RECIBIDA', fecha_envio_sri = COALESCE(fecha_envio_sri, NOW()),
            retry_count = 0, ultimo_error_tecnico = NULL, updated_at = NOW()
        WHERE id = :did AND estado_sri IN ('FIRMADO', 'EN_REVISION', 'DEVUELTA')
    """), {"did": str(doc.id)})
    await db.commit()


async def registrar_error_tecnico(db: AsyncSession, doc_id, detalle: str) -> int:
    """Suma un intento técnico fallido y devuelve cuántos van."""
    res = await db.execute(text("""
        UPDATE documentos_emitidos
        SET retry_count = COALESCE(retry_count, 0) + 1,
            last_retry = NOW(),
            ultimo_error_tecnico = :detalle,
            updated_at = NOW()
        WHERE id = :did
        RETURNING retry_count
    """), {"did": str(doc_id), "detalle": (detalle or "")[:1000]})
    intentos = res.scalar() or 0
    await db.commit()
    return intentos


async def marcar_en_revision(db: AsyncSession, doc, detalle: str) -> None:
    """Falla técnica que no se pudo resolver sola. No toca stock ni crédito.
    Notifica al usuario para que sepa que su comprobante está pendiente."""
    await db.execute(text("""
        UPDATE documentos_emitidos
        SET estado_sri = 'EN_REVISION', ultimo_error_tecnico = :detalle, updated_at = NOW()
        WHERE id = :did AND estado_sri IN ('FIRMADO', 'RECIBIDA')
    """), {"did": str(doc.id), "detalle": (detalle or "")[:1000]})
    await db.commit()
    await invalidar_cache(doc.emisor_id)

    tipo_label = TIPO_DOC_LABEL.get(doc.tipo_doc, "Comprobante")
    numero     = doc.numero_doc or doc.clave_acceso[-10:]
    prefijo    = "🧪 [SANDBOX] " if doc.es_sandbox else ""

    await crear_notificacion(
        db         = db,
        emisor_id  = doc.emisor_id,
        tipo       = "DOCUMENTO",
        titulo     = f"{prefijo}⏳ {tipo_label} pendiente de autorización",
        mensaje    = f"{prefijo}{tipo_label} {numero}: el SRI no ha respondido. "
                     "Seguiremos reintentando automáticamente.",
        referencia = f"/documentos/{doc.id}",
    )

    print(f"[SRI] 🔎 EN_REVISION: {doc.clave_acceso} — {detalle}")


async def finalizar_autorizado(db: AsyncSession, doc_id, resp: sri.RespuestaSRI) -> bool:
    doc = await cargar_documento(db, doc_id, bloquear=True)
    if not doc or doc.estado_sri == "AUTORIZADO":
        await db.rollback()
        return False

    previo = doc.estado_sri
    if resp.comprobante:
        upload_file(doc.xml_path, resp.comprobante.encode("utf-8"), "text/xml")
    fecha = datetime.fromisoformat(resp.fecha.replace("Z", "+00:00")) if resp.fecha else datetime.utcnow()

    await db.execute(text("""
        UPDATE documentos_emitidos
        SET estado_sri = 'AUTORIZADO', fecha_autorizacion = :fecha,
            mensajes_sri = CAST(:msg AS jsonb), ultimo_error_tecnico = NULL,
            sri_verificado_at = NOW(), updated_at = NOW()
        WHERE id = :did
    """), {"fecha": fecha, "msg": json.dumps(resp.mensajes or []), "did": str(doc.id)})

    corregido = (previo in ("DEVUELTA", "RECHAZADO")
                 or doc.stock_estado == "REVERTIDO" or doc.credito_estado == "DEVUELTO")
    await stock_service.reaplicar(db, doc)
    await _reaplicar_credito(db, doc)
    await db.commit()
    await invalidar_cache(doc.emisor_id)

    tipo_label = TIPO_DOC_LABEL.get(doc.tipo_doc, "Comprobante")
    numero     = doc.numero_doc or doc.clave_acceso[-10:]
    prefijo    = "🧪 [SANDBOX] " if doc.es_sandbox else ""
    doc_dict   = _doc_dict(doc)

    await disparar_webhooks(doc.id, doc.emisor_id, "documento.autorizado", doc_dict)

    # ── Notificación push: solo si se corrigió un falso rechazo o si tardó mucho ──
    if corregido:
        await crear_notificacion(
            db         = db,
            emisor_id  = doc.emisor_id,
            tipo       = "DOCUMENTO",
            titulo     = f"{prefijo}✅ {tipo_label} autorizado (corregido)",
            mensaje    = f"{prefijo}{tipo_label} {numero} sí está autorizado por el SRI. "
                         "Corregimos el estado, el inventario y los créditos.",
            referencia = f"/documentos/{doc.id}",
        )
    elif _tardo_mucho(doc):
        await crear_notificacion(
            db         = db,
            emisor_id  = doc.emisor_id,
            tipo       = "DOCUMENTO",
            titulo     = f"{prefijo}✅ {tipo_label} autorizado",
            mensaje    = f"{prefijo}{tipo_label} {numero} autorizado por el SRI{' de pruebas' if doc.es_sandbox else ''}.",
            referencia = f"/documentos/{doc.id}",
        )

    # PDF y correo (fuera de la transacción)
    if doc.tipo_doc in ("FAC", "LIQ") and resp.comprobante:
        pdf_bytes = await generar_pdf(resp.comprobante, doc, resp.fecha or "")
        destino   = await _email_destino(db, doc)
        if destino:
            await enviar_email_comprobante(
                email=destino, razon_social=doc.razon_social, ruc=doc.ruc, tipo_doc=doc.tipo_doc,
                secuencial=doc.secuencial, clave_acceso=doc.clave_acceso,
                fecha_autorizacion=resp.fecha or "", xml_str=resp.comprobante,
                pdf_bytes=pdf_bytes, es_sandbox=doc.es_sandbox,
            )
    print(f"[SRI] ✅ AUTORIZADO{' (corregido desde ' + previo + ')' if corregido else ''}: {doc.clave_acceso}")
    return True


async def _rechazo_real(db: AsyncSession, doc_id, resp: sri.RespuestaSRI, estado: str) -> bool:
    """DEVUELTA (recepción) o RECHAZADO (autorización) confirmados por el SRI."""
    doc = await cargar_documento(db, doc_id, bloquear=True)
    if not doc or doc.estado_sri in ("AUTORIZADO", estado):
        await db.rollback()
        return False

    await db.execute(text("""
        UPDATE documentos_emitidos
        SET estado_sri = :estado, mensajes_sri = CAST(:msg AS jsonb),
            ultimo_error_tecnico = NULL, sri_verificado_at = NOW(), updated_at = NOW()
        WHERE id = :did
    """), {"estado": estado, "msg": json.dumps(resp.mensajes or []), "did": str(doc.id)})
    await stock_service.revertir(db, doc)
    await _revertir_credito(db, doc)
    await db.commit()
    await invalidar_cache(doc.emisor_id)

    tipo_label = TIPO_DOC_LABEL.get(doc.tipo_doc, "Comprobante")
    numero     = doc.numero_doc or doc.clave_acceso[-10:]
    prefijo    = "🧪 [SANDBOX] " if doc.es_sandbox else ""
    verbo      = "devuelto" if estado == "DEVUELTA" else "rechazado"
    icono      = "⚠️" if estado == "DEVUELTA" else "❌"

    await notificar_cambio_estado(_doc_dict(doc), estado, resp.mensajes)
    await crear_notificacion(
        db         = db,
        emisor_id  = doc.emisor_id,
        tipo       = "DOCUMENTO",
        titulo     = f"{prefijo}{icono} {tipo_label} {verbo} por el SRI",
        mensaje    = f"{prefijo}{tipo_label} {numero} fue {verbo}. Revisa los errores en el detalle.",
        referencia = f"/documentos/{doc.id}",
    )
    if estado == "RECHAZADO":
        await disparar_webhooks(doc.id, doc.emisor_id, "documento.rechazado", _doc_dict(doc))
    print(f"[SRI] {icono} {estado}: {doc.clave_acceso} — {sorted(resp.ids)}")
    return True


async def finalizar_devuelta(db: AsyncSession, doc_id, resp: sri.RespuestaSRI) -> bool:
    return await _rechazo_real(db, doc_id, resp, "DEVUELTA")


async def finalizar_rechazado(db: AsyncSession, doc_id, resp: sri.RespuestaSRI) -> bool:
    return await _rechazo_real(db, doc_id, resp, "RECHAZADO")


async def aplicar_respuesta_autorizacion(db: AsyncSession, doc, resp: sri.RespuestaSRI) -> bool:
    """
    Aplica una respuesta del servicio de autorización. Devuelve True si quedó resuelto
    (o en camino); False si el SRI no tiene el comprobante o hubo falla técnica.
    """
    if resp.estado == sri.AUTORIZADO:
        await finalizar_autorizado(db, doc.id, resp)
        return True
    if resp.estado == sri.NO_AUTORIZADO:
        await finalizar_rechazado(db, doc.id, resp)
        return True
    if resp.estado == sri.EN_PROCESO:
        if doc.estado_sri in ("FIRMADO", "EN_REVISION", "DEVUELTA"):
            await marcar_recibida(db, doc)
        await programar(QUEUE_AUTORIZACION, doc.id, 10)
        return True
    return False


# =============================================================================
# SINCRONIZAR CON EL SRI (conciliación y botón "Consultar en el SRI")
# =============================================================================
async def sincronizar_documento(db: AsyncSession, doc_id) -> dict:
    doc = await cargar_documento(db, doc_id)
    if not doc:
        return {"ok": False, "mensaje": "Documento no encontrado."}

    previo = doc.estado_sri
    resp   = await sri.consultar_autorizacion(doc.clave_acceso, ambiente_efectivo(doc))

    if resp.estado == sri.TECNICO:
        return {"ok": False, "sri": resp.estado, "estado_anterior": previo, "estado_actual": previo,
                "cambio": False, "mensaje": f"No pudimos consultar al SRI: {resp.resumen_tecnico()}"}

    if resp.estado == sri.NO_ENCONTRADO:
        await db.execute(text("UPDATE documentos_emitidos SET sri_verificado_at = NOW() WHERE id = :did"),
                         {"did": str(doc.id)})
        await db.commit()
        return {"ok": True, "sri": resp.estado, "estado_anterior": previo, "estado_actual": previo,
                "cambio": False, "mensaje": "El SRI no tiene registrado este comprobante."}

    await aplicar_respuesta_autorizacion(db, doc, resp)
    actual = (await cargar_documento(db, doc.id)).estado_sri
    mensajes = {
        sri.AUTORIZADO:    "El SRI confirma que el comprobante está AUTORIZADO.",
        sri.NO_AUTORIZADO: "El SRI confirma que el comprobante NO fue autorizado.",
        sri.EN_PROCESO:    "El SRI todavía está procesando el comprobante.",
    }
    return {"ok": True, "sri": resp.estado, "estado_anterior": previo, "estado_actual": actual,
            "cambio": previo != actual, "mensaje": mensajes.get(resp.estado, "")}


# =============================================================================
# EFECTOS: webhooks, PDF, correo
# =============================================================================
async def disparar_webhooks(doc_id, emisor_id: int, evento: str, payload: dict):
    from app.core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        try:
            res = await db.execute(text("""
                SELECT url, secret FROM webhooks
                WHERE emisor_id = :eid AND activo = true AND eventos @> CAST(:evento AS jsonb)
            """), {"eid": emisor_id, "evento": json.dumps([evento])})
            webhooks = res.fetchall()
            if not webhooks:
                return
            body = json.dumps({
                "evento":    evento,
                "doc_id":    str(doc_id),
                "timestamp": datetime.utcnow().isoformat(),
                "data":      payload,
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


async def generar_pdf(xml_autorizado: str, doc, fecha_auth_str: str) -> bytes | None:
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
        print(f"[SRI] ⚠️ Error generando PDF: {e}")
    return None


async def _email_destino(db: AsyncSession, doc) -> str | None:
    """Sandbox: al dueño de la empresa. Producción: al comprador."""
    if not doc.es_sandbox:
        return doc.email_comprador
    res = await db.execute(text("""
        SELECT p.email FROM profiles p
        JOIN emisor_usuarios eu ON eu.profile_id = p.id
        WHERE eu.emisor_id = :eid
        ORDER BY eu.created_at ASC
        LIMIT 1
    """), {"eid": doc.emisor_id})
    fila = res.fetchone()
    return fila.email if fila else None


async def enviar_email_comprobante(*, email, razon_social, ruc, tipo_doc, secuencial, clave_acceso,
                                   fecha_autorizacion, xml_str, pdf_bytes, es_sandbox=False):
    try:
        await mail_service.send_comprobante(
            email=email, razon_social=razon_social, ruc=ruc, tipo_doc=tipo_doc,
            secuencial=secuencial, clave_acceso=clave_acceso,
            fecha_autorizacion=fecha_autorizacion, xml_str=xml_str,
            pdf_bytes=pdf_bytes, es_sandbox=es_sandbox,
        )
    except Exception as e:
        print(f"[SRI] ⚠️ Error enviando email: {e}")