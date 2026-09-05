# app/api/v1/app/productos.py
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from decimal import Decimal
from app.core.database import get_db
from app.core.security import verify_firebase_token
from app.core.cache import get_redis, cache_get, cache_set, cache_delete, cache_clear_prefix
from app.core.permisos import verificar_permiso
from app.services.audit_service import audit_log

router = APIRouter()

TTL_LISTA    = 300
TTL_DETALLE  = 600
TTL_BUSQUEDA = 60

def ck_lista(emisor_id: int) -> str:
    return f"productos:{emisor_id}:lista"
def ck_detalle(emisor_id: int, producto_id: str) -> str:
    return f"productos:{emisor_id}:item:{producto_id}"
def ck_busqueda(emisor_id: int, q: str) -> str:
    return f"productos:{emisor_id}:search:{q.lower().strip()}"
async def invalidar_cache_productos(emisor_id: int):
    await cache_clear_prefix(f"productos:{emisor_id}:")

class ProductoCreate(BaseModel):
    codigo:       Optional[str] = None
    descripcion:  str           = Field(..., min_length=2, max_length=300)
    precio:       Decimal       = Field(..., ge=0)
    tipo_iva:     str           = Field(default="15")
    unidad:       str           = Field(default="UNIDAD")
    stock:        int           = Field(default=-1)
    stock_minimo: int           = Field(default=0, ge=0)

class ProductoUpdate(BaseModel):
    codigo:       Optional[str]     = None
    descripcion:  Optional[str]     = None
    precio:       Optional[Decimal] = None
    tipo_iva:     Optional[str]     = None
    unidad:       Optional[str]     = None
    activo:       Optional[bool]    = None
    stock:        Optional[int]     = None
    stock_minimo: Optional[int]     = None

class StockAjuste(BaseModel):
    cantidad: int = Field(..., description="Positivo=entrada, Negativo=salida")
    motivo:   str = Field(default="Ajuste manual")

# ── GET / ─────────────────────────────────────────────────────────────────────
@router.get("", summary="Listar productos del catálogo")
async def listar_productos(
    response:          Response,
    auth_data:         dict         = Depends(verify_firebase_token),
    db:                AsyncSession = Depends(get_db),
    incluir_inactivos: bool         = Query(False)
):
    response.headers["Cache-Control"] = "no-cache"
    emisor_id = auth_data["emisor_id"]
    verificar_permiso(auth_data, "productos")

    cache_key = ck_lista(emisor_id)
    if not incluir_inactivos:
        cached = await cache_get(cache_key)
        if cached:
            return {"ok": True, "data": cached, "source": "cache"}

    filtro = "" if incluir_inactivos else "AND activo = true"
    res = await db.execute(text(f"""
        SELECT id, codigo, descripcion, precio, tipo_iva, unidad, stock, stock_minimo, activo, created_at
        FROM catalogo_items
        WHERE emisor_id = :eid {filtro}
        ORDER BY descripcion ASC
    """), {"eid": emisor_id})
    rows = res.fetchall()
    data = [
        {
            "id":           str(r.id),
            "codigo":       r.codigo or "",
            "descripcion":  r.descripcion,
            "precio":       float(r.precio),
            "tipo_iva":     r.tipo_iva,
            "unidad":       r.unidad,
            "stock":        r.stock,
            "stock_minimo": r.stock_minimo,
            "activo":       r.activo,
        }
        for r in rows
    ]
    if not incluir_inactivos:
        await cache_set(cache_key, data, TTL_LISTA)
    return {"ok": True, "data": data, "source": "db"}

# ── GET /buscar ───────────────────────────────────────────────────────────────
@router.get("/buscar", summary="Buscar productos por descripción o código")
async def buscar_productos(
    response:  Response,
    q:         str          = Query(..., min_length=1, max_length=100),
    auth_data: dict         = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-cache"
    emisor_id = auth_data["emisor_id"]
    verificar_permiso(auth_data, "productos")

    cache_key = ck_busqueda(emisor_id, q)
    cached = await cache_get(cache_key)
    if cached:
        return {"ok": True, "data": cached, "source": "cache"}

    res = await db.execute(text("""
        SELECT id, codigo, descripcion, precio, tipo_iva, unidad, stock, stock_minimo
        FROM catalogo_items
        WHERE emisor_id = :eid AND activo = true
          AND (LOWER(descripcion) LIKE LOWER(:q) OR LOWER(codigo) LIKE LOWER(:q))
        ORDER BY descripcion ASC
        LIMIT 20
    """), {"eid": emisor_id, "q": f"%{q}%"})
    rows = res.fetchall()
    data = [
        {
            "id":           str(r.id),
            "codigo":       r.codigo or "",
            "descripcion":  r.descripcion,
            "precio":       float(r.precio),
            "tipo_iva":     r.tipo_iva,
            "unidad":       r.unidad,
            "stock":        r.stock,
            "stock_minimo": r.stock_minimo,
        }
        for r in rows
    ]
    await cache_set(cache_key, data, TTL_BUSQUEDA)
    return {"ok": True, "data": data, "source": "db"}

# ── GET /{producto_id} ────────────────────────────────────────────────────────
@router.get("/{producto_id}", summary="Obtener detalle de un producto")
async def obtener_producto(
    producto_id: str,
    response:    Response,
    auth_data:   dict         = Depends(verify_firebase_token),
    db:          AsyncSession = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-cache"
    emisor_id = auth_data["emisor_id"]
    verificar_permiso(auth_data, "productos")

    cache_key = ck_detalle(emisor_id, producto_id)
    cached = await cache_get(cache_key)
    if cached:
        return {"ok": True, "data": cached, "source": "cache"}

    res = await db.execute(text("""
        SELECT id, codigo, descripcion, precio, tipo_iva, unidad, stock, stock_minimo, activo, created_at, updated_at
        FROM catalogo_items WHERE id = :id AND emisor_id = :eid
    """), {"id": producto_id, "eid": emisor_id})
    row = res.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Producto no encontrado.")

    data = {
        "id":           str(row.id),
        "codigo":       row.codigo or "",
        "descripcion":  row.descripcion,
        "precio":       float(row.precio),
        "tipo_iva":     row.tipo_iva,
        "unidad":       row.unidad,
        "stock":        row.stock,
        "stock_minimo": row.stock_minimo,
        "activo":       row.activo,
        "created_at":   str(row.created_at),
        "updated_at":   str(row.updated_at),
    }
    await cache_set(cache_key, data, TTL_DETALLE)
    return {"ok": True, "data": data, "source": "db"}

# ── POST / — Crear ────────────────────────────────────────────────────────────
@router.post("", summary="Crear producto en el catálogo", status_code=201)
async def crear_producto(
    data:      ProductoCreate,
    request:   Request,
    auth_data: dict         = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db),
):
    emisor_id = auth_data["emisor_id"]
    verificar_permiso(auth_data, "productos")

    if data.tipo_iva not in ("0", "5", "15"):
        raise HTTPException(status_code=400, detail="tipo_iva debe ser 0, 5 o 15.")

    try:
        res = await db.execute(text("""
            INSERT INTO catalogo_items (emisor_id, codigo, descripcion, precio, tipo_iva, unidad, stock, stock_minimo)
            VALUES (:eid, :codigo, :desc, :precio, :iva, :unidad, :stock, :stock_minimo)
            RETURNING id, descripcion, precio, tipo_iva, unidad, stock, stock_minimo, created_at
        """), {
            "eid":          emisor_id,
            "codigo":       data.codigo,
            "desc":         data.descripcion,
            "precio":       data.precio,
            "iva":          data.tipo_iva,
            "unidad":       data.unidad,
            "stock":        data.stock,
            "stock_minimo": data.stock_minimo,
        })
        row = res.fetchone()

        await audit_log(
            db         = db,
            auth_data  = auth_data,
            accion     = "CREATE",
            entidad    = "producto",
            entidad_id = str(row.id),
            detalle    = {
                "descripcion":  data.descripcion,
                "precio":       float(data.precio),
                "tipo_iva":     data.tipo_iva,
                "codigo":       data.codigo,
                "stock_minimo": data.stock_minimo,
            },
            request    = request,
        )
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        if "23505" in str(e):
            raise HTTPException(status_code=400, detail="Ya existe un producto con ese código.")
        raise HTTPException(status_code=500, detail="Error al crear el producto.")

    await invalidar_cache_productos(emisor_id)
    return {
        "ok":      True,
        "mensaje": "Producto creado exitosamente.",
        "data": {
            "id":           str(row.id),
            "descripcion":  row.descripcion,
            "precio":       float(row.precio),
            "tipo_iva":     row.tipo_iva,
            "unidad":       row.unidad,
            "stock":        row.stock,
            "stock_minimo": row.stock_minimo,
            "created_at":   str(row.created_at),
        }
    }

# ── PATCH /{producto_id} — Editar ─────────────────────────────────────────────
@router.patch("/{producto_id}", summary="Actualizar producto del catálogo")
async def actualizar_producto(
    producto_id: str,
    data:        ProductoUpdate,
    request:     Request,
    auth_data:   dict         = Depends(verify_firebase_token),
    db:          AsyncSession = Depends(get_db),
):
    emisor_id = auth_data["emisor_id"]
    verificar_permiso(auth_data, "productos")

    res = await db.execute(text("""
        SELECT id FROM catalogo_items WHERE id = :id AND emisor_id = :eid
    """), {"id": producto_id, "eid": emisor_id})
    if not res.fetchone():
        raise HTTPException(status_code=404, detail="Producto no encontrado.")

    if data.tipo_iva and data.tipo_iva not in ("0", "5", "15"):
        raise HTTPException(status_code=400, detail="tipo_iva debe ser 0, 5 o 15.")

    campos = []
    params = {"id": producto_id, "eid": emisor_id}
    if data.codigo       is not None: campos.append("codigo = :codigo");       params["codigo"]       = data.codigo
    if data.descripcion is not None: campos.append("descripcion = :desc");   params["desc"]         = data.descripcion
    if data.precio       is not None: campos.append("precio = :precio");       params["precio"]       = data.precio
    if data.tipo_iva     is not None: campos.append("tipo_iva = :iva");        params["iva"]          = data.tipo_iva
    if data.unidad       is not None: campos.append("unidad = :unidad");       params["unidad"]       = data.unidad
    if data.activo       is not None: campos.append("activo = :activo");       params["activo"]       = data.activo
    if data.stock        is not None: campos.append("stock = :stock");         params["stock"]        = data.stock
    if data.stock_minimo is not None: campos.append("stock_minimo = :stock_minimo"); params["stock_minimo"] = data.stock_minimo

    if not campos:
        raise HTTPException(status_code=400, detail="No hay campos para actualizar.")

    campos.append("updated_at = NOW()")

    try:
        await db.execute(text(f"""
            UPDATE catalogo_items SET {', '.join(campos)}
            WHERE id = :id AND emisor_id = :eid
        """), params)

        await audit_log(
            db         = db,
            auth_data  = auth_data,
            accion     = "UPDATE",
            entidad    = "producto",
            entidad_id = producto_id,
            detalle    = data.model_dump(exclude_none=True),
            request    = request,
        )
        await db.commit()
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Error al actualizar el producto.")

    await invalidar_cache_productos(emisor_id)
    return {"ok": True, "mensaje": "Producto actualizado exitosamente."}

# ── PATCH /{producto_id}/stock ────────────────────────────────────────────────
@router.patch("/{producto_id}/stock", summary="Ajustar stock manualmente")
async def ajustar_stock(
    producto_id: str,
    data:        StockAjuste,
    request:     Request,
    auth_data:   dict         = Depends(verify_firebase_token),
    db:          AsyncSession = Depends(get_db),
):
    emisor_id = auth_data["emisor_id"]
    verificar_permiso(auth_data, "productos")

    res = await db.execute(text("""
        UPDATE catalogo_items
        SET stock = GREATEST(0, stock + :cantidad), updated_at = NOW()
        WHERE id = :id AND emisor_id = :eid AND stock != -1
        RETURNING id, stock
    """), {"id": producto_id, "eid": emisor_id, "cantidad": data.cantidad})
    row = res.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Producto no encontrado o no maneja stock.")

    await audit_log(
        db         = db,
        auth_data  = auth_data,
        accion     = "UPDATE",
        entidad    = "producto",
        entidad_id = producto_id,
        detalle    = {
            "accion":      "ajuste_stock",
            "cantidad":    data.cantidad,
            "motivo":      data.motivo,
            "stock_nuevo": row.stock,
        },
        request    = request,
    )
    await db.commit()
    await invalidar_cache_productos(emisor_id)
    return {"ok": True, "stock_actual": row.stock}

# ── DELETE /{producto_id} ─────────────────────────────────────────────────────
@router.delete("/{producto_id}", summary="Desactivar producto del catálogo")
async def desactivar_producto(
    producto_id: str,
    request:     Request,
    auth_data:   dict         = Depends(verify_firebase_token),
    db:          AsyncSession = Depends(get_db),
):
    emisor_id = auth_data["emisor_id"]
    verificar_permiso(auth_data, "productos")

    res = await db.execute(text("""
        SELECT descripcion FROM catalogo_items
        WHERE id = :id AND emisor_id = :eid AND activo = true
    """), {"id": producto_id, "eid": emisor_id})
    producto = res.fetchone()
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado o ya desactivado.")

    await db.execute(text("""
        UPDATE catalogo_items SET activo = false, updated_at = NOW()
        WHERE id = :id AND emisor_id = :eid
    """), {"id": producto_id, "eid": emisor_id})

    await audit_log(
        db         = db,
        auth_data  = auth_data,
        accion     = "DELETE",
        entidad    = "producto",
        entidad_id = producto_id,
        detalle    = {"descripcion": producto.descripcion},
        request    = request,
    )
    await db.commit()
    await invalidar_cache_productos(emisor_id)
    return {"ok": True, "mensaje": "Producto desactivado exitosamente."}