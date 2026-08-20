# app/api/v1/public/invoices.py
#
# Endpoints públicos para consulta y descarga de comprobantes.
# No requieren autenticación — solo clave de acceso válida.
# Soporta todos los tipos: FAC | LIQ | NCR | NDB | RET

import re
import base64
import httpx
from typing import Optional
from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from pydantic import BaseModel

from app.core.database import get_db
from app.core.security import verify_public_origin
from app.core.cache import get_redis
from app.core.config import settings
from app.services.storage_service import download_file

router = APIRouter()

NODE_PDF_URL = f"{settings.NODE_SIGNER_URL}/api/pdf"

REGEX_CLAVE = re.compile(r"^\d{49}$")

LABELS_TIPO_DOC = {
    "01": "Factura",
    "03": "Liquidación de Compra",
    "04": "Nota de Crédito",
    "05": "Nota de Débito",
    "07": "Retención",
}


# =============================================================================
# SCHEMAS
# =============================================================================

class ConsultarRequest(BaseModel):
    captchaToken: str
    hpValue:      Optional[str] = None


# =============================================================================
# GET /pdf/{clave_acceso}
# =============================================================================

@router.get("/pdf/{clave_acceso}", summary="Descargar RIDE (PDF)")
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
                d.estado_sri, d.xml_path, d.fecha_autorizacion, d.tipo_doc,
                e.contribuyente_especial
            FROM documentos_emitidos d
            JOIN emisores e ON d.emisor_id = e.id
            WHERE d.clave_acceso = :clave
        """), {"clave": clave_acceso})

        doc = res.fetchone()
        if not doc:
            return JSONResponse(status_code=404, content={"error": "Documento no encontrado."})

        if doc.estado_sri != "AUTORIZADO" or not doc.xml_path:
            return JSONResponse(status_code=404, content={"error": "Documento no autorizado o sin XML."})

        xml_bytes  = download_file(doc.xml_path)
        xml_str    = xml_bytes.decode("utf-8")
        fecha_auth = doc.fecha_autorizacion.strftime("%d/%m/%Y %H:%M:%S") if doc.fecha_autorizacion else None

        async with httpx.AsyncClient(timeout=15.0) as client:
            res_pdf = await client.post(NODE_PDF_URL, json={
                "xmlAutorizado":     xml_str,
                "emisor":            {"contribuyente_especial": doc.contribuyente_especial or ""},
                "fechaAutorizacion": fecha_auth,
                "formato":           formato,
            })

        if res_pdf.status_code != 200 or not res_pdf.json().get("ok"):
            return JSONResponse(status_code=500, content={"error": "Error generando PDF."})

        pdf_bytes = base64.b64decode(res_pdf.json()["pdfBase64"])

        # Guardar en cache
        try:
            await redis.setex(cache_key, 7200, pdf_bytes)
        except Exception as e:
            print(f"[PDF Cache] ⚠️ Error guardando: {e}")

        return Response(
            content    = pdf_bytes,
            media_type = "application/pdf",
            headers    = {
                "Content-Disposition": f'inline; filename="{clave_acceso}.pdf"',
                "Cache-Control":       "public, max-age=7200",
                "X-Cache":             "MISS",
            }
        )

    except Exception as e:
        print(f"[PDF] ❌ {e}")
        return JSONResponse(status_code=500, content={"error": "Error generando PDF."})


# =============================================================================
# GET /xml/{clave_acceso}
# =============================================================================

@router.get("/xml/{clave_acceso}", summary="Descargar XML autorizado")
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
            SELECT estado_sri, xml_path
            FROM documentos_emitidos
            WHERE clave_acceso = :clave
        """), {"clave": clave_acceso})

        doc = res.fetchone()
        if not doc:
            return JSONResponse(status_code=404, content={"error": "Documento no encontrado."})

        if doc.estado_sri != "AUTORIZADO" or not doc.xml_path:
            return JSONResponse(status_code=404, content={"error": "Documento no autorizado o sin XML."})

        file_bytes = download_file(doc.xml_path)

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
# POST /consultar/{clave_acceso}
# =============================================================================

@router.post("/consultar/{clave_acceso}", summary="Consultar comprobante por clave de acceso")
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

    # Verificar Turnstile
    try:
        async with httpx.AsyncClient() as client:
            cf_resp = await client.post(
                "https://challenges.cloudflare.com/turnstile/v0/siteverify",
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
    except httpx.HTTPError as e:
        print(f"[Turnstile] ⚠️ Error: {e}")
        return JSONResponse(status_code=500, content={"error": "Error de validación externa."})

    try:
        res = await db.execute(text("""
            SELECT
                d.clave_acceso, d.numero_doc, d.tipo_doc, d.cod_doc,
                d.fecha_emision, d.estado_sri, d.mensajes_sri,
                d.importe_total,
                e.razon_social AS emisor_nombre,
                e.ruc          AS emisor_ruc
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
            return {
                "success": True,
                "estado":  "AUTORIZADO",
                "data": {
                    "cabecera": {
                        "tipo":    tipo_label,
                        "emisor":  doc.emisor_nombre,
                        "ruc":     doc.emisor_ruc,
                        "numero":  doc.numero_doc,
                        "fecha":   str(doc.fecha_emision),
                    },
                    "totales": {
                        "total": float(doc.importe_total),
                    },
                    "links": {
                        "pdf": f"{base_url}/api/v1/public/pdf/{clave_acceso}",
                        "xml": f"{base_url}/api/v1/public/xml/{clave_acceso}",
                    }
                }
            }

        elif estado in ("RECIBIDA", "FIRMADO"):
            return JSONResponse(status_code=200, content={
                "success":         False,
                "estado":          estado,
                "mensaje_usuario": "El comprobante fue enviado al SRI y está en proceso de autorización.",
            })

        elif estado in ("DEVUELTA", "RECHAZADO"):
            return JSONResponse(status_code=200, content={
                "success":         False,
                "estado":          estado,
                "mensaje_usuario": f"El {tipo_label.lower()} presenta inconsistencias y fue {estado.lower()} por el SRI.",
                "detalles_sri":    doc.mensajes_sri,
                "sugerencia":      f"Contacta al emisor ({doc.emisor_nombre}) para resolver este inconveniente.",
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