# app/api/v1/app/documentos.py
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Header, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from decimal import Decimal
from datetime import date
from app.core.database import get_db
from app.core.security import verify_firebase_token
from app.core.permisos import verificar_permiso
from app.core.rate_limit import RateLimit, RateLimitScope
from app.core.idempotency import verificar_idempotency, guardar_idempotency
from app.services.documento_service import emitir_documento_core
from app.services.audit_service import audit_log

router = APIRouter()

# =============================================================================
# SCHEMAS — sin cambios
# =============================================================================
class ClienteDoc(BaseModel):
    tipo_id:        str
    identificacion: str
    nombre:         str
    email:          Optional[str] = None
    direccion:      Optional[str] = "S/N"
    telefono:       Optional[str] = ""

class ItemDoc(BaseModel):
    codigo:          Optional[str]  = None
    descripcion:     str
    cantidad:        float          = 1
    precio_unitario: float
    descuento:       float          = 0
    tipo_iva:        str            = "15"
    unidad_medida:   Optional[str]  = "UNIDAD"

class PagoDoc(BaseModel):
    forma_pago:    str            = "01"
    total:         Optional[float] = None
    plazo:         Optional[str]  = "0"
    unidad_tiempo: Optional[str]  = "dias"

class CampoAdicional(BaseModel):
    nombre: str
    valor:  str

class EmitirDocumentoRequest(BaseModel):
    establecimiento: str = "001"
    punto_emision:   str = "001"
    cliente_id:      Optional[str]        = None
    cliente:         Optional[ClienteDoc] = None
    items:           Optional[list[ItemDoc]] = None
    pagos:           Optional[list[PagoDoc]] = None
    propina:         Optional[float]         = 0
    doc_origen_id:          Optional[str]        = None
    motivo:                 Optional[str]        = None
    motivos:                Optional[list[dict]] = None
    doc_origen_numero:      Optional[str]        = None
    doc_origen_fecha:       Optional[str]        = None
    doc_origen_cod_doc:     Optional[str]        = None
    cliente_origen:         Optional[dict]       = None
    doc_origen_recibido_id: Optional[str]        = None
    doc_origen_emitido_id:  Optional[str]        = None
    impuestos:              Optional[list[dict]] = None
    periodo_fiscal:         Optional[str]        = None
    campos_adicionales:     Optional[list[CampoAdicional]] = None
    origen:                 Optional[str]                  = "web"
    proforma_id: Optional[str] = None

class ActualizarCobro(BaseModel):
    estado_cobro:            str
    forma_pago_cobro:        Optional[str]  = None
    numero_comprobante_pago: Optional[str]  = None
    fecha_pago:              Optional[date] = None

# =============================================================================
# EMIT — POST /emit/{tipo_doc}
# =============================================================================
@router.post("/emit/{tipo_doc}", summary="Emitir comprobante electrónico")
async def emitir_documento(
    tipo_doc:            str,
    data:                EmitirDocumentoRequest,
    request:             Request,
    auth_data:           dict          = Depends(verify_firebase_token),
    db:                  AsyncSession  = Depends(get_db),
    _rl:                 None          = Depends(RateLimit(RateLimitScope.INVOICE)),
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    x_sandbox:         Optional[str] = Header(None, alias="X-Sandbox"),
):
    emisor_id  = auth_data.get("emisor_id")
    profile_id = auth_data.get("profile_id")
    if not emisor_id:
        raise HTTPException(status_code=400, detail="Emisor no vinculado.")
    verificar_permiso(auth_data, "emitir")

    if not x_idempotency_key:
        raise HTTPException(
            status_code=400,
            detail="Se requiere el header X-Idempotency-Key."
        )

    es_sandbox = x_sandbox == "true"
    tipo_doc   = tipo_doc.upper()

    cached = await verificar_idempotency(emisor_id, x_idempotency_key)
    if cached:
        return cached

    result = await emitir_documento_core(
        tipo_doc   = tipo_doc,
        data       = data.model_dump(exclude_none=True),
        emisor_id  = emisor_id,
        db         = db,
        es_sandbox = es_sandbox,
        created_by = profile_id,
    )

    if result.get("ok"):
        await guardar_idempotency(emisor_id, x_idempotency_key, result)
        await audit_log(
            db        = db,
            auth_data = auth_data,
            accion    = "CREATE",
            entidad   = "documento",
            entidad_id = result.get("id") or result.get("claveAcceso"),
            detalle   = {
                "tipo_doc":   tipo_doc,
                "numero_doc": result.get("numeroDoc"),
                "total":      result.get("importeTotal"),
                "sandbox":    es_sandbox,
            },
            request   = request,
        )
        proforma_id = data.proforma_id
        if proforma_id and result.get("id") and not es_sandbox:
            try:
                from app.services.proforma_service import facturar_proforma_core
                await facturar_proforma_core(
                    emisor_id    = emisor_id,
                    proforma_id  = proforma_id,
                    documento_id = result["id"],
                    db           = db,
                )
                print(f"[Proforma] ✅ {proforma_id} marcada como FACTURADA")
            except Exception as e:
                print(f"[Proforma] ⚠️ No se pudo marcar como facturada: {e}")

        await db.commit()

    return result

# =============================================================================
# HISTORIAL — GET /
# =============================================================================
@router.get("", summary="Historial de documentos emitidos")
async def historial_documentos(
    auth_data:    dict          = Depends(verify_firebase_token),
    db:           AsyncSession  = Depends(get_db),
    tipo_doc:     Optional[str] = Query(None),
    estado_sri:   Optional[str] = Query(None),
    fecha_inicio: Optional[str] = Query(None),
    fecha_fin:    Optional[str] = Query(None),
    q:            Optional[str] = Query(None),
    sandbox:      bool          = Query(False),
    limit:        int           = Query(50, le=100),
    offset:       int           = Query(0),
    _rl:          None          = Depends(RateLimit(RateLimitScope.GENERAL)),
):
    emisor_id = auth_data.get("emisor_id")
    if not emisor_id:
        raise HTTPException(status_code=400, detail="Emisor no vinculado.")
    verificar_permiso(auth_data, "descargar")

    if fecha_inicio and fecha_fin:
        fi = date.fromisoformat(fecha_inicio)
        ff = date.fromisoformat(fecha_fin)
        if (ff - fi).days > 45:
            raise HTTPException(status_code=400, detail="El rango máximo es 45 días.")

    filtros = "WHERE emisor_id = :eid AND es_sandbox = :sandbox"
    params  = {"eid": emisor_id, "sandbox": sandbox}

    if tipo_doc:
        filtros += " AND tipo_doc = :tipo_doc"
        params["tipo_doc"] = tipo_doc.upper()
    if estado_sri:
        filtros += " AND estado_sri = :estado_sri"
        params["estado_sri"] = estado_sri.upper()
    if fecha_inicio:
        filtros += " AND fecha_emision >= :fi"
        params["fi"] = date.fromisoformat(fecha_inicio)
    if fecha_fin:
        filtros += " AND fecha_emision <= :ff"
        params["ff"] = date.fromisoformat(fecha_fin)
    if q:
        filtros += """ AND (
            numero_doc ILIKE :q OR
            datos->'infoFactura'->>'razonSocialComprador' ILIKE :q OR
            datos->'infoFactura'->>'identificacionComprador' ILIKE :q OR
            datos->'infoLiquidacionCompra'->>'razonSocialProveedor' ILIKE :q OR
            datos->'infoLiquidacionCompra'->>'identificacionProveedor' ILIKE :q
        )"""
        params["q"] = f"%{q}%"

    params["limit"]  = limit
    params["offset"] = offset

    res = await db.execute(text(f"""
        SELECT
            id, tipo_doc, cod_doc,
            clave_acceso, numero_doc, secuencial,
            fecha_emision, estado_sri, estado_cobro,
            importe_total, origen, created_at,
            datos->>'legacy_razon_comprador' AS razon_comprador,
            datos->>'legacy_id_comprador'    AS id_comprador,
            datos->'infoFactura'->>'razonSocialComprador'    AS razon_fac,
            datos->'infoFactura'->>'identificacionComprador' AS id_fac
        FROM documentos_emitidos
        {filtros}
        ORDER BY created_at DESC
        LIMIT :limit OFFSET :offset
    """), params)
    rows = res.fetchall()

    data = []
    for r in rows:
        razon  = r.razon_fac or r.razon_comprador or ""
        id_com = r.id_fac or r.id_comprador or ""
        data.append({
            "id":             str(r.id),
            "tipo_doc":       r.tipo_doc,
            "cod_doc":        r.cod_doc,
            "clave_acceso":   r.clave_acceso,
            "numero_doc":     r.numero_doc,
            "fecha_emision":  str(r.fecha_emision),
            "estado_sri":     r.estado_sri,
            "estado_cobro":   r.estado_cobro,
            "importe_total":  float(r.importe_total),
            "razon_social":   razon,
            "identificacion": id_com,
            "origen":         r.origen,
            "created_at":     str(r.created_at),
        })
    return {"ok": True, "total": len(data), "data": data}

# =============================================================================
# RESUMEN — GET /resumen
# =============================================================================
@router.get("/resumen", summary="Resumen por tipo de comprobante para declaración")
async def resumen_documentos(
    auth_data:    dict          = Depends(verify_firebase_token),
    db:           AsyncSession  = Depends(get_db),
    fecha_inicio: Optional[str] = Query(None),
    fecha_fin:    Optional[str] = Query(None),
    _rl:          None          = Depends(RateLimit(RateLimitScope.GENERAL)),
):
    emisor_id = auth_data.get("emisor_id")
    if not emisor_id:
        raise HTTPException(status_code=400, detail="Emisor no vinculado.")
    verificar_permiso(auth_data, "reportes")

    hoy = date.today()
    fi  = date.fromisoformat(fecha_inicio) if fecha_inicio else hoy
    ff  = date.fromisoformat(fecha_fin)    if fecha_fin    else hoy

    if (ff - fi).days > 45:
        raise HTTPException(status_code=400, detail="El rango máximo es 45 días.")

    res_iva = await db.execute(text("""
        SELECT
            d.tipo_doc,
            (imp->>'tarifa')::numeric             AS tarifa,
            SUM((imp->>'baseImponible')::numeric) AS subtotal,
            SUM((imp->>'valor')::numeric)         AS iva,
            COUNT(DISTINCT d.id)                  AS num_docs,
            SUM(d.importe_total)                  AS total
        FROM documentos_emitidos d,
             jsonb_array_elements(
                 CASE
                     WHEN jsonb_typeof(d.datos->'resumenImpuestos') = 'array'
                     THEN d.datos->'resumenImpuestos'
                     ELSE '[]'::jsonb
                 END
             ) AS imp
        WHERE d.emisor_id     = :eid
          AND d.estado_sri    = 'AUTORIZADO'
          AND d.fecha_emision BETWEEN :fi AND :ff
          AND d.es_sandbox    = false
          AND d.tipo_doc      IN ('FAC', 'LIQ', 'NCR', 'NDB')
        GROUP BY d.tipo_doc, (imp->>'tarifa')::numeric
        ORDER BY d.tipo_doc, tarifa
    """), {"eid": emisor_id, "fi": fi, "ff": ff})

    res_ret = await db.execute(text("""
        SELECT
            (imp->>'codigo')          AS codigo_impuesto,
            (imp->>'codigoRetencion') AS codigo_retencion,
            SUM((imp->>'baseImponible')::numeric) AS base,
            SUM((imp->>'valorRetenido')::numeric) AS valor_retenido,
            COUNT(DISTINCT d.id)                  AS num_docs
        FROM documentos_emitidos d,
             jsonb_array_elements(
                 CASE
                     WHEN jsonb_typeof(d.datos->'impuestos'->'impuesto') = 'array'
                     THEN d.datos->'impuestos'->'impuesto'
                     WHEN d.datos->'impuestos'->'impuesto' IS NOT NULL
                     THEN jsonb_build_array(d.datos->'impuestos'->'impuesto')
                     ELSE '[]'::jsonb
                 END
             ) AS imp
        WHERE d.emisor_id     = :eid
          AND d.estado_sri    = 'AUTORIZADO'
          AND d.fecha_emision BETWEEN :fi AND :ff
          AND d.es_sandbox    = false
          AND d.tipo_doc      = 'RET'
        GROUP BY (imp->>'codigo'), (imp->>'codigoRetencion')
        ORDER BY codigo_impuesto, codigo_retencion
    """), {"eid": emisor_id, "fi": fi, "ff": ff})

    res_totales = await db.execute(text("""
        SELECT tipo_doc, COUNT(*) AS num_docs, SUM(importe_total) AS total
        FROM documentos_emitidos
        WHERE emisor_id     = :eid
          AND estado_sri    = 'AUTORIZADO'
          AND fecha_emision BETWEEN :fi AND :ff
          AND es_sandbox    = false
        GROUP BY tipo_doc
    """), {"eid": emisor_id, "fi": fi, "ff": ff})

    rows_iva     = res_iva.fetchall()
    rows_ret     = res_ret.fetchall()
    rows_totales = res_totales.fetchall()

    totales_map: dict = {}
    for r in rows_totales:
        totales_map[r.tipo_doc] = {"num_docs": r.num_docs, "total": float(r.total or 0)}

    desglose_iva: dict = {}
    for r in rows_iva:
        tipo = r.tipo_doc
        if tipo not in desglose_iva:
            desglose_iva[tipo] = []
        desglose_iva[tipo].append({
            "tarifa":   float(r.tarifa or 0),
            "subtotal": float(r.subtotal or 0),
            "iva":      float(r.iva or 0),
        })

    TIPO_IMPUESTO = {"1": "Renta", "2": "IVA", "6": "ISD"}
    desglose_ret: list = []
    for r in rows_ret:
        desglose_ret.append({
            "tipo_impuesto":    TIPO_IMPUESTO.get(str(r.codigo_impuesto), str(r.codigo_impuesto)),
            "codigo_retencion": r.codigo_retencion,
            "base":             float(r.base or 0),
            "valor_retenido":   float(r.valor_retenido or 0),
            "num_docs":         r.num_docs,
        })

    ret_agrupado: dict = {}
    for item in desglose_ret:
        tipo = item["tipo_impuesto"]
        if tipo not in ret_agrupado:
            ret_agrupado[tipo] = {"base": 0, "valor_retenido": 0, "detalle": []}
        ret_agrupado[tipo]["base"]           += item["base"]
        ret_agrupado[tipo]["valor_retenido"] += item["valor_retenido"]
        ret_agrupado[tipo]["detalle"].append(item)

    return {
        "ok": True,
        "data": {
            "periodo": {"desde": str(fi), "hasta": str(ff)},
            "por_tipo": {
                tipo: {
                    **totales_map.get(tipo, {"num_docs": 0, "total": 0}),
                    "desglose_iva": desglose_iva.get(tipo, []),
                }
                for tipo in ["FAC", "LIQ", "NCR", "NDB"]
                if tipo in totales_map or tipo in desglose_iva
            },
            "retenciones": {
                "num_docs": totales_map.get("RET", {}).get("num_docs", 0),
                "total":    totales_map.get("RET", {}).get("total", 0),
                "por_tipo": ret_agrupado,
            },
        }
    }

# =============================================================================
# DETALLE — GET /{doc_id}
# =============================================================================
@router.get("/{doc_id}", summary="Detalle de un documento emitido")
async def detalle_documento(
    doc_id:    str,
    auth_data: dict         = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db),
):
    emisor_id = auth_data.get("emisor_id")
    if not emisor_id:
        raise HTTPException(status_code=400, detail="Emisor no vinculado.")
    verificar_permiso(auth_data, "descargar")

    res = await db.execute(text("""
        SELECT
            d.id, d.tipo_doc, d.cod_doc,
            d.clave_acceso, d.numero_doc, d.secuencial,
            d.fecha_emision, d.estado_sri, d.mensajes_sri,
            d.fecha_envio_sri, d.fecha_autorizacion,
            d.estado_cobro, d.forma_pago_cobro,
            d.numero_comprobante_pago, d.fecha_pago,
            d.importe_total, d.datos,
            d.xml_path, d.pdf_path,
            d.origen, d.created_at,
            d.doc_origen_emitido_id,
            d.doc_origen_recibido_id,
            d.es_sandbox,
            (
                SELECT json_agg(json_build_object(
                    'id', dd.id, 'tipo_doc', dd.tipo_doc,
                    'numero_doc', dd.numero_doc, 'estado_sri', dd.estado_sri,
                    'importe_total', dd.importe_total, 'created_at', dd.created_at
                ) ORDER BY dd.created_at ASC)
                FROM documentos_emitidos dd
                WHERE dd.doc_origen_emitido_id = d.id AND dd.emisor_id = d.emisor_id
            ) AS documentos_derivados,
            (
                SELECT json_build_object(
                    'id', dp.id, 'tipo_doc', dp.tipo_doc,
                    'numero_doc', dp.numero_doc, 'estado_sri', dp.estado_sri,
                    'importe_total', dp.importe_total
                )
                FROM documentos_emitidos dp WHERE dp.id = d.doc_origen_emitido_id
            ) AS doc_origen_emitido,
            (
                SELECT json_build_object(
                    'id', dr.id, 'numero_doc', dr.numero_doc,
                    'ruc_proveedor', dr.ruc_proveedor,
                    'razon_social_proveedor', dr.razon_social_proveedor,
                    'importe_total', dr.importe_total, 'fecha_emision', dr.fecha_emision
                )
                FROM documentos_recibidos dr WHERE dr.id = d.doc_origen_recibido_id
            ) AS doc_origen_recibido
        FROM documentos_emitidos d
        WHERE d.id = :did AND d.emisor_id = :eid
    """), {"did": doc_id, "eid": emisor_id})
    doc = res.fetchone()
    if not doc:
        raise HTTPException(status_code=404, detail="Documento no encontrado.")

    return {
        "ok": True,
        "data": {
            "id":                     str(doc.id),
            "tipo_doc":               doc.tipo_doc,
            "cod_doc":                doc.cod_doc,
            "clave_acceso":           doc.clave_acceso,
            "numero_doc":             doc.numero_doc,
            "secuencial":             doc.secuencial,
            "fecha_emision":          str(doc.fecha_emision),
            "estado_sri":             doc.estado_sri,
            "mensajes_sri":           doc.mensajes_sri,
            "fecha_envio_sri":        str(doc.fecha_envio_sri) if doc.fecha_envio_sri else None,
            "fecha_autorizacion":     str(doc.fecha_autorizacion) if doc.fecha_autorizacion else None,
            "estado_cobro":           doc.estado_cobro,
            "forma_pago_cobro":       doc.forma_pago_cobro,
            "numero_comprobante_pago": doc.numero_comprobante_pago,
            "fecha_pago":             str(doc.fecha_pago) if doc.fecha_pago else None,
            "importe_total":          float(doc.importe_total),
            "datos":                  doc.datos,
            "xml_path":               doc.xml_path,
            "pdf_path":               doc.pdf_path,
            "origen":                 doc.origen,
            "es_sandbox":             doc.es_sandbox,
            "created_at":             str(doc.created_at),
            "doc_origen_emitido_id":  str(doc.doc_origen_emitido_id) if doc.doc_origen_emitido_id else None,
            "doc_origen_recibido_id": str(doc.doc_origen_recibido_id) if doc.doc_origen_recibido_id else None,
            "documentos_derivados":   doc.documentos_derivados or [],
            "doc_origen_emitido":     doc.doc_origen_emitido,
            "doc_origen_recibido":    doc.doc_origen_recibido,
        }
    }

# =============================================================================
# REINTENTAR — POST /{doc_id}/reintentar
# =============================================================================
@router.post("/{doc_id}/reintentar", summary="Reintentar envío al SRI")
async def reintentar_documento(
    doc_id:    str,
    request:   Request,
    auth_data: dict         = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db),
):
    emisor_id = auth_data.get("emisor_id")
    if not emisor_id:
        raise HTTPException(status_code=400, detail="Emisor no vinculado.")
    verificar_permiso(auth_data, "emitir")

    res = await db.execute(text("""
        SELECT id, estado_sri, clave_acceso, numero_doc, es_sandbox
        FROM documentos_emitidos
        WHERE id = :did AND emisor_id = :eid
    """), {"did": doc_id, "eid": emisor_id})
    doc = res.fetchone()
    if not doc:
        raise HTTPException(status_code=404, detail="Documento no encontrado.")
    if doc.es_sandbox:
        raise HTTPException(status_code=400, detail="No se pueden reintentar documentos sandbox.")
    if doc.estado_sri not in ("DEVUELTA", "RECHAZADO", "FIRMADO"):
        raise HTTPException(status_code=400, detail=f"No se puede reintentar en estado {doc.estado_sri}.")

    await db.execute(text("""
        UPDATE documentos_emitidos
        SET estado_sri = 'FIRMADO', mensajes_sri = NULL, updated_at = NOW()
        WHERE id = :did AND emisor_id = :eid
    """), {"did": doc_id, "eid": emisor_id})

    await audit_log(
        db        = db,
        auth_data = auth_data,
        accion    = "UPDATE",
        entidad   = "documento",
        entidad_id = doc_id,
        detalle   = {
            "accion":     "reintento",
            "numero_doc": doc.numero_doc,
            "estado_anterior": doc.estado_sri,
            "estado_nuevo":    "FIRMADO",
        },
        request   = request,
    )

    await db.commit()

    from app.core.cache import get_redis
    redis = await get_redis()
    await redis.lpush("kipu:queue:emision", doc_id)

    return {"ok": True, "mensaje": "Documento reencolado para reintento.", "estado": "FIRMADO"}

# =============================================================================
# COBRO — PATCH /{doc_id}/cobro
# =============================================================================
@router.patch("/{doc_id}/cobro", summary="Actualizar estado de cobro")
async def actualizar_cobro(
    doc_id:    str,
    data:      ActualizarCobro,
    request:   Request,
    auth_data: dict         = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db),
):
    emisor_id = auth_data.get("emisor_id")
    if not emisor_id:
        raise HTTPException(status_code=400, detail="Emisor no vinculado.")
    verificar_permiso(auth_data, "emitir")

    estados_validos = ("PENDIENTE", "PAGADO", "PARCIAL", "ANULADO")
    if data.estado_cobro not in estados_validos:
        raise HTTPException(status_code=400, detail=f"Estado inválido. Válidos: {', '.join(estados_validos)}")

    res = await db.execute(text("""
        SELECT id, tipo_doc, estado_cobro, numero_doc FROM documentos_emitidos
        WHERE id = :did AND emisor_id = :eid
    """), {"did": doc_id, "eid": emisor_id})
    doc = res.fetchone()
    if not doc:
        raise HTTPException(status_code=404, detail="Documento no encontrado.")
    if doc.tipo_doc not in ("FAC", "LIQ"):
        raise HTTPException(status_code=400, detail="El estado de cobro solo aplica a facturas y liquidaciones.")

    await db.execute(text("""
        UPDATE documentos_emitidos SET
            estado_cobro            = :estado,
            forma_pago_cobro        = :forma,
            numero_comprobante_pago = :num_comp,
            fecha_pago              = :fecha_pago,
            updated_at              = NOW()
        WHERE id = :did AND emisor_id = :eid
    """), {
        "estado":     data.estado_cobro,
        "forma":      data.forma_pago_cobro,
        "num_comp":   data.numero_comprobante_pago,
        "fecha_pago": data.fecha_pago,
        "did":        doc_id,
        "eid":        emisor_id,
    })

    await audit_log(
        db        = db,
        auth_data = auth_data,
        accion    = "UPDATE",
        entidad   = "documento",
        entidad_id = doc_id,
        detalle   = {
            "accion":         "cobro",
            "numero_doc":     doc.numero_doc,
            "estado_anterior": doc.estado_cobro,
            "estado_nuevo":    data.estado_cobro,
            "forma_pago":      data.forma_pago_cobro,
            "fecha_pago":      str(data.fecha_pago) if data.fecha_pago else None,
        },
        request   = request,
    )

    await db.commit()
    return {"ok": True, "mensaje": f"Estado de cobro actualizado a {data.estado_cobro}."}

# =============================================================================
# DESGLOSE — GET /{doc_id}/desglose
# =============================================================================
@router.get("/{doc_id}/desglose", summary="Desglose de impuestos de un documento")
async def desglose_documento(
    doc_id:    str,
    auth_data: dict         = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db),
):
    emisor_id = auth_data.get("emisor_id")
    if not emisor_id:
        raise HTTPException(status_code=400, detail="Emisor no vinculado.")
    verificar_permiso(auth_data, "descargar")

    res = await db.execute(text("""
        SELECT
            importe_total,
            datos->'resumenImpuestos'                            AS resumen_impuestos,
            datos->'infoFactura'->>'totalSinImpuestos'           AS subtotal_fac,
            datos->'infoLiquidacionCompra'->>'totalSinImpuestos' AS subtotal_liq
        FROM documentos_emitidos
        WHERE id = :did AND emisor_id = :eid
    """), {"did": doc_id, "eid": emisor_id})
    doc = res.fetchone()
    if not doc:
        raise HTTPException(status_code=404, detail="Documento no encontrado.")

    subtotal = float(doc.subtotal_fac or doc.subtotal_liq or 0)
    resumen  = doc.resumen_impuestos or []
    if not isinstance(resumen, list):
        resumen = [resumen]

    return {
        "ok": True,
        "data": {
            "importe_total":     float(doc.importe_total),
            "subtotal":          subtotal,
            "resumen_impuestos": resumen,
        }
    }