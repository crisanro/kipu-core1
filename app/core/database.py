# app/core/database.py
"""
Conexión async a PostgreSQL.

Pool configurable vía env vars para escalar horizontalmente:
  DB_POOL_SIZE       — conexiones permanentes por instancia (default: 5)
  DB_MAX_OVERFLOW    — conexiones extra bajo carga (default: 10)
  DB_POOL_TIMEOUT    — segundos esperando una conexión libre (default: 30)
  DB_POOL_RECYCLE    — reciclar conexiones cada N segundos (default: 1800)

Cálculo para múltiples instancias:
  max_conexiones_postgres = instancias × (pool_size + max_overflow)
  Ejemplo: 4 servers × (5 + 10) = 60 conexiones máximo
  Postgres default max_connections = 100 → queda margen
"""

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.core.config import settings

# 1. Ajustamos la URL para que use el driver asíncrono
base_url = settings.DATABASE_URL.split('?')[0]
db_url = base_url.replace("postgres://", "postgresql+asyncpg://").replace("postgresql://", "postgresql+asyncpg://")

# 2. Pool configurable vía env vars
pool_size     = int(getattr(settings, "DB_POOL_SIZE",     5))
max_overflow  = int(getattr(settings, "DB_MAX_OVERFLOW",  10))
pool_timeout  = float(getattr(settings, "DB_POOL_TIMEOUT",  30))
pool_recycle  = int(getattr(settings, "DB_POOL_RECYCLE",  1800))

engine = create_async_engine(
    db_url,
    pool_size=pool_size,
    max_overflow=max_overflow,
    pool_timeout=pool_timeout,
    pool_recycle=pool_recycle,
    pool_pre_ping=True,  # verifica que la conexión siga viva antes de usarla
    echo=False,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# Dependencia para inyectar la DB en las rutas
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session