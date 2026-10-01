# app/workers/declaraciones_worker.py
#
# Worker de declaraciones tributarias. Revisa cada hora; una vez al día (desde las 8:00
# hora Ecuador) hace:
#   1. Asegura las filas de periodos de todos los emisores en producción (por calendario).
#   2. Notifica: periodo listo para declarar · vence en 3 días · vence hoy.
#   3. Día 1: limpia documentos sandbox con más de 30 días.
#
# Es idempotente: si se reinicia o corre en varias instancias, no duplica nada.
# Cada notificación se "reclama" en la base (notif_*_at) y se confirma ANTES de
# enviarse. Si el envío falla, el reclamo se libera y se reintenta en la próxima vuelta.
#
# Las filas ya NO dependen de este worker: también se crean al abrir /reportes.

import asyncio
import traceback
from datetime import datetime, date, timedelta

from sqlalchemy import text
from app.core.database import AsyncSessionLocal
from app.services.notification_service import crear_notificacion
from app.services.declaraciones import periodos as per
from app.services.declaraciones import registro
from app.services.declaraciones.obligaciones import cargar_obligaciones
from app.services.declaraciones.iva_104 import calcular_iva_104, resumen_iva

TITULO_TIPO = {"104": "IVA", "ATS": "ATS", "102": "Impuesto a la Renta"}


# =============================================================================
# COMPATIBILIDAD — funciones que otros módulos pueden seguir importando
# =============================================================================
def calcular_vencimiento(ruc: str, periodo: date, tipo_periodo: str = "MENSUAL") -> date:
    """Vencimiento del 104. Delegado al calendario (ahora corre fines de semana al lunes)."""
    return per.vencimiento(ruc, per.crear_periodo("104", tipo_periodo, periodo))


def rango_mensual(periodo: date):
    """(inicio, primer día del mes siguiente) — rango con fin exclusivo, como antes."""
    return periodo, per.sumar_meses(periodo, 1)


def rango_semestral(periodo: date):
    p = per.crear_periodo("104", "SEMESTRAL", periodo)
    return p.inicio, p.fin + timedelta(days=1)


def nombre_periodo(periodo: date, tipo_periodo: str) -> str:
    return per.crear_periodo("104", tipo_periodo, periodo).nombre


async def precalcular_totales(db, emisor_id: int, fi: date, ff: date) -> dict:
    """ff exclusivo (compatibilidad). Usa el mismo cálculo del 104."""
    calc = await calcular_iva_104(db, emisor_id, fi, ff - timedelta(days=1))
    return resumen_iva(calc)


# =============================================================================
# 1. ASEGURAR PERIODOS
# =============================================================================
async def asegurar_periodos_emisor(db, emisor_id: int, hoy: date) -> None:
    """Crea las filas de este año y el anterior para todo lo que declara el emisor."""
    obl = await cargar_obligaciones(db, emisor_id)
    if not obl or not obl.en_produccion:
        return
    for tipo in obl.tipos_que_aplican():
        tp = obl.tipo_periodo(tipo)
        periodos = (
            per.periodos_del_anio(tipo, tp, hoy.year,     obl.inicio, hoy) +
            per.periodos_del_anio(tipo, tp, hoy.year - 1, obl.inicio, hoy)
        )
        await registro.asegurar_filas(db, obl, periodos)


async def asegurar_periodos_todos(db, hoy: date) -> None:
    res = await db.execute(text("SELECT id FROM emisores WHERE ambiente = 2"))
    ids = [r.id for r in res.fetchall()]
    ok = 0
    for eid in ids:
        try:
            await asegurar_periodos_emisor(db, eid, hoy)
            await db.commit()
            ok += 1
        except Exception as e:
            await db.rollback()
            print(f"[Declaraciones] ⚠️ Emisor {eid}: {e}")
    print(f"[Declaraciones] 📋 Periodos asegurados: {ok}/{len(ids)} emisores")


# =============================================================================
# 2. NOTIFICACIONES (idempotentes)
# =============================================================================
async def _reclamar(db, fila_id: int, columna: str) -> bool:
    """Marca la notificación como enviada. Solo una instancia gana."""
    res = await db.execute(text(f"""
        UPDATE declaraciones_sri SET {columna} = NOW()
        WHERE id = :id AND {columna} IS NULL
        RETURNING id
    """), {"id": fila_id})
    return res.fetchone() is not None


async def _liberar(db, fila_id: int, columna: str) -> None:
    """Deshace un reclamo cuando la notificación falló, para reintentar en la próxima vuelta."""
    try:
        await db.execute(text(f"""
            UPDATE declaraciones_sri SET {columna} = NULL
            WHERE id = :id
        """), {"id": fila_id})
        await db.commit()
        print(f"[Declaraciones] ↩️ Reclamo liberado ({columna}) — fila {fila_id}, se reintentará")
    except Exception as e:
        await db.rollback()
        print(f"[Declaraciones] ⚠️ No se pudo liberar reclamo ({columna}) fila {fila_id}: {e}")


async def _candidatas(db, condicion: str, params: dict):
    res = await db.execute(text(f"""
        SELECT d.id, d.emisor_id, d.tipo, d.tipo_periodo, d.periodo, d.vencimiento
        FROM declaraciones_sri d
        JOIN emisores e ON e.id = d.emisor_id
        WHERE d.declarado = false
          AND e.ambiente  = 2
          AND {condicion}
    """), params)
    return res.fetchall()


def _periodo_de_fila(f) -> per.Periodo:
    tp = f.tipo_periodo or ("ANUAL" if f.tipo == "102" else "MENSUAL")
    return per.crear_periodo(f.tipo, tp, f.periodo)


async def notificar_disponibles(db, hoy: date) -> int:
    """Periodo cerrado y todavía a tiempo: 'ya puedes declarar'."""
    enviados = 0
    for f in await _candidatas(db, "d.notif_disponible_at IS NULL AND d.vencimiento >= :hoy", {"hoy": hoy}):
        p = _periodo_de_fila(f)
        if p.en_curso(hoy):
            continue

        # 1. Reclamar y confirmar: ningún otro worker toma esta fila
        if not await _reclamar(db, f.id, "notif_disponible_at"):
            continue
        await db.commit()

        # 2. Notificar
        ok = await crear_notificacion(
            db         = db,
            emisor_id  = f.emisor_id,
            tipo       = "DECLARACION",
            titulo     = f"📋 {TITULO_TIPO.get(f.tipo, f.tipo)} — {p.nombre}",
            mensaje    = f"Ya puedes declarar. Tienes hasta el {per.fecha_larga(f.vencimiento)}. "
                         f"Ya calculamos los valores por ti.",
            referencia = "/reportes",
        )

        # 3. Si falló, liberar para reintentar en la próxima vuelta
        if not ok:
            await _liberar(db, f.id, "notif_disponible_at")
            continue

        enviados += 1
    return enviados


async def notificar_vencimientos(db, hoy: date) -> int:
    enviados = 0
    avisos = [
        ("notif_3dias_at", hoy + timedelta(days=3), "⚠️ {t} vence en 3 días",
         "{p} vence el {v}. No olvides declararla en SRI en Línea."),
        ("notif_hoy_at",   hoy,                     "❌ {t} vence HOY",
         "{p} vence hoy. Declara ahora en SRI en Línea para evitar multas."),
    ]
    for columna, fecha, titulo, mensaje in avisos:
        for f in await _candidatas(db, f"d.{columna} IS NULL AND d.vencimiento = :fecha", {"fecha": fecha}):
            # 1. Reclamar y confirmar
            if not await _reclamar(db, f.id, columna):
                continue
            await db.commit()

            # 2. Notificar
            p = _periodo_de_fila(f)
            t = TITULO_TIPO.get(f.tipo, f.tipo)
            ok = await crear_notificacion(
                db         = db,
                emisor_id  = f.emisor_id,
                tipo       = "DECLARACION",
                titulo     = titulo.format(t=f"Tu declaración de {t}"),
                mensaje    = mensaje.format(p=p.nombre.capitalize(), v=per.fecha_larga(f.vencimiento)),
                referencia = "/reportes",
            )

            # 3. Si falló, liberar para reintentar
            if not ok:
                await _liberar(db, f.id, columna)
                continue

            enviados += 1
    return enviados


# =============================================================================
# EMISOR QUE PASA A PRODUCCIÓN
# =============================================================================
async def crear_declaracion_emisor(db, emisor_id: int, ruc: str = "", periodo_iva: str = "MENSUAL"):
    """
    Llamar cuando un emisor pasa a producción. Registra la fecha de inicio
    (desde ahí existen sus periodos) y crea los del año en curso.
    Firma compatible con la versión anterior (ruc y periodo_iva ya no se usan).

    - Los cambios se confirman ANTES de notificar: si la notificación falla,
      los periodos quedan creados igual.
    - La notificación de bienvenida sale solo la PRIMERA vez que el emisor
      pasa a producción (idempotente si se llama varias veces).
    """
    hoy = per.hoy_ec()
    primera_vez = False

    # 1. Registrar inicio de producción + crear periodos (y confirmar)
    try:
        res = await db.execute(text("""
            UPDATE emisores
            SET fecha_inicio_produccion = :hoy
            WHERE id = :eid AND fecha_inicio_produccion IS NULL
            RETURNING id
        """), {"hoy": hoy, "eid": emisor_id})
        primera_vez = res.fetchone() is not None

        await asegurar_periodos_emisor(db, emisor_id, hoy)
        await db.commit()
        print(f"[Declaraciones] ✅ Periodos creados para emisor {emisor_id}")
    except Exception as e:
        await db.rollback()
        print(f"[Declaraciones] ⚠️ Error creando periodos del emisor {emisor_id}: {e}")
        return

    # 2. Bienvenida — solo la primera vez. Si falla, los periodos ya quedaron guardados.
    if primera_vez:
        await crear_notificacion(
            db         = db,
            emisor_id  = emisor_id,
            tipo       = "DECLARACION",
            titulo     = "📋 Tus declaraciones ya están en Kipu",
            mensaje    = "Desde ahora calculamos tus declaraciones con tus comprobantes y te avisamos antes de cada vencimiento.",
            referencia = "/reportes",
        )


# =============================================================================
# 3. LIMPIEZA SANDBOX (sin cambios)
# =============================================================================
async def limpiar_sandbox(db):
    """Elimina documentos de prueba con más de 30 días."""
    print("[Sandbox] 🧹 Limpiando documentos de prueba antiguos...")
    try:
        from app.services.storage_service import delete_folder
        res = await db.execute(text("""
            SELECT DISTINCT e.ruc
            FROM documentos_emitidos d
            JOIN emisores e ON e.id = d.emisor_id
            WHERE d.es_sandbox = true
              AND d.created_at < NOW() - INTERVAL '30 days'
        """))
        for row in res.fetchall():
            try:
                delete_folder(f"{row.ruc}/sandbox/")
                print(f"[Sandbox] 🗑️ R2 limpiado para RUC: {row.ruc}")
            except Exception as e:
                print(f"[Sandbox] ⚠️ Error R2 {row.ruc}: {e}")

        await db.execute(text("""
            DELETE FROM notificaciones
            WHERE referencia IN (
                SELECT '/documentos/' || id::text
                FROM documentos_emitidos
                WHERE es_sandbox = true
                  AND created_at < NOW() - INTERVAL '30 days'
            )
        """))
        res_del = await db.execute(text("""
            DELETE FROM documentos_emitidos
            WHERE es_sandbox = true
              AND created_at < NOW() - INTERVAL '30 days'
            RETURNING id
        """))
        eliminados = len(res_del.fetchall())
        await db.commit()
        print(f"[Sandbox] ✅ {eliminados} documentos de prueba eliminados")
    except Exception as e:
        await db.rollback()
        print(f"[Sandbox] ❌ Error en limpieza: {e}")


# =============================================================================
# LOOP PRINCIPAL
# =============================================================================
async def ejecutar_ciclo_diario(hoy: date) -> None:
    async with AsyncSessionLocal() as db:
        await asegurar_periodos_todos(db, hoy)
        disp = await notificar_disponibles(db, hoy)
        venc = await notificar_vencimientos(db, hoy)
        print(f"[Declaraciones] 🔔 Avisos: {disp} disponibles · {venc} por vencer")
        if hoy.day == 1:
            await limpiar_sandbox(db)


async def iniciar_worker_declaraciones():
    print("[Declaraciones] 🚀 Worker iniciado.")
    ultimo_ciclo: date | None = None

    while True:
        try:
            ahora = datetime.now(per.TZ_EC)
            hoy   = ahora.date()
            # Desde las 8:00, una vez por día. Si el servidor estuvo caído a las 8,
            # corre en cuanto vuelva (y aunque repita, no duplica nada).
            if ahora.hour >= 8 and ultimo_ciclo != hoy:
                await ejecutar_ciclo_diario(hoy)
                ultimo_ciclo = hoy
        except Exception as e:
            print(f"[Declaraciones] ❌ Error en loop: {e}")
            traceback.print_exc()

        await asyncio.sleep(3600)