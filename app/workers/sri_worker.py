# app/workers/sri_worker.py
#
# Worker de emisión y autorización de comprobantes electrónicos.
#
#   kipu:queue:emision      → recepción del SRI
#   kipu:queue:autorizacion → autorización del SRI
#   kipu:queue:diferida     → reintentos programados (ZSET), sin bloquear al worker
#
# Reglas (Ficha técnica SRI, secciones 7 y 8):
#   1. El SRI es la fuente de verdad. Ante cualquier duda se consulta la autorización
#      por clave de acceso ANTES de reenviar.
#   2. Una falla técnica nunca se convierte en DEVUELTA. Tras varios intentos el
#      documento pasa a EN_REVISION (no es un rechazo) y la conciliación lo sigue.
#   3. Recepción 43 (clave ya registrada) o 45 (secuencial registrado) no son rechazos
#      del contenido: se consulta la autorización.
#   4. Después de RECIBIDA se espera un tiempo parametrizable antes de consultar
#      la autorización, y se insiste hasta 24 horas.
#   5. Las esperas van a la cola diferida: el semáforo solo cubre las llamadas de red.
#
# Escalabilidad:
#   - Múltiples instancias: BRPOP y ZREM son atómicos → safe con N workers.
#   - Conciliación con lock distribuido: solo una instancia la ejecuta a la vez.
#   - LIMIT dinámico: más backlog → más docs por ciclo (100–500).
#   - Semáforo configurable: SRI_MAX_CONCURRENT ajusta sin redeploy.

import asyncio
import time
from datetime import datetime, timezone

from sqlalchemy import text

from app.core.cache import get_redis
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.services import sri_client as sri
from app.services import comprobante_estado_service as svc
from app.services.storage_service import download_file
# Compatibilidad: otros módulos importaban disparar_webhooks desde aquí
from app.services.comprobante_estado_service import disparar_webhooks  # noqa: F401

QUEUE_EMISION      = svc.QUEUE_EMISION
QUEUE_AUTORIZACION = svc.QUEUE_AUTORIZACION
QUEUE_DIFERIDA     = svc.QUEUE_DIFERIDA

# ── Configuración (ajustable sin redeploy vía env vars) ──────────────────────
MAX_CONCURRENT          = int(getattr(settings, "SRI_MAX_CONCURRENT", 3))
BRPOP_TIMEOUT           = 5
MAX_INTENTOS_TECNICOS   = int(getattr(settings, "SRI_MAX_INTENTOS_TECNICOS", 8))
ESPERA_AUTORIZACION_SEG = float(getattr(settings, "SRI_ESPERA_AUTORIZACION_SEG", 3))
LIMITE_AUTORIZACION_H   = 24
CONCILIACION_CADA_SEG   = int(getattr(settings, "SRI_CONCILIACION_CADA_SEG", 30 * 60))
CONCILIACION_LOCK_SEG   = int(getattr(settings, "SRI_CONCILIACION_LOCK_SEG", CONCILIACION_CADA_SEG - 60))
CONCILIACION_LIMIT_MIN  = 100
CONCILIACION_LIMIT_MAX  = 500
CONCILIACION_BATCH      = 20   # docs por batch para no saturar el SRI

_sri_semaphore = asyncio.Semaphore(MAX_CONCURRENT)


def _backoff(intento: int) -> float:
    """10 s, 20 s, 40 s, 80 s, 160 s, 300 s…"""
    return min(10 * (2 ** max(intento - 1, 0)), 300)


def _backoff_autorizacion(intento: int) -> float:
    """5 s, 10 s, 20 s, 30 s, 60 s, 120 s, 300 s…"""
    pasos = [5, 10, 20, 30, 60, 120]
    return pasos[intento] if intento < len(pasos) else 300


async def _con_sri(coro):
    async with _sri_semaphore:
        return await coro


async def _fallo_tecnico(db, doc, resp: sri.RespuestaSRI, cola: str) -> None:
    detalle  = resp.resumen_tecnico()
    intentos = await svc.registrar_error_tecnico(db, doc.id, detalle)
    print(f"[SRI] ⚠️ Falla técnica ({doc.clave_acceso}) intento {intentos}: {detalle}")
    if intentos >= MAX_INTENTOS_TECNICOS:
        await svc.marcar_en_revision(db, doc, detalle)
        return
    await svc.programar(cola, doc.id, _backoff(intentos))


# =============================================================================
# EMISIÓN (recepción)
# =============================================================================
async def procesar_emision(doc_id: str):
    async with AsyncSessionLocal() as db:
        try:
            doc = await svc.cargar_documento(db, doc_id)
            if not doc or doc.estado_sri != "FIRMADO":
                return
            ambiente = svc.ambiente_efectivo(doc)

            # 1) Si ya hubo un intento, el SRI pudo haberlo recibido: se pregunta primero
            if (doc.retry_count or 0) > 0:
                aut = await _con_sri(sri.consultar_autorizacion(doc.clave_acceso, ambiente))
                if await svc.aplicar_respuesta_autorizacion(db, doc, aut):
                    return
                # NO_ENCONTRADO → es seguro enviar · TECNICO → se intenta enviar igual

            # 2) Envío
            xml_bytes = download_file(doc.xml_path)
            rec = await _con_sri(sri.enviar_comprobante(xml_bytes, ambiente))

            if rec.estado == sri.RECIBIDA:
                await svc.marcar_recibida(db, doc)
                await svc.programar(QUEUE_AUTORIZACION, doc.id, ESPERA_AUTORIZACION_SEG)
                return

            if rec.estado == sri.DEVUELTA:
                ids = rec.ids
                if sri.COD_EN_PROCESAMIENTO in ids:
                    print(f"[SRI] ⏳ 70 en procesamiento — reintento en 20 s: {doc.clave_acceso}")
                    await svc.programar(QUEUE_EMISION, doc.id, 20)
                    return

                if ids & {sri.COD_CLAVE_REGISTRADA, sri.COD_SECUENCIAL_REG}:
                    # "Ya lo tengo": se le pregunta al SRI cómo está
                    aut = await _con_sri(sri.consultar_autorizacion(doc.clave_acceso, ambiente))
                    if await svc.aplicar_respuesta_autorizacion(db, doc, aut):
                        return
                    if aut.estado == sri.TECNICO:
                        await _fallo_tecnico(db, doc, aut, QUEUE_EMISION)
                        return
                    if sri.COD_CLAVE_REGISTRADA in ids:
                        # El SRI tiene la clave pero aún no la autoriza: esperar
                        await svc.marcar_recibida(db, doc)
                        await svc.programar(QUEUE_AUTORIZACION, doc.id, 10)
                        return
                    # 45 y el SRI no tiene esta clave: el secuencial es de OTRO comprobante

                await svc.finalizar_devuelta(db, doc.id, rec)
                return

            # 3) Falla técnica: nunca es DEVUELTA
            await _fallo_tecnico(db, doc, rec, QUEUE_EMISION)

        except Exception as err:
            await db.rollback()
            print(f"[Emisión] ❌ Error inesperado ({doc_id}): {err}")
            try:
                async with AsyncSessionLocal() as db2:
                    intentos = await svc.registrar_error_tecnico(db2, doc_id, f"Error interno: {err}")
                await svc.programar(QUEUE_EMISION, doc_id, _backoff(intentos))
            except Exception as e2:
                print(f"[Emisión] ❌ No se pudo reprogramar {doc_id}: {e2}")


# =============================================================================
# AUTORIZACIÓN
# =============================================================================
async def procesar_autorizacion(doc_id: str):
    async with AsyncSessionLocal() as db:
        try:
            doc = await svc.cargar_documento(db, doc_id)
            if not doc or doc.estado_sri != "RECIBIDA":
                return

            aut = await _con_sri(sri.consultar_autorizacion(doc.clave_acceso, svc.ambiente_efectivo(doc)))
            if aut.estado in (sri.AUTORIZADO, sri.NO_AUTORIZADO):
                await svc.aplicar_respuesta_autorizacion(db, doc, aut)
                return

            # Todavía no hay respuesta (o falla técnica): se insiste hasta 24 h
            enviado = doc.fecha_envio_sri or datetime.now(timezone.utc)
            horas   = (datetime.now(timezone.utc) - enviado).total_seconds() / 3600
            if horas >= LIMITE_AUTORIZACION_H:
                await svc.marcar_en_revision(db, doc, f"El SRI no entregó la autorización en {LIMITE_AUTORIZACION_H} horas "
                                                      f"(última respuesta: {aut.estado}).")
                return

            detalle  = aut.resumen_tecnico() if aut.estado == sri.TECNICO else f"Autorización: {aut.estado}"
            intentos = await svc.registrar_error_tecnico(db, doc.id, detalle)
            await svc.programar(QUEUE_AUTORIZACION, doc.id, _backoff_autorizacion(intentos))

        except Exception as err:
            await db.rollback()
            print(f"[Auth] ❌ Error inesperado ({doc_id}): {err}")
            try:
                await svc.programar(QUEUE_AUTORIZACION, doc_id, 60)
            except Exception as e2:
                print(f"[Auth] ❌ No se pudo reprogramar {doc_id}: {e2}")


# =============================================================================
# CONCILIACIÓN: corrige estados preguntándole al SRI
# =============================================================================
_CONCILIACION_WHERE = """
    (estado_sri IN ('FIRMADO', 'RECIBIDA')
     AND updated_at < NOW() - INTERVAL '15 minutes'
     AND created_at > NOW() - INTERVAL '30 days')
    OR estado_sri = 'EN_REVISION'
    OR (estado_sri = 'DEVUELTA'
        AND updated_at > NOW() - INTERVAL '72 hours'
        AND (mensajes_sri::text LIKE '%%"identificador": "43"%%'
             OR mensajes_sri::text LIKE '%%"identificador": "45"%%'
             OR ultimo_error_tecnico IS NOT NULL))
"""


async def _contar_backlog(db) -> int:
    """Cuenta cuántos documentos necesitan conciliación."""
    res = await db.execute(text(f"SELECT COUNT(*) FROM documentos_emitidos WHERE {_CONCILIACION_WHERE}"))
    return res.scalar() or 0


def _calcular_limit(backlog: int) -> int:
    """Más backlog → más docs por ciclo, entre LIMIT_MIN y LIMIT_MAX."""
    if backlog <= CONCILIACION_LIMIT_MIN:
        return CONCILIACION_LIMIT_MIN
    return min(backlog, CONCILIACION_LIMIT_MAX)


async def _adquirir_lock_conciliacion() -> bool:
    """Lock distribuido con Redis SET NX EX. Solo una instancia concilia a la vez."""
    try:
        redis = await get_redis()
        return await redis.set("kipu:lock:conciliacion", "1", nx=True, ex=CONCILIACION_LOCK_SEG)
    except Exception as e:
        print(f"[Conciliación] ⚠️ No se pudo adquirir lock: {e}")
        return False


async def _liberar_lock_conciliacion() -> None:
    try:
        redis = await get_redis()
        await redis.delete("kipu:lock:conciliacion")
    except Exception:
        pass  # expira solo con el TTL


async def conciliar() -> dict:
    """
    Revisa en el SRI:
      - FIRMADO / RECIBIDA atascados más de 15 minutos
      - EN_REVISION
      - DEVUELTA de las últimas 72 h por clave ya registrada (43/45) o con falla técnica previa

    Mejoras de escalabilidad:
      - Lock distribuido: solo una instancia ejecuta la conciliación a la vez.
      - LIMIT dinámico: se ajusta al tamaño del backlog (100–500).
      - Procesamiento en batches de CONCILIACION_BATCH para no saturar el SRI.
    """
    if not await _adquirir_lock_conciliacion():
        return {"revisados": 0, "corregidos": 0, "msg": "otra instancia conciliando"}

    try:
        # 1) Contar backlog y decidir cuántos procesar
        async with AsyncSessionLocal() as db:
            backlog = await _contar_backlog(db)

        if backlog == 0:
            return {"revisados": 0, "corregidos": 0}

        limit = _calcular_limit(backlog)

        # 2) Cargar los IDs a procesar
        async with AsyncSessionLocal() as db:
            res = await db.execute(text(f"""
                SELECT id, estado_sri, emisor_id FROM documentos_emitidos
                WHERE {_CONCILIACION_WHERE}
                ORDER BY updated_at ASC
                LIMIT :limit
            """), {"limit": limit})
            pendientes = res.fetchall()

        if not pendientes:
            return {"revisados": 0, "corregidos": 0}

        # 3) Procesar en batches para no saturar el SRI
        corregidos = 0
        total      = len(pendientes)

        for i in range(0, total, CONCILIACION_BATCH):
            batch = pendientes[i : i + CONCILIACION_BATCH]
            tareas = [_conciliar_uno(fila) for fila in batch]
            resultados = await asyncio.gather(*tareas, return_exceptions=True)
            corregidos += sum(1 for r in resultados if r is True)

            # Pequeña pausa entre batches para no ahogar el SRI
            if i + CONCILIACION_BATCH < total:
                await asyncio.sleep(1)

        print(f"[Conciliación] 🔄 {total} revisados (backlog: {backlog}) · {corregidos} corregidos")
        return {"revisados": total, "corregidos": corregidos, "backlog": backlog}

    finally:
        await _liberar_lock_conciliacion()


async def _conciliar_uno(fila) -> bool:
    """Concilia un solo documento. Devuelve True si hubo cambio."""
    async with AsyncSessionLocal() as db:
        try:
            r = await _con_sri(svc.sincronizar_documento(db, fila.id))
            if r.get("cambio"):
                return True

            # El SRI no lo tiene y está para enviarse: se encola
            if r.get("sri") == sri.NO_ENCONTRADO and fila.estado_sri in ("FIRMADO", "EN_REVISION"):
                await db.execute(text("""
                    UPDATE documentos_emitidos SET estado_sri = 'FIRMADO', updated_at = NOW()
                    WHERE id = :did AND estado_sri IN ('FIRMADO', 'EN_REVISION')
                """), {"did": str(fila.id)})
                await db.commit()
                await svc.invalidar_cache(fila.emisor_id)
                await svc.encolar(QUEUE_EMISION, fila.id)
            elif r.get("sri") == sri.NO_ENCONTRADO and fila.estado_sri == "RECIBIDA":
                await svc.encolar(QUEUE_AUTORIZACION, fila.id)

            return False
        except Exception as e:
            await db.rollback()
            print(f"[Conciliación] ⚠️ {fila.id}: {e}")
            return False


# =============================================================================
# RECOVERY AL ARRANCAR
# =============================================================================
async def recovery_al_arrancar():
    print("[Recovery] 🔍 Buscando comprobantes pendientes en DB...")
    async with AsyncSessionLocal() as db:
        res_e = await db.execute(text("""
            SELECT id FROM documentos_emitidos WHERE estado_sri = 'FIRMADO' ORDER BY created_at ASC
        """))
        res_a = await db.execute(text("""
            SELECT id FROM documentos_emitidos
            WHERE estado_sri = 'RECIBIDA' AND fecha_autorizacion IS NULL
            ORDER BY created_at ASC
        """))
        ids_e = [r.id for r in res_e.fetchall()]
        ids_a = [r.id for r in res_a.fetchall()]

    # Los reintentos ya programados en la cola diferida se respetan;
    # solo se encola lo que no esté programado.
    redis = await get_redis()
    programados = set(await redis.zrange(QUEUE_DIFERIDA, 0, -1))
    n_e = n_a = 0
    for doc_id in ids_e:
        if f"{QUEUE_EMISION}|{doc_id}" not in programados:
            await redis.lpush(QUEUE_EMISION, str(doc_id)); n_e += 1
    for doc_id in ids_a:
        if f"{QUEUE_AUTORIZACION}|{doc_id}" not in programados:
            await redis.lpush(QUEUE_AUTORIZACION, str(doc_id)); n_a += 1
    print(f"[Recovery] ✅ {n_e} → emisión · {n_a} → autorización (sandbox incluido)")


# =============================================================================
# LOOPS
# =============================================================================
async def _loop_cola(cola: str, procesar, nombre: str):
    print(f"[Worker] 🚀 Loop de {nombre} iniciado (concurrencia SRI: {MAX_CONCURRENT}).")
    redis = await get_redis()
    while True:
        try:
            resultado = await redis.brpop(cola, timeout=BRPOP_TIMEOUT)
            if resultado is None:
                continue
            doc_id = resultado[1]
            doc_id = doc_id.decode() if isinstance(doc_id, bytes) else doc_id
            asyncio.create_task(procesar(doc_id))
        except (asyncio.TimeoutError, TimeoutError):
            continue
        except Exception as e:
            print(f"[Worker {nombre}] ❌ Error en loop: {e}")
            await asyncio.sleep(3)
            try:
                redis = await get_redis()
            except Exception:
                pass


async def loop_emision():
    await _loop_cola(QUEUE_EMISION, procesar_emision, "emisión")


async def loop_autorizacion():
    await _loop_cola(QUEUE_AUTORIZACION, procesar_autorizacion, "autorización")


async def loop_diferida():
    """Mueve a su cola los reintentos cuya hora ya llegó. Seguro con varias instancias."""
    print("[Worker] 🚀 Loop de reintentos diferidos iniciado.")
    while True:
        try:
            redis = await get_redis()
            vencidos = await redis.zrangebyscore(QUEUE_DIFERIDA, 0, time.time(), start=0, num=100)
            for miembro in vencidos:
                miembro = miembro.decode() if isinstance(miembro, bytes) else miembro
                if await redis.zrem(QUEUE_DIFERIDA, miembro):   # solo una instancia lo gana
                    cola, doc_id = miembro.split("|", 1)
                    await redis.lpush(cola, doc_id)
        except Exception as e:
            print(f"[Worker diferida] ❌ {e}")
        await asyncio.sleep(1)


async def loop_conciliacion():
    intervalo = CONCILIACION_CADA_SEG
    print(f"[Worker] 🚀 Conciliación con el SRI iniciada (cada {intervalo // 60} min, lock: {CONCILIACION_LOCK_SEG}s).")
    await asyncio.sleep(60)   # deja que arranque todo primero
    while True:
        try:
            await conciliar()
        except Exception as e:
            print(f"[Conciliación] ❌ {e}")
        await asyncio.sleep(intervalo)


async def iniciar_workers():
    await recovery_al_arrancar()
    await asyncio.gather(
        loop_emision(),
        loop_autorizacion(),
        loop_diferida(),
        loop_conciliacion(),
    )