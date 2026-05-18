# app/services/dashboard_service.py — OPTIMIZADO con cache en 2 capas
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date, datetime
import calendar
import pytz
import traceback

from app.core.cache import cache_get, cache_set


# ── TTLs específicos del dashboard ────────────────────────────────────────────
TTL_HEADER        = 300   # 5 min  — firma, créditos, estructura (cambian poco)
TTL_MES_ACTUAL    = 120   # 2 min  — mes en curso (facturas nuevas frecuentes)
TTL_MES_PASADO    = 3600  # 1 hora — meses anteriores (inmutables en la práctica)


def _es_mes_actual(año: int, mes: int) -> bool:
    hoy = date.today()
    return año == hoy.year and mes == hoy.month


def _meses_en_rango(fecha_inicio: date, fecha_fin: date) -> list[tuple[int, int]]:
    """Devuelve lista de (año, mes) cubiertos por el rango."""
    meses = []
    current = fecha_inicio.replace(day=1)
    while current <= fecha_fin:
        meses.append((current.year, current.month))
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)
    return meses


async def obtener_dashboard_core(
    emisor_id: int | None,
    email_usuario: str,
    fecha_inicio: date,
    fecha_fin: date,
    db: AsyncSession
):
    try:
        # ═════════════════════════════════════════════════════════════
        # CAPA 1 — HEADER (sin fechas)
        # Firma, créditos, estructura, WS — TTL 5 min
        # ═════════════════════════════════════════════════════════════
        cache_key_header = f"dashboard_header:{emisor_id}"
        data_header = await cache_get(cache_key_header)

        if not data_header:
            query_header = text("""
                SELECT
                    e.ruc, e.p12_path, e.p12_expiration, e.ambiente,
                    c.balance_emision,
                    c.balance_recepcion,                                          -- ← nuevo
                    p.whatsapp_number,
                    e.id AS emisor_db_id,
                    (SELECT COUNT(*) FROM establecimientos WHERE emisor_id = e.id) AS total_estab,
                    (SELECT COUNT(*) FROM puntos_emision   WHERE emisor_id = e.id) AS total_puntos,
                    (SELECT COUNT(*) FROM api_keys         WHERE emisor_id = e.id AND revoked = false) AS total_keys,
                    (SELECT EXISTS(SELECT 1 FROM notificaciones WHERE emisor_id = e.id AND leida = false)) AS tiene_notificaciones  -- ← nuevo
                FROM profiles p
                LEFT JOIN emisores e     ON p.emisor_id = e.id
                LEFT JOIN user_credits c ON c.emisor_id = e.id
                WHERE LOWER(p.email) = LOWER(:email)
            """)
            res_header = await db.execute(query_header, {"email": email_usuario})
            row_header = res_header.mappings().fetchone()

            if not row_header:
                data_header = {
                    "ruc": None, "p12_expiration": None, "ambiente": None,
                    "p12_path": None, "balance_emision": 0, "balance_recepcion": 0,  # ← actualizado
                    "whatsapp_number": None, "emisor_db_id": None,
                    "total_estab": 0, "total_puntos": 0, "total_keys": 0,
                    "tiene_notificaciones": False  # ← nuevo
                }
            else:
                data_header = dict(row_header)
                # Convertir date a string para que sea serializable en Redis
                if isinstance(data_header.get("p12_expiration"), date):
                    data_header["p12_expiration"] = data_header["p12_expiration"].isoformat()

            debe_cachear = (
                bool(data_header.get("whatsapp_number")) or
                data_header.get("ambiente") == 2
            )
            if debe_cachear:
                await cache_set(cache_key_header, data_header, TTL_HEADER)

        current_emisor_id = emisor_id or data_header.get("emisor_db_id")

        # ═════════════════════════════════════════════════════════════
        # CAPA 2 — FACTURAS POR MES
        # Cada mes se cachea independientemente.
        # Meses pasados: TTL 1h | Mes actual: TTL 2 min
        # ═════════════════════════════════════════════════════════════
        todas_las_facturas = []

        if current_emisor_id:
            meses = _meses_en_rango(fecha_inicio, fecha_fin)

            for (año, mes) in meses:
                cache_key_mes = f"dashboard_facturas:{current_emisor_id}:{año}:{mes:02d}"
                facturas_mes  = await cache_get(cache_key_mes)

                if facturas_mes is None:
                    # Traer el mes COMPLETO desde DB
                    primer_dia  = date(año, mes, 1)
                    ultimo_dia  = date(año, mes, calendar.monthrange(año, mes)[1])

                    query_facturas = text("""
                        SELECT
                            f.id, f.clave_acceso, f.secuencial, f.estado,
                            f.identificacion_comprador, f.razon_social_comprador,
                            f.subtotal_iva, f.subtotal_0, f.valor_iva, f.importe_total,
                            f.fecha_emision,
                            est.codigo AS estab,
                            p.codigo   AS punto
                        FROM invoices_emitidas f
                        JOIN puntos_emision   p   ON f.punto_emision_id   = p.id
                        JOIN establecimientos est  ON p.establecimiento_id = est.id
                        WHERE f.emisor_id     = :eid
                          AND f.fecha_emision BETWEEN :fini AND :ffin
                        ORDER BY f.fecha_emision DESC, f.created_at DESC
                        LIMIT 500
                    """)
                    res_facturas = await db.execute(query_facturas, {
                        "eid":  current_emisor_id,
                        "fini": primer_dia,
                        "ffin": ultimo_dia
                    })

                    facturas_mes = []
                    for f in res_facturas.mappings():
                        facturas_mes.append({
                            "id":             str(f["id"]),
                            "clave_acceso":   f["clave_acceso"],
                            "numero":         f"{f['estab']}-{f['punto']}-{f['secuencial']}",
                            "cliente_nombre": f["razon_social_comprador"],
                            "cliente_id":     f["identificacion_comprador"],
                            "subtotal_15":    float(f["subtotal_iva"]),
                            "subtotal_0":     float(f["subtotal_0"]),
                            "iva":            float(f["valor_iva"]),
                            "total":          float(f["importe_total"]),
                            "estado":         f["estado"],
                            # Guardamos como string ISO para serialización Redis
                            "fecha":          f["fecha_emision"].isoformat() if isinstance(f["fecha_emision"], (date, datetime)) else str(f["fecha_emision"])
                        })

                    # Meses pasados duran 1 hora, mes actual solo 2 min
                    ttl = TTL_MES_ACTUAL if _es_mes_actual(año, mes) else TTL_MES_PASADO
                    await cache_set(cache_key_mes, facturas_mes, ttl)

                todas_las_facturas.extend(facturas_mes)

            # ── Filtrar al rango exacto pedido (en Python, sin DB) ────────
            def _parse_fecha(f) -> date:
                v = f["fecha"]
                if isinstance(v, date):
                    return v
                return date.fromisoformat(str(v)[:10])

            todas_las_facturas = [
                f for f in todas_las_facturas
                if fecha_inicio <= _parse_fecha(f) <= fecha_fin
            ]

            # Ordenar por fecha desc y limitar
            todas_las_facturas.sort(key=_parse_fecha, reverse=True)
            todas_las_facturas = todas_las_facturas[:100]

        # ── Calcular resumen en Python sobre las facturas filtradas ───────
        subtotal_iva = subtotal_0 = valor_iva = importe_total = 0.0
        total_autorizadas = 0

        for f in todas_las_facturas:
            if f["estado"] == "AUTORIZADO":
                subtotal_iva      += f["subtotal_15"]
                subtotal_0        += f["subtotal_0"]
                valor_iva         += f["iva"]
                importe_total     += f["total"]
                total_autorizadas += 1

        resumen = {
            "total_facturas": total_autorizadas,
            "subtotal_iva":   round(subtotal_iva,  2),
            "subtotal_0":     round(subtotal_0,    2),
            "valor_iva":      round(valor_iva,     2),
            "importe_total":  round(importe_total, 2),
        }

        # ═════════════════════════════════════════════════════════════
        # LÓGICA DE FIRMA — usa datos del header cacheado
        # ═════════════════════════════════════════════════════════════
        tz  = pytz.timezone('America/Guayaquil')
        hoy = datetime.now(tz).date()

        expiracion = data_header.get("p12_expiration")
        if isinstance(expiracion, str) and expiracion:
            expiracion = date.fromisoformat(expiracion)
        elif isinstance(expiracion, datetime):
            expiracion = expiracion.date()

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

        return {
            "ok": True,
            "data": {
                "health": {
                    "ruc":                           bool(data_header.get("ruc")),
                    "ambiente_produccion":           data_header.get("ambiente") == 2,
                    "firma_configurada":             bool(data_header.get("p12_path")),
                    "firma_vigente":                 firma_vigente,
                    "firma_alerta":                  firma_alerta,
                    "establecimientos_configurados": int(data_header.get("total_estab", 0)) > 0,
                    "puntos_emision_configurados":   int(data_header.get("total_puntos", 0)) > 0,
                    "balance_emision":               data_header.get("balance_emision") or 0,   # ← actualizado
                    "balance_recepcion":             data_header.get("balance_recepcion") or 0, # ← nuevo
                    "usuario_nuevo":                 not current_emisor_id,
                    "tiene_api_key":                 int(data_header.get("total_keys", 0)) > 0,
                    "whatsapp_vinculado":            bool(data_header.get("whatsapp_number")),
                    "whatsapp_numero":               data_header.get("whatsapp_number"),
                    "tiene_notificaciones":          bool(data_header.get("tiene_notificaciones", False)),  # ← nuevo
                },
                "resumen":  resumen,
                "facturas": todas_las_facturas,
                "periodo": {
                    "desde": fecha_inicio.isoformat(),
                    "hasta": fecha_fin.isoformat()
                }
            }
        }

    except Exception as e:
        traceback.print_exc()
        return {"ok": False, "error": f"Error interno: {str(e)}"}


# ═════════════════════════════════════════════════════════════════════════════
# DETALLE DE FACTURA — sin cambios en lógica, ya tiene cache en dashboard.py
# ═════════════════════════════════════════════════════════════════════════════
async def consultar_detalle_factura_core(emisor_id: int, factura_id: str, db: AsyncSession):
    try:
        query = text("""
            SELECT
                i.id AS factura_id,
                est.codigo AS estab_codigo,
                pe.codigo  AS pto_emi_codigo,
                i.secuencial,
                i.clave_acceso,
                i.fecha_emision,
                i.estado,
                i.importe_total,
                i.subtotal_iva,
                i.subtotal_0,
                i.valor_iva,
                i.datos_factura,
                i.mensajes_sri,
                i.xml_path,
                i.pdf_path,
                c.id AS cliente_uid,
                c.tipo_identificacion_sri,
                COALESCE(c.identificacion, i.identificacion_comprador) AS identificacion_comprador,
                COALESCE(c.razon_social,   i.razon_social_comprador)   AS razon_social_comprador,
                c.direccion AS direccion_comprador,
                COALESCE(c.email, i.email_comprador) AS email_comprador,
                c.telefono  AS telefono_comprador
            FROM invoices_emitidas i
            LEFT JOIN clientes_emisor c   ON i.cliente_emisor_id   = c.id
            LEFT JOIN puntos_emision pe   ON i.punto_emision_id    = pe.id
            LEFT JOIN establecimientos est ON pe.establecimiento_id = est.id
            WHERE i.id = :fid AND i.emisor_id = :eid
        """)

        res     = await db.execute(query, {"fid": factura_id, "eid": emisor_id})
        factura = res.fetchone()

        if not factura:
            raise HTTPException(status_code=404, detail="Factura no encontrada.")

        row_dict = dict(factura._mapping)
        datos    = row_dict.get("datos_factura") or {}
        info_raw = datos.get("infoAdicional", {}).get("campoAdicional", [])
        total_descuento = float(datos.get("infoFactura", {}).get("totalDescuento", 0) or 0)

        if isinstance(info_raw, dict):
            info_raw = [info_raw]

        info_limpia = [
            {"nombre": item.get("@nombre", ""), "valor": item.get("#text", "")}
            for item in info_raw if isinstance(item, dict)
        ]

        return {
            "ok": True,
            "factura": {
                "id":             str(row_dict["factura_id"]),
                "numero_completo": f"{row_dict['estab_codigo'] or '000'}-{row_dict['pto_emi_codigo'] or '000'}-{row_dict['secuencial']}",
                "secuencial":     row_dict["secuencial"],
                "clave_acceso":   row_dict["clave_acceso"],
                "fecha_emision":  row_dict["fecha_emision"].strftime('%Y-%m-%d') if row_dict["fecha_emision"] else None,
                "estado":         row_dict["estado"],
                "totales": {
                    "importe_total": float(row_dict["importe_total"] or 0),
                    "subtotal_iva":  float(row_dict["subtotal_iva"]  or 0),
                    "subtotal_0":    float(row_dict["subtotal_0"]    or 0),
                    "valor_iva":     float(row_dict["valor_iva"]     or 0),
                    "total_descuento": total_descuento
                },
                "archivos": {
                    "xml": row_dict["xml_path"],
                    "pdf": row_dict["pdf_path"]
                },
                "mensajes_sri":  row_dict["mensajes_sri"],
                "detalles":      datos.get("detalles", {}).get("detalle", []),
                "pagos":         datos.get("infoFactura", {}).get("pagos", {}).get("pago", []),
                "info_adicional": info_limpia
            },
            "cliente": {
                "uid":                    str(row_dict["cliente_uid"]) if row_dict["cliente_uid"] else None,
                "tipo_identificacion_sri": row_dict["tipo_identificacion_sri"],
                "identificacion":         row_dict["identificacion_comprador"],
                "razon_social":           row_dict["razon_social_comprador"],
                "direccion":              row_dict["direccion_comprador"],
                "email":                  row_dict["email_comprador"],
                "telefono":               row_dict["telefono_comprador"]
            }
        }

    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail="Error interno.")