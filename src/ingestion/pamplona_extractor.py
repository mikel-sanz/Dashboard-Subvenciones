"""
Extractor específico para el Ayuntamiento de Pamplona.

Utiliza la BDNS como fuente subyacente pero aplica filtros específicos para 
obtener exclusivamente las convocatorias emitidas por el Ayuntamiento de Pamplona.
"""

import logging
from typing import Any

import httpx

from src.ingestion.base_extractor import BaseExtractor

logger = logging.getLogger(__name__)


class PamplonaExtractor(BaseExtractor):
    """
    Cliente para la ingesta de subvenciones específicas del Ayuntamiento de Pamplona.
    """

    def __init__(self) -> None:
        super().__init__(name="PamplonaLocal", source_label="Pamplona")
        self.base_url = (
            "https://www.infosubvenciones.es/bdnstrans/api/"
            "convocatorias/busqueda"
        )

    def _extract_real(self) -> list[dict[str, Any]]:
        """
        Consulta la BDNS y filtra por Pamplona.
        """
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json",
        }

        # Podemos usar parámetros de búsqueda de la BDNS si los conocemos,
        # o traer una página más grande y filtrar en memoria.
        params = {"page": 0, "pageSize": 100}

        with httpx.Client(timeout=15.0, headers=headers) as client:
            response = client.get(self.base_url, params=params)
            response.raise_for_status()

            payload = response.json()
            content = payload.get("content", [])
            
            if not isinstance(content, list):
                logger.warning("[PamplonaLocal] 'content' no es una lista.")
                return []

            # Filtrado estricto por Pamplona (Ayuntamiento, Consistorio, Iruña)
            resultados_pamplona = []
            for item in content:
                desc = str(item.get("descripcion", "")).lower()
                org = str(item.get("nivel3", "")).lower()
                
                # Buscamos menciones a Pamplona o Iruña en el órgano o la descripción
                if "pamplona" in org or "iruña" in org or "pamplona" in desc:
                    resultados_pamplona.append(item)

            logger.info(
                f"[PamplonaLocal] Registros totales BDNS: {len(content)}. "
                f"Filtrados para Pamplona: {len(resultados_pamplona)}."
            )
            return resultados_pamplona

    def _get_simulated_data(self) -> list[dict[str, Any]]:
        """
        Retorna registros simulados representativos de ayudas locales de Pamplona.
        """
        return [
            {
                "numeroConvocatoria": 810010,
                "descripcion": (
                    "Subvenciones para comercio local y hostelería "
                    "del Ayuntamiento de Pamplona"
                ),
                "fechaRecepcion": "2026-11-15",
                "nivel1": "LOCAL",
                "nivel3": "Ayuntamiento de Pamplona",
            },
            {
                "numeroConvocatoria": 810011,
                "descripcion": (
                    "Ayudas para la rehabilitación de viviendas "
                    "en el Casco Antiguo de Pamplona"
                ),
                "fechaRecepcion": "2026-10-31",
                "nivel1": "LOCAL",
                "nivel3": "Ayuntamiento de Pamplona",
            },
            {
                "numeroConvocatoria": 810012,
                "descripcion": (
                    "Programa de fomento de actividades culturales y "
                    "participación ciudadana en barrios (Pamplona)"
                ),
                "fechaRecepcion": "2026-09-30",
                "nivel1": "LOCAL",
                "nivel3": "Ayuntamiento de Pamplona",
            },
        ]
