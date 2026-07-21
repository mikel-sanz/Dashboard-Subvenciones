"""
Módulo de repositorio para operaciones relacionadas con usuarios y auditoría.
"""
import logging
import bcrypt
import pandas as pd
from sqlalchemy import text

from src.storage.models import UsuarioDB, LogAuditoriaDB
from src.storage.db_session import DBSession

logger = logging.getLogger(__name__)

class UserRepository:
    """
    Repositorio para gestionar usuarios y registros de auditoría.
    """

    def __init__(self):
        DBSession.initialize()

    def sembrar_usuario_defecto(self) -> None:
        session = DBSession.get_session()
        try:
            usuarios_cnt = session.query(UsuarioDB).count()
            if usuarios_cnt == 0:
                password_plana = "admin123"
                pwd_bytes = password_plana.encode("utf-8")
                salt = bcrypt.gensalt()
                password_hash = bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")

                usuario_base = UsuarioDB(
                    username="ADMIN",
                    email="admin@moriarty.local",
                    password_hash=password_hash,
                )
                session.add(usuario_base)
                session.commit()
                logger.info("Usuario administrador base sembrado con éxito.")

            usuarios_fijos = [
                ("MIKEL", "mikel@trivium.local", "jeVnmq54H86jspj"),
                ("ANA", "ana@trivium.local", "ana123*QP"),
                ("BRENDA", "brenda@trivium.local", "brenda123*PM"),
            ]
            for usr, email, pwd in usuarios_fijos:
                existe = session.query(UsuarioDB).filter(UsuarioDB.username == usr).first()
                if not existe:
                    pwd_bytes = pwd.encode("utf-8")
                    salt = bcrypt.gensalt()
                    password_hash = bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")

                    usuario_db = UsuarioDB(
                        username=usr, email=email, password_hash=password_hash,
                    )
                    session.add(usuario_db)
                    session.commit()
                    logger.info(f"Usuario fijo '{usr}' sembrado con éxito.")
        except Exception as exc:
            session.rollback()
            logger.error(f"Error al sembrar usuarios: {exc}")
        finally:
            session.close()

    def registrar_evento_auditoria(self, username: str, accion: str, detalles: str = None) -> None:
        session = DBSession.get_session()
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
        query = (
            "SELECT fecha_hora, username, accion, detalles "
            f"FROM logs_auditoria ORDER BY fecha_hora DESC LIMIT {limite}"
        )
        try:
            with DBSession.get_engine().connect() as connection:
                df = pd.read_sql_query(query, connection)
                if not df.empty:
                    df["fecha_hora"] = pd.to_datetime(df["fecha_hora"])
                return df
        except Exception as exc:
            logger.error(f"Error al obtener logs de auditoría: {exc}")
            return pd.DataFrame(columns=["fecha_hora", "username", "accion", "detalles"])

    def validar_credenciales(self, username: str, password: str) -> bool:
        username = username.upper()
        session = DBSession.get_session()
        try:
            usuario = session.query(UsuarioDB).filter(UsuarioDB.username == username).first()
            if not usuario:
                return False

            pwd_bytes = password.encode("utf-8")
            hash_bytes = usuario.password_hash.encode("utf-8")
            return bool(bcrypt.checkpw(pwd_bytes, hash_bytes))
        except Exception as exc:
            logger.error(f"Error al validar credenciales de '{username}': {exc}")
            return False
        finally:
            session.close()

    def obtener_usuarios(self) -> list[UsuarioDB]:
        session = DBSession.get_session()
        try:
            return session.query(UsuarioDB).order_by(UsuarioDB.username).all()
        except Exception as exc:
            logger.error(f"Error al obtener usuarios: {exc}")
            return []
        finally:
            session.close()

    def crear_usuario(self, username: str, email: str, contrasena_plana: str) -> bool:
        username = username.upper()
        session = DBSession.get_session()
        try:
            existe = session.query(UsuarioDB).filter(UsuarioDB.username == username).first()
            if existe:
                logger.warning(f"Intento de registrar usuario duplicado: '{username}'")
                return False

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
        username = username.upper()
        session = DBSession.get_session()
        try:
            usuario = session.query(UsuarioDB).filter(UsuarioDB.username == username).first()
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

    def actualizar_contrasena(self, username: str, nueva_contrasena_plana: str) -> bool:
        username = username.upper()
        session = DBSession.get_session()
        try:
            usuario = session.query(UsuarioDB).filter(UsuarioDB.username == username).first()
            if not usuario:
                logger.warning(f"Intento de actualizar contraseña de usuario inexistente: '{username}'")
                return False

            salt = bcrypt.gensalt()
            pwd_bytes = nueva_contrasena_plana.encode("utf-8")
            password_hash = bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")

            usuario.password_hash = password_hash
            session.commit()
            logger.info(f"Contraseña actualizada correctamente para: '{username}'")
            return True
        except Exception as exc:
            session.rollback()
            logger.error(f"Error al actualizar contraseña del usuario '{username}': {exc}")
            return False
        finally:
            session.close()

    def _migrar_usuarios_columnas(self) -> None:
        columnas_migracion = {
            "recibir_alertas": "BOOLEAN DEFAULT 0 NOT NULL",
            "sectores_interes": "VARCHAR DEFAULT '*' NOT NULL",
            "ambitos_interes": "VARCHAR DEFAULT '*' NOT NULL",
        }
        with DBSession.get_engine().connect() as conn:
            for col_name, col_type in columnas_migracion.items():
                try:
                    conn.execute(text(f"ALTER TABLE usuarios ADD COLUMN {col_name} {col_type}"))
                    conn.commit()
                    logger.info(f"Columna '{col_name}' añadida con éxito.")
                except Exception:
                    pass

    def actualizar_preferencias_alertas(self, username: str, recibir: bool, sectores: str, ambitos: str) -> tuple[bool, str]:
        username = username.upper()
        session = DBSession.get_session()
        try:
            usuario = session.query(UsuarioDB).filter(UsuarioDB.username == username).first()
            if not usuario:
                return False, f"Usuario inexistente: '{username}'"

            usuario.recibir_alertas = recibir
            usuario.sectores_interes = sectores
            usuario.ambitos_interes = ambitos
            session.commit()
            logger.info(f"Preferencias actualizadas para: '{username}'")
            return True, ""
        except Exception as exc:
            session.rollback()
            err_msg = str(exc)
            logger.error(f"Error al actualizar preferencias de '{username}': {err_msg}")
            return False, err_msg
        finally:
            session.close()
