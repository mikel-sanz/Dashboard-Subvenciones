"""
Pruebas Unitarias para la Capa de Ingesta (Extractores).

Este módulo valida el comportamiento de la clase base abstracta de extracción
y sus especializaciones ante escenarios de simulación y fallos de red,
utilizando pytest-mock para aislar las llamadas de httpx.
Sigue el patrón Arrange-Act-Assert (AAA).
"""

from typing import Any

import httpx
import pytest

from src.config import settings
from src.ingestion.espana_bdns import EspanaBdnsExtractor
from src.ingestion.europa_funding import EuropaFundingExtractor
from src.ingestion.navarra_ckan import NavarraCkanExtractor


def test_extractor_simulacion_forzada() -> None:
    """
    ARRANGE: Configurar el sistema para forzar datos simulados.
    ACT: Ejecutar el extractor de Navarra.
    ASSERT: Validar que no hace peticiones HTTP, devuelve datos simulados y marca
            el flag '_is_simulated' como True.
    """
    settings.FORCE_SIMULATED_DATA = True
    extractor = NavarraCkanExtractor()

    resultados = extractor.extract()

    assert len(resultados) > 0
    for registro in resultados:
        assert registro["_is_simulated"] is True
        assert registro["_extractor_source"] == "Navarra"
        assert "Linea_Ayuda" in registro


def test_extractor_fallback_ante_error_red(mocker: Any) -> None:
    """
    ARRANGE: Simular un fallo de red en el cliente httpx.Client
             y activar la configuración de fallback automático.
    ACT: Ejecutar la extracción de España.
    ASSERT: Validar que la app absorbe el fallo, carga la simulación de fallback
            e inyecta el flag '_is_simulated' en True.
    """
    settings.FORCE_SIMULATED_DATA = False
    settings.ALLOW_SIMULATED_FALLBACK = True

    # Parcheamos el método get en httpx.Client para simular fallo de red
    mocker.patch(
        "httpx.Client.get",
        side_effect=httpx.ConnectError("Fallo de conexión al servidor BDNS"),
    )

    extractor = EspanaBdnsExtractor()

    resultados = extractor.extract()

    assert len(resultados) > 0
    for registro in resultados:
        assert registro["_is_simulated"] is True
        assert registro["_extractor_source"] == "España"
        assert "descripcion" in registro


def test_extractor_error_propaga_si_no_se_permite_fallback(mocker: Any) -> None:
    """
    ARRANGE: Simular fallo de conexión en la API de la Comisión Europea y desactivar
             el fallback automático.
    ACT & ASSERT: Validar que el extractor propaga la excepción HTTP esperada
                  sin silenciar el error.
    """
    settings.FORCE_SIMULATED_DATA = False
    settings.ALLOW_SIMULATED_FALLBACK = False

    # Parcheamos el método post de httpx.Client para que lance una excepción
    mocker.patch(
        "httpx.Client.post",
        side_effect=httpx.ConnectError("Conexión rechazada por el servidor europeo"),
    )

    extractor = EuropaFundingExtractor()

    with pytest.raises(httpx.RequestError):
        extractor.extract()


def test_extractor_exito_real(mocker: Any) -> None:
    """
    ARRANGE: Mockear el método 'get' de httpx.Client para retornar una respuesta
             válida con status 200 y JSON correcto.
    ACT: Ejecutar la extracción de Navarra.
    ASSERT: Validar que se recupera el payload simulado y se marca '_is_simulated'
            como False.
    """
    settings.FORCE_SIMULATED_DATA = False

    mock_response = mocker.Mock()
    mock_response.status_code = 200
    mock_payload = {
        "success": True,
        "result": {
            "records": [
                {
                    "Linea_Ayuda": "Subvención Real Navarra Digital",
                    "Presupuesto_Euros": 85000.00,
                    "Fecha_Limite": "2026-11-15",
                    "Organismo_Convocante": "Gobierno de Navarra",
                }
            ]
        },
    }
    mock_response.json.return_value = mock_payload
    mock_response.raise_for_status.return_value = None

    # Parcheamos el método get en httpx.Client para retornar la respuesta mockeada
    mocker.patch("httpx.Client.get", return_value=mock_response)

    extractor = NavarraCkanExtractor()

    resultados = extractor.extract()

    assert len(resultados) == 1
    assert resultados[0]["Linea_Ayuda"] == "Subvención Real Navarra Digital"
    assert resultados[0]["_is_simulated"] is False
    assert resultados[0]["_extractor_source"] == "Navarra"
