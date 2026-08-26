# app/utils/sri_core.py
#
# Funciones compartidas para emisión de comprobantes electrónicos SRI Ecuador.
# Usadas por documento_service.py
import json
import base64
import httpx
from decimal import Decimal
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from app.schemas.cliente import ClienteCreate
from app.services.cliente_service import crear_cliente_core
from app.utils.crypto import decrypt_password
from app.services.storage_service import download_file
from app.core.config import settings

NODE_SIGNER_URL = f"{settings.NODE_SIGNER_URL}/api/firmar"


# ── Cliente ────────────────────────────────────────────────────────────────────

import uuid as uuid_lib

# Aliases reconocidos como consumidor final
_CONSUMIDOR_FINAL_ALIASES = {
    "consumidor_final",
    "cliente-final",
    "consumidor-final",
    "9999999999999",
    "cf",
}

async def resolver_cliente(factura_data: dict, emisor_id: int, db: AsyncSession) -> tuple[dict, any]:
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
    if cliente_id and str(cliente_id).strip().lower() in _CONSUMIDOR_FINAL_ALIASES:
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
        # Validar formato UUID antes de ir a la DB
        try:
            uuid_lib.UUID(str(cliente_id))
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"'cliente_id' inválido: '{cliente_id}'. Debe ser un UUID, 'consumidor_final', o usa el objeto 'cliente'."
            )

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
        if tipo_id in ("04", "05", "06", "08") and identificacion:
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

    pagos_xml        = []
    total_cubierto   = Decimal("0.00")
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
        pagos_xml.append({
            "formaPago": ultimo_sin_total["formaPago"],
            "total": f"{saldo:.2f}",
            "plazo": ultimo_sin_total["plazo"],
            "unidadTiempo": ultimo_sin_total["unidadTiempo"],
        })
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