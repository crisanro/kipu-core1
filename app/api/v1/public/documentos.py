# app/api/v1/public/invoices.py
#
# Endpoints públicos para consulta y descarga de comprobantes.
# No requieren autenticación — solo clave de acceso válida.
# Soporta todos los tipos: FAC | LIQ | NCR | NDB | RET
#
# PDF:
#   - AUTORIZADO → RIDE oficial (con fecha y número de autorización)
#   - FIRMADO / RECIBIDA / EN_REVISION → PDF provisional desde el XML firmado,
#     sin fecha de autorización. El frontend o el Node de PDF debe mostrar
#     "PENDIENTE DE AUTORIZACIÓN" como marca. Se cachea solo 30 seg (va a cambiar pronto).
#   - DEVUELTA / RECHAZADO / ANULADO → no se genera PDF.

import re
import json
import base64
import asyncio
import httpx
from typing import Optional, Any, List
from fastapi import APIRouter, Depends, Request, Header, HTTPException
from fastapi.responses import Response, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.security import verify_public_origin, verify_api_key
from app.core.cache import get_redis
from app.core.config import settings
from app.core.http_clients import pdf_client, turnstile_client
from app.services.storage_service import download_file

router = APIRouter()

REGEX_CLAVE = re.compile(r"^\d{49}$")

LABELS_TIPO_DOC = {
    "01": "Factura",
    "03": "Liquidación de Compra",
    "04": "Nota de Crédito",
    "05": "Nota de Débito",
    "07": "Retención",
}

# Estados en los que el documento está en tránsito al SRI
_ESTADOS_EN_PROCESO = ("FIRMADO", "RECIBIDA", "EN_REVISION")

# Estados en los que se puede generar PDF (autorizado o en proceso)
_ESTADOS_CON_PDF = ("AUTORIZADO", *_ESTADOS_EN_PROCESO)

# Cache corto para PDFs provisionales (el estado va a cambiar pronto)
_TTL_PDF_PROVISIONAL = 30    # 30 segundos
_TTL_PDF_AUTORIZADO  = 7200  # 2 horas


# =============================================================================
# SCHEMAS
# =============================================================================

class ConsultarRequest(BaseModel):
    captchaToken: str
    hpValue:      Optional[str] = None


class ErrorPublicResponse(BaseModel):
    """Respuesta de error genérica."""
    error: str = Field(..., description="Descripción del error")


class EstadoDocumentoResponse(BaseModel):
    """Estado de un comprobante consultado por clave de acceso."""
    ok:                  bool          = Field(True, description="Siempre true si se encontró el documento")
    clave_acceso:        str           = Field(..., description="Clave de acceso de 49 dígitos", examples=["2210202601091234567800110010010000001231234567816"])
    tipo_doc:            str           = Field(..., description="Código interno: FAC, LIQ, NCR, NDB, RET", examples=["FAC"])
    tipo_doc_descripcion: str          = Field(..., description="Nombre legible del tipo de documento", examples=["Factura"])
    numero_doc:          Optional[str] = Field(None, description="Número del comprobante (est-pto-sec)", examples=["001-001-000000123"])
    estado_sri:          str           = Field(..., description="Estado SRI: FIRMADO, RECIBIDA, EN_REVISION, AUTORIZADO, DEVUELTA, RECHAZADO, ANULADO", examples=["AUTORIZADO"])
    fecha_emision:       str           = Field(..., description="Fecha de emisión (YYYY-MM-DD)", examples=["2026-10-22"])
    fecha_autorizacion:  Optional[str] = Field(None, description="Fecha/hora de autorización SRI (dd/mm/yyyy HH:MM:SS)", examples=["22/10/2026 14:35:20"])
    importe_total:       float         = Field(..., description="Importe total del comprobante", examples=[115.00])
    comprador_nombre:    Optional[str] = Field(None, description="Razón social del comprador/proveedor/sujeto retenido", examples=["Juan Pérez"])
    comprador_id:        Optional[str] = Field(None, description="Identificación del comprador", examples=["1722334455"])
    mensajes_sri:        Optional[Any] = Field(None, description="Mensajes del SRI (solo si fue devuelta/rechazada)")
    links:               Optional[dict] = Field(None, description="Links de descarga (PDF y XML) — solo si está AUTORIZADO o en proceso")


# =============================================================================
# HELPERS
# =============================================================================

def _respuesta_no_descargable(estado_sri: str, tipo: str = "documento") -> JSONResponse:
    """Respuesta cuando el documento NO puede generar PDF (rechazado/anulado)."""
    if estado_sri in ("DEVUELTA", "RECHAZADO"):
        return JSONResponse(status_code=422, content={
            "error":   f"Comprobante {estado_sri.lower()} por el SRI.",
            "estado":  estado_sri,
            "mensaje": f"El {tipo} fue {estado_sri.lower()} por el SRI. "
                       "Contacta al emisor para más información.",
        })
    if estado_sri == "ANULADO":
        return JSONResponse(status_code=410, content={
            "error":   "Comprobante anulado.",
            "estado":  estado_sri,
            "mensaje": f"El {tipo} fue anulado y ya no tiene validez tributaria.",
        })
    return JSONResponse(status_code=404, content={
        "error":   f"Comprobante en estado: {estado_sri}.",
        "estado":  estado_sri,
        "mensaje": f"El {tipo} no está disponible para descarga en este momento.",
    })


# =============================================================================
# GET /estado/{clave_acceso}  — Consulta autenticada por API Key
# =============================================================================

@router.get(
    "/estado/{clave_acceso}",
    summary="Consultar estado de un comprobante por clave de acceso",
    tags=["🔍 Consultas", "public_export"],
    description=(
        "Devuelve el estado actual de un comprobante emitido, identificado por su clave de acceso "
        "de 49 dígitos.\n\n"
        "**Requiere autenticación** con `X-Api-Key`. Solo devuelve documentos que pertenecen "
        "al emisor autenticado — si la clave de acceso corresponde a otro emisor, responde 404.\n\n"
        "**Estados posibles:**\n"
        "- `FIRMADO` — XML firmado, pendiente de envío al SRI.\n"
        "- `RECIBIDA` — El SRI recibió el comprobante, pendiente de autorización.\n"
        "- `EN_REVISION` — El SRI está procesando el comprobante.\n"
        "- `AUTORIZADO` — Comprobante válido y autorizado por el SRI.\n"
        "- `DEVUELTA` — El SRI rechazó el envío (error de estructura o validación).\n"
        "- `RECHAZADO` — El SRI no autorizó el comprobante.\n"
        "- `ANULADO` — Comprobante anulado manualmente.\n\n"
        "**Links de descarga:** se incluyen `pdf` y `xml` cuando el documento está AUTORIZADO "
        "o en proceso de autorización."
    ),
    response_model=EstadoDocumentoResponse,
    responses={
        400: {"model": ErrorPublicResponse, "description": "Clave de acceso inválida (no son 49 dígitos)."},
        401: {"model": ErrorPublicResponse, "description": "API Key inválida o no proporcionada."},
        404: {"model": ErrorPublicResponse, "description": "Documento no encontrado o no pertenece al emisor autenticado."},
        500: {"model": ErrorPublicResponse, "description": "Error interno del servidor."},
    },
)
async def get_estado_documento(
    clave_acceso: str,
    auth:         dict         = Depends(verify_api_key),
    db:           AsyncSession = Depends(get_db),
):
    if not REGEX_CLAVE.match(clave_acceso):
        raise HTTPException(status_code=400, detail="Clave de acceso inválida. Debe ser exactamente 49 dígitos numéricos.")

    emisor_id = auth["emisor_id"]

    try:
        res = await db.execute(text("""
            SELECT
                d.clave_acceso, d.tipo_doc, d.cod_doc, d.numero_doc,
                d.estado_sri, d.fecha_emision, d.fecha_autorizacion,
                d.importe_total, d.mensajes_sri,
                COALESCE(
                    d.datos->'infoFactura'->>'razonSocialComprador',
                    d.datos->'infoLiquidacionCompra'->>'razonSocialProveedor',
                    d.datos->'infoNotaCredito'->>'razonSocialComprador',
                    d.datos->'infoNotaDebito'->>'razonSocialComprador',
                    d.datos->'infoCompRetencion'->>'razonSocialSujetoRetenido'
                ) AS comprador_nombre,
                COALESCE(
                    d.datos->'infoFactura'->>'identificacionComprador',
                    d.datos->'infoLiquidacionCompra'->>'identificacionProveedor',
                    d.datos->'infoNotaCredito'->>'identificacionComprador',
                    d.datos->'infoNotaDebito'->>'identificacionComprador',
                    d.datos->'infoCompRetencion'->>'identificacionSujetoRetenido'
                ) AS comprador_id
            FROM documentos_emitidos d
            WHERE d.clave_acceso = :clave
              AND d.emisor_id = :emisor_id
        """), {"clave": clave_acceso, "emisor_id": emisor_id})

        doc = res.fetchone()
        if not doc:
            raise HTTPException(status_code=404, detail="Documento no encontrado o no pertenece al emisor autenticado.")

        tipo_label = LABELS_TIPO_DOC.get(doc.cod_doc, "Comprobante")
        base_url   = settings.BACKEND_URL

        # Links de descarga solo si tiene PDF disponible
        links = None
        if doc.estado_sri in _ESTADOS_CON_PDF:
            links = {
                "pdf": f"{base_url}/api/v1/public/pdf/{clave_acceso}",
                "xml": f"{base_url}/api/v1/public/xml/{clave_acceso}" if doc.estado_sri == "AUTORIZADO" else None,
            }

        fecha_auth = None
        if doc.fecha_autorizacion:
            fecha_auth = doc.fecha_autorizacion.strftime("%d/%m/%Y %H:%M:%S")

        return {
            "ok":                  True,
            "clave_acceso":        doc.clave_acceso,
            "tipo_doc":            doc.tipo_doc,
            "tipo_doc_descripcion": tipo_label,
            "numero_doc":          doc.numero_doc,
            "estado_sri":          doc.estado_sri,
            "fecha_emision":       str(doc.fecha_emision),
            "fecha_autorizacion":  fecha_auth,
            "importe_total":       float(doc.importe_total),
            "comprador_nombre":    doc.comprador_nombre,
            "comprador_id":        doc.comprador_id,
            "mensajes_sri":        doc.mensajes_sri if doc.estado_sri in ("DEVUELTA", "RECHAZADO") else None,
            "links":               links,
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"[Estado] ❌ {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor.")


# =============================================================================
# GET /pdf/{clave_acceso}
# =============================================================================

@router.get(
    "/pdf/{clave_acceso}",
    summary="Descargar RIDE (PDF)",
    tags=["📥 Descargas", "public_export"],
    description=(
        "Descarga el RIDE (Representación Impresa del Documento Electrónico) en formato PDF.\n\n"
        "**No requiere autenticación** — cualquiera con la clave de acceso puede descargar.\n\n"
        "**Comportamiento según estado:**\n"
        "- `AUTORIZADO` → RIDE oficial con fecha y número de autorización SRI. Cache: 2 horas.\n"
        "- `FIRMADO` / `RECIBIDA` / `EN_REVISION` → PDF provisional con marca \"PENDIENTE DE AUTORIZACIÓN\". Cache: 30 seg.\n"
        "- `DEVUELTA` / `RECHAZADO` → Error 422.\n"
        "- `ANULADO` → Error 410.\n\n"
        "**Parámetro `formato`:** `a4` (default) o `ticket` para impresión térmica."
    ),
    responses={
        200: {"content": {"application/pdf": {}}, "description": "PDF del RIDE generado correctamente."},
        400: {"model": ErrorPublicResponse, "description": "Clave de acceso inválida."},
        404: {"model": ErrorPublicResponse, "description": "Documento no encontrado o XML no disponible."},
        410: {"model": ErrorPublicResponse, "description": "Comprobante anulado."},
        422: {"model": ErrorPublicResponse, "description": "Comprobante rechazado/devuelto por el SRI."},
        500: {"model": ErrorPublicResponse, "description": "Error generando el PDF."},
    },
)
async def get_pdf(
    clave_acceso: str,
    formato:      str          = "a4",
    db:           AsyncSession = Depends(get_db),
):
    if not REGEX_CLAVE.match(clave_acceso):
        return JSONResponse(status_code=400, content={"error": "Clave de acceso inválida."})

    # Cache Redis
    cache_key = f"kipu:pdf:{clave_acceso}:{formato}"
    try:
        redis      = await get_redis()
        cached_pdf = await redis.get(cache_key)
        if cached_pdf:
            return Response(
                content    = cached_pdf,
                media_type = "application/pdf",
                headers    = {
                    "Content-Disposition": f'inline; filename="{clave_acceso}.pdf"',
                    "X-Cache": "HIT",
                }
            )
    except Exception as e:
        print(f"[PDF Cache] ⚠️ {e}")

    try:
        res = await db.execute(text("""
            SELECT
                d.estado_sri, d.xml_path, d.fecha_autorizacion, d.tipo_doc, d.cod_doc,
                e.contribuyente_especial
            FROM documentos_emitidos d
            JOIN emisores e ON d.emisor_id = e.id
            WHERE d.clave_acceso = :clave
        """), {"clave": clave_acceso})

        doc = res.fetchone()
        if not doc:
            return JSONResponse(status_code=404, content={"error": "Documento no encontrado."})

        # Solo AUTORIZADO y estados en proceso pueden generar PDF
        if doc.estado_sri not in _ESTADOS_CON_PDF:
            tipo_label = LABELS_TIPO_DOC.get(doc.cod_doc, "comprobante").lower()
            return _respuesta_no_descargable(doc.estado_sri, tipo_label)

        if not doc.xml_path:
            return JSONResponse(status_code=404, content={"error": "XML no disponible."})

        es_autorizado = doc.estado_sri == "AUTORIZADO"

        # asyncio.to_thread() evita bloquear el event loop en I/O síncrono
        xml_bytes  = await asyncio.to_thread(download_file, doc.xml_path)
        xml_str    = xml_bytes.decode("utf-8")

        # AUTORIZADO → fecha real de autorización
        # EN PROCESO → None, el generador de PDF debe mostrar "PENDIENTE DE AUTORIZACIÓN"
        fecha_auth = None
        if es_autorizado and doc.fecha_autorizacion:
            fecha_auth = doc.fecha_autorizacion.strftime("%d/%m/%Y %H:%M:%S")

        # Cliente HTTP compartido — reutiliza conexiones TCP/TLS
        res_pdf = await pdf_client.post("/api/pdf", json={
            "xmlAutorizado":     xml_str,
            "emisor":            {"contribuyente_especial": doc.contribuyente_especial or ""},
            "fechaAutorizacion": fecha_auth,
            "formato":           formato,
            "provisional":       not es_autorizado,
        })

        if res_pdf.status_code != 200 or not res_pdf.json().get("ok"):
            return JSONResponse(status_code=500, content={"error": "Error generando PDF."})

        pdf_bytes = base64.b64decode(res_pdf.json()["pdfBase64"])

        # Cachear: AUTORIZADO → 2 horas, EN PROCESO → 30 seg (va a cambiar)
        ttl_cache = _TTL_PDF_AUTORIZADO if es_autorizado else _TTL_PDF_PROVISIONAL
        try:
            await redis.setex(cache_key, ttl_cache, pdf_bytes)
        except Exception as e:
            print(f"[PDF Cache] ⚠️ Error guardando: {e}")

        # Headers distintos: el provisional no se cachea en el browser
        cache_control = f"public, max-age={ttl_cache}" if es_autorizado else "no-cache, no-store"
        extra_headers = {
            "Content-Disposition": f'inline; filename="{clave_acceso}.pdf"',
            "Cache-Control":       cache_control,
            "X-Cache":             "MISS",
        }
        if not es_autorizado:
            extra_headers["X-Documento-Estado"] = doc.estado_sri

        return Response(
            content    = pdf_bytes,
            media_type = "application/pdf",
            headers    = extra_headers,
        )

    except Exception as e:
        print(f"[PDF] ❌ {e}")
        return JSONResponse(status_code=500, content={"error": "Error generando PDF."})


# =============================================================================
# GET /xml/{clave_acceso}
# =============================================================================

@router.get(
    "/xml/{clave_acceso}",
    summary="Descargar XML autorizado",
    tags=["📥 Descargas", "public_export"],
    description=(
        "Descarga el XML autorizado del comprobante electrónico.\n\n"
        "**No requiere autenticación** — cualquiera con la clave de acceso puede descargar.\n\n"
        "**Solo disponible en estado `AUTORIZADO`** — el XML firmado sin autorización del SRI "
        "no tiene validez tributaria.\n\n"
        "- `FIRMADO` / `RECIBIDA` / `EN_REVISION` → 202 Accepted (en proceso, reintenta luego).\n"
        "- `DEVUELTA` / `RECHAZADO` / `ANULADO` → Error con detalle del estado."
    ),
    responses={
        200: {"content": {"application/xml": {}}, "description": "XML autorizado del comprobante."},
        202: {"model": ErrorPublicResponse, "description": "Comprobante en proceso de autorización. Reintenta en unos minutos."},
        400: {"model": ErrorPublicResponse, "description": "Clave de acceso inválida."},
        404: {"model": ErrorPublicResponse, "description": "Documento no encontrado."},
        410: {"model": ErrorPublicResponse, "description": "Comprobante anulado."},
        422: {"model": ErrorPublicResponse, "description": "Comprobante rechazado/devuelto por el SRI."},
        500: {"model": ErrorPublicResponse, "description": "Error interno."},
    },
)
async def get_xml(
    clave_acceso: str,
    db:           AsyncSession = Depends(get_db),
):
    if not REGEX_CLAVE.match(clave_acceso):
        return JSONResponse(status_code=400, content={"error": "Clave de acceso inválida."})

    cache_key = f"kipu:xml:{clave_acceso}"
    try:
        redis      = await get_redis()
        cached_xml = await redis.get(cache_key)
        if cached_xml:
            return Response(
                content    = cached_xml,
                media_type = "application/xml",
                headers    = {
                    "Content-Disposition": f'attachment; filename="{clave_acceso}.xml"',
                    "X-Cache": "HIT",
                }
            )
    except Exception as e:
        print(f"[XML Cache] ⚠️ {e}")

    try:
        res = await db.execute(text("""
            SELECT estado_sri, xml_path, cod_doc
            FROM documentos_emitidos
            WHERE clave_acceso = :clave
        """), {"clave": clave_acceso})

        doc = res.fetchone()
        if not doc:
            return JSONResponse(status_code=404, content={"error": "Documento no encontrado."})

        # XML: solo AUTORIZADO (el XML firmado sin autorización no tiene validez tributaria)
        if doc.estado_sri != "AUTORIZADO":
            tipo_label = LABELS_TIPO_DOC.get(doc.cod_doc, "comprobante").lower()
            if doc.estado_sri in _ESTADOS_EN_PROCESO:
                return JSONResponse(status_code=202, content={
                    "error":   "Comprobante en proceso de autorización.",
                    "estado":  doc.estado_sri,
                    "mensaje": f"El {tipo_label} está en proceso de autorización. "
                               "El XML estará disponible una vez autorizado.",
                })
            return _respuesta_no_descargable(doc.estado_sri, tipo_label)

        if not doc.xml_path:
            return JSONResponse(status_code=404, content={"error": "XML autorizado no disponible."})

        file_bytes = await asyncio.to_thread(download_file, doc.xml_path)

        try:
            await redis.setex(cache_key, 7200, file_bytes)
        except Exception as e:
            print(f"[XML Cache] ⚠️ Error guardando: {e}")

        return Response(
            content    = file_bytes,
            media_type = "application/xml",
            headers    = {
                "Content-Disposition": f'attachment; filename="{clave_acceso}.xml"',
                "Cache-Control":       "public, max-age=7200",
                "X-Cache":             "MISS",
            }
        )

    except Exception as e:
        print(f"[XML] ❌ {e}")
        return JSONResponse(status_code=500, content={"error": "Archivo no encontrado."})


# =============================================================================
# POST /consultar/{clave_acceso}  — Consulta pública con captcha
# =============================================================================

@router.post(
    "/consultar/{clave_acceso}",
    summary="Consultar comprobante público (con captcha)",
    tags=["🔍 Consultas", "public_export"],
    description=(
        "Consulta de un comprobante para el **comprador/receptor**.\n\n"
        "⚠️ **Este endpoint NO es de uso abierto.** Funciona exclusivamente desde la "
        "página de consulta de Kipu (`consulta.kipu.ec`), ya que requiere un token válido "
        "de **Cloudflare Turnstile** que solo se genera en esa página.\n\n"
        "No requiere API Key, pero las peticiones sin un `captchaToken` válido "
        "serán rechazadas con `403`.\n\n"
        "Devuelve los datos completos del comprobante: emisor, comprador, totales, impuestos "
        "y links de descarga (PDF/XML) si está AUTORIZADO."
    ),
    responses={
        200: {"description": "Datos del comprobante (puede ser success=true o false según el estado)."},
        400: {"model": ErrorPublicResponse, "description": "Clave de acceso inválida o bot detectado."},
        403: {"model": ErrorPublicResponse, "description": "Verificación de captcha fallida."},
        404: {"model": ErrorPublicResponse, "description": "Comprobante no encontrado."},
        500: {"model": ErrorPublicResponse, "description": "Error interno."},
    },
)
async def consultar_comprobante(
    clave_acceso: str,
    request:      Request,
    body:         ConsultarRequest,
    _auth=Depends(verify_public_origin),
    db:           AsyncSession = Depends(get_db),
):
    if body.hpValue:
        return JSONResponse(status_code=400, content={"error": "Bot detectado."})
    if not REGEX_CLAVE.match(clave_acceso):
        return JSONResponse(status_code=400, content={"error": "Clave de acceso inválida."})

    # Verificar Turnstile — cliente compartido con timeout de 10s
    try:
        cf_resp = await turnstile_client.post(
            "/turnstile/v0/siteverify",
            data={
                "secret":   settings.TURNSTILE_SECRET_KEY,
                "response": body.captchaToken,
                "remoteip": request.client.host,
            }
        )
        if not cf_resp.json().get("success"):
            return JSONResponse(status_code=403, content={
                "success":         False,
                "mensaje_usuario": "La verificación de seguridad falló. Intenta de nuevo.",
            })
    except httpx.TimeoutException:
        print("[Turnstile] ⚠️ Timeout verificando captcha")
        return JSONResponse(status_code=500, content={"error": "Timeout en validación de seguridad."})
    except httpx.HTTPError as e:
        print(f"[Turnstile] ⚠️ Error: {e}")
        return JSONResponse(status_code=500, content={"error": "Error de validación externa."})

    # Cache Redis
    cache_key = f"kipu:consulta:{clave_acceso}"
    try:
        redis  = await get_redis()
        cached = await redis.get(cache_key)
        if cached:
            return JSONResponse(content=json.loads(cached))
    except Exception as e:
        print(f"[Consulta Cache] ⚠️ {e}")

    try:
        res = await db.execute(text("""
            SELECT
                d.clave_acceso, d.numero_doc, d.tipo_doc, d.cod_doc,
                d.fecha_emision, d.fecha_autorizacion,
                d.estado_sri, d.mensajes_sri,
                d.importe_total, d.datos,
                e.razon_social  AS emisor_nombre,
                e.ruc           AS emisor_ruc,
                e.direccion_matriz,
                -- Comprador según tipo de doc
                COALESCE(
                    d.datos->'infoFactura'->>'razonSocialComprador',
                    d.datos->'infoLiquidacionCompra'->>'razonSocialProveedor',
                    d.datos->'infoNotaCredito'->>'razonSocialComprador',
                    d.datos->'infoNotaDebito'->>'razonSocialComprador',
                    d.datos->'infoCompRetencion'->>'razonSocialSujetoRetenido'
                ) AS comprador_nombre,
                COALESCE(
                    d.datos->'infoFactura'->>'identificacionComprador',
                    d.datos->'infoLiquidacionCompra'->>'identificacionProveedor',
                    d.datos->'infoNotaCredito'->>'identificacionComprador',
                    d.datos->'infoNotaDebito'->>'identificacionComprador',
                    d.datos->'infoCompRetencion'->>'identificacionSujetoRetenido'
                ) AS comprador_id,
                -- Totales
                COALESCE(
                    (d.datos->'infoFactura'->>'totalSinImpuestos')::numeric,
                    (d.datos->'infoLiquidacionCompra'->>'totalSinImpuestos')::numeric,
                    (d.datos->'infoNotaCredito'->>'totalSinImpuestos')::numeric
                ) AS subtotal,
                -- Resumen impuestos
                d.datos->'resumenImpuestos' AS impuestos
            FROM documentos_emitidos d
            JOIN emisores e ON d.emisor_id = e.id
            WHERE d.clave_acceso = :clave
        """), {"clave": clave_acceso})
        doc = res.fetchone()

        if not doc:
            return JSONResponse(status_code=404, content={
                "success":         False,
                "mensaje_usuario": "El comprobante no existe en nuestro sistema. Verifica la clave de acceso.",
            })

        estado     = doc.estado_sri
        tipo_label = LABELS_TIPO_DOC.get(doc.cod_doc, "Comprobante")
        base_url   = settings.BACKEND_URL

        if estado == "AUTORIZADO":
            # Procesar impuestos
            impuestos_raw = doc.impuestos or []
            impuestos     = []
            total_iva     = 0.0
            for imp in impuestos_raw:
                base  = float(imp.get("baseImponible", 0))
                valor = float(imp.get("valor", imp.get("valorImpuesto", 0)))
                tarifa = imp.get("tarifa", imp.get("codigoPorcentaje", ""))
                total_iva += valor
                impuestos.append({
                    "tarifa":  tarifa,
                    "base":    round(base, 2),
                    "valor":   round(valor, 2),
                })

            subtotal = float(doc.subtotal or 0)
            total    = float(doc.importe_total)

            response_data = {
                "success": True,
                "estado":  "AUTORIZADO",
                "data": {
                    "cabecera": {
                        "tipo":              tipo_label,
                        "emisor":            doc.emisor_nombre,
                        "ruc":               doc.emisor_ruc,
                        "direccion":         doc.direccion_matriz,
                        "numero":            doc.numero_doc,
                        "fecha_emision":     str(doc.fecha_emision),
                        "fecha_autorizacion": doc.fecha_autorizacion.strftime("%d/%m/%Y %H:%M:%S") if doc.fecha_autorizacion else None,
                        "clave_acceso":      clave_acceso,
                    },
                    "comprador": {
                        "nombre":          doc.comprador_nombre,
                        "identificacion":  doc.comprador_id,
                    },
                    "totales": {
                        "subtotal":   round(subtotal, 2),
                        "impuestos":  impuestos,
                        "total_iva":  round(total_iva, 2),
                        "total":      round(total, 2),
                    },
                    "links": {
                        "pdf": f"{base_url}/api/v1/public/pdf/{clave_acceso}",
                        "xml": f"{base_url}/api/v1/public/xml/{clave_acceso}",
                    }
                }
            }

            # Cachear 2 horas
            try:
                await redis.setex(cache_key, 7200, json.dumps(response_data))
            except Exception as e:
                print(f"[Consulta Cache] ⚠️ Error guardando: {e}")

            return response_data

        elif estado in _ESTADOS_EN_PROCESO:
            return JSONResponse(status_code=200, content={
                "success":         False,
                "estado":          estado,
                "mensaje_usuario": f"El {tipo_label.lower()} fue enviado al SRI y está en proceso de autorización. "
                                   "Intenta consultar de nuevo en unos minutos.",
            })

        elif estado in ("DEVUELTA", "RECHAZADO"):
            return JSONResponse(status_code=200, content={
                "success":         False,
                "estado":          estado,
                "mensaje_usuario": f"El {tipo_label.lower()} presenta inconsistencias y fue {estado.lower()} por el SRI.",
                "detalles_sri":    doc.mensajes_sri,
                "sugerencia":      f"Contacta al emisor ({doc.emisor_nombre}) para resolver este inconveniente.",
            })

        elif estado == "ANULADO":
            return JSONResponse(status_code=200, content={
                "success":         False,
                "estado":          estado,
                "mensaje_usuario": f"El {tipo_label.lower()} fue anulado y ya no tiene validez tributaria.",
            })

        else:
            return JSONResponse(status_code=200, content={
                "success":         False,
                "estado":          estado,
                "mensaje_usuario": f"El comprobante se encuentra en estado: {estado}.",
            })

    except Exception as e:
        print(f"[Consulta] ❌ {e}")
        return JSONResponse(status_code=500, content={"error": "Error interno del servidor."})