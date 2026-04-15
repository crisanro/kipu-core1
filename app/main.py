from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Importamos la inicialización de Firebase (Esto lo enciende automáticamente)
import app.core.firebase 
import time
# Importamos los Workers
from app.workers.sri_worker import job_enviar_facturas, job_autorizar_facturas

# Importamos las Rutas (Routers) con alias para no confundir nombres
from app.api.v1.app import (
    auth as auth_app,
    emisor as emisor_app,
    estructura as estructura_app,
    clientes as clientes_app,
    invoices as invoices_app,
    dashboard as dashboard_app,
    apikeys as apikeys_app
)
from app.api.v1.public import (
    clientes as clientes_public,
    integraciones as integraciones_public
)
from app.api.v1.admin import (
    clientes_n8n,
    integraciones as integraciones_n8n
)



# ─── CONFIGURACIÓN DE LOS WORKERS (CRONJOBS) ─────────────────────────────────
scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Configurar y encender Workers al iniciar el servidor
    scheduler.add_job(job_enviar_facturas, 'interval', minutes=2)
    scheduler.add_job(job_autorizar_facturas, 'interval', minutes=3)
    scheduler.start()
    print("⏰ Workers del SRI iniciados correctamente.")
    
    yield # Aquí FastAPI atiende las peticiones HTTP
    
    # 2. Apagar Workers suavemente al detener el servidor
    scheduler.shutdown()
    print("💤 Workers del SRI detenidos.")

# ─── INICIALIZACIÓN DE FASTAPI ────────────────────────────────────────────────
app = FastAPI(
    title="Kipu Core API",
    description="Microservicios Core para Facturación Electrónica SRI",
    version="2.0.0",
    lifespan=lifespan
)


# ─── CONFIGURACIÓN DE CORS (Para tu Frontend en Vue/React) ───────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # En producción cambia esto por ["https://kipu.ec"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Imprime en la terminal qué falló exactamente
    print("❌ ERROR DE VALIDACIÓN 422 ❌")
    print("Ruta:", request.url.path)
    print("Errores detallados:", exc.errors())
    
    # Devuelve la respuesta normal de FastAPI
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )


# ─── MIDDLEWARE DE LOGS Y TIEMPO DE RESPUESTA ────────────────────────────────
async def set_body(request: Request, body: bytes):
    """
    Truco vital en FastAPI: Si leemos el body en el middleware, el endpoint se
    queda sin datos y se bloquea. Esta función reconstruye el flujo de datos.
    """
    async def receive():
        return {"type": "http.request", "body": body}
    request._receive = receive

@app.middleware("http")
async def log_request_data_and_time(request: Request, call_next):
    start_time = time.time()

    # 1. Capturar el body
    body = await request.body()
    await set_body(request, body)

    # 2. Dejar que la API haga su trabajo
    response = await call_next(request)

    # 3. Preparar la información de los datos en una sola línea
    data_log = "Ninguno"
    if request.query_params:
        data_log = f"Query: {request.query_params}"
    elif body:
        try:
            # Decodificamos y quitamos saltos de línea para que no rompa la consola
            decoded = body.decode('utf-8').replace('\n', '').replace('\r', '').replace('  ', '')
            # Si el body es gigantesco, mostramos solo los primeros 150 caracteres
            if len(decoded) > 150:
                decoded = decoded[:150] + "... [truncado]"
            data_log = f"Body: {decoded}"
        except Exception:
            data_log = "Body: [Archivo Binario]"

    # 4. Calcular tiempo e imprimir con print normal (con flush=True)
    process_time_ms = (time.time() - start_time) * 1000
    
    print(f"   [{request.method}] {response.status_code} | {process_time_ms:.2f} ms | Data: {data_log}", flush=True)

    # (Opcional) Guardar tiempo en headers
    response.headers["X-Process-Time-Ms"] = str(round(process_time_ms, 2))

    return response

# ─── REGISTRO DE RUTAS (ENDPOINTS) ────────────────────────────────────────────

# 1. CANAL: App Web & Mobile (Firebase Auth)
app.include_router(auth_app.router, prefix="/api/v1/app/auth", tags=["📱 App - Auth & Nuke"])
app.include_router(emisor_app.router, prefix="/api/v1/app/emisor", tags=["📱 App - Emisor & Config"])
app.include_router(estructura_app.router, prefix="/api/v1/app/estructura", tags=["📱 App - Estructura"])
app.include_router(clientes_app.router, prefix="/api/v1/app/clientes", tags=["📱 App - Clientes"])
app.include_router(invoices_app.router, prefix="/api/v1/app/invoices", tags=["📱 App - Facturación"])
app.include_router(dashboard_app.router, prefix="/api/v1/app/dashboard", tags=["📱 App - Dashboard"])
app.include_router(apikeys_app.router, prefix="/api/v1/app/apikeys", tags=["📱 App - API Keys"])

# 2. CANAL: API Pública (API Key Auth)
app.include_router(integraciones_public.router, prefix="/api/v1/public/integraciones", tags=["🌍 API Pública - Facturación"])
app.include_router(clientes_public.router, prefix="/api/v1/public/clientes", tags=["🌍 API Pública - Clientes"])

# 3. CANAL: Admin / n8n / WhatsApp (Headers Internos)
app.include_router(integraciones_n8n.router, prefix="/api/v1/admin", tags=["🤖 n8n Automations - Core"])
app.include_router(clientes_n8n.router, prefix="/api/v1/admin/n8n/clientes", tags=["🤖 n8n Automations - Clientes"])

# ─── RUTA DE ESTADO (HEALTH CHECK) ────────────────────────────────────────────
@app.get("/", tags=["Health"])   # <--- EL ERROR ESTÁ AQUÍ
async def root():
    return {"status": "Kipu API is running! 🚀", "docs": "Visita /docs para la documentación interactiva."}