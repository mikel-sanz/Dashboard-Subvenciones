"""
Módulo para la gestión de la sesión y conexión con la base de datos.
"""
import logging
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.config import settings
from src.storage.models import Base

logger = logging.getLogger(__name__)


class DBSession:
    """
    Gestor de la conexión a la base de datos.
    """
    _engine = None
    _SessionLocal = None

    @classmethod
    def initialize(cls, db_url: str = settings.DATABASE_URL, force: bool = False) -> None:
        if cls._engine is not None and not force:
            return

        if force and cls._engine is not None:
            cls._engine.dispose()
            cls._engine = None
            cls._SessionLocal = None

        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)

        try:
            cls._setup_engine(db_url)
        except Exception as exc:
            logger.error(f"Fallo al conectar a DB externa: {exc}. Iniciando fallback a SQLite local...")
            db_url = "sqlite:///data/processed/subvenciones.db"
            cls._setup_engine(db_url)

    @classmethod
    def _setup_engine(cls, db_url: str) -> None:
        if db_url.startswith("sqlite:///"):
            path_str = db_url.replace("sqlite:///", "")
            if path_str != ":memory:":
                db_path = Path(path_str)
                db_path.parent.mkdir(parents=True, exist_ok=True)

        cls._engine = create_engine(
            db_url,
            connect_args={"check_same_thread": False} if "sqlite" in db_url else {},
        )
        cls._SessionLocal = sessionmaker(bind=cls._engine, autoflush=False, autocommit=False)
        Base.metadata.create_all(bind=cls._engine)
        logger.info("Base de datos inicializada correctamente.")

    @classmethod
    def get_session(cls):
        if cls._SessionLocal is None:
            cls.initialize()
        return cls._SessionLocal()

    @classmethod
    def get_engine(cls):
        if cls._engine is None:
            cls.initialize()
        return cls._engine
