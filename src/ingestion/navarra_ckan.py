"""
Extractor para Open Data Navarra (CKAN).

Este módulo implementa el cliente para consultar la API de Datastore de CKAN
de Navarra y recuperar convocatorias de subvenciones públicas autonómicas.
"""

from typing import Any

import httpx

from src.config import settings
from src.ingestion.base_extractor import BaseExtractor


class NavarraCkanExtractor(BaseExtractor):
    """
    Cliente para la ingesta de subvenciones desde la API CKAN de Navarra.
    """

    def __init__(self) -> None:
        super().__init__(name="NavarraCKAN", source_label="Navarra")
        self.base_url = (
            "https://datosabiertos.navarra.es/es/api/3/action/datastore_search"
        )

    def _extract_real(self) -> list[dict[str, Any]]:
        """
        Consulta la API CKAN real de Navarra mediante el endpoint de datastore_search.
        """
        # Parámetros requeridos por CKAN para filtrar por recurso
        params = {"resource_id": settings.NAVARRA_RESOURCE_ID, "limit": 100}

        # Uso de httpx con timeout explícito para evitar bloqueos
        with httpx.Client(timeout=10.0) as client:
            response = client.get(self.base_url, params=params)
            # Lanza HTTPStatusError si el código de estado es de error (4xx, 5xx)
            response.raise_for_status()

            payload = response.json()
            # Validamos la estructura estándar del JSON devuelto por CKAN
            if payload.get("success") and "result" in payload:
                records = payload["result"].get("records", [])
                if isinstance(records, list):
                    return records

            # Si el formato no es el esperado, retornamos vacío
            return []

    def _get_simulated_data(self) -> list[dict[str, Any]]:
        """
        Retorna registros simulados de subvenciones de Navarra.

        Asegura que el dashboard sea funcional localmente con datos coherentes.
        """
        return [
            {
                "Linea_Ayuda": (
                    "Ayudas para la Digitalización y Robótica Industrial en Navarra"
                ),
                "Presupuesto_Euros": 750000.00,
                "Fecha_Limite": "2026-11-30",
                "Organismo_Convocante": (
                    "Departamento de Industria y de Transición "
                    "Ecológica y Digital Empresarial"
                ),
                "Actividad_Simulada": "Digitalización/Robótica",
            },
            {
                "Linea_Ayuda": "Subvenciones para Seguros Agrarios de Navarra",
                "Presupuesto_Euros": 1250000.00,
                "Fecha_Limite": "2026-09-15",
                "Organismo_Convocante": (
                    "Departamento de Desarrollo Rural y Medio Ambiente"
                ),
                "Actividad_Simulada": "Agroalimentario",
            },
            {
                "Linea_Ayuda": "Programa de Escuelas Taller de Empleo Navarra",
                "Presupuesto_Euros": 340000.00,
                "Fecha_Limite": "2026-08-01",
                "Organismo_Convocante": "Servicio Navarro de Empleo (SNE)",
                "Actividad_Simulada": "Educación/Social",
            },
            {
                "Linea_Ayuda": "Fomento de Proyectos de I+D+i en Economía Circular",
                "Presupuesto_Euros": 620000.00,
                "Fecha_Limite": "2026-10-15",
                "Organismo_Convocante": (
                    "Departamento de Desarrollo Rural y Medio Ambiente"
                ),
                "Actividad_Simulada": "Transición Verde/Sostenibilidad",
            },
        ]
