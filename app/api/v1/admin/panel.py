# app/api/v1/admin/panel.py
import asyncio
import json
import time
from fastapi import APIRouter, Depends, HTTPException, Body, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime, timezone, timedelta
from firebase_admin import auth as fb_auth
from app.core.database import get_db
from app.core.security import verify_firebase_token
from app.services.notification_service import crear_notificacion, notificar_todos_emisores
from app.services.audit_service import audit_log
from app.services.mail_service import mail_service
from app.api.v1.admin.stripe_webhook import _emitir_factura_kipu, _auth_stripe
from app.core.cache import invalidate_emisor

router = APIRouter()

# =============================================================================
# CONFIGURACIÓN
# =============================================================================
# Roles de emisor_usuarios que cuentan como "dueño" de la empresa.
# Valores posibles: admin | contador | emisor
ROLES_DUENO = ["admin"]

# A dónde vuelve el usuario después de verificar o resetear contraseña.
# El dominio debe estar en Firebase Console → Authentication → Settings → Authorized domains.
APP_LOGIN_URL = "https://app.kipu.ec/login"

# Caché en memoria de usuarios de Firebase para la búsqueda por coincidencia.
# Es por proceso: si corres varios workers, cada uno tiene la suya.
FB_CACHE_TTL = 300  # segundos
_FB_CACHE: dict = {"ts": 0.0, "users": []}

# =============================================================================
# GUARD SUPERADMIN
# =============================================================================
async def verify_superadmin(auth_data: dict = Depends(verify_firebase_token)):
    if auth_data.get("role") != "superadmin":
        raise HTTPException(status_code=403, detail="Acceso restringido.")
    return auth_data

# =============================================================================
# HELPERS
# =============================================================================
def _parse_json(val):
    """json_agg puede volver como str según el codec del driver."""
    if isinstance(val, str):
        try:
            return json.loads(val)
        except Exception:
            return []
    return val or []

def _ts(ms: Optional[int]) -> Optional[str]:
    if not ms:
        return None
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()

# =============================================================================
# SCHEMAS
# =============================================================================
class NotificacionMasivaRequest(BaseModel):
    titulo:     str
    mensaje:    str
    tipo:       str           = "SISTEMA"
    referencia: Optional[str] = None
    emisor_id:  Optional[int] = None

class EditarEmisorRequest(BaseModel):
    razon_social:           Optional[str] = None
    nombre_comercial:       Optional[str] = None
    direccion_matriz:       Optional[str] = None
    obligado_contabilidad:  Optional[str] = None  # SI | NO
    contribuyente_especial: Optional[str] = None

class ActivarTransferenciaRequest(BaseModel):
    emisor_id:         int
    monto:             float
    referencia_pago:   str
    banco:             Optional[str] = None
    notas:             Optional[str] = None
    fecha_pago:        Optional[str] = None   # ISO date YYYY-MM-DD, default hoy
    periodo:           str           = "ANUAL"
    plan:              str           = "PRO"

class EnviarLinkRequest(BaseModel):
    email:  str
    enviar: bool = True   # True = se envía por correo automáticamente

class VerificarManualRequest(BaseModel):
    email:  str
    motivo: str = Field(..., min_length=5, max_length=300)

# =============================================================================
# GET /emisores
# =============================================================================
@router.get("/emisores", summary="Listar todos los emisores")
async def listar_emisores(
    auth_data: dict         = Depends(verify_superadmin),
    db:        AsyncSession = Depends(get_db),
):
    res = await db.execute(text("""
        SELECT
            e.id, e.ruc, e.razon_social, e.nombre_comercial,
            e.ambiente, e.tipo_emisor, e.created_at,
            COALESCE(uc.balance, 0)  AS balance_emision,
            s.estado                 AS sub_estado,
            s.plan                   AS sub_plan,
            s.current_period_end     AS sub_vencimiento,
            COUNT(DISTINCT eu.profile_id)                              AS total_usuarios,
            COUNT(DISTINCT CASE WHEN d.estado_sri = 'AUTORIZADO'
                                 AND d.tipo_doc IN ('FAC','LIQ')
                            THEN d.id END)                             AS total_facturas
        FROM emisores e
        LEFT JOIN user_credits    uc ON uc.emisor_id = e.id
        LEFT JOIN subscriptions   s  ON s.emisor_id  = e.id
        LEFT JOIN emisor_usuarios eu ON eu.emisor_id = e.id
        LEFT JOIN documentos_emitidos d ON d.emisor_id = e.id
        GROUP BY e.id, uc.balance, s.estado, s.plan, s.current_period_end
        ORDER BY e.created_at DESC
    """))
    rows = res.fetchall()
    return {
        "ok":   True,
        "data": [dict(r._mapping) for r in rows],
    }

# =============================================================================
# GET /stats
# =============================================================================
@router.get("/stats", summary="Estadísticas globales de Kipu")
async def stats_globales(
    auth_data: dict         = Depends(verify_superadmin),
    db:        AsyncSession = Depends(get_db),
):
    # Subqueries independientes: evita que los JOINs multipliquen SUMs
    res = await db.execute(text("""
        SELECT
            (SELECT COUNT(*) FROM emisores)                    AS total_emisores,
            (SELECT COUNT(*) FROM emisores WHERE ambiente = 2) AS en_produccion,
            (SELECT COUNT(*) FROM emisores WHERE ambiente = 1) AS en_pruebas,
            (SELECT COUNT(*) FROM subscriptions
              WHERE estado IN ('ACTIVO', 'TRIAL'))             AS con_suscripcion,
            d.total_facturas,
            d.autorizadas,
            d.monto_total,
            (SELECT COALESCE(SUM(balance), 0) FROM user_credits) AS creditos_totales,
            (SELECT COUNT(*) FROM profiles)                    AS total_usuarios,
            (SELECT COUNT(*) FROM profiles p
              WHERE NOT EXISTS (
                  SELECT 1 FROM emisor_usuarios eu WHERE eu.profile_id = p.id
              ))                                               AS usuarios_sin_empresa
        FROM (
            SELECT
                COUNT(*)                                                AS total_facturas,
                COUNT(*) FILTER (WHERE estado_sri = 'AUTORIZADO')       AS autorizadas,
                COALESCE(SUM(importe_total)
                    FILTER (WHERE estado_sri = 'AUTORIZADO'), 0)        AS monto_total
            FROM documentos_emitidos
            WHERE tipo_doc IN ('FAC', 'LIQ')
        ) d
    """))
    row = res.fetchone()
    return {"ok": True, "data": dict(row._mapping)}

# =============================================================================
# GET /usuarios — listado paginado con segmentos
# =============================================================================
@router.get("/usuarios", summary="Listar usuarios (profiles) con sus empresas")
async def listar_usuarios(
    q:         str = Query("", max_length=100),
    segmento:  Literal["todos", "duenos", "colaboradores", "sin_empresa"] = "todos",
    page:      int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    auth_data: dict         = Depends(verify_superadmin),
    db:        AsyncSession = Depends(get_db),
):
    q_clean = q.strip()
    params = {
        "q":      q_clean,
        "q_like": f"%{q_clean}%",
        "roles":  ROLES_DUENO,
    }

    base_cte = """
        WITH base AS (
            SELECT
                p.id, p.email, p.full_name, p.created_at,
                EXISTS (
                    SELECT 1 FROM emisor_usuarios eu
                    WHERE eu.profile_id = p.id
                ) AS tiene_empresa,
                EXISTS (
                    SELECT 1 FROM emisor_usuarios eu
                    WHERE eu.profile_id = p.id AND eu.rol = ANY(:roles)
                ) AS es_dueno
            FROM profiles p
            WHERE CAST(:q AS text) = ''
               OR p.email     ILIKE :q_like
               OR p.full_name ILIKE :q_like
        )
    """

    # Conteos por segmento (respetan la búsqueda) — para los badges de los tabs
    res_cnt = await db.execute(text(base_cte + """
        SELECT
            COUNT(*)                                              AS todos,
            COUNT(*) FILTER (WHERE es_dueno)                      AS duenos,
            COUNT(*) FILTER (WHERE tiene_empresa AND NOT es_dueno) AS colaboradores,
            COUNT(*) FILTER (WHERE NOT tiene_empresa)             AS sin_empresa
        FROM base
    """), params)
    conteos = dict(res_cnt.fetchone()._mapping)

    # Fragmentos fijos (no vienen del usuario) — seguro interpolarlos
    filtros = {
        "todos":         "TRUE",
        "duenos":        "b.es_dueno",
        "colaboradores": "b.tiene_empresa AND NOT b.es_dueno",
        "sin_empresa":   "NOT b.tiene_empresa",
    }

    params["limit"]  = page_size
    params["offset"] = (page - 1) * page_size

    res = await db.execute(text(base_cte + f"""
        SELECT
            b.id, b.email, b.full_name AS nombre, b.created_at,
            b.tiene_empresa, b.es_dueno,
            COALESCE((
                SELECT json_agg(json_build_object(
                    'emisor_id', e.id,
                    'ruc',       e.ruc,
                    'nombre',    COALESCE(e.nombre_comercial, e.razon_social),
                    'ambiente',  e.ambiente,
                    'rol',       eu.rol
                ) ORDER BY eu.created_at)
                FROM emisor_usuarios eu
                JOIN emisores e ON e.id = eu.emisor_id
                WHERE eu.profile_id = b.id
            ), '[]'::json) AS emisores
        FROM base b
        WHERE {filtros[segmento]}
        ORDER BY b.created_at DESC NULLS LAST
        LIMIT :limit OFFSET :offset
    """), params)

    data = []
    for r in res.fetchall():
        row = dict(r._mapping)
        row["emisores"] = _parse_json(row["emisores"])
        data.append(row)

    return {
        "ok":        True,
        "data":      data,
        "conteos":   conteos,
        "page":      page,
        "page_size": page_size,
        "total":     conteos[segmento],
    }

# =============================================================================
# GET /usuarios/{id} — detalle + datos de Firebase
# =============================================================================
@router.get("/usuarios/{profile_id}", summary="Detalle de un usuario")
async def detalle_usuario(
    profile_id: str,
    auth_data:  dict         = Depends(verify_superadmin),
    db:         AsyncSession = Depends(get_db),
):
    res = await db.execute(text("""
        SELECT
            p.id, p.firebase_uid, p.email, p.full_name AS nombre,
            p.role, p.whatsapp_number, p.empresa_default_id, p.created_at,
            COALESCE(ed.nombre_comercial, ed.razon_social) AS empresa_default_nombre,
            (SELECT COUNT(*) FROM documentos_emitidos d
              WHERE d.created_by = p.id)                       AS docs_emitidos,
            (SELECT MAX(a.created_at) FROM audit_logs a
              WHERE a.profile_id = p.id)                       AS ultima_accion_kipu
        FROM profiles p
        LEFT JOIN emisores ed ON ed.id = p.empresa_default_id
        WHERE p.id::text = :pid
    """), {"pid": profile_id})
    perfil = res.fetchone()
    if not perfil:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    data = dict(perfil._mapping)

    # Empresas vinculadas
    res_e = await db.execute(text("""
        SELECT
            e.id AS emisor_id, e.ruc, e.razon_social, e.nombre_comercial,
            e.ambiente, eu.rol, eu.permisos, eu.created_at AS vinculado_at,
            COALESCE(uc.balance, 0) AS balance_emision,
            s.estado AS sub_estado, s.plan AS sub_plan,
            s.current_period_end AS sub_vencimiento
        FROM emisor_usuarios eu
        JOIN emisores e           ON e.id = eu.emisor_id
        LEFT JOIN user_credits uc ON uc.emisor_id = e.id
        LEFT JOIN subscriptions s ON s.emisor_id  = e.id
        WHERE eu.profile_id::text = :pid
        ORDER BY eu.created_at ASC
    """), {"pid": profile_id})
    data["emisores"] = [dict(r._mapping) for r in res_e.fetchall()]

    # Firebase — por uid, solo en detalle
    data["firebase"] = None
    if data.get("firebase_uid"):
        try:
            fb_user = await asyncio.to_thread(fb_auth.get_user, data["firebase_uid"])
            data["firebase"] = {
                "uid":              fb_user.uid,
                "email":            fb_user.email,
                "email_verified":   fb_user.email_verified,
                "disabled":         fb_user.disabled,
                "providers":        [p.provider_id for p in fb_user.provider_data],
                "creado":           _ts(fb_user.user_metadata.creation_timestamp),
                "ultimo_login":     _ts(fb_user.user_metadata.last_sign_in_timestamp),
                "ultima_actividad": _ts(getattr(fb_user.user_metadata, "last_refresh_timestamp", None)),
            }
        except fb_auth.UserNotFoundError:
            data["firebase"] = {"error": "No existe en Firebase"}
        except Exception as ex:
            data["firebase"] = {"error": f"Error consultando Firebase: {ex}"}

    return {"ok": True, "data": data}

# =============================================================================
# GET /emisores/{id}
# =============================================================================
@router.get("/emisores/{emisor_id}", summary="Detalle de un emisor")
async def detalle_emisor(
    emisor_id: int,
    auth_data: dict         = Depends(verify_superadmin),
    db:        AsyncSession = Depends(get_db),
):
    res = await db.execute(text("""
        SELECT
            e.id, e.ruc, e.razon_social, e.nombre_comercial,
            e.direccion_matriz, e.ambiente, e.tipo_emisor,
            e.obligado_contabilidad, e.contribuyente_especial,
            e.p12_expiration, e.created_at,
            e.p12_path IS NOT NULL      AS firma_ok,
            COALESCE(uc.balance, 0)     AS balance_emision,
            s.estado                    AS sub_estado,
            s.plan                      AS sub_plan,
            s.periodo                   AS sub_periodo,
            s.current_period_start      AS sub_period_start,
            s.current_period_end        AS sub_period_end,
            s.cancel_at_period_end,
            s.stripe_subscription_id
        FROM emisores e
        LEFT JOIN user_credits  uc ON uc.emisor_id = e.id
        LEFT JOIN subscriptions s  ON s.emisor_id  = e.id
        WHERE e.id = :eid
    """), {"eid": emisor_id})
    emisor = res.fetchone()
    if not emisor:
        raise HTTPException(status_code=404, detail="Emisor no encontrado.")

    # Usuarios
    res_u = await db.execute(text("""
        SELECT p.id AS profile_id, p.email, p.full_name AS nombre, eu.rol
        FROM emisor_usuarios eu
        JOIN profiles p ON p.id = eu.profile_id
        WHERE eu.emisor_id = :eid
        ORDER BY eu.created_at ASC
    """), {"eid": emisor_id})
    usuarios = [dict(r._mapping) for r in res_u.fetchall()]

    # Últimos 20 documentos emitidos
    res_d = await db.execute(text("""
        SELECT id, numero_doc, tipo_doc, estado_sri,
               importe_total, fecha_emision, origen
        FROM documentos_emitidos
        WHERE emisor_id = :eid
        ORDER BY created_at DESC
        LIMIT 20
    """), {"eid": emisor_id})
    documentos = [dict(r._mapping) for r in res_d.fetchall()]

    # Conteos
    res_cnt = await db.execute(text("""
        SELECT
            COUNT(*)                                               AS total_documentos,
            COUNT(CASE WHEN estado_sri = 'AUTORIZADO' THEN 1 END) AS autorizados,
            COUNT(CASE WHEN tipo_doc = 'FAC' THEN 1 END)          AS facturas,
            COUNT(CASE WHEN tipo_doc = 'RET' THEN 1 END)          AS retenciones
        FROM documentos_emitidos
        WHERE emisor_id = :eid
    """), {"eid": emisor_id})
    cnt = res_cnt.fetchone()

    # Últimas transacciones de créditos
    res_tx = await db.execute(text("""
        SELECT tipo, cantidad, precio_total, metodo_pago, notas, created_at
        FROM credit_transactions
        WHERE emisor_id = :eid
        ORDER BY created_at DESC
        LIMIT 10
    """), {"eid": emisor_id})
    transacciones = [dict(r._mapping) for r in res_tx.fetchall()]

    # Historial de pagos por transferencia (audit_log)
    res_tf = await db.execute(text("""
        SELECT detalle, created_at
        FROM audit_logs
        WHERE emisor_id  = :eid
          AND entidad    = 'suscripcion'
          AND accion     = 'CREATE'
          AND detalle->>'origen' = 'transferencia'
        ORDER BY created_at DESC
        LIMIT 5
    """), {"eid": emisor_id})
    transferencias = [dict(r._mapping) for r in res_tf.fetchall()]

    data = dict(emisor._mapping)
    data["usuarios"]       = usuarios
    data["documentos"]     = documentos
    data["conteos"]        = dict(cnt._mapping)
    data["total_usuarios"] = len(usuarios)
    data["transacciones"]  = transacciones
    data["transferencias"] = transferencias

    return {"ok": True, "data": data}

# =============================================================================
# PATCH /emisores/{id} — editar datos del emisor
# =============================================================================
@router.patch("/emisores/{emisor_id}", summary="Editar datos del emisor")
async def editar_emisor(
    emisor_id: int,
    req:       EditarEmisorRequest,
    auth_data: dict         = Depends(verify_superadmin),
    db:        AsyncSession = Depends(get_db),
):
    """
    Reglas:
    - RUC: nunca editable desde aquí (ni siquiera por soporte si hay firma).
    - Razón Social: editable por soporte (superadmin) siempre.
    - Resto: editable siempre.
    """
    res_e = await db.execute(text("""
        SELECT id, ruc, razon_social, nombre_comercial,
               direccion_matriz, obligado_contabilidad,
               contribuyente_especial, p12_path
        FROM emisores WHERE id = :eid
    """), {"eid": emisor_id})
    emisor = res_e.fetchone()
    if not emisor:
        raise HTTPException(status_code=404, detail="Emisor no encontrado.")

    campos      = {}
    cambios_log = {}

    if req.razon_social is not None:
        val = req.razon_social.strip()
        if val and val != emisor.razon_social:
            campos["razon_social"] = val
            cambios_log["razon_social"] = {"antes": emisor.razon_social, "despues": val}

    if req.nombre_comercial is not None:
        val = req.nombre_comercial.strip() or None
        if val != emisor.nombre_comercial:
            campos["nombre_comercial"] = val
            cambios_log["nombre_comercial"] = {"antes": emisor.nombre_comercial, "despues": val}

    if req.direccion_matriz is not None:
        val = req.direccion_matriz.strip()
        if val and val != emisor.direccion_matriz:
            campos["direccion_matriz"] = val
            cambios_log["direccion_matriz"] = {"antes": emisor.direccion_matriz, "despues": val}

    if req.obligado_contabilidad is not None:
        val = req.obligado_contabilidad.upper()
        if val not in ("SI", "NO"):
            raise HTTPException(status_code=400, detail="obligado_contabilidad debe ser SI o NO.")
        if val != emisor.obligado_contabilidad:
            campos["obligado_contabilidad"] = val
            cambios_log["obligado_contabilidad"] = {"antes": emisor.obligado_contabilidad, "despues": val}

    if req.contribuyente_especial is not None:
        val = req.contribuyente_especial.strip() or None
        if val != emisor.contribuyente_especial:
            campos["contribuyente_especial"] = val
            cambios_log["contribuyente_especial"] = {"antes": emisor.contribuyente_especial, "despues": val}

    if not campos:
        return {"ok": True, "mensaje": "Sin cambios."}

    set_clause = ", ".join(f"{k} = :{k}" for k in campos)
    campos["emisor_id"] = emisor_id
    await db.execute(
        text(f"UPDATE emisores SET {set_clause}, updated_at = NOW() WHERE id = :emisor_id"),
        campos,
    )

    await audit_log(
        db        = db,
        auth_data = {"emisor_id": emisor_id, "profile_id": auth_data.get("profile_id"), "emisor_rol": "superadmin"},
        accion    = "UPDATE",
        entidad   = "config",
        entidad_id = str(emisor_id),
        detalle   = {
            "origen":       "admin_soporte",
            "editado_por":  auth_data.get("email", "superadmin"),
            "cambios":      cambios_log,
        },
    )
    await db.commit()
    await invalidate_emisor(emisor_id)
    return {"ok": True, "mensaje": "Emisor actualizado.", "campos_editados": list(cambios_log.keys())}

# =============================================================================
# POST /topup  — recargar créditos API manualmente
# =============================================================================
@router.post("/topup", summary="Recargar créditos API a un emisor")
async def topup_creditos(
    data:      dict         = Body(...),
    auth_data: dict         = Depends(verify_superadmin),
    db:        AsyncSession = Depends(get_db),
):
    emisor_id = data.get("emisor_id")
    cantidad  = data.get("cantidad", 0)
    notas     = data.get("notas", "Recarga manual admin")

    if not emisor_id or cantidad <= 0:
        raise HTTPException(status_code=400, detail="emisor_id y cantidad son requeridos.")

    # Upsert: si el emisor no tenía fila en user_credits, se crea
    res = await db.execute(text("""
        INSERT INTO user_credits (emisor_id, balance, last_updated)
        VALUES (:eid, :qty, NOW())
        ON CONFLICT (emisor_id) DO UPDATE SET
            balance      = user_credits.balance + EXCLUDED.balance,
            last_updated = NOW()
        RETURNING balance
    """), {"qty": cantidad, "eid": emisor_id})
    nuevo_balance = res.scalar()

    await db.execute(text("""
        INSERT INTO credit_transactions
            (emisor_id, tipo, cantidad, precio_total, metodo_pago, notas)
        VALUES
            (:eid, 'BONO', :qty, 0.00, 'ADMIN', :notas)
    """), {"eid": emisor_id, "qty": cantidad, "notas": notas})

    await audit_log(
        db        = db,
        auth_data = {"emisor_id": emisor_id, "profile_id": auth_data.get("profile_id"), "emisor_rol": "superadmin"},
        accion    = "CREATE",
        entidad   = "creditos",
        entidad_id = str(emisor_id),
        detalle   = {"origen": "admin_manual", "cantidad": cantidad, "notas": notas, "balance_nuevo": nuevo_balance},
    )
    await db.commit()
    await invalidate_emisor(emisor_id)
    return {
        "ok":            True,
        "mensaje":       f"{cantidad} créditos agregados al emisor {emisor_id}.",
        "balance_nuevo": nuevo_balance,
    }

# =============================================================================
# POST /suscripcion/transferencia — activar suscripción pagada por transferencia
# =============================================================================
@router.post("/suscripcion/transferencia", summary="Activar suscripción por transferencia bancaria")
async def activar_suscripcion_transferencia(
    req:       ActivarTransferenciaRequest,
    auth_data: dict         = Depends(verify_superadmin),
    db:        AsyncSession = Depends(get_db),
):
    """
    Activa o renueva la suscripción Pro de un emisor que pagó por transferencia.
    - Registra la referencia de pago en audit_log.
    - Emite factura de Kipu al emisor automáticamente.
    - current_period_end = hoy + 1 año (ANUAL) o + 1 mes (MENSUAL).
    """
    res_e = await db.execute(text("""
        SELECT id, ruc, razon_social FROM emisores WHERE id = :eid
    """), {"eid": req.emisor_id})
    emisor = res_e.fetchone()
    if not emisor:
        raise HTTPException(status_code=404, detail="Emisor no encontrado.")

    from datetime import date
    fecha_comprobante = req.fecha_pago or date.today().isoformat()

    now = datetime.now(tz=timezone.utc)
    if req.periodo == "ANUAL":
        period_end = now + timedelta(days=365)
    else:
        period_end = now + timedelta(days=30)

    await db.execute(text("""
        INSERT INTO subscriptions
            (emisor_id, plan, periodo, estado,
             current_period_start, current_period_end)
        VALUES
            (:eid, :plan, :periodo, 'ACTIVO', :start, :end)
        ON CONFLICT (emisor_id) DO UPDATE SET
            plan                 = EXCLUDED.plan,
            periodo              = EXCLUDED.periodo,
            estado               = 'ACTIVO',
            current_period_start = EXCLUDED.current_period_start,
            current_period_end   = EXCLUDED.current_period_end,
            cancel_at_period_end = false,
            updated_at           = NOW()
    """), {
        "eid":    req.emisor_id,
        "plan":   req.plan,
        "periodo": req.periodo,
        "start":  now,
        "end":    period_end,
    })

    await audit_log(
        db        = db,
        auth_data = {"emisor_id": req.emisor_id, "profile_id": auth_data.get("profile_id"), "emisor_rol": "superadmin"},
        accion    = "CREATE",
        entidad   = "suscripcion",
        entidad_id = str(req.emisor_id),
        detalle   = {
            "origen":           "transferencia",
            "plan":             req.plan,
            "periodo":          req.periodo,
            "monto":            req.monto,
            "referencia_pago":  req.referencia_pago,
            "banco":            req.banco,
            "fecha_comprobante": fecha_comprobante,
            "notas":            req.notas,
            "activado_por":     auth_data.get("email", "superadmin"),
            "period_end":       period_end.isoformat(),
        },
    )

    await db.commit()
    await invalidate_emisor(req.emisor_id)

    # Notificación al emisor (sesión propia, push en segundo plano)
    await crear_notificacion(
        db        = db,
        emisor_id = req.emisor_id,
        tipo      = "SUSCRIPCION",
        titulo    = "✅ Suscripción activada",
        mensaje   = f"Tu suscripción {req.plan} ({req.periodo}) está activa hasta {period_end.strftime('%d/%m/%Y')}. ¡Bienvenido a Kipu!",
        referencia = "/dashboard",
    )

    # Emitir factura de Kipu al emisor — mismo flujo que Stripe
    descripcion = f"Suscripción Kipu {req.plan} — {req.periodo}"
    fake_obj    = {"amount_total": int(req.monto * 100)}  # centavos, igual que Stripe
    await _emitir_factura_kipu(
        obj         = fake_obj,
        emisor_id   = req.emisor_id,
        db          = db,
        monto       = req.monto,
        descripcion = descripcion,
    )

    return {
        "ok":       True,
        "mensaje":  f"Suscripción {req.plan} activada para emisor {req.emisor_id} hasta {period_end.strftime('%d/%m/%Y')}.",
        "period_end": period_end.isoformat(),
    }

# =============================================================================
# POST /suscripcion/forzar — soporte: cambiar estado sin pago
# =============================================================================
@router.post("/suscripcion/forzar", summary="Forzar estado de suscripción (soporte)")
async def forzar_suscripcion(
    data:      dict         = Body(...),
    auth_data: dict         = Depends(verify_superadmin),
    db:        AsyncSession = Depends(get_db),
):
    """Para soporte — activar trial, cancelar, extender, etc. Sin emitir factura."""
    emisor_id = data.get("emisor_id")
    estado    = data.get("estado")   # ACTIVO | TRIAL | CANCELADO | VENCIDO
    plan      = data.get("plan", "PRO")
    periodo   = data.get("periodo", "ANUAL")

    if not emisor_id or not estado:
        raise HTTPException(status_code=400, detail="emisor_id y estado son requeridos.")

    now = datetime.now(tz=timezone.utc)
    period_end = now + timedelta(days=365) if periodo == "ANUAL" else now + timedelta(days=30)

    await db.execute(text("""
        INSERT INTO subscriptions
            (emisor_id, plan, periodo, estado, current_period_start, current_period_end)
        VALUES
            (:eid, :plan, :periodo, :estado, :start, :end)
        ON CONFLICT (emisor_id) DO UPDATE SET
            estado               = EXCLUDED.estado,
            plan                 = EXCLUDED.plan,
            periodo              = EXCLUDED.periodo,
            current_period_start = EXCLUDED.current_period_start,
            current_period_end   = EXCLUDED.current_period_end,
            updated_at           = NOW()
    """), {
        "eid": emisor_id, "plan": plan, "periodo": periodo,
        "estado": estado, "start": now, "end": period_end,
    })

    await audit_log(
        db        = db,
        auth_data = {"emisor_id": emisor_id, "profile_id": auth_data.get("profile_id"), "emisor_rol": "superadmin"},
        accion    = "UPDATE",
        entidad   = "suscripcion",
        entidad_id = str(emisor_id),
        detalle   = {
            "origen":       "admin_soporte",
            "estado_nuevo": estado,
            "plan":         plan,
            "periodo":      periodo,
            "forzado_por":  auth_data.get("email", "superadmin"),
        },
    )
    await db.commit()
    await invalidate_emisor(emisor_id)
    return {"ok": True, "mensaje": f"Suscripción del emisor {emisor_id} → {estado}."}

# =============================================================================
# POST /notificar
# =============================================================================
@router.post("/notificar", summary="Enviar notificación masiva o individual")
async def enviar_notificacion(
    data:      NotificacionMasivaRequest,
    auth_data: dict         = Depends(verify_superadmin),
    db:        AsyncSession = Depends(get_db),
):
    if data.emisor_id:
        await crear_notificacion(
            db         = db,
            emisor_id  = data.emisor_id,
            tipo       = data.tipo,
            titulo     = data.titulo,
            mensaje    = data.mensaje,
            referencia = data.referencia,
        )
        return {"ok": True, "mensaje": f"Notificación enviada al emisor {data.emisor_id}."}

    total = await notificar_todos_emisores(
        db              = db,
        tipo            = data.tipo,
        titulo          = data.titulo,
        mensaje         = data.mensaje,
        referencia      = data.referencia,
        solo_produccion = True,
    )
    return {
        "ok":      True,
        "mensaje": f"Notificación enviada a {total} emisores en producción. Los push salen en segundo plano.",
        "total":   total,
    }


# =============================================================================
# SOPORTE — búsqueda bajo demanda (exacta + por coincidencia) y envío de links
# =============================================================================

def _norm_email(email: str) -> str:
    email = (email or "").strip().lower()
    if "@" not in email or len(email) > 254:
        raise HTTPException(status_code=400, detail="Email inválido.")
    return email


def _fb_dict(u) -> dict:
    return {
        "uid":            u.uid,
        "email":          u.email,
        "email_verified": u.email_verified,
        "disabled":       u.disabled,
        "providers":      [p.provider_id for p in u.provider_data],
        "creado":         _ts(u.user_metadata.creation_timestamp),
        "ultimo_login":   _ts(u.user_metadata.last_sign_in_timestamp),
    }


def _estado_cuenta(en_fb: bool, en_kipu: bool, verificado: bool, tiene_empresa: bool) -> str:
    if not en_fb and not en_kipu:
        return "no_existe"
    if en_fb and not en_kipu:
        return "solo_firebase"
    if en_kipu and not en_fb:
        return "solo_db"
    if not verificado:
        return "sin_verificar"
    if not tiene_empresa:
        return "sin_empresa"
    return "activo"


async def _fb_por_email(email: str):
    try:
        return await asyncio.to_thread(fb_auth.get_user_by_email, email)
    except fb_auth.UserNotFoundError:
        return None


def _listar_fb_sync() -> list[dict]:
    out = []
    for u in fb_auth.list_users().iterate_all():
        out.append({
            "uid":            u.uid,
            "email":          (u.email or "").lower(),
            "nombre":         u.display_name,
            "email_verified": u.email_verified,
            "providers":      [p.provider_id for p in u.provider_data],
            "creado":         _ts(u.user_metadata.creation_timestamp),
        })
    return out


async def _fb_usuarios(refrescar: bool = False) -> list[dict]:
    if refrescar or time.time() - _FB_CACHE["ts"] > FB_CACHE_TTL:
        _FB_CACHE["users"] = await asyncio.to_thread(_listar_fb_sync)
        _FB_CACHE["ts"]    = time.time()
    return _FB_CACHE["users"]


def _action_settings():
    return fb_auth.ActionCodeSettings(url=APP_LOGIN_URL, handle_code_in_app=False)


async def _nombre_perfil(db: AsyncSession, email: str) -> Optional[str]:
    res = await db.execute(text("""
        SELECT full_name FROM profiles WHERE lower(email) = :email LIMIT 1
    """), {"email": email})
    row = res.fetchone()
    return row.full_name if row else None


async def _audit_soporte(db: AsyncSession, auth_data: dict, uid: str, detalle: dict):
    await audit_log(
        db         = db,
        auth_data  = {"emisor_id": None, "profile_id": auth_data.get("profile_id"), "emisor_rol": "superadmin"},
        accion     = "SOPORTE",
        entidad    = "usuario",
        entidad_id = uid,
        detalle    = {"origen": "admin_soporte", "por": auth_data.get("email", "superadmin"), **detalle},
    )
    await db.commit()


# -----------------------------------------------------------------------------
# GET /soporte/coincidencias?q= — búsqueda parcial (Kipu + Firebase)
# -----------------------------------------------------------------------------
@router.get("/soporte/coincidencias", summary="Buscar cuentas por coincidencia de email o nombre")
async def soporte_coincidencias(
    q:         str          = Query(..., min_length=2, max_length=100),
    refrescar: bool         = False,
    auth_data: dict         = Depends(verify_superadmin),
    db:        AsyncSession = Depends(get_db),
):
    term = q.strip().lower()

    # Firebase (con caché)
    fb_users  = await _fb_usuarios(refrescar)
    fb_by_uid = {u["uid"]: u for u in fb_users}
    fb_match  = [
        u for u in fb_users
        if term in u["email"] or term in (u["nombre"] or "").lower()
    ]

    # Kipu — coincidencias directas en profiles
    sql_perfil = """
        SELECT p.firebase_uid, lower(p.email) AS email, p.full_name AS nombre, p.created_at,
               EXISTS (SELECT 1 FROM emisor_usuarios eu WHERE eu.profile_id = p.id) AS tiene_empresa
        FROM profiles p
    """
    res = await db.execute(text(sql_perfil + """
        WHERE p.email ILIKE :q_like OR p.full_name ILIKE :q_like
        ORDER BY p.created_at DESC
        LIMIT 50
    """), {"q_like": f"%{term}%"})
    perfiles = {r.firebase_uid: dict(r._mapping) for r in res.fetchall()}

    # Perfiles de los que coincidieron solo en Firebase (ej. por display_name)
    faltantes = [u["uid"] for u in fb_match if u["uid"] not in perfiles]
    if faltantes:
        res2 = await db.execute(text(sql_perfil + """
            WHERE p.firebase_uid = ANY(:uids)
        """), {"uids": faltantes})
        for r in res2.fetchall():
            perfiles[r.firebase_uid] = dict(r._mapping)

    uids = set(perfiles) | {u["uid"] for u in fb_match}
    resultados = []
    for uid in uids:
        fb = fb_by_uid.get(uid)
        p  = perfiles.get(uid)
        creado = (fb or {}).get("creado") or (
            p["created_at"].isoformat() if p and p.get("created_at") else None
        )
        resultados.append({
            "email":          fb["email"] if fb else p["email"],
            "nombre":         (p or {}).get("nombre") or (fb or {}).get("nombre"),
            "en_firebase":    bool(fb),
            "en_kipu":        bool(p),
            "email_verified": fb["email_verified"] if fb else None,
            "providers":      fb["providers"] if fb else [],
            "creado":         creado,
            "estado":         _estado_cuenta(
                                  bool(fb), bool(p),
                                  bool(fb and fb["email_verified"]),
                                  bool(p and p["tiene_empresa"]),
                              ),
        })

    resultados.sort(key=lambda r: r["creado"] or "", reverse=True)

    return {
        "ok":       True,
        "data":     resultados[:30],
        "total":    len(resultados),
        "cache_ts": datetime.fromtimestamp(_FB_CACHE["ts"], tz=timezone.utc).isoformat(),
    }


# -----------------------------------------------------------------------------
# GET /soporte/buscar?email= — detalle exacto
# -----------------------------------------------------------------------------
@router.get("/soporte/buscar", summary="Buscar una cuenta por email exacto (Firebase + Kipu)")
async def soporte_buscar(
    email:     str          = Query(..., min_length=3, max_length=254),
    auth_data: dict         = Depends(verify_superadmin),
    db:        AsyncSession = Depends(get_db),
):
    email   = _norm_email(email)
    fb_user = await _fb_por_email(email)

    res = await db.execute(text("""
        SELECT p.id, p.firebase_uid, p.email, p.full_name AS nombre,
               p.whatsapp_number, p.created_at
        FROM profiles p
        WHERE lower(p.email) = :email OR p.firebase_uid = :uid
        LIMIT 1
    """), {"email": email, "uid": fb_user.uid if fb_user else ""})
    perfil  = res.fetchone()
    profile = dict(perfil._mapping) if perfil else None

    emisores = []
    if profile:
        res_e = await db.execute(text("""
            SELECT e.id AS emisor_id, e.ruc,
                   COALESCE(e.nombre_comercial, e.razon_social) AS nombre,
                   e.ambiente, eu.rol
            FROM emisor_usuarios eu
            JOIN emisores e ON e.id = eu.emisor_id
            WHERE eu.profile_id = :pid
            ORDER BY eu.created_at ASC
        """), {"pid": profile["id"]})
        emisores = [dict(r._mapping) for r in res_e.fetchall()]

    estado = _estado_cuenta(
        bool(fb_user), bool(profile),
        bool(fb_user and fb_user.email_verified),
        bool(emisores),
    )

    return {
        "ok": True,
        "data": {
            "email":    email,
            "estado":   estado,
            "firebase": _fb_dict(fb_user) if fb_user else None,
            "profile":  profile,
            "emisores": emisores,
        },
    }


# -----------------------------------------------------------------------------
# POST /soporte/link-verificacion — genera y (opcional) envía por correo
# -----------------------------------------------------------------------------
@router.post("/soporte/link-verificacion", summary="Generar y enviar link de verificación")
async def soporte_link_verificacion(
    req:       EnviarLinkRequest,
    auth_data: dict         = Depends(verify_superadmin),
    db:        AsyncSession = Depends(get_db),
):
    email   = _norm_email(req.email)
    fb_user = await _fb_por_email(email)
    if not fb_user:
        raise HTTPException(status_code=404, detail="No existe en Firebase.")
    if fb_user.email_verified:
        raise HTTPException(status_code=400, detail="El correo ya está verificado.")

    try:
        link = await asyncio.to_thread(
            fb_auth.generate_email_verification_link, email, _action_settings()
        )
    except Exception as ex:
        raise HTTPException(status_code=502, detail=f"Firebase: {ex}")

    envio = None
    if req.enviar:
        nombre = await _nombre_perfil(db, email) or fb_user.display_name
        envio  = await mail_service.send_link_verificacion(email=email, link=link, nombre=nombre)

    enviado = bool(envio and envio.get("exito"))
    await _audit_soporte(db, auth_data, fb_user.uid, {
        "accion_soporte": "link_verificacion",
        "email":          email,
        "enviado_email":  enviado,
    })

    return {
        "ok":          True,
        "link":        link,
        "enviado":     enviado,
        "envio_error": None if (not req.enviar or enviado) else (envio or {}).get("error") or (envio or {}).get("mensaje"),
    }


# -----------------------------------------------------------------------------
# POST /soporte/link-password — genera y (opcional) envía por correo
# -----------------------------------------------------------------------------
@router.post("/soporte/link-password", summary="Generar y enviar link de restablecimiento de contraseña")
async def soporte_link_password(
    req:       EnviarLinkRequest,
    auth_data: dict         = Depends(verify_superadmin),
    db:        AsyncSession = Depends(get_db),
):
    email   = _norm_email(req.email)
    fb_user = await _fb_por_email(email)
    if not fb_user:
        raise HTTPException(status_code=404, detail="No existe en Firebase.")
    if "password" not in [p.provider_id for p in fb_user.provider_data]:
        raise HTTPException(status_code=400, detail="El usuario entra con Google, no tiene contraseña.")

    try:
        link = await asyncio.to_thread(
            fb_auth.generate_password_reset_link, email, _action_settings()
        )
    except Exception as ex:
        raise HTTPException(status_code=502, detail=f"Firebase: {ex}")

    envio = None
    if req.enviar:
        nombre = await _nombre_perfil(db, email) or fb_user.display_name
        envio  = await mail_service.send_link_password(email=email, link=link, nombre=nombre)

    enviado = bool(envio and envio.get("exito"))
    await _audit_soporte(db, auth_data, fb_user.uid, {
        "accion_soporte": "link_password",
        "email":          email,
        "enviado_email":  enviado,
    })

    return {
        "ok":          True,
        "link":        link,
        "enviado":     enviado,
        "envio_error": None if (not req.enviar or enviado) else (envio or {}).get("error") or (envio or {}).get("mensaje"),
    }


# -----------------------------------------------------------------------------
# POST /soporte/verificar — verificación manual (identidad confirmada por soporte)
# -----------------------------------------------------------------------------
@router.post("/soporte/verificar", summary="Marcar email como verificado manualmente")
async def soporte_verificar_manual(
    req:       VerificarManualRequest,
    auth_data: dict         = Depends(verify_superadmin),
    db:        AsyncSession = Depends(get_db),
):
    email   = _norm_email(req.email)
    fb_user = await _fb_por_email(email)
    if not fb_user:
        raise HTTPException(status_code=404, detail="No existe en Firebase.")
    if fb_user.email_verified:
        return {"ok": True, "mensaje": "El correo ya estaba verificado."}

    try:
        await asyncio.to_thread(fb_auth.update_user, fb_user.uid, email_verified=True)
    except Exception as ex:
        raise HTTPException(status_code=502, detail=f"Firebase: {ex}")

    await _audit_soporte(db, auth_data, fb_user.uid, {
        "accion_soporte": "verificacion_manual",
        "email":          email,
        "motivo":         req.motivo.strip(),
    })
    return {"ok": True, "mensaje": "Correo marcado como verificado. El usuario ya puede iniciar sesión."}