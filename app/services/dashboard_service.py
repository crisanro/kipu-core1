from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date, datetime
import pytz
import traceback

async def obtener_dashboard_core(
    emisor_id: int | None, 
    email_usuario: str, 
    fecha_inicio: date, 
    fecha_fin: date, 
    db: AsyncSession
):
    try:
        # ─────────────────────────────────────────────────────────────
        # QUERY 1: Todo el "header" — emisor + infra + api_keys
        # Sin filtro de fechas — estos datos no cambian por período
        # ─────────────────────────────────────────────────────────────
        query_header = text("""
            SELECT 
                e.ruc, e.p12_path, e.p12_expiration, e.ambiente,
                c.balance_emision AS balance, 
                p.whatsapp_number, 
                e.id AS emisor_db_id,
                (SELECT COUNT(*) FROM establecimientos WHERE emisor_id = e.id) AS total_estab,
                (SELECT COUNT(*) FROM puntos_emision   WHERE emisor_id = e.id) AS total_puntos,
                (SELECT COUNT(*) FROM api_keys         WHERE emisor_id = e.id AND revoked = false) AS total_keys
            FROM profiles p
            LEFT JOIN emisores e     ON p.emisor_id  = e.id
            LEFT JOIN user_credits c ON c.emisor_id  = e.id
            WHERE LOWER(p.email) = LOWER(:email)
        """)
        res_header = await db.execute(query_header, {"email": email_usuario})
        row_header = res_header.mappings().fetchone()

        if not row_header:
            data_header = {
                "ruc": None, "p12_expiration": None, "ambiente": None,
                "p12_path": None, "balance": 0, "whatsapp_number": None,
                "emisor_db_id": None, "total_estab": 0, "total_puntos": 0, "total_keys": 0
            }
        else:
            data_header = dict(row_header)

        current_emisor_id = emisor_id or data_header.get("emisor_db_id")

        # ─────────────────────────────────────────────────────────────
        # QUERY 2: Facturas del período — resumen se calcula en Python
        # El frontend controla fecha_inicio y fecha_fin libremente
        # ─────────────────────────────────────────────────────────────
        facturas_map = []
        resumen = {
            "total_facturas": 0, "subtotal_iva": 0.0, "subtotal_0": 0.0,
            "valor_iva": 0.0, "importe_total": 0.0
        }

        if current_emisor_id:
            query_facturas = text("""
                SELECT 
                    f.id, f.clave_acceso, f.secuencial, f.estado,
                    f.identificacion_comprador, f.razon_social_comprador,
                    f.subtotal_iva, f.subtotal_0, f.valor_iva, f.importe_total,
                    f.fecha_emision,
                    e.codigo AS estab,
                    p.codigo AS punto
                FROM invoices_emitidas f
                JOIN puntos_emision  p ON f.punto_emision_id  = p.id
                JOIN establecimientos e ON p.establecimiento_id = e.id
                WHERE f.emisor_id    = :eid
                  AND f.fecha_emision BETWEEN :fini AND :ffin
                ORDER BY f.fecha_emision DESC, f.created_at DESC
                LIMIT 100
            """)
            res_facturas = await db.execute(query_facturas, {
                "eid":  current_emisor_id,
                "fini": fecha_inicio,
                "ffin": fecha_fin
            })

            subtotal_iva = subtotal_0 = valor_iva = importe_total = 0.0
            total_autorizadas = 0

            for f in res_facturas.mappings():
                facturas_map.append({
                    "id":            str(f["id"]),
                    "clave_acceso":  f["clave_acceso"],
                    "numero":        f"{f['estab']}-{f['punto']}-{f['secuencial']}",
                    "cliente_nombre": f["razon_social_comprador"],
                    "cliente_id":    f["identificacion_comprador"],
                    "subtotal_15":   float(f["subtotal_iva"]),
                    "subtotal_0":    float(f["subtotal_0"]),
                    "iva":           float(f["valor_iva"]),
                    "total":         float(f["importe_total"]),
                    "estado":        f["estado"],
                    "fecha":         f["fecha_emision"].isoformat() if isinstance(f["fecha_emision"], (date, datetime)) else str(f["fecha_emision"])
                })
                # Resumen solo con AUTORIZADAS
                if f["estado"] == "AUTORIZADO":
                    subtotal_iva      += float(f["subtotal_iva"])
                    subtotal_0        += float(f["subtotal_0"])
                    valor_iva         += float(f["valor_iva"])
                    importe_total     += float(f["importe_total"])
                    total_autorizadas += 1

            resumen = {
                "total_facturas": total_autorizadas,
                "subtotal_iva":   round(subtotal_iva,  2),
                "subtotal_0":     round(subtotal_0,    2),
                "valor_iva":      round(valor_iva,     2),
                "importe_total":  round(importe_total, 2),
            }

        # ─────────────────────────────────────────────────────────────
        # Lógica de firma — sin query extra, datos ya están en header
        # ─────────────────────────────────────────────────────────────
        tz  = pytz.timezone('America/Guayaquil')
        hoy = datetime.now(tz).date()

        expiracion = data_header.get("p12_expiration")
        if isinstance(expiracion, datetime):
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
                    "ruc":                          bool(data_header.get("ruc")),
                    "ambiente_produccion":          data_header.get("ambiente") == 2,
                    "firma_configurada":            bool(data_header.get("p12_path")),
                    "firma_vigente":                firma_vigente,
                    "firma_alerta":                 firma_alerta,
                    "establecimientos_configurados": int(data_header.get("total_estab", 0)) > 0,
                    "puntos_emision_configurados":  int(data_header.get("total_puntos", 0)) > 0,
                    "creditos_disponibles":         data_header.get("balance") or 0,
                    "usuario_nuevo":                not current_emisor_id,
                    "tiene_api_key":                int(data_header.get("total_keys", 0)) > 0,
                    "whatsapp_vinculado":           bool(data_header.get("whatsapp_number")),
                    "whatsapp_numero":              data_header.get("whatsapp_number")
                },
                "resumen":  resumen,
                "facturas": facturas_map,
                "periodo": {
                    "desde": fecha_inicio.isoformat(),
                    "hasta": fecha_fin.isoformat()
                }
            }
        }

    except Exception as e:
        traceback.print_exc()
        return {"ok": False, "error": f"Error interno: {str(e)}"}

async def consultar_detalle_factura_core(emisor_id: int, factura_id: str, db: AsyncSession):
    try:
        # AJUSTE: Tabla 'invoices_emitidas'
        query = text("""
            SELECT 
                i.id AS factura_id,
                est.codigo AS estab_codigo,
                pe.codigo AS pto_emi_codigo,
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
                COALESCE(c.razon_social, i.razon_social_comprador) AS razon_social_comprador,
                c.direccion AS direccion_comprador,
                COALESCE(c.email, i.email_comprador) AS email_comprador,
                c.telefono AS telefono_comprador
            FROM invoices_emitidas i
            LEFT JOIN clientes_emisor c ON i.cliente_emisor_id = c.id
            LEFT JOIN puntos_emision pe ON i.punto_emision_id = pe.id
            LEFT JOIN establecimientos est ON pe.establecimiento_id = est.id
            WHERE i.id = :fid AND i.emisor_id = :eid
        """)
        
        res = await db.execute(query, {"fid": factura_id, "eid": emisor_id})
        factura = res.fetchone()

        if not factura:
            raise HTTPException(status_code=404, detail="Factura no encontrada.")

        row_dict = dict(factura._mapping)
        
        # Limpieza de info adicional
        # AJUSTE: Añadimos validación para que no rompa si 'datos_factura' es None o no tiene la llave
        datos = row_dict.get("datos_factura") or {}
        info_raw = datos.get("infoAdicional", {}).get("campoAdicional", [])
        
        if isinstance(info_raw, dict):
            info_raw = [info_raw]
            
        info_limpia = [
            {"nombre": item.get("@nombre", ""), "valor": item.get("#text", "")} 
            for item in info_raw if isinstance(item, dict)
        ]
        
        return {
            "ok": True,
            "factura": {
                "id": str(row_dict["factura_id"]),
                "numero_completo": f"{row_dict['estab_codigo'] or '000'}-{row_dict['pto_emi_codigo'] or '000'}-{row_dict['secuencial']}",       
                "secuencial": row_dict["secuencial"],     
                "clave_acceso": row_dict["clave_acceso"],
                "fecha_emision": row_dict["fecha_emision"].strftime('%Y-%m-%d') if row_dict["fecha_emision"] else None,
                "estado": row_dict["estado"],
                "totales": {
                    "importe_total": float(row_dict["importe_total"] or 0),
                    "subtotal_iva": float(row_dict["subtotal_iva"] or 0),
                    "subtotal_0": float(row_dict["subtotal_0"] or 0),
                    "valor_iva": float(row_dict["valor_iva"] or 0)
                },
                "archivos": {
                    "xml": row_dict["xml_path"],
                    "pdf": row_dict["pdf_path"]
                },
                "mensajes_sri": row_dict["mensajes_sri"],
                "detalles": datos.get("detalles", {}).get("detalle", []),
                "pagos": datos.get("infoFactura", {}).get("pagos", {}).get("pago", []),
                "info_adicional": info_limpia 
            },
            "cliente": {
                "uid": str(row_dict["cliente_uid"]) if row_dict["cliente_uid"] else None,
                "identificacion": row_dict["identificacion_comprador"],
                "razon_social": row_dict["razon_social_comprador"],
                "email": row_dict["email_comprador"]
            }
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail="Error interno.")