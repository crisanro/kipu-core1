# app/core/permisos.py
#
# Sistema de permisos granulares por usuario/empresa.
# El rol es una etiqueta de referencia — los permisos JSONB son lo que controla el acceso.
# Admin siempre tiene todo, sin restricciones.
#
# Filosofía:
#   - "emitir" implica LECTURA de clientes, productos y estructura (necesarios para emitir)
#   - "clientes", "productos", "estructura" controlan EDICIÓN (crear/editar/eliminar)
#   - Endpoints GET usan verificar_algun_permiso(auth_data, ["emitir", "clientes"])
#   - Endpoints POST/PUT/DELETE usan verificar_permiso(auth_data, "clientes")

from fastapi import HTTPException

PERMISOS_DEFAULT = {
    "admin": {},
    "contador": {
        "emitir":               True,
        "descargar":            True,
        "clientes":             True,
        "productos":            True,
        "estructura":           True,
        "declaraciones":        True,
        "reportes":             True,
        "documentos_recibidos": True,
        "auditoria":            False,
        "configuracion":        False,
        "api_keys":             False,
        "usuarios":             False,
    },
    "asistente": {
        "emitir":               True,
        "descargar":            True,
        "clientes":             True,
        "productos":            True,
        "estructura":           True,
        "documentos_recibidos": True,
        "declaraciones":        False,
        "reportes":             False,
        "auditoria":            False,
        "configuracion":        False,
        "api_keys":             False,
        "usuarios":             False,
    },
    "emisor": {
        "emitir":               True,
        "descargar":            True,
        "documentos_recibidos": True,
        "clientes":             False,
        "productos":            False,
        "estructura":           False,
        "declaraciones":        False,
        "reportes":             False,
        "auditoria":            False,
        "configuracion":        False,
        "api_keys":             False,
        "usuarios":             False,
    },
}

PERMISOS_DISPONIBLES = [
    "emitir",               # emitir comprobantes + lectura de clientes, productos, estructura
    "descargar",            # descargar PDF/XML
    "clientes",             # crear, editar y eliminar clientes
    "productos",            # crear, editar y eliminar productos
    "estructura",           # crear y editar establecimientos y puntos de emisión
    "declaraciones",        # ver declaraciones SRI
    "reportes",             # ver dashboard y reportes
    "documentos_recibidos", # registrar y editar documentos de proveedores
    "auditoria",            # ver log de auditoría
    "configuracion",        # datos fiscales, firma, leyendas
    "api_keys",             # crear y revocar API keys
    "usuarios",             # invitar y gestionar usuarios
]

def permisos_para_rol(rol: str) -> dict:
    return PERMISOS_DEFAULT.get(rol, PERMISOS_DEFAULT["emisor"]).copy()

def tiene_permiso(rol: str, permisos: dict, permiso: str) -> bool:
    if rol == "admin":
        return True
    return bool(permisos.get(permiso, False))

def tiene_algun_permiso(rol: str, permisos: dict, permisos_requeridos: list[str]) -> bool:
    """True si el usuario tiene AL MENOS UNO de los permisos listados."""
    if rol == "admin":
        return True
    return any(permisos.get(p, False) for p in permisos_requeridos)

def verificar_permiso(auth_data: dict, permiso: str):
    rol      = auth_data.get("emisor_rol", "emisor")
    permisos = auth_data.get("permisos", {})
    if not tiene_permiso(rol, permisos, permiso):
        raise HTTPException(status_code=403, detail="No tienes permisos para realizar esta acción.")

def verificar_algun_permiso(auth_data: dict, permisos_requeridos: list[str]):
    """Lanza 403 si el usuario no tiene AL MENOS UNO de los permisos."""
    rol      = auth_data.get("emisor_rol", "emisor")
    permisos = auth_data.get("permisos", {})
    if not tiene_algun_permiso(rol, permisos, permisos_requeridos):
        raise HTTPException(status_code=403, detail="No tienes permisos para realizar esta acción.")

def verificar_admin(auth_data: dict):
    if auth_data.get("emisor_rol") != "admin":
        raise HTTPException(status_code=403, detail="Solo el administrador puede realizar esta acción.")

def verificar_email(auth_data: dict):
    if not auth_data.get("email_verified", False):
        raise HTTPException(
            status_code=403,
            detail="Debes verificar tu correo electrónico antes de continuar.",
            headers={"X-Error-Code": "EMAIL_NOT_VERIFIED"},
        )