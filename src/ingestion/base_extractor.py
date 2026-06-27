"""
Módulo del Extractor Base para Ingesta de Subvenciones.

Este módulo define la clase base abstracta de la cual heredan todos los clientes
de APIs externas. Controla el flujo de ejecución (Template Method), los fallbacks
transparentes a datos simulados y la inyección de metadatos de trazabilidad.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any

from src.config import settings

# Configuración del registrador de logs para rastrear la ejecución
logger = logging.getLogger(__name__)


class BaseExtractor(ABC):
    """
    Clase abstracta para los extractores de datos de subvenciones.

    Implementa la plantilla de ejecución (extract) para unificar el flujo de
    llamadas reales, reintentos y recuperación ante fallos mediante datos simulados.
    """

    def __init__(self, name: str, source_label: str) -> None:
        """
        Inicializa el extractor con un nombre y una etiqueta geográfica.

        Args:
            name: Nombre identificativo del extractor para logging.
            source_label: Ámbito geográfico ('Europa', 'España', 'Navarra').
        """
        self.name: str = name
        self.source_label: str = source_label

    @abstractmethod
    def _extract_real(self) -> list[dict[str, Any]]:
        """
        Realiza la petición HTTP real a la API correspondiente.

        Debe ser implementado por cada extractor específico.

        Returns:
            list[dict[str, Any]]: Lista de diccionarios con datos crudos de la API.
        """
        pass

    @abstractmethod
    def _get_simulated_data(self) -> list[dict[str, Any]]:
        """
        Retorna un conjunto mínimo de datos de simulación realistas.

        Utilizado como fallback en desarrollo o ante fallos del servidor real.

        Returns:
            list[dict[str, Any]]: Lista de diccionarios simulando el payload de la API.
        """
        pass

    def extract(self) -> list[dict[str, Any]]:
        """
        Orquesta la extracción de datos y la inyección de metadatos de control.

        Este método implementa el flujo común:
        1. Comprobar si se fuerza el modo simulación.
        2. Intentar llamar al extractor real.
        3. Si falla y está permitido, hacer fallback a datos simulados.
        4. Inyectar metadatos sobre la procedencia y si el dato es simulado.

        Returns:
            list[dict[str, Any]]: Registros crudos con metadatos de control.
        """
        is_simulated = False
        data: list[dict[str, Any]] = []

        # Paso 1: Comprobar si se fuerza la simulación mediante configuración
        if settings.FORCE_SIMULATED_DATA:
            logger.warning(
                f"[{self.name}] Simulación forzada por configuración global."
            )
            data = self._get_simulated_data()
            is_simulated = True
        else:
            # Paso 2: Intentar la consulta real de datos
            try:
                logger.info(f"[{self.name}] Conectando a la API real...")
                data = self._extract_real()
            except Exception as exc:
                logger.error(f"[{self.name}] Fallo al consultar la API real: {exc}")
                # Paso 3: Evaluar si el fallback a datos simulados está permitido
                if settings.ALLOW_SIMULATED_FALLBACK:
                    logger.warning(
                        f"[{self.name}] Fallback activado: Cargando simulación."
                    )
                    data = self._get_simulated_data()
                    is_simulated = True
                else:
                    # Si no se permite fallback, propagamos el error
                    raise exc

        # Paso 4: Enriquecer los registros con metadatos de procedencia para el frontend
        for record in data:
            record["_extractor_source"] = self.source_label
            record["_is_simulated"] = is_simulated

        logger.info(
            f"[{self.name}] Extracción finalizada. Registros procesados: {len(data)}"
        )
        return data
