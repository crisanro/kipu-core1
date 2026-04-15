# Usamos una imagen de Python optimizada
FROM python:3.13-slim

# Evita que Python genere archivos .pyc y permite que los logs salgan en tiempo real
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Instalamos dependencias del sistema necesarias para:
# - psycopg2 (libpq-dev, gcc)
# - Pillow/Criptografía (libffi-dev)
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copiamos e instalamos los requerimientos
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copiamos el resto del código
COPY . .

# Exponemos el puerto de FastAPI
EXPOSE 8000

# Comando para arrancar con Uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]