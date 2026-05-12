import asyncio
from app.core.database import engine  # Asegúrate de que esta ruta apunte a donde definiste tu 'engine'
from app.models.all_models import Base # Asegúrate de que apunte a tu archivo de modelos

async def create_tables():
    print("⏳ Conectando a Neon y creando tablas...")
    async with engine.begin() as conn:
        # Esto lee tu Base y crea todas las tablas en el schema public
        await conn.run_sync(Base.metadata.create_all)
    print("✅ ¡Tablas creadas con éxito en Neon!")

if __name__ == "__main__":
    asyncio.run(create_tables())