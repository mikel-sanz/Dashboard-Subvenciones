"""
🛡️ NEXO MDU: test_classifier.py
Propósito: Pruebas unitarias para el clasificador semántico NLP local y fallback.
Arquitectura: Modular Design Unit (MDU) - Suite de Pruebas Unitarias.
Licencia: Propietaria NEXO Ecosystem.
"""

import sys
from unittest.mock import MagicMock, patch

if "transformers" not in sys.modules:
    mock_transformers = MagicMock()
    sys.modules["transformers"] = mock_transformers

from src.processing.classifier import SemanticClassifier


def test_clasificacion_heuristica_clasica_desactivada() -> None:
    """
    ARRANGE: Desactivar por configuración el clasificador semántico.
    ACT: Clasificar un texto con palabras clave sin subcadenas 'ia'.
    ASSERT: Verificar que se aplica la heurística clásica correctamente.
    """
    # Arrange
    with patch("src.config.settings.USE_SEMANTIC_CLASSIFIER", False):
        # Act
        sector = SemanticClassifier.clasificar(
            titulo="Placas solares y descarbonizacion",
            organo="Ministerio de Medio Ambiente",
        )
        # Assert
        assert sector == "Transición Verde/Sostenibilidad"


def test_clasificacion_semantica_nlp_exito() -> None:
    """
    ARRANGE: Mockear el comportamiento de pipeline para retornar un dict controlado.
    ACT: Clasificar una subvención.
    ASSERT: Verificar que retorna el sector devuelto por el modelo.
    """
    # Arrange
    mock_pipeline = MagicMock()
    mock_pipeline.return_value = {
        "labels": ["Digitalización y Robótica", "Transición Verde y Sostenibilidad"],
        "scores": [0.95, 0.05]
    }

    SemanticClassifier._pipeline = None
    SemanticClassifier._usar_fallback = False

    with (
        patch("src.config.settings.USE_SEMANTIC_CLASSIFIER", True),
        patch("transformers.pipeline", return_value=mock_pipeline),
    ):
        # Act
        sector = SemanticClassifier.clasificar(
            titulo="Desarrollo de Software IA para PYMEs",
            organo="Secretaría de Digitalización",
        )

        # Assert
        assert sector == "Digitalización/Robótica"
        assert SemanticClassifier._usar_fallback is False


def test_clasificacion_semantica_fallback_por_excepcion() -> None:
    """
    ARRANGE: Provocar una excepción al cargar el modelo NLP (ej. MemoryError).
    ACT: Clasificar un registro.
    ASSERT: Verificar que se activa el fallback y se devuelve la heurística clásica.
    """
    SemanticClassifier._pipeline = None
    SemanticClassifier._usar_fallback = False

    with (
        patch("src.config.settings.USE_SEMANTIC_CLASSIFIER", True),
        patch(
            "transformers.pipeline",
            side_effect=RuntimeError("Falta de memoria RAM"),
        ),
    ):
        # Act
        sector = SemanticClassifier.clasificar(
            titulo="Capacitacion y formacion de desempleados",
            organo="Servicio de Empleo",
        )

        # Assert
        assert sector == "Educación/Social"
        assert SemanticClassifier._usar_fallback is True
