# main.py
import asyncio
import time
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from contextlib import asynccontextmanager

# Firebase
import app.core.firebase

# Workers
from app.workers.sri_worker import iniciar_workers
from app.workers.declaraciones_worker import iniciar_worker_declaraciones

# Routers
from app.api.v1.app import (
    auth as auth_app,
    emisor as emisor_app,
    estructura as estructura_app,
    clientes as clientes_app,
    invoices as invoices_app,
    declaraciones as declaraciones_app,
    dashboard as dashboard_app,
    apikeys as apikeys_app,
    catalogo as catalogo_app,
    recibidas as recibidas_app,
    notificaciones as notificaciones_app,
    productos as productos_app,
    usuarios as usuarios_app,
    notas_credito as notas_credito_app,
    creditos as creditos_app
)
from app.api.v1.public import (
    clientes as clientes_public,
    integraciones as integraciones_public,
    invoices as invoices_public,
)
from app.api.v1.admin import (
    integraciones as integraciones_n8n,
)

# ─── LIFESPAN ─────────────────────────────────────────────────────────────────
_worker_task:        asyncio.Task | None = None
_declaraciones_task: asyncio.Task | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _worker_task, _declaraciones_task
    _worker_task        = asyncio.create_task(iniciar_workers())
    _declaraciones_task = asyncio.create_task(iniciar_worker_declaraciones())
    print("🚀 Workers iniciados.")
    yield
    for task in [_worker_task, _declaraciones_task]:
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    print("💤 Workers detenidos.")

# ─── APP ──────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Kipu Core API",
    description="Microservicios Core para Facturación Electrónica SRI",
    version="2.0.0",
    lifespan=lifespan,
    redirect_slashes=False
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
    schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type":        "http",
            "scheme":      "bearer",
            "bearerFormat": "JWT",
            "description": "Token Firebase — cópialo desde la app web"
        }
    }
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
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── HANDLER DE ERRORES DE VALIDACIÓN ─────────────────────────────────────────
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    print("❌ ERROR DE VALIDACIÓN 422 ❌")
    print("Ruta:", request.url.path)
    print("Errores:", exc.errors())
    errores = []
    for e in exc.errors():
        errores.append({
            "campo":          " → ".join(str(x) for x in e["loc"]),
            "mensaje":        e["msg"],
            "valor_recibido": str(e.get("input", ""))
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
    body       = await request.body()
    await set_body(request, body)
    response   = await call_next(request)

    data_log = "Ninguno"
    if request.query_params:
        data_log = f"Query: {request.query_params}"
    elif body:
        try:
            decoded = body.decode("utf-8").replace("\n", "").replace("\r", "").replace("  ", "")
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
app.include_router(auth_app.router,           prefix="/api/v1/app/auth",             tags=["📱 App - Auth & Nuke"])
app.include_router(emisor_app.router,         prefix="/api/v1/app/emisor",           tags=["📱 App - Emisor & Config"])
app.include_router(estructura_app.router,     prefix="/api/v1/app/estructura",       tags=["📱 App - Estructura"])
app.include_router(productos_app.router,      prefix="/api/v1/app/productos",        tags=["📱 App - Productos"])
app.include_router(usuarios_app.router,       prefix="/api/v1/app/usuarios",         tags=["📱 App - Usuarios"])
app.include_router(clientes_app.router,       prefix="/api/v1/app/clientes",         tags=["📱 App - Clientes"])
app.include_router(invoices_app.router,       prefix="/api/v1/app/invoices",         tags=["📱 App - Facturación"])
app.include_router(dashboard_app.router,      prefix="/api/v1/app/dashboard",        tags=["📱 App - Dashboard"])
app.include_router( declaraciones_app.router, prefix="/api/v1/app/declaraciones", tags=["📱 App - Declaraciones"] )
app.include_router(apikeys_app.router,        prefix="/api/v1/app/apikeys",          tags=["📱 App - API Keys"])
app.include_router(catalogo_app.router,       prefix="/api/v1/app/catalogo",         tags=["📱 App - Catálogo"])
app.include_router(recibidas_app.router,      prefix="/api/v1/app/invoices/received", tags=["📱 App - Facturas Recibidas"])
app.include_router(notificaciones_app.router, prefix="/api/v1/app/notificaciones",    tags=["📱 App - Notificaciones"])
app.include_router(creditos_app.router,       prefix="/api/v1/app/creditos",         tags=["📱 App - Créditos"])
app.include_router(notas_credito_app.router,  prefix="/api/v1/app/notas-credito",    tags=["📱 App - Notas de Crédito"])

app.include_router(integraciones_public.router, prefix="/api/v1/public/integraciones", tags=["🌍 API Facturación"])
app.include_router(invoices_public.router,       prefix="/api/v1/public",              tags=["🌍 API Facturación"])
app.include_router(clientes_public.router,       prefix="/api/v1/public/clientes",      tags=["🌍 API Facturación"])

app.include_router(integraciones_n8n.router, prefix="/api/v1/admin", tags=["🤖 n8n Automations - Core"])

# ─── HEALTH CHECK ─────────────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
async def root():
    return {
        "status": "Kipu API is running! 🚀",
        "docs":   "Visita /docs para la documentación interactiva."
    }

# ─── OPENAPI PÚBLICO PARA CLIENTES ────────────────────────────────────────────
@app.get("/api-docs", include_in_schema=False)
async def openapi_publico():
    from fastapi.responses import JSONResponse
    schema = get_openapi(
        title="Kipu — API de Facturación Electrónica",
        version="2.0.0",
        description="""
# Kipu API — Facturación Electrónica Ecuador

Integra facturación electrónica SRI en tu sistema en minutos.

## Autenticación
X-Api-Key: tu_api_key_aqui
Obtén tu API Key desde **Configuración → API Keys** en [app.kipu.ec](https://app.kipu.ec).

## Flujo básico
1. **Verificar** → `POST /api/v1/public/integraciones/validate`
2. **Emitir factura** → `POST /api/v1/public/integraciones/invoice`
3. **Descargar PDF** → `GET /api/v1/public/pdf/{clave_acceso}`
4. **Descargar XML** → `GET /api/v1/public/xml/{clave_acceso}`
""",
        routes=app.routes,
    )
    rutas_publicas = {
        "/api/v1/public/integraciones/validate",
        "/api/v1/public/integraciones/status",
        "/api/v1/public/integraciones/invoice",
        "/api/v1/public/pdf/{clave_acceso}",
        "/api/v1/public/xml/{clave_acceso}",
        "/api/v1/public/clientes/",
        "/api/v1/public/clientes/buscar",
        "/api/v1/public/clientes/{identificacion}",
    }
    schema["paths"] = {k: v for k, v in schema["paths"].items() if k in rutas_publicas}
    schema["components"]["securitySchemes"] = {
        "ApiKeyAuth": {
            "type": "apiKey", "in": "header", "name": "X-Api-Key",
            "description": "API Key desde Configuración → API Keys en app.kipu.ec"
        }
    }
    for path, path_item in schema["paths"].items():
        for method_data in path_item.values():
            method_data["security"] = [{"ApiKeyAuth": []}]
            if "integraciones" in path:              method_data["tags"] = ["🧾 Facturación"]
            elif "clientes" in path:                method_data["tags"] = ["👥 Clientes"]
            elif "pdf" in path or "xml" in path:    method_data["tags"] = ["📄 Documentos"]
    schemas_necesarios = {
        "ValidatePuntoRequest", "ClienteCreate", "ClienteBusquedaMasiva",
        "ClienteFactura", "ItemFactura", "PagoFactura",
        "HTTPValidationError", "ValidationError",
    }
    schema["components"]["schemas"] = {
        k: v for k, v in schema["components"]["schemas"].items()
        if k in schemas_necesarios
    }
    return JSONResponse(content=schema)