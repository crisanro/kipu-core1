# app/services/sri_client.py
#
# Cliente único para los web services del SRI (Ficha técnica, secciones 7 y 8):
#
#   Recepción     validarComprobante                        → RECIBIDA | DEVUELTA
#   Autorización  autorizacionComprobante                   → AUTORIZADO | NO AUTORIZADO | EN PROCESO
#   Consulta      consultarEstadoAutorizacionComprobante    → AUTORIZADO | NO AUTORIZADO |
#                                                             PENDIENTE DE ANULAR | ANULADO
#
# Regla de oro: una FALLA TÉCNICA (timeout, HTTP != 200, respuesta ilegible) nunca
# se traduce en un estado del SRI. Se devuelve estado TECNICO con el detalle y los
# primeros caracteres de la respuesta cruda, y quien llama decide qué hacer
# (normalmente: preguntarle al SRI por la clave de acceso antes de reenviar).
#
# Los hosts se pueden cambiar por configuración (la ficha recomienda no quemarlos):
#   SRI_HOST_PRUEBAS     (por defecto https://celcer.sri.gob.ec)
#   SRI_HOST_PRODUCCION  (por defecto https://cel.sri.gob.ec)

from dataclasses import dataclass, field
from xml.parsers.expat import ExpatError

import httpx
import xmltodict

from app.core.config import settings

HOSTS = {
    "1": getattr(settings, "SRI_HOST_PRUEBAS",    None) or "https://celcer.sri.gob.ec",
    "2": getattr(settings, "SRI_HOST_PRODUCCION", None) or "https://cel.sri.gob.ec",
}
RUTAS = {
    "recepcion":    "/comprobantes-electronicos-ws/RecepcionComprobantesOffline?wsdl",
    "autorizacion": "/comprobantes-electronicos-ws/AutorizacionComprobantesOffline?wsdl",
    "consulta":     "/comprobantes-electronicos-ws/ConsultaComprobante?wsdl",
}
TIMEOUT = httpx.Timeout(connect=10.0, read=30.0, write=30.0, pool=10.0)

# ── Estados normalizados ──────────────────────────────────────────────────────
RECIBIDA         = "RECIBIDA"
DEVUELTA         = "DEVUELTA"
AUTORIZADO       = "AUTORIZADO"
NO_AUTORIZADO    = "NO_AUTORIZADO"
EN_PROCESO       = "EN_PROCESO"
NO_ENCONTRADO    = "NO_ENCONTRADO"     # el SRI no tiene esa clave (todavía)
PENDIENTE_ANULAR = "PENDIENTE_ANULAR"
ANULADO          = "ANULADO"
FUERA_DE_RANGO   = "FUERA_DE_RANGO"    # consulta de validez: fecha fuera del rango permitido
TECNICO          = "TECNICO"           # no sabemos qué pasó: NO es una respuesta del SRI

# Códigos de recepción que NO son un rechazo del contenido
COD_EN_PROCESAMIENTO = "70"   # clave en procesamiento
COD_CLAVE_REGISTRADA = "43"   # el SRI ya tiene esta clave de acceso
COD_SECUENCIAL_REG   = "45"   # secuencial ya registrado (puede ser este mismo comprobante)


@dataclass
class RespuestaSRI:
    estado:            str
    mensajes:          list = field(default_factory=list)
    fecha:             str | None = None    # fechaAutorizacion
    numero:            str | None = None    # numeroAutorizacion
    comprobante:       str | None = None    # XML autorizado (CDATA)
    http_status:       int | None = None
    detalle:           str | None = None    # descripción de la falla técnica
    crudo:             str | None = None    # primeros caracteres de la respuesta (diagnóstico)
    posible_recepcion: bool = False         # falla técnica en la que el SRI PUDO haber recibido

    @property
    def ids(self) -> set[str]:
        return {str(m.get("identificador", "")).strip() for m in self.mensajes if m.get("identificador")}

    def resumen_tecnico(self) -> str:
        partes = [self.detalle or "Falla técnica"]
        if self.http_status:
            partes.append(f"HTTP {self.http_status}")
        if self.crudo:
            partes.append(f"Respuesta: {self.crudo!r}")
        return " · ".join(partes)


# =============================================================================
# PARSEO ROBUSTO
# =============================================================================
def _local(clave: str) -> str:
    return clave.split(":")[-1]


def _buscar(nodo, nombre: str):
    """Primer nodo cuyo nombre local coincide, sin importar el prefijo (soap:, S:, ns2:…)."""
    if isinstance(nodo, dict):
        for k, v in nodo.items():
            if _local(k) == nombre:
                return v
        for v in nodo.values():
            hallado = _buscar(v, nombre)
            if hallado is not None:
                return hallado
    elif isinstance(nodo, list):
        for v in nodo:
            hallado = _buscar(v, nombre)
            if hallado is not None:
                return hallado
    return None


def _lista(v) -> list:
    if v is None or v == "":
        return []
    return v if isinstance(v, list) else [v]


def _texto(v) -> str | None:
    if v is None:
        return None
    if isinstance(v, dict):
        v = v.get("#text")
    return str(v).strip() if v is not None else None


def _mensajes(nodo_mensajes) -> list[dict]:
    if not isinstance(nodo_mensajes, dict):
        return []
    salida = []
    for m in _lista(nodo_mensajes.get("mensaje")):
        if not isinstance(m, dict):
            continue
        salida.append({
            "identificador":        _texto(m.get("identificador")),
            "mensaje":              _texto(m.get("mensaje")),
            "informacionAdicional": _texto(m.get("informacionAdicional")),
            "tipo":                 _texto(m.get("tipo")),
        })
    return salida


def _crudo(texto: str | None) -> str | None:
    if not texto:
        return None
    return " ".join(texto[:300].split())


def _parsear(texto: str) -> dict:
    """Parsea el SOAP ignorando basura antes del primer '<' (BOM, espacios, etc.)."""
    if not texto or "<" not in texto:
        raise ExpatError("respuesta vacía o sin XML")
    inicio = texto.find("<")
    return xmltodict.parse(texto[inicio:])


# =============================================================================
# TRANSPORTE
# =============================================================================
async def _post(url: str, body: str) -> RespuestaSRI | tuple[int, str]:
    """
    Una sola petición. Solo se reintenta si NO llegó a salir (error de conexión).
    Un timeout de lectura NO se reintenta: el SRI pudo haberla recibido.
    """
    headers = {"Content-Type": "text/xml; charset=utf-8"}
    for intento in (1, 2, 3):
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                r = await client.post(url, content=body.encode("utf-8"), headers=headers)
                return r.status_code, r.text
        except (httpx.ConnectError, httpx.ConnectTimeout) as e:
            if intento == 3:
                return RespuestaSRI(estado=TECNICO, detalle=f"Sin conexión con el SRI: {type(e).__name__}",
                                    posible_recepcion=False)
        except (httpx.ReadTimeout, httpx.WriteTimeout, httpx.ReadError,
                httpx.RemoteProtocolError, httpx.PoolTimeout) as e:
            return RespuestaSRI(estado=TECNICO, detalle=f"Se cortó la comunicación con el SRI: {type(e).__name__}",
                                posible_recepcion=True)
        except httpx.HTTPError as e:
            return RespuestaSRI(estado=TECNICO, detalle=f"Error HTTP: {type(e).__name__}: {e}",
                                posible_recepcion=True)
    return RespuestaSRI(estado=TECNICO, detalle="Sin respuesta")  # inalcanzable


def _fallo_si_no_es_soap(status: int, texto: str) -> RespuestaSRI | dict:
    if status != 200:
        return RespuestaSRI(estado=TECNICO, http_status=status, crudo=_crudo(texto),
                            detalle="El SRI respondió con un error HTTP", posible_recepcion=True)
    try:
        doc = _parsear(texto)
    except ExpatError as e:
        return RespuestaSRI(estado=TECNICO, http_status=status, crudo=_crudo(texto),
                            detalle=f"Respuesta del SRI ilegible ({e})", posible_recepcion=True)
    fault = _buscar(doc, "Fault")
    if fault is not None:
        msg = _texto(_buscar(fault, "faultstring")) or "SOAP Fault"
        return RespuestaSRI(estado=TECNICO, http_status=status, crudo=_crudo(texto),
                            detalle=f"SRI Fault: {msg}", posible_recepcion=True)
    return doc


def url(ambiente, servicio: str) -> str:
    return f"{HOSTS[str(ambiente)]}{RUTAS[servicio]}"


# =============================================================================
# 1. RECEPCIÓN
# =============================================================================
async def enviar_comprobante(xml_bytes: bytes, ambiente) -> RespuestaSRI:
    import base64
    xml_b64 = base64.b64encode(xml_bytes).decode("ascii")
    body = (
        '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" '
        'xmlns:ec="http://ec.gob.sri.ws.recepcion">'
        f'<soapenv:Body><ec:validarComprobante><xml>{xml_b64}</xml>'
        '</ec:validarComprobante></soapenv:Body></soapenv:Envelope>'
    )
    res = await _post(url(ambiente, "recepcion"), body)
    if isinstance(res, RespuestaSRI):
        return res
    status, texto = res
    doc = _fallo_si_no_es_soap(status, texto)
    if isinstance(doc, RespuestaSRI):
        return doc

    resp = _buscar(doc, "RespuestaRecepcionComprobante")
    if not isinstance(resp, dict):
        return RespuestaSRI(estado=TECNICO, http_status=status, crudo=_crudo(texto),
                            detalle="Respuesta de recepción sin RespuestaRecepcionComprobante",
                            posible_recepcion=True)

    estado   = (_texto(resp.get("estado")) or "").upper()
    mensajes = []
    comprobantes = resp.get("comprobantes")
    if isinstance(comprobantes, dict):
        for c in _lista(comprobantes.get("comprobante")):
            if isinstance(c, dict):
                mensajes += _mensajes(c.get("mensajes"))

    if estado == "RECIBIDA":
        return RespuestaSRI(estado=RECIBIDA, mensajes=mensajes, http_status=status)
    if estado == "DEVUELTA":
        return RespuestaSRI(estado=DEVUELTA, mensajes=mensajes, http_status=status)
    return RespuestaSRI(estado=TECNICO, mensajes=mensajes, http_status=status, crudo=_crudo(texto),
                        detalle=f"Estado de recepción desconocido: {estado or '(vacío)'}",
                        posible_recepcion=True)


# =============================================================================
# 2. AUTORIZACIÓN
# =============================================================================
_MAPA_AUTORIZACION = {
    "AUTORIZADO":       AUTORIZADO,
    "NO AUTORIZADO":    NO_AUTORIZADO,
    "RECHAZADO":        NO_AUTORIZADO,
    "EN PROCESO":       EN_PROCESO,
    "EN PROCESAMIENTO": EN_PROCESO,
    "PPR":              EN_PROCESO,
}


async def consultar_autorizacion(clave_acceso: str, ambiente) -> RespuestaSRI:
    body = (
        '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" '
        'xmlns:ec="http://ec.gob.sri.ws.autorizacion">'
        '<soapenv:Body><ec:autorizacionComprobante>'
        f'<claveAccesoComprobante>{clave_acceso}</claveAccesoComprobante>'
        '</ec:autorizacionComprobante></soapenv:Body></soapenv:Envelope>'
    )
    res = await _post(url(ambiente, "autorizacion"), body)
    if isinstance(res, RespuestaSRI):
        return res
    status, texto = res
    doc = _fallo_si_no_es_soap(status, texto)
    if isinstance(doc, RespuestaSRI):
        return doc

    resp = _buscar(doc, "RespuestaAutorizacionComprobante")
    if not isinstance(resp, dict):
        return RespuestaSRI(estado=TECNICO, http_status=status, crudo=_crudo(texto),
                            detalle="Respuesta de autorización sin RespuestaAutorizacionComprobante")

    try:
        numero_comp = int(_texto(resp.get("numeroComprobantes")) or 0)
    except ValueError:
        numero_comp = 0
    autorizaciones = []
    nodo_aut = resp.get("autorizaciones")
    if isinstance(nodo_aut, dict):
        autorizaciones = [a for a in _lista(nodo_aut.get("autorizacion")) if isinstance(a, dict)]
    if numero_comp == 0 or not autorizaciones:
        return RespuestaSRI(estado=NO_ENCONTRADO, http_status=status)

    # Si hay varias (reenvíos), manda la AUTORIZADA; si no, la última
    elegida = next((a for a in autorizaciones if (_texto(a.get("estado")) or "").upper() == "AUTORIZADO"),
                   autorizaciones[-1])
    estado_sri = (_texto(elegida.get("estado")) or "").upper()
    estado     = _MAPA_AUTORIZACION.get(estado_sri)
    if not estado:
        return RespuestaSRI(estado=TECNICO, http_status=status, crudo=_crudo(texto),
                            detalle=f"Estado de autorización desconocido: {estado_sri or '(vacío)'}")

    return RespuestaSRI(
        estado      = estado,
        mensajes    = _mensajes(elegida.get("mensajes")),
        fecha       = _texto(elegida.get("fechaAutorizacion")),
        numero      = _texto(elegida.get("numeroAutorizacion")),
        comprobante = _texto(elegida.get("comprobante")),
        http_status = status,
    )


# =============================================================================
# 3. CONSULTA DE VALIDEZ (sirve también para verificar anulaciones)
# =============================================================================
_MAPA_CONSULTA = {
    "AUTORIZADO":          AUTORIZADO,
    "NO AUTORIZADO":       NO_AUTORIZADO,
    "PENDIENTE DE ANULAR": PENDIENTE_ANULAR,
    "ANULADO":             ANULADO,
}


async def consultar_estado(clave_acceso: str, ambiente) -> RespuestaSRI:
    body = (
        '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" '
        'xmlns:ec="http://ec.gob.sri.ws.consultas">'
        '<soapenv:Header/><soapenv:Body><ec:consultarEstadoAutorizacionComprobante>'
        f'<claveAcceso>{clave_acceso}</claveAcceso>'
        '</ec:consultarEstadoAutorizacionComprobante></soapenv:Body></soapenv:Envelope>'
    )
    res = await _post(url(ambiente, "consulta"), body)
    if isinstance(res, RespuestaSRI):
        return res
    status, texto = res
    doc = _fallo_si_no_es_soap(status, texto)
    if isinstance(doc, RespuestaSRI):
        return doc

    resp = _buscar(doc, "EstadoAutorizacionComprobante")
    if not isinstance(resp, dict):
        return RespuestaSRI(estado=TECNICO, http_status=status, crudo=_crudo(texto),
                            detalle="Respuesta de consulta sin EstadoAutorizacionComprobante")

    mensajes = _mensajes(resp.get("mensajes"))
    if (_texto(resp.get("estadoConsulta")) or "").upper() == "RECHAZADA":
        info = " ".join((m.get("informacionAdicional") or "") for m in mensajes).lower()
        return RespuestaSRI(estado=FUERA_DE_RANGO if "fuera del rango" in info else NO_ENCONTRADO,
                            mensajes=mensajes, http_status=status)

    estado_sri = (_texto(resp.get("estadoAutorizacion")) or "").upper()
    estado     = _MAPA_CONSULTA.get(estado_sri)
    if not estado:
        return RespuestaSRI(estado=TECNICO, mensajes=mensajes, http_status=status, crudo=_crudo(texto),
                            detalle=f"Estado de consulta desconocido: {estado_sri or '(vacío)'}")
    return RespuestaSRI(estado=estado, mensajes=mensajes, http_status=status,
                        fecha=_texto(resp.get("fechaAutorizacion")))