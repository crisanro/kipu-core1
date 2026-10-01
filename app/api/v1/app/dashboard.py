# app/api/v1/app/dashboard.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date
from firebase_admin import auth as fb_auth

from app.core.database import get_db
from app.core.security import verify_firebase_token
from app.services.dashboard_service import obtener_dashboard_core
from app.core.cache import cache_get, cache_set, CK, TTL
from app.services.declaraciones import periodos as per
from app.services.declaraciones import registro
from app.services.declaraciones.obligaciones import cargar_obligaciones

router = APIRouter()


@router.get("", summary="Dashboard completo — una sola llamada")
async def get_dashboard(
    fecha_inicio: date = Query(...),
    fecha_fin:    date = Query(...),
    sandbox:      bool = Query(False),
    auth_data:    dict         = Depends(verify_firebase_token),
    db:           AsyncSession = Depends(get_db),
):
    emisor_id = auth_data.get("emisor_id")

    email_verificado = False
    try:
        fb_user          = fb_auth.get_user(auth_data["uid"])
        email_verificado = fb_user.email_verified
    except Exception:
        pass

    cache_key = CK.fmt(CK.DASHBOARD, eid=emisor_id, fi=fecha_inicio, ff=fecha_fin, sb=sandbox)
    cached    = await cache_get(cache_key)
    if cached:
        return cached

    # Dashboard base
    result = await obtener_dashboard_core(
        emisor_id        = emisor_id,
        email_usuario    = auth_data.get("email"),
        email_verificado = email_verificado,
        fecha_inicio     = fecha_inicio,
        fecha_fin        = fecha_fin,
        sandbox          = sandbox,
        db               = db,
    )

    if not result.get("ok"):
        return result

    # Declaración que toca declarar — incluida en la misma llamada
    declaracion = await _obtener_declaracion_actual(emisor_id, db)
    result["data"]["declaracion"] = declaracion

    # Recibidos recientes — últimos 30 días, máx 6
    recibidos = await _obtener_recibidos_recientes(emisor_id, db)
    result["data"]["recibidos_recientes"] = recibidos

    await cache_set(cache_key, result, TTL.DASHBOARD)
    return result


# =============================================================================
# HELPERS INTERNOS
# =============================================================================

async def _obtener_declaracion_actual(emisor_id: int | None, db: AsyncSession):
    """
    IVA que toca declarar ahora (el último periodo cerrado), con el mismo servicio
    que /reportes y /declaraciones/actual.

    Antes buscaba la fila del mes EN CURSO, que solo existía si la empresa había
    activado producción ese mes: por eso a unos les aparecía y a otros no.
    """
    if not emisor_id:
        return None
    try:
        obl = await cargar_obligaciones(db, emisor_id)
        if not obl or obl.motivo_no_aplica("104"):
            return None

        hoy = per.hoy_ec()
        p   = per.periodo_a_declarar("104", obl.tipo_periodo("104"), hoy)
        if not p.existe_para(obl.inicio, hoy):
            return None   # entró a producción este mes: todavía no hay nada que declarar

        await registro.asegurar_filas(db, obl, [p])
        await db.commit()
        filas = await registro.leer_filas(db, emisor_id, "104", [p])
        item  = registro.serializar(p, filas[p.inicio], hoy)

        venc = filas[p.inicio].vencimiento
        return {
            "aplica":          True,
            "tipo":            "104",
            "periodo":         p.nombre,
            "periodo_key":     p.key,
            "periodo_iso":     p.inicio.isoformat(),
            "declarado":       item["declarado"],
            "fecha_declarado": item["fecha_declarado"],
            "vencimiento":     item["vencimiento"],
            "vencimiento_fmt": venc.strftime("%d/%m/%Y"),
            "dias_restantes":  item["dias_restantes"],
            "estado":          item["estado"],
        }
    except Exception as e:
        await db.rollback()
        print(f"[Dashboard] ⚠️ Error declaración: {e}")
        return None


async def _obtener_recibidos_recientes(emisor_id: int | None, db: AsyncSession):
    """Últimos 6 documentos recibidos — 30 días."""
    if not emisor_id:
        return []
    try:
        res = await db.execute(text("""
            SELECT
                id, tipo_doc, numero_doc, fecha_emision,
                ruc_proveedor, razon_social_proveedor,
                importe_total, credito_tributario_iva,
                estado_pago
            FROM documentos_recibidos
            WHERE emisor_id   = :eid
              AND fecha_emision >= CURRENT_DATE - INTERVAL '30 days'
            ORDER BY created_at DESC
            LIMIT 6
        """), {"eid": emisor_id})
        rows = res.fetchall()
        return [
            {
                "id":                     str(r.id),
                "tipo_doc":               r.tipo_doc,
                "numero_doc":             r.numero_doc,
                "fecha_emision":          str(r.fecha_emision),
                "ruc_proveedor":          r.ruc_proveedor,
                "razon_social_proveedor": r.razon_social_proveedor,
                "importe_total":          float(r.importe_total),
                "credito_tributario_iva": r.credito_tributario_iva,
                "estado_pago":            r.estado_pago,
            }
            for r in rows
        ]
    except Exception as e:
        print(f"[Dashboard] ⚠️ Error recibidos: {e}")
        return []