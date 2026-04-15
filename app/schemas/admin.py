from pydantic import BaseModel, EmailStr, Field
from typing import Optional

class TopupRequest(BaseModel):
    ruc: str = Field(..., description="RUC del emisor", min_length=13, max_length=13)
    amount: int = Field(..., description="Cantidad de créditos a recargar", gt=0)
    reference_id: Optional[str] = Field(None, description="ID de referencia (ej. Stripe)")

class RequestPin(BaseModel):
    email: EmailStr
    whatsapp_number: str = Field(..., min_length=8)
    tipo_accion: Optional[str] = Field("VALIDACION_GENERAL", description="Contexto del PIN")