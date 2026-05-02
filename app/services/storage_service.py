# app/services/storage_service.py
#
# Storage service para Cloudflare R2.
# API compatible con S3 — usa boto3.
#
# Estructura de paths en el bucket:
#   {RUC}/firmas/{timestamp}.p12
#   {RUC}/facturas/{año}/{mes}/{clave_acceso}_firmado.xml   ← temporal
#   {RUC}/facturas/{año}/{mes}/{clave_acceso}.xml           ← autorizado (permanente)
#
# Los PDFs NO se guardan — se generan bajo demanda desde el XML autorizado.

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from app.core.config import settings
import time

# =============================================================================
# CLIENTE R2
# =============================================================================

r2_client = boto3.client(
    's3',
    endpoint_url=f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
    aws_access_key_id=settings.R2_ACCESS_KEY_ID,
    aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
    config=Config(signature_version='s3v4'),
    region_name='auto'
)

BUCKET = settings.R2_BUCKET_NAME

print(f"[Storage] R2 inicializado — bucket: {BUCKET}")
print(f"[Storage] R2 inicializado — bucket: {BUCKET}")
print(f"[Storage] Account ID: {settings.R2_ACCOUNT_ID[:8]}...")  # solo primeros 8 chars por seguridad
print(f"[Storage] Access Key: {settings.R2_ACCESS_KEY_ID[:8]}...")

# =============================================================================
# FUNCIONES PRINCIPALES
# Mismos nombres que el storage_service.py anterior para no romper nada.
# =============================================================================

def upload_file(path: str, file_bytes: bytes, content_type: str = 'application/octet-stream') -> str:
    """
    Sube un archivo a R2.

    Args:
        path:         Path completo en el bucket. Ej: '1234567890001/facturas/2025/05/abc123.xml'
        file_bytes:   Contenido del archivo en bytes.
        content_type: MIME type del archivo.

    Returns:
        El mismo path recibido (para guardar en DB).
    """
    r2_client.put_object(
        Bucket=BUCKET,
        Key=path,
        Body=file_bytes,
        ContentType=content_type
    )
    return path


def download_file(path: str) -> bytes:
    """
    Descarga un archivo de R2 por su path.

    Args:
        path: Path completo en el bucket.

    Returns:
        Contenido del archivo en bytes.
    """
    response = r2_client.get_object(Bucket=BUCKET, Key=path)
    return response['Body'].read()


def delete_file(path: str) -> bool:
    """
    Elimina un archivo de R2.

    Args:
        path: Path completo en el bucket.

    Returns:
        True si se eliminó correctamente.
    """
    try:
        r2_client.delete_object(Bucket=BUCKET, Key=path)
        return True
    except ClientError as e:
        print(f"⚠️ Error eliminando {path}: {e}")
        return False


def delete_folder(prefix: str) -> bool:
    """
    Elimina todos los archivos bajo un prefijo (simula borrar una carpeta).
    Útil para el nuke de cuenta — borra todo el RUC de un cliente.

    Args:
        prefix: Prefijo del path. Ej: '1234567890001/' borra todo el RUC.

    Returns:
        True si se completó sin errores críticos.
    """
    # Asegurar que el prefix termine en '/' para no borrar RUCs similares
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

            # Borrar en lotes de hasta 1000 (límite de S3/R2)
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
# Funciones para construir paths consistentes en todo el sistema.
# =============================================================================

def path_firma(ruc: str) -> str:
    """
    Path para el certificado P12 del emisor.
    Ej: '1234567890001/firmas/CERTIFICADO_1714689234567.p12'
    """
    return f"{ruc}/firmas/CERTIFICADO_{int(time.time() * 1000)}.p12"


def path_xml_firmado(ruc: str, clave_acceso: str, fecha) -> str:
    """
    Path temporal del XML firmado (antes de que el SRI lo autorice).
    Ej: '1234567890001/facturas/2025/05/abc123_firmado.xml'
    """
    return f"{ruc}/facturas/{fecha.year}/{fecha.month:02d}/{clave_acceso}_firmado.xml"


def path_xml_autorizado(ruc: str, clave_acceso: str, fecha) -> str:
    """
    Path permanente del XML autorizado por el SRI.
    Ej: '1234567890001/facturas/2025/05/abc123.xml'
    """
    return f"{ruc}/facturas/{fecha.year}/{fecha.month:02d}/{clave_acceso}.xml"