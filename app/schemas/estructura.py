# app/schemas/estructura.py
from pydantic import BaseModel, Field
from typing import Optional
from datetime import date


class EstablecimientoCreate(BaseModel):
    codigo:           int
    nombre_comercial: Optional[str] = None
    direccion:        Optional[str] = None


class EstablecimientoUpdate(BaseModel):
    nombre_comercial: Optional[str]  = None
    direccion:        Optional[str]  = None
    is_active:        Optional[bool] = None


class PuntoEmisionCreate(BaseModel):
    establecimiento_codigo: int
    codigo:                 str
    nombre:                 Optional[str] = None


class PuntoEmisionUpdate(BaseModel):
    nombre:    Optional[str]  = None
    is_active: Optional[bool] = None