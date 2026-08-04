from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date
from firebase_admin import auth as fb_auth

from app.core.database import get_db
from app.core.security import verify_firebase_token
from app.services.dashboard_service import obtener_dashboard_core
from app.core.cache import cache_get, cache_set, CK, TTL
from app.core.config import settings


router = APIRouter()


@router.get("", summary="Obtener datos globales del Dashboard")
async def get_dashboard(
    fecha_inicio: date = Query(..., description="Fecha inicial (YYYY-MM-DD)"),
    fecha_fin:    date = Query(..., description="Fecha final (YYYY-MM-DD)"),
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db),
):
    emisor_id = auth_data.get("emisor_id")

    # Verificación de email en Firebase Auth
    email_verificado = False
    try:
        fb_user = fb_auth.get_user(auth_data["uid"])
        email_verificado = fb_user.email_verified
    except Exception:
        pass

    # 1. Cache corregido por emisor + rango de fechas usando CK.fmt
    cache_key = CK.fmt(CK.DASHBOARD, eid=emisor_id, fi=fecha_inicio, ff=fecha_fin)
    cached = await cache_get(cache_key)
    if cached:
        return cached

    result = await obtener_dashboard_core(
        emisor_id=emisor_id,
        email_usuario=auth_data.get("email"),
        email_verificado=email_verificado,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        db=db,
    )

    # Cache con TTL estándar de Dashboard (2 min)
    await cache_set(cache_key, result, TTL.DASHBOARD)
    return result


@router.get("/factura/{factura_id}", summary="Detalle de una factura")
async def detalle_factura(
    factura_id: str,
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db),
):
    emisor_id = auth_data.get("emisor_id")
    
    # 3. Formateo de cache_key unificado con CK.fmt
    cache_key = CK.fmt(CK.FACTURA, eid=emisor_id, fid=factura_id)
    cached = await cache_get(cache_key)
    if cached:
        return cached
    
    res = await db.execute(text("""
        SELECT 
            id, clave_acceso, numero_factura, secuencial, fecha_emision,
            estado, mensajes_sri, fecha_autorizacion, datos_factura,
            xml_path, origen, created_at
        FROM invoices_emitidas
        WHERE id = :fid AND emisor_id = :eid
    """), {"fid": factura_id, "eid": emisor_id})
    
    factura = res.fetchone()
    if not factura:
        raise HTTPException(status_code=404, detail="Factura no encontrada.")
    
    f = factura._mapping
    resultado = {
        "ok": True,
        "factura": {
            "id":                 str(f["id"]),
            "clave_acceso":       f["clave_acceso"],
            "numero_factura":     f["numero_factura"],
            "fecha_emision":      str(f["fecha_emision"]),
            "fecha_autorizacion": str(f["fecha_autorizacion"]) if f["fecha_autorizacion"] else None,
            "estado":             f["estado"],
            "mensajes_sri":       f["mensajes_sri"],
            "origen":             f["origen"],
            "datos":              f["datos_factura"],
            "links": {
                "pdf": f"{settings.BACKEND_URL}/api/v1/public/pdf/{f['clave_acceso']}",
                "xml": f"{settings.BACKEND_URL}/api/v1/public/xml/{f['clave_acceso']}",
            } if f["estado"] == "AUTORIZADO" else None
        }
    }
    
    # 2. TTL.FACTURA_DETALLE aplicado correctamente (5 min si autorizada, 30s si pendiente/otro)
    ttl = TTL.FACTURA_DETALLE if f["estado"] == "AUTORIZADO" else 30
    await cache_set(cache_key, resultado, ttl)
    
    return resultado