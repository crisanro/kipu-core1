from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse

def build_custom_openapi(app: FastAPI):
    """Genera y cachea el esquema OpenAPI completo para la API interna."""
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title="Kipu Core API",
        version="3.0.0",
        description="Backend de facturación electrónica SRI Ecuador",
        routes=app.routes,
    )
    
    schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Token Firebase — cópialo desde la app web",
        }
    }

    for path, path_item in schema.get("paths", {}).items():
        if "/public/" in path or "/admin/" in path or path == "/":
            continue
        for method in path_item.values():
            method["security"] = [{"BearerAuth": []}]

    app.openapi_schema = schema
    return app.openapi_schema


def generate_public_openapi_json(app: FastAPI) -> JSONResponse:
    """Genera la especificación OpenAPI filtrada únicamente para integradores externos."""
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

    for path, path_item in schema.get("paths", {}).items():
        metodos_filtrados = {}

        for method, operation in path_item.items():
            tags = operation.get("tags", [])

            if "public_export" in tags:
                operation["tags"] = [t for t in tags if t != "public_export"]
                operation["security"] = [{"ApiKeyAuth": []}]
                metodos_filtrados[method] = operation

        if metodos_filtrados:
            paths_publicos[path] = metodos_filtrados

    schema["paths"] = paths_publicos
    schema["components"]["securitySchemes"] = {
        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-Api-Key",
            "description": "API Key desde Configuración → API Keys en app.kipu.ec",
        }
    }

    return JSONResponse(content=schema)