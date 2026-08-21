import hashlib
from fastapi import Header, HTTPException, Depends, Request, status
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

    # Detectar sandbox por prefix
    es_sandbox = x_api_key.startswith("kp_test_")

    key_hash = hashlib.sha256(x_api_key.encode('utf-8')).hexdigest()
    
    query = text("""
        SELECT id, emisor_id, nombre, es_sandbox
        FROM api_keys 
        WHERE key_hash = :hash AND revoked = false
    """)
    result = await db.execute(query, {"hash": key_hash})
    key_data = result.fetchone()

    if not key_data:
        raise HTTPException(status_code=403, detail="API Key inválida o revocada")

    # Validar que el prefix coincida con es_sandbox en DB
    if key_data.es_sandbox != es_sandbox:
        raise HTTPException(
            status_code=403,
            detail="API Key inválida — prefix no coincide con el tipo de key."
        )

    await db.execute(
        text("UPDATE api_keys SET last_used_at = NOW() WHERE key_hash = :hash"),
        {"hash": key_hash}
    )
    await db.commit()

    return {
        "emisor_id":  key_data.emisor_id,
        "api_key_id": key_data.id,
        "es_sandbox": es_sandbox,
        "unlimited":  es_sandbox,  # sandbox nunca descuenta créditos
        "role":       "external_app",
        "app_name":   key_data.nombre
    }


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

    # Consultar DB con soporte para multi-empresa ordenado por fecha de vinculación
    query = text("""
        SELECT p.id, p.email, p.role,
               eu.emisor_id, eu.rol as emisor_rol
        FROM profiles p
        LEFT JOIN emisor_usuarios eu ON eu.profile_id = p.id
        WHERE p.firebase_uid = :uid
        ORDER BY eu.created_at ASC
        LIMIT 1
    """)
    result = await db.execute(query, {"uid": decoded_token["uid"]})
    profile = result.fetchone()

    if not profile:
        return {
            "uid":               decoded_token["uid"],
            "email":             decoded_token.get("email"),
            "pending_provision": True
        }

    return {
        "uid":        decoded_token["uid"],
        "profile_id": profile.id,
        "emisor_id":  profile.emisor_id,
        "email":      profile.email,
        "role":       profile.role or profile.emisor_rol
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

    query = text("""
        SELECT eu.emisor_id 
        FROM profiles p
        JOIN emisor_usuarios eu ON eu.profile_id = p.id
        WHERE p.whatsapp_number = :phone
        LIMIT 1
    """)
    result = await db.execute(query, {"phone": x_whatsapp_number})
    relacion = result.fetchone()

    if not relacion:
        raise HTTPException(status_code=404, detail="Número de WhatsApp no vinculado a Kipu.")

    return {"role": "internal_service", "source": "whatsapp", "emisor_id": relacion.emisor_id}


async def validar_y_quemar_pin(db: AsyncSession, emisor_id: int, pin: str, tipo_accion: str):
    query = text("""
        DELETE FROM auth_challenges
        WHERE emisor_id = :eid
          AND pin       = :pin
          AND tipo_accion = :tipo
          AND expires_at > NOW()
        RETURNING id
    """)
    result = await db.execute(query, {"eid": emisor_id, "pin": pin, "tipo": tipo_accion})
    if not result.fetchone():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="PIN incorrecto, expirado o ya utilizado. Solicite uno nuevo."
        )


async def verify_internal_key(
    x_internal_key: str = Header(None, alias="X-Internal-Key"),
):
    if not x_internal_key or x_internal_key != settings.INTERNAL_API_KEY:
        raise HTTPException(status_code=403, detail="Clave interna inválida.")
    return {
        "emisor_id":  settings.KIPU_EMISOR_ID,
        "unlimited":  True,
        "role":       "internal_service",
        "api_key_id": None,
    }