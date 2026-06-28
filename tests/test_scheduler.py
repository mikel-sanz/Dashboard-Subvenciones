"""
🛡️ NEXO MDU: test_scheduler.py
Propósito: Pruebas unitarias para programador asincrono y alertas de ingesta.
Arquitectura: Modular Design Unit (MDU) - Suite de Pruebas Unitarias.
Licencia: Propietaria NEXO Ecosystem.
"""

from unittest.mock import patch

from src.ingestion.scheduler import IngestionScheduler
from src.storage.database import DatabaseManager, UsuarioDB


def test_scheduler_flujo_completo_con_notificaciones(
    db_manager_in_memory: DatabaseManager,
) -> None:
    """
    ARRANGE: Registrar un usuario activo con preferencias de alertas.
    ACT: Ejecutar el flujo unificado del scheduler de ingesta de APIs.
    ASSERT: Verificar que la subvencion se persiste y se despacha la alerta.
    """
    # Arrange
    db = db_manager_in_memory
    username = "ALERTA_TEST_USER"
    db.crear_usuario(username, "test_alerts@moriarty.local", "pass123")

    # Activar alertas y configurar filtros
    db.actualizar_preferencias_alertas(
        username=username,
        recibir=True,
        sectores="Digitalización/Robótica",
        ambitos="España",
    )

    scheduler = IngestionScheduler(db)

    # Rutas absolutas para parchear los metodos de extraccion
    path_nav = "src.ingestion.navarra_ckan.NavarraCkanExtractor.extract"
    path_esp = "src.ingestion.espana_bdns.EspanaBdnsExtractor.extract"
    path_eur = "src.ingestion.europa_funding.EuropaFundingExtractor.extract"
    path_send = "src.notifications.alerts.EmailNotifier.enviar_correo"

    # Mockear extractores de Navarra, España y Europa
    with (
        patch(path_nav) as mock_nav,
        patch(path_esp) as mock_esp,
        patch(path_eur) as mock_eur,
        patch(path_send) as mock_send,
    ):
        mock_nav.return_value = []
        # España BDNS retorna datos con el formato del normalizador
        mock_esp.return_value = [
            {
                "descripcion": "Subvencion Robotica para PYMEs",
                "presupuesto_euros": 35000.00,
                "fechaRecepcion": "2026-12-31",
                "nivel3": "Ministerio de Industria",
                "numeroConvocatoria": "12345",
                "_extractor_source": "España",
                "_is_simulated": False,
            }
        ]
        mock_eur.return_value = []

        # Act
        scheduler.ejecutar_ingesta_y_notificar()

    # Assert
    # Verificar persistencia en base de datos
    session = db.SessionLocal()
    conteo = (
        session.query(UsuarioDB)
        .filter(UsuarioDB.username == username)
        .first()
    )
    assert conteo.recibir_alertas is True
    session.close()

    # Verificar que se llamo al despachador de correos con el correo del usuario
    mock_send.assert_called_once()
    _, kwargs = mock_send.call_args
    assert kwargs.get("destinatario") == "test_alerts@moriarty.local"
    assert "Subvencion Robotica para PYMEs" in kwargs.get("html_content")
