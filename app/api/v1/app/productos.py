# app/api/v1/app/productos.py
#
# CRUD de productos y servicios del catálogo del emisor.
# Cache en Redis para no golpear la DB en cada búsqueda.
# El frontend debe usar Cache-Control headers para cache del lado del cliente.

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from decimal import Decimal

from app.core.database import get_db
from app.core.security import verify_firebase_token
from app.core.cache import get_redis, cache_get, cache_set, cache_delete, cache_clear_prefix


router = APIRouter()

# ── TTLs ──────────────────────────────────────────────────────────────────────
TTL_LISTA    = 300   # 5 min — lista completa
TTL_DETALLE  = 600   # 10 min — detalle de un producto
TTL_BUSQUEDA = 60    # 1 min — resultados de búsqueda (cambian más seguido)

# ── Cache Keys ─────────────────────────────────────────────────────────────────
def ck_lista(emisor_id: int) -> str:
    return f"productos:{emisor_id}:lista"

def ck_detalle(emisor_id: int, producto_id: str) -> str:
    return f"productos:{emisor_id}:item:{producto_id}"

def ck_busqueda(emisor_id: int, q: str) -> str:
    return f"productos:{emisor_id}:search:{q.lower().strip()}"

async def invalidar_cache_productos(emisor_id: int):
    """Invalida todo el cache de productos de un emisor."""
    await cache_clear_prefix(f"productos:{emisor_id}:")


# ── Schemas ────────────────────────────────────────────────────────────────────
class ProductoCreate(BaseModel):
    codigo:      Optional[str]  = None
    descripcion: str            = Field(..., min_length=2, max_length=300)
    precio:      Decimal        = Field(..., ge=0)
    tipo_iva:    str            = Field(default="15")
    unidad:      str            = Field(default="UNIDAD")
    stock:       int            = Field(default=-1)  # -1 = sin control

class ProductoUpdate(BaseModel):
    codigo:      Optional[str]     = None
    descripcion: Optional[str]     = None
    precio:      Optional[Decimal] = None
    tipo_iva:    Optional[str]     = None
    unidad:      Optional[str]     = None
    activo:      Optional[bool]    = None
    stock:       Optional[int]     = None

class StockAjuste(BaseModel):
    cantidad:  int = Field(..., description="Positivo=entrada, Negativo=salida")
    motivo:    str = Field(default="Ajuste manual")

    
# ── GET / — Listar todos los productos activos ────────────────────────────────
@router.get("", summary="Listar productos del catálogo")
async def listar_productos(
    response: Response,
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db),
    incluir_inactivos: bool = Query(False)
):
    emisor_id = auth_data["emisor_id"]
    cache_key = ck_lista(emisor_id)

    # Cache del servidor
    if not incluir_inactivos:
        cached = await cache_get(cache_key)
        if cached:
            # Cache del cliente — 2 minutos
            response.headers["Cache-Control"] = "no-cache"
            return {"ok": True, "data": cached, "source": "cache"}

    filtro = "" if incluir_inactivos else "AND activo = true"
    res = await db.execute(text(f"""
        SELECT id, codigo, descripcion, precio, tipo_iva, unidad, stock, activo, created_at
        FROM catalogo_items
        WHERE emisor_id = :eid {filtro}
        ORDER BY descripcion ASC
    """), {"eid": emisor_id})
    rows = res.fetchall()

    data = [
        {
            "id":          str(r.id),
            "codigo":      r.codigo or "",
            "descripcion": r.descripcion,
            "precio":      float(r.precio),
            "tipo_iva":    r.tipo_iva,
            "unidad":      r.unidad,
            "stock":       r.stock,
            "activo":      r.activo,
        }
        for r in rows
    ]

    if not incluir_inactivos:
        await cache_set(cache_key, data, TTL_LISTA)

    response.headers["Cache-Control"] = "private, max-age=120"
    return {"ok": True, "data": data, "source": "db"}


# ── GET /buscar — Búsqueda rápida para el buscador al facturar ─────────────────
@router.get("/buscar", summary="Buscar productos por descripción o código")
async def buscar_productos(
    response: Response,
    q: str = Query(..., min_length=1, max_length=100),
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db),
):
    emisor_id = auth_data["emisor_id"]
    cache_key = ck_busqueda(emisor_id, q)

    cached = await cache_get(cache_key)
    if cached:
        response.headers["Cache-Control"] = "private, max-age=60"
        return {"ok": True, "data": cached, "source": "cache"}

    res = await db.execute(text("""
        SELECT id, codigo, descripcion, precio, tipo_iva, unidad, stock
        FROM catalogo_items
        WHERE emisor_id = :eid
          AND activo = true
          AND (
              LOWER(descripcion) LIKE LOWER(:q)
              OR LOWER(codigo)   LIKE LOWER(:q)
          )
        ORDER BY descripcion ASC
        LIMIT 20
    """), {"eid": emisor_id, "q": f"%{q}%"})
    rows = res.fetchall()

    data = [
        {
            "id":          str(r.id),
            "codigo":      r.codigo or "",
            "descripcion": r.descripcion,
            "precio":      float(r.precio),
            "tipo_iva":    r.tipo_iva,
            "unidad":      r.unidad,
            "stock":       r.stock,
        }
        for r in rows
    ]

    await cache_set(cache_key, data, TTL_BUSQUEDA)
    response.headers["Cache-Control"] = "private, max-age=60"
    return {"ok": True, "data": data, "source": "db"}


# ── GET /{id} — Detalle de un producto ────────────────────────────────────────
@router.get("/{producto_id}", summary="Obtener detalle de un producto")
async def obtener_producto(
    producto_id: str,
    response: Response,
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db),
):
    emisor_id = auth_data["emisor_id"]
    cache_key = ck_detalle(emisor_id, producto_id)

    cached = await cache_get(cache_key)
    if cached:
        response.headers["Cache-Control"] = "private, max-age=300"
        return {"ok": True, "data": cached, "source": "cache"}

    res = await db.execute(text("""
        SELECT id, codigo, descripcion, precio, tipo_iva, unidad, stock, activo, created_at, updated_at
        FROM catalogo_items
        WHERE id = :id AND emisor_id = :eid
    """), {"id": producto_id, "eid": emisor_id})
    row = res.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Producto no encontrado.")

    data = {
        "id":          str(row.id),
        "codigo":      row.codigo or "",
        "descripcion": row.descripcion,
        "precio":      float(row.precio),
        "tipo_iva":    row.tipo_iva,
        "unidad":      row.unidad,
        "stock":       row.stock,
        "activo":      row.activo,
        "created_at":  str(row.created_at),
        "updated_at":  str(row.updated_at),
    }

    await cache_set(cache_key, data, TTL_DETALLE)
    response.headers["Cache-Control"] = "private, max-age=300"
    return {"ok": True, "data": data, "source": "db"}


# ── POST / — Crear producto ────────────────────────────────────────────────────
@router.post("", summary="Crear producto en el catálogo", status_code=201)
async def crear_producto(
    data: ProductoCreate,
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db),
):
    emisor_id = auth_data["emisor_id"]

    if data.tipo_iva not in ("0", "5", "15"):
        raise HTTPException(status_code=400, detail="tipo_iva debe ser 0, 5 o 15.")

    try:
        res = await db.execute(text("""
            INSERT INTO catalogo_items (emisor_id, codigo, descripcion, precio, tipo_iva, unidad, stock)
            VALUES (:eid, :codigo, :desc, :precio, :iva, :unidad, :stock)
            RETURNING id, descripcion, precio, tipo_iva, unidad, stock, created_at
        """), {
            "eid":    emisor_id,
            "codigo": data.codigo,
            "desc":   data.descripcion,
            "precio": data.precio,
            "iva":    data.tipo_iva,
            "unidad": data.unidad,
            "stock":  data.stock,
        })
        row = res.fetchone()
        await db.commit()
    except Exception as e:
        await db.rollback()
        if "23505" in str(e):
            raise HTTPException(status_code=400, detail="Ya existe un producto con ese código.")
        raise HTTPException(status_code=500, detail="Error al crear el producto.")

    # Invalidar cache de lista
    await invalidar_cache_productos(emisor_id)

    return {
        "ok":      True,
        "mensaje": "Producto creado exitosamente.",
        "data": {
            "id":          str(row.id),
            "descripcion": row.descripcion,
            "precio":      float(row.precio),
            "tipo_iva":    row.tipo_iva,
            "unidad":      row.unidad,
            "stock":       row.stock,
            "created_at":  str(row.created_at),
        }
    }


# ── PATCH /{id} — Editar producto ─────────────────────────────────────────────
@router.patch("/{producto_id}", summary="Actualizar producto del catálogo")
async def actualizar_producto(
    producto_id: str,
    data: ProductoUpdate,
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db),
):
    emisor_id = auth_data["emisor_id"]

    # Verificar que existe y pertenece al emisor
    res = await db.execute(text("""
        SELECT id FROM catalogo_items WHERE id = :id AND emisor_id = :eid
    """), {"id": producto_id, "eid": emisor_id})
    if not res.fetchone():
        raise HTTPException(status_code=404, detail="Producto no encontrado.")

    if data.tipo_iva and data.tipo_iva not in ("0", "5", "15"):
        raise HTTPException(status_code=400, detail="tipo_iva debe ser 0, 5 o 15.")

    # Construir SET dinámico solo con campos enviados
    campos = []
    params = {"id": producto_id, "eid": emisor_id}

    if data.codigo      is not None: campos.append("codigo = :codigo");      params["codigo"]      = data.codigo
    if data.descripcion is not None: campos.append("descripcion = :desc");   params["desc"]        = data.descripcion
    if data.precio      is not None: campos.append("precio = :precio");      params["precio"]      = data.precio
    if data.tipo_iva    is not None: campos.append("tipo_iva = :iva");       params["iva"]         = data.tipo_iva
    if data.unidad      is not None: campos.append("unidad = :unidad");      params["unidad"]      = data.unidad
    if data.activo      is not None: campos.append("activo = :activo");      params["activo"]      = data.activo
    if data.stock       is not None: campos.append("stock = :stock");        params["stock"]       = data.stock

    if not campos:
        raise HTTPException(status_code=400, detail="No hay campos para actualizar.")

    campos.append("updated_at = NOW()")

    try:
        await db.execute(text(f"""
            UPDATE catalogo_items SET {', '.join(campos)}
            WHERE id = :id AND emisor_id = :eid
        """), params)
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Error al actualizar el producto.")

    # Invalidar cache
    await invalidar_cache_productos(emisor_id)

    return {"ok": True, "mensaje": "Producto actualizado exitosamente."}


# ── PATCH /{id}/stock — Ajuste manual de stock ────────────────────────────────
@router.patch("/{producto_id}/stock", summary="Ajustar stock manualmente")
async def ajustar_stock(
    producto_id: str,
    data: StockAjuste,
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db),
):
    emisor_id = auth_data["emisor_id"]
    res = await db.execute(text("""
        UPDATE catalogo_items
        SET stock = GREATEST(0, stock + :cantidad),
            updated_at = NOW()
        WHERE id = :id AND emisor_id = :eid AND stock != -1
        RETURNING id, stock
    """), {"id": producto_id, "eid": emisor_id, "cantidad": data.cantidad})
    row = res.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Producto no encontrado o no maneja stock.")
    await db.commit()
    await invalidar_cache_productos(emisor_id)
    return {"ok": True, "stock_actual": row.stock}


# ── DELETE /{id} — Desactivar producto (soft delete) ──────────────────────────
@router.delete("/{producto_id}", summary="Desactivar producto del catálogo")
async def desactivar_producto(
    producto_id: str,
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db),
):
    emisor_id = auth_data["emisor_id"]

    res = await db.execute(text("""
        UPDATE catalogo_items SET activo = false, updated_at = NOW()
        WHERE id = :id AND emisor_id = :eid AND activo = true
        RETURNING id
    """), {"id": producto_id, "eid": emisor_id})

    if not res.fetchone():
        raise HTTPException(status_code=404, detail="Producto no encontrado o ya desactivado.")

    await db.commit()
    await invalidar_cache_productos(emisor_id)

    return {"ok": True, "mensaje": "Producto desactivado exitosamente."}