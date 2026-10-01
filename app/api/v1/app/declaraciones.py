# app/api/v1/app/declaraciones.py
#
# Endpoints de declaraciones tributarias. La lógica vive en app/services/declaraciones/.
#
# El sistema NO declara por el usuario: prepara los valores y registra si declaró.
# La declaración real se hace en SRI en Línea.
#
# Tipos: 104 (IVA) | 102 (Renta) | ATS

import json
from datetime import date, timedelta
from typing import Optional
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Body, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import verify_firebase_token
from app.core.permisos import verificar_permiso
from app.core.cache import cache_get, cache_set, invalidate_emisor, TTL, CK
from app.services.audit_service import audit_log
from app.services.storage_service import upload_file, get_presigned_url

from app.services.declaraciones import periodos as per
from app.services.declaraciones import registro, snapshots, demo
from app.services.declaraciones.obligaciones import cargar_obligaciones, Obligaciones
from app.services.declaraciones.iva_104 import (
    calcular_iva_104, resultado_periodo, resumen_iva, CASILLEROS_MANUALES_PERMITIDOS,
)
from app.services.declaraciones.renta_102 import calcular_renta_102
from app.services.declaraciones.ats import calcular_ats, generar_xml_ats
from app.services.credito_tributario_service import registrar_lote_declaracion

router = APIRouter()


# =============================================================================
# HELPERS
# =============================================================================
def _emisor(auth_data: dict) -> int:
    emisor_id = auth_data.get("emisor_id")
    if not emisor_id:
        raise HTTPException(status_code=400, detail="Emisor no vinculado.")
    return emisor_id


def _permiso(auth_data: dict) -> None:
    """Un solo permiso para todo el módulo: basta con 'declaraciones' o 'reportes'."""
    try:
        verificar_permiso(auth_data, "declaraciones")
    except HTTPException:
        verificar_permiso(auth_data, "reportes")


def _tipo_valido(tipo: str) -> str:
    if tipo not in per.TIPOS:
        raise HTTPException(status_code=400, detail=f"Tipo inválido. Válidos: {', '.join(per.TIPOS)}")
    return tipo


async def _obligaciones(db: AsyncSession, emisor_id: int) -> Obligaciones:
    obl = await cargar_obligaciones(db, emisor_id)
    if not obl:
        raise HTTPException(status_code=404, detail="Emisor no encontrado.")
    return obl


async def _verificar_suscripcion(emisor_id: int, db: AsyncSession) -> bool:
    res = await db.execute(text("SELECT estado FROM subscriptions WHERE emisor_id = :eid"), {"eid": emisor_id})
    sub = res.fetchone()
    return sub is not None and sub.estado in ("ACTIVO", "TRIAL")


async def _invalidar_dashboard(emisor_id: int) -> None:
    """El widget del dashboard vive en caché: al declarar, se limpia para que cambie al instante."""
    try:
        from app.core.cache import get_redis
        redis = await get_redis()
        async for key in redis.scan_iter(f"dashboard:{emisor_id}*"):
            await redis.delete(key)
    except Exception as e:
        print(f"[Cache] ⚠️ No invalidado: {e}")


def _parse_periodo(tipo: str, tipo_periodo: str, key: str) -> per.Periodo:
    try:
        return per.parse_periodo(tipo, tipo_periodo, key)
    except Exception:
        raise HTTPException(status_code=400, detail="Formato de periodo inválido. Use YYYY-MM o YYYY.")


# =============================================================================
# GET /obligaciones — qué declara esta empresa
# =============================================================================
@router.get("/obligaciones", summary="Obligaciones tributarias de la empresa")
async def obtener_obligaciones(
    auth_data: dict         = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db),
):
    emisor_id = _emisor(auth_data)
    _permiso(auth_data)
    obl = await _obligaciones(db, emisor_id)
    return {"ok": True, "data": obl.to_dict()}


# =============================================================================
# GET /actual — el periodo que toca declarar ahora
# =============================================================================
@router.get("/actual", summary="Declaración que toca declarar ahora")
async def obtener_declaracion_actual(
    tipo:      str          = Query("104", description="104 | 102 | ATS"),
    auth_data: dict          = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db),
):
    emisor_id = _emisor(auth_data)
    _permiso(auth_data)
    _tipo_valido(tipo)

    obl    = await _obligaciones(db, emisor_id)
    motivo = obl.motivo_no_aplica(tipo)
    if motivo:
        return {"ok": True, "aplica": False, "motivo": motivo}

    hoy = per.hoy_ec()
    p   = per.periodo_a_declarar(tipo, obl.tipo_periodo(tipo), hoy)
    if not p.existe_para(obl.inicio, hoy):
        return {"ok": True, "aplica": False, "motivo": "Todavía no tienes periodos cerrados por declarar."}

    await registro.asegurar_filas(db, obl, [p])

    if tipo == "104":
        calc    = await resultado_periodo(db, obl, p)
        totales = resumen_iva(calc)
        await db.execute(text("""
            UPDATE declaraciones_sri SET totales = CAST(:totales AS jsonb)
            WHERE emisor_id = :eid AND tipo = :tipo AND periodo = :periodo
        """), {"totales": json.dumps(totales), "eid": emisor_id, "tipo": tipo, "periodo": p.inicio})

    await db.commit()

    filas = await registro.leer_filas(db, emisor_id, tipo, [p])
    item  = registro.serializar(p, filas[p.inicio], hoy)

    return {
        "ok":     True,
        "aplica": True,
        "data": {
            **item,
            "periodo":     p.nombre,
            "periodo_iso": p.inicio.isoformat(),
        },
    }


# =============================================================================
# GET /historial — todos los periodos del año (por calendario)
# =============================================================================
@router.get("/historial", summary="Periodos del año con su estado")
async def historial_declaraciones(
    tipo:      str           = Query("104"),
    anio:      Optional[int] = Query(None, description="Año a consultar"),
    auth_data: dict          = Depends(verify_firebase_token),
    db:        AsyncSession  = Depends(get_db),
):
    emisor_id = _emisor(auth_data)
    _permiso(auth_data)
    _tipo_valido(tipo)

    hoy  = per.hoy_ec()
    anio = anio or hoy.year
    obl  = await _obligaciones(db, emisor_id)

    motivo = obl.motivo_no_aplica(tipo)
    if motivo:
        return {"ok": True, "anio": anio, "tipo": tipo, "aplica": False, "motivo": motivo, "data": []}

    periodos = per.periodos_del_anio(tipo, obl.tipo_periodo(tipo), anio, obl.inicio, hoy)
    await registro.asegurar_filas(db, obl, periodos)
    await db.commit()

    filas = await registro.leer_filas(db, emisor_id, tipo, periodos)
    return {
        "ok":     True,
        "anio":   anio,
        "tipo":   tipo,
        "aplica": True,
        "data":   [registro.serializar(p, filas[p.inicio], hoy) for p in periodos if p.inicio in filas],
    }


# =============================================================================
# GET /periodo/{anio}/{mes} — un periodo específico
# =============================================================================
@router.get("/periodo/{anio}/{mes}", summary="Declaración de un periodo específico")
async def declaracion_periodo(
    anio:      int,
    mes:       int,
    tipo:      str          = Query("104"),
    auth_data: dict         = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db),
):
    emisor_id = _emisor(auth_data)
    _permiso(auth_data)
    _tipo_valido(tipo)
    if not (1 <= mes <= 12):
        raise HTTPException(status_code=400, detail="Mes inválido.")

    obl = await _obligaciones(db, emisor_id)
    hoy = per.hoy_ec()
    p   = _parse_periodo(tipo, obl.tipo_periodo(tipo), f"{anio}-{mes:02d}")

    if obl.motivo_no_aplica(tipo) or not p.existe_para(obl.inicio, hoy):
        raise HTTPException(status_code=404, detail="Declaración no encontrada para ese periodo.")

    await registro.asegurar_filas(db, obl, [p])
    await db.commit()
    filas = await registro.leer_filas(db, emisor_id, tipo, [p])
    return {"ok": True, "data": registro.serializar(p, filas[p.inicio], hoy)}


# =============================================================================
# GET /totales/{anio}/{mes} — totales del mes (mismo cálculo que el 104)
# =============================================================================
@router.get("/totales/{anio}/{mes}", summary="Totales fiscales de un mes")
async def calcular_totales_periodo(
    anio:      int,
    mes:       int,
    auth_data: dict         = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db),
):
    emisor_id = _emisor(auth_data)
    _permiso(auth_data)
    if not (1 <= mes <= 12):
        raise HTTPException(status_code=400, detail="Mes inválido.")

    p    = per.crear_periodo("104", "MENSUAL", date(anio, mes, 1))
    calc = await calcular_iva_104(db, emisor_id, p.inicio, p.fin)
    return {
        "ok":      True,
        "periodo": f"{p.inicio.isoformat()} al {p.fin.isoformat()}",
        "data":    resumen_iva(calc),
    }


# =============================================================================
# GET /reportes — reportes guardados
# =============================================================================
@router.get("/reportes", summary="Reportes tributarios guardados")
async def listar_reportes(
    tipo:      str          = Query("IVA"),
    anio:      int          = Query(...),
    auth_data: dict         = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db),
):
    emisor_id = _emisor(auth_data)
    _permiso(auth_data)
    return {"ok": True, "data": await snapshots.listar(db, emisor_id, tipo, anio)}


# =============================================================================
# POST /declarar — marcar un periodo como declarado
# =============================================================================
@router.post("/declarar", summary="Marcar un periodo como declarado")
async def marcar_declarado(
    request:   Request,
    tipo:      str           = Query("104"),
    periodo:   Optional[str] = Query(None, description="YYYY-MM o YYYY. Si se omite, el que toca declarar ahora."),
    auth_data: dict          = Depends(verify_firebase_token),
    db:        AsyncSession  = Depends(get_db),
):
    emisor_id  = _emisor(auth_data)
    profile_id = auth_data.get("profile_id")
    _permiso(auth_data)
    _tipo_valido(tipo)

    obl    = await _obligaciones(db, emisor_id)
    motivo = obl.motivo_no_aplica(tipo)
    if motivo:
        raise HTTPException(status_code=400, detail=motivo)

    hoy = per.hoy_ec()
    tp  = obl.tipo_periodo(tipo)
    p   = _parse_periodo(tipo, tp, periodo) if periodo else per.periodo_a_declarar(tipo, tp, hoy)

    if p.en_curso(hoy):
        raise HTTPException(
            status_code=400,
            detail=f"{p.nombre.capitalize()} todavía no termina. Podrás marcarlo como declarado "
                   f"desde el {per.fecha_larga(p.fin + timedelta(days=1))}.",
        )
    if not p.existe_para(obl.inicio, hoy):
        raise HTTPException(status_code=400, detail="Ese periodo es anterior a tu inicio en producción.")

    await registro.asegurar_filas(db, obl, [p])
    if not await registro.marcar_declarado(db, emisor_id, p, profile_id):
        raise HTTPException(status_code=404, detail="Declaración no encontrada.")

    await audit_log(db, auth_data, "UPDATE", "declaracion", None,
                    {"accion": "declarado", "tipo": tipo, "periodo": p.key}, request)
    await db.commit()

    if tipo == "104":
        calc = await resultado_periodo(db, obl, p, forzar=True)
        await snapshots.guardar(
            db, emisor_id=emisor_id, tipo="IVA", tipo_periodo=tp, periodo_db=p.inicio,
            casilleros=calc["casilleros"], preguntas=calc["preguntas"],
            desglose=calc["desglose"], resumen=calc["resumen"],
            doc_emitidos_ids=calc.get("doc_emitidos_ids") or set(), 
            doc_recibidos_ids=calc.get("doc_recibidos_ids") or set(),
            profile_id=profile_id, regenerar=False,
        )

        c602 = Decimal(str(calc["casilleros"]["resumen"].get("602", 0.0)))
        if c602 > 0:
            await registrar_lote_declaracion(db, emisor_id, p.inicio, c602)
            await db.commit()

    await invalidate_emisor(emisor_id)
    await _invalidar_dashboard(emisor_id)

    return {
        "ok":      True,
        "periodo": p.key,
        "mensaje": f"{p.nombre.capitalize()} marcado como declarado. ¡Hasta el próximo periodo!",
    }


# =============================================================================
# GET /iva — formulario 104
# =============================================================================
@router.get("/iva", summary="Casilleros formulario 104 — IVA")
async def casilleros_iva(
    periodo:      str           = Query(..., description="Periodo YYYY-MM, ej: 2026-08"),
    tipo_periodo: Optional[str] = Query(None),
    regenerar:    bool          = Query(False, description="Recalcular aunque el periodo esté declarado"),
    auth_data:    dict          = Depends(verify_firebase_token),
    db:           AsyncSession  = Depends(get_db),
):
    emisor_id  = _emisor(auth_data)
    profile_id = auth_data.get("profile_id")
    _permiso(auth_data)

    if not await _verificar_suscripcion(emisor_id, db):
        return {"ok": True, "demo": True, "cached": False, "en_curso": False,
                "total_doc_emitidos": 0, "total_doc_recibidos": 0,
                "data": demo.datos_demo_iva()}

    obl = await _obligaciones(db, emisor_id)
    tp  = obl.tipo_periodo("104")
    p   = _parse_periodo("104", tp, periodo)
    hoy = per.hoy_ec()
    en_curso = p.en_curso(hoy)

    cache_key = CK.fmt(CK.DECLARACION_IVA, eid=emisor_id, periodo=periodo)
    if not regenerar:
        cached = await cache_get(cache_key)
        if cached is not None:
            return cached

    calc = await resultado_periodo(db, obl, p, forzar=regenerar)

    doc_emitidos = calc.get("doc_emitidos_ids") or set()
    doc_recibidos = calc.get("doc_recibidos_ids") or set()

    if not en_curso and not calc.get("congelado"):
        await snapshots.guardar(
            db, emisor_id=emisor_id, tipo="IVA", tipo_periodo=tp, periodo_db=p.inicio,
            casilleros=calc["casilleros"], preguntas=calc["preguntas"],
            desglose=calc["desglose"], resumen=calc["resumen"],
            doc_emitidos_ids=doc_emitidos, doc_recibidos_ids=doc_recibidos,
            profile_id=profile_id, regenerar=regenerar,
        )

    saldos = (calc["resumen"] or {}).get("saldos") or {}
    notas  = []
    if calc.get("congelado"):
        notas.append("Periodo declarado: estos son los valores al momento de declarar. "
                     "Usa «Regenerar» solo si vas a presentar una declaración sustitutiva.")
    if saldos.get("origen") == "SIN_HISTORIAL":
        notas.append("Es tu primer periodo en Kipu: ingresa los saldos 605 y 606 de tu última "
                     "declaración para que el cálculo sea exacto.")
    elif saldos.get("origen") == "KIPU":
        notas.append(f"Los saldos 605 y 606 vienen de tu declaración de {saldos.get('periodo_anterior')}.")
    if calc["casilleros"]["ventas"].get("419", 0) == 0:
        notas.append("Sin ventas en el periodo: el crédito tributario se acumula completo (factor 1).")
    notas.append("Activos fijos e importaciones requieren clasificación manual.")
    if en_curso:
        notas.append("⚠️ Periodo en curso — los valores pueden cambiar.")

    response_payload = {
        "ok":            True,
        "cached":        bool(calc.get("congelado")),
        "en_curso":      en_curso,
        "generado_at":   calc.get("generado_at"),
        "regenerado_at": calc.get("regenerado_at"),
        "total_doc_emitidos":  calc.get("total_doc_emitidos", len(doc_emitidos)),
        "total_doc_recibidos": calc.get("total_doc_recibidos", len(doc_recibidos)),
        "campos_manuales_valores": await snapshots.leer_campos_manuales(db, emisor_id, p.inicio),
        "data": {
            "periodo":   {"desde": p.inicio.isoformat(), "hasta": p.fin.isoformat(), "mes": periodo, "tipo": tp},
            "preguntas": calc["preguntas"],
            **calc["desglose"],
            "resumen":   calc["resumen"],
            "notas":     notas,
        },
    }

    await cache_set(cache_key, response_payload, ttl=TTL.DECLARACION_IVA)

    return response_payload


# =============================================================================
# PATCH /iva/campos-manuales — casilleros manuales del 104
# =============================================================================
@router.patch("/iva/campos-manuales", summary="Guardar casilleros manuales del formulario 104")
async def guardar_campos_manuales_iva(
    request:   Request,
    periodo:   str          = Query(..., description="Periodo YYYY-MM, ej: 2026-08"),
    auth_data: dict         = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db),
    body:      dict         = Body(..., example={"605": 150.00, "606": 0.00, "625": 0.00}),
):
    emisor_id  = _emisor(auth_data)
    profile_id = auth_data.get("profile_id")
    _permiso(auth_data)

    obl = await _obligaciones(db, emisor_id)
    tp  = obl.tipo_periodo("104")
    p   = _parse_periodo("104", tp, periodo)

    valores = {}
    for cas, val in body.items():
        if cas not in CASILLEROS_MANUALES_PERMITIDOS:
            raise HTTPException(status_code=400, detail=f"Casillero {cas} no permitido.")
        try:
            valores[cas] = round(float(val), 2)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail=f"Valor inválido para casillero {cas}.")

    await snapshots.guardar_campos_manuales(
        db, emisor_id=emisor_id, periodo_db=p.inicio, tipo_periodo=tp,
        valores=valores, profile_id=profile_id,
    )
    await audit_log(db, auth_data, "UPDATE", "declaracion", None,
                    {"periodo": periodo, "accion": "campos_manuales", "casilleros": valores},
                    request)
    await db.commit()
    await invalidate_emisor(emisor_id)
    await _invalidar_dashboard(emisor_id)

    return {"ok": True, "periodo": periodo, "valores": valores, "mensaje": "Valores guardados correctamente."}


# =============================================================================
# GET /renta — Impuesto a la Renta anual (Consolidado)
# =============================================================================
@router.get("/renta", summary="Impuesto a la Renta anual")
async def casilleros_renta(
    anio:      int          = Query(..., description="Año a declarar, ej: 2025"),
    regenerar: bool         = Query(False, description="Forzar recálculo aunque esté guardado"),
    auth_data: dict         = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db),
):
    emisor_id  = _emisor(auth_data)
    profile_id = auth_data.get("profile_id")
    _permiso(auth_data)

    hoy = per.hoy_ec()
    if anio < 2020 or anio > hoy.year:
        raise HTTPException(status_code=400, detail="Año inválido.")

    if not await _verificar_suscripcion(emisor_id, db):
        return {"ok": True, "demo": True, "cached": False, "en_curso": False,
                "total_doc_emitidos": 0, "total_doc_recibidos": 0,
                "data": demo.datos_demo_renta()}

    p        = per.crear_periodo("102", "ANUAL", date(anio, 1, 1))
    en_curso = p.en_curso(hoy)
    info_periodo = {"anio": anio, "desde": p.inicio.isoformat(), "hasta": p.fin.isoformat()}

    # 1. Intentar leer de Redis (si no viene ?regenerar=true)
    cache_key = f"declaracion:renta:{emisor_id}:{anio}"
    if not regenerar:
        cached_redis = await cache_get(cache_key)
        if cached_redis is not None:
            return cached_redis

    # 2. Intentar responder desde snapshot congelado si no está en curso
    if not en_curso and not regenerar:
        cached = await snapshots.leer(db, emisor_id, "RENTA", p.inicio)
        if cached:
            response_payload = {
                "ok":            True,
                "cached":        True,
                "generado_at":   cached.generado_at.isoformat() if cached.generado_at else None,
                "regenerado_at": cached.regenerado_at.isoformat() if cached.regenerado_at else None,
                "total_doc_emitidos":  cached.total_doc_emitidos,
                "total_doc_recibidos": cached.total_doc_recibidos,
                "data": {
                    "periodo":   info_periodo,
                    "preguntas": cached.preguntas,
                    **cached.desglose,
                    "resumen":   cached.resumen,
                    "notas": ["Reporte generado previamente. Usa ?regenerar=true para recalcular."],
                },
            }
            await cache_set(cache_key, response_payload, ttl=300)
            return response_payload

    # 3. Recalcular consolidado anual
    calc = await calcular_renta_102(db, emisor_id, anio)

    doc_emitidos = calc.get("doc_emitidos_ids") or set()
    doc_recibidos = calc.get("doc_recibidos_ids") or set()

    if not en_curso:
        await snapshots.guardar(
            db, emisor_id=emisor_id, tipo="RENTA", tipo_periodo="ANUAL", periodo_db=p.inicio,
            casilleros=calc.get("casilleros", {}), preguntas=calc.get("preguntas", {}),
            desglose=calc.get("desglose", {}), resumen=calc.get("resumen", {}),
            doc_emitidos_ids=doc_emitidos, doc_recibidos_ids=doc_recibidos,
            profile_id=profile_id, regenerar=regenerar,
        )

    response_payload = {
        "ok":        True,
        "cached":    False,
        "en_curso":  en_curso,
        "total_doc_emitidos":  calc.get("total_doc_emitidos", len(doc_emitidos)),
        "total_doc_recibidos": calc.get("total_doc_recibidos", len(doc_recibidos)),
        "data": {
            "periodo":   info_periodo,
            "preguntas": calc.get("preguntas", {}),
            **calc.get("desglose", {}),
            "resumen":   calc.get("resumen", {}),
            "notas": [
                "Consolidado anual de facturación electrónica registrada en Kipu.",
                "Los ingresos por relación de dependencia, arrendamientos u otros deben agregarse en el SRI.",
                "Los gastos personales deben ingresarse manualmente en el portal del SRI.",
            ] + (["⚠️ Año en curso — los valores son preliminares."] if en_curso else []),
        },
    }

    await cache_set(cache_key, response_payload, ttl=300)

    return response_payload


# =============================================================================
# GET /ats — Anexo Transaccional Simplificado
# =============================================================================
async def _emisor_ats(db: AsyncSession, emisor_id: int):
    res = await db.execute(text("""
        SELECT ruc, razon_social, obligado_contabilidad, tipo_emisor
        FROM emisores WHERE id = :eid
    """), {"eid": emisor_id})
    emisor = res.fetchone()
    if not emisor:
        raise HTTPException(status_code=404, detail="Emisor no encontrado.")
    return emisor


@router.get("/ats", summary="Anexo Transaccional Simplificado — ATS mensual")
async def casilleros_ats(
    periodo:   str          = Query(..., description="Periodo YYYY-MM, ej: 2026-08"),
    regenerar: bool         = Query(False, description="Forzar recálculo aunque esté guardado"),
    auth_data: dict         = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db),
):
    emisor_id  = _emisor(auth_data)
    profile_id = auth_data.get("profile_id")
    _permiso(auth_data)

    p        = _parse_periodo("ATS", "MENSUAL", periodo)
    hoy      = per.hoy_ec()
    en_curso = p.en_curso(hoy)
    emisor   = await _emisor_ats(db, emisor_id)
    obl      = await _obligaciones(db, emisor_id)

    demo_base = {"ok": True, "demo": True, "cached": False, "en_curso": False,
                 "total_doc_emitidos": 0, "total_doc_recibidos": 0, "data": demo.datos_demo_ats()}
    if not await _verificar_suscripcion(emisor_id, db):
        return {**demo_base, "motivo": "sin_suscripcion"}
    if not obl.ats:
        return {**demo_base, "motivo": "no_obligado"}

    info_periodo = {"desde": p.inicio.isoformat(), "hasta": p.fin.isoformat(), "mes": periodo}

    if not en_curso and not regenerar:
        cached = await snapshots.leer(db, emisor_id, "ATS", p.inicio)
        if cached:
            return {
                "ok":            True,
                "cached":        True,
                "generado_at":   cached.generado_at.isoformat() if cached.generado_at else None,
                "regenerado_at": cached.regenerado_at.isoformat() if cached.regenerado_at else None,
                "total_doc_emitidos":  cached.total_doc_emitidos,
                "total_doc_recibidos": cached.total_doc_recibidos,
                "data": {
                    "periodo": info_periodo,
                    **cached.desglose,
                    "resumen": cached.resumen,
                    "notas":   ["Reporte generado previamente. Usa ?regenerar=true para recalcular."],
                },
            }

    calc = await calcular_ats(db, emisor, emisor_id, p.inicio, p.fin)

    doc_emitidos = calc.get("doc_emitidos_ids") or set()
    doc_recibidos = calc.get("doc_recibidos_ids") or set()

    if not en_curso:
        await snapshots.guardar(
            db, emisor_id=emisor_id, tipo="ATS", tipo_periodo="MENSUAL", periodo_db=p.inicio,
            casilleros={}, preguntas=calc.get("preguntas", {}),
            desglose=calc.get("desglose", {}), resumen=calc.get("resumen", {}),
            doc_emitidos_ids=doc_emitidos, doc_recibidos_ids=doc_recibidos,
            profile_id=profile_id, regenerar=regenerar,
        )

    return {
        "ok":        True,
        "cached":    False,
        "en_curso":  en_curso,
        "total_doc_emitidos":  calc.get("total_doc_emitidos", len(doc_emitidos)),
        "total_doc_recibidos": calc.get("total_doc_recibidos", len(doc_recibidos)),
        "data": {
            "periodo":   info_periodo,
            "preguntas": calc.get("preguntas", {}),
            **calc.get("desglose", {}),
            "resumen":   calc.get("resumen", {}),
            "notas": [
                "El ATS incluye todos los comprobantes del periodo — emitidos y recibidos.",
                "Los documentos físicos (fuente=FISICO) están incluidos con clave sintética.",
                "Verifica el ATS en el portal del SRI antes de enviarlo.",
            ] + (["⚠️ Periodo en curso — los valores son preliminares."] if en_curso else []),
        },
    }


# =============================================================================
# POST /ats/generar — XML del ATS subido a R2
# =============================================================================
@router.post("/ats/generar", summary="Generar archivo XML del ATS para el SRI")
async def generar_ats(
    periodo:   str          = Query(..., description="Periodo YYYY-MM"),
    auth_data: dict         = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db),
):
    emisor_id  = _emisor(auth_data)
    profile_id = auth_data.get("profile_id")
    _permiso(auth_data)

    p      = _parse_periodo("ATS", "MENSUAL", periodo)
    emisor = await _emisor_ats(db, emisor_id)
    obl    = await _obligaciones(db, emisor_id)

    if not await _verificar_suscripcion(emisor_id, db):
        raise HTTPException(status_code=402, detail="Se requiere suscripción activa para generar el ATS.")
    if not obl.ats:
        raise HTTPException(status_code=403, detail="El ATS aplica solo a obligados a llevar contabilidad y sociedades.")

    archivo = await generar_xml_ats(db, emisor, emisor_id, p.inicio.year, p.inicio.month, p.inicio, p.fin)

    r2_path = f"{emisor.ruc}/ats/{archivo['nombre_zip']}"
    upload_file(r2_path, archivo["zip_bytes"], "application/zip")

    await snapshots.guardar_archivo_ats(
        db, emisor_id=emisor_id, periodo_db=p.inicio,
        xml_path=r2_path, nombre_zip=archivo["nombre_zip"],
        total_e=archivo["total_ventas"], total_r=archivo["total_compras"],
        profile_id=profile_id,
    )

    return {
        "ok":            True,
        "nombre_zip":    archivo["nombre_zip"],
        "r2_path":       r2_path,
        "download_url":  get_presigned_url(r2_path),
        "total_ventas":  archivo["total_ventas"],
        "total_compras": archivo["total_compras"],
        "mensaje":       f"ATS generado correctamente — {archivo['nombre_zip']}",
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
    emisor_id = _emisor(auth_data)
    _permiso(auth_data)

    if not await _verificar_suscripcion(emisor_id, db):
        raise HTTPException(status_code=402, detail="Se requiere suscripción activa.")
    obl = await _obligaciones(db, emisor_id)
    if not obl.ats:
        raise HTTPException(status_code=403, detail="El ATS aplica solo a obligados a llevar contabilidad y sociedades.")

    p   = _parse_periodo("ATS", "MENSUAL", periodo)
    res = await db.execute(text("""
        SELECT resumen FROM reportes_tributarios
        WHERE emisor_id = :eid AND tipo = 'ATS' AND periodo = :periodo
    """), {"eid": emisor_id, "periodo": p.inicio})
    row = res.fetchone()
    if not row or not row.resumen or not row.resumen.get("xml_path"):
        raise HTTPException(status_code=404, detail="ATS no generado aún. Genera el archivo primero.")

    return {
        "ok":           True,
        "download_url": get_presigned_url(row.resumen["xml_path"]),
        "nombre_zip":   row.resumen.get("nombre_zip"),
    }