"""
🛡️ NEXO MDU: test_classifier.py
Propósito: Pruebas unitarias para el clasificador semántico NLP local y fallback.
Arquitectura: Modular Design Unit (MDU) - Suite de Pruebas Unitarias.
Licencia: Propietaria NEXO Ecosystem.
"""

import sys
from unittest.mock import MagicMock, patch

# Inyección preventiva en sys.modules para permitir tests sin la librería instalada
if "sentence_transformers" not in sys.modules:
    mock_sentence_transformers = MagicMock()
    sys.modules["sentence_transformers"] = mock_sentence_transformers

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
    ARRANGE: Mockear el comportamiento de SentenceTransformer para retornar
            embeddings controlados que simulen una clasificación exitosa.
    ACT: Clasificar una subvención.
    ASSERT: Verificar que retorna el sector con mayor similitud de coseno.
    """
    # Arrange
    mock_model = MagicMock()
    # Mockear encode: la consulta y los 5 sectores
    mock_model.encode.side_effect = [
        [1.0, 0.0, 0.0, 0.0, 0.0],  # Consulta
        [0.9, 0.0, 0.0, 0.0, 0.0],  # Sector 1: Digitalización
        [0.1, 0.0, 0.0, 0.0, 0.0],  # Sector 2: Verde
        [0.0, 0.1, 0.0, 0.0, 0.0],  # Sector 3: Agro
        [0.0, 0.0, 0.1, 0.0, 0.0],  # Sector 4: Social
        [0.0, 0.0, 0.0, 0.1, 0.0],  # Sector 5: I+D
    ]

    # Resetear estado interno del clasificador para forzar carga perezosa
    SemanticClassifier._model = None
    SemanticClassifier._sector_embeddings = None
    SemanticClassifier._usar_fallback = False

    with (
        patch("src.config.settings.USE_SEMANTIC_CLASSIFIER", True),
        patch("sentence_transformers.SentenceTransformer", return_value=mock_model),
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
    # Resetear estado
    SemanticClassifier._model = None
    SemanticClassifier._sector_embeddings = None
    SemanticClassifier._usar_fallback = False

    with (
        patch("src.config.settings.USE_SEMANTIC_CLASSIFIER", True),
        patch(
            "sentence_transformers.SentenceTransformer",
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
