from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional

class TopupRequest(BaseModel):
    ruc:          str
    amount:       int
    tipo:         str = Field(..., description="'emision' o 'recepcion'")
    reference_id: Optional[str] = None

    @field_validator("tipo")
    @classmethod
    def validar_tipo(cls, v):
        if v not in ["emision", "recepcion"]:
            raise ValueError("tipo debe ser 'emision' o 'recepcion'")
        return v

class RequestPin(BaseModel):
    email: EmailStr
    whatsapp_number: str = Field(..., min_length=8)
    tipo_accion: Optional[str] = Field("VALIDACION_GENERAL", description="Contexto del PIN")