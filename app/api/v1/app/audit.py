# app/api/v1/app/audit.py
#
# Endpoints de auditoría — solo admin.
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import verify_firebase_token
from app.core.permisos import verificar_admin

router = APIRouter()

@router.get("", summary="Historial de auditoría de la empresa")
async def listar_audit_logs(
    auth_data:  dict         = Depends(verify_firebase_token),
    db:         AsyncSession = Depends(get_db),
    entidad:    Optional[str] = Query(None, description="documento | cliente | producto | usuario | config | api_key | firma"),
    accion:     Optional[str] = Query(None, description="CREATE | UPDATE | DELETE | REVOKE | INVITE | ACTIVATE"),
    profile_id: Optional[str] = Query(None, description="Filtrar por usuario"),
    fecha_inicio: Optional[str] = Query(None),
    fecha_fin:    Optional[str] = Query(None),
    limit:      int           = Query(50, le=200),
    offset:     int           = Query(0),
):
    emisor_id = auth_data.get("emisor_id")
    if not emisor_id:
        raise HTTPException(status_code=400, detail="Emisor no vinculado.")
    verificar_admin(auth_data)

    filtros = "WHERE al.emisor_id = :eid"
    params  = {"eid": emisor_id}

    if entidad:
        filtros += " AND al.entidad = :entidad"
        params["entidad"] = entidad.lower()

    if accion:
        filtros += " AND al.accion = :accion"
        params["accion"] = accion.upper()

    if profile_id:
        filtros += " AND al.profile_id = :pid"
        params["pid"] = profile_id

    if fecha_inicio:
        filtros += " AND al.created_at >= :fi"
        params["fi"] = fecha_inicio

    if fecha_fin:
        filtros += " AND al.created_at <= :ff"
        params["ff"] = fecha_fin

    params["limit"]  = limit
    params["offset"] = offset

    res = await db.execute(text(f"""
        SELECT
            al.id,
            al.accion,
            al.entidad,
            al.entidad_id,
            al.detalle,
            al.ip,
            al.created_at,
            p.email      AS usuario_email,
            p.full_name  AS usuario_nombre
        FROM audit_logs al
        LEFT JOIN profiles p ON p.id = al.profile_id
        {filtros}
        ORDER BY al.created_at DESC
        LIMIT :limit OFFSET :offset
    """), params)
    rows = res.fetchall()

    # Total para paginación
    res_total = await db.execute(text(f"""
        SELECT COUNT(*) FROM audit_logs al {filtros}
    """), {k: v for k, v in params.items() if k not in ("limit", "offset")})
    total = res_total.scalar()

    return {
        "ok":    True,
        "total": total,
        "data": [
            {
                "id":             str(r.id),
                "accion":         r.accion,
                "entidad":        r.entidad,
                "entidad_id":     r.entidad_id,
                "detalle":        r.detalle,
                "ip":             r.ip,
                "created_at":     str(r.created_at),
                "usuario_email":  r.usuario_email,
                "usuario_nombre": r.usuario_nombre or "",
            }
            for r in rows
        ]
    }