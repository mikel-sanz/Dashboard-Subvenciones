"""
Extractor para el Sistema Nacional de Publicidad de Subvenciones (BDNS) de España.

Este módulo implementa el cliente para consultar la API pública de búsqueda
de la BDNS y recuperar convocatorias estatales, autonómicas y locales.
"""

import logging
from typing import Any

import httpx

from src.ingestion.base_extractor import BaseExtractor

# Logger para trazar la ejecución de la conexión con BDNS
logger = logging.getLogger(__name__)


class EspanaBdnsExtractor(BaseExtractor):
    """
    Cliente para la ingesta de subvenciones desde la API BDNS de España.
    """

    def __init__(self) -> None:
        super().__init__(name="EspañaBDNS", source_label="España")
        # Endpoint de búsqueda pública de la BDNS (el endpoint base
        # /convocatorias devuelve 400 sin parámetros adicionales)
        self.base_url = (
            "https://www.infosubvenciones.es/bdnstrans/api/"
            "convocatorias/busqueda"
        )

    def _extract_real(self) -> list[dict[str, Any]]:
        """
        Consulta la API de búsqueda de la BDNS de España.

        El endpoint de búsqueda devuelve un JSON paginado con los
        resultados bajo la clave 'content'. Cada registro contiene
        descripción, fecha de recepción, ámbito territorial y organismo,
        pero no incluye cuantía presupuestaria en el listado.
        """
        # Se añade un User-Agent realista porque los servidores de la
        # administración pública española suelen bloquear bots genéricos
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json",
        }

        # Parámetros de paginación del endpoint de búsqueda
        params = {"page": 0, "pageSize": 50}

        with httpx.Client(timeout=15.0, headers=headers) as client:
            response = client.get(self.base_url, params=params)
            response.raise_for_status()

            payload = response.json()

            # La respuesta de búsqueda encapsula los datos en 'content'
            content = payload.get("content", [])
            if isinstance(content, list):
                logger.info(
                    f"[EspañaBDNS] Registros obtenidos: {len(content)}"
                )
                return content

            logger.warning(
                "[EspañaBDNS] 'content' no es una lista válida."
            )
            return []

    def _get_simulated_data(self) -> list[dict[str, Any]]:
        """
        Retorna registros simulados representativos de las ayudas de la BDNS.

        Usa la misma estructura de campos que los datos reales para
        mantener la coherencia del normalizador.
        """
        return [
            {
                "numeroConvocatoria": 712903,
                "descripcion": (
                    "Convocatoria Kit Digital - Segmento III "
                    "(Autónomos y Microempresas)"
                ),
                "fechaRecepcion": "2026-10-31",
                "nivel1": "ESTATAL",
                "nivel3": (
                    "Ministerio de Asuntos Económicos "
                    "y Transformación Digital"
                ),
            },
            {
                "numeroConvocatoria": 722401,
                "descripcion": (
                    "Ayudas del PERTE Agroalimentario para la "
                    "Sostenibilidad y Trazabilidad"
                ),
                "fechaRecepcion": "2026-09-30",
                "nivel1": "ESTATAL",
                "nivel3": (
                    "Ministerio de Agricultura, "
                    "Pesca y Alimentación"
                ),
            },
            {
                "numeroConvocatoria": 735912,
                "descripcion": (
                    "Subvenciones para Proyectos de I+D+i en "
                    "Inteligencia Artificial Aplicada"
                ),
                "fechaRecepcion": "2026-12-15",
                "nivel1": "ESTATAL",
                "nivel3": (
                    "Ministerio de Ciencia, "
                    "Innovación y Universidades"
                ),
            },
            {
                "numeroConvocatoria": 749811,
                "descripcion": (
                    "Programa de Fomento del Empleo Joven "
                    "y Prácticas no Laborales"
                ),
                "fechaRecepcion": "2026-08-31",
                "nivel1": "ESTATAL",
                "nivel3": "Ministerio de Trabajo y Economía Social",
            },
        ]
