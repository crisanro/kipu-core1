import hashlib
from fastapi import Header, HTTPException, Depends, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.config import settings
from firebase_admin import auth

# ─── 1. API KEY AUTH (Para clientes externos) ──────────────────────────────────
async def verify_api_key(
    x_api_key: str = Header(None), 
    db: AsyncSession = Depends(get_db)
):
    if not x_api_key:
        raise HTTPException(status_code=401, detail="API Key faltante")

    # Hashear la key
    key_hash = hashlib.sha256(x_api_key.encode('utf-8')).hexdigest()
    
    # Consultar DB
    query = text("SELECT emisor_id, nombre FROM api_keys WHERE key_hash = :hash AND revoked = false")
    result = await db.execute(query, {"hash": key_hash})
    key_data = result.fetchone()

    if not key_data:
        raise HTTPException(status_code=403, detail="API Key inválida o revocada")

    # Actualizar último uso sin bloquear (background update)
    await db.execute(text("UPDATE api_keys SET last_used_at = NOW() WHERE key_hash = :hash"), {"hash": key_hash})
    await db.commit()

    # Retornamos el objeto "usuario" que estará disponible en tu endpoint
    return {"emisor_id": key_data.emisor_id, "role": "external_app", "app_name": key_data.nombre}


# ─── 2. FIREBASE AUTH (Para la App/Web) ────────────────────────────────────────
async def verify_firebase_token(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.lower().startswith('bearer '):
        raise HTTPException(status_code=401, detail="Se requiere sesión activa")
    
    token = auth_header.split(" ")[1]
    
    try:
        decoded_token = auth.verify_id_token(token)
    except Exception as e:
        if "expired" in str(e).lower():
            raise HTTPException(status_code=401, detail="La sesión ha expirado")
        raise HTTPException(status_code=401, detail="Token inválido")

    # Consultar DB
    query = text("SELECT id, emisor_id, email, role FROM profiles WHERE firebase_uid = :uid")
    result = await db.execute(query, {"uid": decoded_token["uid"]})
    profile = result.fetchone()

    if not profile:
        return {"uid": decoded_token["uid"], "email": decoded_token.get("email"), "pending_provision": True}

    return {
        "uid": decoded_token["uid"],
        "profile_id": profile.id,
        "emisor_id": profile.emisor_id,
        "email": profile.email,
        "role": profile.role
    }


# ─── 3. PUBLIC AUTH (Sitio Web Kipu) ──────────────────────────────────────────
async def verify_public_origin(request: Request):
    origin = request.headers.get("origin") or request.headers.get("referer")
    allowed_domains = ['kipu.ec', 'www.kipu.ec']

    if not origin:
        raise HTTPException(status_code=403, detail="No se detectó el origen de la petición.")

    if not any(domain in origin for domain in allowed_domains):
        raise HTTPException(status_code=403, detail="Consulta permitida solo desde el sitio oficial de Kipu.")
    
    return True


# ─── 4. SERVICE AUTH (N8N y WhatsApp) ─────────────────────────────────────────
async def verify_n8n_service(x_n8n_key: str = Header(None)):
    if not x_n8n_key or x_n8n_key != settings.N8N_API_KEY:
        raise HTTPException(status_code=403, detail="Acceso denegado a servicios internos")
    return {"role": "internal_service"}


async def verify_whatsapp_service(
    x_n8n_key: str = Header(None),
    x_whatsapp_number: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    # Reutilizamos la función anterior
    await verify_n8n_service(x_n8n_key)

    if not x_whatsapp_number:
        raise HTTPException(status_code=400, detail="Falta el número de WhatsApp emisor")

    query = text("SELECT emisor_id FROM profiles WHERE whatsapp_number = :phone")
    result = await db.execute(query, {"phone": x_whatsapp_number})
    profile = result.fetchone()

    if not profile:
        raise HTTPException(status_code=404, detail="Número de WhatsApp no vinculado a Kipu.")

    return {"role": "internal_service", "source": "whatsapp", "emisor_id": profile.emisor_id}