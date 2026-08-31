# app/api/v1/app/usuarios.py
import json
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, EmailStr
from app.core.database import get_db
from app.core.security import verify_firebase_token
from app.core.cache import cache_get, cache_set, cache_delete, invalidate_emisor
from app.core.permisos import verificar_permiso, verificar_admin, permisos_para_rol, PERMISOS_DISPONIBLES
from app.services.mail_service import mail_service
from app.services.audit_service import audit_log

router = APIRouter()
TTL_EMPRESAS = 300  # 5 min

# ── Schemas ────────────────────────────────────────────────────────────────────
class InvitarUsuarioRequest(BaseModel):
    email:    EmailStr
    rol:      str  = "emisor"
    permisos: dict = {}

class CambiarEmpresaRequest(BaseModel):
    emisor_id: int

class ActualizarPermisosRequest(BaseModel):
    permisos: dict

# ── GET /empresas ──────────────────────────────────────────────────────────────
@router.get("/empresas", summary="Listar mis empresas")
async def listar_empresas(
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db),
):
    profile_id = auth_data.get("profile_id")
    if not profile_id:
        return {"ok": True, "data": [], "role": None}

    cache_key = f"usuario:{profile_id}:empresas"
    cached    = await cache_get(cache_key)
    if cached:
        return cached

    res = await db.execute(text("""
        SELECT
            e.id, e.ruc, e.razon_social, e.nombre_comercial,
            e.ambiente, e.p12_path, e.p12_expiration, e.tipo_emisor,
            eu.rol, eu.permisos,
            COALESCE(uc.balance, 0)  AS balance_api,
            s.estado                 AS sub_estado,
            s.plan                   AS sub_plan,
            s.current_period_end,
            p.role                   AS profile_role
        FROM emisor_usuarios eu
        JOIN emisores e         ON e.id = eu.emisor_id
        JOIN profiles p         ON p.id = eu.profile_id
        LEFT JOIN user_credits  uc ON uc.emisor_id = e.id
        LEFT JOIN subscriptions s  ON s.emisor_id  = e.id
        WHERE eu.profile_id = :pid
        ORDER BY e.razon_social ASC
    """), {"pid": str(profile_id)})
    rows = res.fetchall()

    data = [
        {
            "id":               r.id,
            "ruc":              r.ruc,
            "razon_social":     r.razon_social,
            "nombre_comercial": r.nombre_comercial or "",
            "ambiente":         r.ambiente,
            "tipo_emisor":      r.tipo_emisor,
            "firma_ok":         bool(r.p12_path),
            "rol":              r.rol,
            "permisos":         r.permisos or {},
            "balance_api":      r.balance_api,
            "suscripcion_activa": r.sub_estado in ("ACTIVO", "TRIAL"),
            "suscripcion": {
                "activa": r.sub_estado in ("ACTIVO", "TRIAL"),
                "estado": r.sub_estado,
                "plan":   r.sub_plan,
            },
        }
        for r in rows
    ]

    profile_role = rows[0].profile_role if rows else None
    response = {"ok": True, "data": data, "role": profile_role}
    await cache_set(cache_key, response, TTL_EMPRESAS)
    return response

# ── POST /empresas/cambiar ─────────────────────────────────────────────────────
@router.post("/empresas/cambiar", summary="Cambiar empresa activa")
async def cambiar_empresa(
    data:      CambiarEmpresaRequest,
    auth_data: dict = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db),
):
    profile_id = auth_data.get("profile_id")
    if not profile_id:
        raise HTTPException(status_code=400, detail="Perfil no encontrado.")

    res = await db.execute(text("""
        SELECT eu.rol, eu.permisos, e.ruc, e.razon_social, e.ambiente, e.tipo_emisor,
               COALESCE(uc.balance, 0) AS balance_api,
               s.estado AS sub_estado, s.plan AS sub_plan
        FROM emisor_usuarios eu
        JOIN emisores e         ON e.id = eu.emisor_id
        LEFT JOIN user_credits  uc ON uc.emisor_id = e.id
        LEFT JOIN subscriptions s  ON s.emisor_id  = e.id
        WHERE eu.profile_id = :pid AND eu.emisor_id = :eid
    """), {"pid": str(profile_id), "eid": data.emisor_id})
    row = res.fetchone()
    if not row:
        raise HTTPException(status_code=403, detail="No tienes acceso a esa empresa.")

    return {
        "ok":      True,
        "mensaje": "Empresa cambiada exitosamente.",
        "data": {
            "emisor_id":          data.emisor_id,
            "ruc":                row.ruc,
            "razon_social":       row.razon_social,
            "ambiente":           row.ambiente,
            "tipo_emisor":        row.tipo_emisor,
            "rol":                row.rol,
            "permisos":           row.permisos or {},
            "balance_api":        row.balance_api,
            "suscripcion_activa": row.sub_estado in ("ACTIVO", "TRIAL"),
            "suscripcion": {
                "activa": row.sub_estado in ("ACTIVO", "TRIAL"),
                "estado": row.sub_estado,
                "plan":   row.sub_plan,
            },
        }
    }

# ── GET /empresas/{emisor_id}/usuarios ────────────────────────────────────────
@router.get("/empresas/{emisor_id}/usuarios", summary="Listar usuarios de mi empresa")
async def listar_usuarios_empresa(
    emisor_id: int,
    auth_data: dict = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db),
):
    verificar_permiso(auth_data, "usuarios")

    cache_key = f"empresa:{emisor_id}:usuarios"
    cached    = await cache_get(cache_key)
    if cached:
        return {"ok": True, "data": cached}

    res = await db.execute(text("""
        SELECT p.id, p.email, p.full_name, eu.rol, eu.permisos, eu.created_at
        FROM emisor_usuarios eu
        JOIN profiles p ON p.id = eu.profile_id
        WHERE eu.emisor_id = :eid
        ORDER BY eu.created_at ASC
    """), {"eid": emisor_id})
    rows = res.fetchall()

    data = [
        {
            "profile_id": str(r.id),
            "email":      r.email,
            "nombre":     r.full_name or "",
            "rol":        r.rol,
            "permisos":   r.permisos or {},
            "desde":      str(r.created_at),
        }
        for r in rows
    ]
    await cache_set(cache_key, data, TTL_EMPRESAS)
    return {"ok": True, "data": data}

# ── POST /empresas/{emisor_id}/invitar ────────────────────────────────────────
@router.post("/empresas/{emisor_id}/invitar", summary="Invitar usuario a mi empresa")
async def invitar_usuario(
    emisor_id: int,
    data:      InvitarUsuarioRequest,
    request:   Request,
    auth_data: dict = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db),
):
    profile_id = auth_data.get("profile_id")
    verificar_permiso(auth_data, "usuarios")

    if data.rol not in ("admin", "contador", "emisor"):
        raise HTTPException(status_code=400, detail="Rol inválido. Usa admin, contador o emisor.")

    permisos_finales = data.permisos if data.permisos else permisos_para_rol(data.rol)

    for p in permisos_finales:
        if p not in PERMISOS_DISPONIBLES:
            raise HTTPException(status_code=400, detail=f"Permiso inválido: {p}")

    res_profile = await db.execute(text("""
        SELECT id, full_name FROM profiles WHERE LOWER(email) = LOWER(:email)
    """), {"email": data.email})
    perfil_existente = res_profile.fetchone()

    res_empresa = await db.execute(text("""
        SELECT razon_social FROM emisores WHERE id = :eid
    """), {"eid": emisor_id})
    empresa = res_empresa.fetchone()
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa no encontrada.")

    if perfil_existente:
        res_existe = await db.execute(text("""
            SELECT id FROM emisor_usuarios
            WHERE profile_id = :pid AND emisor_id = :eid
        """), {"pid": str(perfil_existente.id), "eid": emisor_id})
        if res_existe.fetchone():
            raise HTTPException(status_code=400, detail="Este usuario ya pertenece a tu empresa.")

        await db.execute(text("""
            INSERT INTO emisor_usuarios (emisor_id, profile_id, rol, permisos)
            VALUES (:eid, :pid, :rol, :permisos)
        """), {
            "eid":      emisor_id,
            "pid":      str(perfil_existente.id),
            "rol":      data.rol,
            "permisos": json.dumps(permisos_finales),
        })

        await audit_log(
            db        = db,
            auth_data = auth_data,
            accion    = "INVITE",
            entidad   = "usuario",
            entidad_id = str(perfil_existente.id),
            detalle   = {
                "email":    data.email,
                "rol":      data.rol,
                "permisos": permisos_finales,
                "empresa":  empresa.razon_social,
            },
            request   = request,
        )

        await db.commit()

        # Heredar tokens FCM
        try:
            res_tokens = await db.execute(text("""
                SELECT DISTINCT token, device_id FROM fcm_tokens WHERE profile_id = :pid
            """), {"pid": str(perfil_existente.id)})
            tokens = res_tokens.fetchall()
            for t in tokens:
                await db.execute(text("""
                    INSERT INTO fcm_tokens (profile_id, emisor_id, token, device_id, updated_at)
                    VALUES (:pid, :eid, :token, :did, NOW())
                    ON CONFLICT (profile_id, emisor_id, device_id)
                    DO UPDATE SET token = :token, updated_at = NOW()
                """), {"pid": str(perfil_existente.id), "eid": emisor_id, "token": t.token, "did": t.device_id or "default"})
            if tokens:
                await db.commit()
        except Exception as e:
            print(f"[FCM] ⚠️ Error heredando tokens: {e}")

        await cache_delete(f"empresa:{emisor_id}:usuarios")
        await cache_delete(f"usuario:{perfil_existente.id}:empresas")

        await mail_service.send_mail(
            to=data.email,
            subject=f"Te han agregado a {empresa.razon_social} en Kipu",
            html_content=f"""
                <h2>Tienes acceso a una nueva empresa 🎉</h2>
                <p>Has sido agregado como <strong>{data.rol}</strong> en
                <strong>{empresa.razon_social}</strong>.</p>
                <p>Inicia sesión en Kipu y selecciona la empresa desde el selector.</p>
                <a href='https://app.kipu.ec' style='background:#4F46E5;color:white;
                padding:12px 24px;text-decoration:none;border-radius:6px;
                display:inline-block;'>Abrir Kipu</a>
            """
        )
        return {"ok": True, "mensaje": f"Usuario agregado como {data.rol} exitosamente.", "nuevo": False}

    else:
        await audit_log(
            db        = db,
            auth_data = auth_data,
            accion    = "INVITE",
            entidad   = "usuario",
            entidad_id = None,
            detalle   = {
                "email":   data.email,
                "rol":     data.rol,
                "empresa": empresa.razon_social,
                "estado":  "pendiente_registro",
            },
            request   = request,
        )
        await db.commit()

        await mail_service.send_mail(
            to=data.email,
            subject=f"Te invitan a {empresa.razon_social} en Kipu",
            html_content=f"""
                <h2>Tienes una invitación 🎉</h2>
                <p>Has sido invitado como <strong>{data.rol}</strong> en
                <strong>{empresa.razon_social}</strong>.</p>
                <p>Crea tu cuenta en Kipu con este email para aceptar la invitación.</p>
                <a href='https://app.kipu.ec/register?email={data.email}&empresa={emisor_id}'
                style='background:#4F46E5;color:white;padding:12px 24px;
                text-decoration:none;border-radius:6px;display:inline-block;'>
                Crear cuenta</a>
            """
        )
        return {"ok": True, "mensaje": "Invitación enviada. El usuario debe crear su cuenta en Kipu.", "nuevo": True}

# ── PATCH /empresas/{emisor_id}/usuarios/{target_profile_id}/permisos ──────────
@router.patch("/empresas/{emisor_id}/usuarios/{target_profile_id}/permisos", summary="Actualizar permisos de un usuario")
async def actualizar_permisos_usuario(
    emisor_id:         int,
    target_profile_id: str,
    data:              ActualizarPermisosRequest,
    request:           Request,
    auth_data:         dict = Depends(verify_firebase_token),
    db:                AsyncSession = Depends(get_db),
):
    verificar_permiso(auth_data, "usuarios")

    for p in data.permisos:
        if p not in PERMISOS_DISPONIBLES:
            raise HTTPException(status_code=400, detail=f"Permiso inválido: {p}")

    res_target = await db.execute(text("""
        SELECT rol, permisos FROM emisor_usuarios
        WHERE profile_id = :pid AND emisor_id = :eid
    """), {"pid": target_profile_id, "eid": emisor_id})
    target = res_target.fetchone()
    if not target:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    if target.rol == "admin":
        raise HTTPException(status_code=400, detail="No puedes modificar los permisos de un administrador.")

    await db.execute(text("""
        UPDATE emisor_usuarios
        SET permisos = :permisos, updated_at = NOW()
        WHERE profile_id = :pid AND emisor_id = :eid
    """), {
        "permisos": json.dumps(data.permisos),
        "pid":      target_profile_id,
        "eid":      emisor_id,
    })

    await audit_log(
        db        = db,
        auth_data = auth_data,
        accion    = "UPDATE",
        entidad   = "usuario",
        entidad_id = target_profile_id,
        detalle   = {
            "permisos_antes":  target.permisos or {},
            "permisos_despues": data.permisos,
        },
        request   = request,
    )

    await db.commit()
    await cache_delete(f"empresa:{emisor_id}:usuarios")
    await cache_delete(f"usuario:{target_profile_id}:empresas")

    return {"ok": True, "mensaje": "Permisos actualizados correctamente."}

# ── DELETE /empresas/{emisor_id}/usuarios/{target_profile_id} ─────────────────
@router.delete("/empresas/{emisor_id}/usuarios/{target_profile_id}", summary="Remover usuario de mi empresa")
async def remover_usuario(
    emisor_id:         int,
    target_profile_id: str,
    request:           Request,
    auth_data:         dict = Depends(verify_firebase_token),
    db:                AsyncSession = Depends(get_db),
):
    profile_id = auth_data.get("profile_id")
    verificar_permiso(auth_data, "usuarios")

    if str(profile_id) == target_profile_id:
        raise HTTPException(status_code=400, detail="No puedes removerte a ti mismo.")

    # Obtener datos antes de borrar para el log
    res_target = await db.execute(text("""
        SELECT p.email, p.full_name, eu.rol
        FROM emisor_usuarios eu
        JOIN profiles p ON p.id = eu.profile_id
        WHERE eu.emisor_id = :eid AND eu.profile_id = :pid
    """), {"eid": emisor_id, "pid": target_profile_id})
    target = res_target.fetchone()

    res = await db.execute(text("""
        DELETE FROM emisor_usuarios
        WHERE emisor_id = :eid AND profile_id = :pid
        RETURNING id
    """), {"eid": emisor_id, "pid": target_profile_id})
    if not res.fetchone():
        raise HTTPException(status_code=404, detail="Usuario no encontrado en esta empresa.")

    await audit_log(
        db        = db,
        auth_data = auth_data,
        accion    = "DELETE",
        entidad   = "usuario",
        entidad_id = target_profile_id,
        detalle   = {
            "email":  target.email if target else None,
            "nombre": target.full_name if target else None,
            "rol":    target.rol if target else None,
        },
        request   = request,
    )

    await db.commit()
    await cache_delete(f"empresa:{emisor_id}:usuarios")
    await cache_delete(f"usuario:{target_profile_id}:empresas")
    return {"ok": True, "mensaje": "Usuario removido exitosamente."}