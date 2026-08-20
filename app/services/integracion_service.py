# app/services/integracion_service.py
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from datetime import datetime, timezone, date
from app.core.cache import cache_get, cache_set, CK, TTL


async def validar_estructura_core(
    emisor_id:    int,
    estab_codigo: str,
    punto_codigo: str,
    db:           AsyncSession
):
    """Valida que exista la combinación establecimiento/punto. Sin cache."""
    res = await db.execute(text("""
        SELECT p.id, p.secuencial_actual, e.direccion
        FROM puntos_emision p
        JOIN establecimientos e ON p.establecimiento_id = e.id
        WHERE e.emisor_id = :eid
          AND e.codigo    = :estab
          AND p.codigo    = :punto
          AND e.is_active = true
          AND p.is_active = true
    """), {"eid": emisor_id, "estab": estab_codigo, "punto": punto_codigo})

    row = res.fetchone()
    if not row:
        raise HTTPException(
            status_code=404,
            detail="La combinación de establecimiento y punto de emisión no existe o está inactiva."
        )
    return {"ok": True, "mensaje": "Estructura válida", "data": dict(row._mapping)}


async def obtener_status_core(emisor_id: int, db: AsyncSession):
    """
    Resumen del estado del emisor para integraciones externas.
    Cache TTL 3 min.
    """
    cache_key = CK.fmt(CK.STATUS, eid=emisor_id)
    cached    = await cache_get(cache_key)
    if cached:
        return cached

    res = await db.execute(text("""
        SELECT
            e.ruc, e.razon_social, e.nombre_comercial, e.ambiente, e.p12_expiration,
            COALESCE(uc.balance, 0)  AS balance_api,
            s.estado                 AS sub_estado,
            s.plan                   AS sub_plan,
            s.current_period_end,
            (
                SELECT json_agg(last_docs)
                FROM (
                    SELECT
                        id, fecha_emision, estado_sri,
                        importe_total, clave_acceso, numero_doc,
                        tipo_doc, created_at
                    FROM documentos_emitidos
                    WHERE emisor_id = e.id
                      AND tipo_doc IN ('FAC', 'LIQ')
                    ORDER BY created_at DESC
                    LIMIT 20
                ) last_docs
            ) AS ultimos_documentos
        FROM emisores e
        LEFT JOIN user_credits  uc ON uc.emisor_id = e.id
        LEFT JOIN subscriptions s  ON s.emisor_id  = e.id
        WHERE e.id = :eid
    """), {"eid": emisor_id})

    row = res.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Emisor no encontrado.")

    data = row._mapping

    # Firma
    expiracion   = data["p12_expiration"]
    firma_valida = False
    if expiracion:
        if isinstance(expiracion, date) and not isinstance(expiracion, datetime):
            expiracion = datetime.combine(expiracion, datetime.min.time())
        if expiracion.tzinfo is None:
            expiracion = expiracion.replace(tzinfo=timezone.utc)
        firma_valida = expiracion > datetime.now(timezone.utc)

    dias_restantes = (expiracion - datetime.now(timezone.utc)).days if expiracion else 0

    # Suscripción
    sub_estado = data["sub_estado"]
    suscripcion_activa = sub_estado in ("ACTIVO", "TRIAL")

    result = {
        "ok": True,
        "emisor": {
            "ruc":             data["ruc"],
            "razon_social":    data["razon_social"],
            "nombre_comercial": data["nombre_comercial"],
            "ambiente":        "PRUEBAS" if data["ambiente"] == 1 else "PRODUCCIÓN",
            "firma": {
                "valida":         firma_valida,
                "vencimiento":    expiracion.isoformat() if expiracion else None,
                "dias_restantes": dias_restantes,
            },
        },
        "suscripcion": {
            "activa": suscripcion_activa,
            "estado": sub_estado,
            "plan":   data["sub_plan"],
        },
        "balance_api":  data["balance_api"],
        "historial":    data["ultimos_documentos"] or [],
    }

    await cache_set(cache_key, result, TTL.STATUS_INTEGRACION)
    return result