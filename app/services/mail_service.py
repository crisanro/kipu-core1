import smtplib
from email.message import EmailMessage
import asyncio
from app.core.config import settings

class EmailService:
    def __init__(self):
        # Verificamos si tenemos las credenciales mínimas
        self.enabled = bool(settings.SMTP_HOST and settings.SMTP_USER)
        if not self.enabled:
            print("⚠️ SMTP no configurado. El servicio de correo estará deshabilitado.")

    def _send_sync(self, msg: EmailMessage):
        """
        Función síncrona interna para enviar el correo.
        Se ejecuta en un hilo separado mediante asyncio.to_thread.
        """
        try:
            # AJUSTE: Añadimos un timeout de 15 segundos para evitar bloqueos infinitos
            timeout_sec = 15
            
            # Configuración de conexión según el puerto
            if settings.SMTP_PORT == 465:
                server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=timeout_sec)
            else:
                server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=timeout_sec)
                server.starttls() # Seguridad para puertos 587 o 25

            server.login(settings.SMTP_USER, settings.SMTP_PASS)
            server.send_message(msg)
            server.quit()
            return True
        except Exception as e:
            print(f"❌ [Email Error] Detalle: {str(e)}")
            return False

    async def send_mail(self, to: str, subject: str, html_content: str, attachments: list = None):
        if not self.enabled:
            return {"exito": False, "mensaje": "SMTP no configurado"}

        # Crear el contenedor del mensaje
        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = settings.SMTP_FROM or settings.SMTP_USER
        msg['To'] = to
        
        # Cuerpo principal (Texto plano como fallback y HTML como contenido rico)
        msg.set_content("El contenido de este mensaje requiere un lector de correos compatible con HTML.")
        msg.add_alternative(html_content, subtype='html')

        # Gestión de adjuntos (Facturas XML y PDFs)
        if attachments:
            for att in attachments:
                # att["content"] debe ser bytes
                msg.add_attachment(
                    att["content"], 
                    maintype=att.get("maintype", "application"), 
                    subtype=att.get("subtype", "octet-stream"), 
                    filename=att["filename"]
                )

        # 🚀 LANZAMIENTO ASÍNCRONO
        # to_thread envía la ejecución al pool de hilos para no bloquear el event loop de FastAPI
        success = await asyncio.to_thread(self._send_sync, msg)
        
        if success:
            print(f"📧 [Email] Enviado exitosamente a {to}")
            return {"exito": True}
        
        return {"exito": False, "error": "No se pudo entregar el correo electrónico."}

# Instancia global para importar en tus otros servicios
mail_service = EmailService()