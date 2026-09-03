# app/api/v1/app/declaraciones.py
#
# Endpoints para gestión de declaraciones tributarias.
# Tipos: 104 (IVA mensual) | 102 (Renta anual) | ATS (Anexo Transaccional)
#
# El sistema NO declara por el usuario — prepara los valores y marca si declaró.
# La declaración real la hace el usuario en el SRI en Línea.
import json
from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.database import get_db
from app.core.security import verify_firebase_token
from app.core.permisos import verificar_permiso
from app.workers.declaraciones_worker import calcular_vencimiento

import zipfile
import io
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom

import calendar
from app.services.storage_service import upload_file, get_presigned_url


router = APIRouter()

TIPOS_VALIDOS = ("104", "102", "ATS")


# =============================================================================
# GET /actual — declaración del mes/año en curso
# =============================================================================

@router.get("/actual", summary="Declaración del período actual")
async def obtener_declaracion_actual(
    tipo:      str          = Query("104", description="104 | 102 | ATS"),
    auth_data: dict         = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db),
):
    emisor_id = auth_data.get("emisor_id")
    if not emisor_id:
        raise HTTPException(status_code=400, detail="Emisor no vinculado.")
    verificar_permiso(auth_data, "declaraciones")

    if tipo not in TIPOS_VALIDOS:
        raise HTTPException(status_code=400, detail=f"Tipo inválido. Válidos: {', '.join(TIPOS_VALIDOS)}")

    res_emisor = await db.execute(
        text("SELECT ruc, ambiente FROM emisores WHERE id = :eid"),
        {"eid": emisor_id}
    )
    emisor = res_emisor.fetchone()
    if not emisor:
        raise HTTPException(status_code=404, detail="Emisor no encontrado.")

    if emisor.ambiente != 2:
        return {"ok": True, "aplica": False, "motivo": "Solo aplica en ambiente producción."}

    hoy     = date.today()
    periodo = _periodo_actual(tipo, hoy)

    # Crear si no existe
    await db.execute(text("""
        INSERT INTO declaraciones_sri (emisor_id, tipo, periodo, vencimiento, declarado)
        VALUES (:eid, :tipo, :periodo, :vencimiento, false)
        ON CONFLICT (emisor_id, tipo, periodo) DO NOTHING
    """), {
        "eid":        emisor_id,
        "tipo":       tipo,
        "periodo":    periodo,
        "vencimiento": calcular_vencimiento(emisor.ruc, periodo),
    })
    await db.commit()

    res = await db.execute(text("""
        SELECT id, periodo, vencimiento, declarado, fecha_declarado, totales
        FROM declaraciones_sri
        WHERE emisor_id = :eid AND tipo = :tipo AND periodo = :periodo
    """), {"eid": emisor_id, "tipo": tipo, "periodo": periodo})
    decl = res.fetchone()

    vencimiento    = decl.vencimiento
    dias_restantes = (vencimiento - hoy).days

    return {
        "ok":     True,
        "aplica": True,
        "data": {
            "tipo":            tipo,
            "periodo":         periodo.strftime("%B %Y"),
            "periodo_iso":     str(periodo),
            "declarado":       decl.declarado,
            "fecha_declarado": str(decl.fecha_declarado) if decl.fecha_declarado else None,
            "vencimiento":     str(vencimiento),
            "vencimiento_fmt": vencimiento.strftime("%d de %B de %Y"),
            "dias_restantes":  dias_restantes,
            "estado":          _estado(decl.declarado, dias_restantes),
            "totales":         decl.totales or {},
        }
    }


# =============================================================================
# GET /historial — declaraciones anteriores
# =============================================================================

@router.get("/historial", summary="Historial de declaraciones")
async def historial_declaraciones(
    tipo:      str          = Query("104"),
    anio:      Optional[int] = Query(None, description="Año a consultar"),
    auth_data: dict         = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db),
):
    emisor_id = auth_data.get("emisor_id")
    if not emisor_id:
        raise HTTPException(status_code=400, detail="Emisor no vinculado.")
    verificar_permiso(auth_data, "declaraciones")

    if tipo not in TIPOS_VALIDOS:
        raise HTTPException(status_code=400, detail=f"Tipo inválido. Válidos: {', '.join(TIPOS_VALIDOS)}")

    hoy  = date.today()
    anio = anio or hoy.year

    filtro_anio = "AND EXTRACT(YEAR FROM periodo) = :anio"
    params      = {"eid": emisor_id, "tipo": tipo, "anio": anio}

    res = await db.execute(text(f"""
        SELECT
            id, periodo, vencimiento, declarado,
            fecha_declarado, totales
        FROM declaraciones_sri
        WHERE emisor_id = :eid AND tipo = :tipo
        {filtro_anio}
        ORDER BY periodo DESC
    """), params)

    rows = res.fetchall()

    return {
        "ok":   True,
        "anio": anio,
        "tipo": tipo,
        "data": [
            {
                "id":              r.id,
                "periodo":         str(r.periodo),
                "periodo_fmt":     r.periodo.strftime("%B %Y"),
                "vencimiento":     str(r.vencimiento),
                "declarado":       r.declarado,
                "fecha_declarado": str(r.fecha_declarado) if r.fecha_declarado else None,
                "estado":          _estado(r.declarado, (r.vencimiento - hoy).days),
                "totales":         r.totales or {},
            }
            for r in rows
        ]
    }


# =============================================================================
# GET /periodo/{anio}/{mes} — declaración de un período específico
# =============================================================================

@router.get("/periodo/{anio}/{mes}", summary="Declaración de un período específico")
async def declaracion_periodo(
    anio:      int,
    mes:       int,
    tipo:      str          = Query("104"),
    auth_data: dict         = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db),
):
    emisor_id = auth_data.get("emisor_id")
    if not emisor_id:
        raise HTTPException(status_code=400, detail="Emisor no vinculado.")
    verificar_permiso(auth_data, "declaraciones")

    if not (1 <= mes <= 12):
        raise HTTPException(status_code=400, detail="Mes inválido.")

    if tipo not in TIPOS_VALIDOS:
        raise HTTPException(status_code=400, detail=f"Tipo inválido. Válidos: {', '.join(TIPOS_VALIDOS)}")

    periodo = date(anio, mes, 1)
    hoy     = date.today()

    res = await db.execute(text("""
        SELECT
            id, periodo, vencimiento, declarado,
            fecha_declarado, totales
        FROM declaraciones_sri
        WHERE emisor_id = :eid AND tipo = :tipo AND periodo = :periodo
    """), {"eid": emisor_id, "tipo": tipo, "periodo": periodo})

    decl = res.fetchone()
    if not decl:
        raise HTTPException(status_code=404, detail="Declaración no encontrada para ese período.")

    return {
        "ok":   True,
        "data": {
            "tipo":            tipo,
            "periodo":         str(decl.periodo),
            "periodo_fmt":     decl.periodo.strftime("%B %Y"),
            "vencimiento":     str(decl.vencimiento),
            "declarado":       decl.declarado,
            "fecha_declarado": str(decl.fecha_declarado) if decl.fecha_declarado else None,
            "estado":          _estado(decl.declarado, (decl.vencimiento - hoy).days),
            "totales":         decl.totales or {},
        }
    }


# =============================================================================
# GET /totales/{anio}/{mes} — calcular totales del período en tiempo real
# =============================================================================

@router.get("/totales/{anio}/{mes}", summary="Calcular totales fiscales de un período")
async def calcular_totales_periodo(
    anio:      int,
    mes:       int,
    auth_data: dict         = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db),
):
    emisor_id = auth_data.get("emisor_id")
    if not emisor_id:
        raise HTTPException(status_code=400, detail="Emisor no vinculado.")
    verificar_permiso(auth_data, "declaraciones")
    if not (1 <= mes <= 12):
        raise HTTPException(status_code=400, detail="Mes inválido.")

    fi = date(anio, mes, 1)
    ff = date(anio + 1, 1, 1) if mes == 12 else date(anio, mes + 1, 1)

    # ── Ventas — FAC + LIQ autorizados ───────────────────────────────────
    res_ventas = await db.execute(text("""
        SELECT
            COALESCE(SUM(importe_total), 0) AS total_ventas,
            COALESCE(SUM(
                CASE WHEN tipo_doc IN ('FAC','LIQ')
                THEN (datos->'infoFactura'->>'totalSinImpuestos')::numeric
                ELSE 0 END
            ), 0) AS base_imponible,
            COALESCE(SUM(
                CASE WHEN tipo_doc IN ('FAC','LIQ')
                THEN importe_total - COALESCE(
                    (datos->'infoFactura'->>'totalSinImpuestos')::numeric, 0
                )
                ELSE 0 END
            ), 0) AS iva_cobrado
        FROM documentos_emitidos
        WHERE emisor_id  = :eid
          AND tipo_doc   IN ('FAC', 'LIQ')
          AND estado_sri = 'AUTORIZADO'
          AND fecha_emision >= :fi
          AND fecha_emision <  :ff
    """), {"eid": emisor_id, "fi": fi, "ff": ff})
    ventas = res_ventas.fetchone()

    # ── Compras — usa columnas desnormalizadas ────────────────────────────
    res_compras = await db.execute(text("""
        SELECT
            COALESCE(SUM(importe_total),  0)                                           AS total_compras,
            COALESCE(SUM(CASE WHEN deducible_renta        THEN subtotal_base   ELSE 0 END), 0) AS total_deducible,
            COALESCE(SUM(CASE WHEN credito_tributario_iva THEN valor_iva_total ELSE 0 END), 0) AS credito_tributario
        FROM documentos_recibidos
        WHERE emisor_id  = :eid
          AND tipo_doc   IN ('FAC', 'LIQ')
          AND fecha_emision >= :fi
          AND fecha_emision <  :ff
    """), {"eid": emisor_id, "fi": fi, "ff": ff})
    compras = res_compras.fetchone()

    # ── Retenciones recibidas — suma valor_iva_total de RET recibidas ─────
    # Las RET que nos hicieron tienen el IVA retenido en valor_iva_total
    res_ret = await db.execute(text("""
        SELECT COALESCE(SUM(valor_iva_total), 0) AS total_retenciones
        FROM documentos_recibidos
        WHERE emisor_id  = :eid
          AND tipo_doc   = 'RET'
          AND fecha_emision >= :fi
          AND fecha_emision <  :ff
    """), {"eid": emisor_id, "fi": fi, "ff": ff})
    retenciones = res_ret.fetchone()

    iva_cobrado        = float(ventas.iva_cobrado)
    credito_tributario = float(compras.credito_tributario)
    ret_recibidas      = float(retenciones.total_retenciones)

    iva_causado = iva_cobrado - credito_tributario
    iva_a_pagar = max(0, iva_causado - ret_recibidas)
    saldo_favor = abs(min(0, iva_causado - ret_recibidas))

    totales = {
        "ventas": {
            "total":          float(ventas.total_ventas),
            "base_imponible": float(ventas.base_imponible),
            "iva_cobrado":    iva_cobrado,
        },
        "compras": {
            "total":              float(compras.total_compras),
            "total_deducible":    float(compras.total_deducible),
            "credito_tributario": credito_tributario,
        },
        "retenciones_recibidas": ret_recibidas,
        "resumen_iva": {
            "iva_cobrado":        iva_cobrado,
            "credito_tributario": credito_tributario,
            "iva_causado":        round(iva_causado, 2),
            "retenciones":        ret_recibidas,
            "iva_a_pagar":        round(iva_a_pagar, 2),
            "saldo_a_favor":      round(saldo_favor, 2),
        }
    }

    return {
        "ok":      True,
        "periodo": f"{str(fi)} al {str(ff - timedelta(days=1))}",
        "data":    totales,
    }

# =============================================================================
# POST /declarar — marcar período como declarado
# =============================================================================

@router.get("/reportes", summary="Reportes tributarios guardados")
async def listar_reportes(
    tipo:      str          = Query("IVA"),
    anio:      int          = Query(...),
    auth_data: dict         = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db),
):
    emisor_id = auth_data.get("emisor_id")
    verificar_permiso(auth_data, "reportes")
    res = await db.execute(text("""
        SELECT tipo, periodo, tipo_periodo,
               total_doc_emitidos, total_doc_recibidos,
               generado_at, regenerado_at, resumen
        FROM reportes_tributarios
        WHERE emisor_id = :eid
          AND tipo      = :tipo
          AND EXTRACT(YEAR FROM periodo) = :anio
        ORDER BY periodo DESC
    """), {"eid": emisor_id, "tipo": tipo, "anio": anio})
    rows = res.fetchall()
    return {
        "ok":   True,
        "data": [
            {
                "tipo":                r.tipo,
                "periodo":             str(r.periodo),
                "tipo_periodo":        r.tipo_periodo,
                "total_doc_emitidos":  r.total_doc_emitidos,
                "total_doc_recibidos": r.total_doc_recibidos,
                "generado_at":         str(r.generado_at),
                "regenerado_at":       str(r.regenerado_at) if r.regenerado_at else None,
                "resumen":             r.resumen or {},
            }
            for r in rows
        ]
    }

@router.post("/declarar", summary="Marcar declaración como realizada")
async def marcar_declarado(
    tipo:      str          = Query("104"),
    auth_data: dict         = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db),
):
    emisor_id  = auth_data.get("emisor_id")
    profile_id = auth_data.get("profile_id")
    if not emisor_id:
        raise HTTPException(status_code=400, detail="Emisor no vinculado.")
    verificar_permiso(auth_data, "declaraciones")

    if tipo not in TIPOS_VALIDOS:
        raise HTTPException(status_code=400, detail=f"Tipo inválido. Válidos: {', '.join(TIPOS_VALIDOS)}")

    hoy     = date.today()
    periodo = _periodo_actual(tipo, hoy)

    res = await db.execute(text("""
        UPDATE declaraciones_sri SET
            declarado       = true,
            fecha_declarado = NOW(),
            declarado_por   = :pid
        WHERE emisor_id = :eid
          AND tipo      = :tipo
          AND periodo   = :periodo
        RETURNING id
    """), {
        "eid":     emisor_id,
        "pid":     str(profile_id) if profile_id else None,
        "tipo":    tipo,
        "periodo": periodo,
    })

    updated = res.fetchone()
    if not updated:
        raise HTTPException(status_code=404, detail="Declaración no encontrada.")

    await db.commit()

    return {
        "ok":      True,
        "mensaje": "Declaración marcada correctamente. ¡Hasta el próximo período!"
    }



# =============================================================================
# GET /iva — Casilleros formulario 104
# =============================================================================
@router.get("/iva", summary="Casilleros formulario 104 — Declaración IVA mensual")
async def casilleros_iva(
    periodo:             str          = Query(..., description="Período YYYY-MM, ej: 2026-08"),
    tipo_periodo:        str          = Query("MENSUAL", description="MENSUAL | SEMESTRAL"),
    regenerar:           bool         = Query(False, description="Forzar recálculo aunque esté guardado"),
    auth_data:           dict         = Depends(verify_firebase_token),
    db:                  AsyncSession = Depends(get_db),
):
    emisor_id  = auth_data.get("emisor_id")
    profile_id = auth_data.get("profile_id")
    if not emisor_id:
        raise HTTPException(status_code=400, detail="Emisor no vinculado.")
    verificar_permiso(auth_data, "declaraciones")

    try:
        año, mes = int(periodo.split("-")[0]), int(periodo.split("-")[1])
        if not (1 <= mes <= 12):
            raise ValueError()
    except Exception:
        raise HTTPException(status_code=400, detail="Formato inválido. Use YYYY-MM.")

    hoy = date.today()
    es_mes_actual = (año == hoy.year and mes == hoy.month)

    # Para SEMESTRAL calculamos el rango completo (6 meses)
    if tipo_periodo == "SEMESTRAL":
        if mes <= 6:
            fi = date(año, 1, 1)
            ff = date(año, 6, 30)
        else:
            fi = date(año, 7, 1)
            ff = date(año, 12, 31)
        es_mes_actual = (hoy >= fi and hoy <= ff)
    else:
        fi = date(año, mes, 1)
        ff = date(año, mes, calendar.monthrange(año, mes)[1])

    periodo_db = fi  # primer día del período para guardar en DB

    # ── Verificar suscripción ──────────────────────────────────────────────
    if not await _verificar_suscripcion(emisor_id, db):
        return {"ok": True, "demo": True, "cached": False, "en_curso": False,
                "total_doc_emitidos": 0, "total_doc_recibidos": 0,
                "data": _datos_demo_iva()}

    # ── Verificar si existe reporte guardado ───────────────────────────────
    if not es_mes_actual and not regenerar:
        res_cached = await db.execute(text("""
            SELECT id, casilleros, preguntas, desglose, resumen,
                   campos_manuales_valores,
                   total_doc_emitidos, total_doc_recibidos,
                   generado_at, regenerado_at
            FROM reportes_tributarios
            WHERE emisor_id = :eid
              AND tipo      = 'IVA'
              AND periodo   = :periodo
        """), {"eid": emisor_id, "periodo": periodo_db})
        cached = res_cached.fetchone()
        if cached:
            return {
                "ok":            True,
                "cached":        True,
                "generado_at":   str(cached.generado_at),
                "regenerado_at": str(cached.regenerado_at) if cached.regenerado_at else None,
                "campos_manuales_valores": cached.campos_manuales_valores or {},
                "total_doc_emitidos":  cached.total_doc_emitidos,
                "total_doc_recibidos": cached.total_doc_recibidos,
                "data": {
                    "periodo":   {"desde": str(fi), "hasta": str(ff), "mes": periodo, "tipo": tipo_periodo},
                    "preguntas": cached.preguntas,
                    "ventas":    cached.desglose.get("ventas", {}),
                    "compras":   cached.desglose.get("compras", {}),
                    "retenciones_emitidas":  cached.desglose.get("retenciones_emitidas", {}),
                    "retenciones_recibidas": cached.desglose.get("retenciones_recibidas", {}),
                    "resumen":   cached.resumen,
                    "casilleros_completos": cached.casilleros,
                    "notas": [
                        "Reporte generado previamente — los datos corresponden al período cerrado.",
                        "Usa ?regenerar=true para recalcular si corregiste documentos.",
                    ],
                }
            }

    # ── Calcular en tiempo real ────────────────────────────────────────────

    # VENTAS — FAC + LIQ emitidos por tarifa dinámica
    res_ventas = await db.execute(text("""
        SELECT
            d.id,
            (imp->>'tarifa')::numeric                    AS tarifa,
            SUM((imp->>'baseImponible')::numeric)     AS subtotal,
            SUM((imp->>'valor')::numeric)             AS iva,
            COUNT(DISTINCT d.id)                      AS num_docs
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
          AND d.tipo_doc      IN ('FAC', 'LIQ')
        GROUP BY d.id, (imp->>'tarifa')::numeric
        ORDER BY tarifa
    """), {"eid": emisor_id, "fi": fi, "ff": ff})

    ventas_por_tarifa = {}
    doc_emitidos_ids  = set()
    for r in res_ventas.fetchall():
        doc_emitidos_ids.add(str(r.id))
        t = float(r.tarifa or 0)
        if t not in ventas_por_tarifa:
            ventas_por_tarifa[t] = {"subtotal": 0.0, "iva": 0.0, "num_docs": 0}
        ventas_por_tarifa[t]["subtotal"] += float(r.subtotal or 0)
        ventas_por_tarifa[t]["iva"]      += float(r.iva or 0)
        ventas_por_tarifa[t]["num_docs"] += int(r.num_docs or 0)

    # NCR emitidas
    res_ncr_e = await db.execute(text("""
        SELECT
            d.id,
            (imp->>'tarifa')::numeric              AS tarifa,
            SUM((imp->>'baseImponible')::numeric) AS subtotal,
            SUM((imp->>'valor')::numeric)         AS iva
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
          AND d.tipo_doc      = 'NCR'
        GROUP BY d.id, (imp->>'tarifa')::numeric
    """), {"eid": emisor_id, "fi": fi, "ff": ff})
    ncr_e = {}
    for r in res_ncr_e.fetchall():
        doc_emitidos_ids.add(str(r.id))
        t = float(r.tarifa or 0)
        if t not in ncr_e:
            ncr_e[t] = {"subtotal": 0.0, "iva": 0.0}
        ncr_e[t]["subtotal"] += float(r.subtotal or 0)
        ncr_e[t]["iva"]      += float(r.iva or 0)

    # Totales comprobantes emitidos / anulados
    res_cnt_e = await db.execute(text("""
        SELECT
            COUNT(*) FILTER (WHERE estado_sri != 'ANULADO') AS emitidos,
            COUNT(*) FILTER (WHERE estado_sri  = 'ANULADO') AS anulados
        FROM documentos_emitidos
        WHERE emisor_id     = :eid
          AND fecha_emision BETWEEN :fi AND :ff
          AND es_sandbox    = false
    """), {"eid": emisor_id, "fi": fi, "ff": ff})
    cnt_e = res_cnt_e.fetchone()

    # COMPRAS — usa items_detalle por tarifa y crédito
    res_compras = await db.execute(text("""
        SELECT
            d.id,
            (item->>'tarifa_iva')::numeric                     AS tarifa,
            (item->>'credito_tributario_iva')::boolean     AS aplica_credito,
            SUM((item->>'subtotal')::numeric)              AS subtotal,
            SUM((item->>'valor_iva')::numeric)             AS iva
        FROM documentos_recibidos d,
             jsonb_array_elements(d.items_detalle) AS item
        WHERE d.emisor_id     = :eid
          AND d.fecha_emision BETWEEN :fi AND :ff
          AND d.tipo_doc      IN ('FAC', 'LIQ')
          AND jsonb_array_length(COALESCE(d.items_detalle, '[]'::jsonb)) > 0
        GROUP BY d.id, (item->>'tarifa_iva')::numeric,
                       (item->>'credito_tributario_iva')::boolean
        ORDER BY tarifa, aplica_credito
    """), {"eid": emisor_id, "fi": fi, "ff": ff})
    cc = {}
    sc = {}
    c0 = 0.0
    doc_recibidos_ids = set()
    for r in res_compras.fetchall():
        doc_recibidos_ids.add(str(r.id))
        t = float(r.tarifa or 0)
        if t == 0:
            c0 += float(r.subtotal or 0)
        elif r.aplica_credito:
            cc[t] = cc.get(t, {"subtotal": 0.0, "iva": 0.0})
            cc[t]["subtotal"] += float(r.subtotal or 0)
            cc[t]["iva"]      += float(r.iva or 0)
        else:
            sc[t] = sc.get(t, {"subtotal": 0.0, "iva": 0.0})
            sc[t]["subtotal"] += float(r.subtotal or 0)
            sc[t]["iva"]      += float(r.iva or 0)

    # NCR recibidas — desde items_detalle
    res_ncr_r = await db.execute(text("""
        SELECT
            d.id,
            (item->>'tarifa_iva')::numeric             AS tarifa,
            SUM((item->>'subtotal')::numeric)          AS subtotal,
            SUM((item->>'valor_iva')::numeric)          AS iva
        FROM documentos_recibidos d,
             jsonb_array_elements(d.items_detalle) AS item
        WHERE d.emisor_id     = :eid
          AND d.fecha_emision BETWEEN :fi AND :ff
          AND d.tipo_doc      = 'NCR'
          AND jsonb_array_length(COALESCE(d.items_detalle, '[]'::jsonb)) > 0
        GROUP BY d.id, (item->>'tarifa_iva')::numeric
    """), {"eid": emisor_id, "fi": fi, "ff": ff})
    ncr_r = {}
    for r in res_ncr_r.fetchall():
        doc_recibidos_ids.add(str(r.id))
        t = float(r.tarifa or 0)
        if t not in ncr_r:
            ncr_r[t] = {"subtotal": 0.0, "iva": 0.0}
        ncr_r[t]["subtotal"] += float(r.subtotal or 0)
        ncr_r[t]["iva"]      += float(r.iva or 0)

    # RET que NOS hicieron — solo IVA retenido (casillero 609)
    res_ret_r = await db.execute(text("""
        SELECT
            d.id,
            SUM((item->>'total')::numeric) AS total
        FROM documentos_recibidos d,
             jsonb_array_elements(d.items_detalle) AS item
        WHERE d.emisor_id     = :eid
          AND d.fecha_emision BETWEEN :fi AND :ff
          AND d.tipo_doc      = 'RET'
          AND jsonb_array_length(COALESCE(d.items_detalle, '[]'::jsonb)) > 0
          AND (item->>'codigo_impuesto') = '2'
        GROUP BY d.id
    """), {"eid": emisor_id, "fi": fi, "ff": ff})

    c609 = 0.0
    for r in res_ret_r.fetchall():
        doc_recibidos_ids.add(str(r.id))
        c609 += float(r.total or 0)
    c609 = round(c609, 2)

    # RET que NOSOTROS hicimos (721-731)
    res_ret_e = await db.execute(text("""
        SELECT
            d.id,
            (imp->>'porcentajeRetener')::numeric   AS pct,
            SUM((imp->>'valorRetenido')::numeric)  AS valor
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
          AND (imp->>'codigo') = '2'
        GROUP BY d.id, (imp->>'porcentajeRetener')::numeric
    """), {"eid": emisor_id, "fi": fi, "ff": ff})
    PCT_CAS = {10: 721, 20: 723, 30: 725, 50: 727, 70: 729, 100: 731}
    cas_ret = {v: 0.0 for v in PCT_CAS.values()}
    ret_e_desglose = []
    total_ret_e = 0.0
    for r in res_ret_e.fetchall():
        doc_emitidos_ids.add(str(r.id))
        pct   = float(r.pct or 0)
        valor = float(r.valor or 0)
        cas   = PCT_CAS.get(int(pct))
        if cas:
            cas_ret[cas] = round(valor, 2)
        total_ret_e += valor
        ret_e_desglose.append({"porcentaje": pct, "valor": round(valor, 2)})

    # Totales recibidos
    res_cnt_r = await db.execute(text("""
        SELECT
            COUNT(*) FILTER (WHERE tipo_doc IN ('FAC','NCR','NDB','RET')) AS recibidos,
            COUNT(*) FILTER (WHERE tipo_doc = 'LIQ')                     AS liq
        FROM documentos_recibidos
        WHERE emisor_id     = :eid
          AND fecha_emision BETWEEN :fi AND :ff
    """), {"eid": emisor_id, "fi": fi, "ff": ff})
    cnt_r = res_cnt_r.fetchone()

    # ══════════════════════════════════════════════════
    # CALCULAR CASILLEROS
    # ══════════════════════════════════════════════════
    v_nz = {t: v for t, v in ventas_por_tarifa.items() if t > 0}

    c401 = round(sum(v["subtotal"] for v in v_nz.values()), 2)
    ncr_e_nz_sub = round(sum(v["subtotal"] for t, v in ncr_e.items() if t > 0), 2)
    ncr_e_nz_iva = round(sum(v["iva"]      for t, v in ncr_e.items() if t > 0), 2)
    c411 = round(c401 - ncr_e_nz_sub, 2)
    c421 = round(sum(v["iva"] for v in v_nz.values()) - ncr_e_nz_iva, 2)

    c403 = round(ventas_por_tarifa.get(0.0, {"subtotal": 0.0})["subtotal"], 2)
    c413 = round(c403 - ncr_e.get(0.0, {"subtotal": 0.0})["subtotal"], 2)

    c409 = round(c401 + c403, 2)
    c419 = round(c411 + c413, 2)
    c429 = c421

    ventas_desglose = []
    for t in sorted(ventas_por_tarifa.keys()):
        v   = ventas_por_tarifa[t]
        ncr = ncr_e.get(t, {"subtotal": 0.0, "iva": 0.0})
        ventas_desglose.append({
            "tarifa":    t,
            "bruto":     round(v["subtotal"], 2),
            "ncr":       round(ncr["subtotal"], 2),
            "neto":      round(v["subtotal"] - ncr["subtotal"], 2),
            "iva_bruto": round(v["iva"], 2),
            "iva_neto":  round(v["iva"] - ncr["iva"], 2),
            "num_docs":  v["num_docs"],
        })

    c500 = round(sum(v["subtotal"] for v in cc.values()), 2)
    ncr_r_nz_sub = round(sum(v["subtotal"] for t, v in ncr_r.items() if t > 0), 2)
    ncr_r_nz_iva = round(sum(v["iva"]      for t, v in ncr_r.items() if t > 0), 2)
    c510 = round(c500 - ncr_r_nz_sub, 2)
    c520 = round(sum(v["iva"] for v in cc.values()) - ncr_r_nz_iva, 2)

    c502 = round(sum(v["subtotal"] for v in sc.values()), 2)
    c512 = c502
    c522 = round(sum(v["iva"] for v in sc.values()), 2)

    c507 = round(c0, 2)
    c517 = c507
    c509 = round(c500 + c502 + c507, 2)
    c519 = round(c510 + c512 + c517, 2)
    c529 = round(c520 + c522, 2)

    compras_desglose = []
    for t in sorted(set(cc.keys()) | set(sc.keys())):
        ccv = cc.get(t, {"subtotal": 0.0, "iva": 0.0})
        scv = sc.get(t, {"subtotal": 0.0, "iva": 0.0})
        ncr = ncr_r.get(t, {"subtotal": 0.0, "iva": 0.0})
        compras_desglose.append({
            "tarifa":          t,
            "con_credito":     round(ccv["subtotal"], 2),
            "sin_credito":     round(scv["subtotal"], 2),
            "ncr":             round(ncr["subtotal"], 2),
            "neto":            round(ccv["subtotal"] + scv["subtotal"] - ncr["subtotal"], 2),
            "iva_credito":     round(ccv["iva"], 2),
            "iva_sin_credito": round(scv["iva"], 2),
            "iva_neto":        round(ccv["iva"] + scv["iva"] - ncr["iva"], 2),
        })

    c799 = round(total_ret_e, 2)
    c801 = c799

    c499 = c429
    c564 = c520
    dif  = round(c499 - c564, 2)
    c601 = round(dif,        2) if dif > 0 else 0.0
    c602 = round(abs(dif),   2) if dif < 0 else 0.0
    c620 = round(max(c601 - c609, 0), 2)
    c699 = c620
    c859 = round(c699 + c801, 2)

    preguntas = {
        "requiere_informar":         c409 > 0 or c509 > 0,
        "credito_tributario_renta": c520 > 0,
        "comercio_exterior":         False,
        "notas_credito":             ncr_e_nz_sub > 0 or ncr_r_nz_sub > 0,
        "tarifa_turismo":            any(t == 8.0 for t in ventas_por_tarifa),
        "ha_realizado_ventas":       c409 > 0,
        "ventas_tarifa_0":           c403 > 0,
        "ventas_activos_fijos":      False,
        "ventas_tarifa_nz":          c401 > 0,
        "ha_realizado_compras":      c509 > 0,
        "importaciones":             False,
        "compras_activos_fijos":     False,
        "ha_realizado_retenciones": c799 > 0 or c609 > 0,
        "materiales_construccion":   any(t == 5.0 for t in ventas_por_tarifa),
    }

    # Armar estructuras para guardar
    casilleros_completos = {
        "ventas":    {"401": c401, "411": c411, "421": c421, "403": c403,
                      "413": c413, "409": c409, "419": c419, "429": c429,
                      "111": int(cnt_e.emitidos or 0), "113": int(cnt_e.anulados or 0)},
        "compras":  {"500": c500, "510": c510, "520": c520, "502": c502,
                      "512": c512, "522": c522, "507": c507, "517": c517,
                      "509": c509, "519": c519, "529": c529,
                      "115": int(cnt_r.recibidos or 0), "119": int(cnt_r.liq or 0)},
        "ret_emit": {**{str(k): v for k, v in cas_ret.items()}, "799": c799, "801": c801},
        "ret_recib": {"609": c609},
        "resumen":  {"499": c499, "564": c564, "601": c601, "602": c602,
                      "609": c609, "620": c620, "699": c699, "799": c799,
                      "801": c801, "859": c859},
    }
    desglose_completo = {
        "ventas":                    {"desglose": ventas_desglose,  "casilleros": casilleros_completos["ventas"]},
        "compras":                   {"desglose": compras_desglose, "casilleros": casilleros_completos["compras"]},
        "retenciones_emitidas": {"desglose": ret_e_desglose,  "casilleros": casilleros_completos["ret_emit"]},
        "retenciones_recibidas":{"casilleros": casilleros_completos["ret_recib"]},
    }
    resumen_completo = {
        "casilleros": casilleros_completos["resumen"],
        "campos_manuales": [
            {"casillero": "605", "descripcion": "Saldo crédito tributario mes anterior (adquisiciones)"},
            {"casillero": "606", "descripcion": "Saldo crédito tributario mes anterior (retenciones)"},
            {"casillero": "402", "descripcion": "Ventas de activos fijos gravadas tarifa ≠ 0"},
            {"casillero": "501", "descripcion": "Adquisiciones de activos fijos con crédito tributario"},
            {"casillero": "504", "descripcion": "Importaciones de bienes gravados tarifa ≠ 0"},
        ],
    }

    # ── Guardar si es período cerrado ─────────────────────────────────────
    if not es_mes_actual:
        try:
            if regenerar:
                await db.execute(text("""
                    UPDATE reportes_tributarios SET
                        casilleros          = CAST(:casilleros AS jsonb),
                        preguntas           = CAST(:preguntas  AS jsonb),
                        desglose            = CAST(:desglose    AS jsonb),
                        resumen             = CAST(:resumen     AS jsonb),
                        doc_emitidos_ids    = CAST(:doc_e       AS jsonb),
                        doc_recibidos_ids   = CAST(:doc_r       AS jsonb),
                        total_doc_emitidos  = :total_e,
                        total_doc_recibidos = :total_r,
                        regenerado_at       = NOW(),
                        regenerado_por      = :pid
                    WHERE emisor_id = :eid AND tipo = 'IVA' AND periodo = :periodo
                """), {
                    "eid":        emisor_id,
                    "periodo":    periodo_db,
                    "casilleros": json.dumps(casilleros_completos),
                    "preguntas":  json.dumps(preguntas),
                    "desglose":   json.dumps(desglose_completo),
                    "resumen":    json.dumps(resumen_completo),
                    "doc_e":      json.dumps(list(doc_emitidos_ids)),
                    "doc_r":      json.dumps(list(doc_recibidos_ids)),
                    "total_e":    len(doc_emitidos_ids),
                    "total_r":    len(doc_recibidos_ids),
                    "pid":        str(profile_id) if profile_id else None,
                })
            else:
                await db.execute(text("""
                    INSERT INTO reportes_tributarios (
                        emisor_id, tipo, tipo_periodo, periodo,
                        casilleros, preguntas, desglose, resumen,
                        doc_emitidos_ids, doc_recibidos_ids,
                        total_doc_emitidos, total_doc_recibidos,
                        generado_por
                    ) VALUES (
                        :eid, 'IVA', :tipo_periodo, :periodo,
                        CAST(:casilleros AS jsonb), CAST(:preguntas AS jsonb),
                        CAST(:desglose AS jsonb),    CAST(:resumen AS jsonb),
                        CAST(:doc_e AS jsonb), CAST(:doc_r AS jsonb),
                        :total_e, :total_r, :pid
                    )
                    ON CONFLICT (emisor_id, tipo, periodo) DO NOTHING
                """), {
                    "eid":          emisor_id,
                    "tipo_periodo": tipo_periodo,
                    "periodo":      periodo_db,
                    "casilleros":   json.dumps(casilleros_completos),
                    "preguntas":    json.dumps(preguntas),
                    "desglose":     json.dumps(desglose_completo),
                    "resumen":      json.dumps(resumen_completo),
                    "doc_e":        json.dumps(list(doc_emitidos_ids)),
                    "doc_r":        json.dumps(list(doc_recibidos_ids)),
                    "total_e":      len(doc_emitidos_ids),
                    "total_r":      len(doc_recibidos_ids),
                    "pid":          str(profile_id) if profile_id else None,
                })
            await db.commit()
        except Exception as e:
            print(f"[IVA] ⚠️ Error guardando reporte: {e}")
            await db.rollback()

    return {
        "ok":     True,
        "cached": False,
        "en_curso": es_mes_actual,
        "total_doc_emitidos":  len(doc_emitidos_ids),
        "total_doc_recibidos": len(doc_recibidos_ids),
        "data": {
            "periodo":   {"desde": str(fi), "hasta": str(ff), "mes": periodo, "tipo": tipo_periodo},
            "preguntas": preguntas,
            **desglose_completo,
            "resumen":   resumen_completo,
            "campos_manuales_valores": await _leer_campos_manuales(emisor_id, periodo_db, db),
            "notas": [
                "Los casilleros 605/606 (saldo mes anterior) deben ingresarse manualmente.",
                "Activos fijos e importaciones requieren clasificación manual.",
                "Las tarifas de IVA se calculan dinámicamente.",
            ] + (["⚠️ Período en curso — los valores pueden cambiar."] if es_mes_actual else []),
        }
    }


async def _leer_campos_manuales(emisor_id: int, periodo_db: date, db: AsyncSession) -> dict:
    """Lee los campos manuales guardados para un período, si existen."""
    try:
        res = await db.execute(text("""
            SELECT campos_manuales_valores
            FROM reportes_tributarios
            WHERE emisor_id = :eid AND tipo = 'IVA' AND periodo = :periodo
        """), {"eid": emisor_id, "periodo": periodo_db})
        row = res.fetchone()
        return row.campos_manuales_valores or {} if row else {}
    except Exception:
        return {}

# =============================================================================
# PATCH /iva/campos-manuales — Guardar valores manuales del formulario 104
# =============================================================================
@router.patch("/iva/campos-manuales", summary="Guardar casilleros manuales del formulario 104")
async def guardar_campos_manuales_iva(
    periodo:   str          = Query(..., description="Período YYYY-MM, ej: 2026-08"),
    auth_data: dict         = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db),
    body:      dict         = Body(..., example={"605": 150.00, "606": 0.00}),
):
    emisor_id  = auth_data.get("emisor_id")
    profile_id = auth_data.get("profile_id")
    if not emisor_id:
        raise HTTPException(status_code=400, detail="Emisor no vinculado.")
    verificar_permiso(auth_data, "declaraciones")

    try:
        año, mes = int(periodo.split("-")[0]), int(periodo.split("-")[1])
        if not (1 <= mes <= 12):
            raise ValueError()
    except Exception:
        raise HTTPException(status_code=400, detail="Formato inválido. Use YYYY-MM.")

    # Validar que solo vengan casilleros permitidos y valores numéricos
    CASILLEROS_PERMITIDOS = {"605", "606", "402", "501", "504"}
    valores_limpios = {}
    for cas, val in body.items():
        if cas not in CASILLEROS_PERMITIDOS:
            raise HTTPException(status_code=400, detail=f"Casillero {cas} no permitido.")
        try:
            valores_limpios[cas] = round(float(val), 2)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail=f"Valor inválido para casillero {cas}.")

    periodo_db = date(año, mes, 1)

    # Upsert — si no existe el reporte todavía, lo crea vacío con los campos manuales
    await db.execute(text("""
        INSERT INTO reportes_tributarios (
            emisor_id, tipo, tipo_periodo, periodo,
            casilleros, preguntas, desglose, resumen,
            campos_manuales_valores,
            doc_emitidos_ids, doc_recibidos_ids,
            total_doc_emitidos, total_doc_recibidos,
            generado_por
        ) VALUES (
            :eid, 'IVA', 'MENSUAL', :periodo,
            '{}', '{}', '{}', '{}',
            CAST(:valores AS jsonb),
            '[]', '[]', 0, 0, :pid
        )
        ON CONFLICT (emisor_id, tipo, periodo) DO UPDATE SET
            campos_manuales_valores = CAST(:valores AS jsonb)
    """), {
        "eid":     emisor_id,
        "periodo": periodo_db,
        "valores": json.dumps(valores_limpios),
        "pid":     str(profile_id) if profile_id else None,
    })
    await db.commit()

    return {
        "ok":      True,
        "periodo": periodo,
        "valores": valores_limpios,
        "mensaje": "Valores guardados correctamente.",
    }


# =============================================================================
# GET /renta — Formulario 102 — Impuesto a la Renta anual
# =============================================================================
@router.get("/renta", summary="Casilleros formulario 102 — Impuesto a la Renta anual")
async def casilleros_renta(
    anio:        int          = Query(..., description="Año a declarar, ej: 2025"),
    regenerar:  bool         = Query(False, description="Forzar recálculo aunque esté guardado"),
    auth_data:  dict         = Depends(verify_firebase_token),
    db:         AsyncSession = Depends(get_db),
):
    emisor_id  = auth_data.get("emisor_id")
    profile_id = auth_data.get("profile_id")
    if not emisor_id:
        raise HTTPException(status_code=400, detail="Emisor no vinculado.")
    verificar_permiso(auth_data, "declaraciones")

    if anio < 2020 or anio > date.today().year:
        raise HTTPException(status_code=400, detail="Año inválido.")

    fi         = date(anio, 1, 1)
    ff         = date(anio, 12, 31)
    periodo_db = fi
    hoy        = date.today()
    es_anio_actual = (anio == hoy.year)

    # ── Verificar suscripción ──────────────────────────────────────────────
    if not await _verificar_suscripcion(emisor_id, db):
        return {"ok": True, "demo": True, "cached": False, "en_curso": False,
                "total_doc_emitidos": 0, "total_doc_recibidos": 0,
                "data": _datos_demo_renta()}

    # ── Verificar cache ────────────────────────────────────────────────────
    if not es_anio_actual and not regenerar:
        res_cached = await db.execute(text("""
            SELECT id, casilleros, preguntas, desglose, resumen,
                   total_doc_emitidos, total_doc_recibidos,
                   generado_at, regenerado_at
            FROM reportes_tributarios
            WHERE emisor_id = :eid
              AND tipo      = 'RENTA'
              AND periodo   = :periodo
        """), {"eid": emisor_id, "periodo": periodo_db})
        cached = res_cached.fetchone()
        if cached:
            return {
                "ok":            True,
                "cached":        True,
                "generado_at":   str(cached.generado_at),
                "regenerado_at": str(cached.regenerado_at) if cached.regenerado_at else None,
                "total_doc_emitidos":  cached.total_doc_emitidos,
                "total_doc_recibidos": cached.total_doc_recibidos,
                "data": {
                    "periodo":   {"anio": anio, "desde": str(fi), "hasta": str(ff)},
                    "preguntas": cached.preguntas,
                    **cached.desglose,
                    "resumen":   cached.resumen,
                    "notas": ["Reporte generado previamente. Usa ?regenerar=true para recalcular."],
                }
            }

    # ══════════════════════════════════════════════════════════════
    # INGRESOS — FAC + LIQ autorizados del año
    # ══════════════════════════════════════════════════════════════
    res_ingresos = await db.execute(text("""
        SELECT
            d.id,
            (imp->>'tarifa')::numeric                 AS tarifa,
            SUM((imp->>'baseImponible')::numeric)     AS subtotal,
            SUM(d.importe_total)                      AS total
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
          AND d.tipo_doc      IN ('FAC', 'LIQ')
        GROUP BY d.id, (imp->>'tarifa')::numeric
    """), {"eid": emisor_id, "fi": fi, "ff": ff})

    ingresos_brutos   = 0.0
    doc_emitidos_ids  = set()
    for r in res_ingresos.fetchall():
        doc_emitidos_ids.add(str(r.id))
        ingresos_brutos += float(r.subtotal or 0)

    # NCR emitidas — reducen ingresos
    res_ncr = await db.execute(text("""
        SELECT
            d.id,
            SUM((imp->>'baseImponible')::numeric) AS subtotal
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
          AND d.tipo_doc      = 'NCR'
        GROUP BY d.id
    """), {"eid": emisor_id, "fi": fi, "ff": ff})

    ncr_total = 0.0
    for r in res_ncr.fetchall():
        doc_emitidos_ids.add(str(r.id))
        ncr_total += float(r.subtotal or 0)

    ingresos_netos = round(ingresos_brutos - ncr_total, 2)

    # ══════════════════════════════════════════════════════════════
    # GASTOS DEDUCIBLES — usa columnas desnormalizadas
    # ══════════════════════════════════════════════════════════════
    res_gastos = await db.execute(text("""
        SELECT
            id,
            subtotal_base AS subtotal
        FROM documentos_recibidos
        WHERE emisor_id       = :eid
          AND fecha_emision   BETWEEN :fi AND :ff
          AND deducible_renta = true
          AND tipo_doc        IN ('FAC', 'LIQ')
    """), {"eid": emisor_id, "fi": fi, "ff": ff})

    gastos_deducibles = 0.0
    doc_recibidos_ids = set()
    for r in res_gastos.fetchall():
        doc_recibidos_ids.add(str(r.id))
        gastos_deducibles += float(r.subtotal or 0)
    gastos_deducibles = round(gastos_deducibles, 2)

    # ══════════════════════════════════════════════════════════════
    # RETENCIONES DE RENTA recibidas — usa items_detalle
    # ══════════════════════════════════════════════════════════════
    res_ret_renta = await db.execute(text("""
        SELECT
            d.id,
            SUM((item->>'total')::numeric) AS valor
        FROM documentos_recibidos d,
             jsonb_array_elements(d.items_detalle) AS item
        WHERE d.emisor_id     = :eid
          AND d.fecha_emision BETWEEN :fi AND :ff
          AND d.tipo_doc      = 'RET'
          AND jsonb_array_length(COALESCE(d.items_detalle, '[]'::jsonb)) > 0
          AND (item->>'codigo_impuesto') = '1'
        GROUP BY d.id
    """), {"eid": emisor_id, "fi": fi, "ff": ff})

    retenciones_renta = 0.0
    for r in res_ret_renta.fetchall():
        doc_recibidos_ids.add(str(r.id))
        retenciones_renta += float(r.valor or 0)
    retenciones_renta = round(retenciones_renta, 2)

    # ══════════════════════════════════════════════════════════════
    # CALCULAR CASILLEROS 102
    # ══════════════════════════════════════════════════════════════

    # Base imponible
    base_imponible = round(ingresos_netos - gastos_deducibles, 2)
    base_imponible = max(base_imponible, 0.0)

    # Tabla progresiva IR personas naturales 2025 (SRI)
    TABLA_IR = [
        {"desde": 0,       "hasta": 11902,  "base": 0,     "porcentaje": 0},
        {"desde": 11902,   "hasta": 15159,  "base": 0,     "porcentaje": 5},
        {"desde": 15159,   "hasta": 19682,  "base": 163,   "porcentaje": 10},
        {"desde": 19682,   "hasta": 26031,  "base": 615,   "porcentaje": 12},
        {"desde": 26031,   "hasta": 34255,  "base": 1377,  "porcentaje": 15},
        {"desde": 34255,   "hasta": 45407,  "base": 2611,  "porcentaje": 20},
        {"desde": 45407,   "hasta": 60450,  "base": 4841,  "porcentaje": 25},
        {"desde": 60450,   "hasta": 80605,  "base": 8602,  "porcentaje": 30},
        {"desde": 80605,   "hasta": 107199, "base": 14648, "porcentaje": 35},
        {"desde": 107199,  "hasta": float("inf"), "base": 23957, "porcentaje": 37},
    ]

    # Calcular impuesto causado según tabla
    impuesto_causado = 0.0
    tramo_aplicado   = None
    for tramo in TABLA_IR:
        if base_imponible > tramo["desde"]:
            exceso           = min(base_imponible, tramo["hasta"]) - tramo["desde"]
            impuesto_causado = tramo["base"] + (exceso * tramo["porcentaje"] / 100)
            tramo_aplicado   = tramo
    impuesto_causado = round(impuesto_causado, 2)

    # Impuesto a pagar / saldo a favor
    impuesto_a_pagar = round(max(impuesto_causado - retenciones_renta, 0), 2)
    saldo_a_favor    = round(max(retenciones_renta - impuesto_causado, 0), 2)

    # Casilleros principales del formulario 102
    casilleros = {
        # INGRESOS
        "501": round(ingresos_brutos, 2),   # ingresos brutos en actividad económica
        "502": round(ncr_total, 2),         # devoluciones y descuentos
        "503": ingresos_netos,              # ingresos netos (501-502)

        # GASTOS DEDUCIBLES
        "601": gastos_deducibles,           # total gastos deducibles

        # BASE IMPONIBLE
        "699": base_imponible,              # base imponible (503-601)
        "701": base_imponible,              # base gravada

        # IMPUESTO
        "801": impuesto_causado,            # impuesto causado

        # CRÉDITOS
        "841": retenciones_renta,           # retenciones en la fuente

        # RESULTADO
        "859": impuesto_a_pagar,            # impuesto a pagar
        "869": saldo_a_favor,               # saldo a favor
    }

    preguntas = {
        "tiene_ingresos":          ingresos_netos > 0,
        "tiene_gastos_deducibles": gastos_deducibles > 0,
        "tiene_retenciones":       retenciones_renta > 0,
        "debe_pagar":              impuesto_a_pagar > 0,
        "tiene_saldo_favor":       saldo_a_favor > 0,
        "supera_fraccion_basica": base_imponible > TABLA_IR[0]["hasta"],
    }

    desglose = {
        "ingresos": {
            "brutos": round(ingresos_brutos, 2),
            "ncr":    round(ncr_total, 2),
            "netos":  ingresos_netos,
        },
        "gastos": {
            "deducibles": gastos_deducibles,
        },
        "base_imponible": base_imponible,
        "tabla_ir": {
            "tramo":      tramo_aplicado,
            "tabla_anio": anio,
            "nota":       "Tabla personas naturales — verificar con resolución SRI vigente",
        },
    }

    resumen = {
        "casilleros": casilleros,
        "campos_manuales": [
            {"casillero": "504", "descripcion": "Otros ingresos (arrendamientos, intereses, etc.)"},
            {"casillero": "602", "descripcion": "Gastos personales (salud, educación, alimentación, vivienda, vestimenta)"},
            {"casillero": "603", "descripcion": "Rebaja por tercera edad o discapacidad"},
            {"casillero": "842", "descripcion": "Anticipo pagado año anterior"},
            {"casillero": "843", "descripcion": "Crédito tributario de años anteriores"},
        ],
        "resultado": {
            "impuesto_causado": impuesto_causado,
            "retenciones":      retenciones_renta,
            "a_pagar":          impuesto_a_pagar,
            "saldo_favor":      saldo_a_favor,
        }
    }

    # ── Guardar si es año cerrado ──────────────────────────────────────────
    if not es_anio_actual:
        try:
            await db.execute(text("""
                INSERT INTO reportes_tributarios (
                    emisor_id, tipo, tipo_periodo, periodo,
                    casilleros, preguntas, desglose, resumen,
                    doc_emitidos_ids, doc_recibidos_ids,
                    total_doc_emitidos, total_doc_recibidos,
                    generado_por
                ) VALUES (
                    :eid, 'RENTA', 'ANUAL', :periodo,
                    CAST(:casilleros AS jsonb), CAST(:preguntas AS jsonb),
                    CAST(:desglose AS jsonb),   CAST(:resumen AS jsonb),
                    CAST(:doc_e AS jsonb), CAST(:doc_r AS jsonb),
                    :total_e, :total_r, :pid
                )
                ON CONFLICT (emisor_id, tipo, periodo)
                DO UPDATE SET
                    casilleros          = CAST(:casilleros AS jsonb),
                    preguntas           = CAST(:preguntas  AS jsonb),
                    desglose            = CAST(:desglose   AS jsonb),
                    resumen             = CAST(:resumen    AS jsonb),
                    doc_emitidos_ids    = CAST(:doc_e      AS jsonb),
                    doc_recibidos_ids   = CAST(:doc_r      AS jsonb),
                    total_doc_emitidos  = :total_e,
                    total_doc_recibidos = :total_r,
                    regenerado_at       = CASE WHEN :regenerar THEN NOW() ELSE reportes_tributarios.regenerado_at END,
                    regenerado_por      = CASE WHEN :regenerar THEN :pid  ELSE reportes_tributarios.regenerado_por  END
            """), {
                "eid":        emisor_id,
                "periodo":    periodo_db,
                "casilleros": json.dumps(casilleros),
                "preguntas":  json.dumps(preguntas),
                "desglose":   json.dumps(desglose),
                "resumen":    json.dumps(resumen),
                "doc_e":      json.dumps(list(doc_emitidos_ids)),
                "doc_r":      json.dumps(list(doc_recibidos_ids)),
                "total_e":    len(doc_emitidos_ids),
                "total_r":    len(doc_recibidos_ids),
                "pid":        str(profile_id) if profile_id else None,
                "regenerar":  regenerar,
            })
            await db.commit()
        except Exception as e:
            print(f"[RENTA] ⚠️ Error guardando reporte: {e}")
            await db.rollback()

    return {
        "ok":        True,
        "cached":    False,
        "en_curso": es_anio_actual,
        "total_doc_emitidos":  len(doc_emitidos_ids),
        "total_doc_recibidos": len(doc_recibidos_ids),
        "data": {
            "periodo":   {"anio": anio, "desde": str(fi), "hasta": str(ff)},
            "preguntas": preguntas,
            **desglose,
            "resumen":   resumen,
            "notas": [
                "La tabla de IR corresponde a personas naturales — verifica con la resolución SRI del año.",
                "Los gastos personales (salud, educación, etc.) deben ingresarse manualmente.",
                "Ingresos de otras fuentes (arrendamientos, relación de dependencia) no están incluidos.",
            ] + (["⚠️ Año en curso — los valores son preliminares."] if es_anio_actual else []),
        }
    }

# =============================================================================
# GET /ats — Anexo Transaccional Simplificado
# Solo para obligados a llevar contabilidad
# =============================================================================
@router.get("/ats", summary="Anexo Transaccional Simplificado — ATS mensual")
async def casilleros_ats(
    periodo:    str          = Query(..., description="Período YYYY-MM, ej: 2026-08"),
    regenerar:  bool         = Query(False, description="Forzar recálculo aunque esté guardado"),
    auth_data:  dict         = Depends(verify_firebase_token),
    db:         AsyncSession = Depends(get_db),
):
    emisor_id  = auth_data.get("emisor_id")
    profile_id = auth_data.get("profile_id")
    if not emisor_id:
        raise HTTPException(status_code=400, detail="Emisor no vinculado.")
    verificar_permiso(auth_data, "declaraciones")

    try:
        año, mes = int(periodo.split("-")[0]), int(periodo.split("-")[1])
        if not (1 <= mes <= 12):
            raise ValueError()
    except Exception:
        raise HTTPException(status_code=400, detail="Formato inválido. Use YYYY-MM.")

    fi         = date(año, mes, 1)
    ff         = date(año, mes, calendar.monthrange(año, mes)[1])
    periodo_db = fi
    hoy        = date.today()
    es_mes_actual = (año == hoy.year and mes == hoy.month)

    # Verificar que el emisor exista
    res_emisor = await db.execute(text("""
        SELECT ruc, razon_social, obligado_contabilidad, tipo_emisor
        FROM emisores WHERE id = :eid
    """), {"eid": emisor_id})
    emisor = res_emisor.fetchone()
    if not emisor:
        raise HTTPException(status_code=404, detail="Emisor no encontrado.")

    # ── Verificar suscripción ──────────────────────────────────────────────
    if not await _verificar_suscripcion(emisor_id, db):
        return {"ok": True, "demo": True, "cached": False, "en_curso": False,
                "total_doc_emitidos": 0, "total_doc_recibidos": 0,
                "data": _datos_demo_ats()}
    
    # ── Verificar cache ────────────────────────────────────────────────────
    if not es_mes_actual and not regenerar:
        res_cached = await db.execute(text("""
            SELECT id, casilleros, preguntas, desglose, resumen,
                   total_doc_emitidos, total_doc_recibidos,
                   generado_at, regenerado_at
            FROM reportes_tributarios
            WHERE emisor_id = :eid
              AND tipo      = 'ATS'
              AND periodo   = :periodo
        """), {"eid": emisor_id, "periodo": periodo_db})
        cached = res_cached.fetchone()
        if cached:
            return {
                "ok":            True,
                "cached":        True,
                "generado_at":   str(cached.generado_at),
                "regenerado_at": str(cached.regenerado_at) if cached.regenerado_at else None,
                "total_doc_emitidos":  cached.total_doc_emitidos,
                "total_doc_recibidos": cached.total_doc_recibidos,
                "data": {
                    "periodo":  {"desde": str(fi), "hasta": str(ff), "mes": periodo},
                    **cached.desglose,
                    "resumen":  cached.resumen,
                    "notas": ["Reporte generado previamente. Usa ?regenerar=true para recalcular."],
                }
            }

    # ══════════════════════════════════════════════════════════════
    # VENTAS — detalle por comprobante emitido
    # ══════════════════════════════════════════════════════════════
    res_ventas = await db.execute(text("""
        SELECT
            d.id,
            d.tipo_doc,
            d.cod_doc,
            d.numero_doc,
            d.clave_acceso,
            d.fecha_emision,
            d.importe_total,
            d.datos->'infoFactura'->>'identificacionComprador'    AS id_comprador_fac,
            d.datos->'infoFactura'->>'razonSocialComprador'        AS razon_fac,
            d.datos->'infoFactura'->>'tipoIdentificacionComprador' AS tipo_id_fac,
            d.datos->'infoLiquidacionCompra'->>'identificacionProveedor'   AS id_comprador_liq,
            d.datos->'infoLiquidacionCompra'->>'razonSocialProveedor'       AS razon_liq,
            d.datos->>'legacy_id_comprador'    AS id_legacy,
            d.datos->>'legacy_razon_comprador' AS razon_legacy,
            d.datos->'resumenImpuestos'        AS resumen_impuestos
        FROM documentos_emitidos d
        WHERE d.emisor_id     = :eid
          AND d.estado_sri    = 'AUTORIZADO'
          AND d.fecha_emision BETWEEN :fi AND :ff
          AND d.es_sandbox    = false
          AND d.tipo_doc      IN ('FAC', 'LIQ', 'NCR', 'NDB')
        ORDER BY d.fecha_emision, d.numero_doc
    """), {"eid": emisor_id, "fi": fi, "ff": ff})

    ventas_detalle   = []
    doc_emitidos_ids = set()
    totales_ventas   = {
        "base_iva_diferente_0": 0.0,
        "base_iva_0":           0.0,
        "iva":                  0.0,
        "total":                0.0,
        "num_docs":             0,
    }

    for r in res_ventas.fetchall():
        doc_emitidos_ids.add(str(r.id))
        id_comp   = r.id_comprador_fac or r.id_comprador_liq or r.id_legacy or "9999999999999"
        razon     = r.razon_fac or r.razon_liq or r.razon_legacy or "CONSUMIDOR FINAL"
        tipo_id   = r.tipo_id_fac or "07"

        # Procesar impuestos
        impuestos = r.resumen_impuestos or []
        if not isinstance(impuestos, list):
            impuestos = [impuestos] if impuestos else []

        base_nz = 0.0
        base_0  = 0.0
        iva     = 0.0
        for imp in impuestos:
            if not isinstance(imp, dict):
                continue
            tarifa = float(imp.get("tarifa", 0) or 0)
            base   = float(imp.get("baseImponible", 0) or 0)
            valor  = float(imp.get("valor", 0) or 0)
            if tarifa == 0:
                base_0  += base
            else:
                base_nz += base
                iva     += valor

        ventas_detalle.append({
            "tipo_doc":       r.tipo_doc,
            "cod_doc":        r.cod_doc,
            "numero_doc":     r.numero_doc,
            "clave_acceso":   r.clave_acceso,
            "fecha_emision":  str(r.fecha_emision),
            "tipo_id":        tipo_id,
            "identificacion": id_comp,
            "razon_social":   razon,
            "base_iva_nz":    round(base_nz, 2),
            "base_iva_0":     round(base_0,  2),
            "iva":            round(iva,     2),
            "total":          float(r.importe_total),
        })

        totales_ventas["base_iva_diferente_0"] += base_nz
        totales_ventas["base_iva_0"]           += base_0
        totales_ventas["iva"]                  += iva
        totales_ventas["total"]                += float(r.importe_total)
        totales_ventas["num_docs"]             += 1

    # Retenciones emitidas
    res_ret_e = await db.execute(text("""
        SELECT
            d.id,
            d.numero_doc,
            d.clave_acceso,
            d.fecha_emision,
            d.datos->'infoCompRetencion'->>'identificacionSujetoRetenido' AS id_retenido,
            d.datos->'infoCompRetencion'->>'razonSocialSujetoRetenido'     AS razon_retenido,
            d.datos->'infoCompRetencion'->>'periodoFiscal'                 AS periodo_fiscal,
            d.datos->'impuestos'                                           AS impuestos
        FROM documentos_emitidos d
        WHERE d.emisor_id     = :eid
          AND d.estado_sri    = 'AUTORIZADO'
          AND d.fecha_emision BETWEEN :fi AND :ff
          AND d.es_sandbox    = false
          AND d.tipo_doc      = 'RET'
        ORDER BY d.fecha_emision, d.numero_doc
    """), {"eid": emisor_id, "fi": fi, "ff": ff})

    retenciones_emitidas = []
    for r in res_ret_e.fetchall():
        doc_emitidos_ids.add(str(r.id))
        impuestos = r.impuestos or {}
        imp_list  = impuestos.get("impuesto", [])
        if not isinstance(imp_list, list):
            imp_list = [imp_list] if imp_list else []

        lineas = []
        for imp in imp_list:
            if not isinstance(imp, dict):
                continue
            lineas.append({
                "codigo":           imp.get("codigo"),
                "codigo_retencion": imp.get("codigoRetencion"),
                "base_imponible":   float(imp.get("baseImponible", 0) or 0),
                "porcentaje":       float(imp.get("porcentajeRetener", 0) or 0),
                "valor_retenido":   float(imp.get("valorRetenido", 0) or 0),
            })

        retenciones_emitidas.append({
            "numero_doc":     r.numero_doc,
            "clave_acceso":   r.clave_acceso,
            "fecha_emision":  str(r.fecha_emision),
            "identificacion": r.id_retenido,
            "razon_social":   r.razon_retenido,
            "periodo_fiscal": r.periodo_fiscal,
            "impuestos":      lineas,
        })

    # ══════════════════════════════════════════════════════════════
    # COMPRAS — detalle por comprobante recibido
    # ══════════════════════════════════════════════════════════════
    res_compras = await db.execute(text("""
        SELECT
            d.id,
            d.tipo_doc,
            d.cod_doc,
            d.numero_doc,
            d.clave_acceso,
            d.fecha_emision,
            d.importe_total,
            d.ruc_proveedor,
            d.razon_social_proveedor,
            d.deducible_renta,
            d.credito_tributario_iva,
            d.fuente,
            d.subtotal_base,
            d.valor_iva_total
        FROM documentos_recibidos d
        WHERE d.emisor_id     = :eid
          AND d.fecha_emision BETWEEN :fi AND :ff
          AND d.tipo_doc      IN ('FAC', 'LIQ', 'NCR', 'NDB')
        ORDER BY d.fecha_emision, d.numero_doc
    """), {"eid": emisor_id, "fi": fi, "ff": ff})

    compras_detalle   = []
    doc_recibidos_ids = set()
    totales_compras   = {
        "base_iva_diferente_0": 0.0,
        "base_iva_0":           0.0,
        "iva_con_credito":      0.0,
        "iva_sin_credito":      0.0,
        "total":                0.0,
        "num_docs":             0,
    }

    for r in res_compras.fetchall():
        doc_recibidos_ids.add(str(r.id))

        base_nz      = float(r.subtotal_base    or 0)
        base_0       = 0.0  # Físicos sin IVA / Exentos
        iva_credito  = float(r.valor_iva_total or 0) if r.credito_tributario_iva else 0.0
        iva_sin_cred = float(r.valor_iva_total or 0) if not r.credito_tributario_iva else 0.0

        compras_detalle.append({
            "tipo_doc":        r.tipo_doc,
            "cod_doc":         r.cod_doc,
            "numero_doc":      r.numero_doc,
            "clave_acceso":    r.clave_acceso or f"FISICO-{r.id}",
            "fecha_emision":   str(r.fecha_emision),
            "ruc_proveedor":   r.ruc_proveedor,
            "razon_proveedor": r.razon_social_proveedor,
            "fuente":          r.fuente,
            "base_iva_nz":     round(base_nz,      2),
            "base_iva_0":      round(base_0,       2),
            "iva_credito":     round(iva_credito,  2),
            "iva_sin_credito": round(iva_sin_cred, 2),
            "total":           float(r.importe_total),
            "deducible_renta": r.deducible_renta,
        })

        totales_compras["base_iva_diferente_0"] += base_nz
        totales_compras["base_iva_0"]           += base_0
        totales_compras["iva_con_credito"]      += iva_credito
        totales_compras["iva_sin_credito"]      += iva_sin_cred
        totales_compras["total"]                += float(r.importe_total)
        totales_compras["num_docs"]             += 1

    # Retenciones recibidas — desglosadas desde items_detalle
    res_ret_r = await db.execute(text("""
        SELECT
            d.id,
            d.numero_doc,
            d.clave_acceso,
            d.fecha_emision,
            d.ruc_proveedor,
            d.razon_social_proveedor,
            d.items_detalle
        FROM documentos_recibidos d
        WHERE d.emisor_id     = :eid
          AND d.fecha_emision BETWEEN :fi AND :ff
          AND d.tipo_doc      = 'RET'
        ORDER BY d.fecha_emision
    """), {"eid": emisor_id, "fi": fi, "ff": ff})

    retenciones_recibidas = []
    for r in res_ret_r.fetchall():
        doc_recibidos_ids.add(str(r.id))
        items = r.items_detalle or []
        lineas = []
        for item in items:
            if not isinstance(item, dict):
                continue
            lineas.append({
                "codigo_impuesto":  item.get("codigo_impuesto"),
                "codigo_retencion": item.get("codigo_retencion"),
                "descripcion":      item.get("descripcion"),
                "base_imponible":   float(item.get("subtotal", 0) or 0),
                "porcentaje":       float(item.get("porcentaje", 0) or 0),
                "valor":            float(item.get("total", 0) or 0),
                "aplica_credito":   item.get("credito_tributario_iva", False),
                "num_doc_sustento": item.get("num_doc_sustento"),
                "cod_doc_sustento": item.get("cod_doc_sustento"),
            })
        retenciones_recibidas.append({
            "numero_doc":    r.numero_doc,
            "clave_acceso":  r.clave_acceso,
            "fecha_emision": str(r.fecha_emision),
            "ruc_agente":    r.ruc_proveedor,
            "razon_agente":  r.razon_social_proveedor,
            "impuestos":     lineas,
        })

    # ══════════════════════════════════════════════════════════════
    # RESUMEN Y TOTALES
    # ══════════════════════════════════════════════════════════════
    for k in totales_ventas:
        if k != "num_docs":
            totales_ventas[k] = round(totales_ventas[k], 2)
    for k in totales_compras:
        if k != "num_docs":
            totales_compras[k] = round(totales_compras[k], 2)

    desglose = {
        "ventas": {
            "detalle":     ventas_detalle,
            "retenciones": retenciones_emitidas,
            "totales":     totales_ventas,
        },
        "compras": {
            "detalle":     compras_detalle,
            "retenciones": retenciones_recibidas,
            "totales":     totales_compras,
        },
    }

    resumen = {
        "emisor": {
            "ruc":                   emisor.ruc,
            "razon_social":           emisor.razon_social,
            "obligado_contabilidad": emisor.obligado_contabilidad,
        },
        "periodo": str(fi),
        "totales_ventas":      totales_ventas,
        "totales_compras":     totales_compras,
        "total_ret_emitidas":  len(retenciones_emitidas),
        "total_ret_recibidas": len(retenciones_recibidas),
    }

    preguntas = {
        "tiene_ventas":              totales_ventas["num_docs"] > 0,
        "tiene_compras":             totales_compras["num_docs"] > 0,
        "tiene_retenciones_emitidas":  len(retenciones_emitidas) > 0,
        "tiene_retenciones_recibidas": len(retenciones_recibidas) > 0,
        "obligado_contabilidad":     emisor.obligado_contabilidad == "SI",
    }

    # ── Guardar si período cerrado ─────────────────────────────────────────
    if not es_mes_actual:
        try:
            await db.execute(text("""
                INSERT INTO reportes_tributarios (
                    emisor_id, tipo, tipo_periodo, periodo,
                    casilleros, preguntas, desglose, resumen,
                    doc_emitidos_ids, doc_recibidos_ids,
                    total_doc_emitidos, total_doc_recibidos,
                    generado_por
                ) VALUES (
                    :eid, 'ATS', 'MENSUAL', :periodo,
                    CAST(:casilleros AS jsonb), CAST(:preguntas AS jsonb),
                    CAST(:desglose   AS jsonb), CAST(:resumen   AS jsonb),
                    CAST(:doc_e AS jsonb), CAST(:doc_r AS jsonb),
                    :total_e, :total_r, :pid
                )
                ON CONFLICT (emisor_id, tipo, periodo)
                DO UPDATE SET
                    casilleros          = CAST(:casilleros AS jsonb),
                    preguntas           = CAST(:preguntas  AS jsonb),
                    desglose            = CAST(:desglose   AS jsonb),
                    resumen             = CAST(:resumen    AS jsonb),
                    doc_emitidos_ids    = CAST(:doc_e      AS jsonb),
                    doc_recibidos_ids   = CAST(:doc_r      AS jsonb),
                    total_doc_emitidos  = :total_e,
                    total_doc_recibidos = :total_r,
                    regenerado_at       = CASE WHEN :regenerar THEN NOW() ELSE reportes_tributarios.regenerado_at END,
                    regenerado_por      = CASE WHEN :regenerar THEN :pid  ELSE reportes_tributarios.regenerado_por  END
            """), {
                "eid":        emisor_id,
                "periodo":    periodo_db,
                "casilleros": json.dumps({}),
                "preguntas":  json.dumps(preguntas),
                "desglose":   json.dumps(desglose),
                "resumen":    json.dumps(resumen),
                "doc_e":      json.dumps(list(doc_emitidos_ids)),
                "doc_r":      json.dumps(list(doc_recibidos_ids)),
                "total_e":    len(doc_emitidos_ids),
                "total_r":    len(doc_recibidos_ids),
                "pid":        str(profile_id) if profile_id else None,
                "regenerar":  regenerar,
            })
            await db.commit()
        except Exception as e:
            print(f"[ATS] ⚠️ Error guardando reporte: {e}")
            await db.rollback()

    return {
        "ok":        True,
        "cached":    False,
        "en_curso": es_mes_actual,
        "total_doc_emitidos":  len(doc_emitidos_ids),
        "total_doc_recibidos": len(doc_recibidos_ids),
        "data": {
            "periodo":   {"desde": str(fi), "hasta": str(ff), "mes": periodo},
            "preguntas": preguntas,
            **desglose,
            "resumen":   resumen,
            "notas": [
                "El ATS incluye todos los comprobantes del período — emitidos y recibidos.",
                "Los documentos físicos (fuente=FISICO) están incluidos con clave sintética.",
                "Verifica el ATS en el portal del SRI antes de enviarlo.",
            ] + (["⚠️ Período en curso — los valores son preliminares."] if es_mes_actual else []),
        }
    }

# =============================================================================
# POST /ats/generar — Generar archivo XML del ATS y subirlo a R2
# =============================================================================
@router.post("/ats/generar", summary="Generar archivo XML del ATS para el SRI")
async def generar_ats_xml(
    periodo:   str          = Query(..., description="Período YYYY-MM"),
    auth_data: dict         = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db),
):
    emisor_id  = auth_data.get("emisor_id")
    profile_id = auth_data.get("profile_id")
    if not emisor_id:
        raise HTTPException(status_code=400, detail="Emisor no vinculado.")
    verificar_permiso(auth_data, "declaraciones")

    try:
        año, mes = int(periodo.split("-")[0]), int(periodo.split("-")[1])
    except Exception:
        raise HTTPException(status_code=400, detail="Formato inválido. Use YYYY-MM.")

    fi = date(año, mes, 1)
    ff = date(año, mes, calendar.monthrange(año, mes)[1])

    # Obtener datos del emisor
    res_emisor = await db.execute(text("""
        SELECT ruc, razon_social FROM emisores WHERE id = :eid
    """), {"eid": emisor_id})
    emisor = res_emisor.fetchone()
    if not emisor:
        raise HTTPException(status_code=404, detail="Emisor no encontrado.")

    # ── Verificar suscripción ──────────────────────────────────────────────
    if not await _verificar_suscripcion(emisor_id, db):
        raise HTTPException(
            status_code=402,
            detail="Se requiere suscripción activa para generar el ATS."
        )

    # ── Compras del período (usa columnas desnormalizadas e items_detalle) ──
    res_compras = await db.execute(text("""
        SELECT
            d.id,
            d.tipo_doc,
            d.cod_doc,
            d.numero_doc,
            d.clave_acceso,
            d.fecha_emision,
            d.importe_total,
            d.ruc_proveedor,
            d.razon_social_proveedor,
            d.fuente,
            d.subtotal_base,
            d.valor_iva_total,
            d.credito_tributario_iva,
            d.items_detalle,
            d.datos
        FROM documentos_recibidos d
        WHERE d.emisor_id     = :eid
          AND d.fecha_emision BETWEEN :fi AND :ff
          AND d.tipo_doc      IN ('FAC', 'LIQ', 'NCR', 'NDB')
        ORDER BY d.fecha_emision, d.numero_doc
    """), {"eid": emisor_id, "fi": fi, "ff": ff})
    compras = res_compras.fetchall()

    # ── Retenciones emitidas ──────────────────────────────────────────────
    res_ret = await db.execute(text("""
        SELECT
            d.id,
            d.numero_doc,
            d.clave_acceso,
            d.fecha_emision,
            d.datos->'infoCompRetencion'->>'identificacionSujetoRetenido' AS id_retenido,
            d.datos->'impuestos' AS impuestos
        FROM documentos_emitidos d
        WHERE d.emisor_id     = :eid
          AND d.estado_sri    = 'AUTORIZADO'
          AND d.fecha_emision BETWEEN :fi AND :ff
          AND d.es_sandbox    = false
          AND d.tipo_doc      = 'RET'
        ORDER BY d.fecha_emision
    """), {"eid": emisor_id, "fi": fi, "ff": ff})
    retenciones = res_ret.fetchall()

    # ── Ventas del período ────────────────────────────────────────────────
    res_ventas = await db.execute(text("""
        SELECT
            d.id,
            d.tipo_doc,
            d.cod_doc,
            d.numero_doc,
            d.clave_acceso,
            d.fecha_emision,
            d.importe_total,
            d.datos->'infoFactura'->>'identificacionComprador'     AS id_comprador,
            d.datos->'infoFactura'->>'tipoIdentificacionComprador' AS tipo_id,
            d.datos->'resumenImpuestos'                            AS resumen_impuestos
        FROM documentos_emitidos d
        WHERE d.emisor_id     = :eid
          AND d.estado_sri    = 'AUTORIZADO'
          AND d.fecha_emision BETWEEN :fi AND :ff
          AND d.es_sandbox    = false
          AND d.tipo_doc      IN ('FAC', 'LIQ', 'NCR', 'NDB')
        ORDER BY d.fecha_emision, d.numero_doc
    """), {"eid": emisor_id, "fi": fi, "ff": ff})
    ventas = res_ventas.fetchall()

    # ── Construir XML ─────────────────────────────────────────────────────
    def fmt2(n): return f"{float(n or 0):.2f}"

    root = Element("iva")

    # Cabecera
    _t(root, "TipoIDInformante", "R")
    _t(root, "IdInformante",     emisor.ruc)
    _t(root, "razonSocial",      emisor.razon_social)
    _t(root, "Anio",             str(año))
    _t(root, "Mes",              str(mes).zfill(2))

    # Total ventas
    total_ventas = sum(float(v.importe_total or 0) for v in ventas)
    _t(root, "totalVentas",     fmt2(total_ventas))
    _t(root, "codigoOperativo", "IVA")

    # ── COMPRAS ───────────────────────────────────────────────────────────
    if compras:
        compras_el = SubElement(root, "compras")
        for c in compras:
            det = SubElement(compras_el, "detalleCompras")

            # Parsear número: 001-001-000000555
            if "-" in (c.numero_doc or ""):
                p = c.numero_doc.split("-")
                estab = p[0] if len(p) > 0 else "001"
                punto = p[1] if len(p) > 1 else "001"
                secuencial = p[2] if len(p) > 2 else "000000001"
            else:
                estab = "001"; punto = "001"; secuencial = "000000001"

            # Autorización = clave acceso o número
            autorizacion = c.clave_acceso or secuencial

            # Usar columnas desnormalizadas
            base_grav = float(c.subtotal_base or 0)
            base_0    = 0.0
            monto_iva = float(c.valor_iva_total or 0)

            # Retenciones en este doc
            ret_bien10  = 0.0; ret_serv20  = 0.0; ret_bien100 = 0.0
            ret_serv50  = 0.0; ret_serv100 = 0.0; ret_serv_gen = 0.0

            _t(det, "codSustento",     "01")  # 01=facturas
            _t(det, "tpIdProv",        "01")  # 01=RUC
            _t(det, "idProv",          c.ruc_proveedor or "9999999999999")
            _t(det, "tipoComprobante", c.cod_doc or "01")
            _t(det, "parteRel",        "NO")
            _t(det, "fechaRegistro",   c.fecha_emision.strftime("%d/%m/%Y"))
            _t(det, "establecimiento", estab)
            _t(det, "puntoEmision",    punto)
            _t(det, "secuencial",      secuencial.lstrip("0") or "1")
            _t(det, "fechaEmision",    c.fecha_emision.strftime("%d/%m/%Y"))
            _t(det, "autorizacion",    autorizacion)
            _t(det, "baseNoGraIva",    fmt2(0))
            _t(det, "baseImponible",   fmt2(base_0))
            _t(det, "baseImpGrav",     fmt2(base_grav))
            _t(det, "baseImpExe",      fmt2(0))
            _t(det, "montoIce",        fmt2(0))
            _t(det, "montoIva",        fmt2(monto_iva))
            _t(det, "valRetBien10",    fmt2(ret_bien10))
            _t(det, "valRetServ20",    fmt2(ret_serv20))
            _t(det, "valorRetBienes",  fmt2(ret_bien100))
            _t(det, "valRetServ50",    fmt2(ret_serv50))
            _t(det, "valorRetServicios", fmt2(ret_serv_gen))
            _t(det, "valRetServ100",   fmt2(ret_serv100))
            _t(det, "valorRetencionNc", fmt2(0))
            _t(det, "totbasesImpReemb", fmt2(0))

            # pagoExterior — siempre local
            pago_ext = SubElement(det, "pagoExterior")
            _t(pago_ext, "pagoLocExt",           "01")  # 01=local
            _t(pago_ext, "paisEfecPago",          "NA")
            _t(pago_ext, "aplicConvDobTrib",      "NA")
            _t(pago_ext, "pagExtSujRetNorLeg",    "NA")

            # air — retenciones de renta por doc cruzando con num_doc_sustento en retenciones
            ret_renta_doc = []
            for r in retenciones:
                imp_list = (r.impuestos or {}).get("impuesto", [])
                if not isinstance(imp_list, list):
                    imp_list = [imp_list] if imp_list else []
                for imp in imp_list:
                    if not isinstance(imp, dict):
                        continue
                    if str(imp.get("codigo", "")) == "1":  # Renta
                        num_sustento = str(imp.get("numDocSustento", "")).replace("-", "")
                        num_compra   = str(c.numero_doc or "").replace("-", "")
                        if num_sustento and num_compra and (num_sustento in num_compra or num_compra in num_sustento):
                            ret_renta_doc.append({
                                "codigo_retencion": str(imp.get("codigoRetencion", "332")),
                                "base_imponible":   float(imp.get("baseImponible", 0) or 0),
                                "porcentaje":       float(imp.get("porcentajeRetener", 0) or 0),
                                "valor_retenido":   float(imp.get("valorRetenido", 0) or 0),
                            })

            if ret_renta_doc:
                air_el = SubElement(det, "air")
                for item in ret_renta_doc:
                    det_air = SubElement(air_el, "detalleAir")
                    _t(det_air, "codRetAir",     item["codigo_retencion"])
                    _t(det_air, "baseImpAir",    fmt2(item["base_imponible"]))
                    _t(det_air, "porcentajeAir", fmt2(item["porcentaje"]))
                    _t(det_air, "valRetAir",     fmt2(item["valor_retenido"]))
            else:
                # Air vacío requerido por el schema
                air_el  = SubElement(det, "air")
                det_air = SubElement(air_el, "detalleAir")
                _t(det_air, "codRetAir",     "332")
                _t(det_air, "baseImpAir",    fmt2(0))
                _t(det_air, "porcentajeAir", fmt2(0))
                _t(det_air, "valRetAir",     fmt2(0))

    # ── VENTAS ────────────────────────────────────────────────────────────
    if ventas:
        ventas_el = SubElement(root, "ventas")
        for v in ventas:
            det = SubElement(ventas_el, "detalleVentas")

            if "-" in (v.numero_doc or ""):
                p = v.numero_doc.split("-")
                estab = p[0]; punto = p[1]; secuencial = p[2]
            else:
                estab = "001"; punto = "001"; secuencial = "000000001"

            impuestos = v.resumen_impuestos or []
            if not isinstance(impuestos, list):
                impuestos = [impuestos] if impuestos else []

            base_grav = sum(float(i.get("baseImponible", 0) or 0) for i in impuestos if float(i.get("tarifa", 0) or 0) > 0)
            base_0    = sum(float(i.get("baseImponible", 0) or 0) for i in impuestos if float(i.get("tarifa", 0) or 0) == 0)
            monto_iva = sum(float(i.get("valor", 0) or 0)         for i in impuestos if float(i.get("tarifa", 0) or 0) > 0)

            _t(det, "tpIdCliente",    v.tipo_id or "07")
            _t(det, "idCliente",      v.id_comprador or "9999999999999")
            _t(det, "parteRel",        "NO")
            _t(det, "tipoComprobante", v.cod_doc or "01")
            _t(det, "tipoEm",          "E")  # E=electrónico
            _t(det, "numeroComprobantes", "1")
            _t(det, "baseNoGraIva",    fmt2(0))
            _t(det, "baseImponible",   fmt2(base_0))
            _t(det, "baseImpGrav",     fmt2(base_grav))
            _t(det, "baseImpExe",      fmt2(0))
            _t(det, "montoIce",        fmt2(0))
            _t(det, "montoIva",        fmt2(monto_iva))
            _t(det, "valorRetIva",     fmt2(0))
            _t(det, "valorRetRenta",   fmt2(0))

    # ── Serializar XML ────────────────────────────────────────────────────
    xml_str = minidom.parseString(
        tostring(root, encoding="unicode")
    ).toprettyxml(indent="  ", encoding=None)

    xml_bytes = xml_str.encode("utf-8")

    # ── Comprimir en ZIP ──────────────────────────────────────────────────
    nombre_xml = f"AT-{str(mes).zfill(2)}{año}.xml"
    nombre_zip = f"AT-{str(mes).zfill(2)}{año}-{emisor.ruc}.zip"

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(nombre_xml, xml_bytes)
    zip_bytes = zip_buffer.getvalue()

    # ── Subir a R2 ────────────────────────────────────────────────────────
    r2_path = f"{emisor.ruc}/ats/{nombre_zip}"
    upload_file(r2_path, zip_bytes, "application/zip")

    # ── Guardar path en reportes_tributarios ──────────────────────────────
    try:
        await db.execute(text("""
            INSERT INTO reportes_tributarios (
                emisor_id, tipo, tipo_periodo, periodo,
                casilleros, preguntas, desglose, resumen,
                doc_emitidos_ids, doc_recibidos_ids,
                total_doc_emitidos, total_doc_recibidos,
                generado_por
            ) VALUES (
                :eid, 'ATS', 'MENSUAL', :periodo,
                '{}', '{}', '{}',
                CAST(:resumen AS jsonb),
                '[]', '[]', :total_e, :total_r, :pid
            )
            ON CONFLICT (emisor_id, tipo, periodo) DO UPDATE SET
                resumen        = CAST(:resumen AS jsonb),
                regenerado_at  = NOW(),
                regenerado_por = :pid
        """), {
            "eid":     emisor_id,
            "periodo": fi,
            "resumen": json.dumps({"xml_path": r2_path, "nombre_zip": nombre_zip}),
            "total_e": len(ventas),
            "total_r": len(compras),
            "pid":     str(profile_id) if profile_id else None,
        })
        await db.commit()
    except Exception as e:
        print(f"[ATS] ⚠️ Error guardando: {e}")
        await db.rollback()

    # Retornar URL de descarga
    url = get_presigned_url(r2_path)
    return {
        "ok":           True,
        "nombre_zip":   nombre_zip,
        "r2_path":      r2_path,
        "download_url": url,
        "total_ventas": len(ventas),
        "total_compras": len(compras),
        "mensaje": f"ATS generado correctamente — {nombre_zip}",
    }

# =============================================================================
# GET /ats/descargar — URL de descarga del ATS
# =============================================================================
@router.get("/ats/descargar", summary="Obtener URL de descarga del ATS")
async def descargar_ats(
    periodo:   str          = Query(...),
    auth_data: dict         = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db),
):
    emisor_id = auth_data.get("emisor_id")
    if not emisor_id:
        raise HTTPException(status_code=400, detail="Emisor no vinculado.")
    verificar_permiso(auth_data, "declaraciones")

    try:
        año, mes = int(periodo.split("-")[0]), int(periodo.split("-")[1])
    except Exception:
        raise HTTPException(status_code=400, detail="Formato inválido.")

    fi = date(año, mes, 1)

    res = await db.execute(text("""
        SELECT resumen FROM reportes_tributarios
        WHERE emisor_id = :eid AND tipo = 'ATS' AND periodo = :periodo
    """), {"eid": emisor_id, "periodo": fi})
    row = res.fetchone()

    if not row or not row.resumen or not row.resumen.get("xml_path"):
        raise HTTPException(
            status_code=404,
            detail="ATS no generado aún. Genera el archivo primero."
        )

    url = get_presigned_url(row.resumen["xml_path"])

    return {
        "ok":           True,
        "download_url": url,
        "nombre_zip":   row.resumen.get("nombre_zip"),
    }




# =============================================================================
# HELPERS
# =============================================================================

def _periodo_actual(tipo: str, hoy: date) -> date:
    """Retorna el primer día del período actual según el tipo de declaración."""
    if tipo == "102":
        # Renta — período anual, año anterior
        return date(hoy.year - 1, 1, 1)
    else:
        # 104 y ATS — mensual, mes anterior
        if hoy.month == 1:
            return date(hoy.year - 1, 12, 1)
        return date(hoy.year, hoy.month - 1, 1)


def _estado(declarado: bool, dias_restantes: int) -> str:
    if declarado:            return "DECLARADO"
    if dias_restantes < 0:   return "VENCIDO"
    if dias_restantes <= 3:  return "URGENTE"
    if dias_restantes <= 7:  return "PROXIMO"
    return "PENDIENTE"

# Helper al final de declaraciones.py (antes de _periodo_actual)
async def _verificar_suscripcion(emisor_id: int, db: AsyncSession) -> bool:
    res = await db.execute(text("""
        SELECT estado FROM subscriptions WHERE emisor_id = :eid
    """), {"eid": emisor_id})
    sub = res.fetchone()
    return sub is not None and sub.estado in ("ACTIVO", "TRIAL")


def _t(parent, tag: str, text: str):
    el = SubElement(parent, tag)
    el.text = text
    return el


def _datos_demo_iva() -> dict:
    return {
        "periodo": {"desde": "2026-08-01", "hasta": "2026-08-31", "mes": "2026-08", "tipo": "MENSUAL"},
        "preguntas": {
            "requiere_informar":        True,
            "credito_tributario_renta": True,
            "comercio_exterior":        False,
            "notas_credito":            False,
            "ha_realizado_ventas":      True,
            "ventas_tarifa_0":          True,
            "ventas_tarifa_nz":         True,
            "ha_realizado_compras":     True,
            "importaciones":            False,
            "ha_realizado_retenciones": False,
            "materiales_construccion":  False,
        },
        "ventas": {
            "desglose": [
                {"tarifa": 15, "bruto": 3240.50, "ncr": 0, "neto": 3240.50, "iva_bruto": 486.08, "iva_neto": 486.08, "num_docs": 18},
                {"tarifa": 0,  "bruto": 890.00,  "ncr": 0, "neto": 890.00,  "iva_bruto": 0,      "iva_neto": 0,      "num_docs": 4 },
            ],
            "casilleros": {
                "401": 3240.50, "411": 3240.50, "421": 486.08,
                "403": 890.00,  "413": 890.00,
                "409": 4130.50, "419": 4130.50, "429": 486.08,
                "111": 22, "113": 0,
            },
        },
        "compras": {
            "desglose": [
                {"tarifa": 15, "con_credito": 1850.00, "sin_credito": 0, "ncr": 0,
                 "neto": 1850.00, "iva_credito": 277.50, "iva_sin_credito": 0, "iva_neto": 277.50},
            ],
            "casilleros": {
                "500": 1850.00, "510": 1850.00, "520": 277.50,
                "502": 0,       "512": 0,       "522": 0,
                "507": 320.00,  "517": 320.00,
                "509": 2170.00, "519": 2170.00, "529": 277.50,
                "115": 14, "119": 0,
            },
        },
        "retenciones_emitidas":  {"desglose": [], "casilleros": {"721": 0, "723": 0, "725": 0, "727": 0, "729": 0, "731": 0, "799": 0, "801": 0}},
        "retenciones_recibidas": {"casilleros": {"609": 0}},
        "resumen": {
            "casilleros": {
                "499": 486.08, "564": 277.50,
                "601": 208.58, "602": 0,
                "609": 0,      "620": 208.58,
                "699": 208.58, "799": 0,
                "801": 0,      "859": 208.58,
            },
            "campos_manuales": [
                {"casillero": "605", "descripcion": "Saldo crédito tributario mes anterior (adquisiciones)"},
                {"casillero": "606", "descripcion": "Saldo crédito tributario mes anterior (retenciones)"},
            ],
        },
        "notas": ["⚠️ Estos son datos de ejemplo — suscríbete para ver tus datos reales."],
    }


def _datos_demo_renta() -> dict:
    return {
        "periodo": {"anio": 2025, "desde": "2025-01-01", "hasta": "2025-12-31"},
        "preguntas": {
            "tiene_ingresos":          True,
            "tiene_gastos_deducibles": True,
            "tiene_retenciones":       True,
            "supera_fraccion_basica":  True,
            "debe_pagar":              True,
            "tiene_saldo_favor":       False,
        },
        "ingresos":        {"brutos": 28500.00, "ncr": 0, "netos": 28500.00},
        "gastos":          {"deducibles": 12300.00},
        "base_imponible":  16200.00,
        "tabla_ir":        {"tramo": {"desde": 15159, "hasta": 19682, "base": 163, "porcentaje": 10}, "tabla_anio": 2025, "nota": "Verificar con resolución SRI vigente"},
        "resumen": {
            "casilleros": {
                "501": 28500.00, "502": 0, "503": 28500.00,
                "601": 12300.00,
                "699": 16200.00, "701": 16200.00,
                "801": 1204.10,
                "841": 890.00,
                "859": 314.10,  "869": 0,
            },
            "campos_manuales": [
                {"casillero": "504", "descripcion": "Otros ingresos (arrendamientos, intereses, etc.)"},
                {"casillero": "602", "descripcion": "Gastos personales (salud, educación, etc.)"},
            ],
            "resultado": {
                "impuesto_causado": 1204.10,
                "retenciones":      890.00,
                "a_pagar":          314.10,
                "saldo_favor":      0,
            }
        },
        "notas": ["⚠️ Estos son datos de ejemplo — suscríbete para ver tus datos reales."],
    }


def _datos_demo_ats() -> dict:
    return {
        "periodo": {"desde": "2026-08-01", "hasta": "2026-08-31", "mes": "2026-08"},
        "preguntas": {
            "tiene_ventas":                True,
            "tiene_compras":               True,
            "tiene_retenciones_emitidas":  False,
            "tiene_retenciones_recibidas": False,
            "obligado_contabilidad":       True,
        },
        "ventas": {
            "detalle": [
                {"tipo_doc": "FAC", "cod_doc": "01", "numero_doc": "001-001-000000022",
                 "fecha_emision": "2026-08-15", "tipo_id": "04", "identificacion": "1307715712001",
                 "razon_social": "EMPRESA EJEMPLO S.A.", "base_iva_nz": 3240.50, "base_iva_0": 890.00, "iva": 486.08},
            ],
            "retenciones": [],
            "totales": {"num_docs": 22, "base_iva_diferente_0": 3240.50, "base_iva_0": 890.00, "iva": 486.08, "total": 4616.58},
        },
        "compras": {
            "detalle": [
                {"tipo_doc": "FAC", "cod_doc": "01", "numero_doc": "001-001-000000100",
                 "fecha_emision": "2026-08-05", "ruc_proveedor": "1391936379001",
                 "razon_proveedor": "PROVEEDOR EJEMPLO CIA. LTDA.", "base_iva_nz": 1850.00,
                 "iva_credito": 277.50, "total": 2127.50, "fuente": "🔵 XML"},
            ],
            "retenciones": [],
            "totales": {"num_docs": 14, "base_iva_diferente_0": 1850.00, "base_iva_0": 320.00, "iva_con_credito": 277.50, "iva_sin_credito": 0, "total": 2447.50},
        },
        "resumen": {
            "emisor": {"ruc": "9999999999001", "razon_social": "EMPRESA DEMO S.A.", "obligado_contabilidad": "SI"},
            "periodo": "2026-08-01",
            "totales_ventas":  {"num_docs": 22, "total": 4616.58},
            "totales_compras": {"num_docs": 14, "total": 2447.50},
            "total_ret_emitidas":  0,
            "total_ret_recibidas": 0,
        },
        "notas": ["⚠️ Estos son datos de ejemplo — suscríbete para ver tus datos reales."],
    }