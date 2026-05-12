#app/core/config.py

import os
import json
import boto3
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict
from botocore.exceptions import ClientError
from pydantic import Field

# 1. Leer el .env explícitamente ANTES de que boto3 haga nada
load_dotenv()

def get_aws_secret():
    # 👇 ¡AQUÍ PONEMOS EL NOMBRE REAL DE TU SECRETO!
    secret_name = os.environ.get("AWS_SECRET_NAME")
    
    # 👇 Y AQUÍ LA REGIÓN CORRECTA (us-east-2)
    region_name = os.environ.get("AWS_DEFAULT_REGION")
    
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager', 
        region_name=region_name
    )

    try:
        response = client.get_secret_value(SecretId=secret_name)
        return json.loads(response['SecretString'])
    except ClientError as e:
        print(f"⚠️ Error conectando a AWS: {e}")
        return {}

class Settings(BaseSettings):
    DATABASE_URL: str = Field(validation_alias="DATABASE_URL_KIPU")
    FIREBASE_PROJECT_ID: str
    FIREBASE_CLIENT_EMAIL: str
    FIREBASE_PRIVATE_KEY_ID: str
    FIREBASE_PRIVATE_KEY: str
    N8N_API_KEY: str = Field(validation_alias="KIPU_CORE_KEY")
    WEB_HOOK_NOTIFICACIONES: str
    ENCRYPTION_KEY: str
    TURNSTILE_SECRET_KEY: str
    SMTP_HOST: str
    SMTP_PORT: int
    SMTP_USER: str
    SMTP_PASS: str
    SMTP_FROM: str
    PORT: int = 3000
    FRONTEND_URL: str
    DEBUG_SIGNER: bool = False
    REDIS_URL: str = "redis://localhost:6379/0"

    R2_ACCOUNT_ID:        str
    R2_ACCESS_KEY_ID:     str
    R2_SECRET_ACCESS_KEY: str
    R2_BUCKET_NAME:       str

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
"""
try:
    settings = Settings()
    print("✅ Configuración cargada desde archivo .env local")
except Exception as e:
    print("⚠️ Faltan variables locales, yendo a buscar a AWS Secrets Manager...")
    aws_secrets = get_aws_secret()
    settings = Settings(**aws_secrets)
    print("✅ Configuración cargada con éxito desde AWS")
"""
try:
    # Intento 1: Solo con .env local
    settings = Settings()
    print("✅ Configuración cargada desde archivo .env local")
except Exception:
    print("⚠️ Faltan variables locales, yendo a buscar a AWS Secrets Manager...")
    aws_secrets = get_aws_secret()
    
    
    try:
        settings = Settings(**aws_secrets)
        print("✅ Configuración cargada con éxito (Híbrida Local + AWS)")
    except Exception as final_error:
        print(f"❌ Error fatal de configuración: {final_error}")
        raise final_error    