"""
Esquema de Datos Unificado para Subvenciones.

Este módulo define los modelos de Pydantic que garantizan la integridad,
el tipo y los valores permitidos para cada registro de subvención procesado
por el pipeline de datos.
"""

import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

# Definición de tipos literales para restringir y categorizar de forma estricta
# el ámbito geográfico y el sector de actividad, según los requisitos.
AmbitoTerritorialType = Literal["Europa", "España", "Navarra"]
ActividadRelacionadaType = Literal[
    "Digitalización/Robótica",
    "Transición Verde/Sostenibilidad",
    "Agroalimentario",
    "Educación/Social",
    "I+D+i Científica",
]


class SubvencionSchema(BaseModel):
    """
    Modelo de validación de datos para un registro individual de subvención.

    Alineado con el modelo de datos unificado especificado por el usuario.
    """

    # Campos solicitados por el usuario (respetando capitalización de la especificación)
    Tipo_Subvencion: str = Field(
        ...,
        description="Nombre de la convocatoria o línea de ayuda oficial.",
        min_length=3,
    )
    Cuantia: float = Field(
        ...,
        description="Importe presupuestado de la convocatoria o línea en euros (€).",
    )
    Fecha_Vigencia: datetime.date = Field(
        ..., description="Fecha límite de presentación o vigencia presupuestaria."
    )
    Entidad_Convocante: str = Field(
        ...,
        description="Organismo o administración emisora de la subvención.",
        min_length=2,
    )
    Ambito_Territorial: AmbitoTerritorialType = Field(
        ..., description="Segmentación geográfica: Europa, España o Navarra."
    )
    Actividad_Relacionada: ActividadRelacionadaType = Field(
        ..., description="Clasificación sectorial del gasto o sector objetivo."
    )

    # URL de la fuente oficial para navegación directa
    URL_Convocatoria: str = Field(
        "",
        description="Enlace a la página oficial de la convocatoria.",
    )

    # Campos de control y señalización requeridos para datos simulados
    Es_Simulado: bool = Field(
        False, description="Indica si el registro es simulado (fallback/demostración)."
    )

    @field_validator("Cuantia")
    @classmethod
    def validar_cuantia_positiva(cls, v: float) -> float:
        """
        Valida que el importe presupuestario sea estrictamente mayor que cero.
        """
        if v < 0:
            raise ValueError("El importe de la cuantía no puede ser negativo.")
        return v


# Ejemplo mínimo de uso:
# >>> from src.processing.schemas import SubvencionSchema
# >>> import datetime
# >>> sub = SubvencionSchema(
# ...     Tipo_Subvencion="Ayudas Kit Digital",
# ...     Cuantia=12000.00,
# ...     Fecha_Vigencia=datetime.date(2026, 12, 31),
# ...     Entidad_Convocante="Ministerio de Transformación Digital",
# ...     Ambito_Territorial="España",
# ...     Actividad_Relacionada="Digitalización/Robótica",
# ...     Es_Simulado=True
# ... )
# >>> print(sub.Cuantia)
# 12000.0
