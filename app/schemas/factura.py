from pydantic import BaseModel, Field, model_validator
from typing import Optional, Any
from datetime import date, datetime
from uuid import UUID

class ClienteFactura(BaseModel):
    tipo_id: str = Field(..., description="04=RUC, 05=Cédula, 06=Pasaporte")
    nombre: str = Field(..., min_length=2)
    identificacion: str = Field(..., min_length=3)
    email: Optional[str] = None

class ItemFactura(BaseModel):
    descripcion:     str           = Field(..., min_length=2)
    cantidad:        float         = Field(..., gt=0)
    precio_unitario: float         = Field(..., ge=0)
    descuento:       float         = Field(0.0, ge=0)
    tipo_iva:        Optional[str] = Field("15")
    unidad_medida:   Optional[str] = Field("UNIDAD")

class PagoFactura(BaseModel):
    forma_pago: str = Field("01", description="01=Efectivo, 20=Transferencia")
    total: float = Field(..., gt=0)
    plazo: Optional[str] = "0"
    unidad_tiempo: Optional[str] = "dias"

class FacturaCreate(BaseModel):
    establecimiento: str = Field(..., description="Ej: 001")
    punto_emision:   str = Field(..., description="Ej: 001")
    cliente_id:      Optional[str]          = None  # UUID o "consumidor_final"
    cliente:         Optional[ClienteFactura] = None  # objeto directo
    items:           list[ItemFactura] = Field(..., min_length=1)
    pagos:           list[PagoFactura] = Field(..., min_length=1)
    campos_adicionales: Optional[list[dict]] = None

    @model_validator(mode='after')
    def validar_cliente(self):
        if not self.cliente_id and not self.cliente:
            raise ValueError("Debe proporcionar cliente_id o cliente.")
        return self

class InvoiceSchema(BaseModel):
    id: UUID
    emisor_id: int
    punto_emision_id: int
    clave_acceso: Optional[str]
    secuencial: str
    fecha_emision: date
    estado: str
    identificacion_comprador: str
    razon_social_comprador: str
    importe_total: float
    datos_factura: dict  # Para tu columna jsonb
    mensajes_sri: Optional[Any] # Para tu columna jsonb
    
    class Config:
        from_attributes = True