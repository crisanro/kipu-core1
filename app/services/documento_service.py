# app/services/documento_service.py
#
# Core unificado de emisión de comprobantes electrónicos.
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
#   Bloque 5 — Persistir (documento + movimientos de stock)
#   Después del commit — contador de uso y cola del SRI
#
# Cambios respecto a la versión anterior:
#   - Se encola al SRI DESPUÉS del commit (antes el worker podía tomar el documento
#     antes de que existiera en la base y lo descartaba).
#   - Stock vía stock_service: sandbox no mueve inventario, la LIQ SUMA stock
#     (es una compra) y cada documento registra exactamente lo que movió.
#   - credito_estado = 'COBRADO' cuando se descuenta crédito: solo eso se devuelve
#     si el SRI rechaza el documento.
#   - El contador de uso se incrementa solo si la emisión quedó confirmada.
#   - NC y ND heredan el email del documento origen.
#   - Invalidación de caché unificada vía app.core.cache.invalidate_emisor.

from datetime import datetime
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from app.utils.calculadora import calcular_totales_e_impuestos
from app.utils.crypto import generar_clave_acceso
from app.utils.sri_core import resolver_cliente, completar_items_catalogo, firmar_xml
from app.core.cache import get_redis, invalidate_emisor
from app.services.notification_service import despachar_notificaciones, descartar_notificaciones

from app.services.documentos.helpers import (
    TZ_EC, TIPO_DOC_MAP,
    LIMITE_EFECTIVO, COD_EFECTIVO,
    preparar_items_desde_raw,
)
from app.services.documentos.acceso import verificar_acceso
from app.services.documentos.origen import (
    cargar_doc_origen_emitido,
    cargar_ret_desde_emitido,
    cargar_doc_origen_recibido,
)
from app.services.documentos.secuencial import reservar_secuencial
from app.services.documentos.xml_builder import construir_xml
from app.services.documentos.persistencia import persistir


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
        emisor, acceso = await verificar_acceso(emisor_id, api_key_id, es_sandbox, db)
        ambiente_efectivo = 1 if es_sandbox else emisor.ambiente

        # BLOQUE 1: Resolver cliente / documento origen
        cliente_final       = None
        cliente_id          = None
        doc_origen_emitido  = None
        doc_origen_recibido = None
        if tipo_doc in ("FAC", "LIQ"):
            cliente_final, cliente_id = await resolver_cliente(data, emisor_id, db)
        elif tipo_doc in ("NCR", "NDB"):
            doc_origen_emitido, cliente_final = await cargar_doc_origen_emitido(
                data, emisor_id, tipo_doc, db
            )

            if cliente_final.get("tipo_id") == "07":
                raise HTTPException(
                    status_code=400,
                    detail="No se pueden emitir notas de crédito ni débito para comprobantes a Consumidor Final."
                )
        elif tipo_doc == "RET":
            doc_origen_emitido_id  = data.get("doc_origen_emitido_id")
            doc_origen_recibido_id = data.get("doc_origen_recibido_id")
            if doc_origen_emitido_id or (data.get("doc_origen_numero") and data.get("doc_origen_cod_doc") == "03"):
                doc_origen_emitido, cliente_final = await cargar_ret_desde_emitido(
                    data, emisor_id, db
                )
            else:
                doc_origen_recibido, cliente_final = await cargar_doc_origen_recibido(
                    data, emisor_id, db
                )

        # BLOQUE 2: Calcular totales y reservar secuencial
        punto_emision, secuencial = await reservar_secuencial(
            data, emisor_id, tipo_doc, db, es_sandbox=es_sandbox
        )
        ahora_ec    = datetime.now(TZ_EC)
        fecha_sri   = ahora_ec.strftime("%d/%m/%Y")
        fecha_clave = ahora_ec.strftime("%Y-%m-%d")

        # ── Default estado de cobro para FAC, LIQ, NDB ───────────────
        if tipo_doc in ("FAC", "LIQ", "NDB"):
            if not data.get("estado_cobro"):
                data["estado_cobro"] = "PAGADO"
                if not data.get("fecha_pago"):
                    data["fecha_pago"] = data.get("fecha_emision") or ahora_ec.strftime("%Y-%m-%d")

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
            items_completos = preparar_items_desde_raw(data.get("items", []))
            calculos        = calcular_totales_e_impuestos(items_completos)
            importe_total   = Decimal(str(calculos["totales"]["importeTotal"]))
        elif tipo_doc == "NDB":
            motivos_raw   = data.get("motivos", [])
            importe_total = sum(Decimal(str(m.get("valor", 0))) for m in motivos_raw)
            impuestos_ndb_raw = data.get("impuestos", [])
            if impuestos_ndb_raw:
                importe_total += sum(Decimal(str(i.get("valor", 0))) for i in impuestos_ndb_raw)
            calculos      = None
        elif tipo_doc == "RET":
            impuestos_ret = data.get("impuestos_ret") or data.get("impuestos") or []
            importe_total = sum(
                Decimal(str(i.get("valorRetenido", i.get("valor", 0))))
                for i in impuestos_ret
            )

        # ── Validar regla $500: efectivo no permitido en >= $500 ──────────
        if tipo_doc in ("FAC", "LIQ") and importe_total >= LIMITE_EFECTIVO:
            pagos_raw = data.get("pagos", [])
            tiene_efectivo = any(
                str(p.get("forma_pago", "01")) == COD_EFECTIVO
                for p in pagos_raw
            )
            if tiene_efectivo:
                raise HTTPException(
                    status_code=400,
                    detail=f"Transacciones ≥ ${LIMITE_EFECTIVO} deben utilizar el sistema financiero. "
                           "Cambia la forma de pago a tarjeta, transferencia u otro medio financiero."
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
        xml_obj = await construir_xml(
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
        doc_id = await persistir(
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

        # ── Solo ahora que el documento existe en la base ──────────────────────
        await _post_commit(doc_id, acceso)
        await invalidate_emisor(emisor.id)

        try:
            await despachar_notificaciones(db)
        except Exception as e:
            print(f"[Notif] ⚠️ Error despachando notificaciones post-emisión: {e}")

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
        descartar_notificaciones(db)
        raise
    except Exception as e:
        await db.rollback()
        descartar_notificaciones(db)
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error generando comprobante: {str(e)}")


async def _post_commit(doc_id: str, acceso: dict) -> None:
    """Contador de uso y cola del SRI. Si Redis falla, la conciliación recoge el documento."""
    try:
        redis     = await get_redis()
        redis_key = acceso.get("redis_key")
        if redis_key:
            nuevo = await redis.incr(redis_key)
            if nuevo == 1:
                ttl_dias = acceso.get("redis_ttl", 1)
                await redis.expire(redis_key, ttl_dias * 86400)
        await redis.lpush("kipu:queue:emision", doc_id)
    except Exception as e:
        print(f"[Usage/Queue] ⚠️ Error Redis (la conciliación lo recogerá): {e}")