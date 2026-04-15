import io
from minio import Minio
from app.core.config import settings

print(f"[Storage] Inicializando MinIO con endpoint: {settings.MINIO_ENDPOINT}")

# Inicializamos el cliente de MinIO
minio_client = Minio(
    endpoint=f"{settings.MINIO_ENDPOINT}",#:{settings.MINIO_PORT}",
    access_key=settings.MINIO_ROOT_USER,
    secret_key=settings.MINIO_ROOT_PASSWORD,
    secure=settings.MINIO_USE_SSL
)

def upload_file(bucket_name: str, file_name: str, file_bytes: bytes, content_type: str = 'application/octet-stream') -> str:
    # Asegurar que el bucket existe
    if not minio_client.bucket_exists(bucket_name):
        minio_client.make_bucket(bucket_name)

    # Convertimos los bytes en un "Stream" para que MinIO los pueda leer
    data_stream = io.BytesIO(file_bytes)
    length = len(file_bytes)

    minio_client.put_object(
        bucket_name=bucket_name,
        object_name=file_name,
        data=data_stream,
        length=length,
        content_type=content_type
    )
    return f"{bucket_name}/{file_name}"

def download_file(bucket_name: str, file_name: str) -> bytes:
    try:
        response = minio_client.get_object(bucket_name, file_name)
        return response.read()
    finally:
        response.close()
        response.release_conn()

def delete_file(bucket_name: str, file_name: str) -> bool:
    minio_client.remove_object(bucket_name, file_name)
    return True


def delete_minio_folder(bucket_name: str, folder_prefix: str) -> bool:
    """
    Elimina todos los archivos en MinIO que coincidan con un prefijo (simula borrar una carpeta).
    """
    if not minio_client.bucket_exists(bucket_name):
        return False
        
    # Aseguramos que termine en '/' para no borrar por error RUCs parecidos (ej. 179... y 179...001)
    if not folder_prefix.endswith('/'):
        folder_prefix += '/'
        
    try:
        # list_objects trae todos los archivos que empiecen con ese RUC
        objects_to_delete = minio_client.list_objects(bucket_name, prefix=folder_prefix, recursive=True)
        
        count = 0
        for obj in objects_to_delete:
            minio_client.remove_object(bucket_name, obj.object_name)
            count += 1
            
        print(f"🗑️ Se eliminaron {count} archivos de la ruta: {bucket_name}/{folder_prefix}")
        return True
    except Exception as e:
        print(f"⚠️ Error limpiando la ruta {bucket_name}/{folder_prefix}: {e}")
        return False