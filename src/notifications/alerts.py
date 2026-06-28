"""
🛡️ NEXO MDU: alerts.py
Propósito: Servicio de envío de notificaciones de subvenciones por email.
Arquitectura: Modular Design Unit (MDU) - Capa de Lógica y Servicios.
Licencia: Propietaria NEXO Ecosystem.
"""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List

from src.config import settings
from src.processing.schemas import SubvencionSchema

# Configuración de logging local
logger = logging.getLogger(__name__)


class EmailNotifier:
    """
    Gestiona la construcción de plantillas HTML y el envío de notificaciones
    por correo electrónico a través de un servidor SMTP seguro.
    """

    @staticmethod
    def construir_plantilla_html(
        subvenciones: List[SubvencionSchema], username: str
    ) -> str:
        """
        Construye el cuerpo del correo electrónico en formato HTML.
        """
        filas_tabla = ""
        for sub in subvenciones:
            # Si el registro cuenta con URL oficial, generamos el enlace.
            style_a = (
                "color: #00b4d8; text-decoration: none; font-weight: bold;"
            )
            url_html = (
                f'<a href="{sub.URL_Convocatoria}" style="{style_a}">'
                f"Ver Convocatoria</a>"
                if sub.URL_Convocatoria
                else "No disponible"
            )

            filas_tabla += f"""
            <tr style="border-bottom: 1px solid #e0e0e0;">
                <td style="padding: 12px; font-size: 0.9em; color: #333333;">
                    {sub.Tipo_Subvencion}
                </td>
                <td style="padding: 12px; font-size: 0.9em; color: #333333;
                           text-align: right; font-weight: bold;">
                    {sub.Cuantia:,.2f} €
                </td>
                <td style="padding: 12px; font-size: 0.9em; color: #333333;
                           text-align: center;">
                    {sub.Fecha_Vigencia}
                </td>
                <td style="padding: 12px; font-size: 0.9em; color: #333333;">
                    {sub.Ambito_Territorial}
                </td>
                <td style="padding: 12px; font-size: 0.9em; color: #333333;">
                    {sub.Actividad_Relacionada}
                </td>
                <td style="padding: 12px; font-size: 0.9em; text-align: center;">
                    {url_html}
                </td>
            </tr>
            """

        # Rompemos líneas largas de la plantilla HTML para no exceder 88 caracteres.
        td_header_style = (
            "background-color: #012a4a; padding: 30px; "
            "text-align: center; color: #ffffff;"
        )
        td_footer_style = (
            "background-color: #f7fafc; padding: 20px; "
            "text-align: center; font-size: 0.8em; color: #a0aec0; "
            "border-top: 1px solid #edf2f7;"
        )
        table_style = (
            "max-width: 800px; background-color: #ffffff; "
            "border-radius: 8px; overflow: hidden; "
            "box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1); "
            "border: 1px solid #e2e8f0;"
        )

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Nuevas Subvenciones Publicadas</title>
        </head>
        <body style="font-family: sans-serif; background-color: #f4f7f6;
                     color: #333333; margin: 0; padding: 20px;">
            <table align="center" border="0" cellpadding="0" cellspacing="0"
                   width="100%" style="{table_style}">
                <tr>
                    <td style="{td_header_style}">
                        <h2 style="margin: 0; font-size: 1.6em;
                                   letter-spacing: 1px;">
                            Vigilancia de Subvenciones
                        </h2>
                        <p style="margin: 5px 0 0 0; font-size: 0.9em;
                                   color: #a9d6e5;">
                            Ecosistema de Automatización MORIARTY
                        </p>
                    </td>
                </tr>
                <tr>
                    <td style="padding: 30px;">
                        <p style="font-size: 1.1em; margin-top: 0;">
                            Hola, <strong>{username}</strong>:
                        </p>
                        <p>Hemos detectado nuevas subvenciones y ayudas públicas:</p>
                        <table width="100%" border="0" cellpadding="0"
                               cellspacing="0" style="border-collapse: collapse;
                                                      margin-top: 20px;
                                                      border: 1px solid #e2e8f0;">
                            <thead>
                                <tr style="background-color: #f8fafc;
                                           border-bottom: 2px solid #e2e8f0;">
                                    <th style="padding: 12px; text-align: left;
                                               color: #4a5568;">Convocatoria</th>
                                    <th style="padding: 12px; text-align: right;
                                               color: #4a5568;">Presupuesto</th>
                                    <th style="padding: 12px; text-align: center;
                                               color: #4a5568;">Plazo</th>
                                    <th style="padding: 12px; text-align: left;
                                               color: #4a5568;">Ámbito</th>
                                    <th style="padding: 12px; text-align: left;
                                               color: #4a5568;">Sector</th>
                                    <th style="padding: 12px; text-align: center;
                                               color: #4a5568;">Enlace</th>
                                </tr>
                            </thead>
                            <tbody>
                                {filas_tabla}
                            </tbody>
                        </table>
                        <p style="margin-top: 30px; font-size: 0.9em;
                                   color: #718096; line-height: 1.5;">
                            Para modificar tus preferencias de notificación, por favor
                            inicia sesión y ve al panel de gestión de usuarios.
                        </p>
                    </td>
                </tr>
                <tr>
                    <td style="{td_footer_style}">
                        Este es un correo automático. Por favor no respondas.<br/>
                        &copy; 2026 Ecosistema NEXO - Dashboard de Subvenciones.
                    </td>
                </tr>
            </table>
        </body>
        </html>
        """
        return html

    def enviar_correo(
        self, destinatario: str, asunto: str, html_content: str
    ) -> None:
        """
        Envía un correo electrónico en formato HTML a través de SMTP seguro.
        """
        # Si no se configuraron credenciales y no es puerto 1025 local, saltamos
        if (
            not settings.SMTP_USER
            and not settings.SMTP_PASSWORD
            and settings.SMTP_PORT != 1025
        ):
            logger.warning(
                "Configuración SMTP ausente. Saltando envío real de alerta "
                f"hacia {destinatario}."
            )
            return

        msg = MIMEMultipart("alternative")
        msg["Subject"] = asunto
        msg["From"] = settings.SMTP_FROM_EMAIL
        msg["To"] = destinatario
        msg.attach(MIMEText(html_content, "html"))

        try:
            # Si el puerto es 465, abrimos una conexión con SSL/TLS directa.
            if settings.SMTP_PORT == 465:
                with smtplib.SMTP_SSL(
                    settings.SMTP_SERVER, settings.SMTP_PORT
                ) as server:
                    if settings.SMTP_USER and settings.SMTP_PASSWORD:
                        server.login(
                            settings.SMTP_USER, settings.SMTP_PASSWORD
                        )
                    server.sendmail(
                        settings.SMTP_FROM_EMAIL, destinatario, msg.as_string()
                    )
            # En cualquier otro caso, abrimos una conexión SMTP clásica.
            else:
                with smtplib.SMTP(
                    settings.SMTP_SERVER, settings.SMTP_PORT
                ) as server:
                    if settings.SMTP_PORT == 587:
                        server.starttls()
                    if settings.SMTP_USER and settings.SMTP_PASSWORD:
                        server.login(
                            settings.SMTP_USER, settings.SMTP_PASSWORD
                        )
                    server.sendmail(
                        settings.SMTP_FROM_EMAIL, destinatario, msg.as_string()
                    )

            logger.info(f"Correo de alerta enviado correctamente a {destinatario}.")

        except smtplib.SMTPException as smtp_exc:
            logger.error(
                f"Fallo en la comunicación SMTP al notificar a {destinatario}: "
                f"{smtp_exc}"
            )
        except Exception as exc:
            logger.error(
                f"Error inesperado al enviar correo de alerta a {destinatario}: "
                f"{exc}"
            )
