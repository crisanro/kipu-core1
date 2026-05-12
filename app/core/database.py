from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.core.config import settings
import ssl

# 1. Ajustamos la URL para que use el driver asíncrono y limpiamos parámetros de libpq
# Eliminamos todo lo que viene después del '?' para evitar el error de 'sslmode'
base_url = settings.DATABASE_URL.split('?')[0]
db_url = base_url.replace("postgres://", "postgresql+asyncpg://").replace("postgresql://", "postgresql+asyncpg://")

# 2. Creamos un contexto SSL (Requerido por Neon para conexiones seguras)
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# 3. Configuramos el motor con los connect_args
engine = create_async_engine(
    db_url,
    pool_size=10,
    pool_timeout=30.0,
    pool_recycle=1800,
    echo=False,
    connect_args={
        "ssl": ctx  # <--- Aquí pasamos el SSL que asyncpg sí entiende
    }
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

# Dependencia para inyectar la DB en las rutas
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session