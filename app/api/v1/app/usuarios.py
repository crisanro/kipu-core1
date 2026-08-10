# app/api/v1/app/usuarios.py
#
# Gestión de usuarios y empresas en modelo multi-empresa.
# Un usuario puede tener N empresas, una empresa puede tener N usuarios.

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, EmailStr

from app.core.database import get_db
from app.core.security import verify_firebase_token
from app.core.cache import cache_get, cache_set, cache_delete, invalidate_emisor
from app.services.mail_service import mail_service

router = APIRouter()

TTL_EMPRESAS = 300  # 5 min


# ── Schemas ────────────────────────────────────────────────────────────────────
class InvitarUsuarioRequest(BaseModel):
    email: EmailStr
    rol:   str = "emisor"   # "admin" | "emisor"

class CambiarEmpresaRequest(BaseModel):
    emisor_id: int


# ── GET /empresas — listar todas las empresas del usuario ──────────────────────
@router.get("/empresas", summary="Listar mis empresas")
async def listar_empresas(
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db),
):
    profile_id = auth_data.get("profile_id")
    if not profile_id:
        raise HTTPException(status_code=400, detail="Perfil no encontrado.")

    cache_key = f"usuario:{profile_id}:empresas"
    cached    = await cache_get(cache_key)
    if cached:
        return cached  # ← cached ya incluye role

    # ← Agregar p.role al SELECT
    res = await db.execute(text("""
        SELECT
            e.id, e.ruc, e.razon_social, e.nombre_comercial,
            e.ambiente, e.p12_path, e.p12_expiration,
            eu.rol,
            c.balance_emision, c.balance_recepcion,
            p.role as profile_role
        FROM emisor_usuarios eu
        JOIN emisores e      ON e.id = eu.emisor_id
        JOIN profiles p      ON p.id = eu.profile_id
        LEFT JOIN user_credits c ON c.emisor_id = e.id
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
            "firma_ok":         bool(r.p12_path),
            "rol":              r.rol,
            "balance_emision":  r.balance_emision  or 0,
            "balance_recepcion": r.balance_recepcion or 0,
        }
        for r in rows
    ]

    # ← role del perfil (superadmin, admin, etc.)
    profile_role = rows[0].profile_role if rows else None

    response = {
        "ok":   True,
        "data": data,
        "role": profile_role,
    }

    await cache_set(cache_key, response, TTL_EMPRESAS)
    return response


# ── POST /empresas/cambiar — cambiar empresa activa en sesión ──────────────────
@router.post("/empresas/cambiar", summary="Cambiar empresa activa")
async def cambiar_empresa(
    data: CambiarEmpresaRequest,
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db),
):
    profile_id = auth_data.get("profile_id")
    if not profile_id:
        raise HTTPException(status_code=400, detail="Perfil no encontrado.")

    # Verificar que el usuario pertenece a esa empresa
    res = await db.execute(text("""
        SELECT eu.rol, e.ruc, e.razon_social, e.ambiente,
               c.balance_emision, c.balance_recepcion
        FROM emisor_usuarios eu
        JOIN emisores e      ON e.id = eu.emisor_id
        LEFT JOIN user_credits c ON c.emisor_id = e.id
        WHERE eu.profile_id = :pid AND eu.emisor_id = :eid
    """), {"pid": str(profile_id), "eid": data.emisor_id})
    row = res.fetchone()

    if not row:
        raise HTTPException(status_code=403, detail="No tienes acceso a esa empresa.")

    # El frontend guarda el emisor_id activo en su estado local (localStorage/cookie)
    # El backend devuelve los datos de la empresa seleccionada
    return {
        "ok": True,
        "mensaje": "Empresa cambiada exitosamente.",
        "data": {
            "emisor_id":        data.emisor_id,
            "ruc":              row.ruc,
            "razon_social":     row.razon_social,
            "ambiente":         row.ambiente,
            "rol":              row.rol,
            "balance_emision":  row.balance_emision  or 0,
            "balance_recepcion": row.balance_recepcion or 0,
        }
    }


# ── GET /empresas/{emisor_id}/usuarios — listar usuarios de una empresa ────────
@router.get("/empresas/{emisor_id}/usuarios", summary="Listar usuarios de mi empresa")
async def listar_usuarios_empresa(
    emisor_id: int,
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db),
):
    profile_id = auth_data.get("profile_id")

    # Solo admin puede ver los usuarios
    res_rol = await db.execute(text("""
        SELECT rol FROM emisor_usuarios
        WHERE profile_id = :pid AND emisor_id = :eid
    """), {"pid": str(profile_id), "eid": emisor_id})
    row_rol = res_rol.fetchone()

    if not row_rol:
        raise HTTPException(status_code=403, detail="No tienes acceso a esa empresa.")
    if row_rol.rol != "admin":
        raise HTTPException(status_code=403, detail="Solo el administrador puede ver los usuarios.")

    cache_key = f"empresa:{emisor_id}:usuarios"
    cached    = await cache_get(cache_key)
    if cached:
        return {"ok": True, "data": cached}

    res = await db.execute(text("""
        SELECT p.id, p.email, p.full_name, eu.rol, eu.created_at
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
            "desde":      str(r.created_at),
        }
        for r in rows
    ]

    await cache_set(cache_key, data, TTL_EMPRESAS)
    return {"ok": True, "data": data}


# ── POST /empresas/{emisor_id}/invitar — invitar usuario ──────────────────────
@router.post("/empresas/{emisor_id}/invitar", summary="Invitar usuario a mi empresa")
async def invitar_usuario(
    emisor_id: int,
    data: InvitarUsuarioRequest,
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db),
):
    profile_id = auth_data.get("profile_id")

    if data.rol not in ("admin", "emisor"):
        raise HTTPException(status_code=400, detail="Rol inválido. Debe ser 'admin' o 'emisor'.")

    # Verificar que quien invita es admin
    res_rol = await db.execute(text("""
        SELECT rol FROM emisor_usuarios
        WHERE profile_id = :pid AND emisor_id = :eid
    """), {"pid": str(profile_id), "eid": emisor_id})
    row_rol = res_rol.fetchone()

    if not row_rol or row_rol.rol != "admin":
        raise HTTPException(status_code=403, detail="Solo el administrador puede invitar usuarios.")

    # Buscar si el email ya tiene perfil en Kipu
    res_profile = await db.execute(text("""
        SELECT id, full_name FROM profiles WHERE LOWER(email) = LOWER(:email)
    """), {"email": data.email})
    perfil_existente = res_profile.fetchone()

    # Obtener nombre de la empresa
    res_empresa = await db.execute(text("""
        SELECT razon_social FROM emisores WHERE id = :eid
    """), {"eid": emisor_id})
    empresa = res_empresa.fetchone()
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa no encontrada.")

    if perfil_existente:
        # Verificar que no esté ya en la empresa
        res_existe = await db.execute(text("""
            SELECT id FROM emisor_usuarios
            WHERE profile_id = :pid AND emisor_id = :eid
        """), {"pid": str(perfil_existente.id), "eid": emisor_id})
        if res_existe.fetchone():
            raise HTTPException(status_code=400, detail="Este usuario ya pertenece a tu empresa.")

        # Agregar directo
        await db.execute(text("""
            INSERT INTO emisor_usuarios (emisor_id, profile_id, rol)
            VALUES (:eid, :pid, :rol)
        """), {"eid": emisor_id, "pid": str(perfil_existente.id), "rol": data.rol})
        await db.commit()

        # Invalidar cache
        await cache_delete(f"empresa:{emisor_id}:usuarios")
        await cache_delete(f"usuario:{perfil_existente.id}:empresas")

        # Notificar por email
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

        return {
            "ok":      True,
            "mensaje": f"Usuario agregado como {data.rol} exitosamente.",
            "nuevo":   False
        }

    else:
        # El email no tiene cuenta — enviar invitación para registrarse
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

        return {
            "ok":      True,
            "mensaje": "Invitación enviada. El usuario debe crear su cuenta en Kipu.",
            "nuevo":   True
        }


# ── DELETE /empresas/{emisor_id}/usuarios/{profile_id} — remover usuario ───────
@router.delete("/empresas/{emisor_id}/usuarios/{target_profile_id}", summary="Remover usuario de mi empresa")
async def remover_usuario(
    emisor_id: int,
    target_profile_id: str,
    auth_data: dict = Depends(verify_firebase_token),
    db: AsyncSession = Depends(get_db),
):
    profile_id = auth_data.get("profile_id")

    # Solo admin puede remover
    res_rol = await db.execute(text("""
        SELECT rol FROM emisor_usuarios
        WHERE profile_id = :pid AND emisor_id = :eid
    """), {"pid": str(profile_id), "eid": emisor_id})
    row_rol = res_rol.fetchone()

    if not row_rol or row_rol.rol != "admin":
        raise HTTPException(status_code=403, detail="Solo el administrador puede remover usuarios.")

    # No puede removerse a sí mismo
    if str(profile_id) == target_profile_id:
        raise HTTPException(status_code=400, detail="No puedes removerte a ti mismo.")

    res = await db.execute(text("""
        DELETE FROM emisor_usuarios
        WHERE emisor_id = :eid AND profile_id = :pid
        RETURNING id
    """), {"eid": emisor_id, "pid": target_profile_id})

    if not res.fetchone():
        raise HTTPException(status_code=404, detail="Usuario no encontrado en esta empresa.")

    await db.commit()

    # Invalidar cache
    await cache_delete(f"empresa:{emisor_id}:usuarios")
    await cache_delete(f"usuario:{target_profile_id}:empresas")

    return {"ok": True, "mensaje": "Usuario removido exitosamente."}