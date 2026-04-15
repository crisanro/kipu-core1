from pydantic import BaseModel, Field
from typing import Optional

class OnboardingRequest(BaseModel):
    ruc: str = Field(..., pattern=r"^\d{13}$", description="RUC de 13 dígitos")
    razon_social: str = Field(..., min_length=3)
    nombre_comercial: Optional[str] = None
    direccion_matriz: str = Field(..., min_length=5)
    obligado_contabilidad: str = Field(..., pattern="^(SI|NO)$")
    contribuyente_especial: Optional[str] = None
    full_name: Optional[str] = None

class EmisorUpdate(BaseModel):
    nombre_comercial: Optional[str] = Field(None, min_length=3)
    direccion_matriz: Optional[str] = Field(None, min_length=5)
    contribuyente_especial: Optional[str] = Field(None, max_length=5)
    obligado_contabilidad: Optional[str] = Field(None, max_length=2) # 'SI' o 'NO'