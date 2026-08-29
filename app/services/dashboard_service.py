# app/services/dashboard_service.py
import json
import calendar
from datetime import date, datetime
import pytz
import traceback
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.cache import cache_get, cache_set

TTL_HEADER     = 300
TTL_MES_ACTUAL = 120
TTL_MES_PASADO = 3600


def _es_mes_actual(año: int, mes: int) -> bool:
    hoy = date.today()
    return año == hoy.year and mes == hoy.month


def _meses_en_rango(fecha_inicio: date, fecha_fin: date) -> list[tuple[int, int]]:
    meses   = []
    current = fecha_inicio.replace(day=1)
    while current <= fecha_fin:
        meses.append((current.year, current.month))
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)
    return meses


async def obtener_dashboard_core(
    emisor_id:        int | None,
    email_usuario:    str,
    email_verificado: bool,
    fecha_inicio:     date,
    fecha_fin:        date,
    db:               AsyncSession,
    sandbox:            bool = False,
):
    try:
        # ═══════════════════════════════════════════════════════════
        # CAPA 1 — HEADER
        # ═══════════════════════════════════════════════════════════
        cache_key_header = f"dashboard_header:{emisor_id}"
        data_header      = await cache_get(cache_key_header)

        if not data_header:
            res_header = await db.execute(text("""
                SELECT
                    e.ruc, e.p12_path, e.p12_expiration, e.ambiente, e.tipo_emisor,
                    uc.balance AS balance_api,
                    s.estado   AS sub_estado,
                    s.plan     AS sub_plan,
                    s.current_period_end,
                    p.whatsapp_number,
                    e.id AS emisor_db_id,
                    (SELECT COUNT(*) FROM establecimientos WHERE emisor_id = e.id)                  AS total_estab,
                    (SELECT COUNT(*) FROM puntos_emision   WHERE emisor_id = e.id)                  AS total_puntos,
                    (SELECT COUNT(*) FROM api_keys         WHERE emisor_id = e.id AND revoked = false) AS total_keys,
                    (SELECT EXISTS(
                        SELECT 1 FROM notificaciones WHERE emisor_id = e.id AND leida = false
                    )) AS tiene_notificaciones
                FROM profiles p
                LEFT JOIN emisor_usuarios eu ON eu.profile_id = p.id
                LEFT JOIN emisores e         ON e.id = eu.emisor_id
                LEFT JOIN user_credits uc    ON uc.emisor_id = e.id
                LEFT JOIN subscriptions s    ON s.emisor_id  = e.id
                WHERE LOWER(p.email) = LOWER(:email)
                LIMIT 1
            """), {"email": email_usuario})

            row = res_header.mappings().fetchone()
            if not row:
                data_header = {
                    "ruc": None, "p12_expiration": None, "ambiente": None,
                    "p12_path": None, "balance_api": 0,
                    "sub_estado": None, "sub_plan": None, "current_period_end": None,
                    "whatsapp_number": None, "emisor_db_id": None,
                    "total_estab": 0, "total_puntos": 0, "total_keys": 0,
                    "tiene_notificaciones": False, "tipo_emisor": None,
                }
            else:
                data_header = dict(row)
                if isinstance(data_header.get("p12_expiration"), date):
                    data_header["p12_expiration"] = data_header["p12_expiration"].isoformat()
                if isinstance(data_header.get("current_period_end"), datetime):
                    data_header["current_period_end"] = data_header["current_period_end"].isoformat()

            if data_header.get("ambiente") == 2 or data_header.get("sub_estado"):
                await cache_set(cache_key_header, data_header, TTL_HEADER)

        current_emisor_id = emisor_id or data_header.get("emisor_db_id")

        # ═══════════════════════════════════════════════════════════
        # CAPA 2 — DOCUMENTOS POR MES
        # ═══════════════════════════════════════════════════════════
        todos_los_docs = []

        if current_emisor_id:
            meses = _meses_en_rango(fecha_inicio, fecha_fin)

            for (año, mes) in meses:
                cache_key_mes = f"dashboard_docs:{current_emisor_id}:{año}:{mes:02d}:{sandbox}"
                docs_mes      = await cache_get(cache_key_mes)

                if docs_mes is None:
                    primer_dia = date(año, mes, 1)
                    ultimo_dia = date(año, mes, calendar.monthrange(año, mes)[1])

                    res_docs = await db.execute(text("""
                        SELECT
                            d.id, d.clave_acceso, d.secuencial, d.numero_doc,
                            d.tipo_doc, d.cod_doc, d.estado_sri, d.estado_cobro,
                            d.importe_total, d.fecha_emision, d.created_at,
                            d.datos,
                            est.codigo AS estab,
                            p.codigo   AS punto
                        FROM documentos_emitidos d
                        LEFT JOIN puntos_emision p     ON d.punto_emision_id = p.id
                        LEFT JOIN establecimientos est ON p.establecimiento_id = est.id
                        WHERE d.emisor_id      = :eid
                        AND d.fecha_emision  >= :fini
                        AND d.fecha_emision  <= :ffin
                        AND d.tipo_doc       IN ('FAC', 'LIQ')
                        AND d.es_sandbox     = :sandbox
                        ORDER BY d.fecha_emision DESC, d.created_at DESC
                    """), {
                        "eid":     current_emisor_id,
                        "fini":    primer_dia,
                        "ffin":    ultimo_dia,
                        "sandbox": sandbox,
                    })

                    docs_mes = []
                    for d in res_docs.mappings():
                        datos    = d.get("datos") or {}
                        detalles = datos.get("detalles", {}).get("detalle", [])
                        if not isinstance(detalles, list):
                            detalles = [detalles] if detalles else []

                        # Calcular impuestos desde JSONB
                        impuestos_por_tarifa = {}
                        for detalle in detalles:
                            if not isinstance(detalle, dict):
                                continue
                            imp      = detalle.get("impuestos", {}).get("impuesto", {})
                            imp_list = imp if isinstance(imp, list) else ([imp] if imp else [])
                            for i in imp_list:
                                if not isinstance(i, dict):
                                    continue
                                tarifa = str(i.get("tarifa", "0"))
                                if tarifa not in impuestos_por_tarifa:
                                    impuestos_por_tarifa[tarifa] = {"base": 0.0, "iva": 0.0}
                                impuestos_por_tarifa[tarifa]["base"] += float(i.get("baseImponible") or 0)
                                impuestos_por_tarifa[tarifa]["iva"]  += float(i.get("valor") or 0)

                        # Totales desde datos JSONB o legacy
                        info_fac    = datos.get("infoFactura") or datos.get("infoLiquidacionCompra") or {}
                        total       = float(d["importe_total"] or 0)
                        subtotal_15 = float(info_fac.get("totalSinImpuestos") or datos.get("legacy_subtotal_iva") or 0)
                        subtotal_0  = float(datos.get("legacy_subtotal_0") or 0)
                        iva         = float(datos.get("legacy_valor_iva") or 0)

                        # Comprador
                        razon  = info_fac.get("razonSocialComprador") or datos.get("legacy_razon_comprador") or ""
                        id_com = info_fac.get("identificacionComprador") or datos.get("legacy_id_comprador") or ""

                        docs_mes.append({
                            "id":                str(d["id"]),
                            "clave_acceso":      d["clave_acceso"],
                            "numero":            d["numero_doc"] or f"{d['estab']}-{d['punto']}-{d['secuencial']}",
                            "tipo_doc":          d["tipo_doc"],
                            "cliente_nombre":    razon,
                            "cliente_id":        id_com,
                            "subtotal_15":       subtotal_15,
                            "subtotal_0":        subtotal_0,
                            "iva":               iva,
                            "total":             total,
                            "estado":            d["estado_sri"],
                            "estado_cobro":      d["estado_cobro"],
                            "impuestos_totales": impuestos_por_tarifa,
                            "fecha":             d["fecha_emision"].isoformat() if isinstance(d["fecha_emision"], (date, datetime)) else str(d["fecha_emision"]),
                            "created_at":        d["created_at"].isoformat() if isinstance(d["created_at"], (date, datetime)) else str(d["created_at"] or ""),
                        })

                    ttl = TTL_MES_ACTUAL if _es_mes_actual(año, mes) else TTL_MES_PASADO
                    await cache_set(cache_key_mes, docs_mes, ttl)

                todos_los_docs.extend(docs_mes)

            # Filtrar al rango exacto
            def _parse_fecha(f) -> date:
                v = f["fecha"]
                return date.fromisoformat(str(v)[:10])

            todos_los_docs = [
                f for f in todos_los_docs
                if fecha_inicio <= _parse_fecha(f) <= fecha_fin
            ]
            todos_los_docs.sort(
                key=lambda f: (f["fecha"], f.get("created_at", "")),
                reverse=True
            )
            todos_los_docs = todos_los_docs[:100]

        # Resumen
        subtotal_iva = subtotal_0 = valor_iva = importe_total = 0.0
        total_autorizados = 0
        for d in todos_los_docs:
            if d["estado"] == "AUTORIZADO":
                subtotal_iva      += d["subtotal_15"]
                subtotal_0        += d["subtotal_0"]
                valor_iva         += d["iva"]
                importe_total     += d["total"]
                total_autorizados += 1

        resumen = {
            "total_documentos": total_autorizados,
            "subtotal_iva":     round(subtotal_iva,  2),
            "subtotal_0":       round(subtotal_0,    2),
            "valor_iva":        round(valor_iva,     2),
            "importe_total":    round(importe_total, 2),
        }

        # Firma
        tz          = pytz.timezone("America/Guayaquil")
        hoy         = datetime.now(tz).date()
        expiracion  = data_header.get("p12_expiration")
        if isinstance(expiracion, str) and expiracion:
            expiracion = date.fromisoformat(expiracion)

        firma_vigente = False
        firma_alerta  = None if current_emisor_id else "Configuración inicial pendiente"

        if expiracion:
            dias_restantes = (expiracion - hoy).days
            if dias_restantes <= 0:
                firma_alerta  = "Firma caducada"
                firma_vigente = False
            elif dias_restantes <= 30:
                firma_alerta  = f"Firma próxima a caducar ({dias_restantes} días)"
                firma_vigente = True
            else:
                firma_vigente = True

        sub_estado = data_header.get("sub_estado")
        suscripcion_activa = sub_estado in ("ACTIVO", "TRIAL")

        return {
            "ok": True,
            "data": {
                "health": {
                    "email_verificado":              email_verificado,
                    "ruc":                           bool(data_header.get("ruc")),
                    "ambiente_produccion":           data_header.get("ambiente") == 2,
                    "firma_configurada":             bool(data_header.get("p12_path")),
                    "firma_vigente":                 firma_vigente,
                    "firma_alerta":                  firma_alerta,
                    "establecimientos_configurados": int(data_header.get("total_estab", 0)) > 0,
                    "puntos_emision_configurados":   int(data_header.get("total_puntos", 0)) > 0,
                    "suscripcion_activa":            suscripcion_activa,
                    "suscripcion_plan":              data_header.get("sub_plan"),
                    "suscripcion_estado":            sub_estado,
                    "balance_api":                   data_header.get("balance_api") or 0,
                    "tipo_emisor":                   data_header.get("tipo_emisor"),
                    "usuario_nuevo":                 not current_emisor_id,
                    "tiene_api_key":                 int(data_header.get("total_keys", 0)) > 0,
                    "whatsapp_vinculado":            bool(data_header.get("whatsapp_number")),
                    "whatsapp_numero":               data_header.get("whatsapp_number"),
                    "tiene_notificaciones":          bool(data_header.get("tiene_notificaciones", False)),
                    "listo_produccion": (
                        email_verificado and
                        bool(data_header.get("ruc")) and
                        bool(data_header.get("p12_path")) and
                        firma_vigente and
                        int(data_header.get("total_estab", 0)) > 0 and
                        int(data_header.get("total_puntos", 0)) > 0
                    ),
                },
                "resumen":    resumen,
                "documentos": todos_los_docs,
                "periodo": {
                    "desde": fecha_inicio.isoformat(),
                    "hasta": fecha_fin.isoformat(),
                }
            }
        }

    except Exception as e:
        traceback.print_exc()
        return {"ok": False, "error": f"Error interno: {str(e)}"}


# =============================================================================
# DETALLE DE DOCUMENTO
# =============================================================================

async def consultar_detalle_documento_core(
    emisor_id: int,
    doc_id:    str,
    db:        AsyncSession
):
    try:
        res = await db.execute(text("""
            SELECT
                d.id, d.tipo_doc, d.cod_doc,
                d.clave_acceso, d.numero_doc, d.secuencial,
                d.fecha_emision, d.estado_sri, d.estado_cobro,
                d.importe_total, d.datos, d.mensajes_sri,
                d.xml_path, d.pdf_path,
                d.forma_pago_cobro, d.numero_comprobante_pago, d.fecha_pago,
                est.codigo AS estab_codigo,
                pe.codigo  AS pto_emi_codigo,
                c.id       AS cliente_uid,
                c.tipo_identificacion_sri,
                c.identificacion, c.razon_social,
                c.direccion, c.email, c.telefono
            FROM documentos_emitidos d
            LEFT JOIN clientes_emisor c    ON d.cliente_id          = c.id
            LEFT JOIN puntos_emision pe    ON d.punto_emision_id    = pe.id
            LEFT JOIN establecimientos est ON pe.establecimiento_id = est.id
            WHERE d.id = :did AND d.emisor_id = :eid
        """), {"did": doc_id, "eid": emisor_id})

        doc = res.fetchone()
        if not doc:
            raise HTTPException(status_code=404, detail="Documento no encontrado.")

        row      = dict(doc._mapping)
        datos    = row.get("datos") or {}
        info_fac = datos.get("infoFactura") or datos.get("infoNotaCredito") or datos.get("infoRetencion") or {}

        info_adicional_raw = datos.get("infoAdicional", {}).get("campoAdicional", [])
        if isinstance(info_adicional_raw, dict):
            info_adicional_raw = [info_adicional_raw]
        info_adicional = [
            {"nombre": i.get("@nombre", ""), "valor": i.get("#text", "")}
            for i in info_adicional_raw if isinstance(i, dict)
        ]

        # Comprador desde JSONB o legacy
        razon  = (info_fac.get("razonSocialComprador")
                  or datos.get("legacy_razon_comprador")
                  or row.get("razon_social") or "")
        id_com = (info_fac.get("identificacionComprador")
                  or datos.get("legacy_id_comprador")
                  or row.get("identificacion") or "")
        email  = (datos.get("legacy_email_comprador")
                  or row.get("email") or "")

        return {
            "ok": True,
            "documento": {
                "id":            str(row["id"]),
                "tipo_doc":      row["tipo_doc"],
                "numero_doc":    row["numero_doc"],
                "secuencial":    row["secuencial"],
                "clave_acceso":  row["clave_acceso"],
                "fecha_emision": row["fecha_emision"].strftime("%Y-%m-%d") if row["fecha_emision"] else None,
                "estado_sri":    row["estado_sri"],
                "estado_cobro":  row["estado_cobro"],
                "forma_pago_cobro":        row["forma_pago_cobro"],
                "numero_comprobante_pago": row["numero_comprobante_pago"],
                "fecha_pago":              str(row["fecha_pago"]) if row["fecha_pago"] else None,
                "totales": {
                    "importe_total":   float(row["importe_total"] or 0),
                    "total_descuento": float(info_fac.get("totalDescuento") or 0),
                },
                "archivos": {
                    "xml": row["xml_path"],
                    "pdf": row["pdf_path"],
                },
                "mensajes_sri":  row["mensajes_sri"],
                "detalles":      datos.get("detalles", {}).get("detalle", []),
                "pagos":         info_fac.get("pagos", {}).get("pago", []),
                "impuestos":     datos.get("impuestos", {}).get("impuesto", []),
                "info_adicional": info_adicional,
            },
            "cliente": {
                "uid":           str(row["cliente_uid"]) if row["cliente_uid"] else None,
                "identificacion": id_com,
                "razon_social":  razon,
                "direccion":     row.get("direccion"),
                "email":         email,
                "telefono":      row.get("telefono"),
            }
        }

    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"[Dashboard] ❌ Error detalle: {e}")
        raise HTTPException(status_code=500, detail="Error interno.")