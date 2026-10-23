# app/services/documentos/persistencia.py
#
# Bloque 5 — Persistir documento + movimientos de stock.

import json
import asyncio
from datetime import date
from decimal import Decimal
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.storage_service import upload_file
from app.services import stock_service
from app.services.notification_service import encolar_notificacion
from .helpers import carpeta_por_tipo


async def persistir(
    tipo_doc, cod_doc, xml_firmado_str, xml_obj, xml_root,
    calculos, emisor, punto_emision, cliente_final, cliente_id,
    secuencial, clave_acceso, importe_total, ahora_ec,
    api_key_id, acceso, data,
    doc_origen_emitido, doc_origen_recibido,
    es_sandbox: bool = False, created_by=None,
    db: AsyncSession = None,
) -> str:
    """Inserta el documento y sus movimientos de stock. NO encola ni hace commit."""
    carpeta  = carpeta_por_tipo(tipo_doc)
    prefijo  = "sandbox/" if es_sandbox else ""
    xml_path = f"{emisor.ruc}/{prefijo}{carpeta}/{clave_acceso}.xml"

    # asyncio.to_thread() evita bloquear el event loop en I/O síncrono
    await asyncio.to_thread(
        upload_file, xml_path, xml_firmado_str.encode("utf-8"), "text/xml"
    )

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
            estado_cobro, forma_pago_cobro,
            numero_comprobante_pago, fecha_pago,
            credito_estado,
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
            :estado_cobro, :forma_pago_cobro,
            :num_comp_pago, :fecha_pago_cobro,
            :credito_estado,
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
        "estado_cobro":           data.get("estado_cobro", "PENDIENTE"),
        "forma_pago_cobro":       data.get("forma_pago_cobro"),
        "num_comp_pago":          data.get("numero_comprobante_pago"),
        "fecha_pago_cobro":       date.fromisoformat(data["fecha_pago"]) if data.get("fecha_pago") else None,
        "credito_estado":         "COBRADO" if acceso["descontar_credito"] else None,
    })
    doc_id = str(res.scalar())

    # ── Inventario: FAC resta, LIQ suma, sandbox no mueve nada ────────────────
    cruces = await stock_service.aplicar_emision(
        db, doc_id=doc_id, emisor_id=emisor.id, tipo_doc=tipo_doc,
        datos=datos_json, es_sandbox=es_sandbox,
    )
    for item in cruces:
        encolar_notificacion(
            db         = db,
            emisor_id  = emisor.id,
            tipo       = "SISTEMA",
            titulo     = f"⚠️ Stock bajo: {item['descripcion']}",
            mensaje    = f"Quedan {item['stock']} unidades. Stock mínimo configurado: {item['stock_minimo']}.",
            referencia = f"/productos/{item['id']}",
        )
    if cruces or tipo_doc in ("FAC", "LIQ"):
        try:
            from app.core.cache import cache_clear_prefix
            await cache_clear_prefix(f"productos:{emisor.id}:")
        except Exception as e:
            print(f"[Stock] ⚠️ No se limpió la caché de productos: {e}")

    if tipo_doc in ("FAC", "LIQ") and data.get("items"):
        await _guardar_items_catalogo(data["items"], emisor.id, db)

    return doc_id


async def _guardar_items_catalogo(items: list, emisor_id: int, db: AsyncSession):
    """Guarda en catalogo_items los ítems marcados con guardar_catalogo=True."""
    try:
        guardados = 0
        for item in items:
            if not item.get("guardar_catalogo"):
                continue
            codigo = (item.get("codigo") or "").strip()
            if not codigo:
                continue

            res = await db.execute(text("""
                SELECT id FROM catalogo_items
                WHERE emisor_id = :eid AND codigo = :cod
            """), {"eid": emisor_id, "cod": codigo})
            if res.fetchone():
                continue

            await db.execute(text("""
                INSERT INTO catalogo_items (emisor_id, codigo, descripcion, precio, tipo_iva, unidad)
                VALUES (:eid, :cod, :desc, :precio, :iva, :unidad)
            """), {
                "eid":    emisor_id,
                "cod":    codigo,
                "desc":   item.get("descripcion", ""),
                "precio": item.get("precio_unitario", item.get("precio", 0)),
                "iva":    str(item.get("tipo_iva", "15")),
                "unidad": item.get("unidad_medida", item.get("unidad", "UNIDAD")),
            })
            guardados += 1

        if guardados > 0:
            from app.core.cache import cache_clear_prefix
            await cache_clear_prefix(f"productos:{emisor_id}:")
            print(f"[Catálogo] ✅ {guardados} ítem(s) guardado(s) en catálogo")
    except Exception as e:
        print(f"[Catálogo] ⚠️ Error guardando ítems: {e}")