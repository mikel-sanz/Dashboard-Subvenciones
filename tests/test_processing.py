"""
Pruebas Unitarias para el Módulo de Procesamiento y Normalización.

Este módulo valida la limpieza de datos monetarios, fechas erráticas, clasificación
sectorial automática y la validación de registros mediante Pydantic.
"""

import datetime

from src.processing.normalizer import (
    Normalizer,
    clasificar_actividad,
    limpiar_fecha,
    limpiar_importe,
)


def test_limpiar_importe_vanguardia() -> None:
    """
    ARRANGE & ACT & ASSERT: Probar conversiones de strings numéricos con formato
                          europeo y anglosajón, floats, nulos e inválidos.
    """
    assert limpiar_importe("1.250,50") == 1250.50
    assert limpiar_importe("1,250.75") == 1250.75
    assert limpiar_importe("340000") == 340000.0
    assert limpiar_importe(450.25) == 450.25
    assert limpiar_importe(None) == 0.0
    assert limpiar_importe("importe_invalido_texto") == 0.0


def test_limpiar_fecha_vanguardia() -> None:
    """
    ARRANGE & ACT & ASSERT: Probar formatos ISO, español/europeo y fallback en fechas.
    """
    assert limpiar_fecha("2026-11-30") == datetime.date(2026, 11, 30)
    assert limpiar_fecha("15/09/2026") == datetime.date(2026, 9, 15)

    # Pruebas con datetime
    dt = datetime.datetime(2026, 8, 1, 10, 30, 0)
    assert limpiar_fecha(dt) == datetime.date(2026, 8, 1)

    # Fallback a hoy o futura en caso de vacío/nulo
    assert isinstance(limpiar_fecha(None), datetime.date)


def test_clasificar_actividad_palabras_clave() -> None:
    """
    ARRANGE & ACT & ASSERT: Validar clasificación por palabras clave.
    """
    # 1. Digitalización/Robótica
    assert (
        clasificar_actividad("Ayudas para la implantación de IA", "Ministerio")
        == "Digitalización/Robótica"
    )

    # 2. Sostenibilidad
    assert (
        clasificar_actividad(
            "Fomento de la economía circular en pymes", "Medio Ambiente"
        )
        == "Transición Verde/Sostenibilidad"
    )

    # 3. Agroalimentario
    assert (
        clasificar_actividad("Seguros agrarios combinados 2026", "Agricultura")
        == "Agroalimentario"
    )

    # 4. Social
    assert (
        clasificar_actividad("Subvenciones para escuelas taller de empleo", "Gobierno")
        == "Educación/Social"
    )

    # 5. I+D+i
    assert (
        clasificar_actividad(
            "Proyectos de investigación científica básica", "Universidad"
        )
        == "I+D+i Científica"
    )


def test_normalizador_lote_y_filtrado_corruptos() -> None:
    """
    ARRANGE: Crear un lote con registros válidos y uno corrupto.
    ACT: Normalizar el lote.
    ASSERT: Validar que se omitió el corrupto y se procesaron los válidos.
    """
    registros_crudos = [
        # Registro Navarra Válido
        {
            "Linea_Ayuda": "Digitalización Navarra",
            "Presupuesto_Euros": "45.000,00",
            "Fecha_Limite": "2026-10-30",
            "Organismo_Convocante": "Departamento Digital",
            "_extractor_source": "Navarra",
            "_is_simulated": True,
        },
        # Registro España Válido
        {
            "titulo_oficial": "PERTE Sostenible",
            "presupuesto_euros": 12000000.0,
            "fecha_fin_plazo": "15/12/2026",
            "organo_emisor": "Ministerio de Transición",
            "_extractor_source": "España",
            "_is_simulated": False,
        },
        # Registro Corrupto (le falta el tipo de subvención y la cuantía es negativa)
        {
            "Linea_Ayuda": "",
            "Presupuesto_Euros": -500.0,
            "_extractor_source": "Navarra",
            "_is_simulated": True,
        },
    ]

    resultados = Normalizer.normalizar_lote(registros_crudos)

    # Validar que solo se cargaron los 2 registros correctos y se ignoró el inválido
    assert len(resultados) == 2

    # Verificación de datos del primer registro normalizado (Navarra)
    assert resultados[0].Tipo_Subvencion == "Digitalización Navarra"
    assert resultados[0].Cuantia == 45000.0
    assert resultados[0].Fecha_Vigencia == datetime.date(2026, 10, 30)
    assert resultados[0].Ambito_Territorial == "Navarra"
    assert resultados[0].Actividad_Relacionada == "Digitalización/Robótica"
    assert resultados[0].Es_Simulado is True

    # Verificación de datos del segundo registro normalizado (España)
    assert resultados[1].Tipo_Subvencion == "PERTE Sostenible"
    assert resultados[1].Cuantia == 12000000.0
    assert resultados[1].Fecha_Vigencia == datetime.date(2026, 12, 15)
    assert resultados[1].Ambito_Territorial == "España"
    assert resultados[1].Actividad_Relacionada == "Transición Verde/Sostenibilidad"
    assert resultados[1].Es_Simulado is False
