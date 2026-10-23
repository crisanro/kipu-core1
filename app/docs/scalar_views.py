from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from app.docs.openapi_schemas import generate_public_openapi_json

router = APIRouter(tags=["📖 Documentación Scalar"])

@router.get("/scalar", include_in_schema=False)
async def scalar_docs_privado():
    """Renderiza Scalar UI para la API completa (Interna)."""
    return HTMLResponse(content="""
    <!doctype html>
    <html>
      <head>
        <title>Kipu Core API — Docs Internos</title>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </head>
      <body>
        <script id="api-reference" data-url="/openapi.json"></script>
        <script src="https://cdn.jsdelivr.net/npm/@scalar/api-reference"></script>
      </body>
    </html>
    """)


@router.get("/api-docs", include_in_schema=False)
async def scalar_docs_publico():
    """Renderiza Scalar UI para la API pública de desarrolladores externos."""
    return HTMLResponse(content="""
    <!doctype html>
    <html>
      <head>
        <title>Kipu — Documentación Pública API</title>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </head>
      <body>
        <script 
          id="api-reference" 
          data-url="/openapi-public.json"
          data-configuration='{
            "theme": "purple",
            "darkMode": true,
            "showSidebar": true,
            "searchHotKey": "k"
          }'>
        </script>
        <script src="https://cdn.jsdelivr.net/npm/@scalar/api-reference"></script>
      </body>
    </html>
    """)


@router.get("/openapi-public.json", include_in_schema=False)
async def openapi_publico(request: Request):
    """Endpoint para exponer el schema OpenAPI de endpoints públicos."""
    return generate_public_openapi_json(request.app)