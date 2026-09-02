# app/services/storage_service.py

import boto3
import time
import gzip
import urllib3
from botocore.config import Config
from botocore.exceptions import ClientError
from app.core.config import settings

# Desactivar advertencias de SSL inseguro si se usa fallback
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# =============================================================================
# CLIENTE R2 (CONFIGURACIÓN A PRUEBA DE HANDSHAKE)
# =============================================================================

# Configuración estricta de timeouts y firmas para R2
r2_config = Config(
    signature_version='s3v4',
    s3={'addressing_style': 'path'},
    connect_timeout=10,
    read_timeout=30,
    retries={'max_attempts': 3, 'mode': 'standard'}
)

# Para solucionar SSLV3_ALERT_HANDSHAKE_FAILURE:
# 1. verify=False fuerza a boto3 a no fallar en el TLS Handshake con Cloudflare Edge
# 2. region_name='us-east-1' fuerza el endpoint compatible
r2_client = boto3.client(
    's3',
    endpoint_url=f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
    aws_access_key_id=settings.R2_ACCESS_KEY_ID,
    aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
    config=r2_config,
    region_name='us-east-1',
    verify=False  # <--- Salta el estricto handshake TLS de Python/urllib3 contra Cloudflare
)

BUCKET = settings.R2_BUCKET_NAME

print(f"[Storage] R2 inicializado — bucket: {BUCKET}")
print(f"[Storage] Account ID: {settings.R2_ACCOUNT_ID[:8]}...")
print(f"[Storage] Access Key: {settings.R2_ACCESS_KEY_ID[:8]}...")

# =============================================================================
# FUNCIONES PRINCIPALES
# =============================================================================

def upload_file(path: str, file_bytes: bytes, content_type: str = 'application/octet-stream') -> str:
    """Comprime y sube un archivo binario (ej. XML) a Cloudflare R2."""
    try:
        # 1. Comprimir los bytes con gzip
        compressed_bytes = gzip.compress(file_bytes)
        
        r2_client.put_object(
            Bucket=BUCKET,
            Key=path,
            Body=compressed_bytes,
            ContentType=content_type,
            ContentEncoding='gzip'  # 👈 Clave para que sepa que está comprimido
        )
        return path
    except Exception as e:
        print(f"❌ [Storage Error] Error subiendo a R2 ({path}): {e}")
        raise e


def download_file(path: str) -> bytes:
    """Descarga un archivo desde Cloudflare R2 y lo descomprime solo si está en formato gzip."""
    try:
        response = r2_client.get_object(Bucket=BUCKET, Key=path)
        file_bytes = response['Body'].read()
        
        # Verificar si el archivo comienza con los bytes mágicos de gzip (\x1f\x8b)
        if file_bytes.startswith(b'\x1f\x8b'):
            file_bytes = gzip.decompress(file_bytes)
            
        return file_bytes
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


def get_presigned_url(path: str, expires_in: int = 3600) -> str:
    """
    Genera una URL prefirmada para descarga directa desde R2.
    expires_in: segundos de validez (default 1 hora)
    """
    try:
        url = r2_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": BUCKET, "Key": path},
            ExpiresIn=expires_in,
        )
        return url
    except Exception as e:
        print(f"❌ [Storage Error] Error generando presigned URL ({path}): {e}")
        raise e