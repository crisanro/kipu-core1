# app/api/v1/app/notificaciones.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional
from app.core.database import get_db
from app.core.security import verify_firebase_token
from app.core.cache import cache_get, cache_set, cache_delete

router = APIRouter()

class FCMTokenRequest(BaseModel):
    token:     str
    device_id: Optional[str] = "default"

@router.get("", summary="Listar notificaciones del emisor")
async def listar_notificaciones(
    auth_data: dict          = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db),
):
    emisor_id = auth_data.get("emisor_id")
    if not emisor_id:
        raise HTTPException(status_code=400, detail="EL USUARIO NO TIENE UN EMISOR VINCULADO.")

    cache_key = f"notificaciones:{emisor_id}"
    cached    = await cache_get(cache_key)
    if cached:
        return cached

    res = await db.execute(text("""
        SELECT id, tipo, titulo, mensaje, referencia, leida, created_at
        FROM notificaciones
        WHERE emisor_id = :eid
        ORDER BY created_at DESC
        LIMIT 50
    """), {"eid": emisor_id})
    rows = res.fetchall()

    total_no_leidas = sum(1 for r in rows if not r.leida)

    result = {
        "ok":             True,
        "total":          len(rows),
        "no_leidas":      total_no_leidas,
        "notificaciones": [
            {
                "id":          r.id,
                "type":        r.tipo,
                "title":       r.titulo,
                "description": r.mensaje,
                "redirection": r.referencia,
                "is_read":     r.leida,
                "created_at":  r.created_at,
            }
            for r in rows
        ]
    }
    
    await cache_set(cache_key, result, 60)  # 1 min
    return result


@router.patch("/{notif_id}/leer", summary="Marcar notificación como leída")
async def marcar_leida(
    notif_id:  int,
    auth_data: dict          = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db),
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
    await cache_delete(f"notificaciones:{emisor_id}")
    return {"ok": True, "mensaje": "NOTIFICACIÓN MARCADA COMO LEÍDA."}


@router.patch("/leer-todas", summary="Marcar todas las notificaciones como leídas")
async def marcar_todas_leidas(
    auth_data: dict          = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db),
):
    emisor_id = auth_data.get("emisor_id")
    if not emisor_id:
        raise HTTPException(status_code=400, detail="EL USUARIO NO TIENE UN EMISOR VINCULADO.")

    await db.execute(text("""
        UPDATE notificaciones SET leida = true
        WHERE emisor_id = :eid AND leida = false
    """), {"eid": emisor_id})
    await db.commit()
    await cache_delete(f"notificaciones:{emisor_id}")
    return {"ok": True, "mensaje": "TODAS LAS NOTIFICACIONES MARCADAS COMO LEÍDAS."}


@router.post("/fcm-token", summary="Registrar token FCM en todas las empresas del usuario")
async def registrar_fcm_token(
    data:      FCMTokenRequest,
    auth_data: dict          = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db),
):
    profile_id = auth_data.get("profile_id")
    if not profile_id:
        raise HTTPException(status_code=400, detail="Perfil no encontrado.")

    device_id = data.device_id or "default"

    # Obtener TODAS las empresas del usuario
    res = await db.execute(text("""
        SELECT emisor_id FROM emisor_usuarios
        WHERE profile_id = :pid
    """), {"pid": str(profile_id)})
    emisor_ids = [r.emisor_id for r in res.fetchall()]

    if not emisor_ids:
        return {"ok": True, "empresas_registradas": 0}

    # Registrar token para cada empresa e invalidar su caché de notificaciones
    for emisor_id in emisor_ids:
        await db.execute(text("""
            INSERT INTO fcm_tokens (profile_id, emisor_id, token, device_id, updated_at)
            VALUES (:pid, :eid, :token, :did, NOW())
            ON CONFLICT (profile_id, emisor_id, device_id)
            DO UPDATE SET token = :token, updated_at = NOW()
        """), {
            "pid":   str(profile_id),
            "eid":   emisor_id,
            "token": data.token,
            "did":   device_id,
        })
        await cache_delete(f"notificaciones:{emisor_id}")

    await db.commit()
    print(f"[FCM] ✅ Token registrado en {len(emisor_ids)} empresas — device: {device_id[:8]}...")
    return {"ok": True, "empresas_registradas": len(emisor_ids)}