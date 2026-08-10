# main.py
import asyncio
import time
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from contextlib import asynccontextmanager
from starlette.responses import Response as StarResponse
from app.core.cloudflare import es_ip_cloudflare


# Firebase
import app.core.firebase

# Cache / Redis
from app.core.cache import get_redis

# Services / Config
from app.core.config import settings

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
    panel as panel_admin,
    stripe_webhook,
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
            "type":         "http",
            "scheme":       "bearer",
            "bearerFormat": "JWT",
            "description":  "Token Firebase — cópialo desde la app web"
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

# ─── HELPER RATE LIMIT DE ALERTAS ─────────────────────────────────────────────
async def _puede_alertar(path: str, status: int) -> bool:
    try:
        redis     = await get_redis()
        cache_key = f"kipu:alert:{status}:{path.replace('/', '_')}"
        existe    = await redis.get(cache_key)
        if existe:
            return False
        await redis.setex(cache_key, 300, "1")
        return True
    except Exception as e:
        print(f"[Alert] ⚠️ Redis rate limit error: {e}")
        return True

# ─── FUNCIÓN DE ENVÍO DE ALERTA ───────────────────────────────────────────────
async def _enviar_alerta_error(
    status:       int,
    method:       str,
    path:         str,
    query:        str,
    ip:           str,
    ua:           str,
    body_req:     str,
    req_headers:  dict,
    resp_body:    str,
):
    nivel = "🔴 ERROR 5xx" if status >= 500 else "🟡 ERROR 4xx"
    color = "#cc0000"     if status >= 500 else "#cc8800"
    ahora = datetime.utcnow().strftime("%d/%m/%Y %H:%M:%S UTC")

    # ── Autenticación ──────────────────────────────────────────────────────────
    auth_header = req_headers.get("authorization", "")
    api_key     = req_headers.get("x-api-key", "")
    int_key     = req_headers.get("x-internal-key", "")

    if auth_header.startswith("Bearer "):
        auth_tipo   = "Firebase JWT"
        auth_detalle = f"Token: ...{auth_header[-12:]}"
    elif api_key:
        auth_tipo   = "API Key (cliente externo)"
        auth_detalle = f"Key: ...{api_key[-8:]}"
    elif int_key:
        auth_tipo   = "Clave Interna"
        auth_detalle = "Servicio interno (Komand/Wappti/Kipu)"
    else:
        auth_tipo   = "Anónimo"
        auth_detalle = "Sin credenciales"

    # ── Headers seguros (ocultar secretos) ────────────────────────────────────
    headers_seguros = {
        k: ("***OCULTO***" if k.lower() in ("authorization", "x-api-key", "x-internal-key") else v)
        for k, v in req_headers.items()
    }
    headers_fmt = "\n".join(f"{k}: {v}" for k, v in headers_seguros.items())

    try:
        from app.services.mail_service import mail_service
        await mail_service.send_mail(
            to      = settings.ALERT_EMAIL_TO,
            subject = f"[Kipu] {nivel} — {status} {method} {path}",
            html_content = f"""
            <div style="font-family:Arial,sans-serif;max-width:820px;color:#222">

              <h2 style="color:{color};margin-bottom:4px">{nivel} — HTTP {status}</h2>
              <p style="color:#888;margin-top:0;font-size:13px">⏱ {ahora}</p>

              <!-- SOLICITUD -->
              <h3 style="border-bottom:2px solid {color};padding-bottom:6px;color:{color}">
                📍 Solicitud
              </h3>
              <table border="1" cellpadding="8" cellspacing="0"
                style="border-collapse:collapse;font-size:13px;width:100%;margin-bottom:16px">
                <tr style="background:#f9f9f9">
                  <td width="180"><b>Método</b></td>
                  <td><code style="background:#eee;padding:2px 6px">{method}</code></td>
                </tr>
                <tr>
                  <td><b>Ruta</b></td>
                  <td><code style="background:#eee;padding:2px 6px">{path}</code></td>
                </tr>
                <tr style="background:#f9f9f9">
                  <td><b>Query Params</b></td>
                  <td><code>{query}</code></td>
                </tr>
                <tr>
                  <td><b>Timestamp</b></td>
                  <td>{ahora}</td>
                </tr>
              </table>

              <!-- CLIENTE -->
              <h3 style="border-bottom:2px solid {color};padding-bottom:6px;color:{color}">
                🌐 Cliente
              </h3>
              <table border="1" cellpadding="8" cellspacing="0"
                style="border-collapse:collapse;font-size:13px;width:100%;margin-bottom:16px">
                <tr style="background:#f9f9f9">
                  <td width="180"><b>IP</b></td>
                  <td><code>{ip}</code></td>
                </tr>
                <tr>
                  <td><b>User-Agent</b></td>
                  <td style="font-size:12px">{ua}</td>
                </tr>
                <tr style="background:#f9f9f9">
                  <td><b>Origin</b></td>
                  <td>{req_headers.get('origin', '-')}</td>
                </tr>
                <tr>
                  <td><b>Referer</b></td>
                  <td>{req_headers.get('referer', '-')}</td>
                </tr>
                <tr style="background:#f9f9f9">
                  <td><b>Content-Type</b></td>
                  <td>{req_headers.get('content-type', '-')}</td>
                </tr>
                <tr>
                  <td><b>Accept-Language</b></td>
                  <td>{req_headers.get('accept-language', '-')}</td>
                </tr>
              </table>

              <!-- AUTENTICACIÓN -->
              <h3 style="border-bottom:2px solid {color};padding-bottom:6px;color:{color}">
                🔐 Autenticación
              </h3>
              <table border="1" cellpadding="8" cellspacing="0"
                style="border-collapse:collapse;font-size:13px;width:100%;margin-bottom:16px">
                <tr style="background:#f9f9f9">
                  <td width="180"><b>Tipo</b></td>
                  <td><b>{auth_tipo}</b></td>
                </tr>
                <tr>
                  <td><b>Detalle</b></td>
                  <td><code>{auth_detalle}</code></td>
                </tr>
                <tr style="background:#f9f9f9">
                  <td><b>Idempotency Key</b></td>
                  <td>{req_headers.get('x-idempotency-key', '-')}</td>
                </tr>
              </table>

              <!-- BODY DE LA SOLICITUD -->
              <h3 style="border-bottom:2px solid {color};padding-bottom:6px;color:{color}">
                📦 Body de la Solicitud
              </h3>
              <pre style="background:#f8f8f8;border:1px solid #ddd;padding:12px;
                border-radius:4px;font-size:12px;overflow-x:auto;
                white-space:pre-wrap;word-break:break-all">{body_req}</pre>

              <!-- RESPUESTA DEL SERVIDOR -->
              <h3 style="border-bottom:2px solid {color};padding-bottom:6px;color:{color}">
                💬 Respuesta del Servidor
              </h3>
              <pre style="background:#fff0f0;border:1px solid #ffcccc;padding:12px;
                border-radius:4px;font-size:12px;overflow-x:auto;
                white-space:pre-wrap;word-break:break-all">{resp_body[:3000]}</pre>

              <!-- HEADERS COMPLETOS -->
              <h3 style="border-bottom:2px solid {color};padding-bottom:6px;color:{color}">
                🔧 Headers de la Solicitud
              </h3>
              <pre style="background:#f8f8f8;border:1px solid #ddd;padding:12px;
                border-radius:4px;font-size:11px;overflow-x:auto;
                white-space:pre-wrap">{headers_fmt}</pre>

              <hr style="margin-top:24px;border:none;border-top:1px solid #eee">
              <p style="color:#aaa;font-size:11px">
                Kipu Core API — Sistema de alertas automáticas<br>
                Para deshabilitar: <code>ALERT_EMAIL_ERRORS=false</code> en .env
              </p>
            </div>
            """
        )
        print(f"[Alert] ✅ Alerta enviada: {status} {method} {path}")
    except Exception as e:
        print(f"[Alert] ❌ Error enviando alerta: {e}")

# ─── MIDDLEWARE DE LOGS + ALERTAS ─────────────────────────────────────────────
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

    # ── Log del request ────────────────────────────────────────────────────────
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
    status          = response.status_code
    path            = request.url.path

    print(f"   [{request.method}] {status} | {process_time_ms:.2f} ms | Data: {data_log}", flush=True)
    response.headers["X-Process-Time-Ms"] = str(round(process_time_ms, 2))

    # ── Alertas de error ───────────────────────────────────────────────────────
    if getattr(settings, "ALERT_EMAIL_ERRORS", False) and status >= 400:
        rutas_ignoradas = {"/", "/docs", "/openapi.json", "/api-docs", "/redoc", "/favicon.ico"}
        if path not in rutas_ignoradas and not path.startswith("/wp-"):
            if await _puede_alertar(path, status):
                # Leer body de la respuesta
                resp_body_bytes = b""
                try:
                    async for chunk in response.body_iterator:
                        resp_body_bytes += chunk
                    # Reconstruir respuesta
                    response = StarResponse(
                        content     = resp_body_bytes,
                        status_code = status,
                        headers     = dict(response.headers),
                        media_type  = response.media_type,
                    )
                except Exception as e:
                    print(f"[Alert] ⚠️ No se pudo leer body de respuesta: {e}")

                resp_body_str = resp_body_bytes.decode("utf-8", errors="replace")[:3000]

                asyncio.create_task(_enviar_alerta_error(
                    status      = status,
                    method      = request.method,
                    path        = path,
                    query       = str(request.query_params) or "-",
                    ip          = request.client.host if request.client else "-",
                    ua          = request.headers.get("user-agent", "-"),
                    body_req    = data_log,
                    req_headers = dict(request.headers),
                    resp_body   = resp_body_str,
                ))

    return response

# ─── MIDDLEWARE CLOUDFLARE ─────────────────────────────────────────────────────
@app.middleware("http")
async def validar_cloudflare(request: Request, call_next):
    if not getattr(settings, "CLOUDFLARE_ONLY", False):
        return await call_next(request)

    ip_servidor = request.client.host if request.client else ""

    if not es_ip_cloudflare(ip_servidor):
        print(f"[CF] ⛔ Bloqueado — IP no Cloudflare: {ip_servidor}")
        return JSONResponse(
            status_code = 403,
            content     = {"error": "Acceso no autorizado."}
        )

    return await call_next(request)

# ─── RUTAS ────────────────────────────────────────────────────────────────────
app.include_router(auth_app.router,           prefix="/api/v1/app/auth",              tags=["📱 App - Auth & Nuke"])
app.include_router(emisor_app.router,         prefix="/api/v1/app/emisor",            tags=["📱 App - Emisor & Config"])
app.include_router(estructura_app.router,     prefix="/api/v1/app/estructura",        tags=["📱 App - Estructura"])
app.include_router(productos_app.router,      prefix="/api/v1/app/productos",         tags=["📱 App - Productos"])
app.include_router(usuarios_app.router,       prefix="/api/v1/app/usuarios",          tags=["📱 App - Usuarios"])
app.include_router(clientes_app.router,       prefix="/api/v1/app/clientes",          tags=["📱 App - Clientes"])
app.include_router(invoices_app.router,       prefix="/api/v1/app/invoices",          tags=["📱 App - Facturación"])
app.include_router(dashboard_app.router,      prefix="/api/v1/app/dashboard",         tags=["📱 App - Dashboard"])
app.include_router(declaraciones_app.router,  prefix="/api/v1/app/declaraciones",     tags=["📱 App - Declaraciones"])
app.include_router(apikeys_app.router,        prefix="/api/v1/app/apikeys",           tags=["📱 App - API Keys"])
app.include_router(catalogo_app.router,       prefix="/api/v1/app/catalogo",          tags=["📱 App - Catálogo"])
app.include_router(recibidas_app.router,      prefix="/api/v1/app/invoices/received", tags=["📱 App - Facturas Recibidas"])
app.include_router(notificaciones_app.router, prefix="/api/v1/app/notificaciones",    tags=["📱 App - Notificaciones"])
app.include_router(creditos_app.router,       prefix="/api/v1/app/creditos",          tags=["📱 App - Créditos"])
app.include_router(notas_credito_app.router,  prefix="/api/v1/app/notas-credito",     tags=["📱 App - Notas de Crédito"])

app.include_router(integraciones_public.router, prefix="/api/v1/public/integraciones", tags=["🌍 API Facturación"])
app.include_router(invoices_public.router,       prefix="/api/v1/public",               tags=["🌍 API Facturación"])
app.include_router(clientes_public.router,       prefix="/api/v1/public/clientes",      tags=["🌍 API Facturación"])

app.include_router(integraciones_n8n.router,  prefix="/api/v1/admin",        tags=["🤖 n8n Automations - Core"])
app.include_router(panel_admin.router,         prefix="/api/v1/admin/panel",  tags=["🔧 Admin - Panel"])
app.include_router(stripe_webhook.router,      prefix="/api/v1/admin/stripe", tags=["💳 Stripe Webhook"])

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
            if "integraciones" in path:           method_data["tags"] = ["🧾 Facturación"]
            elif "clientes" in path:              method_data["tags"] = ["👥 Clientes"]
            elif "pdf" in path or "xml" in path:  method_data["tags"] = ["📄 Documentos"]
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