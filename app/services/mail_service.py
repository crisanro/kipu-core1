# app/services/mail_service.py
import html
import smtplib
import asyncio
import xmltodict
from email.message import EmailMessage
from email.utils import formataddr
from app.core.config import settings

# =============================================================================
# MARCA — ajusta cuando tengas logo y colores definidos
# =============================================================================
KIPU_LOGO_URL   = "https://cdn1.kipu.ec/kipu/kipu-mail.png"  # ← reemplazar
KIPU_COLOR_MAIN = "#1B9670"                               # ← reemplazar
KIPU_WEBSITE    = "https://kipu.ec"

TIPO_DOC_LABEL = {
    "FAC": "Factura",
    "LIQ": "Liquidación",
    "NCR": "Nota de Crédito",
    "NDB": "Nota de Débito",
    "RET": "Retención",
}


# =============================================================================
# HELPERS DE TEMPLATE
# =============================================================================

def _extraer_total_y_comprador(xml_str: str) -> tuple[str, str]:
    """Extrae importeTotal y razonSocialComprador del XML autorizado."""
    try:
        doc  = xmltodict.parse(xml_str)
        fact = doc.get("factura") or doc.get("liquidacionCompra") or {}
        info = (
            fact.get("infoFactura")
            or fact.get("infoLiquidacionCompra")
            or {}
        )
        total     = info.get("importeTotal", "0.00")
        comprador = (
            info.get("razonSocialComprador")
            or info.get("razonSocial")
            or "Consumidor Final"
        )
        return str(total), str(comprador)
    except Exception:
        return "0.00", "Consumidor Final"


def _build_html_comprobante(
    razon_social: str,
    ruc: str,
    tipo_label: str,
    secuencial: str,
    clave_acceso: str,
    fecha_autorizacion: str,
    total: str,
    nombre_comprador: str,
    es_sandbox: bool,
) -> str:

    sandbox_banner = ""
    if es_sandbox:
        sandbox_banner = """
        <tr>
          <td style="background-color:#F59E0B;padding:10px 30px;text-align:center;">
            <span style="color:#ffffff;font-family:Arial,sans-serif;
                         font-size:13px;font-weight:bold;">
              🧪 AMBIENTE DE PRUEBAS — Este comprobante no tiene validez tributaria
            </span>
          </td>
        </tr>
        """

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{tipo_label} Electrónica — {secuencial}</title>
</head>
<body style="margin:0;padding:0;background-color:#F3F4F6;font-family:Arial,sans-serif;">

  <table width="100%" cellpadding="0" cellspacing="0"
         style="background-color:#F3F4F6;padding:30px 0;">
    <tr>
      <td align="center">
        <table width="600" cellpadding="0" cellspacing="0"
               style="max-width:600px;width:100%;background-color:#ffffff;
                      border-radius:8px;overflow:hidden;
                      box-shadow:0 2px 8px rgba(0,0,0,0.08);">

          <!-- SANDBOX BANNER -->
          {sandbox_banner}

          <!-- HEADER -->
          <tr>
            <td style="background-color:{KIPU_COLOR_MAIN};
                       padding:28px 30px;text-align:center;">
              <img src="{KIPU_LOGO_URL}" alt="Kipu" width="130"
                   style="display:block;margin:0 auto;">
            </td>
          </tr>

          <!-- TÍTULO -->
          <tr>
            <td style="padding:32px 30px 16px;text-align:center;">
              <p style="margin:0 0 6px;font-size:12px;color:#6B7280;
                        text-transform:uppercase;letter-spacing:1px;">
                {tipo_label} Electrónica Autorizada por el SRI
              </p>
              <h1 style="margin:0;font-size:28px;font-weight:bold;color:#111827;">
                {secuencial}
              </h1>
            </td>
          </tr>

          <!-- CUERPO -->
          <tr>
            <td style="padding:8px 30px 28px;">

              <!-- Tarjeta info -->
              <table width="100%" cellpadding="0" cellspacing="0"
                     style="background-color:#F9FAFB;border-radius:6px;
                            border:1px solid #E5E7EB;margin-bottom:20px;">

                <!-- Emisor -->
                <tr>
                  <td style="padding:16px 20px;border-bottom:1px solid #E5E7EB;">
                    <p style="margin:0;font-size:11px;color:#9CA3AF;
                              text-transform:uppercase;letter-spacing:0.5px;">
                      Emisor
                    </p>
                    <p style="margin:4px 0 0;font-size:15px;
                              font-weight:bold;color:#111827;">
                      {razon_social}
                    </p>
                    <p style="margin:2px 0 0;font-size:13px;color:#6B7280;">
                      RUC: {ruc}
                    </p>
                  </td>
                </tr>

                <!-- Receptor -->
                <tr>
                  <td style="padding:16px 20px;border-bottom:1px solid #E5E7EB;">
                    <p style="margin:0;font-size:11px;color:#9CA3AF;
                              text-transform:uppercase;letter-spacing:0.5px;">
                      Receptor
                    </p>
                    <p style="margin:4px 0 0;font-size:15px;
                              font-weight:bold;color:#111827;">
                      {nombre_comprador}
                    </p>
                  </td>
                </tr>

                <!-- Fecha autorización -->
                <tr>
                  <td style="padding:16px 20px;border-bottom:1px solid #E5E7EB;">
                    <p style="margin:0;font-size:11px;color:#9CA3AF;
                              text-transform:uppercase;letter-spacing:0.5px;">
                      Fecha de autorización
                    </p>
                    <p style="margin:4px 0 0;font-size:14px;color:#374151;">
                      {fecha_autorizacion}
                    </p>
                  </td>
                </tr>

                <!-- Clave de acceso -->
                <tr>
                  <td style="padding:16px 20px;">
                    <p style="margin:0;font-size:11px;color:#9CA3AF;
                              text-transform:uppercase;letter-spacing:0.5px;">
                      Clave de acceso
                    </p>
                    <p style="margin:4px 0 0;font-size:11px;color:#6B7280;
                              word-break:break-all;font-family:monospace;
                              background:#F3F4F6;padding:8px;border-radius:4px;">
                      {clave_acceso}
                    </p>
                  </td>
                </tr>
              </table>

              <!-- Total -->
              <table width="100%" cellpadding="0" cellspacing="0"
                     style="background-color:{KIPU_COLOR_MAIN};
                            border-radius:6px;margin-bottom:24px;">
                <tr>
                  <td style="padding:22px;text-align:center;">
                    <p style="margin:0 0 4px;font-size:12px;
                              color:rgba(255,255,255,0.75);
                              text-transform:uppercase;letter-spacing:1px;">
                      Total del comprobante
                    </p>
                    <p style="margin:0;font-size:36px;
                              font-weight:bold;color:#ffffff;">
                      ${total}
                    </p>
                  </td>
                </tr>
              </table>

              <!-- Nota adjuntos -->
              <p style="margin:0 0 6px;font-size:14px;
                        color:#374151;text-align:center;">
                Adjuntamos el comprobante en formato
                <strong>PDF</strong> y <strong>XML</strong> para sus registros.
              </p>
              <p style="margin:0;font-size:13px;color:#9CA3AF;text-align:center;">
                Puede verificar este comprobante en el portal del SRI
                usando la clave de acceso.
              </p>

            </td>
          </tr>

          <!-- FOOTER -->
          <tr>
            <td style="background-color:#F9FAFB;border-top:1px solid #E5E7EB;
                       padding:20px 30px;text-align:center;">
              <p style="margin:0;font-size:12px;color:#9CA3AF;">
                Comprobante emitido mediante
                <a href="{KIPU_WEBSITE}"
                   style="color:{KIPU_COLOR_MAIN};text-decoration:none;
                          font-weight:bold;">
                  kipu.ec
                </a>
                — Facturación Electrónica Ecuador
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>

</body>
</html>"""


def _build_html_cuenta(
    titulo: str,
    mensaje: str,
    boton: str,
    link: str,
    saludo: str | None = None,
    nota: str | None = None,
) -> str:
    """Plantilla para correos de cuenta: verificación, contraseña, etc."""
    saludo_txt = f"Hola {html.escape(saludo)}," if saludo else "Hola,"
    link_attr  = html.escape(link, quote=True)
    nota_html  = (
        f"""<p style="margin:20px 0 0;font-size:12px;color:#9CA3AF;text-align:center;">
              {html.escape(nota)}
            </p>"""
        if nota else ""
    )

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html.escape(titulo)}</title>
</head>
<body style="margin:0;padding:0;background-color:#F3F4F6;font-family:Arial,sans-serif;">

  <table width="100%" cellpadding="0" cellspacing="0"
         style="background-color:#F3F4F6;padding:30px 0;">
    <tr>
      <td align="center">
        <table width="600" cellpadding="0" cellspacing="0"
               style="max-width:600px;width:100%;background-color:#ffffff;
                      border-radius:8px;overflow:hidden;
                      box-shadow:0 2px 8px rgba(0,0,0,0.08);">

          <!-- HEADER -->
          <tr>
            <td style="background-color:{KIPU_COLOR_MAIN};
                       padding:28px 30px;text-align:center;">
              <img src="{KIPU_LOGO_URL}" alt="Kipu" width="130"
                   style="display:block;margin:0 auto;">
            </td>
          </tr>

          <!-- CUERPO -->
          <tr>
            <td style="padding:32px 30px 28px;">
              <h1 style="margin:0 0 16px;font-size:22px;font-weight:bold;
                         color:#111827;text-align:center;">
                {html.escape(titulo)}
              </h1>
              <p style="margin:0 0 8px;font-size:15px;color:#374151;">
                {saludo_txt}
              </p>
              <p style="margin:0 0 24px;font-size:15px;line-height:1.5;color:#374151;">
                {html.escape(mensaje)}
              </p>

              <!-- Botón -->
              <table cellpadding="0" cellspacing="0" align="center" style="margin:0 auto;">
                <tr>
                  <td style="background-color:{KIPU_COLOR_MAIN};border-radius:6px;">
                    <a href="{link_attr}"
                       style="display:inline-block;padding:14px 28px;font-size:15px;
                              font-weight:bold;color:#ffffff;text-decoration:none;">
                      {html.escape(boton)}
                    </a>
                  </td>
                </tr>
              </table>

              <!-- Link alternativo -->
              <p style="margin:24px 0 6px;font-size:12px;color:#6B7280;text-align:center;">
                Si el botón no funciona, copia y pega este enlace en tu navegador:
              </p>
              <p style="margin:0;font-size:11px;color:#6B7280;word-break:break-all;
                        font-family:monospace;background:#F3F4F6;padding:8px;
                        border-radius:4px;">
                <a href="{link_attr}" style="color:#6B7280;">{html.escape(link)}</a>
              </p>

              {nota_html}
            </td>
          </tr>

          <!-- FOOTER -->
          <tr>
            <td style="background-color:#F9FAFB;border-top:1px solid #E5E7EB;
                       padding:20px 30px;text-align:center;">
              <p style="margin:0;font-size:12px;color:#9CA3AF;">
                <a href="{KIPU_WEBSITE}"
                   style="color:{KIPU_COLOR_MAIN};text-decoration:none;
                          font-weight:bold;">
                  kipu.ec
                </a>
                — Facturación Electrónica Ecuador
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>

</body>
</html>"""


def _build_text_cuenta(
    titulo: str,
    mensaje: str,
    link: str,
    saludo: str | None = None,
    nota: str | None = None,
) -> str:
    partes = [
        titulo,
        "",
        f"Hola {saludo}," if saludo else "Hola,",
        "",
        mensaje,
        "",
        link,
    ]
    if nota:
        partes += ["", nota]
    partes += ["", "— Kipu · kipu.ec"]
    return "\n".join(partes)


# =============================================================================
# EMAIL SERVICE
# =============================================================================

class EmailService:

    def __init__(self):
        self.enabled = bool(settings.SMTP_HOST and settings.SMTP_USER)
        if not self.enabled:
            print("⚠️ SMTP no configurado. El servicio de correo estará deshabilitado.")

    def _send_sync(self, msg: EmailMessage) -> bool:
        try:
            timeout_sec = 15
            if settings.SMTP_PORT == 465:
                server = smtplib.SMTP_SSL(
                    settings.SMTP_HOST, settings.SMTP_PORT,
                    timeout=timeout_sec,
                )
            else:
                server = smtplib.SMTP(
                    settings.SMTP_HOST, settings.SMTP_PORT,
                    timeout=timeout_sec,
                )
                server.starttls()

            server.login(settings.SMTP_USER, settings.SMTP_PASS)
            server.send_message(msg)
            server.quit()
            return True
        except Exception as e:
            print(f"❌ [Email Error] {str(e)}")
            return False

    async def send_mail(
        self,
        to: str,
        subject: str,
        html_content: str,
        attachments: list = None,
        from_name: str = None,
        text_content: str = None,   # ← versión texto plano (opcional)
    ) -> dict:
        if not self.enabled:
            return {"exito": False, "mensaje": "SMTP no configurado"}

        smtp_address = settings.SMTP_FROM or settings.SMTP_USER

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["To"]      = to

        # ── From con nombre personalizado ─────────────────────────────────────
        # formataddr genera: "Nombre del Emisor <no-reply@kipu.ec>"
        # Si no viene from_name, usa "Kipu" como fallback
        display_name   = from_name or "Kipu"
        msg["From"]    = formataddr((display_name, smtp_address))

        msg.set_content(
            text_content
            or "El contenido de este mensaje requiere un lector de correos "
               "compatible con HTML."
        )
        msg.add_alternative(html_content, subtype="html")

        if attachments:
            for att in attachments:
                msg.add_attachment(
                    att["content"],
                    maintype=att.get("maintype", "application"),
                    subtype=att.get("subtype",  "octet-stream"),
                    filename=att["filename"],
                )

        success = await asyncio.to_thread(self._send_sync, msg)

        if success:
            print(f"📧 [Email] Enviado a {to} (from: {display_name})")
            return {"exito": True}

        return {"exito": False, "error": "No se pudo entregar el correo."}

    async def send_comprobante(
        self,
        email: str,
        razon_social: str,
        ruc: str,
        tipo_doc: str,
        secuencial: str,
        clave_acceso: str,
        fecha_autorizacion: str,
        xml_str: str,
        pdf_bytes: bytes | None,
        es_sandbox: bool = False,
    ) -> dict:
        """
        Método de alto nivel para enviar comprobantes electrónicos.
        El From mostrará la razón social del emisor, no "Kipu".
        """
        tipo_label       = TIPO_DOC_LABEL.get(tipo_doc, "Comprobante")
        total, comprador = _extraer_total_y_comprador(xml_str)
        prefijo          = "[SANDBOX] " if es_sandbox else ""
        subject          = f"{prefijo}{tipo_label} Electrónica — {razon_social} — {secuencial}"

        html_content = _build_html_comprobante(
            razon_social       = razon_social,
            ruc                = ruc,
            tipo_label         = tipo_label,
            secuencial         = secuencial,
            clave_acceso       = clave_acceso,
            fecha_autorizacion = fecha_autorizacion,
            total              = total,
            nombre_comprador   = comprador,
            es_sandbox         = es_sandbox,
        )

        attachments = [{
            "filename": f"{clave_acceso}.xml",
            "content":  xml_str.encode("utf-8"),
            "maintype": "text",
            "subtype":  "xml",
        }]
        if pdf_bytes:
            attachments.append({
                "filename": f"{clave_acceso}.pdf",
                "content":  pdf_bytes,
                "maintype": "application",
                "subtype":  "pdf",
            })

        return await self.send_mail(
            to           = email,
            subject      = subject,
            html_content = html_content,
            attachments  = attachments,
            from_name    = razon_social,  # ← el comprador ve el nombre del emisor
        )

    # ── Correos de cuenta ─────────────────────────────────────────────────────

    async def send_link_verificacion(
        self,
        email: str,
        link: str,
        nombre: str | None = None,
    ) -> dict:
        titulo  = "Verifica tu correo"
        mensaje = (
            "Recibimos tu registro en Kipu. Para activar tu cuenta y empezar "
            "a facturar, confirma tu correo con el botón de abajo."
        )
        nota    = "Si no creaste una cuenta en Kipu, puedes ignorar este mensaje."

        return await self.send_mail(
            to           = email,
            subject      = "Verifica tu correo en Kipu",
            html_content = _build_html_cuenta(titulo, mensaje, "Verificar mi correo", link, nombre, nota),
            text_content = _build_text_cuenta(titulo, mensaje, link, nombre, nota),
            from_name    = "Kipu",
        )

    async def send_link_password(
        self,
        email: str,
        link: str,
        nombre: str | None = None,
    ) -> dict:
        titulo  = "Restablece tu contraseña"
        mensaje = (
            "Recibimos una solicitud para restablecer la contraseña de tu cuenta "
            "en Kipu. Crea una nueva con el botón de abajo."
        )
        nota    = (
            "Por seguridad, este enlace vence pronto. Si no solicitaste este "
            "cambio, ignora este correo: tu contraseña actual sigue funcionando."
        )

        return await self.send_mail(
            to           = email,
            subject      = "Restablece tu contraseña de Kipu",
            html_content = _build_html_cuenta(titulo, mensaje, "Crear nueva contraseña", link, nombre, nota),
            text_content = _build_text_cuenta(titulo, mensaje, link, nombre, nota),
            from_name    = "Kipu",
        )


# Instancia global
mail_service = EmailService()