# app/workers/declaraciones_worker.py
#
# Worker de declaraciones tributarias.
# Corre cada hora, ejecuta acciones según el día y hora.
#
# Acciones:
#   Día 1 del mes — crear declaraciones del mes anterior + precalcular totales
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

TIPOS_DECLARACION = ["104"]  # ATS y 102 se agregan en fases futuras


# =============================================================================
# CALCULAR VENCIMIENTO
# =============================================================================

def calcular_vencimiento(ruc: str, periodo: date) -> date:
    """
    Fecha límite según el 9° dígito del RUC.
    El vencimiento es en el mes SIGUIENTE al período declarado.
    """
    TABLA = {
        "1": 10, "2": 12, "3": 14, "4": 16, "5": 18,
        "6": 20, "7": 22, "8": 24, "9": 26, "0": 28,
    }
    noveno   = ruc[8] if len(ruc) >= 9 else "1"
    dia_lim  = TABLA.get(noveno, 28)

    if periodo.month == 12:
        anio_sig = periodo.year + 1
        mes_sig  = 1
    else:
        anio_sig = periodo.year
        mes_sig  = periodo.month + 1

    ultimo_dia = monthrange(anio_sig, mes_sig)[1]
    dia_real   = min(dia_lim, ultimo_dia)

    return date(anio_sig, mes_sig, dia_real)


# =============================================================================
# PRECALCULAR TOTALES DEL PERÍODO
# =============================================================================

async def precalcular_totales(db, emisor_id: int, periodo: date) -> dict:
    """
    Calcula los totales fiscales del período desde documentos_emitidos
    y documentos_recibidos. Se guarda en declaraciones_sri.totales JSONB.
    """
    if periodo.month == 12:
        fi = periodo
        ff = date(periodo.year + 1, 1, 1)
    else:
        fi = periodo
        ff = date(periodo.year, periodo.month + 1, 1)

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
        WHERE emisor_id = :eid
          AND tipo_doc IN ('FAC', 'LIQ')
          AND estado_sri = 'AUTORIZADO'
          AND fecha_emision >= :fi
          AND fecha_emision < :ff
    """), {"eid": emisor_id, "fi": fi, "ff": ff})
    ventas = res_ventas.fetchone()

    # Compras
    res_compras = await db.execute(text("""
        SELECT
            COALESCE(SUM(importe_total), 0) AS total_compras,
            COALESCE(SUM(
                CASE WHEN deducible_renta THEN importe_total ELSE 0 END
            ), 0) AS total_deducible,
            COALESCE(SUM(
                CASE WHEN credito_tributario_iva THEN
                    COALESCE((impuestos_detalle->0->>'valor')::numeric, 0)
                ELSE 0 END
            ), 0) AS credito_tributario
        FROM documentos_recibidos
        WHERE emisor_id = :eid
          AND tipo_doc IN ('FAC', 'LIQ')
          AND fecha_emision >= :fi
          AND fecha_emision < :ff
    """), {"eid": emisor_id, "fi": fi, "ff": ff})
    compras = res_compras.fetchone()

    # Retenciones recibidas
    res_ret = await db.execute(text("""
        SELECT COALESCE(SUM(
            COALESCE((impuestos_detalle->0->>'valor')::numeric, 0)
        ), 0) AS total_retenciones
        FROM documentos_recibidos
        WHERE emisor_id = :eid
          AND tipo_doc = 'RET'
          AND fecha_emision >= :fi
          AND fecha_emision < :ff
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
# CREAR DECLARACIONES DEL MES
# =============================================================================

async def crear_declaraciones_mes(db, periodo: date):
    """
    Crea registros de declaración para todos los emisores en producción
    y precalcula los totales del período cerrado.
    """
    print(f"[Declaraciones] 📋 Creando declaraciones para {periodo.strftime('%B %Y')}...")

    res = await db.execute(text("""
        SELECT id, ruc FROM emisores WHERE ambiente = 2
    """))
    emisores = res.fetchall()

    creados = 0
    for emisor in emisores:
        try:
            for tipo in TIPOS_DECLARACION:
                vencimiento = calcular_vencimiento(emisor.ruc, periodo)

                await db.execute(text("""
                    INSERT INTO declaraciones_sri
                        (emisor_id, tipo, periodo, vencimiento, declarado)
                    VALUES (:eid, :tipo, :periodo, :vencimiento, false)
                    ON CONFLICT (emisor_id, tipo, periodo) DO NOTHING
                """), {
                    "eid":        emisor.id,
                    "tipo":       tipo,
                    "periodo":    periodo,
                    "vencimiento": vencimiento,
                })

                # Precalcular totales del período cerrado
                totales = await precalcular_totales(db, emisor.id, periodo)

                await db.execute(text("""
                    UPDATE declaraciones_sri
                    SET totales = CAST(:totales AS jsonb)
                    WHERE emisor_id = :eid
                      AND tipo = :tipo
                      AND periodo = :periodo
                """), {
                    "totales": json.dumps(totales),
                    "eid":     emisor.id,
                    "tipo":    tipo,
                    "periodo": periodo,
                })

            await crear_notificacion(
                db        = db,
                emisor_id = emisor.id,
                tipo      = "DECLARACION",
                titulo    = f"📋 Declaración IVA — {periodo.strftime('%B %Y')}",
                mensaje   = f"Tienes hasta el {vencimiento.strftime('%d de %B')} para declarar el IVA. Ya calculamos los totales por ti.",
                referencia = "/declaraciones",
            )
            creados += 1

        except Exception as e:
            print(f"[Declaraciones] ⚠️ Error en emisor {emisor.id}: {e}")

    await db.commit()
    print(f"[Declaraciones] ✅ {creados}/{len(emisores)} declaraciones creadas")


# =============================================================================
# RECORDATORIOS
# =============================================================================

async def recordatorio_vencimiento_proximo(db, hoy: date):
    """Notifica 3 días antes del vencimiento."""
    res = await db.execute(text("""
        SELECT d.emisor_id, d.periodo, d.vencimiento, d.tipo
        FROM declaraciones_sri d
        JOIN emisores e ON e.id = d.emisor_id
        WHERE d.declarado = false
          AND e.ambiente = 2
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
            mensaje   = f"La declaración de {p.periodo.strftime('%B')} vence el {p.vencimiento.strftime('%d de %B')}. No olvides declararla en el SRI en Línea.",
            referencia = "/declaraciones",
        )

    await db.commit()
    print(f"[Declaraciones] ⚠️ {len(pendientes)} recordatorios enviados")


async def alerta_vencimiento_hoy(db, hoy: date):
    """Alerta el mismo día del vencimiento."""
    res = await db.execute(text("""
        SELECT d.emisor_id, d.periodo, d.tipo
        FROM declaraciones_sri d
        JOIN emisores e ON e.id = d.emisor_id
        WHERE d.declarado = false
          AND e.ambiente = 2
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
            mensaje   = f"La declaración de {p.periodo.strftime('%B')} vence hoy. Declara ahora en el SRI en Línea antes de que sea tarde.",
            referencia = "/declaraciones",
        )

    await db.commit()
    print(f"[Declaraciones] ❌ {len(pendientes)} alertas de vencimiento HOY enviadas")


# =============================================================================
# HELPER PARA NUEVOS EMISORES
# =============================================================================

async def crear_declaracion_emisor(db, emisor_id: int, ruc: str):
    """
    Crea la declaración del mes actual para un emisor nuevo
    que acaba de pasar a producción.
    """
    hoy     = date.today()
    if hoy.month == 1:
        periodo = date(hoy.year - 1, 12, 1)
    else:
        periodo = date(hoy.year, hoy.month - 1, 1)

    try:
        for tipo in TIPOS_DECLARACION:
            vencimiento = calcular_vencimiento(ruc, periodo)

            await db.execute(text("""
                INSERT INTO declaraciones_sri
                    (emisor_id, tipo, periodo, vencimiento, declarado)
                VALUES (:eid, :tipo, :periodo, :vencimiento, false)
                ON CONFLICT (emisor_id, tipo, periodo) DO NOTHING
            """), {
                "eid":        emisor_id,
                "tipo":       tipo,
                "periodo":    periodo,
                "vencimiento": vencimiento,
            })

            totales = await precalcular_totales(db, emisor_id, periodo)

            await db.execute(text("""
                UPDATE declaraciones_sri
                SET totales = CAST(:totales AS jsonb)
                WHERE emisor_id = :eid AND tipo = :tipo AND periodo = :periodo
            """), {
                "totales": json.dumps(totales),
                "eid":     emisor_id,
                "tipo":    tipo,
                "periodo": periodo,
            })

        await crear_notificacion(
            db        = db,
            emisor_id = emisor_id,
            tipo      = "DECLARACION",
            titulo    = f"📋 Declaración IVA — {periodo.strftime('%B %Y')}",
            mensaje   = f"Bienvenido a producción. Tienes hasta el {vencimiento.strftime('%d de %B')} para declarar el IVA.",
            referencia = "/declaraciones",
        )

        await db.commit()
        print(f"[Declaraciones] ✅ Declaración creada para emisor {emisor_id}")

    except Exception as e:
        print(f"[Declaraciones] ⚠️ Error: {e}")


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

                    # Día 1 — crear declaraciones del mes anterior
                    if hoy.day == 1 and ultima_ejecucion_mes != hoy:
                        if hoy.month == 1:
                            periodo = date(hoy.year - 1, 12, 1)
                        else:
                            periodo = date(hoy.year, hoy.month - 1, 1)

                        await crear_declaraciones_mes(db, periodo)
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