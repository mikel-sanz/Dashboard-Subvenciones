"""
Módulo de Configuración Global del Proyecto.

Este módulo define y valida las variables de entorno necesarias para la ejecución
del dashboard de subvenciones, utilizando Pydantic Settings para garantizar la
coherencia de los tipos en tiempo de ejecución.
"""

from pathlib import Path
from typing import Literal, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Clase que define la configuración de la aplicación y la validación de tipos.

    Carga valores desde variables de entorno y tiene como fallback un archivo '.env'.
    """

    # Entorno y logs
    ENV: Literal["development", "production"] = "development"
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # Persistencia
    DATABASE_URL: str = "sqlite:///data/processed/subvenciones.db"

    # Autenticación y Seguridad
    JWT_SECRET: str  # Secreto eliminado. Ahora es obligatorio inyectarlo vía .env
    COOKIE_EXPIRY_DAYS: int = 30

    # Comportamiento de ingesta
    FORCE_SIMULATED_DATA: bool = False
    ALLOW_SIMULATED_FALLBACK: bool = True

    # Navarra CKAN API
    # ID real del dataset "Rehabilitación protegida de viviendas terminadas"
    NAVARRA_RESOURCE_ID: str = "bdf64326-0f6a-4fa0-b6f3-0b891ba14e62"

    # Configuración de Alertas por Email (SMTP)
    SMTP_SERVER: str = "localhost"
    SMTP_PORT: int = 1025
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM_EMAIL: str = "noreply@dashboard-subvenciones.com"

    # Configuración de Refresco Automático y Scheduler
    SCHEDULER_HOUR: int = 6
    AUTO_REFRESH_THRESHOLD_HOURS: int = 24

    # Clasificador Semántico NLP
    USE_SEMANTIC_CLASSIFIER: bool = True
    NLP_MODEL_NAME: str = "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli"

    # Configuración de carga de archivos externos
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    @property
    def database_path(self) -> Path:
        """
        Retorna la ruta absoluta al archivo SQLite a partir del DATABASE_URL.

        Esto nos permite trabajar con pathlib de manera limpia.
        """
        # Extraemos la ruta del string de conexión sqlite:///ruta/al/archivo.db
        if self.DATABASE_URL.startswith("sqlite:///"):
            path_str = self.DATABASE_URL.replace("sqlite:///", "")
            return Path(path_str)
        # Fallback a una ruta por defecto en caso de URLs diferentes
        return Path("data/processed/subvenciones.db")


# Instancia única y compartida de configuración (Patrón Singleton)
settings = Settings()

# Ejemplo mínimo de uso:
# >>> from src.config import settings
# >>> print(settings.ENV)
# 'development'
# >>> print(settings.database_path)
# WindowsPath('data/processed/subvenciones.db')
