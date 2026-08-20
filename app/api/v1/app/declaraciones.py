# app/api/v1/app/declaraciones.py
#
# Endpoints para gestión de declaraciones tributarias.
# Tipos: 104 (IVA mensual) | 102 (Renta anual) | ATS (Anexo Transaccional)
#
# El sistema NO declara por el usuario — prepara los valores y marca si declaró.
# La declaración real la hace el usuario en el SRI en Línea.
import json
from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.database import get_db
from app.core.security import verify_firebase_token
from app.workers.declaraciones_worker import calcular_vencimiento

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
    """
    Calcula en tiempo real los totales del período cruzando
    documentos_emitidos y documentos_recibidos.
    Útil para preparar la declaración antes de hacerla.
    """
    emisor_id = auth_data.get("emisor_id")
    if not emisor_id:
        raise HTTPException(status_code=400, detail="Emisor no vinculado.")

    if not (1 <= mes <= 12):
        raise HTTPException(status_code=400, detail="Mes inválido.")

    fi = date(anio, mes, 1)
    if mes == 12:
        ff = date(anio + 1, 1, 1)
    else:
        ff = date(anio, mes + 1, 1)

    # Totales de ventas (documentos emitidos FAC y LIQ autorizados)
    res_ventas = await db.execute(text("""
        SELECT
            COALESCE(SUM(importe_total), 0) AS total_ventas,
            COALESCE(SUM(
                CASE WHEN (datos->'infoFactura'->>'totalSinImpuestos') IS NOT NULL
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
        WHERE emisor_id = :eid
          AND tipo_doc IN ('FAC', 'LIQ')
          AND estado_sri = 'AUTORIZADO'
          AND fecha_emision >= :fi
          AND fecha_emision < :ff
    """), {"eid": emisor_id, "fi": fi, "ff": ff})
    ventas = res_ventas.fetchone()

    # Totales de compras (documentos recibidos)
    res_compras = await db.execute(text("""
        SELECT
            COALESCE(SUM(importe_total), 0)                           AS total_compras,
            COALESCE(SUM(CASE WHEN deducible_renta THEN importe_total ELSE 0 END), 0) AS total_deducible,
            COALESCE(SUM(
                CASE WHEN credito_tributario_iva THEN
                    COALESCE((impuestos_detalle->0->>'valor')::numeric, 0)
                ELSE 0 END
            ), 0) AS credito_tributario
        FROM documentos_recibidos
        WHERE emisor_id = :eid
          AND tipo_doc IN ('FAC', 'LIQ')
          AND fecha_emision >= :fi
          AND fecha_emision < :ff
    """), {"eid": emisor_id, "fi": fi, "ff": ff})
    compras = res_compras.fetchone()

    # Retenciones recibidas (RET que nos emitieron a nosotros)
    res_ret = await db.execute(text("""
        SELECT COALESCE(SUM(
            COALESCE((impuestos_detalle->0->>'valor')::numeric, 0)
        ), 0) AS total_retenciones
        FROM documentos_recibidos
        WHERE emisor_id = :eid
          AND tipo_doc = 'RET'
          AND fecha_emision >= :fi
          AND fecha_emision < :ff
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
        "ok":     True,
        "periodo": f"{str(fi)} al {str(ff - timedelta(days=1))}",
        "data":   totales,
    }


# =============================================================================
# POST /declarar — marcar período como declarado
# =============================================================================

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