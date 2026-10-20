"""
Extractor de Subvenciones y Becas de Fundaciones Privadas (Navarra, España y Europa).

Este módulo recopila convocatorias de entidades privadas, fundaciones corporativas
y filantrópicas en territorio foral (Navarra), nacional (España) y comunitario
(Unión Europea), combinando rastreo ligero HTML con un catálogo verificado resiliente.
"""

import logging
import re
from typing import Any

import httpx
from bs4 import BeautifulSoup

from src.ingestion.base_extractor import BaseExtractor

logger = logging.getLogger(__name__)

# Catálogo maestro de fundaciones privadas vigiladas (Navarra, España y Europa)
CATALOGO_FUNDACIONES_PRIVADAS: list[dict[str, Any]] = [
    # --- NAVARRA ---
    {
        "entidad": "Fundación Caja Navarra y Fundación ”la Caixa” (Programa Innova)",
        "titulo_base": (
            "Programa Innova Social y Cultural Navarra - Proyectos de Transformación"
        ),
        "cuantia_defecto": 45000.0,
        "fecha_vigencia": "2027-03-31",
        "ambito": "Navarra",
        "sector": "Educación/Social",
        "url": "https://programa-innova.es/",
        "keywords": ["innova", "social", "cultural", "rural", "navarra", "caixa"],
    },
    {
        "entidad": "Laboratorios Cinfa",
        "titulo_base": (
            "Ayudas Cinfa a Entidades Sociales y Apoyo a Personas Cuidadoras"
        ),
        "cuantia_defecto": 60000.0,
        "fecha_vigencia": "2027-02-28",
        "ambito": "Navarra",
        "sector": "Educación/Social",
        "url": (
            "https://www.cinfa.com/sobre-cinfa/lo-que-nos-mueve/"
            "ayudas-y-subvenciones/"
        ),
        "keywords": ["cinfa", "pacientes", "cuidadores", "salud", "social"],
    },
    {
        "entidad": "Fundación LuzIA",
        "titulo_base": (
            "Programa de Impulso a la Inteligencia Artificial Ética e Inclusiva"
        ),
        "cuantia_defecto": 20000.0,
        "fecha_vigencia": "2027-04-15",
        "ambito": "Navarra",
        "sector": "Digitalización/Robótica",
        "url": "https://www.fundacionluzia.com/quienes-somos/",
        "keywords": ["ia", "inteligencia artificial", "luzia", "digital", "ética"],
    },
    {
        "entidad": "Consorcio SINAI - Agentes de Ejecución I+D+i Navarra",
        "titulo_base": (
            "Proyectos Colaborativos de Transferencia Tecnológica SINAI Navarra"
        ),
        "cuantia_defecto": 95000.0,
        "fecha_vigencia": "2027-05-30",
        "ambito": "Navarra",
        "sector": "I+D+i Científica",
        "url": (
            "https://www.navarra.es/es/tramites/on/-/line/"
            "Registro-de-agentes-de-ejecucion-del-Sistema-Navarro-de-I-D-i-SINAI"
        ),
        "keywords": ["sinai", "i+d+i", "investigación", "tecnología", "navarra"],
    },
    # --- ESPAÑA ---
    {
        "entidad": "Argal Alimentación (Taller Argal)",
        "titulo_base": (
            "Becas Taller Argal #GenteQueAmaLoQueHace para Proyectos con Impacto"
        ),
        "cuantia_defecto": 25000.0,
        "fecha_vigencia": "2027-01-31",
        "ambito": "España",
        "sector": "Agroalimentario",
        "url": "https://argal.com/taller-argal/becas-2025/",
        "keywords": ["argal", "becas", "alimentación", "sostenibilidad", "impacto"],
    },
    {
        "entidad": "Fundación ”la Caixa” (CaixaResearch)",
        "titulo_base": (
            "Convocatoria CaixaResearch de Investigación en Salud y Biomedicina"
        ),
        "cuantia_defecto": 500000.0,
        "fecha_vigencia": "2026-11-18",
        "ambito": "España",
        "sector": "I+D+i Científica",
        "url": "https://caixaresearch.org/es/convocatoria-investigacion-salud",
        "keywords": ["caixaresearch", "salud", "biomedicina", "investigación", "caixa"],
    },
    {
        "entidad": "Fundación BBVA",
        "titulo_base": (
            "Becas Leonardo a Investigadores y Creadores Culturales"
        ),
        "cuantia_defecto": 40000.0,
        "fecha_vigencia": "2027-03-20",
        "ambito": "España",
        "sector": "I+D+i Científica",
        "url": "https://www.redleonardo.es/becas/",
        "keywords": ["bbva", "leonardo", "ciencia", "cultura", "investigadores"],
    },
    {
        "entidad": "Fundación Mapfre",
        "titulo_base": (
            "Ayudas a la Investigación Ignacio H. de Larramendi y Programa Accedemos"
        ),
        "cuantia_defecto": 30000.0,
        "fecha_vigencia": "2026-12-15",
        "ambito": "España",
        "sector": "Educación/Social",
        "url": (
            "https://www.fundacionmapfre.org/premios-ayudas/"
            "investigacion-ignacio-larramendi/"
        ),
        "keywords": ["mapfre", "larramendi", "accedemos", "empleo", "salud"],
    },
    {
        "entidad": "Fundación Botín",
        "titulo_base": (
            "Programa Mind the Gap y Talento Solidario para "
            "Emprendimiento Biotecnológico y Social"
        ),
        "cuantia_defecto": 100000.0,
        "fecha_vigencia": "2027-04-10",
        "ambito": "España",
        "sector": "Emprendimiento/Startups",
        "url": (
            "https://fundacionbotin.org/programas/ciencia/"
            "transferencia-tecnologica/"
        ),
        "keywords": ["botin", "mind the gap", "startups", "biotecnología", "talento"],
    },
    {
        "entidad": "Fundación Repsol",
        "titulo_base": (
            "Fondo de Emprendedores: Aceleración de Startups en Transición Energética"
        ),
        "cuantia_defecto": 120000.0,
        "fecha_vigencia": "2027-03-15",
        "ambito": "España",
        "sector": "Transición Verde/Sostenibilidad",
        "url": "https://www.fundacionrepsol.com/es/fondo-emprendedores/",
        "keywords": ["repsol", "energía", "descarbonización", "startups", "clima"],
    },
    # --- COMUNIDAD EUROPEA ---
    {
        "entidad": "Fondation Daniel et Nina Carasso",
        "titulo_base": (
            "Convocatoria Arte Ciudadano y Sistemas Alimentarios "
            "Sostenibles (Francia/España/UE)"
        ),
        "cuantia_defecto": 50000.0,
        "fecha_vigencia": "2027-02-15",
        "ambito": "Europa",
        "sector": "Agroalimentario",
        "url": "https://fondationcarasso.org/es/arte-ciudadano/",
        "keywords": [
            "carasso",
            "arte ciudadano",
            "alimentación sostenible",
            "ecología",
        ],
    },
    {
        "entidad": "European Cultural Foundation (ECF)",
        "titulo_base": (
            "Culture of Solidarity & European Collaboration Grants"
        ),
        "cuantia_defecto": 30000.0,
        "fecha_vigencia": "2026-11-30",
        "ambito": "Europa",
        "sector": "Educación/Social",
        "url": "https://culturalfoundation.eu/grants/",
        "keywords": ["ecf", "cultural foundation", "europe", "solidarity", "culture"],
    },
    {
        "entidad": "Philea - Philanthropy Europe Association",
        "titulo_base": (
            "European Philanthropy Coalition for Climate & Democracy Grants"
        ),
        "cuantia_defecto": 75000.0,
        "fecha_vigencia": "2027-05-01",
        "ambito": "Europa",
        "sector": "Transición Verde/Sostenibilidad",
        "url": "https://philea.eu/how-we-work/programmes/",
        "keywords": ["philea", "philanthropy", "europe", "climate", "foundations"],
    },
    {
        "entidad": "Robert Bosch Stiftung",
        "titulo_base": (
            "Funding for European Civil Society, Health and Climate Action"
        ),
        "cuantia_defecto": 85000.0,
        "fecha_vigencia": "2027-04-20",
        "ambito": "Europa",
        "sector": "Transición Verde/Sostenibilidad",
        "url": "https://www.bosch-stiftung.de/en/funding-areas",
        "keywords": ["bosch", "stiftung", "climate", "health", "europe"],
    },
    {
        "entidad": "VolkswagenStiftung",
        "titulo_base": (
            "Pioneering Research & Artificial Intelligence Impact Grants (EU)"
        ),
        "cuantia_defecto": 250000.0,
        "fecha_vigencia": "2027-06-15",
        "ambito": "Europa",
        "sector": "Digitalización/Robótica",
        "url": "https://www.volkswagenstiftung.de/en/funding",
        "keywords": ["volkswagenstiftung", "research", "ai", "science", "europe"],
    },
    {
        "entidad": "Fondazione Cariplo",
        "titulo_base": (
            "Bandi Ricerca Scientifica, Ambiente e Innovazione Sociale (UE)"
        ),
        "cuantia_defecto": 150000.0,
        "fecha_vigencia": "2027-03-30",
        "ambito": "Europa",
        "sector": "I+D+i Científica",
        "url": "https://www.fondazionecariplo.it/it/bandi/index.html",
        "keywords": ["cariplo", "ricerca", "ambiente", "innovazione", "europa"],
    },
]


def extraer_importe_texto(texto: str, fallback: float = 0.0) -> float:
    """
    Busca cuantías en euros dentro de un texto libre HTML
    (ej. '60.000 €' o '500.000 euros').
    """
    patron = re.compile(
        r"(\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?|\d{4,7})\s*(?:€|euros|eur\b)",
        re.IGNORECASE,
    )
    coincidencias = patron.findall(texto)
    if not coincidencias:
        return fallback

    importes_validos: list[float] = []
    for raw in coincidencias:
        limpio = raw.replace(".", "").replace(",", ".")
        try:
            val = float(limpio)
            if 500.0 <= val <= 50_000_000.0:
                importes_validos.append(val)
        except ValueError:
            continue

    return max(importes_validos) if importes_validos else fallback


class PrivateFoundationsExtractor(BaseExtractor):
    """
    Extractor de convocatorias de fundaciones privadas nacionales, forales y europeas.
    """

    def __init__(self) -> None:
        super().__init__(name="FundacionesPrivadas", source_label="Privada")

    def _extract_real(self) -> list[dict[str, Any]]:
        """
        Realiza un rastreo ligero de las portadas del catálogo de fundaciones privadas
        para enriquecer títulos o cuantías en vivo, manteniendo resiliencia por entidad.
        """
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,"
                "application/xml;q=0.9,*/*;q=0.8"
            ),
        }

        resultados: list[dict[str, Any]] = []
        with httpx.Client(
            timeout=6.0, headers=headers, follow_redirects=True
        ) as client:
            for item in CATALOGO_FUNDACIONES_PRIVADAS:
                registro = {
                    "titulo": item["titulo_base"],
                    "entidad": item["entidad"],
                    "cuantia": item["cuantia_defecto"],
                    "fecha_vigencia": item["fecha_vigencia"],
                    "ambito": item["ambito"],
                    "sector": item["sector"],
                    "url": item["url"],
                    "_tipo_financiacion": "Privada",
                }
                try:
                    resp = client.get(item["url"])
                    if resp.status_code == 200 and resp.text:
                        soup = BeautifulSoup(resp.text, "html.parser")
                        texto_plano = soup.get_text(separator=" ", strip=True)
                        registro["cuantia"] = extraer_importe_texto(
                            texto_plano, fallback=item["cuantia_defecto"]
                        )
                except (httpx.HTTPError, ValueError) as exc:
                    logger.debug(
                        f"[FundacionesPrivadas] Usando ficha base para "
                        f"{item['entidad']}: {exc}"
                    )

                resultados.append(registro)

        return resultados

    def _get_simulated_data(self) -> list[dict[str, Any]]:
        """
        Retorna el catálogo base de fundaciones privadas en modo simulación/fallback.
        """
        return [
            {
                "titulo": item["titulo_base"],
                "entidad": item["entidad"],
                "cuantia": item["cuantia_defecto"],
                "fecha_vigencia": item["fecha_vigencia"],
                "ambito": item["ambito"],
                "sector": item["sector"],
                "url": item["url"],
                "_tipo_financiacion": "Privada",
            }
            for item in CATALOGO_FUNDACIONES_PRIVADAS
        ]


# Ejemplo mínimo de uso:
# >>> from src.ingestion.private_foundations import PrivateFoundationsExtractor
# >>> ext = PrivateFoundationsExtractor()
# >>> datos = ext._get_simulated_data()
# >>> len(datos) >= 10
# True
