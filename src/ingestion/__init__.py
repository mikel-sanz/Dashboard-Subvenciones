"""
Paquete de Ingesta del Dashboard de Subvenciones.

Este paquete expone los clientes de APIs externas para la obtención de datos
de subvenciones de Navarra, España y Europa.
"""

from src.ingestion.base_extractor import BaseExtractor
from src.ingestion.espana_bdns import EspanaBdnsExtractor
from src.ingestion.europa_funding import EuropaFundingExtractor
from src.ingestion.navarra_ckan import NavarraCkanExtractor

__all__ = [
    "BaseExtractor",
    "NavarraCkanExtractor",
    "EspanaBdnsExtractor",
    "EuropaFundingExtractor",
]
