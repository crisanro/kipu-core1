# app/core/permisos.py
#
# Sistema de permisos granulares por usuario/empresa.
# El rol es una etiqueta de referencia — los permisos JSONB son lo que controla el acceso.
# Admin siempre tiene todo, sin restricciones.

from fastapi import HTTPException

# Permisos por defecto al invitar según rol
PERMISOS_DEFAULT = {
    "admin": {},  # admin siempre tiene todo
    "contador": {
        "emitir":        True,
        "descargar":     True,
        "clientes":      True,
        "productos":     True,
        "declaraciones": True,
        "reportes":      True,
        "documentos_recibidos": True,
        "configuracion": False,
        "api_keys":      False,
        "usuarios":      False,
    },
    "emisor": {
        "emitir":        True,
        "descargar":     True,
        "clientes":      True,
        "productos":     True,
        "documentos_recibidos": True,
        "declaraciones": False,
        "reportes":      False,
        "configuracion": False,
        "api_keys":      False,
        "usuarios":      False,
    },
}

PERMISOS_DISPONIBLES = [
    "emitir",               # crear comprobantes
    "descargar",            # descargar PDF/XML
    "clientes",             # ver y editar clientes
    "productos",            # ver y editar productos
    "declaraciones",        # ver declaraciones SRI
    "reportes",             # ver dashboard y reportes
    "configuracion",        # ver y editar configuración del emisor
    "api_keys",             # crear y revocar API keys
    "usuarios",             # invitar y gestionar usuarios
    "documentos_recibidos", # registrar y editar documentos de proveedores
]

def permisos_para_rol(rol: str) -> dict:
    """Retorna los permisos por defecto para un rol."""
    return PERMISOS_DEFAULT.get(rol, PERMISOS_DEFAULT["emisor"]).copy()

def tiene_permiso(rol: str, permisos: dict, permiso: str) -> bool:
    """Verifica si un usuario tiene un permiso específico."""
    if rol == "admin":
        return True  # admin siempre tiene todo
    return bool(permisos.get(permiso, False))

def verificar_permiso(auth_data: dict, permiso: str):
    """
    Lanza 403 si el usuario no tiene el permiso.
    Uso: verificar_permiso(auth_data, "emitir")
    """
    rol      = auth_data.get("emisor_rol", "emisor")
    permisos = auth_data.get("permisos", {})
    if not tiene_permiso(rol, permisos, permiso):
        raise HTTPException(
            status_code=403,
            detail="No tienes permisos para realizar esta acción."
        )

def verificar_admin(auth_data: dict):
    """
    Lanza 403 si el usuario no es admin.
    Uso: verificar_admin(auth_data)
    """
    if auth_data.get("emisor_rol") != "admin":
        raise HTTPException(
            status_code=403,
            detail="Solo el administrador puede realizar esta acción."
        )

def verificar_email(auth_data: dict):
    """
    Lanza 403 si el email no está verificado.
    Uso: verificar_email(auth_data)
    """
    if not auth_data.get("email_verified", False):
        raise HTTPException(
            status_code=403,
            detail="Debes verificar tu correo electrónico antes de continuar.",
            headers={"X-Error-Code": "EMAIL_NOT_VERIFIED"},
        )