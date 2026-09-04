import asyncio
import time
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.openapi.docs import get_swagger_ui_html  # ← Importante para /api-docs
from contextlib import asynccontextmanager
from starlette.responses import Response as StarResponse
from app.core.cloudflare import es_ip_cloudflare

# Firebase
import app.core.firebase

# Cache / Redis
from app.core.cache import get_redis

# Config
from app.core.config import settings

# Workers
from app.workers.sri_worker import iniciar_workers
from app.workers.declaraciones_worker import iniciar_worker_declaraciones

# ─── ROUTERS APP ──────────────────────────────────────────────────────────────
from app.api.v1.app import (
    auth          as auth_app,
    emisor        as emisor_app,
    estructura    as estructura_app,
    clientes      as clientes_app,
    documentos    as documentos_app,
    recibidas     as recibidas_app,
    declaraciones as declaraciones_app,
    dashboard     as dashboard_app,
    apikeys       as apikeys_app,
    catalogo      as catalogo_app,
    notificaciones as notificaciones_app,
    productos     as productos_app,
    usuarios      as usuarios_app,
    creditos      as creditos_app,
    suscripcion   as suscripcion_app, 
    audit,
    cuentas       as cuentas_app,
    proformas     as proformas_app,
)

# ─── ROUTERS PUBLIC ───────────────────────────────────────────────────────────
from app.api.v1.public import (
    clientes      as clientes_public,
    integraciones as integraciones_public,
    documentos    as documentos_public,
    dev_docs      as dev_docs_public,
)

# ─── ROUTERS ADMIN ────────────────────────────────────────────────────────────
from app.api.v1.admin import (
    integraciones as integraciones_admin,
    panel         as panel_admin,
    stripe_webhook,
)


# =============================================================================
# LIFESPAN
# =============================================================================

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


# =============================================================================
# APP
# =============================================================================
ES_PRODUCCION = getattr(settings, "ENVIRONMENT", "development") == "production"

app = FastAPI(
    title            = "Kipu Core API",
    description      = "Backend de facturación electrónica SRI Ecuador",
    version          = "3.0.0",
    lifespan         = lifespan,
    redirect_slashes = False,
    
    # 🔒 En producción desactiva la documentación completa e interna
    docs_url         = None if ES_PRODUCCION else "/docs",
    redoc_url        = None if ES_PRODUCCION else "/redoc",
    openapi_url      = None if ES_PRODUCCION else "/openapi.json",
)


# =============================================================================
# OPENAPI PERSONALIZADO (INTERNO / FULL)
# =============================================================================

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title       = "Kipu Core API",
        version     = "3.0.0",
        description = "Backend de facturación electrónica SRI Ecuador",
        routes      = app.routes,
    )
    schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type":         "http",
            "scheme":       "bearer",
            "bearerFormat": "JWT",
            "description":  "Token Firebase — cópialo desde la app web",
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


# =============================================================================
# CORS
# =============================================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins    = ["*"],
    allow_credentials = False,
    allow_methods    = ["*"],
    allow_headers    = ["*"],
)


# =============================================================================
# HANDLER DE VALIDACIÓN
# =============================================================================

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    print("❌ ERROR DE VALIDACIÓN 422 ❌")
    print("Ruta:", request.url.path)
    errores = []
    for e in exc.errors():
        errores.append({
            "campo":          " → ".join(str(x) for x in e["loc"]),
            "mensaje":        e["msg"],
            "valor_recibido": str(e.get("input", "")),
        })
    return JSONResponse(status_code=422, content={"detail": errores})


# =============================================================================
# RATE LIMIT DE ALERTAS
# =============================================================================

async def _puede_alertar(path: str, status: int) -> bool:
    try:
        redis     = await get_redis()
        cache_key = f"kipu:alert:{status}:{path.replace('/', '_')}"
        if await redis.get(cache_key):
            return False
        await redis.setex(cache_key, 300, "1")
        return True
    except Exception as e:
        print(f"[Alert] ⚠️ Redis error: {e}")
        return True


# =============================================================================
# ENVÍO DE ALERTA POR EMAIL
# =============================================================================

async def _enviar_alerta_error(
    status: int, method: str, path: str, query: str,
    ip: str, ua: str, body_req: str, req_headers: dict, resp_body: str,
):
    nivel = "🔴 ERROR 5xx" if status >= 500 else "🟡 ERROR 4xx"
    color = "#cc0000"     if status >= 500 else "#cc8800"
    ahora = datetime.utcnow().strftime("%d/%m/%Y %H:%M:%S UTC")

    auth_header = req_headers.get("authorization", "")
    api_key     = req_headers.get("x-api-key", "")
    int_key     = req_headers.get("x-internal-key", "")

    if auth_header.startswith("Bearer "):
        auth_tipo    = "Firebase JWT"
        auth_detalle = f"Token: ...{auth_header[-12:]}"
    elif api_key:
        auth_tipo    = "API Key (cliente externo)"
        auth_detalle = f"Key: ...{api_key[-8:]}"
    elif int_key:
        auth_tipo    = "Clave Interna"
        auth_detalle = "Servicio interno"
    else:
        auth_tipo    = "Anónimo"
        auth_detalle = "Sin credenciales"

    headers_seguros = {
        k: ("***OCULTO***" if k.lower() in ("authorization", "x-api-key", "x-internal-key") else v)
        for k, v in req_headers.items()
    }
    headers_fmt = "\n".join(f"{k}: {v}" for k, v in headers_seguros.items())

    try:
        from app.services.mail_service import mail_service
        await mail_service.send_mail(
            to           = settings.ALERT_EMAIL_TO,
            subject      = f"[Kipu] {nivel} — {status} {method} {path}",
            html_content = f"""
            <div style="font-family:Arial,sans-serif;max-width:820px;color:#222">
              <h2 style="color:{color}">{nivel} — HTTP {status}</h2>
              <p style="color:#888;font-size:13px">⏱ {ahora}</p>
              <h3 style="color:{color}">📍 Solicitud</h3>
              <table border="1" cellpadding="8" cellspacing="0" style="border-collapse:collapse;font-size:13px;width:100%;margin-bottom:16px">
                <tr><td width="180"><b>Método</b></td><td><code>{method}</code></td></tr>
                <tr><td><b>Ruta</b></td><td><code>{path}</code></td></tr>
                <tr><td><b>Query</b></td><td><code>{query}</code></td></tr>
                <tr><td><b>Timestamp</b></td><td>{ahora}</td></tr>
              </table>
              <h3 style="color:{color}">🌐 Cliente</h3>
              <table border="1" cellpadding="8" cellspacing="0" style="border-collapse:collapse;font-size:13px;width:100%;margin-bottom:16px">
                <tr><td width="180"><b>IP</b></td><td><code>{ip}</code></td></tr>
                <tr><td><b>User-Agent</b></td><td>{ua}</td></tr>
                <tr><td><b>Origin</b></td><td>{req_headers.get('origin', '-')}</td></tr>
              </table>
              <h3 style="color:{color}">🔐 Autenticación</h3>
              <table border="1" cellpadding="8" cellspacing="0" style="border-collapse:collapse;font-size:13px;width:100%;margin-bottom:16px">
                <tr><td width="180"><b>Tipo</b></td><td><b>{auth_tipo}</b></td></tr>
                <tr><td><b>Detalle</b></td><td><code>{auth_detalle}</code></td></tr>
              </table>
              <h3 style="color:{color}">📦 Body</h3>
              <pre style="background:#f8f8f8;border:1px solid #ddd;padding:12px;font-size:12px;white-space:pre-wrap">{body_req}</pre>
              <h3 style="color:{color}">💬 Respuesta</h3>
              <pre style="background:#fff0f0;border:1px solid #ffcccc;padding:12px;font-size:12px;white-space:pre-wrap">{resp_body[:3000]}</pre>
              <h3 style="color:{color}">🔧 Headers</h3>
              <pre style="background:#f8f8f8;border:1px solid #ddd;padding:12px;font-size:11px;white-space:pre-wrap">{headers_fmt}</pre>
              <hr>
              <p style="color:#aaa;font-size:11px">Kipu Core API — Alertas automáticas</p>
            </div>
            """,
        )
        print(f"[Alert] ✅ Alerta enviada: {status} {method} {path}")
    except Exception as e:
        print(f"[Alert] ❌ Error enviando alerta: {e}")


# =============================================================================
# MIDDLEWARE — LOGS + ALERTAS
# =============================================================================

async def set_body(request: Request, body: bytes):
    async def receive():
        return {"type": "http.request", "body": body}
    request._receive = receive

@app.middleware("http")
async def log_y_alertas(request: Request, call_next):
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
            data_log = f"Body: {decoded[:150]}{'... [truncado]' if len(decoded) > 150 else ''}"
        except Exception:
            data_log = "Body: [Binario]"

    process_time_ms = (time.time() - start_time) * 1000
    status          = response.status_code
    path            = request.url.path

    print(f"   [{request.method}] {status} | {process_time_ms:.2f}ms | {data_log}", flush=True)
    response.headers["X-Process-Time-Ms"] = str(round(process_time_ms, 2))

    if getattr(settings, "ALERT_EMAIL_ERRORS", False) and status >= 500:
        rutas_ignoradas = {"/", "/docs", "/openapi.json", "/api-docs", "/openapi-public.json", "/redoc", "/favicon.ico"}
        if path not in rutas_ignoradas and not path.startswith("/wp-"):
            if await _puede_alertar(path, status):
                resp_body_bytes = b""
                try:
                    async for chunk in response.body_iterator:
                        resp_body_bytes += chunk
                    response = StarResponse(
                        content     = resp_body_bytes,
                        status_code = status,
                        headers     = dict(response.headers),
                        media_type  = response.media_type,
                    )
                except Exception as e:
                    print(f"[Alert] ⚠️ No se pudo leer body: {e}")

                asyncio.create_task(_enviar_alerta_error(
                    status      = status,
                    method      = request.method,
                    path        = path,
                    query       = str(request.query_params) or "-",
                    ip          = request.client.host if request.client else "-",
                    ua          = request.headers.get("user-agent", "-"),
                    body_req    = data_log,
                    req_headers = dict(request.headers),
                    resp_body   = resp_body_bytes.decode("utf-8", errors="replace")[:3000],
                ))

    return response


# =============================================================================
# MIDDLEWARE — CLOUDFLARE
# =============================================================================

@app.middleware("http")
async def validar_cloudflare(request: Request, call_next):
    if not getattr(settings, "CLOUDFLARE_ONLY", False):
        return await call_next(request)

    cf_ip = request.headers.get("cf-connecting-ip", "")
    if not cf_ip:
        ip_servidor = request.client.host if request.client else ""
        if es_ip_cloudflare(ip_servidor):
            return await call_next(request)
        print(f"[CF] ⛔ Sin CF-Connecting-IP — IP: {ip_servidor}")
        return JSONResponse(status_code=403, content={"error": "Acceso no autorizado."})

    return await call_next(request)


# =============================================================================
# RUTAS — APP
# =============================================================================

app.include_router(auth_app.router,          prefix="/api/v1/app/auth",                    tags=["📱 Auth"])
app.include_router(emisor_app.router,        prefix="/api/v1/app/emisor",                  tags=["📱 Emisor"])
app.include_router(estructura_app.router,    prefix="/api/v1/app/estructura",              tags=["📱 Estructura"])
app.include_router(usuarios_app.router,      prefix="/api/v1/app/usuarios",                tags=["📱 Usuarios"])
app.include_router(clientes_app.router,      prefix="/api/v1/app/clientes",                tags=["📱 Clientes"])
app.include_router(cuentas_app.router,       prefix="/api/v1/app/cuentas",                   tags=["📱 Cuentas"])
app.include_router(productos_app.router,     prefix="/api/v1/app/productos",               tags=["📱 Productos"])
app.include_router(catalogo_app.router,      prefix="/api/v1/app/catalogo",                tags=["📱 Catálogo"])
app.include_router(documentos_app.router,    prefix="/api/v1/app/documentos",              tags=["📱 Documentos Emitidos"])
app.include_router(recibidas_app.router,     prefix="/api/v1/app/recibidos",               tags=["📱 Documentos Recibidos"])
app.include_router(declaraciones_app.router, prefix="/api/v1/app/declaraciones",           tags=["📱 Declaraciones"])
app.include_router(dashboard_app.router,     prefix="/api/v1/app/dashboard",               tags=["📱 Dashboard"])
app.include_router(apikeys_app.router,       prefix="/api/v1/app/apikeys",                 tags=["📱 API Keys"])
app.include_router(notificaciones_app.router,prefix="/api/v1/app/notificaciones",          tags=["📱 Notificaciones"])
app.include_router(suscripcion_app.router,   prefix="/api/v1/app/suscripcion",             tags=["📱 Suscripción"])
app.include_router(creditos_app.router,      prefix="/api/v1/app/creditos",                tags=["📱 Créditos API"])
app.include_router(audit.router, prefix="/api/v1/app/audit", tags=["Auditoría"])
app.include_router(proformas_app.router, prefix="/api/v1/app/proformas", tags=["📱 Proformas"])

# =============================================================================
# RUTAS — PUBLIC (SOLO ESTAS LLEVAN "public_export")
# =============================================================================

app.include_router(documentos_public.router,    prefix="/api/v1/public",                  tags=["🌍 Documentos Públicos", "public_export"])
app.include_router(clientes_public.router,      prefix="/api/v1/public/clientes",         tags=["🌍 Clientes", "public_export"])
app.include_router(integraciones_public.router, prefix="/api/v1/public/integraciones",    tags=["🌍 API Externa", "public_export"])
app.include_router(dev_docs_public.router,      prefix="/api/v1/public",                  tags=["📖 Dev Docs"])

# =============================================================================
# RUTAS — ADMIN
# =============================================================================

app.include_router(integraciones_admin.router, prefix="/api/v1/admin",         tags=["🔧 Admin - Integraciones"])
app.include_router(panel_admin.router,         prefix="/api/v1/admin/panel",   tags=["🔧 Admin - Panel"])
app.include_router(stripe_webhook.router,      prefix="/api/v1/admin/stripe",  tags=["💳 Stripe"])


# =============================================================================
# HEALTH CHECK
# =============================================================================

@app.get("/", tags=["Health"])
async def root():
    return {
        "status":   "Kipu API v0.1.0 🚀",
        "api_docs": "/api-docs",
    }


# =============================================================================
# DOCUMENTACIÓN PÚBLICA DE SWAGGER Y ESQUEMA OPENAPI
# =============================================================================

@app.get("/api-docs", include_in_schema=False)
async def swagger_publico():
    """Renderiza la interfaz visual de Swagger UI para desarrolladores externos."""
    return get_swagger_ui_html(
        openapi_url="/openapi-public.json",
        title="Kipu — Documentación Pública API",
        swagger_favicon_url="https://fastapi.tiangolo.com/img/favicon.png",
    )


@app.get("/openapi-public.json", include_in_schema=False)
async def openapi_publico():
    """Genera el JSON de OpenAPI filtrando NADA por defecto, salvo lo etiquetado."""
    schema = get_openapi(
        title="Kipu — API de Facturación Electrónica",
        version="0.1.0",
        description="""

Integra facturación electrónica SRI en tu sistema en minutos.

## Autenticación
`X-Api-Key: tu_api_key_aqui`  
Obtén tu API Key desde **Configuración → API Keys** en [app.kipu.ec](https://app.kipu.ec).

## Flujo básico
1. **Validar** → `POST /api/v1/public/integraciones/validate`
2. **Emitir** → `POST /api/v1/public/integraciones/invoice`
3. **PDF** → `GET /api/v1/public/pdf/{clave_acceso}`
4. **XML** → `GET /api/v1/public/xml/{clave_acceso}`
        """,
        routes=app.routes,
    )

    paths_publicos = {}

    # Por defecto NADA se muestra
    for path, path_item in schema.get("paths", {}).items():
        metodos_filtrados = {}

        for method, operation in path_item.items():
            tags = operation.get("tags", [])

            # REGLA: Si NO tiene la etiqueta 'public_export', SE IGNORA POR COMPLETO
            if "public_export" in tags:
                # Removemos la etiqueta 'public_export' para que no ensucie la UI
                operation["tags"] = [t for t in tags if t != "public_export"]
                
                # Asignamos la seguridad con API Key
                operation["security"] = [{"ApiKeyAuth": []}]
                
                metodos_filtrados[method] = operation

        if metodos_filtrados:
            paths_publicos[path] = metodos_filtrados

    # Reemplazamos todos los paths por ÚNICAMENTE los aprobados
    schema["paths"] = paths_publicos

    # Configuración de Seguridad global
    schema["components"]["securitySchemes"] = {
        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-Api-Key",
            "description": "API Key desde Configuración → API Keys en app.kipu.ec",
        }
    }

    return JSONResponse(content=schema)