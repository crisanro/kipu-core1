from pydantic import BaseModel, EmailStr, Field
from typing import Optional

class ClienteCreate(BaseModel):
    tipo_identificacion_sri: str = Field(..., description="Ej: 04 (RUC), 05 (Cédula)")
    identificacion: str = Field(..., min_length=3)
    razon_social: str = Field(..., min_length=2)
    direccion: Optional[str] = None
    email: Optional[str] = None
    telefono: Optional[str] = None

class ClienteUpdate(BaseModel):
    email: Optional[EmailStr] = None
    telefono: Optional[str] = None
    razon_social: Optional[str] = None
    direccion: Optional[str]

class ClienteBusquedaMasiva(BaseModel):
    terminos: list[str] = Field(..., description="Lista de RUCs, cédulas o UUIDs internos")