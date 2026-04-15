from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.core.config import settings

# FastAPI/asyncpg requiere que la URL empiece con postgresql+asyncpg://
db_url = settings.DATABASE_URL.replace("postgres://", "postgresql+asyncpg://").replace("postgresql://", "postgresql+asyncpg://")

# Esto es el equivalente a tu "new Pool({...})"
engine = create_async_engine(
    db_url,
    pool_size=10,
    pool_timeout=30.0,
    pool_recycle=1800, # Evita el ECONNRESET cerrando conexiones viejas
    echo=False
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