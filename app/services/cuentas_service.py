# app/services/cuentas_service.py
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from app.core.cache import cache_get, cache_set, cache_delete, CK, TTL


# ── Helpers cache ──────────────────────────────────────────────────────────────
async def _invalidar_cuentas(emisor_id: int, cliente_id: str = None):
    await cache_delete(CK.fmt(CK.CUENTAS_LISTA, eid=emisor_id))
    if cliente_id:
        await cache_delete(CK.fmt(CK.CUENTAS_CLIENTE, eid=emisor_id, cid=cliente_id))
        await cache_delete(CK.fmt(CK.CLIENTE_DETALLE, eid=emisor_id, cid=cliente_id))


# ── 1. CREAR CUENTA ────────────────────────────────────────────────────────────
async def crear_cuenta_core(emisor_id: int, datos: dict, db: AsyncSession):
    try:
        # Verificar que el cliente pertenece al emisor
        res = await db.execute(
            text("SELECT id FROM clientes_emisor WHERE id = :cid AND emisor_id = :eid"),
            {"cid": datos["cliente_id"], "eid": emisor_id}
        )
        if not res.fetchone():
            raise HTTPException(status_code=404, detail="EL CLIENTE NO EXISTE O NO LE PERTENECE.")

        if datos["monto_total"] <= 0:
            raise HTTPException(status_code=400, detail="EL MONTO DEBE SER MAYOR A CERO.")

        if datos["tipo"] not in ("COBRAR", "PAGAR"):
            raise HTTPException(status_code=400, detail="TIPO INVÁLIDO. USA COBRAR O PAGAR.")

        res = await db.execute(text("""
            INSERT INTO cuentas_movimientos (
                emisor_id, cliente_id, tipo, concepto,
                monto_total, fecha_emision, fecha_vencimiento,
                documento_emitido_id, documento_recibido_id, notas
            ) VALUES (
                :eid, :cid, :tipo, :concepto,
                :monto_total, :fecha_emision, :fecha_vencimiento,
                :doc_emitido, :doc_recibido, :notas
            ) RETURNING id
        """), {
            "eid":              emisor_id,
            "cid":              datos["cliente_id"],
            "tipo":             datos["tipo"],
            "concepto":         datos["concepto"].strip().upper(),
            "monto_total":      datos["monto_total"],
            "fecha_emision":    datos.get("fecha_emision"),
            "fecha_vencimiento": datos.get("fecha_vencimiento"),
            "doc_emitido":      datos.get("documento_emitido_id"),
            "doc_recibido":     datos.get("documento_recibido_id"),
            "notas": datos.get("notas").strip() if datos.get("notas") else None,
        })
        cuenta_id = res.scalar()
        await db.commit()
        await _invalidar_cuentas(emisor_id, datos["cliente_id"])
        return {"ok": True, "mensaje": "CUENTA REGISTRADA.", "id": str(cuenta_id)}

    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error creando cuenta: {e}")
        raise HTTPException(status_code=500, detail="ERROR AL REGISTRAR LA CUENTA.")


# ── 2. REGISTRAR ABONO ─────────────────────────────────────────────────────────
async def registrar_abono_core(emisor_id: int, cuenta_id: str, datos: dict, db: AsyncSession):
    try:
        # Verificar que la cuenta pertenece al emisor y no está anulada
        res = await db.execute(text("""
            SELECT id, cliente_id, estado, monto_total, monto_pagado
            FROM cuentas_movimientos
            WHERE id = :cid AND emisor_id = :eid
        """), {"cid": cuenta_id, "eid": emisor_id})
        cuenta = res.mappings().fetchone()

        if not cuenta:
            raise HTTPException(status_code=404, detail="LA CUENTA NO EXISTE.")
        if cuenta["estado"] == "ANULADO":
            raise HTTPException(status_code=400, detail="NO SE PUEDE ABONAR A UNA CUENTA ANULADA.")
        if cuenta["estado"] == "PAGADO":
            raise HTTPException(status_code=400, detail="LA CUENTA YA ESTÁ COMPLETAMENTE PAGADA.")

        monto = datos["monto"]
        if monto <= 0:
            raise HTTPException(status_code=400, detail="EL MONTO DEL ABONO DEBE SER MAYOR A CERO.")

        saldo_pendiente = float(cuenta["monto_total"]) - float(cuenta["monto_pagado"])
        if monto > saldo_pendiente:
            raise HTTPException(
                status_code=400,
                detail=f"EL ABONO (${monto:.2f}) SUPERA EL SALDO PENDIENTE (${saldo_pendiente:.2f})."
            )

        await db.execute(text("""
            INSERT INTO cuentas_abonos (cuenta_id, monto, fecha, forma_pago, notas)
            VALUES (:cid, :monto, :fecha, :forma_pago, :notas)
        """), {
            "cid":       cuenta_id,
            "monto":     monto,
            "fecha":     datos.get("fecha"),
            "forma_pago": datos.get("forma_pago") or None,
            "notas":     datos.get("notas").strip() if datos.get("notas") else None,
        })
        await db.commit()
        # El trigger ya actualizó monto_pagado y estado — solo invalidamos cache
        await _invalidar_cuentas(emisor_id, str(cuenta["cliente_id"]))
        return {"ok": True, "mensaje": "ABONO REGISTRADO."}

    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        print(f"Error registrando abono: {e}")
        raise HTTPException(status_code=500, detail="ERROR AL REGISTRAR EL ABONO.")


# ── 3. ANULAR CUENTA ───────────────────────────────────────────────────────────
async def anular_cuenta_core(emisor_id: int, cuenta_id: str, db: AsyncSession):
    try:
        res = await db.execute(text("""
            SELECT id, cliente_id, estado
            FROM cuentas_movimientos
            WHERE id = :cid AND emisor_id = :eid
        """), {"cid": cuenta_id, "eid": emisor_id})
        cuenta = res.mappings().fetchone()

        if not cuenta:
            raise HTTPException(status_code=404, detail="LA CUENTA NO EXISTE.")
        if cuenta["estado"] == "ANULADO":
            raise HTTPException(status_code=400, detail="LA CUENTA YA ESTÁ ANULADA.")
        if cuenta["estado"] == "PAGADO":
            raise HTTPException(status_code=400, detail="NO SE PUEDE ANULAR UNA CUENTA PAGADA.")

        await db.execute(text("""
            UPDATE cuentas_movimientos
            SET estado = 'ANULADO', updated_at = NOW()
            WHERE id = :cid AND emisor_id = :eid
        """), {"cid": cuenta_id, "eid": emisor_id})
        await db.commit()
        await _invalidar_cuentas(emisor_id, str(cuenta["cliente_id"]))
        return {"ok": True, "mensaje": "CUENTA ANULADA."}

    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail="ERROR AL ANULAR LA CUENTA.")


# ── 4. LISTAR CUENTAS DEL EMISOR (vista global) ────────────────────────────────
async def listar_cuentas_core(emisor_id: int, tipo: str = None, estado: str = None, db: AsyncSession = None):
    cache_key = CK.fmt(CK.CUENTAS_LISTA, eid=emisor_id)
    cached = await cache_get(cache_key)
    if cached and not tipo and not estado:
        return cached

    try:
        filtros = "WHERE cm.emisor_id = :eid"
        params  = {"eid": emisor_id}
        if tipo:
            filtros += " AND cm.tipo = :tipo"
            params["tipo"] = tipo
        if estado:
            filtros += " AND cm.estado = :estado"
            params["estado"] = estado

        res = await db.execute(text(f"""
            SELECT
                cm.id,
                cm.tipo,
                cm.concepto,
                cm.monto_total,
                cm.monto_pagado,
                cm.monto_total - cm.monto_pagado AS saldo_pendiente,
                cm.fecha_emision,
                cm.fecha_vencimiento,
                cm.estado,
                cm.notas,
                cm.created_at,
                ce.id          AS cliente_id,
                ce.razon_social,
                ce.identificacion
            FROM cuentas_movimientos cm
            JOIN clientes_emisor ce ON ce.id = cm.cliente_id
            {filtros}
            ORDER BY
                CASE cm.estado
                    WHEN 'PENDIENTE' THEN 1
                    WHEN 'PARCIAL'   THEN 2
                    WHEN 'PAGADO'    THEN 3
                    WHEN 'ANULADO'   THEN 4
                END,
                cm.fecha_vencimiento ASC NULLS LAST,
                cm.created_at DESC
        """), params)

        rows = res.mappings().fetchall()
        data = [_fmt_cuenta(r) for r in rows]

        resumen = _calcular_resumen(data)
        result  = {"ok": True, "resumen": resumen, "data": data}

        if not tipo and not estado:
            await cache_set(cache_key, result, TTL.CUENTAS_LISTA)
        return result

    except Exception as e:
        print(f"Error listando cuentas: {e}")
        raise HTTPException(status_code=500, detail="ERROR AL OBTENER LAS CUENTAS.")


# ── 5. CUENTAS POR CLIENTE ─────────────────────────────────────────────────────
async def listar_cuentas_cliente_core(emisor_id: int, cliente_id: str, db: AsyncSession):
    cache_key = CK.fmt(CK.CUENTAS_CLIENTE, eid=emisor_id, cid=cliente_id)
    cached = await cache_get(cache_key)
    if cached:
        return cached

    try:
        res = await db.execute(text("""
            SELECT
                cm.id,
                cm.tipo,
                cm.concepto,
                cm.monto_total,
                cm.monto_pagado,
                cm.monto_total - cm.monto_pagado AS saldo_pendiente,
                cm.fecha_emision,
                cm.fecha_vencimiento,
                cm.estado,
                cm.notas,
                cm.created_at
            FROM cuentas_movimientos cm
            WHERE cm.emisor_id  = :eid
              AND cm.cliente_id = :cid
            ORDER BY
                CASE cm.estado
                    WHEN 'PENDIENTE' THEN 1
                    WHEN 'PARCIAL'   THEN 2
                    WHEN 'PAGADO'    THEN 3
                    WHEN 'ANULADO'   THEN 4
                END,
                cm.fecha_vencimiento ASC NULLS LAST,
                cm.created_at DESC
        """), {"eid": emisor_id, "cid": cliente_id})

        rows = res.mappings().fetchall()
        data = [_fmt_cuenta(r) for r in rows]
        resumen = _calcular_resumen(data)
        result  = {"ok": True, "resumen": resumen, "data": data}

        await cache_set(cache_key, result, TTL.CUENTAS_CLIENTE)
        return result

    except Exception as e:
        print(f"Error listando cuentas cliente: {e}")
        raise HTTPException(status_code=500, detail="ERROR AL OBTENER LAS CUENTAS DEL CLIENTE.")


# ── 6. DETALLE DE UNA CUENTA (con abonos) ──────────────────────────────────────
async def detalle_cuenta_core(emisor_id: int, cuenta_id: str, db: AsyncSession):
    try:
        res_cuenta = await db.execute(text("""
            SELECT
                cm.id, cm.tipo, cm.concepto,
                cm.monto_total, cm.monto_pagado,
                cm.monto_total - cm.monto_pagado AS saldo_pendiente,
                cm.fecha_emision, cm.fecha_vencimiento,
                cm.estado, cm.notas, cm.created_at,
                ce.id AS cliente_id, ce.razon_social, ce.identificacion
            FROM cuentas_movimientos cm
            JOIN clientes_emisor ce ON ce.id = cm.cliente_id
            WHERE cm.id = :cid AND cm.emisor_id = :eid
        """), {"cid": cuenta_id, "eid": emisor_id})

        cuenta = res_cuenta.mappings().fetchone()
        if not cuenta:
            raise HTTPException(status_code=404, detail="LA CUENTA NO EXISTE.")

        res_abonos = await db.execute(text("""
            SELECT id, monto, fecha, forma_pago, notas, created_at
            FROM cuentas_abonos
            WHERE cuenta_id = :cid
            ORDER BY fecha ASC, created_at ASC
        """), {"cid": cuenta_id})

        abonos = [
            {
                "id":         str(a["id"]),
                "monto":      float(a["monto"]),
                "fecha":      a["fecha"].strftime('%Y-%m-%d') if a["fecha"] else None,
                "forma_pago": a["forma_pago"],
                "notas":      a["notas"],
            }
            for a in res_abonos.mappings().fetchall()
        ]

        return {
            "ok":     True,
            "cuenta": _fmt_cuenta(cuenta),
            "abonos": abonos,
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error detalle cuenta: {e}")
        raise HTTPException(status_code=500, detail="ERROR AL OBTENER EL DETALLE.")


# ── Helpers internos ───────────────────────────────────────────────────────────
def _fmt_cuenta(r) -> dict:
    d = {
        "id":               str(r["id"]),
        "tipo":             r["tipo"],
        "concepto":         r["concepto"],
        "monto_total":      float(r["monto_total"]),
        "monto_pagado":     float(r["monto_pagado"]),
        "saldo_pendiente":  float(r["saldo_pendiente"]),
        "fecha_emision":    r["fecha_emision"].strftime('%Y-%m-%d') if r["fecha_emision"] else None,
        "fecha_vencimiento": r["fecha_vencimiento"].strftime('%Y-%m-%d') if r["fecha_vencimiento"] else None,
        "estado":           r["estado"],
        "notas":            r.get("notas"),
    }
    # campos opcionales presentes solo en lista global
    if "cliente_id" in r.keys():
        d["cliente_id"]    = str(r["cliente_id"])
        d["razon_social"]  = r["razon_social"]
        d["identificacion"] = r["identificacion"]
    return d


def _calcular_resumen(data: list) -> dict:
    por_cobrar_pendiente = sum(
        d["saldo_pendiente"] for d in data
        if d["tipo"] == "COBRAR" and d["estado"] in ("PENDIENTE", "PARCIAL")
    )
    por_pagar_pendiente = sum(
        d["saldo_pendiente"] for d in data
        if d["tipo"] == "PAGAR" and d["estado"] in ("PENDIENTE", "PARCIAL")
    )
    return {
        "por_cobrar": round(por_cobrar_pendiente, 2),
        "por_pagar":  round(por_pagar_pendiente,  2),
        "balance":    round(por_cobrar_pendiente - por_pagar_pendiente, 2),
    }