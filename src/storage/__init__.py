"""
Paquete de Persistencia y Almacenamiento.

Contiene la interfaz para la base de datos SQLite y la carga estructurada de datos.
"""

from src.storage.database import DatabaseManager, SubvencionDB, generar_hash_registro

__all__ = [
    "DatabaseManager",
    "SubvencionDB",
    "generar_hash_registro",
]
