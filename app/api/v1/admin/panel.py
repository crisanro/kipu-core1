# app/api/v1/admin/panel.py
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone, timedelta
from app.core.database import get_db
from app.core.security import verify_firebase_token
from app.services.notification_service import crear_notificacion, notificar_todos_emisores
from app.services.audit_service import audit_log
from app.api.v1.admin.stripe_webhook import _emitir_factura_kipu, _auth_stripe

router = APIRouter()

# =============================================================================
# GUARD SUPERADMIN
# =============================================================================
async def verify_superadmin(auth_data: dict = Depends(verify_firebase_token)):
    if auth_data.get("role") != "superadmin":
        raise HTTPException(status_code=403, detail="Acceso restringido.")
    return auth_data

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
    res = await db.execute(text("""
        SELECT
            COUNT(DISTINCT e.id)                                                   AS total_emisores,
            COUNT(DISTINCT CASE WHEN e.ambiente = 2 THEN e.id END)                 AS en_produccion,
            COUNT(DISTINCT CASE WHEN e.ambiente = 1 THEN e.id END)                 AS en_pruebas,
            COUNT(DISTINCT CASE WHEN s.estado IN ('ACTIVO','TRIAL') THEN e.id END) AS con_suscripcion,
            COUNT(DISTINCT d.id)                                                   AS total_facturas,
            COALESCE(SUM(d.importe_total), 0)                                      AS monto_total,
            COUNT(DISTINCT CASE WHEN d.estado_sri = 'AUTORIZADO' THEN d.id END)    AS autorizadas,
            COALESCE(SUM(uc.balance), 0)                                           AS creditos_totales
        FROM emisores e
        LEFT JOIN documentos_emitidos d ON d.emisor_id = e.id
                                       AND d.tipo_doc IN ('FAC', 'LIQ')
        LEFT JOIN user_credits  uc ON uc.emisor_id = e.id
        LEFT JOIN subscriptions s  ON s.emisor_id  = e.id
    """))
    row = res.fetchone()
    return {"ok": True, "data": dict(row._mapping)}

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
    # Verificar que el emisor existe
    res_e = await db.execute(text("""
        SELECT id, ruc, razon_social, nombre_comercial,
               direccion_matriz, obligado_contabilidad,
               contribuyente_especial, p12_path
        FROM emisores WHERE id = :eid
    """), {"eid": emisor_id})
    emisor = res_e.fetchone()
    if not emisor:
        raise HTTPException(status_code=404, detail="Emisor no encontrado.")

    # Construir solo los campos que vienen en el request
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

    # Construir SET dinámico
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

    await db.execute(text("""
        UPDATE user_credits
        SET balance = balance + :qty, last_updated = NOW()
        WHERE emisor_id = :eid
    """), {"qty": cantidad, "eid": emisor_id})

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
        detalle   = {"origen": "admin_manual", "cantidad": cantidad, "notas": notas},
    )
    await db.commit()
    return {"ok": True, "mensaje": f"{cantidad} créditos agregados al emisor {emisor_id}."}

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
    # Verificar que el emisor existe
    res_e = await db.execute(text("""
        SELECT id, ruc, razon_social FROM emisores WHERE id = :eid
    """), {"eid": req.emisor_id})
    emisor = res_e.fetchone()
    if not emisor:
        raise HTTPException(status_code=404, detail="Emisor no encontrado.")

    # Fecha del comprobante — default hoy
    from datetime import date
    fecha_comprobante = req.fecha_pago or date.today().isoformat()

    # Calcular período
    now = datetime.now(tz=timezone.utc)
    if req.periodo == "ANUAL":
        period_end = now + timedelta(days=365)
    else:
        period_end = now + timedelta(days=30)

    # Upsert suscripción
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

    # Audit con toda la info del pago
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

    # Notificación al emisor
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
    else:
        await notificar_todos_emisores(
            db              = db,
            tipo            = data.tipo,
            titulo          = data.titulo,
            mensaje         = data.mensaje,
            referencia      = data.referencia,
            solo_produccion = True,
        )
        return {"ok": True, "mensaje": "Notificación enviada a todos los emisores en producción."}