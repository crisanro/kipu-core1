import json
from datetime import date
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.cache import cache_get, cache_set, CK, TTL

async def obtener_historial_core(
    emisor_id: int,
    db: AsyncSession,
    fecha_inicio: str = None,
    fecha_fin: str = None
):
    # Validar rango máximo de 45 días entre fecha_inicio y fecha_fin
    if fecha_inicio and fecha_fin:
        fi_date = date.fromisoformat(fecha_inicio)
        ff_date = date.fromisoformat(fecha_fin)
        if (ff_date - fi_date).days > 45:
            raise HTTPException(
                status_code=400,
                detail="El rango máximo de consulta es 45 días."
            )

    # Clave de caché estructurada usando CK.fmt
    cache_key = CK.fmt(CK.HISTORIAL, eid=emisor_id, fi=fecha_inicio, ff=fecha_fin)
    cached = await cache_get(cache_key)
    if cached:
        return cached

    filtro_fecha = ""
    params = {"eid": emisor_id}
    if fecha_inicio:
        filtro_fecha += " AND fecha_emision >= :fi"
        params["fi"] = date.fromisoformat(fecha_inicio)
    if fecha_fin:
        filtro_fecha += " AND fecha_emision <= :ff"
        params["ff"] = date.fromisoformat(fecha_fin)

    # Query SQL con extracción de impuestos desde el JSONB datos_factura
    query = text(f"""
        SELECT
            id, clave_acceso, numero_factura, estado,
            cod_doc,                                        -- ← agregar
            importe_total, subtotal_iva, subtotal_0, valor_iva,
            fecha_emision, created_at,
            razon_social_comprador, identificacion_comprador,
            datos_factura->'infoFactura'->'totalConImpuestos'->'totalImpuesto' AS impuestos_totales
        FROM invoices_emitidas
        WHERE emisor_id = :eid {filtro_fecha}
        ORDER BY created_at DESC
    """)

    res = await db.execute(query, params)
    facturas = res.mappings().fetchall()

    MAP_TARIFA = {
        "0": "0", "5": "5", "15": "15",
        "2": "12", "3": "14", "4": "15" # Mapeo por código porcentual SRI si aplica
    }

    data = []
    for f in facturas:
        d = dict(f)
        d["id"]            = str(d["id"])
        d["importe_total"] = float(d["importe_total"] or 0)
        d["subtotal_iva"]  = float(d["subtotal_iva"] or 0)
        d["subtotal_0"]    = float(d["subtotal_0"] or 0)
        d["valor_iva"]     = float(d["valor_iva"] or 0)
        d["fecha_emision"] = str(d["fecha_emision"])
        d["cod_doc"]       = str(d.get("cod_doc") or "01")
        d["created_at"]    = str(d["created_at"])

        # Deserialización y estructuración de impuestos
        raw = d.pop("impuestos_totales", None)
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except Exception:
                raw = []

        raw_list = raw if isinstance(raw, list) else ([raw] if raw else [])

        resumen_impuestos = []
        for imp in raw_list:
            if isinstance(imp, dict):
                cod_porcentaje = str(imp.get("codigoPorcentaje", "0"))
                tarifa = imp.get("tarifa") or MAP_TARIFA.get(cod_porcentaje, cod_porcentaje)
                resumen_impuestos.append({
                    "codigo": imp.get("codigo"),
                    "codigoPorcentaje": cod_porcentaje,
                    "tarifa": str(tarifa),
                    "baseImponible": float(imp.get("baseImponible", 0)),
                    "valor": float(imp.get("valor", 0))
                })

        d["resumen_impuestos"] = resumen_impuestos
        data.append(d)

    result = {"ok": True, "data": data}
    
    # Guardar en caché con el TTL estándar para historial
    await cache_set(cache_key, result, TTL.HISTORIAL)
    return result