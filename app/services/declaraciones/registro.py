# app/services/declaraciones/registro.py
#
# Filas de declaraciones_sri: una por (emisor, tipo, periodo).
#
# Se crean a partir del calendario cada vez que se leen (upsert idempotente),
# así que no dependen de que el worker haya corrido. El vencimiento se
# recalcula mientras no esté declarado, para corregir filas viejas.

from datetime import date
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .periodos import Periodo, vencimiento, estado, fecha_larga, hoy_ec
from .obligaciones import Obligaciones


async def asegurar_filas(db: AsyncSession, obl: Obligaciones, periodos: list[Periodo]) -> None:
    """Crea las filas que falten. No hace commit."""
    if not periodos:
        return
    await db.execute(text("""
        INSERT INTO declaraciones_sri (emisor_id, tipo, tipo_periodo, periodo, vencimiento, declarado)
        VALUES (:eid, :tipo, :tipo_periodo, :periodo, :vencimiento, false)
        ON CONFLICT (emisor_id, tipo, periodo) DO UPDATE SET
            vencimiento  = EXCLUDED.vencimiento,
            tipo_periodo = EXCLUDED.tipo_periodo
        WHERE declaraciones_sri.declarado = false
    """), [
        {
            "eid":          obl.emisor_id,
            "tipo":         p.tipo,
            "tipo_periodo": p.tipo_periodo,
            "periodo":      p.inicio,
            "vencimiento":  vencimiento(obl.ruc, p, obl.tipo_emisor),
        }
        for p in periodos
    ])


async def leer_filas(db: AsyncSession, emisor_id: int, tipo: str, periodos: list[Periodo]) -> dict[date, object]:
    if not periodos:
        return {}
    res = await db.execute(text("""
        SELECT id, periodo, vencimiento, declarado, fecha_declarado, totales
        FROM declaraciones_sri
        WHERE emisor_id = :eid AND tipo = :tipo AND periodo = ANY(:periodos)
    """), {"eid": emisor_id, "tipo": tipo, "periodos": [p.inicio for p in periodos]})
    return {r.periodo: r for r in res.fetchall()}


def serializar(p: Periodo, fila, hoy: date | None = None) -> dict:
    """Formato común para /historial, /actual y /periodo. Todo calculado en hora de Ecuador."""
    hoy      = hoy or hoy_ec()
    en_curso = p.en_curso(hoy)
    dias     = (fila.vencimiento - hoy).days
    return {
        "id":              fila.id,
        "tipo":            p.tipo,
        "tipo_periodo":    p.tipo_periodo,
        "periodo":         p.inicio.isoformat(),
        "periodo_key":     p.key,
        "periodo_fmt":     p.nombre,
        "desde":           p.inicio.isoformat(),
        "hasta":           p.fin.isoformat(),
        "vencimiento":     fila.vencimiento.isoformat(),
        "vencimiento_fmt": fecha_larga(fila.vencimiento),
        "dias_restantes":  dias,
        "en_curso":        en_curso,
        "declarado":       fila.declarado,
        "fecha_declarado": fila.fecha_declarado.isoformat() if fila.fecha_declarado else None,
        "estado":          estado(fila.declarado, en_curso, dias),
        "totales":         fila.totales or {},
    }


async def marcar_declarado(db: AsyncSession, emisor_id: int, p: Periodo, profile_id) -> bool:
    """No hace commit. Devuelve False si la fila no existe."""
    res = await db.execute(text("""
        UPDATE declaraciones_sri SET
            declarado       = true,
            fecha_declarado = NOW(),
            declarado_por   = :pid
        WHERE emisor_id = :eid AND tipo = :tipo AND periodo = :periodo
        RETURNING id
    """), {
        "eid":     emisor_id,
        "tipo":    p.tipo,
        "periodo": p.inicio,
        "pid":     str(profile_id) if profile_id else None,
    })
    return res.fetchone() is not None