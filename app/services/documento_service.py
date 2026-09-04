# app/services/documento_service.py
#
# Core unificado de emisión de comprobantes electrónicos.
# Reemplaza factura_service.py y nc_service.py.
#
# Tipos soportados:
#   FAC (01) — Factura
#   LIQ (03) — Liquidación de compra
#   NCR (04) — Nota de crédito
#   NDB (05) — Nota de débito
#   RET (07) — Retención
#
# Flujo:
#   Bloque 0 — Verificar acceso (suscripción o créditos API)
#   Bloque 1 — Resolver cliente / documento origen
#   Bloque 2 — Calcular totales y reservar secuencial
#   Bloque 3 — Construir XML según tipo
#   Bloque 4 — Firmar XML
#   Bloque 5 — Persistir, subir a R2 (solo Prod), encolar (solo Prod)

import json
import pytz
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from app.utils.calculadora import calcular_totales_e_impuestos
from app.utils.crypto import generar_clave_acceso
from app.utils.sri_core import (
    resolver_cliente,
    completar_items_catalogo,
    resolver_pagos,
    construir_campos_adicionales,
    firmar_xml,
)
from app.services.storage_service import upload_file
from app.core.cache import get_redis

TZ_EC = pytz.timezone("America/Guayaquil")

TIPO_DOC_MAP = {
    "FAC": {"cod_doc": "01", "xml_root": "factura",              "xml_version": "1.1.0"},
    "LIQ": {"cod_doc": "03", "xml_root": "liquidacionCompra",    "xml_version": "1.1.0"},
    "NCR": {"cod_doc": "04", "xml_root": "notaCredito",          "xml_version": "1.1.0"},
    "NDB": {"cod_doc": "05", "xml_root": "notaDebito",           "xml_version": "1.0.0"},
    "RET": {"cod_doc": "07", "xml_root": "comprobanteRetencion", "xml_version": "1.0.0"},
}

MOTIVOS_NCR_VALIDOS = [
    "DEVOLUCION DE BIEN",
    "ANULACION DE COMPROBANTE",
    "REBAJA DE PRECIO",
    "DESCUENTO COMERCIAL",
    "OTROS",
]

# =============================================================================
# FUNCIÓN PRINCIPAL
# =============================================================================
async def emitir_documento_core(
    tipo_doc:   str,
    data:       dict,
    emisor_id:  int,
    db:         AsyncSession,
    api_key_id: int  = None,
    es_sandbox: bool = False,
    created_by: str  = None,
) -> dict:
    tipo_doc = tipo_doc.upper()
    if tipo_doc not in TIPO_DOC_MAP:
        raise HTTPException(status_code=400, detail=f"Tipo de documento inválido: {tipo_doc}")
    tipo_info = TIPO_DOC_MAP[tipo_doc]
    try:
        # BLOQUE 0: Verificar acceso
        emisor, acceso = await _verificar_acceso(emisor_id, api_key_id, es_sandbox, db)
        ambiente_efectivo = 1 if es_sandbox else emisor.ambiente

        # BLOQUE 1: Resolver cliente / documento origen
        cliente_final       = None
        cliente_id          = None
        doc_origen_emitido  = None
        doc_origen_recibido = None
        if tipo_doc in ("FAC", "LIQ"):
            cliente_final, cliente_id = await resolver_cliente(data, emisor_id, db)
        elif tipo_doc in ("NCR", "NDB"):
            doc_origen_emitido, cliente_final = await _cargar_doc_origen_emitido(
                data, emisor_id, tipo_doc, db
            )
        elif tipo_doc == "RET":
            doc_origen_emitido_id  = data.get("doc_origen_emitido_id")
            doc_origen_recibido_id = data.get("doc_origen_recibido_id")
            if doc_origen_emitido_id or (data.get("doc_origen_numero") and data.get("doc_origen_cod_doc") == "03"):
                doc_origen_emitido, cliente_final = await _cargar_ret_desde_emitido(
                    data, emisor_id, db
                )
            else:
                doc_origen_recibido, cliente_final = await _cargar_doc_origen_recibido(
                    data, emisor_id, db
                )

        # BLOQUE 2: Calcular totales y reservar secuencial
        punto_emision, secuencial = await _reservar_secuencial(
            data, emisor_id, tipo_doc, db, es_sandbox=es_sandbox
        )
        ahora_ec    = datetime.now(TZ_EC)
        fecha_sri   = ahora_ec.strftime("%d/%m/%Y")
        fecha_clave = ahora_ec.strftime("%Y-%m-%d")

        calculos      = None
        importe_total = Decimal("0.00")

        if tipo_doc == "FAC":
            items_completos = await completar_items_catalogo(data.get("items", []), emisor_id, db)
            calculos        = calcular_totales_e_impuestos(items_completos)
            importe_total   = Decimal(str(calculos["totales"]["importeTotal"]))
            propina         = Decimal(str(data.get("propina", 0) or 0)).quantize(Decimal("0.01"))
            importe_total  += propina
            if cliente_final["tipo_id"] == "07" and float(importe_total) > 50.00:
                raise HTTPException(
                    status_code=400,
                    detail=f"Facturas a Consumidor Final no pueden superar $50.00 (total: ${importe_total:.2f})."
                )
        elif tipo_doc == "LIQ":
            if cliente_final["tipo_id"] in ("07", "04"):
                raise HTTPException(
                    status_code=400,
                    detail="La liquidación de compra solo acepta cédula, pasaporte o identificación exterior."
                )
            items_completos = await completar_items_catalogo(data.get("items", []), emisor_id, db)
            calculos        = calcular_totales_e_impuestos(items_completos)
            importe_total   = Decimal(str(calculos["totales"]["importeTotal"]))
        elif tipo_doc == "NCR":
            items_completos = _preparar_items_desde_raw(data.get("items", []))
            calculos        = calcular_totales_e_impuestos(items_completos)
            importe_total   = Decimal(str(calculos["totales"]["importeTotal"]))
        elif tipo_doc == "NDB":
            motivos_raw   = data.get("motivos", [])
            importe_total = sum(Decimal(str(m.get("valor", 0))) for m in motivos_raw)
            calculos      = None
        elif tipo_doc == "RET":
            impuestos_ret = data.get("impuestos_ret") or data.get("impuestos") or []
            importe_total = sum(
                Decimal(str(i.get("valorRetenido", i.get("valor", 0))))
                for i in impuestos_ret
            )

        clave_acceso = generar_clave_acceso(
            fecha            = fecha_clave,
            tipo_comprobante = tipo_info["cod_doc"],
            ruc              = emisor.ruc,
            ambiente         = ambiente_efectivo,
            serie            = f"{punto_emision.estab_codigo}{punto_emision.punto_codigo}",
            secuencial       = secuencial,
        )

        nombre_comercial = punto_emision.nombre_est or emisor.nombre_comercial or emisor.razon_social
        direccion_est    = punto_emision.direccion_est or emisor.direccion_matriz

        # BLOQUE 3: Construir XML
        xml_obj = await _construir_xml(
            tipo_doc            = tipo_doc,
            tipo_info           = tipo_info,
            data                = data,
            emisor              = emisor,
            punto_emision       = punto_emision,
            cliente_final       = cliente_final,
            calculos            = calculos,
            clave_acceso        = clave_acceso,
            secuencial          = secuencial,
            fecha_sri           = fecha_sri,
            nombre_comercial    = nombre_comercial,
            direccion_est       = direccion_est,
            doc_origen_emitido  = doc_origen_emitido,
            doc_origen_recibido = doc_origen_recibido,
            importe_total       = importe_total,
            ambiente_efectivo   = ambiente_efectivo,
        )

        # BLOQUE 4: Firma
        xml_firmado_str = await firmar_xml(xml_obj, emisor)

        # BLOQUE 5: Persistir
        doc_id = await _persistir(
            tipo_doc            = tipo_doc,
            cod_doc             = tipo_info["cod_doc"],
            xml_firmado_str     = xml_firmado_str,
            xml_obj             = xml_obj,
            xml_root            = tipo_info["xml_root"],
            calculos            = calculos,
            emisor              = emisor,
            punto_emision       = punto_emision,
            cliente_final       = cliente_final,
            cliente_id          = cliente_id,
            secuencial          = secuencial,
            clave_acceso        = clave_acceso,
            importe_total       = importe_total,
            ahora_ec            = ahora_ec,
            api_key_id          = api_key_id,
            acceso              = acceso,
            data                = data,
            doc_origen_emitido  = doc_origen_emitido,
            doc_origen_recibido = doc_origen_recibido,
            es_sandbox          = es_sandbox,
            created_by          = created_by,
            db                  = db,
        )

        await db.commit()

        return {
            "ok":          True,
            "id":          doc_id,
            "tipo_doc":    tipo_doc,
            "claveAcceso": clave_acceso,
            "estado":      "FIRMADO" if not es_sandbox else "SANDBOX",
            "es_sandbox":  es_sandbox,
            "mensaje":     "Comprobante en proceso de autorización." if not es_sandbox else "Comprobante de prueba emitido correctamente.",
        }

    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error generando comprobante: {str(e)}")


# =============================================================================
# BLOQUE 0 — VERIFICAR ACCESO
# =============================================================================
async def _verificar_acceso(emisor_id: int, api_key_id: int, es_sandbox: bool, db: AsyncSession):
    # ── Validar firma electrónica ─────────────────────────────────────────────
    res_firma = await db.execute(text("""
        SELECT p12_path, p12_expiration 
        FROM emisores WHERE id = :eid
    """), {"eid": emisor_id})
    firma = res_firma.fetchone()
    if not firma or not firma.p12_path:
        raise HTTPException(
            status_code=402,
            detail="Debes cargar tu firma electrónica antes de emitir."
        )
    if not firma.p12_expiration or firma.p12_expiration <= date.today():
        raise HTTPException(
            status_code=402,
            detail="Tu firma electrónica está vencida. Actualízala para continuar."
        )

    # ── Sandbox ───────────────────────────────────────────────────────────────
    if es_sandbox:
        res = await db.execute(text("""
            SELECT e.* FROM emisores e WHERE e.id = :eid
        """), {"eid": emisor_id})
        emisor = res.fetchone()
        if not emisor:
            raise HTTPException(status_code=404, detail="Emisor no encontrado.")
        redis    = await get_redis()
        hoy      = datetime.now(TZ_EC).strftime("%Y-%m-%d")
        key_sand = f"kipu:usage:sandbox:{emisor_id}:{hoy}"
        uso_hoy_raw = await redis.get(key_sand)
        if uso_hoy_raw is None:
            res_count = await db.execute(text("""
                SELECT COUNT(*) FROM documentos_emitidos
                WHERE emisor_id  = :eid
                  AND es_sandbox = true
                  AND DATE(created_at AT TIME ZONE 'America/Guayaquil') = CURRENT_DATE
            """), {"eid": emisor_id})
            uso_hoy = res_count.scalar() or 0
            await redis.set(key_sand, uso_hoy, ex=86400)
        else:
            uso_hoy = int(uso_hoy_raw)
        if uso_hoy >= 100:
            raise HTTPException(
                status_code=429,
                detail="Límite de 100 documentos de prueba por día alcanzado."
            )
        return emisor, {"tipo": "sandbox", "descontar_credito": False, "redis_key": key_sand, "redis_ttl": 1}

    # ── Producción ────────────────────────────────────────────────────────────
    res = await db.execute(text("""
        SELECT e.*,
               COALESCE(uc.balance, 0) AS balance,
               s.estado                AS sub_estado,
               s.current_period_end,
               s.api_limit_mensual
        FROM emisores e
        LEFT JOIN user_credits  uc ON e.id = uc.emisor_id
        LEFT JOIN subscriptions s  ON e.id = s.emisor_id
        WHERE e.id = :eid
    """), {"eid": emisor_id})
    emisor = res.fetchone()
    if not emisor:
        raise HTTPException(status_code=404, detail="Emisor no encontrado.")

    sub_estado = getattr(emisor, "sub_estado", None)
    balance    = getattr(emisor, "balance", 0) or 0
    tiene_sub  = sub_estado in ("ACTIVO", "TRIAL")

    if not tiene_sub and balance <= 0:
        raise HTTPException(
            status_code=402,
            detail="Se requiere suscripción activa o créditos API para emitir."
        )

    # ── Suscriptor — verificar límite mensual ─────────────────────────────────
    if tiene_sub:
        limite   = getattr(emisor, "api_limit_mensual", 200) or 200
        redis    = await get_redis()
        mes      = datetime.now(TZ_EC).strftime("%Y-%m")
        key_prod = f"kipu:usage:prod:{emisor_id}:{mes}"
        uso_mes_raw = await redis.get(key_prod)
        if uso_mes_raw is None:
            res_count = await db.execute(text("""
                SELECT COUNT(*) FROM documentos_emitidos
                WHERE emisor_id  = :eid
                  AND es_sandbox = false
                  AND DATE_TRUNC('month', created_at AT TIME ZONE 'America/Guayaquil')
                    = DATE_TRUNC('month', NOW() AT TIME ZONE 'America/Guayaquil')
            """), {"eid": emisor_id})
            uso_mes = res_count.scalar() or 0
            await redis.set(key_prod, uso_mes, ex=35 * 86400)
        else:
            uso_mes = int(uso_mes_raw)
        if uso_mes >= limite:
            raise HTTPException(
                status_code=429,
                detail=f"Límite de {limite} documentos por mes alcanzado. Adquiere créditos adicionales para continuar."
            )
        tipo = "api" if api_key_id else "web"
        return emisor, {"tipo": tipo, "descontar_credito": False, "redis_key": key_prod, "redis_ttl": 35}

    # ── Sin suscripción — usa créditos ────────────────────────────────────────
    await db.execute(text("""
        SELECT emisor_id FROM user_credits WHERE emisor_id = :eid FOR UPDATE
    """), {"eid": emisor_id})


# =============================================================================
# BLOQUE 1 — CARGAR DOCUMENTO ORIGEN
# =============================================================================
async def _cargar_doc_origen_emitido(data: dict, emisor_id: int, tipo_doc: str, db: AsyncSession):
    doc_id = data.get("doc_origen_id")
    numero = data.get("doc_origen_numero")
    fecha  = data.get("doc_origen_fecha")

    if not doc_id:
        if not numero or not fecha:
            raise HTTPException(
                status_code=400,
                detail="Debe proporcionar 'doc_origen_id' o 'doc_origen_numero' + 'doc_origen_fecha'."
            )

        cliente_origen = data.get("cliente_origen") or {}

        if not cliente_origen.get("identificacion") or not cliente_origen.get("razon_social"):
            raise HTTPException(
                status_code=400,
                detail="Para documentos externos debe proporcionar 'cliente_origen' con identificacion y razon_social."
            )

        try:
            fecha_obj = datetime.strptime(fecha, "%d/%m/%Y").date()
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Formato de fecha inválido. Use dd/mm/yyyy."
            )

        class DocManual:
            id            = None
            numero_doc    = numero
            clave_acceso  = None
            fecha_emision = fecha_obj
            tipo_doc      = "FAC"
            cod_doc       = data.get("doc_origen_cod_doc", "01")
            datos         = {}

        cliente_final = {
            "identificacion": cliente_origen.get("identificacion"),
            "razon_social":   cliente_origen.get("razon_social"),
            "email":          cliente_origen.get("email"),
            "direccion":      cliente_origen.get("direccion", "S/N"),
            "telefono":       "",
            "tipo_id":        cliente_origen.get("tipo_id", "05"),
        }
        return DocManual(), cliente_final

    tipos_validos = ("FAC",) if tipo_doc in ("NCR", "NDB") else ("FAC", "LIQ", "NCR")

    res = await db.execute(text("""
        SELECT
            d.id, d.numero_doc, d.clave_acceso, d.fecha_emision,
            d.tipo_doc, d.cod_doc, d.datos,
            d.punto_emision_id, d.cliente_id,
            e.id as emisor_db_id, e.ruc, e.razon_social, e.nombre_comercial,
            e.direccion_matriz, e.ambiente, e.p12_path, e.p12_pass,
            e.obligado_contabilidad, e.contribuyente_especial,
            p.codigo as punto_codigo,
            est.codigo as estab_codigo,
            est.direccion as direccion_est,
            est.nombre_comercial as nombre_est
        FROM documentos_emitidos d
        JOIN emisores e  ON d.emisor_id = e.id
        JOIN puntos_emision p ON d.punto_emision_id = p.id
        JOIN establecimientos est ON p.establecimiento_id = est.id
        WHERE d.id = :did
          AND d.emisor_id = :eid
          AND d.estado_sri = 'AUTORIZADO'
          AND d.tipo_doc = ANY(:tipos)
        FOR UPDATE
    """), {"did": doc_id, "eid": emisor_id, "tipos": list(tipos_validos)})

    doc = res.fetchone()
    if not doc:
        raise HTTPException(
            status_code=404,
            detail="Documento origen no encontrado, no autorizado o tipo inválido."
        )

    datos = doc.datos or {}
    info  = (
        datos.get("infoFactura") or
        datos.get("infoLiquidacionCompra") or
        datos.get("infoNotaCredito") or {}
    )
    cliente_final = {
        "identificacion": (
            info.get("identificacionComprador") or
            info.get("identificacionProveedor") or
            datos.get("legacy_id_comprador")
        ),
        "razon_social": (
            info.get("razonSocialComprador") or
            info.get("razonSocialProveedor") or
            datos.get("legacy_razon_comprador")
        ),
        "email":      datos.get("legacy_email_comprador"),
        "direccion": "S/N",
        "telefono":  "",
        "tipo_id": (
            info.get("tipoIdentificacionComprador") or
            info.get("tipoIdentificacionProveedor") or
            "05"
        ),
    }
    return doc, cliente_final


async def _cargar_ret_desde_emitido(data: dict, emisor_id: int, db: AsyncSession):
    doc_id = data.get("doc_origen_emitido_id") or data.get("doc_origen_id")
    numero = data.get("doc_origen_numero")
    fecha  = data.get("doc_origen_fecha")

    if not doc_id:
        if not numero or not fecha:
            raise HTTPException(
                status_code=400,
                detail="Debe proporcionar 'doc_origen_emitido_id' o 'doc_origen_numero' + 'doc_origen_fecha'."
            )
        cliente_origen = data.get("cliente_origen") or data.get("proveedor_origen") or {}
        if not cliente_origen.get("identificacion") or not cliente_origen.get("razon_social"):
            raise HTTPException(
                status_code=400,
                detail="Para documentos externos debe proporcionar 'cliente_origen' o 'proveedor_origen'."
            )
        try:
            fecha_obj = datetime.strptime(fecha, "%d/%m/%Y").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Formato de fecha inválido. Use dd/mm/yyyy.")

        class DocEmitidoManual:
            id                     = None
            numero_doc             = numero
            clave_acceso           = None
            fecha_emision          = fecha_obj
            ruc_proveedor          = cliente_origen.get("identificacion")
            razon_social_proveedor = cliente_origen.get("razon_social")
            cod_doc                = data.get("doc_origen_cod_doc", "03")
            datos                  = {}

        cliente_final = {
            "identificacion": cliente_origen.get("identificacion"),
            "razon_social":   cliente_origen.get("razon_social"),
            "email":          cliente_origen.get("email"),
            "direccion":      cliente_origen.get("direccion", "S/N"),
            "telefono":       "",
            "tipo_id":        cliente_origen.get("tipo_id", "05"),
        }
        return DocEmitidoManual(), cliente_final

    res = await db.execute(text("""
        SELECT
            d.id, d.numero_doc, d.clave_acceso, d.fecha_emision,
            d.tipo_doc, d.cod_doc, d.datos,
            e.contribuyente_especial, e.obligado_contabilidad
        FROM documentos_emitidos d
        JOIN emisores e ON d.emisor_id = e.id
        WHERE d.id         = :did
          AND d.emisor_id  = :eid
          AND d.estado_sri = 'AUTORIZADO'
          AND d.tipo_doc   = 'LIQ'
        FOR UPDATE
    """), {"did": doc_id, "eid": emisor_id})

    doc = res.fetchone()
    if not doc:
        raise HTTPException(status_code=404, detail="Liquidación no encontrada o no autorizada.")

    datos = doc.datos or {}
    info  = datos.get("infoLiquidacionCompra") or {}

    cliente_final = {
        "identificacion": info.get("identificacionProveedor"),
        "razon_social":   info.get("razonSocialProveedor"),
        "email":          None,
        "direccion":      "S/N",
        "telefono":       "",
        "tipo_id":        info.get("tipoIdentificacionProveedor", "05"),
    }

    class DocLiqComoRecibido:
        id                     = doc.id
        numero_doc             = doc.numero_doc
        clave_acceso           = doc.clave_acceso
        fecha_emision          = doc.fecha_emision
        ruc_proveedor          = info.get("identificacionProveedor")
        razon_social_proveedor = info.get("razonSocialProveedor")
        cod_doc                = doc.cod_doc
        datos                  = doc.datos

    return DocLiqComoRecibido(), cliente_final


async def _cargar_doc_origen_recibido(data: dict, emisor_id: int, db: AsyncSession):
    doc_id = data.get("doc_origen_recibido_id") or data.get("doc_origen_id")
    numero = data.get("doc_origen_numero")
    fecha  = data.get("doc_origen_fecha")

    if not doc_id:
        if not numero or not fecha:
            raise HTTPException(
                status_code=400,
                detail="Debe proporcionar 'doc_origen_recibido_id' o 'doc_origen_numero' + 'doc_origen_fecha'."
            )

        cliente_origen = data.get("cliente_origen") or data.get("proveedor_origen") or {}

        if not cliente_origen.get("identificacion") or not cliente_origen.get("razon_social"):
            raise HTTPException(
                status_code=400,
                detail="Para documentos externos debe proporcionar 'cliente_origen' o 'proveedor_origen'."
            )

        try:
            fecha_obj = datetime.strptime(fecha, "%d/%m/%Y").date()
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Formato de fecha inválido. Use dd/mm/yyyy."
            )

        class DocRecibidoManual:
            id                     = None
            numero_doc             = numero
            clave_acceso           = None
            fecha_emision          = fecha_obj
            ruc_proveedor          = cliente_origen.get("identificacion")
            razon_social_proveedor = cliente_origen.get("razon_social")
            cod_doc                = data.get("doc_origen_cod_doc", "01")
            datos                  = {}

        cliente_final = {
            "identificacion": cliente_origen.get("identificacion"),
            "razon_social":   cliente_origen.get("razon_social"),
            "email":          cliente_origen.get("email"),
            "direccion":      cliente_origen.get("direccion", "S/N"),
            "telefono":       "",
            "tipo_id":        cliente_origen.get("tipo_id", "04"),
        }
        return DocRecibidoManual(), cliente_final

    res = await db.execute(text("""
        SELECT
            d.id, d.numero_doc, d.clave_acceso, d.fecha_emision,
            d.ruc_proveedor, d.razon_social_proveedor, d.datos,
            d.cod_doc,
            e.id as emisor_db_id, e.ruc, e.razon_social, e.nombre_comercial,
            e.direccion_matriz, e.ambiente, e.p12_path, e.p12_pass,
            e.contribuyente_especial, e.obligado_contabilidad
        FROM documentos_recibidos d
        JOIN emisores e ON d.emisor_id = e.id
        WHERE d.id = :did AND d.emisor_id = :eid
        FOR UPDATE
    """), {"did": doc_id, "eid": emisor_id})

    doc = res.fetchone()
    if not doc:
        raise HTTPException(status_code=404, detail="Documento recibido no encontrado.")

    res_ret = await db.execute(text("""
        SELECT id FROM documentos_emitidos
        WHERE doc_origen_recibido_id = :did AND tipo_doc = 'RET'
    """), {"did": doc_id})
    if res_ret.fetchone():
        raise HTTPException(status_code=409, detail="Este documento ya tiene una retención emitida.")

    cliente_final = {
        "identificacion": doc.ruc_proveedor,
        "razon_social":   doc.razon_social_proveedor,
        "email":          None,
        "direccion":      "S/N",
        "telefono":       "",
        "tipo_id":        "04",
    }
    return doc, cliente_final


# =============================================================================
# BLOQUE 2 — RESERVAR SECUENCIAL
# =============================================================================
async def _reservar_secuencial(data: dict, emisor_id: int, tipo_doc: str, db: AsyncSession, es_sandbox: bool = False):
    """Reserva el siguiente secuencial del punto de emisión por tipo de documento y ambiente."""
    estab = str(data.get("establecimiento", "001")).zfill(3)
    pto   = str(data.get("punto_emision",   "001")).zfill(3)

    res = await db.execute(text("""
        SELECT
            p.id as punto_id,
            p.codigo as punto_codigo,
            p.secuenciales,
            est.codigo as estab_codigo,
            est.direccion as direccion_est,
            est.nombre_comercial as nombre_est
        FROM puntos_emision p
        JOIN establecimientos est ON p.establecimiento_id = est.id
        WHERE est.codigo    = :estab
          AND p.codigo      = :pto
          AND est.emisor_id = :eid
          AND p.is_active   = true
    """), {"estab": estab, "pto": pto, "eid": emisor_id})

    punto = res.fetchone()
    if not punto:
        raise HTTPException(status_code=404, detail="Establecimiento o punto de emisión no encontrado.")

    rama = "pruebas" if es_sandbox else "produccion"

    res_sec = await db.execute(text("""
        UPDATE puntos_emision
        SET secuenciales = jsonb_set(
            secuenciales,
            ARRAY[:rama, :tipo_doc],
            ((COALESCE((secuenciales->:rama->>:tipo_doc)::int, 0) + 1)::text)::jsonb
        )
        WHERE id = :pid
        RETURNING (secuenciales->:rama->>:tipo_doc)::int AS sec
    """), {"pid": punto.punto_id, "tipo_doc": tipo_doc, "rama": rama})

    secuencial = str(res_sec.scalar()).zfill(9)
    return punto, secuencial


# =============================================================================
# BLOQUE 3 — CONSTRUIR XML
# =============================================================================
async def _construir_xml(
    tipo_doc, tipo_info, data, emisor, punto_emision,
    cliente_final, calculos, clave_acceso, secuencial,
    fecha_sri, nombre_comercial, direccion_est,
    doc_origen_emitido, doc_origen_recibido, importe_total,
    ambiente_efectivo: int = None,
) -> dict:

    info_tributaria = {
        "ambiente":        ambiente_efectivo or emisor.ambiente,
        "tipoEmision":     "1",
        "razonSocial":      emisor.razon_social,
        "nombreComercial": nombre_comercial,
        "ruc":             emisor.ruc,
        "claveAcceso":     clave_acceso,
        "codDoc":          tipo_info["cod_doc"],
        "estab":           punto_emision.estab_codigo,
        "ptoEmi":          punto_emision.punto_codigo,
        "secuencial":      secuencial,
        "dirMatriz":       emisor.direccion_matriz,
    }

    # ── FAC ───────────────────────────────────────────────────────────────────
    if tipo_doc == "FAC":
        propina   = Decimal(str(data.get("propina", 0) or 0)).quantize(Decimal("0.01"))
        pagos_xml = resolver_pagos(data.get("pagos", []), importe_total)

        info_fac = {
            "fechaEmision":                fecha_sri,
            "dirEstablecimiento":          direccion_est,
            "obligadoContabilidad":        getattr(emisor, "obligado_contabilidad", "NO"),
            "tipoIdentificacionComprador": cliente_final["tipo_id"],
            "razonSocialComprador":        cliente_final["razon_social"],
            "identificacionComprador":     cliente_final["identificacion"],
            "totalSinImpuestos":           calculos["totales"]["totalSinImpuestos"],
            "totalDescuento":              calculos["totales"]["totalDescuento"],
            "totalConImpuestos":           {"totalImpuesto": calculos["totalConImpuestosXml"]},
            "propina":                      f"{propina:.2f}",
            "importeTotal":                f"{importe_total:.2f}",
            "moneda":                      "DOLAR",
            "pagos":                       {"pago": pagos_xml},
        }
        if emisor.contribuyente_especial:
            info_fac["contribuyenteEspecial"] = emisor.contribuyente_especial

        return {
            "factura": {
                "@id":            "comprobante",
                "@version":        tipo_info["xml_version"],
                "infoTributaria": info_tributaria,
                "infoFactura":    info_fac,
                "detalles":       {"detalle": calculos["detallesXml"]},
                "infoAdicional":  {"campoAdicional": construir_campos_adicionales(data)},
            }
        }

    # ── LIQ ───────────────────────────────────────────────────────────────────
    elif tipo_doc == "LIQ":
        pagos_xml = resolver_pagos(data.get("pagos", []), importe_total)

        info_liq = {
            "fechaEmision":                fecha_sri,
            "dirEstablecimiento":          direccion_est,
            "obligadoContabilidad":        getattr(emisor, "obligado_contabilidad", "NO"),
            "tipoIdentificacionProveedor":  cliente_final["tipo_id"],
            "razonSocialProveedor":        cliente_final["razon_social"],
            "identificacionProveedor":     cliente_final["identificacion"],
            "direccionProveedor":          cliente_final.get("direccion", "S/N"),
            "totalSinImpuestos":           calculos["totales"]["totalSinImpuestos"],
            "totalDescuento":              calculos["totales"]["totalDescuento"],
            "totalConImpuestos":           {"totalImpuesto": calculos["totalConImpuestosXml"]},
            "importeTotal":                f"{importe_total:.2f}",
            "moneda":                      "DOLAR",
            "pagos":                       {"pago": pagos_xml},
        }
        if emisor.contribuyente_especial:
            info_liq["contribuyenteEspecial"] = emisor.contribuyente_especial

        return {
            "liquidacionCompra": {
                "@id":                   "comprobante",
                "@version":               tipo_info["xml_version"],
                "infoTributaria":        info_tributaria,
                "infoLiquidacionCompra": info_liq,
                "detalles":              {"detalle": calculos["detallesXml"]},
                "infoAdicional":         {"campoAdicional": construir_campos_adicionales(data)},
            }
        }

    # ── NCR ───────────────────────────────────────────────────────────────────
    elif tipo_doc == "NCR":
        motivo = data.get("motivo", "OTROS").strip().upper()
        if not motivo:
            motivo = "OTROS"

        datos_origen = doc_origen_emitido.datos or {}
        info_origen  = datos_origen.get("infoFactura") or datos_origen.get("infoLiquidacionCompra") or {}
        fecha_origen = doc_origen_emitido.fecha_emision.strftime("%d/%m/%Y")
        detalles_nc  = _adaptar_detalles_nc(calculos["detallesXml"])

        info_nc = {
            "fechaEmision":                fecha_sri,
            "dirEstablecimiento":          direccion_est,
            "tipoIdentificacionComprador": cliente_final["tipo_id"],
            "razonSocialComprador":        cliente_final["razon_social"],
            "identificacionComprador":     cliente_final["identificacion"],
            "obligadoContabilidad":        info_origen.get("obligadoContabilidad", "NO"),
            "codDocModificado":            doc_origen_emitido.cod_doc,
            "numDocModificado":            doc_origen_emitido.numero_doc,
            "fechaEmisionDocSustento":     fecha_origen,
            "totalSinImpuestos":           calculos["totales"]["totalSinImpuestos"],
            "valorModificacion":           calculos["totales"]["importeTotal"],
            "totalConImpuestos":           {"totalImpuesto": calculos["totalConImpuestosXml"]},
            "motivo":                      motivo,
        }
        if emisor.contribuyente_especial:
            info_nc["contribuyenteEspecial"] = emisor.contribuyente_especial

        return {
            "notaCredito": {
                "@id":              "comprobante",
                "@version":        tipo_info["xml_version"],
                "infoTributaria":  info_tributaria,
                "infoNotaCredito": info_nc,
                "detalles":        {"detalle": detalles_nc},
                "infoAdicional":   {"campoAdicional": construir_campos_adicionales(data)},
            }
        }

    # ── NDB ───────────────────────────────────────────────────────────────────
    elif tipo_doc == "NDB":
        motivos_raw = data.get("motivos", [])
        if not motivos_raw:
            raise HTTPException(status_code=400, detail="Se requiere al menos un motivo.")

        datos_origen = doc_origen_emitido.datos or {}
        info_origen  = datos_origen.get("infoFactura") or datos_origen.get("infoLiquidacionCompra") or {}
        fecha_origen = doc_origen_emitido.fecha_emision.strftime("%d/%m/%Y")

        total_ndb = sum(Decimal(str(m.get("valor", 0))) for m in motivos_raw)

        motivos_xml = [
            {
                "razon": m.get("razon", ""),
                "valor": f"{Decimal(str(m.get('valor', 0))):.2f}",
            }
            for m in motivos_raw
        ]

        impuestos_ndb_raw = data.get("impuestos", [])
        if impuestos_ndb_raw:
            impuestos_ndb_xml = [
                {
                    "codigo":           str(i.get("codigo", "2")),
                    "codigoPorcentaje": str(i.get("codigoPorcentaje", "4")),
                    "tarifa":           str(i.get("tarifa", "15")),
                    "baseImponible":    f"{Decimal(str(i.get('baseImponible', 0))):.2f}",
                    "valor":            f"{Decimal(str(i.get('valor', 0))):.2f}",
                }
                for i in impuestos_ndb_raw
            ]
        else:
            impuestos_ndb_xml = [{
                "codigo":           "2",
                "codigoPorcentaje": "0",
                "tarifa":           "0",
                "baseImponible":    f"{total_ndb:.2f}",
                "valor":            "0.00",
            }]

        pagos_xml = resolver_pagos(data.get("pagos", []), total_ndb)

        info_ndb = {
            "fechaEmision":                fecha_sri,
            "dirEstablecimiento":          direccion_est,
            "tipoIdentificacionComprador": cliente_final["tipo_id"],
            "razonSocialComprador":        cliente_final["razon_social"],
            "identificacionComprador":     cliente_final["identificacion"],
            "obligadoContabilidad":        info_origen.get("obligadoContabilidad", "NO"),
            "codDocModificado":            doc_origen_emitido.cod_doc,
            "numDocModificado":            doc_origen_emitido.numero_doc,
            "fechaEmisionDocSustento":     fecha_origen,
            "totalSinImpuestos":           f"{total_ndb:.2f}",
            "impuestos":                   {"impuesto": impuestos_ndb_xml},
            "valorTotal":                  f"{total_ndb:.2f}",
            "pagos":                       {"pago": pagos_xml},
        }
        if emisor.contribuyente_especial:
            info_ndb["contribuyenteEspecial"] = emisor.contribuyente_especial

        return {
            "notaDebito": {
                "@id":            "comprobante",
                "@version":        tipo_info["xml_version"],
                "infoTributaria": info_tributaria,
                "infoNotaDebito": info_ndb,
                "motivos":        {"motivo": motivos_xml},
                "infoAdicional":  {"campoAdicional": construir_campos_adicionales(data)},
            }
        }

    # ── RET ───────────────────────────────────────────────────────────────────
    elif tipo_doc == "RET":
        impuestos_ret = data.get("impuestos_ret") or data.get("impuestos") or []
        if not impuestos_ret:
            raise HTTPException(status_code=400, detail="Se requiere al menos un impuesto.")

        doc_ret = doc_origen_recibido or doc_origen_emitido
        if not doc_ret:
            raise HTTPException(status_code=400, detail="Se requiere documento origen para la retención.")

        fecha_origen = doc_ret.fecha_emision.strftime("%d/%m/%Y")

        impuestos_xml = [
            {
                "codigo":                  str(i.get("codigo", "1")),
                "codigoRetencion":         str(i.get("codigoRetencion", "")),
                "baseImponible":           f"{Decimal(str(i.get('baseImponible', 0))):.2f}",
                "porcentajeRetener":       str(i.get("porcentajeRetener", i.get("tarifa", ""))),
                "valorRetenido":           f"{Decimal(str(i.get('valorRetenido', i.get('valor', 0)))):.2f}",
                "codDocSustento":           str(i.get("codDocSustento", doc_ret.cod_doc or "01")),
                "numDocSustento":           (doc_ret.numero_doc or "").replace("-", "").zfill(15),
                "fechaEmisionDocSustento": fecha_origen,
            }
            for i in impuestos_ret
        ]

        info_ret = {
            "fechaEmision":                    fecha_sri,
            "dirEstablecimiento":                direccion_est,
            "obligadoContabilidad":              getattr(emisor, "obligado_contabilidad", "NO"),
            "tipoIdentificacionSujetoRetenido": cliente_final["tipo_id"],
            "razonSocialSujetoRetenido":        cliente_final["razon_social"],
            "identificacionSujetoRetenido":     cliente_final["identificacion"],
            "periodoFiscal":                    data.get("periodo_fiscal", datetime.now(TZ_EC).strftime("%m/%Y")),
        }
        if emisor.contribuyente_especial:
            info_ret["contribuyenteEspecial"] = emisor.contribuyente_especial

        return {
            "comprobanteRetencion": {
                "@id":               "comprobante",
                "@version":          tipo_info["xml_version"],
                "infoTributaria":    info_tributaria,
                "infoCompRetencion": info_ret,
                "impuestos":         {"impuesto": impuestos_xml},
                "infoAdicional":     {"campoAdicional": construir_campos_adicionales(data)},
            }
        }


# =============================================================================
# BLOQUE 5 — PERSISTIR
# =============================================================================
async def _persistir(
    tipo_doc, cod_doc, xml_firmado_str, xml_obj, xml_root,
    calculos, emisor, punto_emision, cliente_final, cliente_id,
    secuencial, clave_acceso, importe_total, ahora_ec,
    api_key_id, acceso, data,
    doc_origen_emitido, doc_origen_recibido,
    es_sandbox: bool = False, created_by = None,
    db = None,
) -> str:
    carpeta  = _carpeta_por_tipo(tipo_doc)
    prefijo  = "sandbox/" if es_sandbox else ""
    xml_path = f"{emisor.ruc}/{prefijo}{carpeta}/{clave_acceso}.xml"
    upload_file(xml_path, xml_firmado_str.encode("utf-8"), "text/xml")

    if acceso["descontar_credito"]:
        await db.execute(text("""
            UPDATE user_credits SET balance = balance - 1, last_updated = NOW()
            WHERE emisor_id = :eid
        """), {"eid": emisor.id})

    datos_json = {
        **xml_obj[xml_root],
        "resumenImpuestos": calculos["resumenImpuestos"] if calculos else [],
    }
    if doc_origen_emitido:
        datos_json["doc_origen_id"] = str(doc_origen_emitido.id)
    if doc_origen_recibido:
        datos_json["doc_origen_recibido_id"] = str(doc_origen_recibido.id)

    origen     = "api" if api_key_id else data.get("origen", "web")
    numero_doc = f"{punto_emision.estab_codigo}-{punto_emision.punto_codigo}-{secuencial}"

    # Extraer email del comprador de forma segura
    email_comprador = (cliente_final.get("email") or "").strip().lower() if cliente_final else ""

    res = await db.execute(text("""
        INSERT INTO documentos_emitidos (
            id,
            emisor_id, punto_emision_id, cliente_id, api_key_id,
            tipo_doc, cod_doc,
            clave_acceso, numero_doc, secuencial, fecha_emision,
            estado_sri, importe_total,
            datos, xml_path, origen,
            email_comprador,
            doc_origen_emitido_id, doc_origen_recibido_id,
            es_sandbox, created_by,
            created_at, updated_at
        ) VALUES (
            gen_random_uuid(),
            :emisor_id, :pto_id, :cliente_id, :api_key_id,
            :tipo_doc, :cod_doc,
            :clave, :numero_doc, :sec, :fecha,
            'FIRMADO', :total,
            CAST(:datos AS jsonb), :xml_path, :origen,
            :email_comprador,
            :doc_origen_emitido_id, :doc_origen_recibido_id,
            :es_sandbox, :created_by,
            NOW(), NOW()
        ) RETURNING id
    """), {
        "emisor_id":              emisor.id,
        "pto_id":                 punto_emision.punto_id,
        "cliente_id":             cliente_id,
        "api_key_id":             api_key_id,
        "tipo_doc":               tipo_doc,
        "cod_doc":                cod_doc,
        "clave":                  clave_acceso,
        "numero_doc":             numero_doc,
        "sec":                    secuencial,
        "fecha":                  ahora_ec.date(),
        "total":                  str(importe_total),
        "datos":                  json.dumps(datos_json, default=str),
        "xml_path":               xml_path,
        "origen":                 origen,
        "email_comprador":        email_comprador or None,
        "doc_origen_emitido_id":  str(doc_origen_emitido.id) if doc_origen_emitido and getattr(doc_origen_emitido, "id", None) else None,
        "doc_origen_recibido_id": str(doc_origen_recibido.id) if doc_origen_recibido and getattr(doc_origen_recibido, "id", None) else None,
        "es_sandbox":             es_sandbox,
        "created_by":             str(created_by) if created_by else None,
    })
    doc_id = str(res.scalar())

    if tipo_doc in ("FAC", "LIQ") and calculos:
        await _descontar_stock(datos_json, emisor.id, db)

    await _invalidar_cache(emisor.id)

    # ── Redis: contador de uso + cola SRI ─────────────────────────────────────
    try:
        redis     = await get_redis()
        redis_key = acceso.get("redis_key")
        if redis_key:
            nuevo = await redis.incr(redis_key)
            if nuevo == 1:
                # Primera emisión del período — establecer TTL
                ttl_dias = acceso.get("redis_ttl", 1)  # sandbox=1día, prod=35días
                await redis.expire(redis_key, ttl_dias * 86400)
        # Todos van al SRI — el worker decide la URL según es_sandbox
        await redis.lpush("kipu:queue:emision", doc_id)
    except Exception as e:
        print(f"[Usage/Queue] ⚠️ Error Redis: {e}")

    return doc_id

# =============================================================================
# HELPERS
# =============================================================================
def _carpeta_por_tipo(tipo_doc: str) -> str:
    return {
        "FAC": "facturas",
        "LIQ": "liquidaciones",
        "NCR": "notas_credito",
        "NDB": "notas_debito",
        "RET": "retenciones",
    }.get(tipo_doc, "documentos")


def _preparar_items_desde_raw(items_raw: list) -> list:
    resultado = []
    for item in items_raw:
        codigo_raw = item.get("codigo")
        resultado.append({
            "codigo":          str(codigo_raw) if codigo_raw and str(codigo_raw) != "None" else "S/C",
            "descripcion":     item.get("descripcion", ""),
            "cantidad":        float(item.get("cantidad", 1)),
            "precio_unitario": float(item.get("precio_unitario", 0)),
            "descuento":       float(item.get("descuento", 0)),
            "tipo_iva":        str(item.get("tipo_iva", "15")),
            "unidad_medida":   item.get("unidad_medida", "UNIDAD"),
        })
    if not resultado:
        raise HTTPException(status_code=400, detail="Se requiere al menos un ítem.")
    return resultado


def _adaptar_detalles_nc(detalles_xml: list) -> list:
    resultado = []
    for det in detalles_xml:
        d      = dict(det)
        codigo = d.pop("codigoPrincipal", "S/C")
        det_nc = {}
        if codigo and codigo != "S/C":
            det_nc["codigoInterno"] = codigo
        det_nc["descripcion"]            = d.get("descripcion", "")
        det_nc["cantidad"]               = d.get("cantidad", "1.000000")
        det_nc["precioUnitario"]         = d.get("precioUnitario", "0.000000")
        det_nc["descuento"]              = d.get("descuento", "0.00")
        det_nc["precioTotalSinImpuesto"] = d.get("precioTotalSinImpuesto", "0.00")
        det_nc["impuestos"]              = d.get("impuestos", {})
        resultado.append(det_nc)
    return resultado


async def _descontar_stock(datos_json: dict, emisor_id: int, db: AsyncSession):
    try:
        detalles = datos_json.get("detalles", {}).get("detalle", [])
        if not isinstance(detalles, list):
            detalles = [detalles]
        for det in detalles:
            codigo   = det.get("codigoPrincipal") or det.get("codigoAuxiliar")
            if not codigo or codigo == "S/C":
                continue
            cantidad = float(det.get("cantidad", 0))
            await db.execute(text("""
                UPDATE catalogo_items
                SET stock = GREATEST(0, stock - :qty), updated_at = NOW()
                WHERE emisor_id = :eid AND stock > 0 AND codigo = :cod
            """), {"qty": int(cantidad), "eid": emisor_id, "cod": codigo})
    except Exception as e:
        print(f"[Stock] ⚠️ Error descontando stock: {e}")


async def _invalidar_cache(emisor_id: int):
    try:
        redis   = await get_redis()
        pattern = f"kipu:cache:*:{emisor_id}:*"
        keys    = await redis.keys(pattern)
        if keys:
            await redis.delete(*keys)
    except Exception as e:
        print(f"[Cache] ⚠️ No invalidado: {e}")