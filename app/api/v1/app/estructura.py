from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.core.database import get_db
from app.core.security import verify_firebase_token
from app.schemas.estructura import (
    EstablecimientoCreate, PuntoEmisionCreate,
    EstablecimientoUpdate, PuntoEmisionUpdate, WhatsappConfigUpdate
)
from app.core.cache import cache_get, cache_set, cache_delete, CK, TTL

router = APIRouter()

# ── GET Estructura — CON CACHE ─────────────────────────────────────────────────
@router.get("", summary="Listar establecimientos y puntos de emisión")
async def listar_estructura(
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db),
):
    emisor_id = auth_data["emisor_id"]

    cache_key = CK.fmt(CK.ESTRUCTURA, eid=emisor_id)
    cached = await cache_get(cache_key)
    if cached:
        return cached

    # OPTIMIZACIÓN: query única con JOIN (antes requería múltiples queries)
    query = text("""
        SELECT
            e.id AS estab_id, e.codigo AS estab_codigo, e.nombre_comercial,
            e.direccion, e.is_active AS estab_activo,
            p.id AS punto_id, p.codigo AS punto_codigo, p.nombre AS punto_nombre,
            p.secuencial_actual, p.is_active AS punto_activo,
            em.ws_establecimiento, em.ws_punto_emision
        FROM establecimientos e
        LEFT JOIN puntos_emision p ON p.establecimiento_id = e.id
        JOIN emisores em ON em.id = e.emisor_id
        WHERE e.emisor_id = :eid
        ORDER BY e.codigo ASC, p.codigo ASC
    """)
    res = await db.execute(query, {"eid": emisor_id})
    rows = res.fetchall()

    estructura_map = {}
    for row in rows:
        if row.estab_id not in estructura_map:
            estructura_map[row.estab_id] = {
                "id":               row.estab_id,
                "codigo":           row.estab_codigo,
                "nombre_comercial": row.nombre_comercial,
                "direccion":        row.direccion,
                "is_active":        row.estab_activo,
                "puntos_emision":   [],
            }
        if row.punto_id:
            es_ws = (
                row.ws_establecimiento == row.estab_codigo and
                row.ws_punto_emision   == row.punto_codigo
            )
            estructura_map[row.estab_id]["puntos_emision"].append({
                "id":                row.punto_id,
                "codigo":            row.punto_codigo,
                "nombre":            row.punto_nombre,
                "secuencial_actual": row.secuencial_actual,
                "is_active":         row.punto_activo,
                "es_canal_whatsapp": es_ws,
            })

    response = {"ok": True, "data": list(estructura_map.values())}
    await cache_set(cache_key, response, TTL.ESTRUCTURA)
    return response


async def _invalidar_estructura(emisor_id: int):
    """Borra cache de estructura Y dashboard_header — ambos se ven afectados."""
    await cache_delete(CK.fmt(CK.ESTRUCTURA, eid=emisor_id))
    await cache_delete(f"dashboard_header:{emisor_id}")


# ── POST Establecimiento ───────────────────────────────────────────────────────
@router.post("/establecimientos", summary="Crear un nuevo establecimiento")
async def crear_establecimiento(
    data: EstablecimientoCreate,
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db),
):
    emisor_id  = auth_data["emisor_id"]
    codigo_fmt = str(data.codigo).zfill(3)

    try:
        # OPTIMIZACIÓN: traemos nombre_comercial y direccion en la misma query de validación
        res_emisor = await db.execute(
            text("SELECT nombre_comercial, direccion_matriz FROM emisores WHERE id = :eid"),
            {"eid": emisor_id}
        )
        emisor_data = res_emisor.fetchone()
        if not emisor_data:
            raise HTTPException(status_code=404, detail="Emisor no encontrado.")

        final_nombre   = data.nombre_comercial or emisor_data.nombre_comercial
        final_direccion = data.direccion or emisor_data.direccion_matriz

        res = await db.execute(text("""
            INSERT INTO establecimientos (emisor_id, codigo, nombre_comercial, direccion, is_active)
            VALUES (:eid, :cod, :nom, :dir, true)
            RETURNING id, codigo, nombre_comercial, direccion, is_active
        """), {"eid": emisor_id, "cod": codigo_fmt, "nom": final_nombre, "dir": final_direccion})
        nuevo_estab = res.fetchone()
        await db.commit()

        await _invalidar_estructura(emisor_id)
        return {"ok": True, "mensaje": "Establecimiento creado correctamente.", "data": dict(nuevo_estab._mapping)}

    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail=f"El establecimiento {codigo_fmt} ya existe.")
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ── POST Punto de Emisión ──────────────────────────────────────────────────────
@router.post("/puntos-emision", summary="Crear un punto de emisión")
async def crear_punto_emision(
    data: PuntoEmisionCreate,
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db),
):
    emisor_id = auth_data["emisor_id"]

    try:
        codigo_estab_fmt = str(data.establecimiento_codigo).zfill(3)
        res_estab = await db.execute(
            text("SELECT id FROM establecimientos WHERE emisor_id = :eid AND codigo = :cod"),
            {"eid": emisor_id, "cod": codigo_estab_fmt}
        )
        estab = res_estab.fetchone()
        if not estab:
            raise HTTPException(status_code=404, detail=f"No existe el establecimiento {codigo_estab_fmt}.")

        nombre_punto = data.nombre or f"Punto {data.codigo}"
        res = await db.execute(text("""
            INSERT INTO puntos_emision (establecimiento_id, emisor_id, codigo, secuencial_actual, nombre, is_active)
            VALUES (:estab_id, :eid, :cod, 1, :nom, true)
            RETURNING id, establecimiento_id, emisor_id, codigo, secuencial_actual, nombre, is_active
        """), {
            "estab_id": estab.id,
            "eid":      emisor_id,
            "cod":      str(data.codigo).zfill(3),
            "nom":      nombre_punto,
        })
        nuevo_punto = res.fetchone()
        await db.commit()

        await _invalidar_estructura(emisor_id)
        return {"ok": True, "mensaje": f"Punto de emisión {data.codigo} creado.", "data": dict(nuevo_punto._mapping)}

    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="El punto de emisión ya existe en este establecimiento.")
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ── PATCH WhatsApp Config ──────────────────────────────────────────────────────
@router.patch("/whatsapp-config", summary="Configurar punto de emisión para WhatsApp")
async def configurar_whatsapp(
    data: WhatsappConfigUpdate,
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db),
):
    emisor_id = auth_data.get("emisor_id")
    if not emisor_id:
        raise HTTPException(status_code=400, detail="EL USUARIO NO TIENE UN EMISOR VINCULADO.")

    estab_raw  = data.establecimiento
    punto_raw  = data.punto_emision
    estab_reset = estab_raw is None or str(estab_raw).strip().lstrip("0") == ""
    punto_reset = punto_raw is None or str(punto_raw).strip().lstrip("0") == ""

    if estab_reset and punto_reset:
        await db.execute(text("""
            UPDATE emisores SET ws_establecimiento = NULL, ws_punto_emision = NULL, updated_at = NOW()
            WHERE id = :eid
        """), {"eid": emisor_id})
        await db.commit()
        # Invalida estructura Y perfil del emisor (el perfil incluye whatsapp_info)
        await _invalidar_estructura(emisor_id)
        await cache_delete(CK.fmt(CK.EMISOR, eid=emisor_id))
        return {"ok": True, "mensaje": "CANAL WHATSAPP DESACTIVADO CORRECTAMENTE."}

    estab_fmt = str(estab_raw).zfill(3)
    punto_fmt = str(punto_raw).zfill(3)

    res_check = await db.execute(text("""
        SELECT e.is_active AS estab_activo, p.is_active AS punto_activo
        FROM establecimientos e
        JOIN puntos_emision p ON p.establecimiento_id = e.id
        WHERE e.emisor_id = :eid AND e.codigo = :estab AND p.codigo = :punto
    """), {"eid": emisor_id, "estab": estab_fmt, "punto": punto_fmt})
    row = res_check.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail=f"NO EXISTE EL ESTABLECIMIENTO {estab_fmt} CON PUNTO {punto_fmt}.")
    if not row.estab_activo:
        raise HTTPException(status_code=400, detail=f"EL ESTABLECIMIENTO {estab_fmt} ESTÁ INACTIVO.")
    if not row.punto_activo:
        raise HTTPException(status_code=400, detail=f"EL PUNTO {punto_fmt} ESTÁ INACTIVO.")

    await db.execute(text("""
        UPDATE emisores SET ws_establecimiento = :estab, ws_punto_emision = :punto, updated_at = NOW()
        WHERE id = :eid
    """), {"estab": estab_fmt, "punto": punto_fmt, "eid": emisor_id})
    await db.commit()

    await _invalidar_estructura(emisor_id)
    await cache_delete(CK.fmt(CK.EMISOR, eid=emisor_id))

    return {
        "ok":      True,
        "mensaje": "CANAL WHATSAPP CONFIGURADO CORRECTAMENTE.",
        "data":    {"establecimiento": estab_fmt, "punto_emision": punto_fmt}
    }


# ── PUT Establecimiento ────────────────────────────────────────────────────────
@router.put("/establecimientos/{estab_id}", summary="Editar un establecimiento")
async def editar_establecimiento(
    estab_id: int,
    data: EstablecimientoUpdate,
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db),
):
    emisor_id = auth_data["emisor_id"]

    if data.is_active is False:
        res_check = await db.execute(text("""
            SELECT ws_establecimiento FROM emisores
            WHERE id = :eid AND ws_establecimiento = (
                SELECT codigo FROM establecimientos WHERE id = :id AND emisor_id = :eid
            )
        """), {"eid": emisor_id, "id": estab_id})
        if res_check.fetchone():
            raise HTTPException(
                status_code=400,
                detail="ESTE ESTABLECIMIENTO TIENE UN PUNTO WHATSAPP ACTIVO. DESACTÍVALO PRIMERO."
            )

    res = await db.execute(text("""
        UPDATE establecimientos
        SET nombre_comercial = COALESCE(:nom, nombre_comercial),
            direccion        = COALESCE(:dir, direccion),
            is_active        = COALESCE(:act, is_active)
        WHERE id = :id AND emisor_id = :eid
        RETURNING id, codigo, nombre_comercial, direccion, is_active
    """), {"nom": data.nombre_comercial, "dir": data.direccion, "act": data.is_active, "id": estab_id, "eid": emisor_id})
    updated = res.fetchone()
    if not updated:
        raise HTTPException(status_code=404, detail="Establecimiento no encontrado o no te pertenece.")

    await db.commit()
    await _invalidar_estructura(emisor_id)
    return {"ok": True, "mensaje": "Establecimiento actualizado.", "data": dict(updated._mapping)}


# ── PUT Punto de Emisión ───────────────────────────────────────────────────────
@router.put("/puntos-emision/{punto_id}", summary="Editar un punto de emisión")
async def editar_punto_emision(
    punto_id: int,
    data: PuntoEmisionUpdate,
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db),
):
    emisor_id = auth_data["emisor_id"]

    if data.is_active is False:
        res_check = await db.execute(text("""
            SELECT ws_punto_emision FROM emisores
            WHERE id = :eid
              AND ws_punto_emision = (
                  SELECT pe.codigo FROM puntos_emision pe
                  JOIN establecimientos e ON pe.establecimiento_id = e.id
                  WHERE pe.id = :pid AND e.emisor_id = :eid
              )
              AND ws_establecimiento = (
                  SELECT e.codigo FROM establecimientos e
                  JOIN puntos_emision pe ON pe.establecimiento_id = e.id
                  WHERE pe.id = :pid AND e.emisor_id = :eid
              )
        """), {"eid": emisor_id, "pid": punto_id})
        if res_check.fetchone():
            raise HTTPException(
                status_code=400,
                detail="ESTE PUNTO ESTÁ CONFIGURADO COMO CANAL WHATSAPP. DESACTÍVALO PRIMERO."
            )

    res = await db.execute(text("""
        UPDATE puntos_emision pe
        SET nombre    = COALESCE(:nom, pe.nombre),
            is_active = COALESCE(:act, pe.is_active)
        FROM establecimientos e
        WHERE pe.establecimiento_id = e.id AND pe.id = :pid AND e.emisor_id = :eid
        RETURNING pe.id, pe.codigo, pe.nombre, pe.is_active
    """), {"nom": data.nombre, "act": data.is_active, "pid": punto_id, "eid": emisor_id})
    updated = res.fetchone()
    if not updated:
        raise HTTPException(status_code=404, detail="Punto de emisión no encontrado.")

    await db.commit()
    await _invalidar_estructura(emisor_id)
    return {"ok": True, "mensaje": "Punto de emisión actualizado.", "data": dict(updated._mapping)}


# ── PATCH Secuencial ───────────────────────────────────────────────────────────
@router.patch("/puntos-emision/{punto_id}/secuencial", summary="Corregir secuencial de un punto")
async def editar_secuencial(
    punto_id: int,
    data: dict,
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db),
):
    emisor_id    = auth_data["emisor_id"]
    nuevo_sec    = data.get("secuencial_actual")

    if nuevo_sec is None or int(nuevo_sec) < 1:
        raise HTTPException(status_code=400, detail="El secuencial debe ser mayor a 0.")

    res = await db.execute(text("""
        UPDATE puntos_emision pe
        SET secuencial_actual = :sec
        FROM establecimientos e
        WHERE pe.establecimiento_id = e.id
          AND pe.id = :pid
          AND e.emisor_id = :eid
        RETURNING pe.id, pe.codigo, pe.secuencial_actual
    """), {"sec": int(nuevo_sec), "pid": punto_id, "eid": emisor_id})
    updated = res.fetchone()
    if not updated:
        raise HTTPException(status_code=404, detail="Punto no encontrado.")
    await db.commit()
    await _invalidar_estructura(emisor_id)
    return {"ok": True, "mensaje": "Secuencial actualizado.", "data": dict(updated._mapping)}