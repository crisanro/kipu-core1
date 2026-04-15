from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

# Asegúrate de que estas rutas de importación coincidan con tu proyecto
from app.core.database import get_db
from app.core.security import verify_firebase_token
from app.schemas.estructura import EstablecimientoCreate, PuntoEmisionCreate, EstablecimientoUpdate, PuntoEmisionUpdate


router = APIRouter()


@router.get("/", summary="Listar establecimientos y puntos de emisión")
async def listar_estructura(
    auth_data: dict = Depends(verify_firebase_token), 
    db: AsyncSession = Depends(get_db)
):
    """Retorna la estructura jerárquica del emisor logueado."""
    emisor_id = auth_data["emisor_id"]
    
    query = text("""
        SELECT 
            e.id AS estab_id, e.codigo AS estab_codigo, e.nombre_comercial,
            e.direccion, e.is_active AS estab_activo,
            p.id AS punto_id, p.codigo AS punto_codigo, p.nombre AS punto_nombre,
            p.secuencial_actual, p.is_active AS punto_activo
        FROM establecimientos e
        LEFT JOIN puntos_emision p ON p.establecimiento_id = e.id
        WHERE e.emisor_id = :eid
        ORDER BY e.codigo ASC, p.codigo ASC
    """)
    res = await db.execute(query, {"eid": emisor_id})
    rows = res.fetchall()

    estructura_map = {}
    for row in rows:
        if row.estab_id not in estructura_map:
            estructura_map[row.estab_id] = {
                "id": row.estab_id,
                "codigo": row.estab_codigo,
                "nombre_comercial": row.nombre_comercial,
                "direccion": row.direccion,
                "is_active": row.estab_activo,
                "puntos_emision": []
            }
        
        if row.punto_id:
            estructura_map[row.estab_id]["puntos_emision"].append({
                "id": row.punto_id,
                "codigo": row.punto_codigo,
                "nombre": row.punto_nombre,
                "secuencial_actual": row.secuencial_actual,
                "is_active": row.punto_activo
            })

    return {"ok": True, "data": list(estructura_map.values())}


@router.post("/establecimientos", summary="Crear un nuevo establecimiento")
async def crear_establecimiento(
    data: EstablecimientoCreate, 
    auth_data: dict = Depends(verify_firebase_token), 
    db: AsyncSession = Depends(get_db)
):
    """Registra un establecimiento. El código se normaliza a 3 dígitos."""
    emisor_id = auth_data["emisor_id"]
    codigo_fmt = str(data.codigo).zfill(3)

    try:
        res_emisor = await db.execute(
            text("SELECT nombre_comercial, direccion_matriz FROM emisores WHERE id = :eid"), 
            {"eid": emisor_id}
        )
        emisor_data = res_emisor.fetchone()
        
        if not emisor_data:
            raise HTTPException(status_code=404, detail="Emisor no encontrado.")

        final_nombre = data.nombre_comercial or emisor_data.nombre_comercial
        final_direccion = data.direccion or emisor_data.direccion_matriz

        query_insert = text("""
            INSERT INTO establecimientos (emisor_id, codigo, nombre_comercial, direccion, is_active)
            VALUES (:eid, :cod, :nom, :dir, true) 
            RETURNING id, codigo, nombre_comercial, direccion, is_active
        """)
        res = await db.execute(query_insert, {
            "eid": emisor_id, "cod": codigo_fmt, "nom": final_nombre, "dir": final_direccion
        })
        nuevo_estab = res.fetchone()
        await db.commit()

        return {"ok": True, "mensaje": "Establecimiento creado correctamente.", "data": dict(nuevo_estab._mapping)}

    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail=f"El establecimiento {codigo_fmt} ya existe para tu empresa.")
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/establecimientos/{estab_id}", summary="Editar un establecimiento")
async def editar_establecimiento(
    estab_id: int,
    data: EstablecimientoUpdate, 
    auth_data: dict = Depends(verify_firebase_token), 
    db: AsyncSession = Depends(get_db)
):
    """Actualiza los datos (nombre, dirección, estado) de un establecimiento."""
    emisor_id = auth_data["emisor_id"]
    
    query = text("""
        UPDATE establecimientos 
        SET nombre_comercial = COALESCE(:nom, nombre_comercial), 
            direccion = COALESCE(:dir, direccion),
            is_active = COALESCE(:act, is_active)
        WHERE id = :id AND emisor_id = :eid
        RETURNING id, codigo, nombre_comercial, direccion, is_active
    """)
    res = await db.execute(query, {
        "nom": data.nombre_comercial, 
        "dir": data.direccion, 
        "act": data.is_active,
        "id": estab_id, 
        "eid": emisor_id
    })
    updated = res.fetchone()
    
    if not updated:
        raise HTTPException(status_code=404, detail="Establecimiento no encontrado o no te pertenece.")
    
    await db.commit()
    return {"ok": True, "mensaje": "Establecimiento actualizado.", "data": dict(updated._mapping)}


@router.post("/puntos-emision", summary="Crear un punto de emisión")
async def crear_punto_emision(
    data: PuntoEmisionCreate, 
    auth_data: dict = Depends(verify_firebase_token), 
    db: AsyncSession = Depends(get_db)
):
    """Registra un punto de emisión dentro de un establecimiento existente."""
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
        query_insert = text("""
            INSERT INTO puntos_emision (establecimiento_id, codigo, secuencial_actual, nombre, is_active)
            VALUES (:estab_id, :cod, 1, :nom, true) 
            RETURNING id, establecimiento_id, codigo, secuencial_actual, nombre, is_active
        """)
        res = await db.execute(query_insert, {
            "estab_id": estab.id, "cod": str(data.codigo).zfill(3), "nom": nombre_punto
        })
        nuevo_punto = res.fetchone()
        await db.commit()

        return {"ok": True, "mensaje": f"Punto de emisión {data.codigo} creado.", "data": dict(nuevo_punto._mapping)}

    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="El punto de emisión ya existe en este establecimiento.")
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/puntos-emision/{punto_id}", summary="Editar un punto de emisión")
async def editar_punto_emision(
    punto_id: int,
    data: PuntoEmisionUpdate, 
    auth_data: dict = Depends(verify_firebase_token), 
    db: AsyncSession = Depends(get_db)
):
    """Actualiza el nombre o el estado de un punto de emisión."""
    emisor_id = auth_data["emisor_id"]
    
    # Aquí usamos 'pe.is_active' en el COALESCE para no confundir con campos de otras tablas
    query = text("""
        UPDATE puntos_emision pe
        SET nombre = COALESCE(:nom, pe.nombre),
            is_active = COALESCE(:act, pe.is_active)
        FROM establecimientos e
        WHERE pe.establecimiento_id = e.id 
          AND pe.id = :pid 
          AND e.emisor_id = :eid
        RETURNING pe.id, pe.codigo, pe.nombre, pe.is_active
    """)
    res = await db.execute(query, {
        "nom": data.nombre, 
        "act": data.is_active,
        "pid": punto_id, 
        "eid": emisor_id
    })
    updated = res.fetchone()
    
    if not updated:
        raise HTTPException(status_code=404, detail="Punto de emisión no encontrado o no te pertenece.")
    
    await db.commit()
    return {"ok": True, "mensaje": "Punto de emisión actualizado.", "data": dict(updated._mapping)}