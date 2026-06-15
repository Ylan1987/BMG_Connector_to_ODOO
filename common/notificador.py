# -*- coding: utf-8 -*-
"""
Módulo Notificador por Email.
"""
import smtplib
from email.mime.text import MIMEText
from . import mapeos

def enviar_email(asunto, cuerpo):
    """
    Envía un email de notificación.
    """
    print(f"      - Intentando enviar email: {asunto}")
    try:
        msg = MIMEText(cuerpo, 'plain', 'utf-8')
        msg['Subject'] = f"[AUTOMATIZACIÓN IMPRENTA] {asunto}"
        msg['From'] = mapeos.SMTP_USUARIO
        msg['To'] = mapeos.EMAIL_DESTINO

        with smtplib.SMTP(mapeos.SMTP_SERVER, mapeos.SMTP_PORT) as server:
            server.starttls()
            server.login(mapeos.SMTP_USUARIO, mapeos.SMTP_CONTRASENA)
            server.send_message(msg)
        print("      - Email enviado con éxito.")
        return True
    except Exception as e:
        print(f"      - ERROR: No se pudo enviar el email. {e}")
        return False
