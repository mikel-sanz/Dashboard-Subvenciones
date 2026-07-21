"""
Módulo de Persistencia y Base de Datos (SQLite).

Este módulo provee la interfaz principal DatabaseManager, que consolida
las operaciones de persistencia de subvenciones, cacheo en memoria de Pandas,
y delega la gestión de usuarios a UserRepository.
"""

import hashlib
import logging
import pandas as pd
import streamlit as st

from src.config import settings
from src.processing.schemas import SubvencionSchema
from src.storage.db_session import DBSession
from src.storage.models import SubvencionDB
from src.storage.user_repository import UserRepository

logger = logging.getLogger(__name__)


def generar_hash_registro(subvencion: SubvencionSchema) -> str:
    """Genera un hash SHA-256 a partir de los campos clave del registro."""
    clave_compuesta = (
        f"{subvencion.Tipo_Subvencion}|"
        f"{subvencion.Cuantia:.2f}|"
        f"{subvencion.Fecha_Vigencia.isoformat()}|"
        f"{subvencion.Entidad_Convocante}|"
        f"{subvencion.Ambito_Territorial}"
    )
    return hashlib.sha256(clave_compuesta.encode("utf-8")).hexdigest()


class DatabaseManager(UserRepository):
    """
    Gestor principal de la base de datos de subvenciones.
    Hereda de UserRepository para exponer las operaciones de usuario
    y mantiene compatibilidad retroactiva.
    """

    def __init__(self, db_url: str = settings.DATABASE_URL) -> None:
        super().__init__()
        # Inicializa la conexión centralizada (forzando si es test en memoria)
        force_init = ":memory:" in db_url
        DBSession.initialize(db_url, force=force_init)
        # Migraciones y semilla de datos (heredados)
        self._migrar_usuarios_columnas()
        self.sembrar_usuario_defecto()

    def bulk_insert(self, subvenciones: list[SubvencionSchema]) -> int:
        """Inserta una lista de esquemas en lote, previniendo duplicados."""
        if not subvenciones:
            return 0

        session = DBSession.get_session()
        nuevos_registros_cnt = 0
        hashes_lote = set()
        try:
            for sub in subvenciones:
                hash_val = generar_hash_registro(sub)
                if hash_val in hashes_lote:
                    continue

                existe = session.query(SubvencionDB).filter(SubvencionDB.Hash_Unico == hash_val).first()
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

            session.commit()
            logger.info("Inserción completada: %d nuevos registros.", nuevos_registros_cnt)
        except Exception as exc:
            session.rollback()
            logger.error(f"Fallo durante la inserción en lote: {exc}")
            raise exc
        finally:
            session.close()

        # Si hay datos nuevos, forzamos la invalidación de la caché de Streamlit
        if nuevos_registros_cnt > 0:
            st.cache_data.clear()

        return nuevos_registros_cnt

    @st.cache_data(ttl="1h", show_spinner=False)
    def load_as_dataframe(_self) -> pd.DataFrame:
        """
        Retorna todas las subvenciones en un DataFrame de Pandas.
        Utilizamos @st.cache_data con _self para no hashear la instancia de la clase,
        lo que mejora enormemente el rendimiento en lecturas recurrentes.
        """
        query = (
            "SELECT Tipo_Subvencion, Cuantia, Fecha_Vigencia, "
            "Entidad_Convocante, Ambito_Territorial, "
            "Actividad_Relacionada, URL_Convocatoria, "
            "Es_Simulado FROM subvenciones"
        )
        try:
            with DBSession.get_engine().connect() as connection:
                df = pd.read_sql_query(query, connection)
                if not df.empty:
                    df["Fecha_Vigencia"] = pd.to_datetime(df["Fecha_Vigencia"]).dt.date
                    if "Es_Simulado" in df.columns:
                        df["Es_Simulado"] = df["Es_Simulado"].astype(bool)
                return df
        except Exception as exc:
            logger.error(f"Error al cargar datos a DataFrame: {exc}")
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
