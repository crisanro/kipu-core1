from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date, datetime, timedelta
import pytz


async def obtener_dashboard_core(
    emisor_id: int | None, 
    email_usuario: str, 
    fecha_inicio: date, 
    fecha_fin: date, 
    db: AsyncSession
):
    try:
        # 1. Perfil y Emisor (Siempre se ejecuta)
        query_emisor = text("""
            SELECT e.ruc, e.p12_path, e.p12_expiration, e.ambiente, c.balance, p.whatsapp_number 
            FROM profiles p
            LEFT JOIN emisores e ON p.emisor_id = e.id 
            LEFT JOIN user_credits c ON c.emisor_id = e.id 
            WHERE LOWER(p.email) = LOWER(:email)
        """)
        res_emisor = await db.execute(query_emisor, {"email": email_usuario})
        # Usamos .mappings() para acceder por nombre de columna fácilmente
        row_basic = res_emisor.mappings().fetchone()

        if not row_basic:
            data_basic = {
                "ruc": None, "p12_expiration": None, "ambiente": None, 
                "p12_path": None, "balance": 0, "whatsapp_number": None
            }
        else:
            data_basic = dict(row_basic)

        # Variables por defecto
        health_stats = {"total_estab": 0, "total_puntos": 0}
        resumen = {
            "total_facturas": 0, "subtotal_iva": 0.0, "subtotal_0": 0.0, 
            "valor_iva": 0.0, "importe_total": 0.0
        }
        facturas_map = []
        total_keys = 0

        # 2. Ejecutamos el resto SOLO si ya completó el onboarding
        if emisor_id:
            # Infraestructura
            query_infra = text("""
                SELECT 
                    (SELECT COUNT(*) FROM establecimientos WHERE emisor_id = :eid) as total_estab,
                    (SELECT COUNT(*) FROM puntos_emision p 
                     JOIN establecimientos e ON p.establecimiento_id = e.id WHERE e.emisor_id = :eid) as total_puntos
            """)
            res_infra = await db.execute(query_infra, {"eid": emisor_id})
            health_stats = dict(res_infra.mappings().fetchone())

            # Resumen financiero
            query_resumen = text("""
                SELECT COUNT(id) as total_facturas, 
                       COALESCE(SUM(subtotal_iva), 0) as subtotal_iva,
                       COALESCE(SUM(subtotal_0), 0) as subtotal_0, 
                       COALESCE(SUM(valor_iva), 0) as valor_iva,
                       COALESCE(SUM(importe_total), 0) as importe_total
                FROM invoices 
                WHERE emisor_id = :eid AND fecha_emision BETWEEN :fini AND :ffin
            """)
            res_resumen = await db.execute(query_resumen, {"eid": emisor_id, "fini": fecha_inicio, "ffin": fecha_fin})
            resumen = dict(res_resumen.mappings().fetchone())

            # Listado de facturas (JOIN con establecimientos y puntos)
            query_facturas = text("""
                SELECT f.id, f.clave_acceso, e.codigo as estab, p.codigo as punto, f.secuencial, f.estado, 
                       f.identificacion_comprador, f.razon_social_comprador, f.subtotal_iva,
                       f.subtotal_0, f.valor_iva, f.importe_total, f.fecha_emision
                FROM invoices f
                JOIN puntos_emision p ON f.punto_emision_id = p.id
                JOIN establecimientos e ON p.establecimiento_id = e.id
                WHERE f.emisor_id = :eid AND f.fecha_emision BETWEEN :fini AND :ffin
                ORDER BY f.created_at DESC LIMIT 50
            """)
            res_facturas = await db.execute(query_facturas, {"eid": emisor_id, "fini": fecha_inicio, "ffin": fecha_fin})
            
            # Mapeo inmediato de facturas
            for f in res_facturas.mappings():
                facturas_map.append({
                    "id": str(f["id"]),
                    "clave_acceso": f["clave_acceso"],
                    "numero": f"{f['estab']}-{f['punto']}-{f['secuencial']}",
                    "cliente_nombre": f["razon_social_comprador"],
                    "cliente_id": f["identificacion_comprador"],
                    "subtotal_15": float(f["subtotal_iva"]),
                    "subtotal_0": float(f["subtotal_0"]),
                    "iva": float(f["valor_iva"]),
                    "total": float(f["importe_total"]),
                    "estado": f["estado"],
                    "fecha": f["fecha_emision"].isoformat() if isinstance(f["fecha_emision"], (date, datetime)) else str(f["fecha_emision"])
                })

            # API Keys
            query_keys = text("SELECT COUNT(*) FROM api_keys WHERE emisor_id = :eid AND revoked = false")
            res_keys = await db.execute(query_keys, {"eid": emisor_id})
            total_keys = res_keys.scalar() or 0

        # --- Lógica de validación de firma ---
        tz = pytz.timezone('America/Guayaquil')
        # Usamos date para comparar con p12_expiration si es tipo DATE en Postgres
        hoy = datetime.now(tz).date() 
        
        expiracion = data_basic.get("p12_expiration")
        # Si la DB devuelve datetime, convertimos a date para comparar manzanas con manzanas
        if isinstance(expiracion, datetime):
            expiracion = expiracion.date()

        firma_vigente = False
        firma_alerta = None if emisor_id else "Configuración inicial pendiente"

        if expiracion:
            firma_vigente = expiracion > hoy
            dias_restantes = (expiracion - hoy).days

            if dias_restantes <= 0:
                firma_alerta = "Firma caducada"
                firma_vigente = False # Forzamos por seguridad
            elif dias_restantes <= 30:
                firma_alerta = f"Firma próxima a caducar ({dias_restantes} días)"

        return {
            "ok": True,
            "data": {
                "health": {
                    "ruc": bool(data_basic.get("ruc")),
                    "ambiente_produccion": data_basic.get("ambiente") == 2,
                    "firma_configurada": bool(data_basic.get("p12_path")),
                    "firma_vigente": firma_vigente,
                    "firma_alerta": firma_alerta,
                    "establecimientos_configurados": int(health_stats["total_estab"]) > 0,
                    "puntos_emision_configurados": int(health_stats["total_puntos"]) > 0,
                    "creditos_disponibles": data_basic.get("balance") or 0,
                    "usuario_nuevo": not emisor_id,
                    "tiene_api_key": total_keys > 0,
                    "whatsapp_vinculado": bool(data_basic.get("whatsapp_number")),
                    "whatsapp_numero": data_basic.get("whatsapp_number")
                },
                "resumen": {
                    "total_facturas": int(resumen["total_facturas"]),
                    "subtotal_iva": float(resumen["subtotal_iva"]),
                    "subtotal_0": float(resumen["subtotal_0"]),
                    "valor_iva": float(resumen["valor_iva"]),
                    "importe_total": float(resumen["importe_total"])
                },
                "facturas": facturas_map
            }
        }

    except Exception as e:
        # Importante: imprimir el error completo para debuggear
        import traceback
        traceback.print_exc()
        return {"ok": False, "error": f"Error interno: {str(e)}"}
    

async def consultar_detalle_factura_core(emisor_id: int, factura_id: str, db: AsyncSession):
    try:
        # Añadimos los JOIN para establecimientos y puntos de emisión
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
                
                -- Datos del cliente
                c.id AS cliente_uid,
                c.tipo_identificacion_sri,
                COALESCE(c.identificacion, i.identificacion_comprador) AS identificacion_comprador,
                COALESCE(c.razon_social, i.razon_social_comprador) AS razon_social_comprador,
                c.direccion AS direccion_comprador,
                COALESCE(c.email, i.email_comprador) AS email_comprador,
                c.telefono AS telefono_comprador
                
            FROM invoices i
            LEFT JOIN clientes_emisor c ON i.cliente_emisor_id = c.id
            LEFT JOIN puntos_emision pe ON i.punto_emision_id = pe.id
            LEFT JOIN establecimientos est ON pe.establecimiento_id = est.id
            WHERE i.id = :fid AND i.emisor_id = :eid
        """)
        
        res = await db.execute(query, {"fid": factura_id, "eid": emisor_id})
        factura = res.fetchone()

        if not factura:
            raise HTTPException(status_code=404, detail="Factura no encontrada o no pertenece a este emisor.")

        row_dict = dict(factura._mapping)
        
        # Armamos el número completo (ej: 001-001-000000123)
        estab = row_dict["estab_codigo"] or "000"
        pto_emi = row_dict["pto_emi_codigo"] or "000"
        numero_completo = f"{estab}-{pto_emi}-{row_dict['secuencial']}"
        
        # ==========================================
        # 🧹 LIMPIEZA DEL FANTASMA DEL XML
        # ==========================================
        info_raw = row_dict["datos_factura"].get("infoAdicional", {}).get("campoAdicional", [])
        
        # Si el XMLdict lo convirtió en un objeto en vez de lista (pasa cuando hay 1 solo item), lo forzamos a lista
        if isinstance(info_raw, dict):
            info_raw = [info_raw]
            
        # Transformamos las llaves feas a algo limpio para el frontend
        info_limpia = [
            {"nombre": item.get("@nombre", ""), "valor": item.get("#text", "")} 
            for item in info_raw if isinstance(item, dict)
        ]
        # ==========================================
        
        return {
            "ok": True,
            "factura": {
                "id": str(row_dict["factura_id"]),
                "numero_completo": numero_completo,       
                "secuencial": row_dict["secuencial"],     
                "clave_acceso": row_dict["clave_acceso"],
                "fecha_emision": row_dict["fecha_emision"].strftime('%Y-%m-%d') if row_dict["fecha_emision"] else None,
                "estado": row_dict["estado"],
                "totales": {
                    "importe_total": float(row_dict["importe_total"]),
                    "subtotal_iva": float(row_dict["subtotal_iva"] or 0),
                    "subtotal_0": float(row_dict["subtotal_0"] or 0),
                    "valor_iva": float(row_dict["valor_iva"] or 0)
                },
                "archivos": {
                    "xml": row_dict["xml_path"],
                    "pdf": row_dict["pdf_path"]
                },
                "mensajes_sri": row_dict["mensajes_sri"],
                
                # Extracción de JSON
                "detalles": row_dict["datos_factura"].get("detalles", {}).get("detalle", []),
                "pagos": row_dict["datos_factura"].get("infoFactura", {}).get("pagos", {}).get("pago", []),
                
                # ¡Aquí inyectamos la lista ya limpiecita!
                "info_adicional": info_limpia 
            },
            "cliente": {
                "uid": str(row_dict["cliente_uid"]) if row_dict["cliente_uid"] else None,
                "tipo_identificacion_sri": row_dict["tipo_identificacion_sri"],
                "identificacion": row_dict["identificacion_comprador"],
                "razon_social": row_dict["razon_social_comprador"],
                "direccion": row_dict["direccion_comprador"],
                "email": row_dict["email_comprador"],
                "telefono": row_dict["telefono_comprador"]
            }
        }

    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error consultando detalle de factura: {e}")
        raise HTTPException(status_code=500, detail="Error interno al obtener los detalles de la factura.")