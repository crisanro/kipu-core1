# app/models/all_models.py
#
# Modelos SQLAlchemy para Kipu — arquitectura de documentos unificada.
# Aislamiento lógico por emisor_id. Schema: public.
# Datos específicos de cada tipo de documento van en JSONB (datos).
# Solo se desnormalizan campos necesarios para queries/listados sin parsear JSONB.

from sqlalchemy import (
    Column, String, Integer, SmallInteger, Boolean, Text,
    Date, Numeric, ForeignKey, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMP
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func
import uuid

Base = declarative_base()

# =============================================================================
# TABLAS GLOBALES
# =============================================================================

class SujetoGlobal(Base):
    """
    Catálogo global de personas/empresas identificadas en Ecuador.
    Compartido entre todos los emisores.
    """
    __tablename__ = "sujetos_global"

    id                      = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tipo_identificacion_sri = Column(String(2), nullable=False)     # 04=RUC 05=CEDULA 06=PASAPORTE
    identificacion          = Column(String(20), nullable=False, unique=True)
    codigo_pais             = Column(String(3), nullable=False, default="EC")
    razon_social            = Column(Text, nullable=False)
    ultima_sincronizacion   = Column(TIMESTAMP(timezone=True), server_default=func.now())

    clientes                = relationship("ClienteEmisor", back_populates="sujeto_global")


class Emisor(Base):
    """
    Clientes de Kipu. Entidad raíz.
    tipo_emisor: NATURAL | JURIDICO
    """
    __tablename__ = "emisores"

    id                      = Column(Integer, primary_key=True, autoincrement=True)
    ruc                     = Column(String(13), unique=True, nullable=False)
    razon_social            = Column(Text, nullable=False)
    nombre_comercial        = Column(Text)
    direccion_matriz        = Column(Text, nullable=False)
    tipo_emisor = Column(String(10), nullable=False, server_default="NATURAL")
    contribuyente_especial  = Column(String(13))
    obligado_contabilidad   = Column(String(2), default="NO")
    ambiente                = Column(SmallInteger, default=1)       # 1=Pruebas 2=Producción
    p12_path                = Column(Text)
    p12_pass                = Column(Text)                          # Encriptado con ENCRYPTION_KEY
    p12_expiration          = Column(Date)
    stripe_customer_id      = Column(String(50), nullable=True)
    created_at              = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at              = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    subscription            = relationship("Subscription", back_populates="emisor", uselist=False)
    credits                 = relationship("UserCredits", back_populates="emisor", uselist=False)
    credit_transactions     = relationship("CreditTransaction", back_populates="emisor")
    api_keys                = relationship("ApiKey", back_populates="emisor")
    establecimientos        = relationship("Establecimiento", back_populates="emisor")
    usuarios                = relationship("EmisorUsuario", back_populates="emisor")
    catalogo_items          = relationship("CatalogoItem", back_populates="emisor")
    clientes                = relationship("ClienteEmisor", back_populates="emisor")
    documentos_emitidos     = relationship("DocumentoEmitido", back_populates="emisor")
    documentos_recibidos    = relationship("DocumentoRecibido", back_populates="emisor")
    cuentas_movimientos = relationship("CuentaMovimiento")
    declaraciones           = relationship("DeclaracionSRI", back_populates="emisor")
    reportes_tributarios = relationship("ReporteTributario", back_populates="emisor")
    notificaciones = relationship("Notificacion", back_populates="emisor")
    proformas = relationship("Proforma")
    audit_logs = relationship("AuditLog", foreign_keys="AuditLog.emisor_id", backref="emisor_audit")



class Profile(Base):
    """Usuarios del sistema. Vinculan Firebase Auth con Kipu."""
    __tablename__ = "profiles"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    firebase_uid    = Column(Text, unique=True, nullable=False)
    email           = Column(Text, unique=True, nullable=False)
    full_name       = Column(Text)
    role            = Column(String(20), default="admin")
    whatsapp_number = Column(String(20))
    created_at      = Column(TIMESTAMP(timezone=True), server_default=func.now())

    emisores        = relationship("EmisorUsuario", back_populates="profile")
    audit_logs = relationship("AuditLog", foreign_keys="AuditLog.profile_id", backref="profile_audit")


class EmisorUsuario(Base):
    """Relación muchos a muchos entre usuarios y emisores."""
    __tablename__ = "emisor_usuarios"
    __table_args__ = (
        UniqueConstraint("emisor_id", "profile_id", name="uq_emisor_profile"),
    )
    id          = Column(Integer, primary_key=True, autoincrement=True)
    emisor_id   = Column(Integer, ForeignKey("emisores.id", ondelete="CASCADE"), nullable=False)
    profile_id  = Column(UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    rol         = Column(String(20), default="emisor")              # admin | contador | emisor
    permisos = Column(JSONB, nullable=False, server_default='{"emitir": true, "descargar": true, "clientes": true, "productos": true, "declaraciones": false, "reportes": false}')
    created_at  = Column(TIMESTAMP(timezone=True), server_default=func.now())
    emisor      = relationship("Emisor", back_populates="usuarios")
    profile     = relationship("Profile", back_populates="emisores")

# =============================================================================
# BILLING
# =============================================================================

class Subscription(Base):
    """
    Suscripción activa del emisor.
    plan:    NATURAL | JURIDICO
    periodo: MENSUAL | ANUAL
    estado:  TRIAL | ACTIVO | CANCELADO | VENCIDO
    Un emisor tiene máximo una suscripción a la vez.
    """
    __tablename__ = "subscriptions"

    id                      = Column(Integer, primary_key=True, autoincrement=True)
    emisor_id               = Column(Integer, ForeignKey("emisores.id", ondelete="CASCADE"), nullable=False, unique=True)
    plan                    = Column(String(20), nullable=False)             # NATURAL | JURIDICO
    periodo                 = Column(String(10), nullable=False)             # MENSUAL | ANUAL
    api_limit_mensual       = Column(Integer, nullable=True, default=200)
    estado                  = Column(String(20), nullable=False, default="TRIAL")
    stripe_subscription_id  = Column(String(50), unique=True, nullable=True)
    stripe_price_id         = Column(String(50), nullable=True)
    current_period_start    = Column(TIMESTAMP(timezone=True), nullable=True)
    current_period_end      = Column(TIMESTAMP(timezone=True), nullable=True)
    trial_end               = Column(TIMESTAMP(timezone=True), nullable=True)
    cancel_at_period_end    = Column(Boolean, default=False)
    created_at              = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at              = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    emisor                  = relationship("Emisor", back_populates="subscription")


class UserCredits(Base):
    """
    Créditos exclusivos para consumo de la API REST externa.
    Los suscriptores usan el sistema sin créditos — esto es solo para API.
    """
    __tablename__ = "user_credits"

    emisor_id       = Column(Integer, ForeignKey("emisores.id", ondelete="CASCADE"), primary_key=True)
    balance         = Column(Integer, nullable=False, default=0)
    last_updated    = Column(TIMESTAMP(timezone=True), server_default=func.now())

    emisor          = relationship("Emisor", back_populates="credits")


class CreditTransaction(Base):
    """
    Historial de movimientos de créditos API.
    tipo: COMPRA | USO | BONO | REEMBOLSO | REFERIDO
    """
    __tablename__ = "credit_transactions"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    emisor_id       = Column(Integer, ForeignKey("emisores.id", ondelete="CASCADE"), nullable=False)
    tipo            = Column(String(25), nullable=False)
    cantidad        = Column(Integer, nullable=False)                # positivo=entrada negativo=salida
    precio_total    = Column(Numeric(10, 2), default=0.00)
    metodo_pago     = Column(String(30))
    referencia_pago = Column(String(100))
    notas           = Column(Text)
    created_at      = Column(TIMESTAMP(timezone=True), server_default=func.now())

    emisor          = relationship("Emisor", back_populates="credit_transactions")


class PlanesCreditos(Base):
    """
    Paquetes de créditos API disponibles para compra.
    Separado del modelo de suscripción — solo para API externa.
    """
    __tablename__ = "planes_creditos"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    nombre      = Column(String(100), nullable=False)
    descripcion = Column(Text)
    cantidad    = Column(Integer, nullable=False)                    # créditos que otorga
    precio      = Column(Numeric(10, 2), nullable=False)            # USD sin IVA
    activo      = Column(Boolean, default=True)
    created_at  = Column(TIMESTAMP(timezone=True), server_default=func.now())


class Referido(Base):
    """
    Sistema de referidos.
    $3 por mensual / $10 por anual, liberado a los 30 días.
    estado: PENDIENTE | LIBERADO | PAGADO | ANULADO
    """
    __tablename__ = "referidos"

    id                  = Column(Integer, primary_key=True, autoincrement=True)
    referidor_emisor_id = Column(Integer, ForeignKey("emisores.id", ondelete="SET NULL"), nullable=True)
    referido_emisor_id  = Column(Integer, ForeignKey("emisores.id", ondelete="SET NULL"), nullable=True, unique=True)
    plan_contratado     = Column(String(10))                        # MENSUAL | ANUAL
    comision            = Column(Numeric(8, 2), nullable=False)     # 3.00 | 10.00
    estado              = Column(String(20), default="PENDIENTE")
    fecha_liberacion    = Column(TIMESTAMP(timezone=True))          # 30 días después del pago
    fecha_pago          = Column(TIMESTAMP(timezone=True))
    created_at          = Column(TIMESTAMP(timezone=True), server_default=func.now())


# =============================================================================
# API KEYS Y WEBHOOKS
# =============================================================================
class ApiKey(Base):
    """API Keys para integraciones externas. Siempre consume créditos."""
    __tablename__ = "api_keys"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    emisor_id       = Column(Integer, ForeignKey("emisores.id", ondelete="CASCADE"), nullable=False)
    nombre          = Column(String(100), nullable=False)
    key_prefix      = Column(String(10), nullable=False)
    key_hash        = Column(String(64), unique=True, nullable=False)
    key_plain       = Column(Text, nullable=True)   # ← agregar — solo para sandbox
    revoked         = Column(Boolean, default=False)
    es_sandbox      = Column(Boolean, default=False, nullable=False)
    expires_at      = Column(TIMESTAMP(timezone=True), nullable=True)
    last_used_at    = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at      = Column(TIMESTAMP(timezone=True), server_default=func.now())

    emisor          = relationship("Emisor", back_populates="api_keys")
    webhooks        = relationship("Webhook", back_populates="api_key")

class Webhook(Base):
    """Endpoints para notificar eventos a sistemas externos."""
    __tablename__ = "webhooks"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    emisor_id   = Column(Integer, ForeignKey("emisores.id", ondelete="CASCADE"), nullable=False)
    api_key_id  = Column(Integer, ForeignKey("api_keys.id", ondelete="CASCADE"), nullable=True)
    url         = Column(Text, nullable=False)
    secret      = Column(Text)
    eventos     = Column(JSONB, default=["documento.autorizado", "documento.rechazado"])
    activo      = Column(Boolean, default=True)
    created_at  = Column(TIMESTAMP(timezone=True), server_default=func.now())

    emisor      = relationship("Emisor")
    api_key     = relationship("ApiKey", back_populates="webhooks")

class Notificacion(Base):
    """Notificaciones internas por emisor."""
    __tablename__ = "notificaciones"
    id          = Column(Integer, primary_key=True, autoincrement=True)
    emisor_id   = Column(Integer, ForeignKey("emisores.id", ondelete="CASCADE"), nullable=False)
    tipo        = Column(String(50), nullable=False, default="SISTEMA")
    titulo      = Column(String(255), nullable=False)
    mensaje     = Column(Text, nullable=False)
    referencia  = Column(String(255))
    leida       = Column(Boolean, default=False)
    created_at  = Column(TIMESTAMP(timezone=True), server_default=func.now())
    emisor = relationship("Emisor", back_populates="notificaciones")


class FCMToken(Base):
    """Tokens de Firebase Cloud Messaging para notificaciones push."""
    __tablename__ = "fcm_tokens"
    __table_args__ = (
        UniqueConstraint("profile_id", "emisor_id", "device_id", name="uq_fcm_profile_emisor_device"),
    )
    id         = Column(Integer, primary_key=True, autoincrement=True)
    profile_id = Column(UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    emisor_id  = Column(Integer, ForeignKey("emisores.id", ondelete="CASCADE"), nullable=False)
    token      = Column(Text, nullable=False)
    device_id  = Column(String(100), nullable=False, server_default="default")
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())


# =============================================================================
# ESTRUCTURA OPERATIVA
# =============================================================================

class Establecimiento(Base):
    """Sucursales del emisor."""
    __tablename__ = "establecimientos"
    __table_args__ = (
        UniqueConstraint("emisor_id", "codigo", name="uq_estab_emisor_codigo"),
    )

    id                  = Column(Integer, primary_key=True, autoincrement=True)
    emisor_id           = Column(Integer, ForeignKey("emisores.id", ondelete="CASCADE"), nullable=False)
    codigo              = Column(String(3), nullable=False)
    nombre_comercial    = Column(Text)
    direccion           = Column(Text, nullable=False)
    is_active           = Column(Boolean, default=True)

    emisor              = relationship("Emisor", back_populates="establecimientos")
    puntos_emision      = relationship("PuntoEmision", back_populates="establecimiento")


class PuntoEmision(Base):
    """Puntos de emisión por establecimiento."""
    __tablename__ = "puntos_emision"
    __table_args__ = (
        UniqueConstraint("establecimiento_id", "codigo", name="uq_pe_estab_codigo"),
    )
    id                 = Column(Integer, primary_key=True, autoincrement=True)
    establecimiento_id = Column(Integer, ForeignKey("establecimientos.id", ondelete="CASCADE"), nullable=False)
    emisor_id          = Column(Integer, ForeignKey("emisores.id", ondelete="CASCADE"), nullable=False)
    codigo             = Column(String(3), nullable=False)
    secuencial_actual  = Column(Integer, default=1)  # ← mantener por compatibilidad, ya no se usa
    secuenciales       = Column(JSONB, nullable=False, server_default='{"FAC":0,"LIQ":0,"NCR":0,"NDB":0,"RET":0}')
    nombre             = Column(Text)
    is_active          = Column(Boolean, default=True)
    establecimiento    = relationship("Establecimiento", back_populates="puntos_emision")
    documentos         = relationship("DocumentoEmitido", back_populates="punto_emision")


class CatalogoItem(Base):
    """Productos y servicios del emisor."""
    __tablename__ = "catalogo_items"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    emisor_id   = Column(Integer, ForeignKey("emisores.id", ondelete="CASCADE"), nullable=False)
    codigo      = Column(String(50))
    descripcion = Column(Text, nullable=False)
    precio      = Column(Numeric(12, 2), nullable=False)
    tipo_iva    = Column(String(10), default="15")
    unidad      = Column(String(20), default="UNIDAD")
    stock       = Column(Integer, default=-1)                       # -1=sin control
    activo      = Column(Boolean, default=True)
    created_at  = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at  = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    emisor      = relationship("Emisor", back_populates="catalogo_items")


class ClienteEmisor(Base):
    """
    Catálogo vivo de compradores del emisor.
    El snapshot al momento de emisión vive en DocumentoEmitido.datos JSONB.
    Esta tabla es para historial, autocompletar y stats.
    """
    __tablename__ = "clientes_emisor"
    __table_args__ = (
        UniqueConstraint("emisor_id", "identificacion", name="uq_cliente_emisor_id"),
    )

    id                      = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    emisor_id               = Column(Integer, ForeignKey("emisores.id", ondelete="CASCADE"), nullable=False)
    sujeto_global_id        = Column(UUID(as_uuid=True), ForeignKey("sujetos_global.id", ondelete="SET NULL"), nullable=True)
    tipo_identificacion_sri = Column(String(2))
    identificacion          = Column(String(20))
    razon_social            = Column(Text)
    email                   = Column(String(150))
    telefono                = Column(String(20))
    direccion               = Column(Text)
    created_at              = Column(TIMESTAMP(timezone=True), server_default=func.now())

    sujeto_global           = relationship("SujetoGlobal", back_populates="clientes")
    emisor                  = relationship("Emisor", back_populates="clientes")
    documentos_emitidos     = relationship("DocumentoEmitido", back_populates="cliente")
    cuentas = relationship("CuentaMovimiento", back_populates="cliente")


# =============================================================================
# DOCUMENTOS EMITIDOS
# =============================================================================

class DocumentoEmitido(Base):
    """
    Todos los comprobantes electrónicos emitidos al SRI.

    tipo_doc / cod_doc:
        FAC → 01  Factura
        LIQ → 03  Liquidación de compra
        NCR → 04  Nota de crédito
        NDB → 05  Nota de débito
        RET → 07  Retención

    estado_sri:   PENDIENTE | FIRMADO | RECIBIDA | AUTORIZADO | DEVUELTA | RECHAZADO
    estado_cobro: PENDIENTE | PAGADO | PARCIAL | ANULADO  (solo FAC y LIQ)

    Referencias entre documentos:
        NCR/NDB desde FAC propia:    doc_origen_emitido_id  → documentos_emitidos.id
        RET desde FAC recibida:      doc_origen_recibido_id → documentos_recibidos.id

    datos JSONB según tipo_doc:
        FAC/LIQ: { infoTributaria, infoFactura, detalles[], pagos[], resumenImpuestos }
        NCR:     { infoTributaria, infoNotaCredito, detalles[], resumenImpuestos }
        NDB:     { infoTributaria, infoNotaDebito, motivos[], resumenImpuestos }
        RET:     { infoTributaria, infoRetencion, impuestos[] }
    """
    __tablename__ = "documentos_emitidos"

    id                      = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    emisor_id               = Column(Integer, ForeignKey("emisores.id"), nullable=False)
    email_comprador = Column(String(150), nullable=True)
    punto_emision_id        = Column(Integer, ForeignKey("puntos_emision.id"), nullable=True)
    cliente_id              = Column(UUID(as_uuid=True), ForeignKey("clientes_emisor.id", ondelete="SET NULL"), nullable=True)
    api_key_id  = Column(Integer, ForeignKey("api_keys.id", ondelete="SET NULL"), nullable=True)
    created_by  = Column(UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)  # ← agregar

    # Tipo e identificación SRI
    tipo_doc                = Column(String(5), nullable=False)     # FAC | LIQ | NCR | NDB | RET
    cod_doc                 = Column(String(2), nullable=False)     # 01 | 03 | 04 | 05 | 07
    clave_acceso            = Column(String(49), unique=True)
    numero_doc              = Column(String(17))                    # 001-001-000000001
    secuencial              = Column(String(9))
    fecha_emision           = Column(Date, server_default=func.current_date())
    es_sandbox              = Column(Boolean, default=False, nullable=False)

    # Estado SRI
    estado_sri              = Column(String(20), default="PENDIENTE")
    mensajes_sri            = Column(JSONB)
    fecha_envio_sri         = Column(TIMESTAMP(timezone=True))
    fecha_autorizacion      = Column(TIMESTAMP(timezone=True))
    fecha_anulacion         = Column(TIMESTAMP(timezone=True), nullable=True)   # ← añadir
    motivo_anulacion        = Column(String(100), nullable=True)             
    retry_count             = Column(Integer, default=0)
    last_retry              = Column(TIMESTAMP(timezone=True))

    # Estado de cobro — solo FAC y LIQ
    estado_cobro            = Column(String(20), nullable=True)     # PENDIENTE | PAGADO | PARCIAL | ANULADO
    forma_pago_cobro        = Column(String(30), nullable=True)     # EFECTIVO | TRANSFERENCIA | CHEQUE | TARJETA | OTRO
    numero_comprobante_pago = Column(String(100), nullable=True)
    fecha_pago              = Column(Date, nullable=True)

    # Total desnormalizado para queries rápidas
    importe_total           = Column(Numeric(12, 2), nullable=False)

    # Datos completos del comprobante
    datos                   = Column(JSONB, nullable=False)

    # Almacenamiento R2
    xml_path                = Column(Text)
    pdf_path                = Column(Text)

    # Origen
    origen                  = Column(String(20), default="web")     # web | api | komand | wappti

    # Referencias entre documentos
    doc_origen_emitido_id   = Column(UUID(as_uuid=True), ForeignKey("documentos_emitidos.id", ondelete="SET NULL"), nullable=True)
    doc_origen_recibido_id  = Column(UUID(as_uuid=True), ForeignKey("documentos_recibidos.id", ondelete="SET NULL"), nullable=True)

    created_at              = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at              = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relaciones
    emisor                  = relationship("Emisor", back_populates="documentos_emitidos")
    punto_emision           = relationship("PuntoEmision", back_populates="documentos")
    cliente                 = relationship("ClienteEmisor", back_populates="documentos_emitidos")
    api_key                 = relationship("ApiKey")
    doc_origen_emitido      = relationship("DocumentoEmitido", remote_side="DocumentoEmitido.id", foreign_keys=[doc_origen_emitido_id])
    doc_origen_recibido     = relationship("DocumentoRecibido", back_populates="retencion_emitida", foreign_keys=[doc_origen_recibido_id])
    documentos_derivados    = relationship("DocumentoEmitido", foreign_keys=[doc_origen_emitido_id])


# =============================================================================
# PROFORMAS
# =============================================================================
class Proforma(Base):
    """
    Proformas comerciales — no son comprobantes SRI.
    El número se genera en el service: PRO-2026-000000001
    estado: VIGENTE | FACTURADA
    Si fecha_validez < hoy y estado = VIGENTE → vencida en la UI (no en DB)
    """
    __tablename__ = "proformas"

    id                   = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    emisor_id            = Column(Integer, ForeignKey("emisores.id", ondelete="CASCADE"), nullable=False)
    cliente_id           = Column(UUID(as_uuid=True), ForeignKey("clientes_emisor.id", ondelete="SET NULL"), nullable=True)
    numero               = Column(String(20), nullable=False)
    fecha_emision        = Column(Date, nullable=False, server_default=func.current_date())
    fecha_validez        = Column(Date, nullable=True)
    items                = Column(JSONB, nullable=False, server_default="[]")
    subtotal             = Column(Numeric(12, 2), nullable=False, default=0)
    total_iva            = Column(Numeric(12, 2), nullable=False, default=0)
    total                = Column(Numeric(12, 2), nullable=False, default=0)
    notas                = Column(Text, nullable=True)
    estado               = Column(String(10), nullable=False, default="VIGENTE")
    documento_emitido_id = Column(UUID(as_uuid=True), ForeignKey("documentos_emitidos.id", ondelete="SET NULL"), nullable=True)
    created_at           = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at           = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("emisor_id", "numero", name="uq_proforma_emisor_numero"),
    )

    # Relaciones
    emisor            = relationship("Emisor")
    cliente           = relationship("ClienteEmisor")
    documento_emitido = relationship("DocumentoEmitido", foreign_keys=[documento_emitido_id])


# =============================================================================
# DOCUMENTOS RECIBIDOS
# =============================================================================
class DocumentoRecibido(Base):
    """
    Comprobantes recibidos de proveedores.
    tipo_doc: FAC | LIQ | NCR | NDB | RET
    estado_pago: PENDIENTE | PAGADO | PARCIAL | ANULADO
    fuente: MANUAL | XML | API
    Vínculos:
    - doc_origen_recibido_id: NCR/NDB recibida → FAC/LIQ recibida que modifica
    - doc_origen_emitido_id:  RET recibida → FAC/LIQ que nosotros emitimos
    """
    __tablename__ = "documentos_recibidos"

    id                      = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    emisor_id               = Column(Integer, ForeignKey("emisores.id", ondelete="CASCADE"), nullable=False)

    # ── Proveedor desnormalizado ───────────────────────────────────────────────
    ruc_proveedor           = Column(String(13), nullable=False)
    razon_social_proveedor  = Column(Text,       nullable=False)

    # ── Identificación del comprobante ────────────────────────────────────────
    tipo_doc                = Column(String(5),  nullable=False)   # FAC | LIQ | NCR | NDB | RET
    cod_doc                 = Column(String(2),  nullable=False)   # 01 | 03 | 04 | 05 | 07
    clave_acceso            = Column(String(49), unique=True)
    numero_doc              = Column(String(17))
    fecha_emision           = Column(Date,                nullable=False)
    fecha_autorizacion      = Column(TIMESTAMP(timezone=True))     # Fecha de autorización SRI

    # ── Totales desnormalizados ────────────────────────────────────────────────
    # Guardamos los tres para evitar tocar JSONB en queries de resumen
    subtotal_base           = Column(Numeric(12, 2), nullable=False, default=0)  # Base sin IVA
    valor_iva_total         = Column(Numeric(12, 2), nullable=False, default=0)  # IVA total
    importe_total           = Column(Numeric(12, 2), nullable=False)             # Total con IVA

    # ── Vínculos entre documentos ─────────────────────────────────────────────
    # NCR/NDB recibida → FAC/LIQ recibida que modifica
    doc_origen_recibido_id  = Column(
        UUID(as_uuid=True),
        ForeignKey("documentos_recibidos.id", ondelete="SET NULL"),
        nullable=True,
    )
    # RET recibida → FAC/LIQ que nosotros emitimos (nos retuvieron)
    doc_origen_emitido_id   = Column(
        UUID(as_uuid=True),
        ForeignKey("documentos_emitidos.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ── Clasificación fiscal ──────────────────────────────────────────────────
    # Flags globales — índice rápido para filtros y resumen del listado
    # El detalle exacto por línea está en items_detalle
    deducible_renta         = Column(Boolean, nullable=False, default=True)
    credito_tributario_iva  = Column(Boolean, nullable=False, default=False)
    notas                   = Column(String(128))                  # Máx 128 chars

    # ── Ítems con clasificación fiscal por línea ──────────────────────────────
    # [{"descripcion":"...","cantidad":1,"precio_unitario":100,"subtotal":100,
    #   "tarifa_iva":15,"valor_iva":15,"total":115,
    #   "deducible_renta":true,"credito_tributario_iva":true}]
    items_detalle           = Column(JSONB)

    # ── Estado de pago al proveedor ───────────────────────────────────────────
    estado_pago             = Column(String(20), nullable=True, default="PENDIENTE")
    forma_pago              = Column(String(30), nullable=True)
    numero_comprobante_pago = Column(String(100), nullable=True)
    fecha_pago              = Column(Date, nullable=True)

    # ── Almacenamiento ────────────────────────────────────────────────────────
    datos                   = Column(JSONB)   # Datos completos del XML limpio
    xml_path                = Column(Text)    # Path en R2

    # ── Metadata ─────────────────────────────────────────────────────────────
    fuente                  = Column(String(10), nullable=False, default="MANUAL")  # MANUAL | XML | API
    created_at              = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at              = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    # ── Relaciones ────────────────────────────────────────────────────────────
    emisor                  = relationship("Emisor", back_populates="documentos_recibidos")

    doc_origen_recibido     = relationship(
                                "DocumentoRecibido",
                                foreign_keys=[doc_origen_recibido_id],
                                remote_side="DocumentoRecibido.id",
                                backref="documentos_derivados_recibidos",
                              )
    doc_origen_emitido      = relationship(
                                "DocumentoEmitido",
                                foreign_keys=[doc_origen_emitido_id],
                                backref="retenciones_recibidas",
                              )
    retencion_emitida       = relationship(
                                "DocumentoEmitido",
                                back_populates="doc_origen_recibido",
                                foreign_keys="DocumentoEmitido.doc_origen_recibido_id",
                              )


# =============================================================================
# CUENTAS POR COBRAR / PAGAR
# =============================================================================
class CuentaMovimiento(Base):
    """
    Cuentas por cobrar y por pagar del emisor.
    tipo: COBRAR | PAGAR
    estado: PENDIENTE | PARCIAL | PAGADO | ANULADO
    El cliente debe estar registrado en clientes_emisor (llamado "Personas" en la UI).
    monto_pagado se recalcula automáticamente al registrar abonos.
    """
    __tablename__ = "cuentas_movimientos"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    emisor_id       = Column(Integer, ForeignKey("emisores.id", ondelete="CASCADE"), nullable=False)
    cliente_id      = Column(UUID(as_uuid=True), ForeignKey("clientes_emisor.id", ondelete="RESTRICT"), nullable=False)
    tipo            = Column(String(6), nullable=False)             # COBRAR | PAGAR
    concepto        = Column(Text, nullable=False)
    monto_total     = Column(Numeric(12, 2), nullable=False)
    monto_pagado    = Column(Numeric(12, 2), nullable=False, default=0)
    fecha_emision   = Column(Date, nullable=False, server_default=func.current_date())
    fecha_vencimiento = Column(Date, nullable=True)
    estado          = Column(String(10), nullable=False, default="PENDIENTE")  # PENDIENTE | PARCIAL | PAGADO | ANULADO
    documento_emitido_id  = Column(UUID(as_uuid=True), ForeignKey("documentos_emitidos.id",  ondelete="SET NULL"), nullable=True)
    documento_recibido_id = Column(UUID(as_uuid=True), ForeignKey("documentos_recibidos.id", ondelete="SET NULL"), nullable=True)
    notas           = Column(Text, nullable=True)
    created_at      = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at      = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relaciones
    emisor          = relationship("Emisor")
    cliente         = relationship("ClienteEmisor", back_populates="cuentas")
    abonos          = relationship("CuentaAbono", back_populates="cuenta", cascade="all, delete-orphan")
    documento_emitido  = relationship("DocumentoEmitido",  foreign_keys=[documento_emitido_id])
    documento_recibido = relationship("DocumentoRecibido", foreign_keys=[documento_recibido_id])


class CuentaAbono(Base):
    """
    Abonos/pagos parciales o totales a una cuenta.
    Al registrar un abono el service recalcula monto_pagado y estado en CuentaMovimiento.
    """
    __tablename__ = "cuentas_abonos"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cuenta_id   = Column(UUID(as_uuid=True), ForeignKey("cuentas_movimientos.id", ondelete="CASCADE"), nullable=False)
    monto       = Column(Numeric(12, 2), nullable=False)
    fecha       = Column(Date, nullable=False, server_default=func.current_date())
    forma_pago  = Column(String(30), nullable=True)   # EFECTIVO | TRANSFERENCIA | CHEQUE | TARJETA | OTRO
    notas       = Column(Text, nullable=True)
    created_at  = Column(TIMESTAMP(timezone=True), server_default=func.now())

    # Relaciones
    cuenta      = relationship("CuentaMovimiento", back_populates="abonos")


# =============================================================================
# DECLARACIONES SRI
# =============================================================================

class DeclaracionSRI(Base):
    """
    Control de declaraciones tributarias por período.

    tipo:    104 (IVA mensual) | 102 (Renta anual) | ATS (Anexo Transaccional)
    periodo: primer día del mes/año declarado

    totales JSONB — cifras precalculadas del período para preparar la declaración:
    {
        "ventas_gravadas": 0,
        "ventas_0": 0,
        "iva_cobrado": 0,
        "compras_deducibles": 0,
        "credito_tributario": 0,
        "retenciones_recibidas": 0,
        "iva_a_pagar": 0,
        "saldo_a_favor": 0
    }
    """
    __tablename__ = "declaraciones_sri"
    __table_args__ = (
        UniqueConstraint("emisor_id", "tipo", "periodo", name="uq_declaracion_emisor_tipo_periodo"),
    )

    id              = Column(Integer, primary_key=True, autoincrement=True)
    emisor_id       = Column(Integer, ForeignKey("emisores.id", ondelete="CASCADE"), nullable=False)
    tipo            = Column(String(10), nullable=False)            # 104 | 102 | ATS
    periodo         = Column(Date, nullable=False)                  # primer día del mes
    vencimiento     = Column(Date, nullable=False)                  # guardado al crear, no recalcular
    declarado       = Column(Boolean, default=False)
    fecha_declarado = Column(TIMESTAMP(timezone=True))
    declarado_por   = Column(UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)
    totales         = Column(JSONB)                                 # cifras precalculadas
    created_at      = Column(TIMESTAMP(timezone=True), server_default=func.now())

    emisor          = relationship("Emisor", back_populates="declaraciones")


# =============================================================================
# AUDITORÍA Y CONTROL
# =============================================================================

class AuthChallenge(Base):
    """Desafíos OTP para login por WhatsApp o email."""
    __tablename__ = "auth_challenges"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    email           = Column(Text, nullable=False)
    whatsapp_number = Column(String(20))
    pin             = Column(String(10), nullable=False)
    tipo_accion     = Column(String(30), nullable=False)  # LOGIN | CAMBIO_EMAIL | NUKE | CREAR_TOKEN | ELIMINAR_TOKEN | ACTIVAR_PRODUCCION
    emisor_id       = Column(Integer, ForeignKey("emisores.id", ondelete="CASCADE"), nullable=True)  # ← agregar
    extra_data      = Column(JSONB)
    expires_at      = Column(TIMESTAMP(timezone=True), nullable=False)
    created_at      = Column(TIMESTAMP(timezone=True), server_default=func.now())

    
class EmailRateLimit(Base):
    """Anti-spam para envío de correos."""
    __tablename__ = "email_rate_limits"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    email       = Column(String(255), unique=True, nullable=False)
    last_sent   = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())


class TransactionLog(Base):
    """Auditoría de operaciones administrativas."""
    __tablename__ = "transaction_logs"

    id                  = Column(Integer, primary_key=True, autoincrement=True)
    target_emisor_id    = Column(Integer, ForeignKey("emisores.id", ondelete="SET NULL"), nullable=True)
    amount              = Column(Integer, nullable=False)
    action_type         = Column(String(50), nullable=False)
    description         = Column(Text)
    created_at          = Column(TIMESTAMP(timezone=True), server_default=func.now())


class LeadExUsuario(Base):
    """Ex-clientes para análisis de churn y reactivación."""
    __tablename__ = "leads_ex_usuarios"

    id                      = Column(Integer, primary_key=True, autoincrement=True)
    ruc                     = Column(String(13))
    razon_social            = Column(Text)
    email                   = Column(Text)
    full_name               = Column(Text)
    tipo_emisor             = Column(String(10))                    # NATURAL | JURIDICO
    plan_ultimo             = Column(String(20))
    motivo_salida           = Column(Text)
    total_docs_emitidos     = Column(Integer)
    total_docs_recibidos    = Column(Integer)
    fecha_registro_original = Column(TIMESTAMP)
    fecha_eliminacion       = Column(TIMESTAMP, server_default=func.now())


class AuditLog(Base):
    """
    Registro de auditoría de todas las operaciones de escritura.
    accion:  CREATE | UPDATE | DELETE | REVOKE | INVITE | ACTIVATE
    entidad: documento | cliente | producto | usuario | config | api_key | firma | suscripcion | creditos
    Solo el admin de la empresa puede ver estos logs.
    """
    __tablename__ = "audit_logs"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    emisor_id  = Column(Integer, ForeignKey("emisores.id", ondelete="SET NULL"), nullable=True)
    profile_id = Column(UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)
    accion     = Column(String(50), nullable=False)   # CREATE | UPDATE | DELETE | REVOKE | INVITE | ACTIVATE
    entidad    = Column(String(50), nullable=False)   # documento | cliente | producto | usuario | config | api_key | firma | suscripcion | creditos
    entidad_id = Column(String(100), nullable=True)   # ID del registro afectado
    detalle    = Column(JSONB, nullable=True)          # qué cambió exactamente
    ip         = Column(String(45), nullable=True)    # IP del request
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())



class ReporteTributario(Base):
    """
    Reportes fiscales generados — IVA (104) | Renta (102) | ATS.
    Una vez generado para un período cerrado, se guarda y no se recalcula.
    El período actual siempre se recalcula en tiempo real.

    tipo:         IVA | RENTA | ATS
    tipo_periodo: MENSUAL | SEMESTRAL | ANUAL
    periodo:      primer día del período — 2026-08-01 para agosto, 2026-01-01 para año

    Trazabilidad para auditoría SRI:
    - doc_emitidos_ids:   UUIDs de todos los documentos emitidos incluidos
    - doc_recibidos_ids:  UUIDs de todos los documentos recibidos incluidos

    campos_manuales_valores: valores ingresados por el usuario para casilleros
    que no se pueden calcular automáticamente (605, 606, 402, etc.).
    Columna separada del resumen calculado — sobrevive regeneraciones.
    """
    __tablename__ = "reportes_tributarios"
    __table_args__ = (
        UniqueConstraint(
            "emisor_id", "tipo", "periodo",
            name="uq_reporte_emisor_tipo_periodo"
        ),
    )

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    emisor_id       = Column(Integer, ForeignKey("emisores.id", ondelete="CASCADE"), nullable=False)

    # Tipo y período
    tipo            = Column(String(10), nullable=False)   # IVA | RENTA | ATS
    tipo_periodo    = Column(String(10), nullable=False)   # MENSUAL | SEMESTRAL | ANUAL
    periodo         = Column(Date, nullable=False)          # 2026-08-01

    # Datos calculados por el backend — se sobreescriben al regenerar
    casilleros      = Column(JSONB, nullable=False, server_default='{}')
    preguntas       = Column(JSONB, nullable=False, server_default='{}')
    desglose        = Column(JSONB, nullable=False, server_default='{}')
    resumen         = Column(JSONB, nullable=False, server_default='{}')

    # Ingresado por el usuario — sobrevive regeneraciones
    campos_manuales_valores = Column(JSONB, nullable=False, server_default='{}')
    # Ejemplo: {"605": 150.00, "606": 0.00, "402": 500.00}

    # Trazabilidad — auditoría SRI
    doc_emitidos_ids    = Column(JSONB, nullable=False, server_default='[]')
    doc_recibidos_ids   = Column(JSONB, nullable=False, server_default='[]')
    total_doc_emitidos  = Column(Integer, nullable=False, default=0)
    total_doc_recibidos = Column(Integer, nullable=False, default=0)

    # Quién y cuándo generó
    generado_at     = Column(TIMESTAMP(timezone=True), server_default=func.now())
    generado_por    = Column(UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)

    # Regeneración — cuando el usuario fuerza recálculo
    regenerado_at   = Column(TIMESTAMP(timezone=True), nullable=True)
    regenerado_por  = Column(UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)

    # Relaciones
    emisor          = relationship("Emisor", back_populates="reportes_tributarios")