from pydantic import BaseModel, Field

class ValidatePuntoRequest(BaseModel):
    estab_codigo: str = Field(..., description="Código de establecimiento, Ej: 001", min_length=3, max_length=3)
    punto_codigo: str = Field(..., description="Código de punto de emisión, Ej: 001", min_length=3, max_length=3)