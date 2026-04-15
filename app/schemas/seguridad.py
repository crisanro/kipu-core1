from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional


class ApiKeyCreate(BaseModel):
    nombre: str = Field(..., min_length=2, description="Nombre de la integración (ej. ERP)")

class ResetPasswordRequest(BaseModel):
    email: EmailStr

class VerifyPinRequest(BaseModel):
    pin: str = Field(..., min_length=6, max_length=6, description="PIN de 6 dígitos recibido por WhatsApp")


class RequestPinSchema(BaseModel):
    whatsapp_number: str
    tipo_accion: str
    email: Optional[str] = None # Más flexible para debug que EmailStr
    metadata: Optional[dict] = None
    
    model_config = ConfigDict(from_attributes=True)

class ApiKeyCreate(BaseModel):
    nombre: str
    pin: str  # El PIN que el usuario recibió por WhatsApp