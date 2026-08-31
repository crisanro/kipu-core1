# app/schemas/emisor.py
from pydantic import BaseModel, Field
from typing import Optional


class OnboardingRequest(BaseModel):
    # Modo vinculación (invitado)
    emisor_id:              Optional[int] = None 
    rol:                    Optional[str] = "emisor" 
    # Modo creación (campos obligatorios solo si no viene emisor_id)
    ruc:                    Optional[str] = Field(None, pattern=r"^\d{13}$")
    razon_social:           Optional[str] = Field(None, min_length=3)
    nombre_comercial:       Optional[str] = None
    direccion_matriz:       Optional[str] = Field(None, min_length=5)
    obligado_contabilidad:  str           = Field("NO", pattern="^(SI|NO)$")
    contribuyente_especial: Optional[str] = None
    tipo_emisor:            str           = Field("NATURAL", pattern="^(NATURAL|JURIDICO)$")
    full_name:              Optional[str] = None


class EmisorUpdate(BaseModel):
    nombre_comercial:       Optional[str] = None
    direccion_matriz:       Optional[str] = None
    contribuyente_especial: Optional[str] = Field(None, max_length=5)
    obligado_contabilidad:  Optional[str] = Field(None, max_length=2)
    tipo_emisor:            Optional[str] = Field(None, pattern="^(NATURAL|JURIDICO)$")