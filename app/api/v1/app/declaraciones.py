# app/api/v1/app/declaraciones.py
from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import verify_firebase_token
from app.workers.declaraciones_worker import calcular_vencimiento

router = APIRouter()

# ── GET /actual — estado declaración del mes en curso ─────────────────────────
@router.get("/actual", summary="Obtener declaración del mes actual")
async def obtener_declaracion_actual(
    auth_data: dict         = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db),
):
    emisor_id = auth_data.get("emisor_id")
    if not emisor_id:
        raise HTTPException(status_code=400, detail="EMISOR NO VINCULADO.")

    hoy     = date.today()
    periodo = date(hoy.year, hoy.month, 1)

    # Buscar emisor para el RUC
    res_emisor = await db.execute(
        text("SELECT ruc, ambiente FROM emisores WHERE id = :eid"),
        {"eid": emisor_id}
    )
    emisor = res_emisor.fetchone()
    if not emisor:
        raise HTTPException(status_code=404, detail="EMISOR NO ENCONTRADO.")

    # Solo aplica en producción
    if emisor.ambiente != 2:
        return {"ok": True, "aplica": False}

    # Buscar declaración del mes
    res = await db.execute(text("""
        SELECT id, tipo, periodo, declarado, fecha_declarado
        FROM declaraciones_sri
        WHERE emisor_id = :eid AND tipo = '104' AND periodo = :periodo
    """), {"eid": emisor_id, "periodo": periodo})
    decl = res.fetchone()

    # Si no existe aún — puede pasar si el worker no corrió
    if not decl:
        await db.execute(text("""
            INSERT INTO declaraciones_sri (emisor_id, tipo, periodo, declarado)
            VALUES (:eid, '104', :periodo, false)
            ON CONFLICT (emisor_id, tipo, periodo) DO NOTHING
        """), {"eid": emisor_id, "periodo": periodo})
        await db.commit()
        declarado      = False
        fecha_declarado = None
    else:
        declarado       = decl.declarado
        fecha_declarado = decl.fecha_declarado

    vencimiento    = calcular_vencimiento(emisor.ruc, periodo)
    dias_restantes = (vencimiento - hoy).days

    return {
        "ok":     True,
        "aplica": True,
        "data": {
            "periodo":         periodo.strftime("%B %Y"),
            "periodo_iso":     str(periodo),
            "declarado":       declarado,
            "fecha_declarado": str(fecha_declarado) if fecha_declarado else None,
            "vencimiento":     str(vencimiento),
            "vencimiento_fmt": vencimiento.strftime("%d de %B de %Y"),
            "dias_restantes":  dias_restantes,
            "estado":          _estado(declarado, dias_restantes),
        }
    }


# ── POST /declarar — marcar como declarado ────────────────────────────────────
@router.post("/declarar", summary="Marcar declaración como realizada")
async def marcar_declarado(
    auth_data: dict         = Depends(verify_firebase_token),
    db:        AsyncSession = Depends(get_db),
):
    emisor_id  = auth_data.get("emisor_id")
    profile_id = auth_data.get("profile_id")
    if not emisor_id:
        raise HTTPException(status_code=400, detail="EMISOR NO VINCULADO.")

    hoy     = date.today()
    periodo = date(hoy.year, hoy.month, 1)

    res = await db.execute(text("""
        UPDATE declaraciones_sri
        SET declarado       = true,
            fecha_declarado = NOW(),
            declarado_por   = :pid
        WHERE emisor_id = :eid
          AND tipo      = '104'
          AND periodo   = :periodo
        RETURNING id
    """), {
        "eid":     emisor_id,
        "pid":     str(profile_id) if profile_id else None,
        "periodo": periodo,
    })
    updated = res.fetchone()
    if not updated:
        raise HTTPException(status_code=404, detail="Declaración no encontrada.")

    await db.commit()
    return {
        "ok":      True,
        "mensaje": "Declaración marcada correctamente. ¡Hasta el próximo mes!"
    }


# ── Helper estado ──────────────────────────────────────────────────────────────
def _estado(declarado: bool, dias_restantes: int) -> str:
    if declarado:           return "DECLARADO"
    if dias_restantes < 0:  return "VENCIDO"
    if dias_restantes <= 3: return "URGENTE"
    if dias_restantes <= 7: return "PROXIMO"
    return "PENDIENTE"