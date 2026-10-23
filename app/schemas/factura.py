# app/schemas/factura.py
from pydantic import BaseModel, Field, model_validator
from typing import Optional, List, Any
from datetime import date
from uuid import UUID

# =============================================================================
# BLOQUES COMPONENTES
# =============================================================================

class ClienteDoc(BaseModel):
    """Datos del cliente/comprador del comprobante."""
    tipo_id:        str           = Field(..., description="Tipo de identificación SRI: 04=RUC, 05=Cédula, 06=Pasaporte, 07=Consumidor Final, 08=Identificación del Exterior", examples=["05"])
    nombre:         str           = Field(..., min_length=2, description="Nombre o razón social del comprador", examples=["Juan Pérez"])
    identificacion: str           = Field(..., min_length=3, description="Número de identificación (RUC, cédula, pasaporte)", examples=["1722334455"])
    email:          Optional[str] = Field(None, description="Email para envío automático del RIDE", examples=["juan.perez@example.com"])
    direccion:      Optional[str] = Field("S/N", description="Dirección del comprador", examples=["Av. Amazonas y Colón, Quito"])
    telefono:       Optional[str] = Field("", description="Teléfono de contacto", examples=["0991234567"])

class ItemDoc(BaseModel):
    """Ítem/detalle de un comprobante (factura, liquidación o nota de crédito)."""
    codigo:          Optional[str]   = Field(None, description="Código interno del producto/servicio", examples=["PROD-001"])
    descripcion:     str             = Field(..., description="Descripción del bien o servicio", examples=["Servicio de desarrollo de software"])
    cantidad:        float           = Field(..., gt=0, description="Cantidad vendida", examples=[1.0])
    precio_unitario: float           = Field(..., ge=0, description="Precio unitario sin impuestos", examples=[100.00])
    descuento:       float           = Field(0.0, ge=0, description="Descuento en valor absoluto (no porcentaje)", examples=[0.0])
    tipo_iva:        Optional[str]   = Field("15", description="Tarifa IVA: 15 (15%), 0 (0%), 5 (5%), NA (No aplica), EX (Exento)", examples=["15"])
    unidad_medida:   Optional[str]   = Field("UNIDAD", description="Unidad de medida", examples=["UNIDAD"])
    guardar_catalogo: Optional[bool] = Field(False, description="Si true, guarda el ítem en el catálogo del emisor para autocompletado futuro")

class PagoDoc(BaseModel):
    """Forma de pago del comprobante según catálogo SRI."""
    forma_pago:    str             = Field("01", description="Código SRI de forma de pago: 01=Sin utilización del sistema financiero, 15=Compensación de deudas, 16=Tarjeta de débito, 17=Dinero electrónico, 18=Tarjeta prepago, 19=Tarjeta de crédito, 20=Otros con utilización del sistema financiero", examples=["20"])
    total:         float           = Field(..., description="Monto pagado con esta forma de pago", examples=[115.00])
    plazo:         Optional[str]   = Field("0", description="Plazo del pago", examples=["0"])
    unidad_tiempo: Optional[str]   = Field("dias", description="Unidad de tiempo del plazo", examples=["dias"])

class CampoAdicional(BaseModel):
    """Campo adicional que aparece al pie del comprobante (máx. 300 caracteres por valor)."""
    nombre: str = Field(..., description="Nombre del campo", examples=["Observaciones"])
    valor:  str = Field(..., description="Valor del campo", examples=["Servicio correspondiente a octubre 2026"])

class MotivoNDB(BaseModel):
    """Motivo/razón del cargo en una Nota de Débito."""
    razon: str   = Field(..., description="Descripción del cargo", examples=["Intereses por mora en pago"])
    valor: float = Field(..., gt=0, description="Valor del cargo", examples=[15.00])

class ImpuestoRET(BaseModel):
    """Línea de impuesto retenido en un Comprobante de Retención."""
    codigo:            str            = Field("1", description="Tipo de impuesto: 1=Renta, 2=IVA, 6=ISD", examples=["1"])
    codigoRetencion:   str            = Field(..., description="Código de retención SRI (ej: 303=Honorarios profesionales 10%, 312=Transferencia de bienes 1%)", examples=["303"])
    baseImponible:     float          = Field(..., description="Base imponible sobre la que se aplica la retención", examples=[100.00])
    porcentajeRetener: float          = Field(..., description="Porcentaje de retención", examples=[10.0])
    valorRetenido:     float          = Field(..., description="Valor retenido = baseImponible × porcentajeRetener / 100", examples=[10.00])
    codDocSustento:    Optional[str]  = Field(None, description="Código del documento sustento (01=Factura, 03=Liquidación)", examples=["01"])
    codigoPorcentaje:  Optional[str]  = Field(None, description="Alias de codigoRetencion (compatibilidad)")
    tarifa:            Optional[str]  = Field(None, description="Alias de porcentajeRetener (compatibilidad)")
    valor:             Optional[float] = Field(None, description="Alias de valorRetenido (compatibilidad)")

    @model_validator(mode="after")
    def resolver_aliases(self):
        if not self.codigoRetencion and self.codigoPorcentaje:
            self.codigoRetencion = self.codigoPorcentaje
        if not self.porcentajeRetener and self.tarifa:
            self.porcentajeRetener = float(self.tarifa)
        if not self.valorRetenido and self.valor:
            self.valorRetenido = self.valor
        return self

class ClienteOrigenManual(BaseModel):
    """Datos del cliente/proveedor cuando el documento origen es externo (no existe en Kipu)."""
    tipo_id:        str           = Field("05", examples=["05"])
    identificacion: str           = Field(..., description="Identificación del cliente del documento origen", examples=["1722334455"])
    razon_social:   str           = Field(..., description="Razón social / nombre", examples=["Juan Pérez"])
    email:          Optional[str] = Field(None, examples=["juan@example.com"])
    direccion:      Optional[str] = Field("S/N", examples=["Quito"])


# =============================================================================
# RESPONSE SCHEMAS
# =============================================================================

class EmisionResponse(BaseModel):
    """Respuesta exitosa de emisión de comprobante."""
    ok:          bool = Field(True, description="Siempre true en respuesta exitosa")
    id:          str  = Field(..., description="UUID del documento emitido en Kipu", examples=["d4e5f6a7-8901-2345-6789-abcdef012345"])
    tipo_doc:    str  = Field(..., description="Tipo de documento emitido", examples=["FAC"])
    claveAcceso: str  = Field(..., description="Clave de acceso SRI de 49 dígitos", examples=["2210202601091234567800110010010000001231234567816"])
    estado:      str  = Field(..., description="FIRMADO (producción, pendiente autorización SRI) o SANDBOX (pruebas)", examples=["FIRMADO"])
    es_sandbox:  bool = Field(..., description="True si se emitió en ambiente de pruebas", examples=[False])
    mensaje:     str  = Field(..., description="Mensaje descriptivo", examples=["Comprobante en proceso de autorización."])

class ErrorResponse(BaseModel):
    """Respuesta de error estándar."""
    detail: str = Field(..., description="Descripción del error", examples=["Tipo de documento inválido: XYZ"])


# =============================================================================
# SCHEMAS DE EMISIÓN POR TIPO DE DOCUMENTO
# =============================================================================

class FacturaCreate(BaseModel):
    """
    Factura Electrónica (FAC / código SRI 01).

    El comprador se identifica con `cliente_id` (UUID de un cliente ya creado en Kipu)
    o con el objeto `cliente` para crear/usar uno al vuelo.

    **Reglas SRI:**
    - Consumidor Final (tipo_id=07): máximo $50.00.
    - Transacciones >= $500: no pueden usar efectivo (forma_pago=01).
    """
    establecimiento:         str                            = Field("001", min_length=3, max_length=3, description="Código del establecimiento (3 dígitos)", examples=["001"])
    punto_emision:           str                            = Field("001", min_length=3, max_length=3, description="Código del punto de emisión (3 dígitos)", examples=["001"])
    cliente_id:              Optional[str]                  = Field(None, description="UUID del cliente existente en Kipu")
    cliente:                 Optional[ClienteDoc]           = Field(None, description="Datos del cliente si no existe en Kipu (se crea al vuelo)")
    items:                   List[ItemDoc]                  = Field(..., min_length=1, description="Detalle de bienes/servicios (mínimo 1)")
    pagos:                   List[PagoDoc]                  = Field(..., min_length=1, description="Formas de pago (la suma debe coincidir con el total)")
    propina:                 Optional[float]                = Field(0.0, ge=0, description="Propina (se suma al importe total)", examples=[0.0])
    campos_adicionales:      Optional[List[CampoAdicional]] = Field(None, description="Información adicional al pie del comprobante")
    estado_cobro:            Optional[str]                  = Field(None, description="Estado de cobro: PAGADO (default si no se envía), PENDIENTE, PARCIAL. Si se omite, se registra como PAGADO.")
    forma_pago_cobro:        Optional[str]                  = Field(None, description="Forma de pago del cobro: EFECTIVO, TRANSFERENCIA, TARJETA, CHEQUE, OTRO")
    numero_comprobante_pago: Optional[str]                  = Field(None, description="Número de comprobante de pago (referencia bancaria, número de recibo, etc.)")
    fecha_pago:              Optional[str]                  = Field(None, description="Fecha de pago en formato YYYY-MM-DD. Si se omite y estado_cobro es PAGADO, se usa la fecha de emisión.")

    @model_validator(mode="after")
    def validar_cliente(self):
        if not self.cliente_id and not self.cliente:
            raise ValueError("Debe proporcionar 'cliente_id' (existente) o el objeto 'cliente' (nuevo).")
        return self


class NotaCreditoCreate(BaseModel):
    """
    Nota de Crédito Electrónica (NCR / código SRI 04).

    Modifica una factura previamente autorizada. Puede referenciar un documento
    interno de Kipu (`doc_origen_id`) o uno externo (`doc_origen_numero` + `doc_origen_fecha`).

    **Reglas SRI:**
    - No se puede emitir sobre Consumidor Final (tipo_id=07).
    - Los ítems deben corresponder a líneas del documento original.
    """
    establecimiento:    str                            = Field("001", min_length=3, max_length=3, examples=["001"])
    punto_emision:      str                            = Field("001", min_length=3, max_length=3, examples=["001"])
    doc_origen_id:      Optional[str]                  = Field(None, description="UUID del comprobante autorizado en Kipu a modificar")
    doc_origen_numero:  Optional[str]                  = Field(None, description="Número de documento externo (ej: 001-001-000000123)")
    doc_origen_fecha:   Optional[str]                  = Field(None, description="Fecha del documento externo en formato dd/mm/yyyy")
    doc_origen_cod_doc: Optional[str]                  = Field("01", description="Código SRI del documento origen (01=Factura)")
    cliente_origen:     Optional[ClienteOrigenManual]  = Field(None, description="Requerido si el documento origen es externo")
    motivo:             str                            = Field("ANULACION DE COMPROBANTE", description="Motivo de la nota de crédito", examples=["DEVOLUCION DE MERCADERIA"])
    items:              List[ItemDoc]                  = Field(..., min_length=1, description="Ítems que se devuelven/anulan")
    campos_adicionales: Optional[List[CampoAdicional]] = None


class NotaDebitoCreate(BaseModel):
    """
    Nota de Débito Electrónica (NDB / código SRI 05).

    Carga valores adicionales (intereses, diferencias, penalizaciones) sobre una
    factura previamente autorizada.

    **Reglas SRI:**
    - No se puede emitir sobre Consumidor Final (tipo_id=07).
    """
    establecimiento:         str                            = Field("001", min_length=3, max_length=3, examples=["001"])
    punto_emision:           str                            = Field("001", min_length=3, max_length=3, examples=["001"])
    doc_origen_id:           Optional[str]                  = Field(None, description="UUID del comprobante autorizado en Kipu")
    doc_origen_numero:       Optional[str]                  = Field(None, description="Número de documento externo")
    doc_origen_fecha:        Optional[str]                  = Field(None, description="Fecha del documento externo (dd/mm/yyyy)")
    doc_origen_cod_doc:      Optional[str]                  = Field("01", description="Código SRI del documento origen")
    cliente_origen:          Optional[ClienteOrigenManual]  = Field(None, description="Requerido si el documento origen es externo")
    motivos:                 List[MotivoNDB]                = Field(..., min_length=1, description="Razones del cargo adicional")
    impuestos:               Optional[List[dict]]           = Field(None, description="Impuestos adicionales si aplica")
    pagos:                   Optional[List[PagoDoc]]        = Field(None, description="Formas de pago")
    campos_adicionales:      Optional[List[CampoAdicional]] = None
    estado_cobro:            Optional[str]                  = Field(None, description="Estado de cobro: PAGADO (default si no se envía), PENDIENTE, PARCIAL. Si se omite, se registra como PAGADO.")
    forma_pago_cobro:        Optional[str]                  = Field(None, description="Forma de pago del cobro: EFECTIVO, TRANSFERENCIA, TARJETA, CHEQUE, OTRO")
    numero_comprobante_pago: Optional[str]                  = Field(None, description="Número de comprobante de pago (referencia bancaria, número de recibo, etc.)")
    fecha_pago:              Optional[str]                  = Field(None, description="Fecha de pago en formato YYYY-MM-DD. Si se omite y estado_cobro es PAGADO, se usa la fecha de emisión.")


class LiquidacionCompraCreate(BaseModel):
    """
    Liquidación de Compra de Bienes o Prestación de Servicios (LIQ / código SRI 03).

    Se emite cuando el vendedor/proveedor no entrega factura (personas naturales
    no obligadas a llevar contabilidad, servicios ocasionales, etc.).

    **Reglas SRI:**
    - No acepta Consumidor Final (07) ni RUC (04) como tipo de identificación del proveedor.
    - Solo cédula (05), pasaporte (06) o identificación del exterior (08).
    - El stock de los ítems se SUMA al inventario (es una compra).
    """
    establecimiento:         str                            = Field("001", min_length=3, max_length=3, examples=["001"])
    punto_emision:           str                            = Field("001", min_length=3, max_length=3, examples=["001"])
    cliente_id:              Optional[str]                  = Field(None, description="UUID del proveedor existente en Kipu")
    cliente:                 Optional[ClienteDoc]           = Field(None, description="Datos del proveedor si no existe en Kipu")
    items:                   List[ItemDoc]                  = Field(..., min_length=1, description="Bienes/servicios adquiridos")
    pagos:                   List[PagoDoc]                  = Field(..., min_length=1, description="Formas de pago al proveedor")
    campos_adicionales:      Optional[List[CampoAdicional]] = None
    estado_cobro:            Optional[str]                  = Field(None, description="Estado de cobro: PAGADO (default si no se envía), PENDIENTE, PARCIAL. Si se omite, se registra como PAGADO.")
    forma_pago_cobro:        Optional[str]                  = Field(None, description="Forma de pago del cobro: EFECTIVO, TRANSFERENCIA, TARJETA, CHEQUE, OTRO")
    numero_comprobante_pago: Optional[str]                  = Field(None, description="Número de comprobante de pago (referencia bancaria, número de recibo, etc.)")
    fecha_pago:              Optional[str]                  = Field(None, description="Fecha de pago en formato YYYY-MM-DD. Si se omite y estado_cobro es PAGADO, se usa la fecha de emisión.")


class RetencionCreate(BaseModel):
    """
    Comprobante de Retención Electrónico (RET / código SRI 07, versión 2.0).

    Se emite sobre un documento recibido (factura de proveedor) o una liquidación
    de compra emitida por el propio emisor.

    **Orígenes soportados:**
    - `doc_origen_recibido_id`: documento recibido registrado en Kipu.
    - `doc_origen_emitido_id`: liquidación de compra emitida en Kipu (tipo LIQ).
    - `doc_origen_numero` + `doc_origen_fecha`: documento externo (manual).

    **Regla:** Solo se permite una retención por documento recibido.
    """
    establecimiento:        str                            = Field("001", min_length=3, max_length=3, examples=["001"])
    punto_emision:          str                            = Field("001", min_length=3, max_length=3, examples=["001"])
    doc_origen_recibido_id: Optional[str]                  = Field(None, description="UUID del documento recibido en Kipu")
    doc_origen_emitido_id:  Optional[str]                  = Field(None, description="UUID de la liquidación de compra emitida en Kipu")
    doc_origen_numero:      Optional[str]                  = Field(None, description="Número del documento externo (ej: 001-001-000000456)")
    doc_origen_fecha:       Optional[str]                  = Field(None, description="Fecha del documento externo (dd/mm/yyyy)")
    doc_origen_cod_doc:     Optional[str]                  = Field("01", description="Código SRI del documento sustento (01=Factura, 03=Liquidación)")
    proveedor_origen:       Optional[ClienteOrigenManual]  = Field(None, description="Datos del proveedor si es documento externo")
    periodo_fiscal:         str                            = Field(..., description="Período fiscal de la retención (MM/YYYY)", examples=["10/2026"])
    impuestos_ret:          List[ImpuestoRET]              = Field(..., min_length=1, description="Impuestos retenidos (mínimo 1 línea)")
    campos_adicionales:     Optional[List[CampoAdicional]] = None


# =============================================================================
# SCHEMA MULTIUSO / LEGACY (MANTENIDO PARA /emit)
# =============================================================================

class DocumentoCreate(BaseModel):
    """Schema unificado legacy para compatibilidad con POST /emit. Usa las rutas específicas en su lugar."""
    tipo_doc:                Optional[str]                  = Field("FAC", examples=["FAC"])
    establecimiento:         str                            = Field("001", examples=["001"])
    punto_emision:           str                            = Field("001", examples=["001"])
    cliente_id:              Optional[str]                  = None
    cliente:                 Optional[ClienteDoc]           = None
    items:                   Optional[List[ItemDoc]]        = None
    pagos:                   Optional[List[PagoDoc]]        = None
    propina:                 Optional[float]                = 0
    doc_origen_id:           Optional[str]                  = None
    motivo:                  Optional[str]                  = None
    doc_origen_numero:       Optional[str]                  = None
    doc_origen_fecha:        Optional[str]                  = None
    doc_origen_cod_doc:      Optional[str]                  = None
    cliente_origen:          Optional[ClienteOrigenManual]  = None
    motivos:                 Optional[List[MotivoNDB]]      = None
    impuestos:               Optional[List[dict]]           = None
    doc_origen_recibido_id:  Optional[str]                  = None
    impuestos_ret:           Optional[List[ImpuestoRET]]    = None
    periodo_fiscal:          Optional[str]                  = None
    campos_adicionales:      Optional[List[CampoAdicional]] = None
    origen:                  Optional[str]                  = "web"
    estado_cobro:            Optional[str]                  = None
    forma_pago_cobro:        Optional[str]                  = None
    numero_comprobante_pago: Optional[str]                  = None
    fecha_pago:              Optional[str]                  = None


# =============================================================================
# SCHEMA DE SALIDA (CONSULTA)
# =============================================================================

class DocumentoEmitidoSchema(BaseModel):
    """Documento emitido consultado desde la base de datos."""
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