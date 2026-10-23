# app/core/http_clients.py
#
# Clientes HTTP compartidos a nivel de aplicación.
# Reutilizan conexiones TCP/TLS en vez de crear una nueva por request.
#
# Uso:
#   from app.core.http_clients import pdf_client, turnstile_client
#
# Cerrar en shutdown de la app:
#   await close_http_clients()

import httpx
from app.core.config import settings

# ─── Cliente para generación de PDF (Node signer) ───────────────────────────
pdf_client = httpx.AsyncClient(
    base_url=settings.NODE_SIGNER_URL,
    timeout=httpx.Timeout(15.0, connect=5.0),
    limits=httpx.Limits(
        max_connections=20,
        max_keepalive_connections=10,
    ),
)

# ─── Cliente para verificación Cloudflare Turnstile ──────────────────────────
turnstile_client = httpx.AsyncClient(
    base_url="https://challenges.cloudflare.com",
    timeout=httpx.Timeout(10.0, connect=5.0),
    limits=httpx.Limits(
        max_connections=10,
        max_keepalive_connections=5,
    ),
)


async def close_http_clients():
    """Cerrar clientes HTTP. Llamar en app shutdown."""
    await pdf_client.aclose()
    await turnstile_client.aclose()