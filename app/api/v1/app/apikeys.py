# app/api/v1/app/apikeys.py
import secrets
import hashlib
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import verify_firebase_token, validar_y_quemar_pin
from app.schemas.seguridad import ApiKeyCreate
from app.core.rate_limit import RateLimit, RateLimitScope

router = APIRouter(tags=["Seguridad"])

MAX_API_KEYS = 5  # Máximo de keys activas por emisor


@router.get("", summary="Listar API Keys del emisor")
async def listar_api_keys(
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db),
    _rl: None = Depends(RateLimit(RateLimitScope.GENERAL)),
):
    emisor_id = auth_data.get("emisor_id")
    try:
        res = await db.execute(text("""
            SELECT id, nombre, revoked, created_at, last_used_at
            FROM api_keys
            WHERE emisor_id = :eid
            ORDER BY created_at DESC
        """), {"eid": emisor_id})
        keys = res.fetchall()
        return [
            {
                "id":           k.id,
                "nombre":       k.nombre,
                "estado":       "activa" if not k.revoked else "revocada",
                "created_at":   k.created_at,
                "last_used_at": k.last_used_at
            }
            for k in keys
        ]
    except Exception as e:
        print(f"❌ Error al listar API Keys: {e}")
        raise HTTPException(status_code=500, detail="Error al obtener las API Keys.")


@router.post("", summary="Generar una nueva API Key", status_code=201)
async def crear_api_key(
    data: ApiKeyCreate,
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db),
    _rl: None = Depends(RateLimit(RateLimitScope.GENERAL)),
):
    emisor_id = auth_data.get("emisor_id")

    # Verificar límite de keys activas
    res_count = await db.execute(text("""
        SELECT COUNT(*) FROM api_keys
        WHERE emisor_id = :eid AND revoked = false
    """), {"eid": emisor_id})
    total = res_count.scalar()
    if total >= MAX_API_KEYS:
        raise HTTPException(
            status_code=400,
            detail=f"Has alcanzado el límite de {MAX_API_KEYS} API Keys activas. Revoca una antes de crear otra."
        )

    # Validar PIN
    await validar_y_quemar_pin(db, emisor_id, data.pin, "CREAR_TOKEN")

    # Generar key
    raw_key    = f"kp_live_{secrets.token_urlsafe(32)}"
    key_hash   = hashlib.sha256(raw_key.encode()).hexdigest()
    key_prefix = raw_key[:8]  # Primeros caracteres para identificación/auditoría

    await db.execute(text("""
        INSERT INTO api_keys (emisor_id, nombre, key_hash, key_prefix, unlimited, revoked)
        VALUES (:eid, :nombre, :hash, :prefix, false, false)
    """), {"eid": emisor_id, "nombre": data.nombre, "hash": key_hash, "prefix": key_prefix})

    await db.commit()

    return {
        "ok":      True,
        "api_key": raw_key,
        "mensaje": "Guarda esta key en un lugar seguro. No podrás verla de nuevo."
    }


@router.delete("/{key_id}", summary="Revocar una API Key")
async def revocar_api_key(
    key_id: int,
    pin: str,
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db),
    _rl: None = Depends(RateLimit(RateLimitScope.GENERAL)),
):
    emisor_id = auth_data.get("emisor_id")

    # Verificar que la key pertenece al emisor
    res = await db.execute(text("""
        SELECT id FROM api_keys
        WHERE id = :kid AND emisor_id = :eid AND revoked = false
    """), {"kid": key_id, "eid": emisor_id})
    if not res.fetchone():
        raise HTTPException(status_code=404, detail="API Key no encontrada o ya revocada.")

    # Validar PIN
    await validar_y_quemar_pin(db, emisor_id, pin, "ELIMINAR_TOKEN")

    await db.execute(text("""
        UPDATE api_keys SET revoked = true WHERE id = :kid AND emisor_id = :eid
    """), {"kid": key_id, "eid": emisor_id})
    await db.commit()

    return {"ok": True, "mensaje": "API Key revocada exitosamente."}