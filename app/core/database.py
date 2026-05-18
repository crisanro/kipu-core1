from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.core.config import settings

# 1. Ajustamos la URL para que use el driver asíncrono
base_url = settings.DATABASE_URL.split('?')[0]
db_url = base_url.replace("postgres://", "postgresql+asyncpg://").replace("postgresql://", "postgresql+asyncpg://")

# Eliminamos la creación del contexto SSL (ctx). Ya no lo necesitamos para contenedores internos.

# 2. Configuramos el motor sin los connect_args de SSL
engine = create_async_engine(
    db_url,
    pool_size=10,
    pool_timeout=30.0,
    pool_recycle=1800,
    echo=False
    # Eliminamos por completo el bloque connect_args={"ssl": ctx}
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