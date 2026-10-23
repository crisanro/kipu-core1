# app/services/documentos/origen.py
#
# Bloque 1 — Resolver documento origen (para NC, ND, Retención).

from datetime import datetime
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from .helpers import toArray_py, tarifa_a_codigo_porcentaje


async def cargar_doc_origen_emitido(data: dict, emisor_id: int, tipo_doc: str, db: AsyncSession):
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
            d.tipo_doc, d.cod_doc, d.datos, d.email_comprador,
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
        "email":      doc.email_comprador or datos.get("legacy_email_comprador"),
        "direccion": "S/N",
        "telefono":  "",
        "tipo_id": (
            info.get("tipoIdentificacionComprador") or
            info.get("tipoIdentificacionProveedor") or
            "05"
        ),
    }
    return doc, cliente_final


async def cargar_ret_desde_emitido(data: dict, emisor_id: int, db: AsyncSession):
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


async def cargar_doc_origen_recibido(data: dict, emisor_id: int, db: AsyncSession):
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