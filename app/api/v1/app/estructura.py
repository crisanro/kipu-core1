# app/api/v1/app/estructura.py
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.core.database import get_db
from app.core.security import verify_firebase_token
from app.schemas.estructura import (
    EstablecimientoCreate, PuntoEmisionCreate,
    EstablecimientoUpdate, PuntoEmisionUpdate,
)
from app.core.cache import cache_get, cache_set, cache_delete, CK, TTL

router = APIRouter()


# =============================================================================
# GET /
# =============================================================================

@router.get("", summary="Listar establecimientos y puntos de emisión")
async def listar_estructura(
    auth_data: dict         = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db),
):
    emisor_id = auth_data["emisor_id"]
    cache_key = CK.fmt(CK.ESTRUCTURA, eid=emisor_id)
    cached    = await cache_get(cache_key)
    if cached:
        return cached

    res = await db.execute(text("""
        SELECT
            e.id AS estab_id, e.codigo AS estab_codigo,
            e.nombre_comercial, e.direccion, e.is_active AS estab_activo,
            p.id AS punto_id, p.codigo AS punto_codigo,
            p.nombre AS punto_nombre, p.secuencial_actual,
            p.secuenciales,
            p.is_active AS punto_activo
        FROM establecimientos e
        LEFT JOIN puntos_emision p ON p.establecimiento_id = e.id
        WHERE e.emisor_id = :eid
        ORDER BY e.codigo ASC, p.codigo ASC
    """), {"eid": emisor_id})

    rows           = res.fetchall()
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
            estructura_map[row.estab_id]["puntos_emision"].append({
                "id":                row.punto_id,
                "codigo":            row.punto_codigo,
                "nombre":            row.punto_nombre,
                "secuencial_actual": row.secuencial_actual,
                "secuenciales":      row.secuenciales or {},
                "is_active":         row.punto_activo,
            })

    response = {"ok": True, "data": list(estructura_map.values())}
    await cache_set(cache_key, response, TTL.ESTRUCTURA)
    return response


async def _invalidar_estructura(emisor_id: int):
    await cache_delete(CK.fmt(CK.ESTRUCTURA, eid=emisor_id))
    await cache_delete(f"dashboard_header:{emisor_id}")


# =============================================================================
# POST /establecimientos
# =============================================================================

@router.post("/establecimientos", summary="Crear establecimiento")
async def crear_establecimiento(
    data:      EstablecimientoCreate,
    auth_data: dict         = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db),
):
    emisor_id  = auth_data["emisor_id"]
    codigo_fmt = str(data.codigo).zfill(3)

    try:
        res_emisor = await db.execute(
            text("SELECT nombre_comercial, direccion_matriz FROM emisores WHERE id = :eid"),
            {"eid": emisor_id}
        )
        emisor_data = res_emisor.fetchone()
        if not emisor_data:
            raise HTTPException(status_code=404, detail="Emisor no encontrado.")

        final_nombre    = data.nombre_comercial or emisor_data.nombre_comercial
        final_direccion = data.direccion or emisor_data.direccion_matriz

        res = await db.execute(text("""
            INSERT INTO establecimientos
                (emisor_id, codigo, nombre_comercial, direccion, is_active)
            VALUES (:eid, :cod, :nom, :dir, true)
            RETURNING id, codigo, nombre_comercial, direccion, is_active
        """), {"eid": emisor_id, "cod": codigo_fmt, "nom": final_nombre, "dir": final_direccion})

        nuevo = res.fetchone()
        await db.commit()
        await _invalidar_estructura(emisor_id)
        return {"ok": True, "mensaje": "Establecimiento creado.", "data": dict(nuevo._mapping)}

    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail=f"El establecimiento {codigo_fmt} ya existe.")
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# POST /puntos-emision
# =============================================================================

@router.post("/puntos-emision", summary="Crear punto de emisión")
async def crear_punto_emision(
    data:      PuntoEmisionCreate,
    auth_data: dict         = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db),
):
    emisor_id = auth_data["emisor_id"]

    try:
        codigo_estab_fmt = str(data.establecimiento_codigo).zfill(3)

        res_estab = await db.execute(text("""
            SELECT id FROM establecimientos
            WHERE emisor_id = :eid AND codigo = :cod
        """), {"eid": emisor_id, "cod": codigo_estab_fmt})
        estab = res_estab.fetchone()
        if not estab:
            raise HTTPException(status_code=404, detail=f"No existe el establecimiento {codigo_estab_fmt}.")

        res = await db.execute(text("""
            INSERT INTO puntos_emision
                (establecimiento_id, emisor_id, codigo, secuencial_actual,
                 secuenciales, nombre, is_active)
            VALUES (:estab_id, :eid, :cod, 1,
                    '{"FAC":0,"LIQ":0,"NCR":0,"NDB":0,"RET":0}'::jsonb,
                    :nom, true)
            RETURNING id, establecimiento_id, codigo, secuencial_actual,
                      secuenciales, nombre, is_active
        """), {
            "estab_id": estab.id,
            "eid":      emisor_id,
            "cod":      str(data.codigo).zfill(3),
            "nom":      data.nombre or f"Punto {data.codigo}",
        })

        nuevo = res.fetchone()
        await db.commit()
        await _invalidar_estructura(emisor_id)
        return {"ok": True, "mensaje": f"Punto {data.codigo} creado.", "data": dict(nuevo._mapping)}

    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="El punto de emisión ya existe en este establecimiento.")
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# PUT /establecimientos/{id}
# =============================================================================

@router.put("/establecimientos/{estab_id}", summary="Editar establecimiento")
async def editar_establecimiento(
    estab_id:  int,
    data:      EstablecimientoUpdate,
    auth_data: dict         = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db),
):
    emisor_id = auth_data["emisor_id"]

    res = await db.execute(text("""
        UPDATE establecimientos
        SET nombre_comercial = COALESCE(:nom, nombre_comercial),
            direccion        = COALESCE(:dir, direccion),
            is_active        = COALESCE(:act, is_active)
        WHERE id = :id AND emisor_id = :eid
        RETURNING id, codigo, nombre_comercial, direccion, is_active
    """), {
        "nom": data.nombre_comercial,
        "dir": data.direccion,
        "act": data.is_active,
        "id":  estab_id,
        "eid": emisor_id,
    })
    updated = res.fetchone()
    if not updated:
        raise HTTPException(status_code=404, detail="Establecimiento no encontrado.")

    await db.commit()
    await _invalidar_estructura(emisor_id)
    return {"ok": True, "mensaje": "Establecimiento actualizado.", "data": dict(updated._mapping)}


# =============================================================================
# PUT /puntos-emision/{id}
# =============================================================================

@router.put("/puntos-emision/{punto_id}", summary="Editar punto de emisión")
async def editar_punto_emision(
    punto_id:  int,
    data:      PuntoEmisionUpdate,
    auth_data: dict         = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db),
):
    emisor_id = auth_data["emisor_id"]

    res = await db.execute(text("""
        UPDATE puntos_emision pe
        SET nombre    = COALESCE(:nom, pe.nombre),
            is_active = COALESCE(:act, pe.is_active)
        FROM establecimientos e
        WHERE pe.establecimiento_id = e.id
          AND pe.id = :pid AND e.emisor_id = :eid
        RETURNING pe.id, pe.codigo, pe.nombre, pe.is_active
    """), {"nom": data.nombre, "act": data.is_active, "pid": punto_id, "eid": emisor_id})

    updated = res.fetchone()
    if not updated:
        raise HTTPException(status_code=404, detail="Punto de emisión no encontrado.")

    await db.commit()
    await _invalidar_estructura(emisor_id)
    return {"ok": True, "mensaje": "Punto actualizado.", "data": dict(updated._mapping)}


# =============================================================================
# PATCH /puntos-emision/{id}/secuencial
# =============================================================================

@router.patch("/puntos-emision/{punto_id}/secuencial", summary="Corregir secuencial")
async def editar_secuencial(
    punto_id:  int,
    data:      dict,
    auth_data: dict         = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db),
):
    emisor_id = auth_data["emisor_id"]

    # Caso nuevo — secuenciales por tipo en JSONB
    nuevos_secs = data.get("secuenciales")
    if nuevos_secs:
        for tipo, val in nuevos_secs.items():
            if int(val) < 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"El secuencial de {tipo} no puede ser negativo."
                )
        res = await db.execute(text("""
            UPDATE puntos_emision pe
            SET secuenciales = CAST(:secs AS jsonb)
            FROM establecimientos e
            WHERE pe.establecimiento_id = e.id
              AND pe.id = :pid AND e.emisor_id = :eid
            RETURNING pe.id, pe.codigo, pe.secuenciales
        """), {
            "secs": json.dumps(nuevos_secs),
            "pid":  punto_id,
            "eid":  emisor_id,
        })
        updated = res.fetchone()
        if not updated:
            raise HTTPException(status_code=404, detail="Punto no encontrado.")
        await db.commit()
        await _invalidar_estructura(emisor_id)
        return {"ok": True, "mensaje": "Secuenciales actualizados.", "data": dict(updated._mapping)}

    # Caso legacy — secuencial_actual único
    nuevo_sec = data.get("secuencial_actual")
    if nuevo_sec is None or int(nuevo_sec) < 1:
        raise HTTPException(status_code=400, detail="El secuencial debe ser mayor a 0.")

    res = await db.execute(text("""
        UPDATE puntos_emision pe
        SET secuencial_actual = :sec
        FROM establecimientos e
        WHERE pe.establecimiento_id = e.id
          AND pe.id = :pid AND e.emisor_id = :eid
        RETURNING pe.id, pe.codigo, pe.secuencial_actual
    """), {"sec": int(nuevo_sec), "pid": punto_id, "eid": emisor_id})

    updated = res.fetchone()
    if not updated:
        raise HTTPException(status_code=404, detail="Punto no encontrado.")

    await db.commit()
    await _invalidar_estructura(emisor_id)
    return {"ok": True, "mensaje": "Secuencial actualizado.", "data": dict(updated._mapping)}