import os
import hashlib
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.database import get_db
from app.core.security import verify_firebase_token
from app.schemas.seguridad import ApiKeyCreate, RequestPinSchema

router = APIRouter(tags=["Seguridad"])

# --- HELPERS DE LÓGICA (Manteniéndolos en el mismo archivo para simplicidad) ---

async def validar_y_quemar_pin(db: AsyncSession, emisor_id: int, pin: str, tipo_accion: str):
    """
    Busca el PIN en auth_challenges. Si es válido, lo elimina y retorna True.
    Si no, lanza una excepción 403.
    """
    query = text("""
        DELETE FROM auth_challenges 
        WHERE emisor_id = :eid 
          AND pin = :pin 
          AND tipo_accion = :tipo 
          AND expires_at > NOW()
        RETURNING id
    """)
    
    result = await db.execute(query, {
        "eid": emisor_id,
        "pin": pin,
        "tipo": tipo_accion
    })
    
    if not result.fetchone():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="PIN incorrecto, expirado o ya utilizado. Solicite uno nuevo."
        )
    
# --- ENDPOINTS ---

@router.get("/", summary="Listar API Keys del emisor")
async def listar_apikeys(
    auth_data: dict = Depends(verify_firebase_token), 
    db: AsyncSession = Depends(get_db)
):
    emisor_id = auth_data["emisor_id"]

    # Seleccionamos solo las columnas necesarias según tu esquema
    query = text("""
        SELECT 
            id, 
            nombre, 
            revoked, 
            created_at, 
            last_used_at
        FROM api_keys 
        WHERE emisor_id = :eid 
        ORDER BY created_at DESC
    """)

    try:
        res = await db.execute(query, {"eid": emisor_id})
        keys = res.fetchall()

        # Construimos la lista simplificada
        return [
            {
                "id": k.id,
                "nombre": k.nombre,
                "estado": "activa" if not k.revoked else "revocada",
                "created_at": k.created_at,
                "last_used_at": k.last_used_at
            }
            for k in keys
        ]

    except Exception as e:
        print(f"❌ Error al listar API Keys: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Error al obtener el listado de llaves."
        )
    
@router.post("/", summary="Generar una nueva API Key", status_code=201)
async def crear_apikey(
    data: ApiKeyCreate, # Debe incluir 'pin' en el schema
    auth_data: dict = Depends(verify_firebase_token), 
    db: AsyncSession = Depends(get_db)
):
    emisor_id = auth_data["emisor_id"]

    # 1. Validar el PIN enviado desde el bot de WhatsApp
    await validar_y_quemar_pin(db, emisor_id, data.pin, "CREAR_TOKEN")

    # 2. Lógica de generación de llave
    nombre_limpio = data.nombre.strip()
    prefix = 'kp_live'
    secret = os.urandom(24).hex()
    raw_key = f"{prefix}_{secret}"
    key_hash = hashlib.sha256(raw_key.encode('utf-8')).hexdigest()

    try:
        # Nota: 'revoked' tiene default false y 'created_at' tiene default now()
        query = text("""
            INSERT INTO api_keys (emisor_id, key_hash, key_prefix, nombre) 
            VALUES (:eid, :hash, :prefix, :nombre) 
            RETURNING id, created_at
        """)
        
        res = await db.execute(query, {
            "eid": emisor_id, 
            "hash": key_hash, 
            "prefix": prefix, 
            "nombre": nombre_limpio
        })
        nueva_key = res.fetchone()
        await db.commit()

        return {
            "ok": True,
            "mensaje": "¡Guarda tu API Key en un lugar seguro! No podrás verla de nuevo.",
            "key_id": nueva_key.id,
            "api_key": raw_key,
            "created_at": nueva_key.created_at
        }
    except Exception as e:
        await db.rollback()
        # Error de nombre duplicado (Unique constraint)
        if "23505" in str(e):
            raise HTTPException(status_code=400, detail="Ya existe una llave con ese nombre.")
        raise HTTPException(status_code=500, detail="Error al procesar la solicitud.")

@router.delete("/{key_id}", summary="Revocar una API Key")
async def revocar_apikey(
    key_id: int, 
    pin: str, # Se puede pasar por query param (?pin=123456)
    auth_data: dict = Depends(verify_firebase_token), 
    db: AsyncSession = Depends(get_db)
):
    emisor_id = auth_data["emisor_id"]
    
    # 1. Validar PIN de confirmación para eliminación
    await validar_y_quemar_pin(db, emisor_id, pin, "ELIMINAR_TOKEN")

    # 2. Ejecutar la revocación
    query = text("""
        UPDATE api_keys 
        SET revoked = true, expires_at = NOW() 
        WHERE id = :id AND emisor_id = :eid AND revoked = false
        RETURNING id
    """)
    
    res = await db.execute(query, {"id": key_id, "eid": emisor_id})
    
    if not res.fetchone():
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Llave no encontrada, ya revocada o no autorizada."
        )
        
    await db.commit()
    return {"ok": True, "mensaje": "API Key revocada exitosamente."}