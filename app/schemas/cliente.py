from pydantic import BaseModel, Field, field_validator
from typing import Optional
import re

_TIPOS_VALIDOS = {"04", "05", "06", "08"}
_EMAIL_REGEX   = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")


def _validar_email(v):
    """Helper reutilizable para validar email opcional."""
    if not v or not str(v).strip():
        return ""
    v = v.strip().lower()
    if not _EMAIL_REGEX.match(v):
        raise ValueError("El email no tiene un formato válido.")
    return v


class ClienteCreate(BaseModel):
    tipo_identificacion_sri: str          = Field(..., description="04=RUC, 05=Cédula, 06=Pasaporte, 08=Exterior")
    identificacion:          str          = Field(..., min_length=3)
    razon_social:            str          = Field(..., min_length=2)
    direccion:               Optional[str] = None
    email:                   Optional[str] = None
    telefono:                Optional[str] = None

    @field_validator("tipo_identificacion_sri", mode="before")
    @classmethod
    def validar_tipo(cls, v):
        if not v or not str(v).strip():
            raise ValueError("El tipo de identificación es obligatorio.")
        if v not in _TIPOS_VALIDOS:
            raise ValueError("Tipo inválido. Use: 04=RUC, 05=Cédula, 06=Pasaporte, 08=Exterior")
        return v

    @field_validator("identificacion")
    @classmethod
    def limpiar_identificacion(cls, v):
        return v.strip().upper()

    @field_validator("razon_social")
    @classmethod
    def mayusculas_razon(cls, v):
        return v.strip().upper()

    @field_validator("email", mode="before")
    @classmethod
    def validar_email(cls, v):
        return _validar_email(v)

    @field_validator("telefono", mode="before")
    @classmethod
    def limpiar_telefono(cls, v):
        if not v or not str(v).strip():
            return ""
        return v.strip()

    @field_validator("direccion", mode="before")
    @classmethod
    def limpiar_direccion(cls, v):
        if not v or not str(v).strip():
            return ""
        return v.strip().upper()


class ClienteUpdate(BaseModel):
    razon_social: Optional[str] = None
    direccion:    Optional[str] = None
    email:        Optional[str] = None
    telefono:     Optional[str] = None

    @field_validator("email", mode="before")
    @classmethod
    def validar_email(cls, v):
        return _validar_email(v)

    @field_validator("razon_social", mode="before")
    @classmethod
    def mayusculas_razon(cls, v):
        if not v or not str(v).strip():
            return None
        return v.strip().upper()

    @field_validator("direccion", mode="before")
    @classmethod
    def mayusculas_direccion(cls, v):
        if not v or not str(v).strip():
            return None
        return v.strip().upper()

    @field_validator("telefono", mode="before")
    @classmethod
    def limpiar_telefono(cls, v):
        if not v or not str(v).strip():
            return None
        return v.strip()
    
    
class ClienteBusquedaMasiva(BaseModel):
    terminos: list[str] = Field(..., description="Lista de RUCs, cédulas o UUIDs internos")