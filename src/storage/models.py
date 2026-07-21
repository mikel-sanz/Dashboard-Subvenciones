"""
Modelos ORM de SQLAlchemy.
"""

import datetime
from sqlalchemy import Boolean, Column, Date, DateTime, Float, Integer, String
from sqlalchemy.orm import declarative_base

# Base declarativa de SQLAlchemy para modelos
Base = declarative_base()

class SubvencionDB(Base):  # type: ignore
    """Modelo ORM de SQLAlchemy para la tabla de subvenciones."""
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
    """Modelo ORM para usuarios del sistema."""
    __tablename__ = "usuarios"

    username = Column(String, primary_key=True)
    email = Column(String, nullable=False, unique=True)
    password_hash = Column(String, nullable=False)

    # Campos de configuración de alertas
    recibir_alertas = Column(Boolean, default=False, nullable=False)
    sectores_interes = Column(String, default="*", nullable=False)
    ambitos_interes = Column(String, default="*", nullable=False)

class LogAuditoriaDB(Base):  # type: ignore
    """Modelo ORM para almacenar el historial de auditoría de actividad de los usuarios."""
    __tablename__ = "logs_auditoria"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fecha_hora = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    username = Column(String, nullable=False)
    accion = Column(String, nullable=False)
    detalles = Column(String, nullable=True)
