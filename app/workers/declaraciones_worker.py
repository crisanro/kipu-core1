# app/workers/declaraciones_worker.py

import asyncio
from datetime import datetime, date, timedelta
from calendar import monthrange
import pytz

from sqlalchemy import text
from app.core.database import AsyncSessionLocal
from app.services.notification_service import crear_notificacion

TZ_EC = pytz.timezone("America/Guayaquil")

# ── Calcular fecha de vencimiento según 9° dígito del RUC ─────────────────────
def calcular_vencimiento(ruc: str, periodo: date) -> date:
    """
    Retorna la fecha límite de declaración según el 9° dígito del RUC.
    El vencimiento es en el mes SIGUIENTE al período declarado.
    """
    TABLA_VENCIMIENTO = {
        "1": 10, "2": 12, "3": 14, "4": 16, "5": 18,
        "6": 20, "7": 22, "8": 24, "9": 26, "0": 28,
    }
    noveno_digito = ruc[8] if len(ruc) >= 9 else "1"
    dia_limite    = TABLA_VENCIMIENTO.get(noveno_digito, 28)

    # El vencimiento es el mes siguiente al período
    if periodo.month == 12:
        mes_sig = date(periodo.year + 1, 1, dia_limite)
    else:
        # Validar que el día exista en el mes
        ultimo_dia = monthrange(periodo.year, periodo.month + 1)[1]
        dia_real   = min(dia_limite, ultimo_dia)
        mes_sig    = date(periodo.year, periodo.month + 1, dia_real)

    return mes_sig


# ── Crear registros del nuevo mes ─────────────────────────────────────────────
async def crear_declaraciones_mes(db, periodo: date):
    """
    Crea registros de declaración para todos los emisores en producción.
    """
    print(f"[Declaraciones] 📋 Creando declaraciones para {periodo.strftime('%B %Y')}...")

    res = await db.execute(text("""
        SELECT id, ruc FROM emisores
        WHERE ambiente = 2
    """))
    emisores = res.fetchall()

    creados = 0
    for emisor in emisores:
        try:
            # Crear declaración IVA (104)
            await db.execute(text("""
                INSERT INTO declaraciones_sri (emisor_id, tipo, periodo, declarado)
                VALUES (:eid, '104', :periodo, false)
                ON CONFLICT (emisor_id, tipo, periodo) DO NOTHING
            """), {"eid": emisor.id, "periodo": periodo})

            # Calcular fecha de vencimiento
            vencimiento = calcular_vencimiento(emisor.ruc, periodo)

            # Notificar
            await crear_notificacion(
                db         = db,
                emisor_id  = emisor.id,
                tipo       = "DECLARACION",
                titulo     = f"📋 Declaración IVA — {periodo.strftime('%B %Y')}",
                mensaje    = f"Tienes hasta el {vencimiento.strftime('%d de %B')} para declarar el IVA del mes anterior.",
                referencia = "/dashboard",
            )
            creados += 1

        except Exception as e:
            print(f"[Declaraciones] ⚠️ Error creando para emisor {emisor.id}: {e}")

    await db.commit()
    print(f"[Declaraciones] ✅ {creados}/{len(emisores)} declaraciones creadas")


# ── Recordatorio 3 días antes ─────────────────────────────────────────────────
async def recordatorio_vencimiento_proximo(db, hoy: date):
    res = await db.execute(text("""
        SELECT d.emisor_id, d.periodo, e.ruc
        FROM declaraciones_sri d
        JOIN emisores e ON e.id = d.emisor_id
        WHERE d.declarado = false
          AND d.tipo = '104'
          AND e.ambiente = 2
    """))
    pendientes = res.fetchall()

    recordados = 0
    for p in pendientes:
        vencimiento = calcular_vencimiento(p.ruc, p.periodo)
        dias_restantes = (vencimiento - hoy).days

        if dias_restantes == 3:
            await crear_notificacion(
                db         = db,
                emisor_id  = p.emisor_id,
                tipo       = "DECLARACION",
                titulo     = "⚠️ Tu declaración vence en 3 días",
                mensaje    = f"La declaración de IVA de {p.periodo.strftime('%B')} vence el {vencimiento.strftime('%d de %B')}. No olvides declararla.",
                referencia = "/dashboard",
            )
            recordados += 1
    
    if recordados > 0:
        await db.commit()
        print(f"[Declaraciones] ⚠️ {recordados} recordatorios enviados")


# ── Alerta día del vencimiento ────────────────────────────────────────────────
async def alerta_vencimiento_hoy(db, hoy: date):
    res = await db.execute(text("""
        SELECT d.emisor_id, d.periodo, e.ruc
        FROM declaraciones_sri d
        JOIN emisores e ON e.id = d.emisor_id
        WHERE d.declarado = false
          AND d.tipo = '104'
          AND e.ambiente = 2
    """))
    pendientes = res.fetchall()

    alertados = 0
    for p in pendientes:
        vencimiento = calcular_vencimiento(p.ruc, p.periodo)
        if vencimiento == hoy:
            await crear_notificacion(
                db         = db,
                emisor_id  = p.emisor_id,
                tipo       = "DECLARACION",
                titulo     = "❌ Tu declaración vence HOY",
                mensaje    = f"La declaración de IVA de {p.periodo.strftime('%B')} vence hoy. Declara ahora en el SRI en Línea.",
                referencia = "/dashboard",
            )
            alertados += 1
    
    if alertados > 0:
        await db.commit()
        print(f"[Declaraciones] ❌ {alertados} alertas de vencimiento HOY enviadas")


# ── Loop principal ────────────────────────────────────────────────────────────
async def iniciar_worker_declaraciones():
    print("[Declaraciones] 🚀 Worker de declaraciones iniciado.")

    ultima_ejecucion_mes: date | None = None
    ultima_ejecucion_dia: date | None = None

    while True:
        try:
            ahora = datetime.now(TZ_EC)
            hoy   = ahora.date()
            hora  = ahora.hour

            if hora == 8:
                async with AsyncSessionLocal() as db:
                    # ── 1° del mes — crear declaraciones ──────────────────────
                    if hoy.day == 1 and ultima_ejecucion_mes != hoy:
                        if hoy.month == 1:
                            periodo = date(hoy.year - 1, 12, 1)
                        else:
                            periodo = date(hoy.year, hoy.month - 1, 1)
                        
                        await crear_declaraciones_mes(db, periodo)
                        ultima_ejecucion_mes = hoy

                    # ── Todos los días — recordatorios y alertas ───────────────
                    if ultima_ejecucion_dia != hoy:
                        await recordatorio_vencimiento_proximo(db, hoy)
                        await alerta_vencimiento_hoy(db, hoy)
                        ultima_ejecucion_dia = hoy

        except Exception as e:
            print(f"[Declaraciones] ❌ Error en loop: {e}")
            import traceback; traceback.print_exc()

        await asyncio.sleep(3600)

# ── Helper individual ────────────────────────────────────────────────────────
async def crear_declaracion_emisor(db, emisor_id: int, ruc: str):
    """
    Crea la declaración del mes actual para un emisor específico.
    """
    hoy     = date.today()
    periodo = date(hoy.year, hoy.month, 1)

    try:
        await db.execute(text("""
            INSERT INTO declaraciones_sri (emisor_id, tipo, periodo, declarado)
            VALUES (:eid, '104', :periodo, false)
            ON CONFLICT (emisor_id, tipo, periodo) DO NOTHING
        """), {"eid": emisor_id, "periodo": periodo})

        vencimiento = calcular_vencimiento(ruc, periodo)

        await crear_notificacion(
            db         = db,
            emisor_id  = emisor_id,
            tipo       = "DECLARACION",
            titulo     = f"📋 Declaración IVA — {periodo.strftime('%B %Y')}",
            mensaje    = f"Bienvenido a producción. Tienes hasta el {vencimiento.strftime('%d de %B')} para declarar el IVA de este mes.",
            referencia = "/dashboard",
        )
        await db.commit()
        print(f"[Declaraciones] ✅ Declaración creada para emisor {emisor_id}")

    except Exception as e:
        print(f"[Declaraciones] ⚠️ Error: {e}")