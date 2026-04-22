import os
import re
import httpx
from typing import Optional
from fastapi import APIRouter, Depends, Request, Header
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from pydantic import BaseModel

from app.core.database import get_db
from app.services.storage_service import minio_client 
from app.core.config import settings

# 👇 Importamos TU función de seguridad real
from app.core.security import verify_public_origin 

router = APIRouter()

# --- SCHEMAS ---
class ConsultarFacturaRequest(BaseModel):
    captchaToken: str
    hpValue: Optional[str] = None

# --- FUNCIONES HELPER ---
def stream_minio_object(bucket_name: str, object_name: str):
    response = minio_client.get_object(bucket_name, object_name)
    try:
        for data in response.stream(32 * 1024):
            yield data
    finally:
        response.close()
        response.release_conn()


# ── Descarga PDF ──────────────────────────────────────────────────────────────
@router.get("/pdf/{clave_acceso}", summary="Descargar RIDE (PDF) público")
async def get_pdf(
    clave_acceso: str, 
    _auth = Depends(verify_public_origin), # 👈 Usamos tu seguridad
    db: AsyncSession = Depends(get_db)
):
    if not re.match(r"^\d{49}$", clave_acceso):
        return JSONResponse(status_code=400, content={"error": "Clave inválida"})

    try:
        query = text("SELECT pdf_path FROM invoices WHERE clave_acceso = :clave")
        result = await db.execute(query, {"clave": clave_acceso})
        row = result.fetchone()

        if not row or not row.pdf_path:
            return JSONResponse(status_code=404, content={"error": "Factura no encontrada"})

        parts = row.pdf_path.split('/')
        bucket = parts[0]
        object_name = '/'.join(parts[1:])

        headers = {"Content-Disposition": f'inline; filename="{clave_acceso}.pdf"'}
        return StreamingResponse(
            stream_minio_object(bucket, object_name), 
            media_type="application/pdf", 
            headers=headers
        )
    except Exception as e:
        print(f"Error Public PDF: {e}")
        return JSONResponse(status_code=404, content={"error": "Archivo no encontrado"})


# ── Descarga XML ──────────────────────────────────────────────────────────────
@router.get("/xml/{clave_acceso}", summary="Descargar XML autorizado")
async def get_xml(
    clave_acceso: str, 
    _auth = Depends(verify_public_origin), # 👈 Usamos tu seguridad
    db: AsyncSession = Depends(get_db)
):
    if not re.match(r"^\d{49}$", clave_acceso):
        return JSONResponse(status_code=400, content={"error": "Clave inválida"})

    try:
        query = text("SELECT xml_path FROM invoices WHERE clave_acceso = :clave")
        result = await db.execute(query, {"clave": clave_acceso})
        row = result.fetchone()

        if not row or not row.xml_path:
            return JSONResponse(status_code=404, content={"error": "Factura no encontrada"})

        parts = row.xml_path.split('/')
        bucket = parts[0]
        object_name = '/'.join(parts[1:])

        headers = {"Content-Disposition": f'attachment; filename="{clave_acceso}.xml"'}
        return StreamingResponse(
            stream_minio_object(bucket, object_name), 
            media_type="application/xml", 
            headers=headers
        )
    except Exception as e:
        print(f"Error Public XML: {e}")
        return JSONResponse(status_code=404, content={"error": "Archivo no encontrado"})


# ── Consulta de Factura ────────────────────────────────────────────────────────
@router.post("/consultar/{clave_acceso}", summary="Consultar factura por clave de acceso")
async def consultar_factura(
    clave_acceso: str,
    request: Request,
    body: ConsultarFacturaRequest,
    x_n8n_api_key: Optional[str] = Header(None, alias="x-n8n-api-key"),
    _auth = Depends(verify_public_origin), # 👈 Usamos tu seguridad
    db: AsyncSession = Depends(get_db)
):
    try:
        is_n8n_request = (x_n8n_api_key == settings.N8N_API_KEY)

        if not is_n8n_request and body.hpValue:
            print(f"[SECURITY] Honeypot activado por IP: {request.client.host}")
            return JSONResponse(status_code=400, content={"error": "Bot detectado"})

        if not re.match(r"^\d{49}$", clave_acceso):
            return JSONResponse(status_code=400, content={"error": "Clave de acceso inválida"})

        if not is_n8n_request:
            turnstile_secret = settings.TURNSTILE_SECRET_KEY
            async with httpx.AsyncClient() as client:
                cf_resp = await client.post(
                    "https://challenges.cloudflare.com/turnstile/v0/siteverify",
                    data={
                        "secret": turnstile_secret,
                        "response": body.captchaToken,
                        "remoteip": request.client.host
                    }
                )
                cf_data = cf_resp.json()
                if not cf_data.get("success"):
                    return JSONResponse(status_code=403, content={
                        "success": False,
                        "mensaje_usuario": "La verificación de seguridad ha fallado."
                    })

        query = text("""
            SELECT 
                i.clave_acceso, i.secuencial, i.fecha_emision, i.estado, i.mensajes_sri,
                i.razon_social_comprador, i.identificacion_comprador,
                i.importe_total, i.subtotal_iva, i.subtotal_0, i.valor_iva,
                e.razon_social as emisor_nombre, e.ruc as emisor_ruc
            FROM invoices i
            JOIN emisores e ON i.emisor_id = e.id
            WHERE i.clave_acceso = :clave
        """)
        
        result = await db.execute(query, {"clave": clave_acceso})
        factura = result.fetchone()

        if not factura:
            return JSONResponse(status_code=404, content={
                "success": False,
                "mensaje_usuario": "La factura no existe en nuestro sistema. Verifique la clave de acceso."
            })

        f = factura._mapping
        estado = f["estado"]

        if estado == 'AUTORIZADO':
            return {
                "success": True,
                "estado": "AUTORIZADO",
                "data": {
                    "cabecera": {
                        "emisor": f["emisor_nombre"],
                        "ruc": f["emisor_ruc"],
                        "nro": f["secuencial"],
                        "fecha": str(f["fecha_emision"]) 
                    },
                    "totales": {"total": float(f["importe_total"])},
                    "links": {
                        "pdf": f"https://core.kipu.ec/api/v1/public/pdf/{clave_acceso}",
                        "xml": f"https://core.kipu.ec/api/v1/public/xml/{clave_acceso}"
                    }
                }
            }

        elif estado in ['RECIBIDO', 'EN PROCESO']:
            return JSONResponse(status_code=200, content={
                "success": False,
                "estado": estado,
                "mensaje_usuario": "Tu factura ha sido recibida por el SRI y está en proceso de autorización."
            })

        elif estado in ['DEVUELTA', 'RECHAZADO']:
            return JSONResponse(status_code=200, content={
                "success": False,
                "estado": estado,
                "mensaje_usuario": "La factura presenta inconsistencias y fue devuelta/rechazada por el SRI.",
                "detalles_sri": f["mensajes_sri"],
                "sugerencia": f"Por favor, contacta al emisor ({f['emisor_nombre']}) para solucionar este inconveniente."
            })

        else:
            return JSONResponse(status_code=200, content={
                "success": False,
                "estado": estado,
                "mensaje_usuario": f"El comprobante se encuentra en estado: {estado}",
                "sugerencia": "Si el problema persiste, contacta al comercio emisor."
            })

    except httpx.HTTPError as e:
        print(f"Error de Cloudflare (Red): {e}")
        return JSONResponse(status_code=500, content={"error": "Error de validación externa"})
        
    except Exception as e:
        print(f"Error en validación o consulta: {e}")
        return JSONResponse(status_code=500, content={"error": "Error interno del servidor"})
