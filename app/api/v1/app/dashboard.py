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

router = APIRouter()


@router.get("", summary="Dashboard completo — una sola llamada")
async def get_dashboard(
    fecha_inicio: date = Query(...),
    fecha_fin:    date = Query(...),
    sandbox:      bool = Query(False),
    auth_data:    dict         = Depends(verify_firebase_token),
    db:           AsyncSession = Depends(get_db),
):
    print(f"[Dashboard] sandbox={sandbox}, emisor_id={auth_data.get('emisor_id')}")
    emisor_id = auth_data.get("emisor_id")

    email_verificado = False
    try:
        fb_user          = fb_auth.get_user(auth_data["uid"])
        email_verificado = fb_user.email_verified
    except Exception:
        pass

    cache_key = CK.fmt(CK.DASHBOARD, eid=emisor_id, fi=fecha_inicio, ff=fecha_fin, sb=sandbox)
    print(f"[Dashboard] cache_key={cache_key}")
    cached    = await cache_get(cache_key)
    print(f"[Dashboard] cache hit={cached is not None}")   
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

    # Declaración actual — incluida en la misma llamada
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
    """Declaración IVA del mes actual — mismo cálculo que /declaraciones/actual."""
    if not emisor_id:
        return None
    try:
        hoy    = date.today()
        primer = hoy.replace(day=1)
        res    = await db.execute(text("""
            SELECT
                tipo, periodo, vencimiento, declarado,
                fecha_declarado, totales
            FROM declaraciones_sri
            WHERE emisor_id = :eid
              AND tipo      = '104'
              AND periodo   = :periodo
            LIMIT 1
        """), {"eid": emisor_id, "periodo": primer})
        row = res.fetchone()
        if not row:
            return None
        venc           = row.vencimiento
        dias_restantes = (venc - hoy).days if venc else 0

        if row.declarado:
            estado = "DECLARADO"
        elif dias_restantes < 0:
            estado = "VENCIDO"
        elif dias_restantes <= 3:
            estado = "URGENTE"
        elif dias_restantes <= 10:
            estado = "PROXIMO"
        else:
            estado = "PENDIENTE"

        return {
            "aplica":          True,
            "periodo":         row.periodo.strftime("%B %Y") if row.periodo else None,
            "periodo_iso":     str(row.periodo),
            "declarado":       row.declarado,
            "fecha_declarado": str(row.fecha_declarado) if row.fecha_declarado else None,
            "vencimiento":     str(venc),
            "vencimiento_fmt": venc.strftime("%d/%m/%Y") if venc else None,
            "dias_restantes":  dias_restantes,
            "estado":          estado,
        }
    except Exception as e:
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