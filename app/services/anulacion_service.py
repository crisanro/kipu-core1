# app/services/anulacion_service.py
#
# Reglas de anulación de comprobantes electrónicos (Res. NAC-DGERCGC25-00000017).
#
# - Plazo: hasta el día 7 del mes siguiente a la emisión. Si cae en fin de
#   semana se corre al lunes.
# - FAC / LIQ: se anulan sin aceptación del receptor.
# - RET / NCR / NDB: requieren aceptación del receptor en 5 días hábiles.
#   Sin respuesta → la solicitud queda sin efecto y el comprobante sigue vigente.
#   Excepción: receptor con pasaporte o identificación del exterior → directo.
# - FAC a consumidor final: no se anula ni admite nota de crédito (desde 2026).
# - Vencido el plazo: FAC solo con nota de crédito (máx. 12 meses).
#
# Integración con el SOAP del SRI:
# - Verifica mediante `consultar_estado` antes de marcar un comprobante como ANULADO o PENDIENTE.
#
# Columnas en documentos_emitidos:
#   anulacion_estado        NULL | PENDIENTE | ACEPTADA | RECHAZADA | VENCIDA
#   anulacion_solicitada_at timestamptz
#   anulacion_limite_aceptacion date (último día hábil para que el receptor acepte)
#   sri_verificado_at       timestamptz

import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from app.services import sri_client as sri

logger = logging.getLogger(__name__)

TZ_EC = ZoneInfo("America/Guayaquil")

MOTIVOS_ANULACION = [
    "ERROR EN EL COMPROBANTE",
    "OPERACIÓN NO REALIZADA",
]

REQUIEREN_ACEPTACION = {"RET", "NCR", "NDB"}
TIPOS_ID_EXTERIOR    = {"06", "08"}   # 06 = pasaporte, 08 = identificación del exterior
DIAS_HABILES_ACEPTACION = 5

TIPO_COMPROBANTE_SRI = {
    "FAC": "Factura",
    "LIQ": "Liquidación de compra de bienes y prestación de servicios",
    "NCR": "Nota de crédito",
    "NDB": "Nota de débito",
    "RET": "Comprobante de retención",
}

# (bloque JSONB, tipo id, identificación, razón social)
_CAMPOS_RECEPTOR = {
    "FAC": ("infoFactura",           "tipoIdentificacionComprador",      "identificacionComprador",      "razonSocialComprador"),
    "LIQ": ("infoLiquidacionCompra", "tipoIdentificacionProveedor",      "identificacionProveedor",      "razonSocialProveedor"),
    "NCR": ("infoNotaCredito",       "tipoIdentificacionComprador",      "identificacionComprador",      "razonSocialComprador"),
    "NDB": ("infoNotaDebito",        "tipoIdentificacionComprador",      "identificacionComprador",      "razonSocialComprador"),
    "RET": ("infoCompRetencion",     "tipoIdentificacionSujetoRetenido", "identificacionSujetoRetenido", "razonSocialSujetoRetenido"),
}

_NOMBRES_CAMPO_EMAIL = {"email", "e-mail", "correo", "correo electronico", "correo electrónico", "mail"}


# =============================================================================
# FECHAS
# =============================================================================
def hoy_ec() -> date:
    return datetime.now(TZ_EC).date()


def fecha_limite_anulacion(fecha_emision: date) -> date:
    """Día 7 del mes siguiente; si cae sábado o domingo, pasa al lunes."""
    if fecha_emision.month == 12:
        limite = date(fecha_emision.year + 1, 1, 7)
    else:
        limite = date(fecha_emision.year, fecha_emision.month + 1, 7)
    if limite.weekday() == 5:
        limite += timedelta(days=2)
    elif limite.weekday() == 6:
        limite += timedelta(days=1)
    return limite


def sumar_dias_habiles(desde: date, dias: int) -> date:
    d, contados = desde, 0
    while contados < dias:
        d += timedelta(days=1)
        if d.weekday() < 5:
            contados += 1
    return d


def fecha_sri(dt) -> str | None:
    """dd/mm/aaaa en hora de Ecuador (formato del portal SRI)."""
    if not dt:
        return None
    if isinstance(dt, datetime):
        if dt.tzinfo:
            dt = dt.astimezone(TZ_EC)
        return dt.strftime("%d/%m/%Y")
    if isinstance(dt, date):
        return dt.strftime("%d/%m/%Y")
    return str(dt)


def iso(dt) -> str | None:
    return dt.isoformat() if dt else None


# =============================================================================
# RECEPTOR
# =============================================================================
def receptor_documento(tipo_doc: str, datos: dict) -> dict:
    datos = datos or {}
    bloque, k_tipo, k_id, k_razon = _CAMPOS_RECEPTOR.get(tipo_doc, _CAMPOS_RECEPTOR["FAC"])
    info = datos.get(bloque) or {}
    return {
        "tipo_id":        info.get(k_tipo) or "",
        "identificacion": info.get(k_id) or datos.get("legacy_id_comprador") or "",
        "razon_social":   info.get(k_razon) or datos.get("legacy_razon_comprador") or "",
    }


def email_receptor(email_comprador: str | None, datos: dict) -> str:
    if email_comprador:
        return email_comprador
    datos = datos or {}
    if datos.get("legacy_email_comprador"):
        return datos["legacy_email_comprador"]
    campos = (datos.get("infoAdicional") or {}).get("campoAdicional") or []
    if isinstance(campos, dict):
        campos = [campos]
    for c in campos:
        if not isinstance(c, dict):
            continue
        nombre = str(c.get("@nombre", "")).strip().lower()
        if nombre in _NOMBRES_CAMPO_EMAIL and c.get("#text"):
            return str(c["#text"]).strip()
    return ""


def es_consumidor_final(tipo_doc: str, receptor: dict) -> bool:
    return tipo_doc == "FAC" and (
        receptor["tipo_id"] == "07" or receptor["identificacion"] == "9999999999999"
    )


# =============================================================================
# EVALUACIÓN
# =============================================================================
def evaluar_anulacion(doc: dict) -> dict:
    """
    doc necesita: tipo_doc, estado_sri, es_sandbox, fecha_emision, fecha_autorizacion,
    clave_acceso, email_comprador, datos, anulacion_estado, anulacion_solicitada_at,
    anulacion_limite_aceptacion, motivo_anulacion
    """
    tipo_doc  = doc["tipo_doc"]
    datos     = doc.get("datos") or {}
    receptor  = receptor_documento(tipo_doc, datos)
    hoy       = hoy_ec()
    limite    = fecha_limite_anulacion(doc["fecha_emision"])
    estado_an = doc.get("anulacion_estado")

    consumidor_final    = es_consumidor_final(tipo_doc, receptor)
    receptor_exterior   = receptor["tipo_id"] in TIPOS_ID_EXTERIOR
    requiere_aceptacion = tipo_doc in REQUIEREN_ACEPTACION and not receptor_exterior
    plazo_vencido       = hoy > limite
    dentro_12_meses     = (hoy - doc["fecha_emision"]).days <= 365

    motivo_bloqueo = None
    if doc.get("es_sandbox"):
        motivo_bloqueo = "Los comprobantes de prueba no se anulan en el SRI."
    elif doc["estado_sri"] != "AUTORIZADO":
        motivo_bloqueo = "Solo se pueden anular comprobantes autorizados."
    elif estado_an == "PENDIENTE":
        motivo_bloqueo = "Ya hay una solicitud de anulación esperando al receptor."
    elif consumidor_final:
        motivo_bloqueo = (
            "Las facturas a consumidor final no se pueden anular ni corregir "
            "con nota de crédito una vez enviadas al SRI."
        )
    elif plazo_vencido:
        if tipo_doc == "FAC" and dentro_12_meses:
            motivo_bloqueo = (
                f"El plazo para anular venció el {fecha_sri(limite)}. "
                "Para dejarla sin efecto, emite una nota de crédito."
            )
        else:
            motivo_bloqueo = (
                f"El plazo para anular venció el {fecha_sri(limite)}. "
                "Este comprobante ya no se puede anular."
            )

    return {
        "puede_anular":         motivo_bloqueo is None,
        "motivo_bloqueo":       motivo_bloqueo,
        "sugerir_nota_credito": (
            tipo_doc == "FAC" and plazo_vencido and not consumidor_final
            and dentro_12_meses and doc["estado_sri"] == "AUTORIZADO"
        ),
        "fecha_limite":         limite.isoformat(),
        "dias_restantes":       (limite - hoy).days,
        "requiere_aceptacion":  requiere_aceptacion,
        "estado":               estado_an,
        "solicitada_at":        iso(doc.get("anulacion_solicitada_at")),
        "limite_aceptacion":    iso(doc.get("anulacion_limite_aceptacion")),
        "motivo":               doc.get("motivo_anulacion"),
        "motivos":              MOTIVOS_ANULACION,
        "sri": {
            "tipo_comprobante":        TIPO_COMPROBANTE_SRI.get(tipo_doc, tipo_doc),
            "fecha_autorizacion":      fecha_sri(doc.get("fecha_autorizacion")),
            "clave_acceso":            doc.get("clave_acceso"),
            "numero_autorizacion":     doc.get("clave_acceso"),  # en electrónicos son iguales
            "identificacion_receptor": receptor["identificacion"],
            "razon_social_receptor":   receptor["razon_social"],
            "email_receptor":          email_receptor(doc.get("email_comprador"), datos),
        },
    }


# =============================================================================
# INTEGRACIÓN CON WEBSERVICE DEL SRI (ConsultaComprobante)
# =============================================================================
async def verificar_sri_y_procesar_anulacion(
    db: AsyncSession,
    doc: dict,
    emisor_id: int,
    motivo: str = "ERROR EN EL COMPROBANTE"
) -> dict:
    """
    Consulta al SRI. Si el SRI responde AUTORIZADO, SIGNIFICA QUE NO HA SIDO ANULADO
    en el portal del SRI todavía (o el SRI aún no actualiza sus registros).
    Por ende, RECHAZA la anulación en Kipu para evitar anulaciones falsas.
    """
    ambiente = 1 if doc.get("es_sandbox") else doc.get("ambiente", 2)
    clave_acceso = doc["clave_acceso"]

    # 1. Consulta al WS del SRI
    res_sri = await sri.consultar_estado(clave_acceso, ambiente)

    if res_sri.estado == sri.TECNICO:
        raise HTTPException(
            status_code=503,
            detail=f"No pudimos verificar el estado con el SRI: {res_sri.detalle}"
        )

    # 2. CASO REAL: El SRI ya lo reporta como ANULADO oficialmente
    if res_sri.estado == sri.ANULADO:
        await db.execute(text("""
            UPDATE documentos_emitidos
            SET estado_sri               = 'ANULADO',
                motivo_anulacion        = :motivo,
                fecha_anulacion         = NOW(),
                anulacion_estado        = 'ACEPTADA',
                sri_verificado_at       = NOW(),
                estado_cobro            = CASE
                                            WHEN tipo_doc IN ('FAC', 'LIQ', 'NDB') THEN 'ANULADO'
                                            ELSE estado_cobro
                                          END,
                updated_at              = NOW()
            WHERE id = :did AND emisor_id = :eid
        """), {"motivo": motivo, "did": str(doc["id"]), "eid": emisor_id})

        efectos = await aplicar_efectos_anulacion(db, str(doc["id"]), emisor_id)

        return {
            "ok": True,
            "estado": "ANULADO",
            "sri_estado": "ANULADO",
            "cambio": True,
            "mensaje": "Comprobante verificado y confirmado como ANULADO en el SRI.",
            "efectos": efectos,
        }

    # 3. CASO PENDIENTE EN EL SRI (Retenciones / Notas de Crédito que esperan al receptor)
    if res_sri.estado == sri.PENDIENTE_ANULAR:
        limite_aceptacion = sumar_dias_habiles(hoy_ec(), DIAS_HABILES_ACEPTACION)
        await db.execute(text("""
            UPDATE documentos_emitidos
            SET anulacion_estado        = 'PENDIENTE',
                anulacion_solicitada_at = NOW(),
                anulacion_limite_aceptacion = :limite,
                motivo_anulacion        = :motivo,
                sri_verificado_at       = NOW(),
                updated_at              = NOW()
            WHERE id = :did AND emisor_id = :eid
        """), {"limite": limite_aceptacion, "motivo": motivo, "did": str(doc["id"]), "eid": emisor_id})

        return {
            "ok": True,
            "estado": "PENDIENTE",
            "sri_estado": "PENDIENTE_ANULAR",
            "cambio": True,
            "mensaje": f"La anulación está registrada en el SRI en espera de aceptación del receptor.",
            "efectos": {"cuentas_anuladas": 0, "cuentas_con_abonos": 0},
        }

    # 4. PROTECCIÓN ESTRICTA: Si sigue AUTORIZADO en el SRI, BLOQUEAR la anulación
    if res_sri.estado == sri.AUTORIZADO:
        raise HTTPException(
            status_code=422,
            detail=(
                "El SRI reporta que este comprobante aún está AUTORIZADO y vigente en su portal. "
                "Debes ingresar primero a SRI en línea y procesar la anulación. "
                "Una vez procesada allá, vuelve a intentar la verificación aquí."
            )
        )

    raise HTTPException(
        status_code=400,
        detail=f"Estado del comprobante en el SRI no permite la anulación: {res_sri.estado}"
    )

# =============================================================================
# EFECTOS DE UNA ANULACIÓN CONFIRMADA
# =============================================================================
async def aplicar_efectos_anulacion(db: AsyncSession, doc_id: str, emisor_id: int) -> dict:
    """
    Se llama cuando el documento pasa a ANULADO (directo o por aceptación).
    No hace commit: corre dentro de la misma transacción del endpoint.

    - Cuentas por cobrar/pagar vinculadas → ANULADO. Los abonos se conservan
      como historial (no se borran), para que quede rastro de lo cobrado.
    """
    res = await db.execute(text("""
        UPDATE cuentas_movimientos
        SET estado     = 'ANULADO',
            notas      = CONCAT_WS(E'\\n', NULLIF(notas, ''), 'Anulada por anulación del comprobante.'),
            updated_at = NOW()
        WHERE documento_emitido_id = :did
          AND emisor_id            = :eid
          AND estado              <> 'ANULADO'
        RETURNING id, monto_pagado
    """), {"did": doc_id, "eid": emisor_id})
    cuentas = res.fetchall()

    return {
        "cuentas_anuladas":   len(cuentas),
        "cuentas_con_abonos": sum(1 for c in cuentas if float(c.monto_pagado or 0) > 0),
    }


# =============================================================================
# VENCIMIENTO DE SOLICITUDES
# =============================================================================
async def vencer_si_corresponde(db: AsyncSession, doc: dict) -> dict:
    """
    Vencimiento perezoso: si la solicitud pasó su límite, se marca VENCIDA al leerla.
    Devuelve el doc actualizado en memoria.
    """
    limite = doc.get("anulacion_limite_aceptacion")
    if doc.get("anulacion_estado") == "PENDIENTE" and limite and hoy_ec() > limite:
        await db.execute(text("""
            UPDATE documentos_emitidos
            SET anulacion_estado = 'VENCIDA', updated_at = NOW()
            WHERE id = :did AND anulacion_estado = 'PENDIENTE'
        """), {"did": str(doc["id"])})
        await db.commit()
        doc = {**doc, "anulacion_estado": "VENCIDA"}
    return doc


async def vencer_anulaciones_pendientes(db: AsyncSession) -> int:
    """
    Versión en lote para un cron diario (opcional). Devuelve cuántas venció.
    """
    res = await db.execute(text("""
        UPDATE documentos_emitidos
        SET anulacion_estado = 'VENCIDA', updated_at = NOW()
        WHERE anulacion_estado = 'PENDIENTE'
          AND anulacion_limite_aceptacion < (NOW() AT TIME ZONE 'America/Guayaquil')::date
        RETURNING id
    """))
    vencidas = len(res.fetchall())
    await db.commit()
    return vencidas