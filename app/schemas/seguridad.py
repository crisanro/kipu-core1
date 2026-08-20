# app/schemas/seguridad.py
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional


class ApiKeyCreate(BaseModel):
    nombre: str  = Field(..., min_length=2, description="Nombre de la integración")
    pin:    str  = Field(..., min_length=6, max_length=6, description="PIN de verificación")


class ResetPasswordRequest(BaseModel):
    email: EmailStr


class VerifyPinRequest(BaseModel):
    pin: str = Field(..., min_length=6, max_length=6, description="PIN de 6 dígitos")


class RequestPinSchema(BaseModel):
    email:       str
    tipo_accion: str
    metadata:    Optional[dict] = None

    model_config = ConfigDict(from_attributes=True)