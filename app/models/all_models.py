# app/models/all_models.py
#
# Modelos SQLAlchemy para arquitectura multi-tenant de Kipu.
#
# Schemas:
#   public      → datos globales, auth, control del sistema, créditos
#   tenant_NNN  → datos de negocio por grupo de emisores (alto volumen)
#
# Nota sobre tenant models:
#   Están definidos con schema='tenant_001' como referencia.
#   En runtime, database.py setea el search_path al tenant correcto,
#   por lo que SQLAlchemy apunta automáticamente al schema del emisor.

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
# SCHEMA: public — Tablas globales y de control
# =============================================================================

class SujetoGlobal(Base):
    """
    Catálogo global de personas/empresas identificadas en Ecuador.
    Compartido entre todos los emisores — evita duplicar datos de RUC/cédula.
    """
    __tablename__ = "sujetos_global"
    __table_args__ = {"schema": "public"}

    id                      = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tipo_identificacion_sri = Column(String(2), nullable=False)     # 04=RUC 05=CEDULA 06=PASAPORTE
    identificacion          = Column(String(20), nullable=False)
    codigo_pais             = Column(String(3), nullable=False, default="EC")
    razon_social            = Column(Text, nullable=False)
    ultima_sincronizacion   = Column(TIMESTAMP(timezone=True), server_default=func.now())

    clientes                = relationship("ClienteEmisor", back_populates="sujeto_global")


class Emisor(Base):
    """
    Clientes de Kipu: emprendedores o empresas con RUC.
    Entidad raíz — casi todas las demás tablas apuntan aquí.
    """
    __tablename__ = "emisores"
    __table_args__ = {"schema": "public"}

    id                      = Column(Integer, primary_key=True, autoincrement=True)
    ruc                     = Column(String(13), unique=True, nullable=False)
    razon_social            = Column(Text, nullable=False)
    nombre_comercial        = Column(Text)
    direccion_matriz        = Column(Text, nullable=False)
    contribuyente_especial  = Column(String(13))
    obligado_contabilidad   = Column(String(2), default="NO")
    ambiente                = Column(SmallInteger, default=1)       # 1: Pruebas, 2: Producción
    p12_path                = Column(Text)                          # Path en R2
    p12_pass                = Column(Text)                          # Encriptado con ENCRYPTION_KEY
    p12_expiration          = Column(Date)
    created_at              = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at              = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    profile                 = relationship("Profile", back_populates="emisor", uselist=False)
    credits                 = relationship("UserCredits", back_populates="emisor", uselist=False)
    tenant_map              = relationship("EmisorTenantMap", back_populates="emisor", uselist=False)
    api_keys                = relationship("ApiKey", back_populates="emisor")
    credit_transactions     = relationship("CreditTransaction", back_populates="emisor")


class EmisorTenantMap(Base):
    """
    Tabla de ruteo: mapea cada emisor al schema tenant que le corresponde.
    FastAPI consulta esto en cada request para saber a qué schema apuntar.
    Se cachea en memoria (_tenant_cache en database.py) para no ir a DB en cada request.
    """
    __tablename__ = "emisor_tenant_map"
    __table_args__ = {"schema": "public"}

    emisor_id       = Column(Integer, ForeignKey("public.emisores.id", ondelete="CASCADE"), primary_key=True)
    tenant_schema   = Column(String(20), nullable=False)            # 'tenant_001', 'tenant_002'...
    created_at      = Column(TIMESTAMP(timezone=True), server_default=func.now())

    emisor          = relationship("Emisor", back_populates="tenant_map")


class Profile(Base):
    """Usuarios del sistema. Vinculan Firebase Auth con un emisor de Kipu."""
    __tablename__ = "profiles"
    __table_args__ = {"schema": "public"}

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    firebase_uid    = Column(Text, unique=True, nullable=False)
    emisor_id       = Column(Integer, ForeignKey("public.emisores.id", ondelete="SET NULL"), nullable=True)
    email           = Column(Text, unique=True, nullable=False)
    full_name       = Column(Text)
    role            = Column(String(20), default="admin")           # 'admin', 'contador', 'viewer'
    whatsapp_number = Column(String(20))
    created_at      = Column(TIMESTAMP(timezone=True), server_default=func.now())

    emisor          = relationship("Emisor", back_populates="profile")


class UserCredits(Base):
    """
    Balance de créditos del emisor — separado por tipo.

    balance_emision   → para emitir facturas electrónicas al SRI (1 crédito/factura)
    balance_recepcion → para recibir facturas de proveedores vía email automático (1 crédito/factura)
                        La subida manual de XML es gratuita.

    Al comprar créditos de emisión se bonifican automáticamente créditos de recepción (50%).
    """
    __tablename__ = "user_credits"
    __table_args__ = {"schema": "public"}

    emisor_id           = Column(Integer, ForeignKey("public.emisores.id", ondelete="CASCADE"), primary_key=True)
    balance_emision     = Column(Integer, nullable=False, default=0)
    balance_recepcion   = Column(Integer, nullable=False, default=0)
    last_updated        = Column(TIMESTAMP(timezone=True), server_default=func.now())

    emisor              = relationship("Emisor", back_populates="credits")


class CreditTransaction(Base):
    """
    Historial de todos los movimientos de créditos.

    Tipos de transacción:
      COMPRA_EMISION    → compra de créditos de emisión
      COMPRA_RECEPCION  → compra de créditos de recepción
      BONUS_RECEPCION   → créditos de recepción gratis por compra de emisión (50%)
      USO_EMISION       → factura emitida al SRI (descuenta balance_emision)
      USO_RECEPCION     → factura recibida via email (descuenta balance_recepcion)
      REEMBOLSO         → devolución por error técnico
    """
    __tablename__ = "credit_transactions"
    __table_args__ = {"schema": "public"}

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    emisor_id       = Column(Integer, ForeignKey("public.emisores.id", ondelete="CASCADE"), nullable=False)
    tipo            = Column(String(25), nullable=False)
    cantidad        = Column(Integer, nullable=False)               # positivo: entrada, negativo: salida
    precio_total    = Column(Numeric(10, 2), default=0.00)          # 0 en bonos y usos
    metodo_pago     = Column(String(30))                            # 'BINANCE', 'PICHINCHA', 'STRIPE'
    referencia_pago = Column(String(100))
    notas           = Column(Text)
    created_at      = Column(TIMESTAMP(timezone=True), server_default=func.now())

    emisor          = relationship("Emisor", back_populates="credit_transactions")


class TransactionLog(Base):
    """Auditoría de operaciones administrativas (n8n, admin panel)."""
    __tablename__ = "transaction_logs"
    __table_args__ = {"schema": "public"}

    id                  = Column(Integer, primary_key=True, autoincrement=True)
    target_emisor_id    = Column(Integer, ForeignKey("public.emisores.id", ondelete="SET NULL"), nullable=True)
    amount              = Column(Integer, nullable=False)
    action_type         = Column(String(50), nullable=False)
    description         = Column(Text)
    created_at          = Column(TIMESTAMP(timezone=True), server_default=func.now())


class ApiKey(Base):
    """API Keys para integraciones externas (ERP, POS, etc.)."""
    __tablename__ = "api_keys"
    __table_args__ = {"schema": "public"}

    id              = Column(Integer, primary_key=True, autoincrement=True)
    emisor_id       = Column(Integer, ForeignKey("public.emisores.id", ondelete="CASCADE"), nullable=False)
    nombre          = Column(String(100), nullable=False)
    key_prefix      = Column(String(10), nullable=False)            # "kp_live_" — visible al usuario
    key_hash        = Column(String(64), unique=True, nullable=False)   # SHA256 del key completo
    revoked         = Column(Boolean, default=False)
    expires_at      = Column(TIMESTAMP(timezone=True), nullable=True)
    last_used_at    = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at      = Column(TIMESTAMP(timezone=True), server_default=func.now())

    emisor          = relationship("Emisor", back_populates="api_keys")


class AuthChallenge(Base):
    """Desafíos OTP/PIN para login por WhatsApp o email."""
    __tablename__ = "auth_challenges"
    __table_args__ = {"schema": "public"}

    id              = Column(Integer, primary_key=True, autoincrement=True)
    emisor_id       = Column(Integer, ForeignKey("public.emisores.id", ondelete="CASCADE"), nullable=True)
    email           = Column(Text, nullable=False)
    whatsapp_number = Column(String(20))
    pin             = Column(String(10), nullable=False)
    tipo_accion     = Column(String(30), nullable=False)            # 'LOGIN', 'CAMBIO_EMAIL', 'NUKE'
    metadata        = Column(JSONB)
    expires_at      = Column(TIMESTAMP(timezone=True), nullable=False)
    created_at      = Column(TIMESTAMP(timezone=True), server_default=func.now())


class LeadExUsuario(Base):
    """Ex-clientes para análisis de churn y campañas de reactivación."""
    __tablename__ = "leads_ex_usuarios"
    __table_args__ = {"schema": "public"}

    id                          = Column(Integer, primary_key=True, autoincrement=True)
    ruc                         = Column(String(13))
    razon_social                = Column(Text)
    email                       = Column(Text)
    full_name                   = Column(Text)
    motivo_salida               = Column(Text)
    ultimo_balance_emision      = Column(Integer)
    ultimo_balance_recepcion    = Column(Integer)
    total_facturas_emitidas     = Column(Integer)
    total_facturas_recibidas    = Column(Integer)
    fecha_registro_original     = Column(TIMESTAMP)
    fecha_eliminacion           = Column(TIMESTAMP, server_default=func.now())


# =============================================================================
# SCHEMA: tenant_NNN — Tablas de volumen por grupo de emisores
#
# Definidos con schema='tenant_001' como referencia estática.
# En runtime, database.py setea search_path al tenant del emisor autenticado.
# SQLAlchemy resuelve las tablas sin schema explícito contra ese search_path.
# =============================================================================

class Establecimiento(Base):
    """Sucursales del emisor (establecimientos SRI: 001, 002...)."""
    __tablename__ = "establecimientos"
    __table_args__ = (
        UniqueConstraint("emisor_id", "codigo", name="uq_estab_emisor_codigo"),
        {"schema": "tenant_001"},
    )

    id                  = Column(Integer, primary_key=True, autoincrement=True)
    emisor_id           = Column(Integer, ForeignKey("public.emisores.id", ondelete="CASCADE"), nullable=False)
    codigo              = Column(String(3), nullable=False)         # SRI: '001', '002'
    nombre_comercial    = Column(Text)
    direccion           = Column(Text, nullable=False)
    is_active           = Column(Boolean, default=True)

    puntos_emision      = relationship("PuntoEmision", back_populates="establecimiento")


class PuntoEmision(Base):
    """Puntos de emisión (cajas o terminales de facturación)."""
    __tablename__ = "puntos_emision"
    __table_args__ = (
        UniqueConstraint("establecimiento_id", "codigo", name="uq_pe_estab_codigo"),
        {"schema": "tenant_001"},
    )

    id                  = Column(Integer, primary_key=True, autoincrement=True)
    establecimiento_id  = Column(Integer, ForeignKey("tenant_001.establecimientos.id", ondelete="CASCADE"), nullable=False)
    emisor_id           = Column(Integer, ForeignKey("public.emisores.id", ondelete="CASCADE"), nullable=False)
    codigo              = Column(String(3), nullable=False)         # SRI: '001', '002'
    secuencial_actual   = Column(Integer, default=1)
    nombre              = Column(Text)
    is_active           = Column(Boolean, default=True)

    establecimiento     = relationship("Establecimiento", back_populates="puntos_emision")
    invoices            = relationship("InvoiceEmitida", back_populates="punto_emision")


class ClienteEmisor(Base):
    """
    Compradores frecuentes del emisor.
    Referencia a public.sujetos_global pero con datos locales del emisor.
    Campos de identificación desnormalizados para evitar JOINs en cada factura.
    """
    __tablename__ = "clientes_emisor"
    __table_args__ = (
        UniqueConstraint("emisor_id", "identificacion", name="uq_cliente_emisor_id"),
        {"schema": "tenant_001"},
    )

    id                      = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    emisor_id               = Column(Integer, ForeignKey("public.emisores.id", ondelete="CASCADE"), nullable=False)
    sujeto_global_id        = Column(UUID(as_uuid=True), ForeignKey("public.sujetos_global.id", ondelete="SET NULL"), nullable=True)
    email                   = Column(String(150))
    telefono                = Column(String(20))
    tipo_identificacion_sri = Column(String(2))
    identificacion          = Column(String(20))
    razon_social            = Column(Text)
    direccion               = Column(Text)
    created_at              = Column(TIMESTAMP(timezone=True), server_default=func.now())

    sujeto_global           = relationship("SujetoGlobal", back_populates="clientes")
    invoices                = relationship("InvoiceEmitida", back_populates="cliente")


class InvoiceEmitida(Base):
    """
    Facturas electrónicas emitidas — comprobantes enviados al SRI.
    Ciclo de vida: PENDIENTE → ENVIADA → AUTORIZADA | RECHAZADA | ERROR
    Consume 1 crédito de balance_emision al crearse.
    """
    __tablename__ = "invoices_emitidas"
    __table_args__ = {"schema": "tenant_001"}

    id                          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    emisor_id                   = Column(Integer, ForeignKey("public.emisores.id"), nullable=False)
    punto_emision_id            = Column(Integer, ForeignKey("tenant_001.puntos_emision.id"), nullable=False)
    cliente_emisor_id           = Column(UUID(as_uuid=True), ForeignKey("tenant_001.clientes_emisor.id", ondelete="SET NULL"), nullable=True)
    clave_acceso                = Column(String(49), unique=True)
    secuencial                  = Column(String(9), nullable=False)
    numero_factura              = Column(String(17))                # calculado: 001-001-000000001
    fecha_emision               = Column(Date, server_default=func.current_date())
    estado                      = Column(String(20), default="PENDIENTE")
    identificacion_comprador    = Column(String(20), nullable=False)
    razon_social_comprador      = Column(Text, nullable=False)
    email_comprador             = Column(String(150))
    importe_total               = Column(Numeric(12, 2), nullable=False)
    subtotal_iva                = Column(Numeric(12, 2), default=0)
    subtotal_0                  = Column(Numeric(12, 2), default=0)
    valor_iva                   = Column(Numeric(12, 2), default=0)
    datos_factura               = Column(JSONB, nullable=False)
    xml_path                    = Column(Text)
    pdf_path                    = Column(Text)
    mensajes_sri                = Column(JSONB)
    fecha_envio_sri             = Column(TIMESTAMP(timezone=True))
    fecha_autorizacion          = Column(TIMESTAMP(timezone=True))
    retry_count                 = Column(Integer, default=0)
    last_retry                  = Column(TIMESTAMP(timezone=True))
    created_at                  = Column(TIMESTAMP(timezone=True), server_default=func.now())

    punto_emision               = relationship("PuntoEmision", back_populates="invoices")
    cliente                     = relationship("ClienteEmisor", back_populates="invoices")


class InvoiceRecibida(Base):
    """
    Facturas electrónicas RECIBIDAS por el emisor.
    Base para declaración de renta — el cliente clasifica cada factura.

    Fuentes:
      MANUAL  → el cliente sube el XML manualmente (gratuito)
      EMAIL   → recepción automática por buzón inteligente (1 crédito de recepción)
      API     → integración futura
    """
    __tablename__ = "invoices_recibidas"
    __table_args__ = {"schema": "tenant_001"}

    id                      = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    emisor_id               = Column(Integer, ForeignKey("public.emisores.id"), nullable=False)
    ruc_proveedor           = Column(String(13), nullable=False)
    razon_social_proveedor  = Column(Text, nullable=False)
    clave_acceso            = Column(String(49), unique=True)
    numero_factura          = Column(String(17))
    fecha_emision           = Column(Date, nullable=False)
    subtotal_0              = Column(Numeric(12, 2), default=0)
    subtotal_iva            = Column(Numeric(12, 2), default=0)
    valor_iva               = Column(Numeric(12, 2), default=0)
    importe_total           = Column(Numeric(12, 2), nullable=False)
    categoria_gasto         = Column(String(50))    # 'OPERACIONAL', 'ARRIENDO', 'SUELDOS'...
    deducible_renta         = Column(Boolean, default=True)
    notas_cliente           = Column(Text)
    xml_path                = Column(Text)
    xml_raw                 = Column(JSONB)         # datos parseados para queries rápidas
    fuente                  = Column(String(10), default="MANUAL")
    procesado               = Column(Boolean, default=False)
    created_at              = Column(TIMESTAMP(timezone=True), server_default=func.now())