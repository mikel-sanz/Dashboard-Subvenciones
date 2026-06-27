"""
Extractor para el Portal de Funding & Tenders de la Comisión Europea (SEDIA).

Este módulo implementa el cliente para consultar la API pública de búsqueda
de la Comisión Europea y extraer proyectos y convocatorias de subvenciones
(Horizonte Europa, LIFE, FEDER, NextGenerationEU, etc.).
"""

import logging
from typing import Any

import httpx

from src.ingestion.base_extractor import BaseExtractor

# Logger para trazar la ejecución de la conexión con SEDIA
logger = logging.getLogger(__name__)


class EuropaFundingExtractor(BaseExtractor):
    """
    Cliente para la ingesta de subvenciones desde la API de la Comisión Europea.
    """

    def __init__(self) -> None:
        super().__init__(name="EuropaFunding", source_label="Europa")
        # Base URL oficial del servicio de búsqueda pública (SEDIA)
        self.base_url = (
            "https://api.tech.ec.europa.eu/search-api/prod/rest/search"
        )

    def _aplanar_metadata(
        self, resultado: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Aplana la estructura de un resultado de SEDIA a un diccionario plano.

        La API devuelve los metadatos como listas de un solo elemento.
        Este método extrae el primer valor de cada lista relevante para
        simplificar el mapeo posterior en el normalizador.

        Args:
            resultado: Diccionario crudo de un resultado de la API SEDIA.

        Returns:
            Diccionario plano con los campos relevantes extraídos.
        """
        metadata = resultado.get("metadata", {})

        def _primer_valor(campo: str) -> str:
            """Extrae el primer elemento de una lista de metadatos o ''."""
            valores = metadata.get(campo, [])
            if isinstance(valores, list) and valores:
                return str(valores[0])
            return ""

        return {
            "title": (
                _primer_valor("title")
                or resultado.get("summary", "European Funding")
            ),
            "budget": _primer_valor("esIN_overallBudget"),
            "programme": _primer_valor("esST_programmes"),
            "date": _primer_valor("es_SortDate"),
            "keywords": metadata.get("esST_freeKeywords", []),
            "url": resultado.get("url", ""),
            # Metadatos extra para trazabilidad
            "_extractor_source": "Europa",
        }

    def _extract_real(self) -> list[dict[str, Any]]:
        """
        Consulta la API de búsqueda de la Comisión Europea mediante POST.

        Busca proyectos y convocatorias de tipo 'grants' con paginación
        controlada y aplana los metadatos a campos planos para el normalizador.
        """
        # Parámetros de query obligatorios para SEDIA
        params = {"apiKey": "SEDIA", "text": "grants"}

        # Payload JSON con la configuración de búsqueda paginada
        payload = {
            "languages": ["en"],
            "pageSize": 50,
            "pageNumber": 1,
        }

        with httpx.Client(timeout=15.0) as client:
            response = client.post(
                self.base_url, params=params, json=payload
            )
            response.raise_for_status()

            response_data = response.json()
            # La API SEDIA devuelve los resultados bajo la clave 'results'
            results = response_data.get("results", [])

            if not isinstance(results, list):
                logger.warning(
                    "[EuropaFunding] 'results' no es una lista válida."
                )
                return []

            # Aplanamos cada resultado para simplificar el normalizador
            registros_planos: list[dict[str, Any]] = []
            for resultado in results:
                try:
                    plano = self._aplanar_metadata(resultado)
                    registros_planos.append(plano)
                except (KeyError, TypeError) as exc:
                    logger.warning(
                        f"[EuropaFunding] Registro omitido por error: {exc}"
                    )
                    continue

            logger.info(
                f"[EuropaFunding] Registros aplanados: "
                f"{len(registros_planos)}"
            )
            return registros_planos

    def _get_simulated_data(self) -> list[dict[str, Any]]:
        """
        Retorna registros simulados del Marco Financiero Plurianual y NextGenerationEU.

        Garantiza consistencia estructural para fondos europeos de gran envergadura.
        """
        return [
            {
                "title": (
                    "Horizonte Europa: Tecnologías Digitales Avanzadas "
                    "y Robótica Autónoma"
                ),
                "budget": "150000000.00",
                "date": "2026-11-15",
                "programme": "NextGenerationEU - Horizonte Europa",
                "keywords": ["digital", "robotics", "AI"],
                "url": "",
            },
            {
                "title": (
                    "Programa LIFE: Proyectos de Acción Climática "
                    "y Transición Energética"
                ),
                "budget": "95000000.00",
                "date": "2026-09-05",
                "programme": "Programa LIFE - Gestión Directa CE",
                "keywords": ["climate", "energy", "transition"],
                "url": "",
            },
            {
                "title": (
                    "Fondo Europeo de Desarrollo Regional (FEDER) - "
                    "Infraestructuras Digitales"
                ),
                "budget": "240000000.00",
                "date": "2026-12-01",
                "programme": "Fondos Estructurales FEDER",
                "keywords": ["digital", "infrastructure", "regional"],
                "url": "",
            },
            {
                "title": (
                    "Horizonte Europa: Innovación y Sostenibilidad "
                    "en la Cadena Agroalimentaria"
                ),
                "budget": "70000000.00",
                "date": "2026-10-20",
                "programme": "NextGenerationEU - Horizonte Europa",
                "keywords": ["agriculture", "sustainability", "food"],
                "url": "",
            },
        ]
