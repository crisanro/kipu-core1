# app/services/stock_service.py
#
# Movimientos de inventario por documento. Cada documento registra EXACTAMENTE
# cuánto movió de cada producto, para que revertir y reaplicar sean exactos.
#
#   FAC  → salida  (resta stock)
#   LIQ  → entrada (suma stock: la liquidación de compra es una COMPRA)
#   Sandbox o NC/ND/RET → no mueven inventario
#
# documentos_emitidos.stock_estado:
#   APLICADO   el movimiento está vigente
#   REVERTIDO  se devolvió (el SRI rechazó el documento)
#   SIN_STOCK  el documento no mueve inventario
#   NULL       documento anterior a este registro (se revierte como lo hacía antes)
#
# Revertir y reaplicar son idempotentes: dependen de stock_estado, no de cuántas
# veces se llamen. Quien llama debe tener el documento bloqueado (FOR UPDATE).

from collections import defaultdict
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

TIPOS_CON_STOCK = {"FAC": -1, "LIQ": +1}   # signo del movimiento


def _detalles(datos: dict) -> list[dict]:
    detalles = (datos or {}).get("detalles", {}).get("detalle", [])
    return detalles if isinstance(detalles, list) else ([detalles] if detalles else [])


def _cantidades_por_codigo(datos: dict) -> dict[str, int]:
    """Suma las cantidades por código (un mismo producto puede venir en varias líneas)."""
    totales: dict[str, int] = defaultdict(int)
    for det in _detalles(datos):
        if not isinstance(det, dict):
            continue
        codigo = det.get("codigoPrincipal") or det.get("codigoAuxiliar") or det.get("codigoInterno")
        if not codigo or codigo == "S/C":
            continue
        totales[codigo] += int(float(det.get("cantidad", 0) or 0))
    return {c: q for c, q in totales.items() if q > 0}


async def _mover(db: AsyncSession, *, emisor_id: int, codigo: str = None, item_id=None,
                 delta: int, solo_con_stock: bool) -> tuple | None:
    """
    Aplica delta al producto y devuelve (item_id, descripcion, antes, despues, stock_minimo).
    Solo productos con control de stock (stock != -1). Nunca deja stock negativo.
    """
    filtro = "c.id = :iid" if item_id else "c.emisor_id = :eid AND c.codigo = :cod"
    minimo = "AND c.stock > 0" if solo_con_stock else ""
    res = await db.execute(text(f"""
        WITH antes AS (
            SELECT c.id, c.stock FROM catalogo_items c
            WHERE {filtro} AND c.stock <> -1 {minimo}
            FOR UPDATE
        )
        UPDATE catalogo_items c
        SET stock = GREATEST(0, c.stock + :delta), updated_at = NOW()
        FROM antes
        WHERE c.id = antes.id
        RETURNING c.id, c.descripcion, antes.stock AS antes, c.stock AS despues, c.stock_minimo
    """), {"iid": item_id, "eid": emisor_id, "cod": codigo, "delta": delta})
    return res.fetchone()


async def _registrar(db, *, emisor_id, doc_id, item_id, codigo, cantidad, tipo):
    if cantidad == 0:
        return
    await db.execute(text("""
        INSERT INTO movimientos_stock (emisor_id, documento_id, catalogo_item_id, codigo, cantidad, tipo)
        VALUES (:eid, :did, :iid, :cod, :cant, :tipo)
    """), {"eid": emisor_id, "did": str(doc_id), "iid": str(item_id) if item_id else None,
           "cod": codigo, "cant": cantidad, "tipo": tipo})


async def _marcar(db, doc_id, estado: str):
    await db.execute(text("UPDATE documentos_emitidos SET stock_estado = :e WHERE id = :did"),
                     {"e": estado, "did": str(doc_id)})


# =============================================================================
# EMISIÓN
# =============================================================================
async def aplicar_emision(db: AsyncSession, *, doc_id, emisor_id: int, tipo_doc: str,
                          datos: dict, es_sandbox: bool) -> list[dict]:
    """
    Mueve el inventario al emitir. Devuelve los productos que cruzaron su stock mínimo
    (para avisar). No hace commit.
    """
    if es_sandbox or tipo_doc not in TIPOS_CON_STOCK:
        await _marcar(db, doc_id, "SIN_STOCK")
        return []

    signo  = TIPOS_CON_STOCK[tipo_doc]
    cruces = []
    for codigo, cantidad in _cantidades_por_codigo(datos).items():
        fila = await _mover(db, emisor_id=emisor_id, codigo=codigo, delta=signo * cantidad,
                            solo_con_stock=(signo < 0))
        if not fila:
            continue
        aplicado = fila.despues - fila.antes
        await _registrar(db, emisor_id=emisor_id, doc_id=doc_id, item_id=fila.id,
                         codigo=codigo, cantidad=aplicado, tipo="EMISION")
        # Aviso solo cuando ESTA venta cruza el mínimo
        if signo < 0 and fila.stock_minimo and fila.despues <= fila.stock_minimo < fila.antes:
            cruces.append({"id": str(fila.id), "descripcion": fila.descripcion,
                           "stock": fila.despues, "stock_minimo": fila.stock_minimo})

    await _marcar(db, doc_id, "APLICADO")
    return cruces


# =============================================================================
# REVERTIR (el SRI rechazó) / REAPLICAR (era un falso rechazo)
# =============================================================================
async def _saldos(db, doc_id) -> list:
    res = await db.execute(text("""
        SELECT catalogo_item_id, codigo,
               SUM(cantidad)                                                AS neto,
               COALESCE(SUM(cantidad) FILTER (WHERE tipo = 'EMISION'), 0)   AS emitido,
               COALESCE(SUM(cantidad) FILTER (WHERE tipo IN ('REVERSO', 'REAPLICACION')), 0) AS pendiente
        FROM movimientos_stock
        WHERE documento_id = :did
        GROUP BY catalogo_item_id, codigo
    """), {"did": str(doc_id)})
    return res.fetchall()


async def revertir(db: AsyncSession, doc) -> int:
    """
    Devuelve al inventario lo que movió el documento. Idempotente. No hace commit.
    doc necesita: id, emisor_id, tipo_doc, datos, stock_estado.
    Devuelve la cantidad de productos ajustados.
    """
    if doc.stock_estado in ("REVERTIDO", "SIN_STOCK"):
        return 0

    ajustados = 0
    saldos = await _saldos(db, doc.id)
    if any(s.emitido for s in saldos):
        # Documento con registro: se deshace exactamente lo movido
        for s in saldos:
            if s.neto == 0:
                continue
            fila = await _mover(db, emisor_id=doc.emisor_id, item_id=s.catalogo_item_id,
                                delta=-s.neto, solo_con_stock=False)
            if fila:
                await _registrar(db, emisor_id=doc.emisor_id, doc_id=doc.id, item_id=fila.id,
                                 codigo=s.codigo, cantidad=fila.despues - fila.antes, tipo="REVERSO")
                ajustados += 1
    elif doc.stock_estado is None and doc.tipo_doc in TIPOS_CON_STOCK:
        # Documento anterior al registro: se revierte como antes (sumando lo facturado)
        for codigo, cantidad in _cantidades_por_codigo(doc.datos or {}).items():
            fila = await _mover(db, emisor_id=doc.emisor_id, codigo=codigo, delta=cantidad,
                                solo_con_stock=False)
            if fila:
                await _registrar(db, emisor_id=doc.emisor_id, doc_id=doc.id, item_id=fila.id,
                                 codigo=codigo, cantidad=fila.despues - fila.antes, tipo="REVERSO")
                ajustados += 1

    await _marcar(db, doc.id, "REVERTIDO")
    return ajustados


async def reaplicar(db: AsyncSession, doc) -> int:
    """
    Vuelve a aplicar lo que se había revertido (p. ej. el SRI sí lo autorizó).
    Idempotente. No hace commit.
    """
    if doc.stock_estado != "REVERTIDO":
        return 0

    ajustados = 0
    for s in await _saldos(db, doc.id):
        if s.pendiente == 0:
            continue
        fila = await _mover(db, emisor_id=doc.emisor_id, item_id=s.catalogo_item_id,
                            delta=-s.pendiente, solo_con_stock=False)
        if fila:
            await _registrar(db, emisor_id=doc.emisor_id, doc_id=doc.id, item_id=fila.id,
                             codigo=s.codigo, cantidad=fila.despues - fila.antes, tipo="REAPLICACION")
            ajustados += 1

    await _marcar(db, doc.id, "APLICADO")
    return ajustados