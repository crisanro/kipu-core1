# main.py
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import time

# Firebase
import app.core.firebase

# Workers
from app.workers.sri_worker import job_enviar_facturas, job_autorizar_facturas

# Routers
from app.api.v1.app import (
    auth as auth_app,
    emisor as emisor_app,
    estructura as estructura_app,
    clientes as clientes_app,
    invoices as invoices_app,
    dashboard as dashboard_app,
    apikeys as apikeys_app,
    catalogo as catalogo_app,
    notificaciones as notificaciones_app

)
from app.api.v1.public import (
    clientes as clientes_public,
    integraciones as integraciones_public,
    invoices as invoices_public
)
from app.api.v1.admin import (
    integraciones as integraciones_n8n
)

# ─── WORKERS ──────────────────────────────────────────────────────────────────
scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(job_enviar_facturas,   'interval', seconds=20, max_instances=1)
    scheduler.add_job(job_autorizar_facturas, 'interval', seconds=30, max_instances=1)
    scheduler.start()
    print("⏰ Workers del SRI iniciados correctamente.")
    yield
    scheduler.shutdown()
    print("💤 Workers del SRI detenidos.")

# ─── APP ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Kipu Core API",
    description="Microservicios Core para Facturación Electrónica SRI",
    version="2.0.0",
    lifespan=lifespan
)

# ─── OPENAPI PERSONALIZADO ────────────────────────────────────────────────────
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title="Kipu Core API",
        version="2.0.0",
        description="Microservicios Core para Facturación Electrónica SRI",
        routes=app.routes,
    )

    # Esquema Bearer JWT Firebase
    schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Token Firebase — cópialo desde la app web"
        }
    }

    # Aplicar candado solo a rutas NO públicas y NO admin
    for path, path_item in schema["paths"].items():
        if "/public/" in path or "/admin/" in path or path == "/":
            continue
        for method in path_item.values():
            method["security"] = [{"BearerAuth": []}]

    app.openapi_schema = schema
    return app.openapi_schema

app.openapi = custom_openapi

# ─── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción: ["https://kipu.ec"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── HANDLER DE ERRORES DE VALIDACIÓN ─────────────────────────────────────────
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    print("❌ ERROR DE VALIDACIÓN 422 ❌")
    print("Ruta:", request.url.path)
    errores = []
    for e in exc.errors():
        errores.append({
            "campo":           " → ".join(str(x) for x in e["loc"]),
            "mensaje":         e["msg"],
            "valor_recibido":  str(e.get("input", ""))
        })
    return JSONResponse(status_code=422, content={"detail": errores})

# ─── MIDDLEWARE DE LOGS ────────────────────────────────────────────────────────
async def set_body(request: Request, body: bytes):
    async def receive():
        return {"type": "http.request", "body": body}
    request._receive = receive

@app.middleware("http")
async def log_request_data_and_time(request: Request, call_next):
    start_time = time.time()
    body = await request.body()
    await set_body(request, body)
    response = await call_next(request)

    data_log = "Ninguno"
    if request.query_params:
        data_log = f"Query: {request.query_params}"
    elif body:
        try:
            decoded = body.decode('utf-8').replace('\n', '').replace('\r', '').replace('  ', '')
            if len(decoded) > 150:
                decoded = decoded[:150] + "... [truncado]"
            data_log = f"Body: {decoded}"
        except Exception:
            data_log = "Body: [Archivo Binario]"

    process_time_ms = (time.time() - start_time) * 1000
    print(f"   [{request.method}] {response.status_code} | {process_time_ms:.2f} ms | Data: {data_log}", flush=True)
    response.headers["X-Process-Time-Ms"] = str(round(process_time_ms, 2))
    return response

# ─── RUTAS ────────────────────────────────────────────────────────────────────

# App Web & Mobile (Firebase Auth)
app.include_router(auth_app.router,       prefix="/api/v1/app/auth",       tags=["📱 App - Auth & Nuke"])
app.include_router(emisor_app.router,     prefix="/api/v1/app/emisor",     tags=["📱 App - Emisor & Config"])
app.include_router(estructura_app.router, prefix="/api/v1/app/estructura", tags=["📱 App - Estructura"])
app.include_router(clientes_app.router,   prefix="/api/v1/app/clientes",   tags=["📱 App - Clientes"])
app.include_router(invoices_app.router,   prefix="/api/v1/app/invoices",   tags=["📱 App - Facturación"])
app.include_router(dashboard_app.router,  prefix="/api/v1/app/dashboard",  tags=["📱 App - Dashboard"])
app.include_router(apikeys_app.router,    prefix="/api/v1/app/apikeys",    tags=["📱 App - API Keys"])
app.include_router(catalogo_app.router, prefix="/api/v1/app/catalogo", tags=["📱 App - Catálogo"])
app.include_router(notificaciones_app.router, prefix="/api/v1/app/notificaciones", tags=["📱 App - Notificaciones"] )

# API Pública (API Key Auth)
app.include_router(integraciones_public.router, prefix="/api/v1/public/integraciones", tags=["🌍 API Facturación"])
app.include_router(invoices_public.router,       prefix="/api/v1/public",               tags=["🌍 API Facturación"])
app.include_router(clientes_public.router,       prefix="/api/v1/public/clientes",      tags=["🌍 API Facturación"])

# Admin / n8n / WhatsApp (Headers Internos)
app.include_router(integraciones_n8n.router, prefix="/api/v1/admin",              tags=["🤖 n8n Automations - Core"])

# ─── HEALTH CHECK ─────────────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
async def root():
    return {
        "status": "Kipu API is running! 🚀",
        "docs": "Visita /docs para la documentación interactiva."
    }