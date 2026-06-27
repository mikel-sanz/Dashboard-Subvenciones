"""
Módulo del Normalizador de Subvenciones.

Este módulo procesa y limpia los registros crudos de las tres fuentes (Navarra,
España, Europa) y los mapea hacia el esquema unificado de Pydantic, infiriendo
la clasificación sectorial mediante palabras clave si es necesario.
"""

import datetime
import logging
import re
from decimal import Decimal, InvalidOperation
from typing import Any

from src.processing.schemas import SubvencionSchema

# Configuración de logs
logger = logging.getLogger(__name__)


def limpiar_importe(valor: Any) -> float:
    """
    Limpia y convierte un valor de importe monetario a float de forma segura.

    Maneja formatos tipo string con separadores de miles y decimales comunes en Europa.
    """
    if valor is None:
        return 0.0
    if isinstance(valor, (int, float)):
        return float(valor)

    # Tratamiento de strings
    val_str = str(valor).strip()
    try:
        # Quitamos espacios y símbolos de moneda comunes
        val_str = re.sub(r"[^\d.,-]", "", val_str)
        # Si tiene puntos y comas (ej. 1.250,50 o 1,250.50)
        if "." in val_str and "," in val_str:
            # Determinamos cuál es el decimal analizando la posición
            if val_str.find(".") < val_str.find(","):
                # Formato europeo: 1.250,50 -> quitar puntos, cambiar coma a punto
                val_str = val_str.replace(".", "").replace(",", ".")
            else:
                # Formato anglosajón: 1,250.50 -> quitamos comas
                val_str = val_str.replace(",", "")
        elif "," in val_str:
            # Si solo tiene coma, verificar si actúa como decimal.
            # En España/Navarra suele actuar como decimal.
            val_str = val_str.replace(",", ".")

        return float(Decimal(val_str))
    except (ValueError, TypeError, InvalidOperation):
        logger.warning(f"No se pudo limpiar el importe '{valor}'. Asignando 0.0.")
        return 0.0


def limpiar_fecha(valor: Any) -> datetime.date:
    """
    Limpia y convierte un valor a un objeto datetime.date de forma segura.
    """
    if isinstance(valor, datetime.datetime):
        return valor.date()
    if isinstance(valor, datetime.date):
        return valor

    if not valor:
        # Si no hay fecha, asignamos una por defecto futura lejana (o el día de hoy)
        return datetime.date.today() + datetime.timedelta(days=90)

    val_str = str(valor).strip()
    # Intentar varios formatos de fecha comunes
    formatos = [
        "%Y-%m-%d",  # 2026-12-31
        "%d/%m/%Y",  # 31/12/2026
        "%Y/%m/%d",  # 2026/12/31
        "%d-%m-%Y",  # 31-12-2026
        "%Y-%m-%dT%H:%M:%S",  # ISO con tiempo
        "%Y-%m-%dT%H:%M:%SZ",  # ISO UTC
    ]

    # Limpiamos formatos ISO complejos eliminando fracciones de segundo si existieran
    val_str = val_str.split(".")[0]

    for fmt in formatos:
        try:
            return datetime.datetime.strptime(val_str, fmt).date()
        except ValueError:
            continue

    logger.warning(f"Formato de fecha no reconocido para '{valor}'. Asignando hoy.")
    return datetime.date.today()


def clasificar_actividad(titulo: str, organo: str) -> str:
    """
    Clasifica de forma automatizada la subvención en uno de los 5 sectores estratégicos
    basándose en el análisis de palabras clave en el título y órgano emisor.
    """
    texto = (titulo + " " + organo).lower()

    # 1. Digitalización / Robótica
    patrones_digital = [
        "digital",
        "robotic",
        "ia",
        "inteligencia artificial",
        "software",
        "comput",
        "comunicaciones",
        "conectividad",
        "ciberseguridad",
        "tecnologias de la informacion",
        "tic",
        "internet",
        "redes",
        "sensor",
    ]
    if any(p in texto for p in patrones_digital):
        return "Digitalización/Robótica"

    # 2. Transición Verde / Sostenibilidad
    patrones_verde = [
        "verde",
        "sostenib",
        "clima",
        "energia",
        "circular",
        "ambiental",
        "ecolog",
        "descarboni",
        "renovab",
        "residuo",
        "agua",
        "emisiones",
        "biodiversidad",
        "conservacion",
        "eficiencia energetica",
    ]
    if any(p in texto for p in patrones_verde):
        return "Transición Verde/Sostenibilidad"

    # 3. Agroalimentario
    patrones_agro = [
        "agro",
        "agrari",
        "agricult",
        "pesca",
        "aliment",
        "cultiv",
        "ganad",
        "rural",
        "granja",
        "vitivinicola",
        "feader",
        "pac ",
    ]
    if any(p in texto for p in patrones_agro):
        return "Agroalimentario"

    # 4. Educación / Social
    patrones_social = [
        "empleo",
        "taller",
        "laboral",
        "educa",
        "joven",
        "social",
        "formacion",
        "capacita",
        "integra",
        "beca",
        "inclusion",
        "cohesion",
        "igualdad",
        "vulnerab",
        "escuela",
        "enseñanza",
    ]
    if any(p in texto for p in patrones_social):
        return "Educación/Social"

    # 5. I+D+i Científica (Fallback para investigación técnica)
    patrones_idi = [
        "ciencia",
        "cienti",
        "investig",
        "tecnolog",
        "innovac",
        "universi",
        "i+d",
        "desarrollo experimental",
        "patente",
    ]
    if any(p in texto for p in patrones_idi):
        return "I+D+i Científica"

    # Si no se detectan patrones específicos, clasificamos en I+D+i por defecto
    # al ser un dashboard industrial, o bien a Sostenibilidad / Social según contexto.
    return "I+D+i Científica"


class Normalizer:
    """
    Clase encargada de unificar los diccionarios crudos de ingesta al esquema validado.
    """

    @staticmethod
    def normalizar_registro(registro: dict[str, Any]) -> SubvencionSchema | None:
        """
        Normaliza un único registro crudo según su origen geográfico.

        Si ocurre un error de validación, retorna None y registra el fallo sin abortar.
        """
        origen = registro.get("_extractor_source")
        es_simulado = bool(registro.get("_is_simulated", False))

        try:
            if origen == "Navarra":
                # Mapeo para Navarra — CKAN real (Rehabilitación
                # protegida) y datos simulados
                # Campos reales CKAN: "OrgGestor/Capit/Partida
                # Presupuestaria", "Presupuesto General", "Subvencion",
                # "Ano", "No Exp", "No Viv"
                # Campos simulados: "Linea_Ayuda",
                # "Presupuesto_Euros", etc.
                tipo = (
                    registro.get("Linea_Ayuda")
                    or registro.get(
                        "OrgGestor/Capit/Partida Presupuestaria"
                    )
                    or registro.get("Concepto")
                    or registro.get("Titulo")
                    or "Subvención Autonómica"
                )
                cuantia = limpiar_importe(
                    registro.get("Presupuesto_Euros")
                    or registro.get("Subvencion")
                    or registro.get("Presupuesto General")
                    or registro.get("Importe")
                    or 0.0
                )
                # Los datos CKAN de Navarra solo tienen "Ano" (año),
                # no una fecha completa de plazo
                ano_raw = registro.get("Ano")
                if ano_raw and not registro.get("Fecha_Limite"):
                    fecha = limpiar_fecha(f"{ano_raw}-12-31")
                else:
                    fecha = limpiar_fecha(
                        registro.get("Fecha_Limite")
                        or registro.get("Fecha_Resolucion")
                    )
                entidad = (
                    registro.get("Organismo_Convocante")
                    or registro.get("Organo")
                    or "Gobierno de Navarra"
                )
                actividad = clasificar_actividad(
                    str(tipo), str(entidad)
                )
                # Navarra CKAN no proporciona URLs directas
                url_convocatoria = ""

            elif origen == "España":
                # Mapeo para España — BDNS real (endpoint /busqueda)
                # Campos reales: "descripcion", "fechaRecepcion",
                # "nivel1", "nivel3", "numeroConvocatoria"
                # La API de búsqueda NO incluye cuantía presupuestaria
                tipo = (
                    registro.get("descripcion")
                    or registro.get("titulo_oficial")
                    or "Convocatoria Estatal"
                )
                cuantia = limpiar_importe(
                    registro.get("presupuesto_euros")
                    or registro.get("importe")
                    or 0.0
                )
                fecha = limpiar_fecha(
                    registro.get("fechaRecepcion")
                    or registro.get("fecha_fin_plazo")
                )
                entidad = (
                    registro.get("nivel3")
                    or registro.get("organo_emisor")
                    or registro.get("organismo")
                    or "Administración General del Estado"
                )
                actividad = clasificar_actividad(
                    str(tipo), str(entidad)
                )
                # Construir URL de la ficha de convocatoria en BDNS
                num_conv = registro.get("numeroConvocatoria")
                if num_conv:
                    url_convocatoria = (
                        "https://www.infosubvenciones.es/"
                        "bdnstrans/GE/es/convocatoria/"
                        f"{num_conv}"
                    )
                else:
                    url_convocatoria = ""

            elif origen == "Europa":
                # Mapeo para Europa — Datos aplanados del extractor
                # SEDIA. Campos: "title", "budget", "programme",
                # "date", "keywords"
                tipo = (
                    registro.get("title")
                    or "European Funding Call"
                )
                cuantia = limpiar_importe(
                    registro.get("budget") or 0.0
                )
                fecha = limpiar_fecha(
                    registro.get("date")
                    or registro.get("submission_deadline")
                )
                entidad = (
                    registro.get("programme")
                    or "Comisión Europea"
                )
                actividad = clasificar_actividad(
                    str(tipo), str(entidad)
                )
                # URL directa proporcionada por SEDIA
                url_convocatoria = registro.get("url", "")
            else:
                logger.error(
                    f"Registro con origen desconocido "
                    f"'{origen}': {registro}"
                )
                return None

            # Construimos y validamos mediante Pydantic
            return SubvencionSchema(
                Tipo_Subvencion=str(tipo),
                Cuantia=float(cuantia),
                Fecha_Vigencia=fecha,
                Entidad_Convocante=str(entidad),
                Ambito_Territorial=origen,  # type: ignore
                Actividad_Relacionada=actividad,  # type: ignore
                URL_Convocatoria=url_convocatoria,
                Es_Simulado=es_simulado,
            )
        except Exception as exc:
            logger.error(
                f"Error de normalización/validación en registro "
                f"({origen}): {exc}. "
                f"Registro conflictivo: {registro}"
            )
            return None

    @classmethod
    def normalizar_lote(cls, registros: list[dict[str, Any]]) -> list[SubvencionSchema]:
        """
        Normaliza registros crudos omitiendo los fallidos.
        """
        resultados: list[SubvencionSchema] = []
        for reg in registros:
            norm = cls.normalizar_registro(reg)
            if norm is not None:
                resultados.append(norm)
        return resultados
