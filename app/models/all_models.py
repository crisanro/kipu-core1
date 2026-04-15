from sqlalchemy import Column, String, Integer, Boolean, Text, Date, DateTime, Numeric, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func
import uuid

Base = declarative_base()

# --- EMISORES ---
class Emisor(Base):
    __tablename__ = "emisores"
    id = Column(Integer, primary_key=True, index=True)
    ruc = Column(String(13), unique=True, nullable=False)
    razon_social = Column(Text, nullable=False)
    nombre_comercial = Column(Text)
    direccion_matriz = Column(Text, nullable=False)
    ambiente = Column(Integer, default=1) # 1: Pruebas, 2: Producción
    p12_path = Column(Text)
    p12_pass = Column(Text)
    p12_expiration = Column(Date)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# --- PROFILES (Usuarios con Firebase) ---
class Profile(Base):
    __tablename__ = "profiles"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    firebase_uid = Column(Text, unique=True, nullable=False)
    emisor_id = Column(Integer, ForeignKey("emisores.id"))
    email = Column(Text, unique=True, nullable=False)
    full_name = Column(Text)
    role = Column(String, server_default="'admin'")
    whatsapp_number = Column(String)

# --- INVOICES (Facturas Electrónicas) ---
class Invoice(Base):
    __tablename__ = "invoices"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    emisor_id = Column(Integer, ForeignKey("emisores.id"), nullable=False)
    punto_emision_id = Column(Integer, ForeignKey("puntos_emision.id"), nullable=False)
    clave_acceso = Column(String(49), unique=True)
    secuencial = Column(String(9), nullable=False)
    fecha_emision = Column(Date, server_default=func.current_date())
    estado = Column(String, server_default="'PENDIENTE'")
    
    identificacion_comprador = Column(String, nullable=False)
    razon_social_comprador = Column(Text, nullable=False)
    email_comprador = Column(String)
    
    importe_total = Column(Numeric, nullable=False)
    subtotal_iva = Column(Numeric, default=0)
    subtotal_0 = Column(Numeric, default=0)
    valor_iva = Column(Numeric, default=0)
    
    datos_factura = Column(JSONB, nullable=False) # Tu columna JSONB de datos
    mensajes_sri = Column(JSONB)                 # Tu columna JSONB de errores/respuestas
    
    xml_path = Column(Text)
    pdf_path = Column(Text)
    retry_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# --- CLIENTES (Tu estructura global + emisor) ---
class SujetoGlobal(Base):
    __tablename__ = "sujetos_global"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    identificacion = Column(String, unique=True, nullable=False)
    razon_social = Column(Text, nullable=False)
    tipo_identificacion_sri = Column(String, nullable=False)

class ClienteEmisor(Base):
    __tablename__ = "clientes_emisor"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    emisor_id = Column(Integer, ForeignKey("emisores.id"), nullable=False)
    sujeto_global_id = Column(UUID(as_uuid=True), ForeignKey("sujetos_global.id"), nullable=False)
    email = Column(String)
    telefono = Column(String)