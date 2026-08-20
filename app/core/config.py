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
    STRIPE_PRICE_NATURAL_MENSUAL:  str = ""
    STRIPE_PRICE_NATURAL_ANUAL:    str = ""
    STRIPE_PRICE_JURIDICO_MENSUAL: str = ""
    STRIPE_PRICE_JURIDICO_ANUAL:   str = ""
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

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

try:
    settings = Settings()
    print("✅ Configuración cargada desde .env")
except Exception as e:
    print(f"❌ Error fatal de configuración: {e}")
    raise