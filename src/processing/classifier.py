"""
🛡️ NEXO MDU: classifier.py
Propósito: Clasificador semántico NLP local para sectorización de subvenciones.
Arquitectura: Modular Design Unit (MDU) - Capa de Procesamiento y Servicios.
Licencia: Propietaria NEXO Ecosystem.
"""

import logging
from typing import Dict

from src.config import settings

# Configuración del registrador de logs
logger = logging.getLogger(__name__)

# Descripciones expandidas para optimizar la similitud de coseno
SECTORES_DESCRIPCIONES: Dict[str, str] = {
    "Digitalización/Robótica": (
        "tecnologías de la información y comunicación, digitalización industrial, "
        "robótica, automatización, inteligencia artificial, software, computación, "
        "conectividad 5G, internet de las cosas IoT, sensores, ciberseguridad, redes"
    ),
    "Transición Verde/Sostenibilidad": (
        "transición ecológica, energías renovables, solar, eólica, sostenibilidad, "
        "descarbonización, reducción de emisiones, economía circular, reciclaje, "
        "eficiencia energética, gestión de agua, protección de biodiversidad"
    ),
    "Agroalimentario": (
        "agricultura de precisión, ganadería, pesca sostenible, sector alimentario, "
        "desarrollo rural, cultivos, maquinaria agrícola, pac, feader, granjas, "
        "industria vitivinícola, producción de alimentos, cadena alimentaria"
    ),
    "Educación/Social": (
        "cohesión social, educación, talleres de empleo, inserción laboral, "
        "capacitación profesional, becas escolares, colectivos vulnerables, "
        "igualdad de oportunidades, formación a jóvenes, programas sociales"
    ),
    "I+D+i Científica": (
        "investigación científica, desarrollo experimental, innovación tecnológica, "
        "patentes industriales, proyectos universitarios, laboratorios, ciencia, "
        "transferencia de conocimiento, ensayos clínicos, becas de investigación"
    ),
}


class SemanticClassifier:
    """
    Clasificador semántico basado en SentenceTransformers para categorizar
    subvenciones en base a la similitud semántica con los sectores definidos.
    """

    _model = None
    _sector_embeddings = None
    _usar_fallback = False

    @classmethod
    def _cargar_modelo_perezoso(cls) -> None:
        """
        Carga el modelo SentenceTransformer de forma perezosa (Lazy Loading)
        para no penalizar el tiempo de arranque de la aplicación principal.
        """
        if cls._model is not None or cls._usar_fallback:
            return

        try:
            logger.info(
                "Inicializando clasificador NLP con: "
                f"{settings.NLP_MODEL_NAME}"
            )
            # Importación dinámica para resiliencia
            from sentence_transformers import SentenceTransformer

            # Carga del modelo (se descarga de Hugging Face en el primer uso)
            cls._model = SentenceTransformer(settings.NLP_MODEL_NAME)
            logger.info("Modelo NLP cargado con éxito en memoria.")

            # Precalcular y cachear los embeddings de las descripciones
            cls._sectores_nombres = list(SECTORES_DESCRIPCIONES.keys())
            descripciones = list(SECTORES_DESCRIPCIONES.values())

            # Generamos los embeddings
            cls._sector_embeddings = cls._model.encode(
                descripciones, convert_to_numpy=True
            )
            logger.info("Embeddings de sectores precalculados con éxito.")

        except Exception as exc:
            logger.warning(
                f"No se pudo inicializar el modelo NLP ({exc}). "
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

        # 3. Si el fallback está activo por fallo de carga, usamos heurísticas clásicas
        if cls._usar_fallback or cls._model is None or cls._sector_embeddings is None:
            return cls._clasificar_heuristica_clasica(titulo, organo)

        try:
            import numpy as np

            # Combinamos título y órgano para mayor contexto semántico
            texto_consulta = f"{titulo} {organo}"
            query_embedding = cls._model.encode(texto_consulta, convert_to_numpy=True)

            # Calcular similitud de coseno
            # Similitud = (A.B) / (||A||.||B||)
            similitudes = []
            for emb in cls._sector_embeddings:
                norm_a = np.linalg.norm(query_embedding)
                norm_b = np.linalg.norm(emb)
                if norm_a == 0 or norm_b == 0:
                    sim = 0.0
                else:
                    sim = np.dot(query_embedding, emb) / (norm_a * norm_b)
                similitudes.append(sim)

            # Obtener el índice del sector con mayor similitud
            max_idx = int(np.argmax(similitudes))
            mejor_sector = cls._sectores_nombres[max_idx]

            logger.debug(
                f"Clasificación Semántica NLP exitosa para '{titulo[:40]}...': "
                f"'{mejor_sector}' (Similitud: {similitudes[max_idx]:.4f})"
            )
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
        Reutiliza la lógica importándola dinámicamente de normalizer.py.
        """
        from src.processing.normalizer import clasificar_actividad_clasica
        return clasificar_actividad_clasica(titulo, organo)
