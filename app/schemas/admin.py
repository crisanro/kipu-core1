# app/schemas/admin.py
from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional


class TopupRequest(BaseModel):
    """Recarga de créditos API a un emisor."""
    emisor_id: int
    cantidad:  int   = Field(..., gt=0)
    notas:     Optional[str] = "Recarga manual admin"


class RequestPin(BaseModel):
    email:       EmailStr
    tipo_accion: Optional[str] = Field("VALIDACION_GENERAL")