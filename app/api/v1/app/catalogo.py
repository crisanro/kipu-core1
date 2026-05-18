# app/api/v1/app/catalogo.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import verify_firebase_token

router = APIRouter()

@router.get("/ads", summary="Obtener un anuncio balanceado")
async def get_ad(
    auth_data: dict = Depends(verify_firebase_token),  # ← agregar
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(text("""
        SELECT id, titulo, descripcion, imagen_url, cta_url, hex_color, views_count, producto
        FROM app_ads WHERE activo = true ORDER BY views_count ASC LIMIT 1
    """))
    ad = res.fetchone()
    if not ad:
        raise HTTPException(status_code=404, detail="NO HAY ANUNCIOS DISPONIBLES.")
    await db.execute(text("UPDATE app_ads SET views_count = views_count + 1 WHERE id = :id"), {"id": ad.id})
    await db.commit()
    return {
        "id": ad.id, "titulo": ad.titulo, "descripcion": ad.descripcion,
        "imagen_url": ad.imagen_url, "hex_color": ad.hex_color,"producto": ad.producto,
        "click_url": f"/api/v1/app/catalogo/ads/{ad.id}/click"  # ← URL correcta
    }

@router.post("/ads/{ad_id}/click", summary="Registrar clic en anuncio")
async def click_ad(
    ad_id: int,
    auth_data: dict = Depends(verify_firebase_token),  # ← agregar
    db: AsyncSession = Depends(get_db)
):
    emisor_id = auth_data.get("emisor_id")

    res = await db.execute(text("""
        UPDATE app_ads SET clicks_count = clicks_count + 1
        WHERE id = :id AND activo = true RETURNING cta_url
    """), {"id": ad_id})
    row = res.fetchone()
    await db.commit()
    if not row:
        raise HTTPException(status_code=404, detail="ANUNCIO NO ENCONTRADO.")
    return {"cta_url": row.cta_url}


@router.get("/servicios", summary="Obtener un servicio")
async def get_servicio(
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(text("""
        SELECT id, nombre, descripcion, precio, hex_color, imagen_url
        FROM servicios
        WHERE activo = true
        ORDER BY RANDOM()
        LIMIT 1
    """))
    servicio = res.fetchone()
    if not servicio:
        raise HTTPException(status_code=404, detail="NO HAY SERVICIOS DISPONIBLES.")

    return {
        "id":          servicio.id,
        "titulo":      servicio.nombre,
        "descripcion": servicio.descripcion,
        "hex_color": servicio.hex_color,
        "precio":      servicio.precio,
        "imagen_url": servicio.imagen_url
    }


@router.get("/planes", summary="Listar planes de créditos")
async def get_planes(
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db)
):
    res = await db.execute(text("""
        SELECT id, nombre, descripcion, tipo, cantidad, precio, popular
        FROM planes_creditos WHERE activo = true ORDER BY tipo ASC, orden ASC
    """))
    planes = res.fetchall()

    emision = []
    recepcion = []
    for p in planes:
        item = {
            "id": p.id, "nombre": p.nombre, "descripcion": p.descripcion,
            "cantidad": p.cantidad, "precio": p.precio, "popular": p.popular,
        }
        if p.tipo == "emision":
            emision.append(item)
        else:
            recepcion.append(item)

    return {"ok": True, "data": {"emision": emision, "recepcion": recepcion}}