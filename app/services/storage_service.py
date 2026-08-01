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
import certifi
import time
from botocore.config import Config
from botocore.exceptions import ClientError
from app.core.config import settings

# =============================================================================
# CLIENTE R2
# =============================================================================

r2_client = boto3.client(
    's3',
    endpoint_url=f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
    aws_access_key_id=settings.R2_ACCESS_KEY_ID,
    aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
    config=Config(
        signature_version='s3v4',
        connect_timeout=10,
        read_timeout=30,
    ),
    region_name='auto',
    verify=certifi.where()   # Usa los certificados CA de certifi — funciona en todos los entornos
)

BUCKET = settings.R2_BUCKET_NAME

print(f"[Storage] R2 inicializado — bucket: {BUCKET}")
print(f"[Storage] Account ID: {settings.R2_ACCOUNT_ID[:8]}...")
print(f"[Storage] Access Key: {settings.R2_ACCESS_KEY_ID[:8]}...")

# =============================================================================
# FUNCIONES PRINCIPALES
# =============================================================================

def upload_file(path: str, file_bytes: bytes, content_type: str = 'application/octet-stream') -> str:
    try:
        r2_client.put_object(
            Bucket=BUCKET,
            Key=path,
            Body=file_bytes,
            ContentType=content_type
        )
        return path
    except Exception as e:
        print(f"❌ [Storage Error] Error subiendo a R2: {e}")
        raise e


def download_file(path: str) -> bytes:
    response = r2_client.get_object(Bucket=BUCKET, Key=path)
    return response['Body'].read()


def delete_file(path: str) -> bool:
    try:
        r2_client.delete_object(Bucket=BUCKET, Key=path)
        return True
    except ClientError as e:
        print(f"⚠️ Error eliminando {path}: {e}")
        return False


def delete_folder(prefix: str) -> bool:
    if not prefix.endswith('/'):
        prefix += '/'

    try:
        paginator = r2_client.get_paginator('list_objects_v2')
        pages     = paginator.paginate(Bucket=BUCKET, Prefix=prefix)

        count = 0
        for page in pages:
            objects = page.get('Contents', [])
            if not objects:
                continue

            r2_client.delete_objects(
                Bucket=BUCKET,
                Delete={
                    'Objects': [{'Key': obj['Key']} for obj in objects],
                    'Quiet':   True
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