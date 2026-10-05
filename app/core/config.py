# app/core/config.py
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

load_dotenv()

class Settings(BaseSettings):
    DATABASE_URL:           str = Field(validation_alias="DATABASE_URL_KIPU")
    REDIS_URL:              str
    NODE_SIGNER_URL:        str
    CLOUDFLARE_ONLY:      bool = False
    IVA_RATE: float = 0.15
    BACKEND_URL: str = "https://core.kipu.ec"
    STRIPE_SECRET_KEY: str
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRICE_PRO_ANUAL: str = ""
    KIPU_EMISOR_ID:        int = 0
    KIPU_ESTABLECIMIENTO:  str = "001"
    KIPU_PUNTO_EMISION:    str = "001"
    INTERNAL_API_KEY:      str = ""
    FIREBASE_PROJECT_ID:    str
    FIREBASE_CLIENT_EMAIL:  str
    FIREBASE_PRIVATE_KEY_ID: str
    FIREBASE_PRIVATE_KEY:   str
    N8N_API_KEY:            str = Field(validation_alias="KIPU_CORE_KEY")
    WEB_HOOK_NOTIFICACIONES: str
    ENCRYPTION_KEY:         str
    TURNSTILE_SECRET_KEY:   str
    SMTP_HOST:              str
    SMTP_PORT:              int
    SMTP_USER:              str
    SMTP_PASS:              str
    SMTP_FROM:              str
    ALERT_EMAIL_ERRORS: bool = True
    ALERT_EMAIL_TO:     str  = "cristhian@kipu.ec"
    PORT:                   int = 3000
    FRONTEND_URL:           str
    DEBUG_SIGNER:           bool = False
    R2_ACCOUNT_ID:          str
    R2_ACCESS_KEY_ID:       str
    R2_SECRET_ACCESS_KEY:   str
    R2_BUCKET_NAME:         str
    R2_PUBLIC_URL:          str
    ENVIRONMENT:            str

    # ── Pool de base de datos (horizontal scaling) ────────────────────────
    DB_POOL_SIZE:       int = 5      # conexiones permanentes por instancia
    DB_MAX_OVERFLOW:    int = 10     # conexiones extra bajo carga
    DB_POOL_TIMEOUT:    int = 30     # segundos esperando conexión libre
    DB_POOL_RECYCLE:    int = 1800   # reciclar conexiones cada 30 min

    # ── Worker SRI ────────────────────────────────────────────────────────
    SRI_MAX_CONCURRENT:          int = 3      # llamadas SOAP simultáneas al SRI
    SRI_MAX_INTENTOS_TECNICOS:   int = 8      # reintentos antes de EN_REVISION
    SRI_ESPERA_AUTORIZACION_SEG: float = 3.0  # espera tras RECIBIDA antes de consultar
    SRI_CONCILIACION_CADA_SEG:   int = 1800   # cada 30 min
    SRI_CONCILIACION_LOCK_SEG:   int = 1740   # TTL del lock (< intervalo)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

try:
    settings = Settings()
    print("✅ Configuración cargada desde .env")
except Exception as e:
    print(f"❌ Error fatal de configuración: {e}")
    raise