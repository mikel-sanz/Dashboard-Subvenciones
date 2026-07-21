"""
🛡️ NEXO MDU: classifier.py
Propósito: Clasificador semántico NLP local para sectorización de subvenciones.
Arquitectura: Modular Design Unit (MDU) - Capa de Procesamiento y Servicios.
Licencia: Propietaria NEXO Ecosystem.
"""

import logging
from typing import Dict

from src.config import settings
from src.processing.heuristics import clasificar_actividad_clasica

# Configuración del registrador de logs
logger = logging.getLogger(__name__)

# Etiquetas/Sectores para clasificación Zero-Shot
SECTORES_LABELS = [
    "Digitalización y Robótica",
    "Transición Verde y Sostenibilidad",
    "Agroalimentario",
    "Educación y Social",
    "Investigación, Desarrollo e Innovación Científica",
    "Emprendimiento y Creación de Startups"
]

# Diccionario para mapear las labels devueltas por el modelo a los nombres originales
MAPEO_SECTORES: Dict[str, str] = {
    "Digitalización y Robótica": "Digitalización/Robótica",
    "Transición Verde y Sostenibilidad": "Transición Verde/Sostenibilidad",
    "Agroalimentario": "Agroalimentario",
    "Educación y Social": "Educación/Social",
    "Investigación, Desarrollo e Innovación Científica": "I+D+i Científica",
    "Emprendimiento y Creación de Startups": "Emprendimiento/Startups"
}


class SemanticClassifier:
    """
    Clasificador semántico Zero-Shot basado en Hugging Face pipeline
    para categorizar subvenciones sin necesidad de embeddings manuales.
    """

    _pipeline = None
    _usar_fallback = False

    @classmethod
    def _cargar_modelo_perezoso(cls) -> None:
        """
        Carga el pipeline Zero-Shot de forma perezosa (Lazy Loading).
        """
        if cls._pipeline is not None or cls._usar_fallback:
            return

        try:
            logger.info("Inicializando clasificador Zero-Shot NLP...")
            from transformers import pipeline

            # Usamos un modelo multilenguaje apto para zero-shot en español
            model_name = "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli"
            cls._pipeline = pipeline("zero-shot-classification", model=model_name)
            logger.info(f"Modelo Zero-Shot ({model_name}) cargado con éxito.")

        except Exception as exc:
            logger.warning(
                f"No se pudo inicializar el modelo Zero-Shot NLP ({exc}). "
                "Activando fallback automático a heurísticas clásicas."
            )
            cls._usar_fallback = True

    @classmethod
    def clasificar(cls, titulo: str, organo: str) -> str:
        """
        Clasifica una subvención basándose en la similitud semántica de su texto.

        Args:
            titulo: Título de la convocatoria de subvención.
            organo: Órgano o entidad convocante.

        Returns:
            str: Sector estratégico asignado.
        """
        # 1. Validamos si está desactivado por configuración global
        if not settings.USE_SEMANTIC_CLASSIFIER:
            return cls._clasificar_heuristica_clasica(titulo, organo)

        # 2. Intentamos la carga perezosa del modelo NLP
        cls._cargar_modelo_perezoso()

        # 3. Si el fallback está activo, usamos heurísticas clásicas
        if cls._usar_fallback or cls._pipeline is None:
            return cls._clasificar_heuristica_clasica(titulo, organo)

        try:
            texto_consulta = f"{titulo}. Convocado por: {organo}"
            
            # Realizar predicción zero-shot
            resultado = cls._pipeline(
                texto_consulta, 
                SECTORES_LABELS, 
                multi_label=False
            )
            
            mejor_label = resultado["labels"][0]
            score = resultado["scores"][0]
            
            mejor_sector = MAPEO_SECTORES.get(mejor_label, "Otros")

            logger.debug(
                f"Zero-Shot NLP exitoso para '{titulo[:40]}...': "
                f"'{mejor_sector}' (Confianza: {score:.4f})"
            )
            
            # Si la confianza es muy baja, aplicar fallback heurístico
            if score < 0.30:
                 return cls._clasificar_heuristica_clasica(titulo, organo)
                 
            return mejor_sector

        except Exception as exc:
            logger.error(
                f"Excepción durante la inferencia NLP para '{titulo[:40]}...': {exc}. "
                "Aplicando fallback heurístico."
            )
            return cls._clasificar_heuristica_clasica(titulo, organo)

    @staticmethod
    def _clasificar_heuristica_clasica(titulo: str, organo: str) -> str:
        """
        Método de fallback basado en palabras clave clásicas.
        """
        return clasificar_actividad_clasica(titulo, organo)
