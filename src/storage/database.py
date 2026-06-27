"""
Módulo de Persistencia y Base de Datos (SQLite).

Este módulo gestiona la conexión con la base de datos SQLite utilizando SQLAlchemy,
define el modelo relacional unificado, previene la duplicación de registros mediante
un hash SHA-256 único, y proporciona interfaces de carga en lote y lectura a Pandas.
"""

import datetime
import hashlib
import logging
from pathlib import Path

import bcrypt
import pandas as pd
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    Integer,
    String,
    create_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker

from src.config import settings
from src.processing.schemas import SubvencionSchema

# Configuración del logging
logger = logging.getLogger(__name__)

# Base declarativa de SQLAlchemy para modelos
Base = declarative_base()


class SubvencionDB(Base):  # type: ignore
    """
    Modelo ORM de SQLAlchemy para la tabla de subvenciones.
    """

    __tablename__ = "subvenciones"

    id = Column(Integer, primary_key=True, autoincrement=True)
    Tipo_Subvencion = Column(String, nullable=False)
    Cuantia = Column(Float, nullable=False)
    Fecha_Vigencia = Column(Date, nullable=False)
    Entidad_Convocante = Column(String, nullable=False)
    Ambito_Territorial = Column(String, nullable=False)
    Actividad_Relacionada = Column(String, nullable=False)
    URL_Convocatoria = Column(String, default="", nullable=False)
    Es_Simulado = Column(Boolean, default=False, nullable=False)
    Hash_Unico = Column(String, unique=True, nullable=False, index=True)


class UsuarioDB(Base):  # type: ignore
    """
    Modelo ORM para usuarios del sistema con almacenamiento de contraseñas seguras.
    """

    __tablename__ = "usuarios"

    username = Column(String, primary_key=True)
    email = Column(String, nullable=False, unique=True)
    password_hash = Column(String, nullable=False)


class LogAuditoriaDB(Base):  # type: ignore
    """
    Modelo ORM para almacenar el historial de auditoría de actividad de los usuarios.
    """

    __tablename__ = "logs_auditoria"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fecha_hora = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    username = Column(String, nullable=False)
    accion = Column(String, nullable=False)
    detalles = Column(String, nullable=True)


def generar_hash_registro(subvencion: SubvencionSchema) -> str:
    """
    Genera un hash SHA-256 a partir de los campos clave del registro.

    Esto previene duplicados en inserciones repetitivas de forma determinista.
    """
    clave_compuesta = (
        f"{subvencion.Tipo_Subvencion}|"
        f"{subvencion.Cuantia:.2f}|"
        f"{subvencion.Fecha_Vigencia.isoformat()}|"
        f"{subvencion.Entidad_Convocante}|"
        f"{subvencion.Ambito_Territorial}"
    )
    return hashlib.sha256(clave_compuesta.encode("utf-8")).hexdigest()


class DatabaseManager:
    """
    Gestor de la conexión e interacción con la base de datos de persistencia.
    """

    def __init__(self, db_url: str = settings.DATABASE_URL) -> None:
        self.db_url = db_url

        # Si es SQLite local, creamos los directorios padres.
        # Previene errores de directorio inexistente en SQLAlchemy.
        if self.db_url.startswith("sqlite:///"):
            path_str = self.db_url.replace("sqlite:///", "")
            if path_str != ":memory:":
                db_path = Path(path_str)
                db_path.parent.mkdir(parents=True, exist_ok=True)

        # Crear el engine y la factoría de sesiones
        self.engine = create_engine(
            self.db_url,
            connect_args={"check_same_thread": False}
            if "sqlite" in self.db_url
            else {},
        )
        self.SessionLocal = sessionmaker(
            bind=self.engine, autoflush=False, autocommit=False
        )

        # Crear las tablas en la base de datos si no existen
        Base.metadata.create_all(bind=self.engine)
        self.sembrar_usuario_defecto()
        logger.info("Estructura de base de datos inicializada correctamente.")

    def bulk_insert(self, subvenciones: list[SubvencionSchema]) -> int:
        """
        Inserta una lista de esquemas validados en la base de datos.

        Evita inyectar registros duplicados utilizando el hash unívoco.

        Returns:
            int: Cantidad de nuevos registros insertados con éxito.
        """
        if not subvenciones:
            return 0

        session = self.SessionLocal()
        nuevos_registros_cnt = 0
        hashes_lote = set()
        try:
            for sub in subvenciones:
                hash_val = generar_hash_registro(sub)

                # Evitamos duplicados en el propio lote actual antes de consultar la DB
                if hash_val in hashes_lote:
                    continue

                # Comprobamos si existe en la base de datos por su hash.
                existe = (
                    session.query(SubvencionDB)
                    .filter(SubvencionDB.Hash_Unico == hash_val)
                    .first()
                )
                if not existe:
                    registro_db = SubvencionDB(
                        Tipo_Subvencion=sub.Tipo_Subvencion,
                        Cuantia=sub.Cuantia,
                        Fecha_Vigencia=sub.Fecha_Vigencia,
                        Entidad_Convocante=sub.Entidad_Convocante,
                        Ambito_Territorial=sub.Ambito_Territorial,
                        Actividad_Relacionada=sub.Actividad_Relacionada,
                        URL_Convocatoria=sub.URL_Convocatoria,
                        Es_Simulado=sub.Es_Simulado,
                        Hash_Unico=hash_val,
                    )
                    session.add(registro_db)
                    hashes_lote.add(hash_val)
                    nuevos_registros_cnt += 1

            # Confirmar la transacción
            session.commit()
            logger.info(
                "Inserción completada: %d nuevos registros.", nuevos_registros_cnt
            )
        except Exception as exc:
            session.rollback()
            logger.error(f"Fallo durante la inserción en lote: {exc}")
            raise exc
        finally:
            session.close()

        return nuevos_registros_cnt

    def load_as_dataframe(self) -> pd.DataFrame:
        """
        Retorna todas las subvenciones en un DataFrame de Pandas.
        """
        query = (
            "SELECT Tipo_Subvencion, Cuantia, Fecha_Vigencia, "
            "Entidad_Convocante, Ambito_Territorial, "
            "Actividad_Relacionada, URL_Convocatoria, "
            "Es_Simulado FROM subvenciones"
        )
        try:
            # Uso de context manager para conexión de SQLAlchemy
            with self.engine.connect() as connection:
                df = pd.read_sql_query(query, connection)

                # Asegurar conversión de fecha e integridad de booleano
                if not df.empty:
                    df["Fecha_Vigencia"] = pd.to_datetime(df["Fecha_Vigencia"]).dt.date
                    if "Es_Simulado" in df.columns:
                        df["Es_Simulado"] = df["Es_Simulado"].astype(bool)
                return df
        except Exception as exc:
            logger.error(f"Error al cargar datos a DataFrame: {exc}")
            # Retorna un DataFrame vacío con las columnas esperadas en caso de fallo
            return pd.DataFrame(
                columns=[
                    "Tipo_Subvencion",
                    "Cuantia",
                    "Fecha_Vigencia",
                    "Entidad_Convocante",
                    "Ambito_Territorial",
                    "Actividad_Relacionada",
                    "Es_Simulado",
                ]
            )

    def sembrar_usuario_defecto(self) -> None:
        """
        Siembre un usuario de administración por defecto si la tabla está vacía.
        """
        session = self.SessionLocal()
        try:
            usuarios_cnt = session.query(UsuarioDB).count()
            if usuarios_cnt == 0:
                password_plana = "admin123"
                pwd_bytes = password_plana.encode("utf-8")
                # Hashear con sal usando bcrypt
                salt = bcrypt.gensalt()
                password_hash = bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")

                usuario_base = UsuarioDB(
                    username="admin",
                    email="admin@moriarty.local",
                    password_hash=password_hash,
                )
                session.add(usuario_base)
                session.commit()
                logger.info("Usuario administrador base sembrado con éxito.")
        except Exception as exc:
            session.rollback()
            logger.error(f"Error al sembrar usuario por defecto: {exc}")
        finally:
            session.close()

    def registrar_evento_auditoria(
        self, username: str, accion: str, detalles: str = None
    ) -> None:
        """
        Registra una acción de usuario en el log persistente de auditoría.
        """
        session = self.SessionLocal()
        try:
            log_db = LogAuditoriaDB(username=username, accion=accion, detalles=detalles)
            session.add(log_db)
            session.commit()
        except Exception as exc:
            session.rollback()
            logger.error(f"Error al registrar log de auditoría: {exc}")
        finally:
            session.close()

    def obtener_logs_auditoria(self, limite: int = 100) -> pd.DataFrame:
        """
        Retorna los registros de auditoría ordenados por fecha descendente.
        """
        query = (
            "SELECT fecha_hora, username, accion, detalles "
            f"FROM logs_auditoria ORDER BY fecha_hora DESC LIMIT {limite}"
        )
        try:
            with self.engine.connect() as connection:
                df = pd.read_sql_query(query, connection)
                if not df.empty:
                    df["fecha_hora"] = pd.to_datetime(df["fecha_hora"])
                return df
        except Exception as exc:
            logger.error(f"Error al obtener logs de auditoría: {exc}")
            return pd.DataFrame(
                columns=["fecha_hora", "username", "accion", "detalles"]
            )

    def validar_credenciales(self, username: str, password: str) -> bool:
        """
        Valida el nombre de usuario y su contraseña contra la base de datos.
        """
        session = self.SessionLocal()
        try:
            usuario = (
                session.query(UsuarioDB).filter(UsuarioDB.username == username).first()
            )
            if not usuario:
                return False

            # Validar con bcrypt
            pwd_bytes = password.encode("utf-8")
            hash_bytes = usuario.password_hash.encode("utf-8")
            return bool(bcrypt.checkpw(pwd_bytes, hash_bytes))
        except Exception as exc:
            logger.error(f"Error al validar credenciales de '{username}': {exc}")
            return False
        finally:
            session.close()

    def obtener_usuarios(self) -> list[UsuarioDB]:
        """
        Retorna la lista completa de usuarios registrados.
        """
        session = self.SessionLocal()
        try:
            return session.query(UsuarioDB).order_by(UsuarioDB.username).all()
        except Exception as exc:
            logger.error(f"Error al obtener usuarios: {exc}")
            return []
        finally:
            session.close()

    def crear_usuario(self, username: str, email: str, contrasena_plana: str) -> bool:
        """
        Crea un nuevo usuario encriptando la contraseña con bcrypt.
        """
        session = self.SessionLocal()
        try:
            # Comprobar si el usuario ya existe
            existe = (
                session.query(UsuarioDB).filter(UsuarioDB.username == username).first()
            )
            if existe:
                logger.warning(f"Intento de registrar usuario duplicado: '{username}'")
                return False

            # Hashear la contraseña con bcrypt
            salt = bcrypt.gensalt()
            pwd_bytes = contrasena_plana.encode("utf-8")
            password_hash = bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")

            nuevo_usuario = UsuarioDB(
                username=username, email=email, password_hash=password_hash
            )
            session.add(nuevo_usuario)
            session.commit()
            logger.info(f"Usuario registrado correctamente: '{username}'")
            return True
        except Exception as exc:
            session.rollback()
            logger.error(f"Error al crear usuario '{username}': {exc}")
            return False
        finally:
            session.close()

    def eliminar_usuario(self, username: str) -> bool:
        """
        Elimina un usuario por su nombre de usuario.
        """
        session = self.SessionLocal()
        try:
            usuario = (
                session.query(UsuarioDB).filter(UsuarioDB.username == username).first()
            )
            if not usuario:
                logger.warning(f"Intento de eliminar usuario inexistente: '{username}'")
                return False

            session.delete(usuario)
            session.commit()
            logger.info(f"Usuario eliminado correctamente: '{username}'")
            return True
        except Exception as exc:
            session.rollback()
            logger.error(f"Error al eliminar usuario '{username}': {exc}")
            return False
        finally:
            session.close()

    def actualizar_contrasena(
        self, username: str, nueva_contrasena_plana: str
    ) -> bool:
        """
        Actualiza la contraseña de un usuario hasheándola con bcrypt.
        """
        session = self.SessionLocal()
        try:
            usuario = (
                session.query(UsuarioDB)
                .filter(UsuarioDB.username == username)
                .first()
            )
            if not usuario:
                logger.warning(
                    f"Intento de actualizar contraseña de usuario "
                    f"inexistente: '{username}'"
                )
                return False

            # Hashear la nueva contraseña con bcrypt
            salt = bcrypt.gensalt()
            pwd_bytes = nueva_contrasena_plana.encode("utf-8")
            password_hash = bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")

            usuario.password_hash = password_hash
            session.commit()
            logger.info(
                f"Contraseña actualizada correctamente para el usuario: "
                f"'{username}'"
            )
            return True
        except Exception as exc:
            session.rollback()
            logger.error(
                f"Error al actualizar contraseña del usuario '{username}': "
                f"{exc}"
            )
            return False
        finally:
            session.close()
