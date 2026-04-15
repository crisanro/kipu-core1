import smtplib
from email.message import EmailMessage
import asyncio
from app.core.config import settings

class EmailService:
    def __init__(self):
        self.enabled = bool(settings.SMTP_HOST and settings.SMTP_USER)
        if not self.enabled:
            print("⚠️ SMTP no configurado. El servicio de correo estará deshabilitado.")

    def _send_sync(self, msg: EmailMessage):
        """Función síncrona interna para enviar el correo"""
        try:
            # Si el puerto es 465 usamos SMTP_SSL, sino SMTP normal
            if settings.SMTP_PORT == 465:
                server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT)
            else:
                server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT)
                server.starttls() # Asegura la conexión

            server.login(settings.SMTP_USER, settings.SMTP_PASS)
            server.send_message(msg)
            server.quit()
            return True
        except Exception as e:
            print(f"[Email Error] {str(e)}")
            return False

    async def send_mail(self, to: str, subject: str, html_content: str, attachments: list = None):
        if not self.enabled:
            return {"exito": False, "mensaje": "SMTP no configurado"}

        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = settings.SMTP_FROM or settings.SMTP_USER
        msg['To'] = to
        msg.set_content("Por favor activa HTML para ver este correo.")
        msg.add_alternative(html_content, subtype='html')

        # Adjuntar archivos (XML, PDF)
        if attachments:
            for att in attachments:
                msg.add_attachment(
                    att["content"], 
                    maintype=att.get("maintype", "application"), 
                    subtype=att.get("subtype", "octet-stream"), 
                    filename=att["filename"]
                )

        # Ejecutamos el envío en un hilo separado para no bloquear FastAPI
        success = await asyncio.to_thread(self._send_sync, msg)
        
        if success:
            print(f"[Email] Enviado a {to}")
            return {"exito": True}
        return {"exito": False, "error": "Fallo al enviar"}

# Instancia global
mail_service = EmailService()