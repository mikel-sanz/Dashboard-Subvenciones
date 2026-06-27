"""
Configuración General de Pytest y Fixtures de Prueba.

Este módulo define las fixtures compartidas por toda la suite de pruebas,
incluyendo bases de datos efímeras en memoria para evitar efectos colaterales.
"""

from typing import Generator

import pytest

from src.config import settings
from src.storage.database import Base, DatabaseManager


@pytest.fixture(autouse=True)
def restablecer_settings() -> Generator[None, None, None]:
    """
    Asegura que los settings vuelvan a su estado original tras cada test.

    Evita la contaminación de configuración entre pruebas consecutivas.
    """
    # Guardamos los valores originales
    original_force = settings.FORCE_SIMULATED_DATA
    original_fallback = settings.ALLOW_SIMULATED_FALLBACK
    original_url = settings.DATABASE_URL

    yield

    # Restauramos los valores originales
    settings.FORCE_SIMULATED_DATA = original_force
    settings.ALLOW_SIMULATED_FALLBACK = original_fallback
    settings.DATABASE_URL = original_url


@pytest.fixture
def db_manager_in_memory() -> Generator[DatabaseManager, None, None]:
    """
    Fixture que proporciona un DatabaseManager conectado a una base de datos SQLite
    en memoria (:memory:) limpia.

    Se encarga de crear las tablas al inicio y destruirlas al finalizar.
    """
    # Usamos base de datos en memoria para aislamiento absoluto de tests
    manager = DatabaseManager("sqlite:///:memory:")

    yield manager

    # Limpiamos las tablas y cerramos conexiones
    Base.metadata.drop_all(bind=manager.engine)
    manager.engine.dispose()
