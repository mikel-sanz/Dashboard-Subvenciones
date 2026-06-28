"""
🛡️ NEXO MDU: test_alerts.py
Propósito: Pruebas unitarias para formateador HTML y envío de alertas SMTP.
Arquitectura: Modular Design Unit (MDU) - Suite de Pruebas Unitarias.
Licencia: Propietaria NEXO Ecosystem.
"""

import datetime
from unittest.mock import MagicMock, patch

from src.notifications.alerts import EmailNotifier
from src.processing.schemas import SubvencionSchema


def test_construccion_plantilla_html_con_datos_correctos() -> None:
    """
    Arrange: Preparar un conjunto de subvenciones válidas.
    Act: Invocar el renderizador de plantillas HTML.
    Assert: Validar que todos los campos y URLs se inyectan correctamente.
    """
    # Arrange
    url_conv = (
        "https://www.infosubvenciones.es/bdnstrans/GE/es/convocatoria/12345"
    )
    subvenciones = [
        SubvencionSchema(
            Tipo_Subvencion="Ayudas Kit Digital",
            Cuantia=12000.00,
            Fecha_Vigencia=datetime.date(2026, 12, 31),
            Entidad_Convocante="Red.es",
            Ambito_Territorial="España",
            Actividad_Relacionada="Digitalización/Robótica",
            URL_Convocatoria=url_conv,
        ),
        SubvencionSchema(
            Tipo_Subvencion="Proyectos de Innovación Agroalimentaria",
            Cuantia=75400.50,
            Fecha_Vigencia=datetime.date(2026, 8, 15),
            Entidad_Convocante="Gobierno de Navarra",
            Ambito_Territorial="Navarra",
            Actividad_Relacionada="Agroalimentario",
            URL_Convocatoria="https://navarra.es/convocatoria-agro",
        ),
    ]
    username = "mikel"

    # Act
    html_cuerpo = EmailNotifier.construir_plantilla_html(
        subvenciones, username
    )

    # Assert
    assert "Hola, <strong>mikel</strong>" in html_cuerpo
    assert "Ayudas Kit Digital" in html_cuerpo
    assert "12,000.00 €" in html_cuerpo
    assert url_conv in html_cuerpo
    assert "Proyectos de Innovación Agroalimentaria" in html_cuerpo
    assert "75,400.50 €" in html_cuerpo
    assert "https://navarra.es/convocatoria-agro" in html_cuerpo
    assert "Agroalimentario" in html_cuerpo
    assert "Digitalización/Robótica" in html_cuerpo


@patch("smtplib.SMTP")
def test_enviar_correo_exitoso_smtp_clasico(mock_smtp: MagicMock) -> None:
    """
    Arrange: Mockear el servidor SMTP y configurar credenciales SMTP.
    Act: Intentar el envío de correo.
    Assert: Validar que se conecta al host y se inicia sesión.
    """
    # Arrange
    instancia_smtp = mock_smtp.return_value.__enter__.return_value
    notifier = EmailNotifier()

    # Act
    with patch("src.notifications.alerts.settings") as mock_settings:
        mock_settings.SMTP_SERVER = "smtp.test.com"
        mock_settings.SMTP_PORT = 587
        mock_settings.SMTP_USER = "user@test.com"
        mock_settings.SMTP_PASSWORD = "app_password_here"
        mock_settings.SMTP_FROM_EMAIL = "noreply@test.com"

        notifier.enviar_correo(
            destinatario="usuario@correo.com",
            asunto="Alerta de Subvención",
            html_content="<p>Test</p>",
        )

    # Assert
    mock_smtp.assert_called_once_with("smtp.test.com", 587)
    instancia_smtp.starttls.assert_called_once()
    instancia_smtp.login.assert_called_once_with(
        "user@test.com", "app_password_here"
    )
    instancia_smtp.sendmail.assert_called_once()


@patch("smtplib.SMTP_SSL")
def test_enviar_correo_exitoso_smtp_ssl(mock_smtp_ssl: MagicMock) -> None:
    """
    Arrange: Mockear el servidor SMTP_SSL para puerto 465 seguro.
    Act: Enviar correo de alerta.
    Assert: Validar que se crea el canal SSL y se loguea de forma segura.
    """
    # Arrange
    instancia_ssl = mock_smtp_ssl.return_value.__enter__.return_value
    notifier = EmailNotifier()

    # Act
    with patch("src.notifications.alerts.settings") as mock_settings:
        mock_settings.SMTP_SERVER = "smtp.secure.com"
        mock_settings.SMTP_PORT = 465
        mock_settings.SMTP_USER = "secure@test.com"
        mock_settings.SMTP_PASSWORD = "secure_password"
        mock_settings.SMTP_FROM_EMAIL = "noreply@secure.com"

        notifier.enviar_correo(
            destinatario="dest@correo.com",
            asunto="Alerta Segura",
            html_content="<p>SSL Test</p>",
        )

    # Assert
    mock_smtp_ssl.assert_called_once_with("smtp.secure.com", 465)
    instancia_ssl.login.assert_called_once_with(
        "secure@test.com", "secure_password"
    )
    instancia_ssl.sendmail.assert_called_once()
