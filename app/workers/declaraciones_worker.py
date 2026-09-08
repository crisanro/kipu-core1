# app/workers/declaraciones_worker.py
#
# Worker de declaraciones tributarias.
# Corre cada hora, ejecuta acciones según el día y hora.
#
# Acciones:
#   Día 1 del mes — crear declaraciones mensuales del mes anterior
#   Día 1 de julio — crear declaraciones semestrales S1 (enero-junio)
#   Día 1 de enero — crear declaraciones semestrales S2 (julio-diciembre)
#   Todos los días — recordatorio 3 días antes del vencimiento
#   Todos los días — alerta el día del vencimiento

import json
import asyncio
from datetime import datetime, date, timedelta
from calendar import monthrange
import pytz
from sqlalchemy import text
from app.core.database import AsyncSessionLocal
from app.services.notification_service import crear_notificacion

TZ_EC = pytz.timezone("America/Guayaquil")

# =============================================================================
# CALCULAR VENCIMIENTO
# =============================================================================
def calcular_vencimiento(ruc: str, periodo: date, tipo_periodo: str = "MENSUAL") -> date:
    """
    Fecha límite según el 9° dígito del RUC.
    Para MENSUAL: vence el mes siguiente al período.
    Para SEMESTRAL: vence el mes siguiente al último mes del semestre.
      S1 (2026-01-01) → vence en julio
      S2 (2026-07-01) → vence en enero del año siguiente
    """
    TABLA = {
        "1": 10, "2": 12, "3": 14, "4": 16, "5": 18,
        "6": 20, "7": 22, "8": 24, "9": 26, "0": 28,
    }
    noveno  = ruc[8] if len(ruc) >= 9 else "1"
    dia_lim = TABLA.get(noveno, 28)

    if tipo_periodo == "SEMESTRAL":
        # S1 → periodo.month == 1 → vence en julio
        # S2 → periodo.month == 7 → vence en enero del año siguiente
        if periodo.month == 1:
            mes_vence  = 7
            anio_vence = periodo.year
        else:  # mes == 7
            mes_vence  = 1
            anio_vence = periodo.year + 1
    else:
        # MENSUAL — mes siguiente al período
        if periodo.month == 12:
            mes_vence  = 1
            anio_vence = periodo.year + 1
        else:
            mes_vence  = periodo.month + 1
            anio_vence = periodo.year

    ultimo_dia = monthrange(anio_vence, mes_vence)[1]
    dia_real   = min(dia_lim, ultimo_dia)
    return date(anio_vence, mes_vence, dia_real)

# =============================================================================
# PRECALCULAR TOTALES DEL PERÍODO
# =============================================================================
async def precalcular_totales(db, emisor_id: int, fi: date, ff: date) -> dict:
    """
    Calcula los totales fiscales del período desde documentos_emitidos
    y documentos_recibidos. Acepta rango explícito (fi, ff) para
    soportar tanto períodos mensuales como semestrales.
    """
    # Ventas autorizadas
    res_ventas = await db.execute(text("""
        SELECT
            COALESCE(SUM(importe_total), 0) AS total_ventas,
            COALESCE(SUM(
                CASE WHEN (datos->'infoFactura'->>'totalSinImpuestos') IS NOT NULL
                THEN (datos->'infoFactura'->>'totalSinImpuestos')::numeric
                ELSE 0 END
            ), 0) AS base_imponible,
            COALESCE(SUM(
                importe_total - COALESCE(
                    (datos->'infoFactura'->>'totalSinImpuestos')::numeric, 0
                )
            ), 0) AS iva_cobrado
        FROM documentos_emitidos
        WHERE emisor_id  = :eid
          AND tipo_doc   IN ('FAC', 'LIQ')
          AND estado_sri = 'AUTORIZADO'
          AND es_sandbox = false
          AND fecha_emision >= :fi
          AND fecha_emision <  :ff
    """), {"eid": emisor_id, "fi": fi, "ff": ff})
    ventas = res_ventas.fetchone()

    # Compras — usa columnas desnormalizadas
    res_compras = await db.execute(text("""
        SELECT
            COALESCE(SUM(importe_total), 0)                                                    AS total_compras,
            COALESCE(SUM(CASE WHEN deducible_renta        THEN subtotal_base   ELSE 0 END), 0) AS total_deducible,
            COALESCE(SUM(CASE WHEN credito_tributario_iva THEN valor_iva_total ELSE 0 END), 0) AS credito_tributario
        FROM documentos_recibidos
        WHERE emisor_id  = :eid
          AND tipo_doc   IN ('FAC', 'LIQ')
          AND fecha_emision >= :fi
          AND fecha_emision <  :ff
    """), {"eid": emisor_id, "fi": fi, "ff": ff})
    compras = res_compras.fetchone()

    # Retenciones recibidas — usa valor_iva_total desnormalizado
    res_ret = await db.execute(text("""
        SELECT COALESCE(SUM(valor_iva_total), 0) AS total_retenciones
        FROM documentos_recibidos
        WHERE emisor_id  = :eid
          AND tipo_doc   = 'RET'
          AND fecha_emision >= :fi
          AND fecha_emision <  :ff
    """), {"eid": emisor_id, "fi": fi, "ff": ff})
    retenciones = res_ret.fetchone()

    iva_cobrado        = float(ventas.iva_cobrado)
    credito_tributario = float(compras.credito_tributario)
    ret_recibidas      = float(retenciones.total_retenciones)
    iva_causado        = iva_cobrado - credito_tributario
    iva_a_pagar        = max(0, iva_causado - ret_recibidas)
    saldo_favor        = abs(min(0, iva_causado - ret_recibidas))

    return {
        "ventas": {
            "total":          float(ventas.total_ventas),
            "base_imponible": float(ventas.base_imponible),
            "iva_cobrado":    round(iva_cobrado, 2),
        },
        "compras": {
            "total":              float(compras.total_compras),
            "total_deducible":    float(compras.total_deducible),
            "credito_tributario": round(credito_tributario, 2),
        },
        "retenciones_recibidas": round(ret_recibidas, 2),
        "resumen_iva": {
            "iva_cobrado":        round(iva_cobrado, 2),
            "credito_tributario": round(credito_tributario, 2),
            "iva_causado":        round(iva_causado, 2),
            "retenciones":        round(ret_recibidas, 2),
            "iva_a_pagar":        round(iva_a_pagar, 2),
            "saldo_a_favor":      round(saldo_favor, 2),
        }
    }

# =============================================================================
# HELPERS — rango de fechas por tipo de período
# =============================================================================
def rango_mensual(periodo: date):
    """Retorna (fi, ff) para un período mensual."""
    if periodo.month == 12:
        return periodo, date(periodo.year + 1, 1, 1)
    return periodo, date(periodo.year, periodo.month + 1, 1)

def rango_semestral(periodo: date):
    """
    Retorna (fi, ff) para un período semestral.
    periodo.month == 1 → S1 enero-junio
    periodo.month == 7 → S2 julio-diciembre
    """
    if periodo.month == 1:
        return date(periodo.year, 1, 1), date(periodo.year, 7, 1)
    else:
        return date(periodo.year, 7, 1), date(periodo.year + 1, 1, 1)

def nombre_periodo(periodo: date, tipo_periodo: str) -> str:
    if tipo_periodo == "SEMESTRAL":
        if periodo.month == 1:
            return f"1er semestre {periodo.year}"
        return f"2do semestre {periodo.year}"
    return periodo.strftime("%B %Y")

# =============================================================================
# CREAR DECLARACIONES DEL MES/SEMESTRE
# =============================================================================
async def crear_declaraciones_mes(db, hoy: date):
    """
    Día 1 de cada mes:
    - Crea declaraciones 104 MENSUAL para emisores con periodo_iva = MENSUAL
    - Crea declaraciones 104 SEMESTRAL el 1 de julio (S1) y 1 de enero (S2)
    """
    # ── Mensuales ─────────────────────────────────────────────────────────────
    if hoy.month == 1:
        periodo_mensual = date(hoy.year - 1, 12, 1)
    else:
        periodo_mensual = date(hoy.year, hoy.month - 1, 1)

    fi_m, ff_m = rango_mensual(periodo_mensual)

    print(f"[Declaraciones] 📋 Mensuales — {nombre_periodo(periodo_mensual, 'MENSUAL')}...")

    res_m = await db.execute(text("""
        SELECT id, ruc FROM emisores
        WHERE ambiente = 2 AND periodo_iva = 'MENSUAL'
    """))
    emisores_mensuales = res_m.fetchall()

    creados_m = 0
    for emisor in emisores_mensuales:
        try:
            vencimiento = calcular_vencimiento(emisor.ruc, periodo_mensual, "MENSUAL")
            await db.execute(text("""
                INSERT INTO declaraciones_sri
                    (emisor_id, tipo, periodo, vencimiento, declarado)
                VALUES (:eid, '104', :periodo, :vencimiento, false)
                ON CONFLICT (emisor_id, tipo, periodo) DO NOTHING
            """), {"eid": emisor.id, "periodo": periodo_mensual, "vencimiento": vencimiento})

            totales = await precalcular_totales(db, emisor.id, fi_m, ff_m)
            await db.execute(text("""
                UPDATE declaraciones_sri
                SET totales = CAST(:totales AS jsonb)
                WHERE emisor_id = :eid AND tipo = '104' AND periodo = :periodo
            """), {"totales": json.dumps(totales), "eid": emisor.id, "periodo": periodo_mensual})

            await crear_notificacion(
                db        = db,
                emisor_id = emisor.id,
                tipo      = "DECLARACION",
                titulo    = f"📋 Declaración IVA — {nombre_periodo(periodo_mensual, 'MENSUAL')}",
                mensaje   = f"Tienes hasta el {vencimiento.strftime('%d de %B')} para declarar el IVA. Ya calculamos los totales por ti.",
                referencia = "/reportes",
            )
            creados_m += 1
        except Exception as e:
            print(f"[Declaraciones] ⚠️ Error mensual emisor {emisor.id}: {e}")

    print(f"[Declaraciones] ✅ Mensuales: {creados_m}/{len(emisores_mensuales)}")

    # ── Semestrales — solo en julio (S1) y enero (S2) ─────────────────────────
    es_inicio_semestre = hoy.month in (1, 7)
    if not es_inicio_semestre:
        await db.commit()
        return

    # S1: periodo = año-01-01, S2: periodo = año-07-01
    # En julio creamos S1 (enero-junio del mismo año)
    # En enero creamos S2 (julio-diciembre del año anterior)
    if hoy.month == 7:
        periodo_sem = date(hoy.year, 1, 1)      # S1
    else:  # enero
        periodo_sem = date(hoy.year - 1, 7, 1)  # S2

    fi_s, ff_s = rango_semestral(periodo_sem)

    print(f"[Declaraciones] 📋 Semestrales — {nombre_periodo(periodo_sem, 'SEMESTRAL')}...")

    res_s = await db.execute(text("""
        SELECT id, ruc FROM emisores
        WHERE ambiente = 2 AND periodo_iva = 'SEMESTRAL'
    """))
    emisores_semestrales = res_s.fetchall()

    creados_s = 0
    for emisor in emisores_semestrales:
        try:
            vencimiento = calcular_vencimiento(emisor.ruc, periodo_sem, "SEMESTRAL")
            await db.execute(text("""
                INSERT INTO declaraciones_sri
                    (emisor_id, tipo, periodo, vencimiento, declarado)
                VALUES (:eid, '104', :periodo, :vencimiento, false)
                ON CONFLICT (emisor_id, tipo, periodo) DO NOTHING
            """), {"eid": emisor.id, "periodo": periodo_sem, "vencimiento": vencimiento})

            totales = await precalcular_totales(db, emisor.id, fi_s, ff_s)
            await db.execute(text("""
                UPDATE declaraciones_sri
                SET totales = CAST(:totales AS jsonb)
                WHERE emisor_id = :eid AND tipo = '104' AND periodo = :periodo
            """), {"totales": json.dumps(totales), "eid": emisor.id, "periodo": periodo_sem})

            await crear_notificacion(
                db        = db,
                emisor_id = emisor.id,
                tipo      = "DECLARACION",
                titulo    = f"📋 Declaración IVA — {nombre_periodo(periodo_sem, 'SEMESTRAL')}",
                mensaje   = f"Tienes hasta el {vencimiento.strftime('%d de %B')} para declarar el IVA semestral. Ya calculamos los totales.",
                referencia = "/reportes",
            )
            creados_s += 1
        except Exception as e:
            print(f"[Declaraciones] ⚠️ Error semestral emisor {emisor.id}: {e}")

    print(f"[Declaraciones] ✅ Semestrales: {creados_s}/{len(emisores_semestrales)}")
    await db.commit()

# =============================================================================
# RECORDATORIOS
# =============================================================================
async def recordatorio_vencimiento_proximo(db, hoy: date):
    """Notifica 3 días antes del vencimiento."""
    res = await db.execute(text("""
        SELECT d.emisor_id, d.periodo, d.vencimiento, d.tipo
        FROM declaraciones_sri d
        JOIN emisores e ON e.id = d.emisor_id
        WHERE d.declarado   = false
          AND e.ambiente    = 2
          AND d.vencimiento = :fecha_objetivo
    """), {"fecha_objetivo": hoy + timedelta(days=3)})
    pendientes = res.fetchall()
    if not pendientes:
        return
    for p in pendientes:
        await crear_notificacion(
            db        = db,
            emisor_id = p.emisor_id,
            tipo      = "DECLARACION",
            titulo    = f"⚠️ Tu declaración {p.tipo} vence en 3 días",
            mensaje   = f"La declaración de {p.periodo.strftime('%B %Y')} vence el {p.vencimiento.strftime('%d de %B')}. No olvides declararla en el SRI en Línea.",
            referencia = "/reportes",
        )
    await db.commit()
    print(f"[Declaraciones] ⚠️ {len(pendientes)} recordatorios enviados")

async def alerta_vencimiento_hoy(db, hoy: date):
    """Alerta el mismo día del vencimiento."""
    res = await db.execute(text("""
        SELECT d.emisor_id, d.periodo, d.tipo
        FROM declaraciones_sri d
        JOIN emisores e ON e.id = d.emisor_id
        WHERE d.declarado   = false
          AND e.ambiente    = 2
          AND d.vencimiento = :hoy
    """), {"hoy": hoy})
    pendientes = res.fetchall()
    if not pendientes:
        return
    for p in pendientes:
        await crear_notificacion(
            db        = db,
            emisor_id = p.emisor_id,
            tipo      = "DECLARACION",
            titulo    = f"❌ Tu declaración {p.tipo} vence HOY",
            mensaje   = f"La declaración de {p.periodo.strftime('%B %Y')} vence hoy. Declara ahora en el SRI en Línea antes de que sea tarde.",
            referencia = "/reportes",
        )
    await db.commit()
    print(f"[Declaraciones] ❌ {len(pendientes)} alertas de vencimiento HOY enviadas")

# =============================================================================
# HELPER PARA NUEVOS EMISORES
# =============================================================================
async def crear_declaracion_emisor(db, emisor_id: int, ruc: str, periodo_iva: str = "MENSUAL"):
    """
    Crea la declaración del período actual para un emisor nuevo
    que acaba de pasar a producción.
    """
    hoy = date.today()

    if periodo_iva == "SEMESTRAL":
        # Semestre actual o anterior según el mes
        if hoy.month < 7:
            # Estamos en S1 — crear S1 del año anterior si ya pasó julio,
            # o S2 del año anterior si estamos en enero-junio
            periodo = date(hoy.year - 1, 7, 1)  # S2 año anterior
        else:
            periodo = date(hoy.year, 1, 1)       # S1 año actual
        fi, ff = rango_semestral(periodo)
        tipo_periodo_str = "SEMESTRAL"
    else:
        # Mensual — mes anterior
        if hoy.month == 1:
            periodo = date(hoy.year - 1, 12, 1)
        else:
            periodo = date(hoy.year, hoy.month - 1, 1)
        fi, ff = rango_mensual(periodo)
        tipo_periodo_str = "MENSUAL"

    try:
        vencimiento = calcular_vencimiento(ruc, periodo, tipo_periodo_str)
        await db.execute(text("""
            INSERT INTO declaraciones_sri
                (emisor_id, tipo, periodo, vencimiento, declarado)
            VALUES (:eid, '104', :periodo, :vencimiento, false)
            ON CONFLICT (emisor_id, tipo, periodo) DO NOTHING
        """), {"eid": emisor_id, "periodo": periodo, "vencimiento": vencimiento})

        totales = await precalcular_totales(db, emisor_id, fi, ff)
        await db.execute(text("""
            UPDATE declaraciones_sri
            SET totales = CAST(:totales AS jsonb)
            WHERE emisor_id = :eid AND tipo = '104' AND periodo = :periodo
        """), {"totales": json.dumps(totales), "eid": emisor_id, "periodo": periodo})

        await crear_notificacion(
            db        = db,
            emisor_id = emisor_id,
            tipo      = "DECLARACION",
            titulo    = f"📋 Declaración IVA — {nombre_periodo(periodo, tipo_periodo_str)}",
            mensaje   = f"Bienvenido a producción. Tienes hasta el {vencimiento.strftime('%d de %B')} para declarar el IVA.",
            referencia = "/reportes",
        )
        await db.commit()
        print(f"[Declaraciones] ✅ Declaración {tipo_periodo_str} creada para emisor {emisor_id}")
    except Exception as e:
        print(f"[Declaraciones] ⚠️ Error: {e}")

# =============================================================================
# LIMPIEZA SANDBOX
# =============================================================================
async def limpiar_sandbox(db):
    """Elimina documentos de prueba con más de 30 días. Corre el día 1."""
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
        rucs = res.fetchall()
        for row in rucs:
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
async def iniciar_worker_declaraciones():
    print("[Declaraciones] 🚀 Worker iniciado.")
    ultima_ejecucion_mes: date | None = None
    ultima_ejecucion_dia: date | None = None

    while True:
        try:
            ahora = datetime.now(TZ_EC)
            hoy   = ahora.date()
            hora  = ahora.hour

            if hora == 8:
                async with AsyncSessionLocal() as db:
                    # Día 1 — crear declaraciones + limpiar sandbox
                    if hoy.day == 1 and ultima_ejecucion_mes != hoy:
                        await crear_declaraciones_mes(db, hoy)
                        await limpiar_sandbox(db)
                        ultima_ejecucion_mes = hoy

                    # Todos los días — recordatorios y alertas
                    if ultima_ejecucion_dia != hoy:
                        await recordatorio_vencimiento_proximo(db, hoy)
                        await alerta_vencimiento_hoy(db, hoy)
                        ultima_ejecucion_dia = hoy

        except Exception as e:
            print(f"[Declaraciones] ❌ Error en loop: {e}")
            import traceback; traceback.print_exc()

        await asyncio.sleep(3600)