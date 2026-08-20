# app/schemas/factura.py
#
# Schemas de entrada y salida para emisión de documentos electrónicos.
from pydantic import BaseModel, Field, model_validator
from typing import Optional, Any
from datetime import date
from uuid import UUID

# =============================================================================
# SCHEMAS DE ENTRADA
# =============================================================================
class ClienteDoc(BaseModel):
    tipo_id:        str            = Field(..., description="04=RUC 05=Cédula 06=Pasaporte 07=Consumidor Final")
    nombre:         str            = Field(..., min_length=2)
    identificacion: str            = Field(..., min_length=3)
    email:          Optional[str]  = None
    direccion:      Optional[str]  = "S/N"
    telefono:       Optional[str]  = ""

class ItemDoc(BaseModel):
    codigo:          Optional[str]   = None
    descripcion:     Optional[str]   = None
    cantidad:        float            = Field(..., gt=0)
    precio_unitario: Optional[float] = None
    descuento:       float            = Field(0.0, ge=0)
    tipo_iva:        Optional[str]   = "15"
    unidad_medida:   Optional[str]   = "UNIDAD"

class PagoDoc(BaseModel):
    forma_pago:    str             = "01"
    total:         Optional[float] = None
    plazo:         Optional[str]   = "0"
    unidad_tiempo: Optional[str]   = "dias"

class CampoAdicional(BaseModel):
    nombre: str
    valor:  str

class MotivoNDB(BaseModel):
    razon: str
    valor: float

class ImpuestoRET(BaseModel):
    codigo:            str            = "1"   # 1=Renta 2=IVA 6=ISD
    codigoRetencion:   str                    # código SRI ej: 303, 1, 2
    baseImponible:     float
    porcentajeRetener: float                  # porcentaje ej: 10, 30, 100
    valorRetenido:     float
    codDocSustento:    Optional[str]  = None
    # Aliases backward compat
    codigoPorcentaje:  Optional[str]  = None
    tarifa:            Optional[str]  = None
    valor:             Optional[float] = None

    @model_validator(mode="after")
    def resolver_aliases(self):
        # Soportar tanto codigoRetencion como codigoPorcentaje (viejo)
        if not self.codigoRetencion and self.codigoPorcentaje:
            self.codigoRetencion = self.codigoPorcentaje
        if not self.porcentajeRetener and self.tarifa:
            self.porcentajeRetener = float(self.tarifa)
        if not self.valorRetenido and self.valor:
            self.valorRetenido = self.valor
        return self

# Datos del cliente cuando el doc origen no está en Kipu
class ClienteOrigenManual(BaseModel):
    tipo_id:        str           = "05"
    identificacion: str
    razon_social:   str
    email:          Optional[str] = None
    direccion:      Optional[str] = "S/N"

# =============================================================================
# SCHEMA PRINCIPAL DE EMISIÓN
# =============================================================================
class DocumentoCreate(BaseModel):
    """
    Schema unificado para emitir cualquier comprobante electrónico.
    FAC / LIQ: cliente + items + pagos
    NCR / NDB:  doc_origen_id (Kipu) O doc_origen_manual + cliente_origen + items/motivos
    RET:        doc_origen_recibido_id + impuestos
    """
    # Estructura SRI
    establecimiento: str = Field("001")
    punto_emision:   str = Field("001")

    # Cliente — FAC y LIQ
    cliente_id: Optional[str]        = None
    cliente:    Optional[ClienteDoc] = None

    # Items — FAC, LIQ, NCR
    items:   Optional[list[ItemDoc]]  = None
    pagos:   Optional[list[PagoDoc]]  = None
    propina: Optional[float]          = 0

    # NCR / NDB — doc origen en Kipu
    doc_origen_id: Optional[str] = None
    motivo:        Optional[str] = None   # NCR

    # NCR / NDB — doc origen MANUAL (no está en Kipu)
    doc_origen_numero:  Optional[str] = None  # "001-001-000000123"
    doc_origen_fecha:   Optional[str] = None  # "21/10/2012" dd/mm/yyyy
    doc_origen_cod_doc: Optional[str] = None  # "01"=FAC "03"=LIQ
    cliente_origen:     Optional[ClienteOrigenManual] = None

    # NDB
    motivos:   Optional[list[MotivoNDB]]   = None
    impuestos: Optional[list[dict]]        = None  # NDB impuestos

    # RET
    doc_origen_recibido_id: Optional[str]           = None
    impuestos_ret:          Optional[list[ImpuestoRET]] = None
    periodo_fiscal:         Optional[str]            = None

    # Extras
    campos_adicionales: Optional[list[CampoAdicional]] = None
    origen:             Optional[str]                   = "web"

    @model_validator(mode="after")
    def validar_por_contexto(self):
        tiene_cliente     = bool(self.cliente_id or self.cliente)
        tiene_origen_kipu = bool(self.doc_origen_id or self.doc_origen_recibido_id)
        tiene_origen_manual = bool(self.doc_origen_numero and self.doc_origen_fecha)
        tiene_ret         = bool(self.impuestos_ret or self.impuestos)

        if not tiene_cliente and not tiene_origen_kipu and not tiene_origen_manual and not tiene_ret:
            raise ValueError(
                "Debe proporcionar cliente, doc_origen_id, "
                "doc_origen_recibido_id, o doc_origen_numero+fecha."
            )
        return self

# =============================================================================
# SCHEMAS DE SALIDA
# =============================================================================
class DocumentoEmitidoSchema(BaseModel):
    id:            UUID
    emisor_id:     int
    tipo_doc:      str
    cod_doc:       str
    clave_acceso:  Optional[str]
    numero_doc:    Optional[str]
    secuencial:    Optional[str]
    fecha_emision: date
    estado_sri:    str
    estado_cobro:  Optional[str]
    importe_total: float
    datos:         dict
    mensajes_sri:  Optional[Any]

    class Config:
        from_attributes = True

# Aliases backward compat
FacturaCreate  = DocumentoCreate
ClienteFactura = ClienteDoc
ItemFactura    = ItemDoc
PagoFactura    = PagoDoc
InvoiceSchema  = DocumentoEmitidoSchema