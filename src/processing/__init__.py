"""
Paquete de Procesamiento y Normalización de Datos.

Contiene las clases y funciones necesarias para validar, limpiar y clasificar
las subvenciones obtenidas por los extractores.
"""

from src.processing.normalizer import (
    Normalizer,
    clasificar_actividad,
    limpiar_fecha,
    limpiar_importe,
)
from src.processing.schemas import SubvencionSchema

__all__ = [
    "SubvencionSchema",
    "Normalizer",
    "clasificar_actividad",
    "limpiar_fecha",
    "limpiar_importe",
]
