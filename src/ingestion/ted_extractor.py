"""
Extractor para Tenders Electronic Daily (TED).

Este módulo implementa la ingesta de licitaciones y contratos públicos europeos,
que muchas empresas utilizan de forma complementaria a las subvenciones.
"""

import logging
from typing import Any

from src.ingestion.base_extractor import BaseExtractor

logger = logging.getLogger(__name__)


class TedExtractor(BaseExtractor):
    """
    Cliente para la ingesta de licitaciones europeas desde TED.
    """

    def __init__(self) -> None:
        super().__init__(name="EuropaTED", source_label="Europa-TED")
        self.base_url = "https://ted.europa.eu/api/v2.0/notices/search"

    def _extract_real(self) -> list[dict[str, Any]]:
        """
        Consulta la API de TED.
        Debido a los requerimientos de autenticación Oauth2 del EU Login,
        implementamos temporalmente un fallback simulado controlado.
        """
        logger.warning(
            "[Europa-TED] Autenticación no configurada. Cayendo a datos resilientes (Simulados)."
        )
        return []

    def _get_simulated_data(self) -> list[dict[str, Any]]:
        """
        Retorna registros simulados representativos de licitaciones TED.
        """
        return [
            {
                "contractTitle": "Provision of Cloud Infrastructure Services for the EU",
                "estimatedValue": "45000000.00",
                "deadlineDate": "2026-10-31",
                "authority": "European Commission - DG DIGIT",
                "cpvCodes": ["72200000", "48800000"],
                "noticeUrl": "https://ted.europa.eu/udl?uri=TED:NOTICE:123-2026:TEXT:EN:HTML",
            },
            {
                "contractTitle": "Supply of Robotics Equipment for Educational Centers",
                "estimatedValue": "5200000.00",
                "deadlineDate": "2026-09-15",
                "authority": "Ministry of Education",
                "cpvCodes": ["38000000"],
                "noticeUrl": "https://ted.europa.eu/udl?uri=TED:NOTICE:456-2026:TEXT:EN:HTML",
            },
            {
                "contractTitle": "Construction of Solar Plant Facilities in Southern EU",
                "estimatedValue": "112000000.00",
                "deadlineDate": "2026-11-20",
                "authority": "European Investment Bank",
                "cpvCodes": ["09330000", "45200000"],
                "noticeUrl": "https://ted.europa.eu/udl?uri=TED:NOTICE:789-2026:TEXT:EN:HTML",
            },
        ]
