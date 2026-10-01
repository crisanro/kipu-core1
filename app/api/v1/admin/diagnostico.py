# app/api/v1/admin/diagnostico.py
#
# Diagnóstico de correo: configuración SMTP, DNS del dominio (SPF/DKIM/DMARC)
# y envío de prueba con el error exacto de cada paso.

import asyncio
import json
import re
import secrets
import smtplib
import time
import urllib.parse
import urllib.request
from datetime import datetime
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.core.config import settings
from app.core.security import verify_firebase_token

router = APIRouter(prefix="/diagnostico")

TZ_EC = ZoneInfo("America/Guayaquil")


# =============================================================================
# GUARD SUPERADMIN (copia local para evitar import circular con panel.py)
# =============================================================================
async def verify_superadmin(auth_data: dict = Depends(verify_firebase_token)):
    if auth_data.get("role") != "superadmin":
        raise HTTPException(status_code=403, detail="Acceso restringido.")
    return auth_data


class ProbarCorreoRequest(BaseModel):
    destino:       Optional[str] = None
    solo_conexion: bool          = False


# =============================================================================
# HELPERS
# =============================================================================
def _dominio(addr: Optional[str]) -> Optional[str]:
    if addr and "@" in addr:
        return addr.split("@")[-1].strip().lower()
    return None


def _mask(user: Optional[str]) -> Optional[str]:
    if not user:
        return None
    if "@" in user:
        local, dom = user.split("@", 1)
        return f"{local[:2]}***@{dom}"
    return f"{user[:2]}***"


def _dns_txt(nombre: str) -> list[str]:
    """Consulta TXT vía DNS-over-HTTPS (Google). Sin dependencias extra."""
    url = f"https://dns.google/resolve?name={urllib.parse.quote(nombre)}&type=TXT"
    with urllib.request.urlopen(url, timeout=6) as r:
        data = json.loads(r.read().decode())
    out = []
    for a in data.get("Answer", []) or []:
        if a.get("type") != 16:
            continue
        raw    = a.get("data", "")
        partes = re.findall(r'"([^"]*)"', raw)
        out.append("".join(partes) if partes else raw)
    return out


def _revisar_registro(nombre: str, prefijo: str) -> dict:
    try:
        registros = _dns_txt(nombre)
    except Exception as e:
        return {"ok": False, "registro": None, "detalle": f"No se pudo consultar DNS: {e}"}
    match = next((r for r in registros if r.lower().startswith(prefijo.lower())), None)
    if match:
        return {"ok": True, "registro": match, "detalle": "Registro encontrado."}
    return {"ok": False, "registro": None, "detalle": f"No existe registro {prefijo} en {nombre}."}


def _check_dns_sync(dominio: str, selector: Optional[str]) -> dict:
    spf   = _revisar_registro(dominio, "v=spf1")
    dmarc = _revisar_registro(f"_dmarc.{dominio}", "v=DMARC1")
    dkim  = None
    if selector:
        nombre = f"{selector.strip()}._domainkey.{dominio}"
        try:
            registros = _dns_txt(nombre)
            match = next((r for r in registros if "p=" in r), None)
            dkim = (
                {"ok": True,  "registro": match[:120] + ("…" if len(match) > 120 else ""), "detalle": "Clave DKIM publicada."}
                if match else
                {"ok": False, "registro": None, "detalle": f"No hay clave DKIM en {nombre}."}
            )
        except Exception as e:
            dkim = {"ok": False, "registro": None, "detalle": f"No se pudo consultar DNS: {e}"}
    return {"spf": spf, "dmarc": dmarc, "dkim": dkim}


def _html_prueba(codigo: str, fecha: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8"></head>
<body style="margin:0;padding:30px 0;background:#F3F4F6;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center">
    <table width="520" cellpadding="0" cellspacing="0"
           style="max-width:520px;width:100%;background:#fff;border-radius:8px;padding:28px;">
      <tr><td>
        <h2 style="margin:0 0 12px;color:#111827;">Prueba de correo de Kipu ✅</h2>
        <p style="margin:0 0 8px;color:#374151;font-size:14px;">
          Si estás leyendo esto, el envío desde Kipu funciona y el correo llegó a esta bandeja.
        </p>
        <p style="margin:16px 0 4px;color:#6B7280;font-size:12px;">Código de prueba</p>
        <p style="margin:0;font-family:monospace;font-size:22px;font-weight:bold;color:#111827;">{codigo}</p>
        <p style="margin:16px 0 0;color:#9CA3AF;font-size:12px;">Enviado: {fecha}</p>
      </td></tr>
    </table>
  </td></tr></table>
</body></html>"""


def _probar_smtp_sync(destino: Optional[str]) -> dict:
    pasos: list[dict] = []
    t0    = time.perf_counter()
    etapa = "conexion"

    def marca(nombre: str, ok: bool, detalle: str = ""):
        pasos.append({
            "paso":    nombre,
            "ok":      ok,
            "ms":      round((time.perf_counter() - t0) * 1000),
            "detalle": detalle,
        })

    host, port   = settings.SMTP_HOST, settings.SMTP_PORT
    smtp_address = settings.SMTP_FROM or settings.SMTP_USER
    codigo       = secrets.token_hex(3).upper()
    message_id   = None
    server       = None

    try:
        if port == 465:
            server = smtplib.SMTP_SSL(host, port, timeout=15)
            marca("conexion", True, f"Conectado a {host}:{port} (SSL)")
        else:
            server = smtplib.SMTP(host, port, timeout=15)
            marca("conexion", True, f"Conectado a {host}:{port}")
            etapa = "tls"
            server.starttls()
            marca("tls", True, "STARTTLS negociado")

        etapa = "login"
        server.login(settings.SMTP_USER, settings.SMTP_PASS)
        marca("login", True, f"Autenticado como {_mask(settings.SMTP_USER)}")

        if destino:
            etapa = "envio"
            fecha = datetime.now(TZ_EC).strftime("%d/%m/%Y %H:%M:%S")
            msg   = EmailMessage()
            msg["Subject"]    = f"[Kipu] Prueba de correo · {codigo}"
            msg["From"]       = formataddr(("Kipu", smtp_address))
            msg["To"]         = destino
            msg["Date"]       = formatdate(localtime=True)
            message_id        = make_msgid(domain=_dominio(smtp_address) or "kipu.ec")
            msg["Message-ID"] = message_id
            msg.set_content(
                f"Prueba de correo de Kipu.\n\nCódigo: {codigo}\nEnviado: {fecha}\n\n"
                "Si lees esto, el envío funciona y el correo llegó a esta bandeja."
            )
            msg.add_alternative(_html_prueba(codigo, fecha), subtype="html")

            rechazados = server.send_message(msg)
            if rechazados:
                marca("envio", False, f"El servidor rechazó destinatarios: {rechazados}")
            else:
                marca("envio", True, f"El servidor SMTP aceptó el correo para {destino}")

        try:
            server.quit()
        except Exception:
            pass

    except smtplib.SMTPAuthenticationError as e:
        err = e.smtp_error.decode(errors="ignore") if isinstance(e.smtp_error, bytes) else str(e.smtp_error)
        marca(etapa, False, f"Credenciales rechazadas ({e.smtp_code}): {err}")
    except smtplib.SMTPRecipientsRefused as e:
        marca(etapa, False, f"Destinatario rechazado: {e.recipients}")
    except smtplib.SMTPSenderRefused as e:
        err = e.smtp_error.decode(errors="ignore") if isinstance(e.smtp_error, bytes) else str(e.smtp_error)
        marca(etapa, False, f"Remitente rechazado ({e.smtp_code}): {err} — revisa SMTP_FROM")
    except smtplib.SMTPException as e:
        marca(etapa, False, f"{type(e).__name__}: {e}")
    except Exception as e:
        marca(etapa, False, f"{type(e).__name__}: {e}")
    finally:
        if server:
            try:
                server.close()
            except Exception:
                pass

    return {
        "ok":         bool(pasos) and all(p["ok"] for p in pasos),
        "codigo":     codigo if destino else None,
        "destino":    destino,
        "message_id": message_id,
        "pasos":      pasos,
    }


# =============================================================================
# GET /diagnostico/correo/config
# =============================================================================
@router.get("/correo/config", summary="Configuración SMTP y DNS del dominio remitente")
async def correo_config(
    dkim_selector: Optional[str] = Query(None, max_length=63),
    auth_data:     dict          = Depends(verify_superadmin),
):
    smtp_from   = settings.SMTP_FROM or settings.SMTP_USER
    dom_from    = _dominio(smtp_from)
    dom_user    = _dominio(settings.SMTP_USER)
    habilitado  = bool(settings.SMTP_HOST and settings.SMTP_USER)

    dns = None
    if dom_from:
        dns = await asyncio.to_thread(_check_dns_sync, dom_from, dkim_selector)

    return {
        "ok": True,
        "data": {
            "habilitado":   habilitado,
            "host":         settings.SMTP_HOST,
            "port":         settings.SMTP_PORT,
            "modo":         "SSL" if settings.SMTP_PORT == 465 else "STARTTLS",
            "usuario":      _mask(settings.SMTP_USER),
            "remitente":    smtp_from,
            "dominio_from": dom_from,
            "dominio_user": dom_user,
            "alineado":     (dom_from == dom_user) if (dom_from and dom_user) else None,
            "dns":          dns,
        },
    }


# =============================================================================
# POST /diagnostico/correo/probar
# =============================================================================
@router.post("/correo/probar", summary="Probar conexión SMTP o enviar correo de prueba")
async def correo_probar(
    req:       ProbarCorreoRequest,
    auth_data: dict = Depends(verify_superadmin),
):
    if not (settings.SMTP_HOST and settings.SMTP_USER):
        raise HTTPException(status_code=400, detail="SMTP no configurado (SMTP_HOST / SMTP_USER vacíos).")

    destino = None
    if not req.solo_conexion:
        destino = (req.destino or "").strip()
        if "@" not in destino or len(destino) > 254:
            raise HTTPException(status_code=400, detail="Correo de destino inválido.")

    resultado = await asyncio.to_thread(_probar_smtp_sync, destino)
    print(f"[DIAG-CORREO] {'✅' if resultado['ok'] else '❌'} destino={destino} pasos={resultado['pasos']}")
    return {"ok": True, "data": resultado}