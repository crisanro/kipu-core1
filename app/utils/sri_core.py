# app/utils/sri_core.py
#
# Funciones compartidas para emisión de comprobantes electrónicos SRI Ecuador.
# Usadas por factura_service.py, nc_service.py, nd_service.py
import json
import base64
import httpx
from decimal import Decimal
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from app.schemas.cliente import ClienteCreate
from app.services.cliente_service import crear_cliente_core
from app.utils.calculadora import calcular_totales_e_impuestos
from app.utils.crypto import decrypt_password
from app.services.storage_service import upload_file, download_file
from app.core.config import settings
from app.core.cache import get_redis
from app.api.v1.app.productos import invalidar_cache_productos

NODE_SIGNER_URL = f"{settings.NODE_SIGNER_URL}/api/firmar"


# ── Cliente ────────────────────────────────────────────────────────────────────

async def resolver_cliente(factura_data: dict, emisor_id: int, db: AsyncSession) -> tuple[dict, any]:
    """
    Resuelve la identidad del cliente desde cliente_id, objeto cliente, o consumidor final.
    Retorna (cliente_final, cliente_emisor_id).
    """
    cliente_id    = factura_data.get("cliente_id")
    cliente_obj   = factura_data.get("cliente")
    cliente_emisor_id = None

    cliente_final = {
        "identificacion": None,
        "razon_social":   None,
        "email":          None,
        "direccion":      "S/N",
        "telefono":       "",
        "tipo_id":        "05"
    }

    # ── Consumidor Final ───────────────────────────────────────────────────────
    if cliente_id and str(cliente_id).strip().lower() == "consumidor_final":
        return {
            "identificacion": "9999999999999",
            "razon_social":   "CONSUMIDOR FINAL",
            "email":          None,
            "direccion":      "S/N",
            "telefono":       "",
            "tipo_id":        "07"
        }, None

    # ── Por UUID ───────────────────────────────────────────────────────────────
    if cliente_id and str(cliente_id).strip():
        res = await db.execute(text("""
            SELECT id, tipo_identificacion_sri, identificacion, razon_social,
                   direccion, email, telefono
            FROM clientes_emisor
            WHERE id = :cid AND emisor_id = :eid
        """), {"cid": cliente_id, "eid": emisor_id})
        row = res.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="El 'cliente_id' proporcionado no existe.")
        return {
            "identificacion": row.identificacion,
            "razon_social":   row.razon_social,
            "email":          row.email,
            "direccion":      row.direccion,
            "telefono":       row.telefono,
            "tipo_id":        row.tipo_identificacion_sri,
        }, row.id

    # ── Por objeto cliente ─────────────────────────────────────────────────────
    if cliente_obj:
        identificacion = cliente_obj.get("identificacion")
        tipo_id        = cliente_obj.get("tipo_id") or cliente_obj.get("tipoId") or "05"
        razon_social   = cliente_obj.get("nombre") or cliente_obj.get("razonSocial")
        email          = cliente_obj.get("email")
        direccion      = cliente_obj.get("direccion", "S/N")
        telefono       = cliente_obj.get("telefono", "")

        cliente_final.update({
            "identificacion": identificacion,
            "razon_social":   razon_social,
            "email":          email,
            "direccion":      direccion,
            "telefono":       telefono,
            "tipo_id":        tipo_id,
        })

        # Buscar o crear en clientes_emisor
        if tipo_id in ("04", "05") and identificacion:
            try:
                res = await db.execute(text("""
                    SELECT id, razon_social, email, direccion, telefono, tipo_identificacion_sri
                    FROM clientes_emisor
                    WHERE emisor_id = :eid AND identificacion = :id
                """), {"eid": emisor_id, "id": identificacion})
                existente = res.fetchone()

                if existente:
                    cliente_emisor_id             = existente.id
                    cliente_final["razon_social"] = existente.razon_social
                    cliente_final["email"]        = existente.email or email
                    cliente_final["direccion"]    = existente.direccion or direccion
                    cliente_final["telefono"]     = existente.telefono or telefono
                    cliente_final["tipo_id"]      = existente.tipo_identificacion_sri
                else:
                    nuevo = ClienteCreate(
                        tipo_identificacion_sri=tipo_id,
                        identificacion=identificacion,
                        razon_social=razon_social,
                        direccion=direccion,
                        email=email or "",
                        telefono=telefono or ""
                    )
                    res_creacion      = await crear_cliente_core(emisor_id, nuevo, db, lanzar_error_si_existe=False)
                    cliente_emisor_id = res_creacion.get("uid")
            except Exception as e:
                print(f"⚠️ Cliente no persistido, modo invitado: {e}")

        return cliente_final, cliente_emisor_id

    raise HTTPException(
        status_code=400,
        detail="Debe proporcionar 'cliente_id' o un objeto 'cliente' completo."
    )


# ── Items ──────────────────────────────────────────────────────────────────────

async def completar_items_catalogo(items: list, emisor_id: int, db: AsyncSession) -> list:
    """
    Completa los campos faltantes de cada item consultando catalogo_items por código.
    Si el item no tiene código o no existe en catálogo, usa los datos que trae.
    Si el item tiene código y existe → completa descripcion, tipo_iva, unidad_medida.
    Si el item trae precio_unitario lo respeta, si no usa el del catálogo.
    """
    items_completos = []

    for item in items:
        codigo = item.get("codigo") or item.get("codigoPrincipal")

        if codigo and codigo != "S/C":
            res = await db.execute(text("""
                SELECT descripcion, precio, tipo_iva, unidad
                FROM catalogo_items
                WHERE emisor_id = :eid AND codigo = :cod AND activo = true
            """), {"eid": emisor_id, "cod": codigo})
            producto = res.fetchone()

            if producto:
                item_completo = {
                    "codigo":          codigo,
                    "descripcion":     item.get("descripcion") or producto.descripcion,
                    "cantidad":        item.get("cantidad", 1),
                    "precio_unitario": item.get("precio_unitario") if item.get("precio_unitario") is not None else float(producto.precio),
                    "descuento":       item.get("descuento", 0),
                    "tipo_iva":        item.get("tipo_iva") or producto.tipo_iva,
                    "unidad_medida":   item.get("unidad_medida") or producto.unidad,
                }
                items_completos.append(item_completo)
                continue

        # Sin código o no encontrado en catálogo — usar tal cual
        items_completos.append({
            "codigo":          codigo or "S/C",
            "descripcion":     item.get("descripcion", "PRODUCTO SIN NOMBRE"),
            "cantidad":        item.get("cantidad", 1),
            "precio_unitario": item.get("precio_unitario", 0),
            "descuento":       item.get("descuento", 0),
            "tipo_iva":        item.get("tipo_iva", "15"),
            "unidad_medida":   item.get("unidad_medida", "UNIDAD"),
        })

    if not items_completos:
        raise HTTPException(status_code=400, detail="La factura debe tener al menos un ítem válido.")

    return items_completos


# ── Pagos ──────────────────────────────────────────────────────────────────────

def resolver_pagos(pagos_raw: list, importe_total: Decimal) -> list:
    """
    Arma el array de pagos para el XML.
    - Si hay un solo pago sin total → recibe el importe completo.
    - Si hay varios pagos con total → valida que sumen correctamente.
    - El último pago sin total recibe el saldo restante.
    """
    if not pagos_raw:
        return [{
            "formaPago":    "01",
            "total":        f"{importe_total:.2f}",
            "plazo":        "0",
            "unidadTiempo": "dias"
        }]

    pagos_xml    = []
    total_cubierto = Decimal("0.00")
    ultimo_sin_total = None

    for i, pago in enumerate(pagos_raw):
        forma   = pago.get("forma_pago") or pago.get("formaPago") or "01"
        total_p = pago.get("total")
        plazo   = str(pago.get("plazo", "0"))
        unidad  = pago.get("unidad_tiempo") or pago.get("unidadTiempo") or "dias"

        if total_p is None:
            # Sin total — candidato para recibir el saldo
            ultimo_sin_total = {"formaPago": forma, "plazo": plazo, "unidadTiempo": unidad}
        else:
            monto = Decimal(str(total_p)).quantize(Decimal("0.01"))
            total_cubierto += monto
            pagos_xml.append({
                "formaPago":    forma,
                "total":        f"{monto:.2f}",
                "plazo":        plazo,
                "unidadTiempo": unidad,
            })

    # Saldo restante → último pago sin total
    saldo = (importe_total - total_cubierto).quantize(Decimal("0.01"))

    if ultimo_sin_total:
        if saldo < Decimal("0.00"):
            raise HTTPException(
                status_code=400,
                detail=f"Los pagos especificados (${total_cubierto:.2f}) superan el importe total (${importe_total:.2f})."
            )
        pagos_xml.append({ "formaPago": ultimo_sin_total["formaPago"], "total": f"{saldo:.2f}", "plazo": ultimo_sin_total["plazo"], "unidadTiempo": ultimo_sin_total["unidadTiempo"], })
    else:
        # Todos los pagos tienen total — validar que sumen
        if total_cubierto != importe_total:
            raise HTTPException(
                status_code=400,
                detail=f"La suma de pagos (${total_cubierto:.2f}) no coincide con el importe total (${importe_total:.2f})."
            )

    return pagos_xml


# ── Campos adicionales ─────────────────────────────────────────────────────────

def construir_campos_adicionales(factura_data: dict) -> list:
    """
    Construye el array de campoAdicional para infoAdicional del XML.
    El campo Proveedor siempre va al final.
    """
    campos = []

    campos_raw = factura_data.get("campos_adicionales") or []
    for campo in campos_raw:
        if campo.get("nombre") and campo.get("valor"):
            campos.append({
                "@nombre": str(campo["nombre"])[:300],
                "#text":   str(campo["valor"])[:300]
            })

    # Proveedor siempre al final
    campos.append({
        "@nombre": "PROVEEDOR_SISTEMA_INFORMATICO",
        "#text":   "1312838392001 (kipu.ec)"
    })

    return campos


# ── Firma ──────────────────────────────────────────────────────────────────────

async def firmar_xml(xml_obj: dict, emisor) -> str:
    """
    Envía el XML al microservicio Node.js para firma XAdES-BES.
    Retorna el XML firmado como string.
    """
    try:
        p12_bytes  = download_file(emisor.p12_path)
        p12_base64 = base64.b64encode(p12_bytes).decode("utf-8")

        async with httpx.AsyncClient() as client:
            res = await client.post(
                NODE_SIGNER_URL,
                json={
                    "xmlObj":    xml_obj,
                    "emisor": {
                        "p12_pass":     decrypt_password(emisor.p12_pass),
                        "ruc":          emisor.ruc,
                        "razon_social": emisor.razon_social,
                        "ambiente":     emisor.ambiente,
                    },
                    "p12Base64": p12_base64,
                },
                timeout=25.0,
            )

        data = res.json()
        if not data.get("ok"):
            raise ValueError(f"Node Error: {data.get('error')}")

        return data["xmlFirmado"]

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Falla técnica en firma: {str(e)}")


# ── Guardar y encolar ──────────────────────────────────────────────────────────

async def guardar_y_encolar(
    xml_firmado_str: str,
    xml_path_rel:    str,
    datos_fac_json:  dict,
    calculos:        dict,
    emisor_id:       int,
    punto_emision:   any,
    cliente_final:   dict,
    cliente_emisor_id: any,
    secuencial:      str,
    clave_acceso:    str,
    ahora_ecuador:   any,
    api_key_id:      any,
    unlimited:       bool,
    origen:          str,
    db:              AsyncSession,
    cod_doc:           str  = "01",   # ← agregar
    doc_referencia_id: str  = None,   # ← agregar
) -> str:
    """
    Guarda el XML en R2, inserta la factura en DB, descuenta crédito y encola.
    Retorna el factura_id.
    """
    try:
        upload_file(xml_path_rel, xml_firmado_str.encode("utf-8"), "text/xml")

        if not unlimited:
            await db.execute(
                text("UPDATE user_credits SET balance_emision = balance_emision - 1 WHERE emisor_id = :eid"),
                {"eid": emisor_id}
            )

        res_insert = await db.execute(text("""
            INSERT INTO invoices_emitidas (
                emisor_id, punto_emision_id, cliente_emisor_id, api_key_id, origen,
                secuencial, fecha_emision, clave_acceso, numero_factura, estado,
                identificacion_comprador, razon_social_comprador, email_comprador,
                importe_total, subtotal_iva, subtotal_0, valor_iva,
                xml_path, datos_factura,
                cod_doc, doc_referencia_id
            ) VALUES (
                :emisor_id, :pto_id, :cliente_emisor_id, :api_key_id, :origen,
                :sec, :fecha, :clave, :num_fac, 'FIRMADO',
                :id_comp, :razon_comp, :email_comp,
                :total, :sub_iva, :sub_0, :val_iva,
                :xml_path, CAST(:datos_fac AS jsonb),
                :cod_doc, :doc_ref_id
            ) RETURNING id
        """), {
            "emisor_id":         emisor_id,
            "pto_id":            punto_emision.punto_id,
            "cliente_emisor_id": cliente_emisor_id,
            "api_key_id":        api_key_id,
            "origen":            origen,
            "sec":               secuencial,
            "fecha":             ahora_ecuador.date(),
            "clave":             clave_acceso,
            "num_fac":           f"{punto_emision.estab_codigo}-{punto_emision.punto_codigo}-{secuencial}",
            "id_comp":           cliente_final["identificacion"],
            "razon_comp":        cliente_final["razon_social"],
            "email_comp":        cliente_final["email"],
            "total":             calculos["totales"]["importeTotal"],
            "sub_iva":           calculos["totales"]["subtotal_iva"],
            "sub_0":             calculos["totales"]["subtotal_0"],
            "val_iva":           calculos["totales"]["totalIva"],
            "xml_path":          xml_path_rel,
            "datos_fac":         json.dumps(datos_fac_json),
            "cod_doc":           cod_doc,            # ← agregar
            "doc_ref_id":        doc_referencia_id,  # ← agregar
        })
        factura_id = res_insert.scalar()
        await db.commit()

        # Descontar stock
        await descontar_stock(datos_fac_json, emisor_id, db)

        # Invalidar cache
        try:
            redis   = await get_redis()
            pattern = f"kipu:cache:*:{emisor_id}:*"
            keys    = await redis.keys(pattern)
            if keys:
                await redis.delete(*keys)
        except Exception as e:
            print(f"⚠️ Cache no invalidado: {e}")

        # Encolar
        redis = await get_redis()
        await redis.lpush("kipu:queue:emision", str(factura_id))

        return str(factura_id)

    except Exception as e:
        await db.rollback()
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ── Stock ──────────────────────────────────────────────────────────────────────

async def descontar_stock(factura_data: dict, emisor_id: int, db: AsyncSession):
    """
    Descuenta stock al firmar. Solo afecta productos con stock > 0 y código válido.
    """
    try:
        detalles = factura_data.get("detalles", {}).get("detalle", [])
        if not isinstance(detalles, list):
            detalles = [detalles]

        for detalle in detalles:
            codigo = detalle.get("codigoPrincipal") or detalle.get("codigoAuxiliar")
            if not codigo or codigo == "S/C":
                continue
            cantidad = float(detalle.get("cantidad", 0))
            await db.execute(text("""
                UPDATE catalogo_items
                SET stock = GREATEST(0, stock - :qty), updated_at = NOW()
                WHERE emisor_id = :eid AND stock > 0 AND codigo = :cod
            """), {"qty": int(cantidad), "eid": emisor_id, "cod": codigo})

        await db.commit()
        await invalidar_cache_productos(emisor_id)

    except Exception as e:
        print(f"[Stock] ⚠️ Error descontando stock: {e}")


async def devolver_stock(factura_id: str, emisor_id: int, db: AsyncSession):
    """
    Devuelve stock si el SRI rechaza o devuelve la factura.
    """
    try:
        res = await db.execute(text("""
            SELECT datos_factura FROM invoices_emitidas WHERE id = :id
        """), {"id": factura_id})
        datos = res.scalar()
        if not datos:
            return

        detalles = datos.get("detalles", {}).get("detalle", [])
        if not isinstance(detalles, list):
            detalles = [detalles]

        for detalle in detalles:
            codigo = detalle.get("codigoPrincipal") or detalle.get("codigoAuxiliar")
            if not codigo or codigo == "S/C":
                continue
            cantidad = float(detalle.get("cantidad", 0))
            await db.execute(text("""
                UPDATE catalogo_items
                SET stock = stock + :qty, updated_at = NOW()
                WHERE emisor_id = :eid AND stock != -1 AND codigo = :cod
            """), {"qty": int(cantidad), "eid": emisor_id, "cod": codigo})

        await db.commit()
        await invalidar_cache_productos(emisor_id)
        print(f"[Stock] ↩️ Stock devuelto para factura {factura_id}")

    except Exception as e:
        print(f"[Stock] ⚠️ Error devolviendo stock: {e}")