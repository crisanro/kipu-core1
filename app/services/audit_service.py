# app/services/audit_service.py
#
# Servicio de auditoría — registra todas las operaciones de escritura.
# Solo lectura para el admin de la empresa.
# Uso: await audit_log(db, auth_data, "CREATE", "cliente", cliente_id, {"nombre": "..."}, request)

import json
from typing import Optional
from fastapi import Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def audit_log(
    db:        AsyncSession,
    auth_data: dict,
    accion:    str,                    # CREATE | UPDATE | DELETE | REVOKE | INVITE | ACTIVATE
    entidad:   str,                    # documento | cliente | producto | usuario | config | api_key | firma | suscripcion | creditos
    entidad_id: Optional[str] = None,  # ID del registro afectado
    detalle:   Optional[dict] = None,  # qué cambió exactamente
    request:   Optional[Request] = None,
):
    """
    Registra una operación de escritura en audit_logs.
    No lanza excepciones — si falla el log, la operación principal no se interrumpe.
    """
    try:
        emisor_id  = auth_data.get("emisor_id")
        profile_id = auth_data.get("profile_id")
        ip         = None

        if request:
            # Intentar obtener IP real detrás de proxy/nginx
            forwarded = request.headers.get("X-Forwarded-For")
            ip = forwarded.split(",")[0].strip() if forwarded else str(request.client.host)

        await db.execute(text("""
            INSERT INTO audit_logs (emisor_id, profile_id, accion, entidad, entidad_id, detalle, ip)
            VALUES (:emisor_id, :profile_id, :accion, :entidad, :entidad_id, CAST(:detalle AS jsonb), :ip)
        """), {
            "emisor_id":  emisor_id,
            "profile_id": str(profile_id) if profile_id else None,
            "accion":     accion.upper(),
            "entidad":    entidad.lower(),
            "entidad_id": str(entidad_id) if entidad_id else None,
            "detalle":    json.dumps(detalle) if detalle else None,
            "ip":         ip,
        })
        # No hacemos commit aquí — se commitea junto con la operación principal

    except Exception as e:
        print(f"[Audit] ⚠️ Error registrando log: {e}")
        # Nunca interrumpir la operación principal por un fallo de auditoría