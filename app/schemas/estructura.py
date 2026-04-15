from pydantic import BaseModel, Field
from typing import Optional

class EstablecimientoCreate(BaseModel):
    codigo: int
    nombre_comercial: Optional[str] = None
    direccion: Optional[str] = None

class EstablecimientoUpdate(BaseModel):
    nombre_comercial: Optional[str] = None
    direccion: Optional[str] = None
    is_active: Optional[bool] = None  # Agregado para activar/inactivar desde aquí

class PuntoEmisionCreate(BaseModel):
    establecimiento_codigo: int
    codigo: str
    nombre: Optional[str] = None

class PuntoEmisionUpdate(BaseModel):
    nombre: Optional[str] = None
    is_active: Optional[bool] = None