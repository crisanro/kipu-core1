# app/services/proforma_service.py
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from datetime import date
from app.core.cache import cache_get, cache_set, cache_delete, CK, TTL


# ── Cache helpers ──────────────────────────────────────────────────────────────
async def _invalidar_proformas(emisor_id: int, proforma_id: str = None):
    await cache_delete(CK.fmt(CK.PROFORMAS_LISTA, eid=emisor_id))
    if proforma_id:
        await cache_delete(CK.fmt(CK.PROFORMA_DETALLE, eid=emisor_id, pid=proforma_id))


# ── Generar número ─────────────────────────────────────────────────────────────
async def _generar_numero(emisor_id: int, db: AsyncSession) -> str:
    anio = date.today().year
    res  = await db.execute(text("""
        SELECT COALESCE(MAX(
            CAST(SPLIT_PART(numero, '-', 3) AS INTEGER)
        ), 0) + 1 AS siguiente
        FROM proformas
        WHERE emisor_id = :eid
          AND SPLIT_PART(numero, '-', 2) = :anio
    """), {"eid": emisor_id, "anio": str(anio)})
    siguiente = res.scalar() or 1
    return f"PRO-{anio}-{str(siguiente).zfill(9)}"


# ── 1. CREAR ───────────────────────────────────────────────────────────────────
async def crear_proforma_core(emisor_id: int, datos: dict, db: AsyncSession):
    try:
        # Validaciones
        if not datos.get("items"):
            raise HTTPException(status_code=400, detail="LA PROFORMA DEBE TENER AL MENOS UN ÍTEM.")

        # Verificar cliente si viene
        cliente_id = datos.get("cliente_id")
        if cliente_id:
            res = await db.execute(
                text("SELECT id FROM clientes_emisor WHERE id = :cid AND emisor_id = :eid"),
                {"cid": cliente_id, "eid": emisor_id}
            )
            if not res.fetchone():
                raise HTTPException(status_code=404, detail="EL CLIENTE NO EXISTE O NO LE PERTENECE.")

        # Calcular totales desde los items
        subtotal  = 0.0
        total_iva = 0.0
        items_ok  = []

        for item in datos["items"]:
            cant     = float(item.get("cantidad", 1))
            precio   = float(item.get("precio_unitario", 0))
            tipo_iva = int(item.get("tipo_iva", 15))  # 0 | 8 | 15
            sub      = round(cant * precio, 2)
            iva      = round(sub * tipo_iva / 100, 2)
            items_ok.append({
                "descripcion":     item.get("descripcion", "").strip().upper(),
                "cantidad":        cant,
                "precio_unitario": precio,
                "tipo_iva":        tipo_iva,
                "subtotal":        sub,
                "valor_iva":       iva,
                "total":           round(sub + iva, 2),
            })
            subtotal  += sub
            total_iva += iva

        total    = round(subtotal + total_iva, 2)
        subtotal = round(subtotal, 2)
        total_iva = round(total_iva, 2)

        # Generar número
        numero = await _generar_numero(emisor_id, db)

        res = await db.execute(text("""
            INSERT INTO proformas (
                emisor_id, cliente_id, numero,
                fecha_emision, fecha_validez,
                items, subtotal, total_iva, total, notas
            ) VALUES (
                :eid, :cid, :numero,
                :fecha_emision, :fecha_validez,
                CAST(:items AS jsonb), :subtotal, :total_iva, :total, :notas
            ) RETURNING id
        """), {
            "eid":           emisor_id,
            "cid":           cliente_id,
            "numero":        numero,
            "fecha_emision": datos.get("fecha_emision") or date.today(),
            "fecha_validez": datos.get("fecha_validez") or None,
            "items":         __import__("json").dumps(items_ok),
            "subtotal":      subtotal,
            "total_iva":     total_iva,
            "total":         total,
            "notas":         datos.get("notas").strip() if datos.get("notas") else None,
        })
        proforma_id = res.scalar()
        await db.commit()
        await _invalidar_proformas(emisor_id)
        return {"ok": True, "mensaje": "PROFORMA CREADA.", "id": str(proforma_id), "numero": numero}

    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error creando proforma: {e}")
        raise HTTPException(status_code=500, detail="ERROR AL CREAR LA PROFORMA.")


# ── 2. LISTAR ──────────────────────────────────────────────────────────────────
async def listar_proformas_core(emisor_id: int, db: AsyncSession):
    cache_key = CK.fmt(CK.PROFORMAS_LISTA, eid=emisor_id)
    cached    = await cache_get(cache_key)
    if cached:
        return cached

    try:
        res = await db.execute(text("""
            SELECT
                p.id, p.numero, p.fecha_emision, p.fecha_validez,
                p.subtotal, p.total_iva, p.total,
                p.estado, p.notas, p.created_at,
                ce.id          AS cliente_id,
                ce.razon_social,
                ce.identificacion
            FROM proformas p
            LEFT JOIN clientes_emisor ce ON ce.id = p.cliente_id
            WHERE p.emisor_id = :eid
            ORDER BY p.created_at DESC
        """), {"eid": emisor_id})

        rows = res.mappings().fetchall()
        data = [_fmt_proforma(r) for r in rows]
        result = {"ok": True, "total": len(data), "data": data}
        await cache_set(cache_key, result, TTL.PROFORMAS_LISTA)
        return result

    except Exception as e:
        print(f"Error listando proformas: {e}")
        raise HTTPException(status_code=500, detail="ERROR AL OBTENER LAS PROFORMAS.")


# ── 3. DETALLE ─────────────────────────────────────────────────────────────────
async def detalle_proforma_core(emisor_id: int, proforma_id: str, db: AsyncSession):
    cache_key = CK.fmt(CK.PROFORMA_DETALLE, eid=emisor_id, pid=proforma_id)
    cached    = await cache_get(cache_key)
    if cached:
        return cached

    try:
        res = await db.execute(text("""
            SELECT
                p.id, p.numero, p.fecha_emision, p.fecha_validez,
                p.items, p.subtotal, p.total_iva, p.total,
                p.estado, p.notas, p.created_at,
                p.documento_emitido_id,
                ce.id            AS cliente_id,
                ce.razon_social,
                ce.identificacion,
                ce.email,
                ce.telefono,
                ce.direccion,
                ce.tipo_identificacion_sri,
                e.razon_social   AS emisor_razon_social,
                e.ruc            AS emisor_ruc,
                e.direccion_matriz AS emisor_direccion,
                e.nombre_comercial AS emisor_nombre_comercial
            FROM proformas p
            LEFT JOIN clientes_emisor ce ON ce.id    = p.cliente_id
            JOIN  emisores e             ON e.id     = p.emisor_id
            WHERE p.id = :pid AND p.emisor_id = :eid
        """), {"pid": proforma_id, "eid": emisor_id})

        row = res.mappings().fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="PROFORMA NO ENCONTRADA.")

        data   = _fmt_proforma(row, incluir_items=True)
        result = {"ok": True, "proforma": data}
        await cache_set(cache_key, result, TTL.PROFORMA_DETALLE)
        return result

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error detalle proforma: {e}")
        raise HTTPException(status_code=500, detail="ERROR AL OBTENER LA PROFORMA.")


# ── 4. MARCAR FACTURADA ────────────────────────────────────────────────────────
async def facturar_proforma_core(emisor_id: int, proforma_id: str, documento_id: str, db: AsyncSession):
    try:
        res = await db.execute(text("""
            SELECT id, estado FROM proformas
            WHERE id = :pid AND emisor_id = :eid
        """), {"pid": proforma_id, "eid": emisor_id})
        row = res.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="PROFORMA NO ENCONTRADA.")
        if row.estado == "FACTURADA":
            raise HTTPException(status_code=400, detail="LA PROFORMA YA FUE FACTURADA.")

        await db.execute(text("""
            UPDATE proformas
            SET estado               = 'FACTURADA',
                documento_emitido_id = :did,
                updated_at           = NOW()
            WHERE id = :pid AND emisor_id = :eid
        """), {"pid": proforma_id, "eid": emisor_id, "did": documento_id})
        await db.commit()
        await _invalidar_proformas(emisor_id, proforma_id)
        return {"ok": True, "mensaje": "PROFORMA MARCADA COMO FACTURADA."}

    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail="ERROR AL FACTURAR LA PROFORMA.")


# ── 5. ELIMINAR ────────────────────────────────────────────────────────────────
async def eliminar_proforma_core(emisor_id: int, proforma_id: str, db: AsyncSession):
    try:
        res = await db.execute(text("""
            SELECT id, estado FROM proformas
            WHERE id = :pid AND emisor_id = :eid
        """), {"pid": proforma_id, "eid": emisor_id})
        row = res.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="PROFORMA NO ENCONTRADA.")
        if row.estado == "FACTURADA":
            raise HTTPException(status_code=400, detail="NO SE PUEDE ELIMINAR UNA PROFORMA FACTURADA.")

        await db.execute(
            text("DELETE FROM proformas WHERE id = :pid AND emisor_id = :eid"),
            {"pid": proforma_id, "eid": emisor_id}
        )
        await db.commit()
        await _invalidar_proformas(emisor_id, proforma_id)
        return {"ok": True, "mensaje": "PROFORMA ELIMINADA."}

    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail="ERROR AL ELIMINAR LA PROFORMA.")


# ── Helpers ────────────────────────────────────────────────────────────────────
def _fmt_proforma(r, incluir_items: bool = False) -> dict:
    hoy     = date.today()
    vencida = (
        r["fecha_validez"] is not None and
        r["fecha_validez"] < hoy and
        r["estado"] == "VIGENTE"
    )
    d = {
        "id":            str(r["id"]),
        "numero":        r["numero"],
        "fecha_emision": r["fecha_emision"].strftime("%Y-%m-%d") if r["fecha_emision"] else None,
        "fecha_validez": r["fecha_validez"].strftime("%Y-%m-%d") if r["fecha_validez"] else None,
        "subtotal":      float(r["subtotal"]),
        "total_iva":     float(r["total_iva"]),
        "total":         float(r["total"]),
        "estado":        r["estado"],
        "vencida":       vencida,
        "notas":         r.get("notas"),
        "documento_emitido_id": str(r["documento_emitido_id"]) if r.get("documento_emitido_id") else None,
    }
    # Cliente
    if r.get("cliente_id"):
        d["cliente"] = {
            "id":                      str(r["cliente_id"]),
            "razon_social":            r["razon_social"],
            "identificacion":          r["identificacion"],
            "email":                   r.get("email"),
            "telefono":                r.get("telefono"),
            "direccion":               r.get("direccion"),
            "tipo_identificacion_sri": r.get("tipo_identificacion_sri"),
        }
    else:
        d["cliente"] = None

    # Emisor — solo en detalle
    if incluir_items:
        d["items"] = r["items"] if isinstance(r["items"], list) else []
        d["emisor"] = {
            "razon_social":    r.get("emisor_razon_social"),
            "nombre_comercial": r.get("emisor_nombre_comercial"),
            "ruc":             r.get("emisor_ruc"),
            "direccion":       r.get("emisor_direccion"),
        }

    return d