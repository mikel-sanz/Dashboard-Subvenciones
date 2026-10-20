"""
Pruebas unitarias para el módulo de subvenciones privadas y explorador web (Patrón AAA).

Valida la extracción del catálogo de fundaciones privadas (Navarra, España, Europa),
la normalización con Tipo_Financiacion='Privada', la validación anti-SSRF del
buscador web y la persistencia en la base de datos SQLite en memoria.
"""

import httpx

from src.ingestion.private_foundations import (
     PrivateFoundationsExtractor,
    extraer_importe_texto,
)
from src.ingestion.web_hunter import PrivateWebHunter, validar_url_segura
from src.processing.normalizer import Normalizer
from src.storage.database import DatabaseManager


def test_extraer_importe_texto_formato_europeo() -> None:
    """
    Valida que extraer_importe_texto detecta correctamente importes en euros
    formateados con puntos de miles dentro de un párrafo HTML libre.
    """
    # Arrange
    texto_html = (
        "La Fundación convoca becas con una dotación máxima de 60.000 € "
        "y ayudas accesorias de 15.000 euros por proyecto seleccionado."
    )

    # Act
    importe = extraer_importe_texto(texto_html, fallback=5000.0)

    # Assert
    assert importe == 60000.0


def test_normalizacion_catalogo_fundaciones_privadas() -> None:
    """
    Valida que el catálogo de fundaciones privadas (Navarra, España y Europa)
    se normaliza íntegramente con Tipo_Financiacion='Privada'.
    """
    # Arrange
    extractor = PrivateFoundationsExtractor()
    datos_crudos = extractor._get_simulated_data()
    for reg in datos_crudos:
        reg["_extractor_source"] = "Privada"
        reg["_is_simulated"] = True

    # Act
    lote_validado = Normalizer.normalizar_lote(datos_crudos)

    # Assert
    assert len(lote_validado) >= 15
    assert all(sub.Tipo_Financiacion == "Privada" for sub in lote_validado)
    ambitos = {sub.Ambito_Territorial for sub in lote_validado}
    assert {"Navarra", "España", "Europa"}.issubset(ambitos)


def test_seguridad_anti_ssrf_validar_url() -> None:
    """
    Valida que el filtro anti-SSRF bloquea direcciones locales/internas y esquemas
    no permitidos, permitiendo dominios públicos HTTPS.
    """
    # Arrange
    url_local = "http://127.0.0.1:8080/admin"
    url_file = "file:///etc/passwd"
    url_valida = "https://fondationcarasso.org/es/arte-ciudadano/"

    # Act
    ok_local, _ = validar_url_segura(url_local)
    ok_file, _ = validar_url_segura(url_file)
    ok_valida, _ = validar_url_segura(url_valida)

    # Assert
    assert ok_local is False
    assert ok_file is False
    assert ok_valida is True


def test_buscador_web_hunter_filtrado_catalogo() -> None:
    """
    Valida que PrivateWebHunter filtra adecuadamente por palabra clave y ámbito.
    """
    # Arrange & Act
    res_navarra = PrivateWebHunter.buscar_convocatorias_privadas(
        query="cinfa", ambito_filtro="Navarra"
    )
    res_europa = PrivateWebHunter.buscar_convocatorias_privadas(
        query="", ambito_filtro="Europa"
    )

    # Assert
    assert len(res_navarra) == 1
    assert "Cinfa" in res_navarra[0].Entidad_Convocante
    assert len(res_europa) >= 5
    assert all(r.Ambito_Territorial == "Europa" for r in res_europa)


def test_inspeccionar_url_en_vivo_mock(monkeypatch) -> None:
    """
    Valida el raspado HTML en vivo de una fundación privada simulando la respuesta HTTP.
    """
    # Arrange
    html_simulado = """
    <html>
      <head>
        <title>Fundación Ejemplo Europa</title>
        <meta property="og:site_name" content="Fundación Europea de Innovación" />
      </head>
      <body>
        <h2>Convocatoria de Becas Europeas de Inteligencia Artificial 2027</h2>
        <p>Dotación total de 120.000 € para proyectos hasta el 15/11/2027.</p>
      </body>
    </html>
    """

    class DummyResponse:
        status_code = 200
        text = html_simulado

        def raise_for_status(self) -> None:
            pass

    monkeypatch.setattr(
        httpx.Client, "get", lambda self, url, **kwargs: DummyResponse()
    )

    # Act
    detectadas, msg = PrivateWebHunter.inspeccionar_url_en_vivo(
        url="https://fundacion-ejemplo.eu/convocatorias",
        ambito="Europa",
    )

    # Assert
    assert len(detectadas) == 1
    assert detectadas[0].Tipo_Financiacion == "Privada"
    assert detectadas[0].Ambito_Territorial == "Europa"
    assert detectadas[0].Cuantia == 120000.0
    assert "Fundación Europea de Innovación" in detectadas[0].Entidad_Convocante


def test_persistencia_tipo_financiacion_db() -> None:
    """
    Valida que DatabaseManager persiste y recupera la columna Tipo_Financiacion.
    """
    # Arrange
    db = DatabaseManager("sqlite:///:memory:")
    sub_privada = PrivateWebHunter.buscar_convocatorias_privadas(
        query="carasso", ambito_filtro="Europa"
    )

    # Act
    insertados = db.bulk_insert(sub_privada)
    df = db.load_as_dataframe()

    # Assert
    assert insertados == 1
    assert "Tipo_Financiacion" in df.columns
    assert df.iloc[0]["Tipo_Financiacion"] == "Privada"
