# app/services/storage_service.py
#
# Storage service para Cloudflare R2.
# API compatible con S3 — usa boto3.
#
# Estructura de paths en el bucket:
#   {RUC}/firmas/{timestamp}.p12
#   {RUC}/facturas/{año}/{mes}/{clave_acceso}.xml
#
# Los PDFs NO se guardan — se generan bajo demanda desde el XML autorizado.

import boto3
import time
from botocore.config import Config
from botocore.exceptions import ClientError
from app.core.config import settings

# =============================================================================
# CLIENTE R2 (CONFIGURACIÓN OPTIMIZADA)
# =============================================================================

# Configuración de rendimiento y compatibilidad S3/R2
r2_config = Config(
    signature_version='s3v4',
    s3={'addressing_style': 'path'},
    connect_timeout=10,
    read_timeout=30,
    retries={'max_attempts': 3, 'mode': 'standard'}
)

# Inicialización del cliente boto3
# Nota: Usar 'us-east-1' resuelve incompatibilidades de TLS Handshake con el endpoint de Cloudflare
r2_client = boto3.client(
    's3',
    endpoint_url=f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
    aws_access_key_id=settings.R2_ACCESS_KEY_ID,
    aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
    config=r2_config,
    region_name='us-east-1',
    verify=True  # Usa la cadena de certificados SSL del sistema operativo
)

BUCKET = settings.R2_BUCKET_NAME

print(f"[Storage] R2 inicializado — bucket: {BUCKET}")
print(f"[Storage] Account ID: {settings.R2_ACCOUNT_ID[:8]}...")
print(f"[Storage] Access Key: {settings.R2_ACCESS_KEY_ID[:8]}...")

# =============================================================================
# FUNCIONES PRINCIPALES
# =============================================================================

def upload_file(path: str, file_bytes: bytes, content_type: str = 'application/octet-stream') -> str:
    """Suba un archivo binario directamente a Cloudflare R2."""
    try:
        r2_client.put_object(
            Bucket=BUCKET,
            Key=path,
            Body=file_bytes,
            ContentType=content_type
        )
        return path
    except Exception as e:
        print(f"❌ [Storage Error] Error subiendo a R2 ({path}): {e}")
        raise e


def download_file(path: str) -> bytes:
    """Descarga un archivo desde Cloudflare R2 como bytes."""
    try:
        response = r2_client.get_object(Bucket=BUCKET, Key=path)
        return response['Body'].read()
    except Exception as e:
        print(f"❌ [Storage Error] Error descargando de R2 ({path}): {e}")
        raise e


def delete_file(path: str) -> bool:
    """Elimina un archivo de R2 por su clave/path."""
    try:
        r2_client.delete_object(Bucket=BUCKET, Key=path)
        return True
    except ClientError as e:
        print(f"⚠️ Error eliminando {path}: {e}")
        return False


def delete_folder(prefix: str) -> bool:
    """Elimina iterativamente todos los objetos bajo un prefijo/carpeta."""
    if not prefix.endswith('/'):
        prefix += '/'

    try:
        paginator = r2_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=BUCKET, Prefix=prefix)

        count = 0
        for page in pages:
            objects = page.get('Contents', [])
            if not objects:
                continue

            r2_client.delete_objects(
                Bucket=BUCKET,
                Delete={
                    'Objects': [{'Key': obj['Key']} for obj in objects],
                    'Quiet': True
                }
            )
            count += len(objects)

        print(f"🗑️ {count} archivos eliminados bajo: {prefix}")
        return True

    except ClientError as e:
        print(f"⚠️ Error eliminando carpeta {prefix}: {e}")
        return False


# =============================================================================
# HELPERS DE PATH
# =============================================================================

def path_firma(ruc: str) -> str:
    return f"{ruc}/firmas/CERTIFICADO_{int(time.time() * 1000)}.p12"


def path_xml_firmado(ruc: str, clave_acceso: str, fecha) -> str:
    return f"{ruc}/facturas/{fecha.year}/{fecha.month:02d}/{clave_acceso}_firmado.xml"


def path_xml_autorizado(ruc: str, clave_acceso: str, fecha) -> str:
    return f"{ruc}/facturas/{fecha.year}/{fecha.month:02d}/{clave_acceso}.xml"