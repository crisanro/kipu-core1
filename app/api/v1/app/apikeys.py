# app/api/v1/app/apikeys.py
import secrets
import hashlib
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import verify_firebase_token, validar_y_quemar_pin
from app.core.permisos import verificar_permiso
from app.schemas.seguridad import ApiKeyCreate
from app.core.rate_limit import RateLimit, RateLimitScope
from app.services.audit_service import audit_log

router = APIRouter(tags=["Seguridad"])
MAX_API_KEYS = 5

# ── GET / ─────────────────────────────────────────────────────────────────────
@router.get("", summary="Listar API Keys del emisor")
async def listar_api_keys(
    auth_data: dict         = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db),
    _rl:       None         = Depends(RateLimit(RateLimitScope.GENERAL)),
):
    emisor_id = auth_data.get("emisor_id")
    verificar_permiso(auth_data, "api_keys")
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
                "last_used_at": k.last_used_at,
            }
            for k in keys
        ]
    except Exception as e:
        print(f"❌ Error al listar API Keys: {e}")
        raise HTTPException(status_code=500, detail="Error al obtener las API Keys.")

# ── POST / — Crear ────────────────────────────────────────────────────────────
@router.post("", summary="Generar una nueva API Key", status_code=201)
async def crear_api_key(
    data:      ApiKeyCreate,
    request:   Request,
    auth_data: dict         = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db),
    _rl:       None         = Depends(RateLimit(RateLimitScope.GENERAL)),
):
    emisor_id = auth_data.get("emisor_id")
    verificar_permiso(auth_data, "api_keys")

    res_count = await db.execute(text("""
        SELECT COUNT(*) FROM api_keys WHERE emisor_id = :eid AND revoked = false
    """), {"eid": emisor_id})
    total = res_count.scalar()
    if total >= MAX_API_KEYS:
        raise HTTPException(
            status_code=400,
            detail=f"Has alcanzado el límite de {MAX_API_KEYS} API Keys activas."
        )

    await validar_y_quemar_pin(db, emisor_id, data.pin, "CREAR_TOKEN")

    raw_key    = f"kp_live_{secrets.token_urlsafe(32)}"
    key_hash   = hashlib.sha256(raw_key.encode()).hexdigest()
    key_prefix = raw_key[:8]

    res = await db.execute(text("""
        INSERT INTO api_keys (emisor_id, nombre, key_hash, key_prefix, revoked)
        VALUES (:eid, :nombre, :hash, :prefix, false)
        RETURNING id
    """), {"eid": emisor_id, "nombre": data.nombre, "hash": key_hash, "prefix": key_prefix})
    nueva = res.fetchone()

    await audit_log(
        db        = db,
        auth_data = auth_data,
        accion    = "CREATE",
        entidad   = "api_key",
        entidad_id = str(nueva.id),
        detalle   = {
            "nombre":     data.nombre,
            "key_prefix": key_prefix,
        },
        request   = request,
    )
    await db.commit()

    return {
        "ok":      True,
        "api_key": raw_key,
        "mensaje": "Guarda esta key en un lugar seguro. No podrás verla de nuevo."
    }

# ── DELETE /{key_id} — Revocar ────────────────────────────────────────────────
@router.delete("/{key_id}", summary="Revocar una API Key")
async def revocar_api_key(
    key_id:    int,
    pin:       str,
    request:   Request,
    auth_data: dict         = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db),
    _rl:       None         = Depends(RateLimit(RateLimitScope.GENERAL)),
):
    emisor_id = auth_data.get("emisor_id")
    verificar_permiso(auth_data, "api_keys")

    res = await db.execute(text("""
        SELECT id, nombre, key_prefix FROM api_keys
        WHERE id = :kid AND emisor_id = :eid AND revoked = false
    """), {"kid": key_id, "eid": emisor_id})
    key = res.fetchone()
    if not key:
        raise HTTPException(status_code=404, detail="API Key no encontrada o ya revocada.")

    await validar_y_quemar_pin(db, emisor_id, pin, "ELIMINAR_TOKEN")

    await db.execute(text("""
        UPDATE api_keys SET revoked = true WHERE id = :kid AND emisor_id = :eid
    """), {"kid": key_id, "eid": emisor_id})

    await audit_log(
        db        = db,
        auth_data = auth_data,
        accion    = "REVOKE",
        entidad   = "api_key",
        entidad_id = str(key_id),
        detalle   = {
            "nombre":     key.nombre,
            "key_prefix": key.key_prefix,
        },
        request   = request,
    )
    await db.commit()

    return {"ok": True, "mensaje": "API Key revocada exitosamente."}

# ── GET /sandbox ──────────────────────────────────────────────────────────────
@router.get("/sandbox", summary="Obtener API Key de sandbox")
async def obtener_sandbox_key(
    auth_data: dict         = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db),
):
    emisor_id = auth_data.get("emisor_id")
    verificar_permiso(auth_data, "api_keys")

    res = await db.execute(text("""
        SELECT id, key_prefix, key_plain, created_at, last_used_at
        FROM api_keys
        WHERE emisor_id = :eid AND es_sandbox = true AND revoked = false
        ORDER BY created_at DESC
        LIMIT 1
    """), {"eid": emisor_id})
    key = res.fetchone()
    if not key:
        return {"ok": True, "data": None}

    return {
        "ok": True,
        "data": {
            "id":           key.id,
            "key":          key.key_plain,
            "created_at":   str(key.created_at),
            "last_used_at": str(key.last_used_at) if key.last_used_at else None,
        }
    }

# ── POST /sandbox/regenerar ───────────────────────────────────────────────────
@router.post("/sandbox/regenerar", summary="Regenerar API Key de sandbox")
async def regenerar_sandbox_key(
    request:   Request,
    auth_data: dict         = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db),
):
    emisor_id = auth_data.get("emisor_id")
    verificar_permiso(auth_data, "api_keys")

    await db.execute(text("""
        UPDATE api_keys SET revoked = true
        WHERE emisor_id = :eid AND es_sandbox = true
    """), {"eid": emisor_id})

    raw_key    = f"kp_test_{secrets.token_urlsafe(32)}"
    key_hash   = hashlib.sha256(raw_key.encode()).hexdigest()
    key_prefix = raw_key[:10]

    res = await db.execute(text("""
        INSERT INTO api_keys (emisor_id, nombre, key_hash, key_prefix, key_plain, revoked, es_sandbox)
        VALUES (:eid, 'Sandbox Key', :hash, :prefix, :key_plain, false, true)
        RETURNING id, created_at
    """), {
        "eid":       emisor_id,
        "hash":      key_hash,
        "prefix":    key_prefix,
        "key_plain": raw_key,
    })
    nueva = res.fetchone()

    await audit_log(
        db        = db,
        auth_data = auth_data,
        accion    = "CREATE",
        entidad   = "api_key",
        entidad_id = str(nueva.id),
        detalle   = {
            "tipo":       "sandbox",
            "key_prefix": key_prefix,
            "accion":     "regeneracion",
        },
        request   = request,
    )
    await db.commit()

    return {
        "ok": True,
        "data": {
            "id":           nueva.id,
            "key":          raw_key,
            "created_at":   str(nueva.created_at),
            "last_used_at": None,
        }
    }