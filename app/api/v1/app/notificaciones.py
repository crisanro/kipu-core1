# app/api/v1/app/notificaciones.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import verify_firebase_token

router = APIRouter()


@router.get("/", summary="Listar notificaciones del emisor")
async def listar_notificaciones(
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db),
):
    emisor_id = auth_data.get("emisor_id")
    if not emisor_id:
        raise HTTPException(status_code=400, detail="EL USUARIO NO TIENE UN EMISOR VINCULADO.")

    res = await db.execute(text("""
        SELECT id, tipo, titulo, mensaje, referencia, leida, created_at
        FROM notificaciones
        WHERE emisor_id = :eid
        ORDER BY created_at DESC
    """), {"eid": emisor_id})
    rows = res.fetchall()

    total_no_leidas = sum(1 for r in rows if not r.leida)

    return {
        "ok":             True,
        "total":          len(rows),
        "no_leidas":      total_no_leidas,
        "notificaciones": [
            {
                "id":         r.id,
                "type":       r.tipo,
                "title":     r.titulo,
                "description":    r.mensaje,
                "redirection": r.referencia,
                "is_read":      r.leida,
                "created_at": r.created_at,
            }
            for r in rows
        ]
    }


@router.patch("/{notif_id}/leer", summary="Marcar notificación como leída")
async def marcar_leida(
    notif_id: int,
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db),
):
    emisor_id = auth_data.get("emisor_id")
    if not emisor_id:
        raise HTTPException(status_code=400, detail="EL USUARIO NO TIENE UN EMISOR VINCULADO.")

    res = await db.execute(text("""
        UPDATE notificaciones SET leida = true
        WHERE id = :id AND emisor_id = :eid
        RETURNING id
    """), {"id": notif_id, "eid": emisor_id})

    if not res.fetchone():
        raise HTTPException(status_code=404, detail="NOTIFICACIÓN NO ENCONTRADA.")

    await db.commit()
    return {"ok": True, "mensaje": "NOTIFICACIÓN MARCADA COMO LEÍDA."}


@router.patch("/leer-todas", summary="Marcar todas las notificaciones como leídas")
async def marcar_todas_leidas(
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db),
):
    emisor_id = auth_data.get("emisor_id")
    if not emisor_id:
        raise HTTPException(status_code=400, detail="EL USUARIO NO TIENE UN EMISOR VINCULADO.")

    await db.execute(text("""
        UPDATE notificaciones SET leida = true
        WHERE emisor_id = :eid AND leida = false
    """), {"eid": emisor_id})
    await db.commit()

    return {"ok": True, "mensaje": "TODAS LAS NOTIFICACIONES MARCADAS COMO LEÍDAS."}

