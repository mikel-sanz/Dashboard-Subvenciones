"""
Motor de Búsqueda y Exploración Web en Vivo de Subvenciones Privadas.

Permite inspeccionar URLs externas de fundaciones privadas de forma segura
(con protección anti-SSRF) para extraer convocatorias en vivo, así como
filtrar y buscar ayudas privadas en territorio foral, nacional y europeo.
"""

import datetime
import ipaddress
import logging
import re
import socket
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from src.ingestion.private_foundations import (
    CATALOGO_FUNDACIONES_PRIVADAS,
    extraer_importe_texto,
)
from src.processing.classifier import SemanticClassifier
from src.processing.schemas import SubvencionSchema

logger = logging.getLogger(__name__)


def validar_url_segura(url: str) -> tuple[bool, str]:
    """
    Valida que una URL proporcionada por el usuario sea HTTP/HTTPS y no apunte
    a redes internas o direcciones de loopback (prevención de SSRF).
    """
    url_limpia = url.strip()
    if not url_limpia:
        return False, "La URL no puede estar vacía."

    parsed = urlparse(url_limpia)
    if parsed.scheme not in ("http", "https"):
        return False, "Solo se permiten esquemas HTTP o HTTPS."

    hostname = parsed.hostname
    if not hostname:
        return False, "La URL no contiene un dominio válido."

    host_lower = hostname.lower()
    hosts_locales = ("localhost", "127.0.0.1", "0.0.0.0", "::1")
    if host_lower in hosts_locales or host_lower.endswith(".local"):
        return False, "No se permite el acceso a direcciones locales o internas."

    try:
        ip_obj = ipaddress.ip_address(host_lower)
        if (
            ip_obj.is_private
            or ip_obj.is_loopback
            or ip_obj.is_link_local
            or ip_obj.is_reserved
        ):
            return False, "Dirección IP privada o reservada bloqueada por seguridad."
    except ValueError:
        try:
            ip_resuelta = socket.gethostbyname(host_lower)
            ip_obj = ipaddress.ip_address(ip_resuelta)
            if (
                ip_obj.is_private
                or ip_obj.is_loopback
                or ip_obj.is_link_local
                or ip_obj.is_reserved
            ):
                return (
                    False,
                    "El dominio resuelve a una IP interna bloqueada por seguridad.",
                )
        except socket.gaierror:
            # Si falla el DNS en entorno restringido, httpx gestionará el error
            pass

    return True, ""


def extraer_fecha_texto(texto: str) -> datetime.date:
    """
    Intenta localizar una fecha límite en formato DD/MM/YYYY o DD-MM-YYYY.
    Si no encuentra una fecha futura, asigna 120 días a partir de hoy.
    """
    hoy = datetime.date.today()
    patron_dmy = re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](202[6-9])\b")
    for dia_s, mes_s, anio_s in patron_dmy.findall(texto):
        try:
            fecha_cand = datetime.date(int(anio_s), int(mes_s), int(dia_s))
            if fecha_cand >= hoy:
                return fecha_cand
        except ValueError:
            continue

    return hoy + datetime.timedelta(days=120)


def _extraer_entidad_y_titulos(
    soup: BeautifulSoup, dominio: str, entidad_manual: str
) -> tuple[str, list[str]]:
    """
    Extrae el nombre de la entidad convocante y los títulos candidatos de becas/ayudas
    a partir del árbol DOM de BeautifulSoup.
    """
    entidad = entidad_manual.strip()
    if not entidad:
        og_site = soup.find("meta", property="og:site_name")
        if og_site and og_site.get("content"):
            entidad = str(og_site.get("content")).strip()
        else:
            entidad = f"Fundación / Entidad ({dominio})"

    palabras_clave_ayuda = (
        "beca",
        "ayuda",
        "subvenci",
        "convocatoria",
        "premio",
        "grant",
        "call",
        "funding",
        "programa",
        "innova",
        "bando",
    )

    candidatos_titulos: list[str] = []
    for tag in soup.find_all(["h1", "h2", "h3"]):
        texto_h = tag.get_text(" ", strip=True)
        es_longitud_valida = 10 <= len(texto_h) <= 180
        contiene_kw = any(kw in texto_h.lower() for kw in palabras_clave_ayuda)
        if es_longitud_valida and contiene_kw and texto_h not in candidatos_titulos:
            candidatos_titulos.append(texto_h)

    if not candidatos_titulos:
        if soup.title and soup.title.string:
            candidatos_titulos.append(soup.title.string.strip()[:160])
        else:
            candidatos_titulos.append(f"Convocatoria Privada en {dominio}")

    return entidad, candidatos_titulos


class PrivateWebHunter:
    """
    Explorador interactivo para buscar y extraer subvenciones privadas en internet.
    """

    @staticmethod
    def buscar_convocatorias_privadas(
        query: str = "",
        ambito_filtro: str = "Todos",
        sector_filtro: str = "Todos",
    ) -> list[SubvencionSchema]:
        """
        Filtra y busca convocatorias dentro del catálogo de fundaciones privadas
        de Navarra, España y Europa por palabras clave, ámbito y sector.
        """
        terminos = [t.strip().lower() for t in query.split() if t.strip()]
        resultados: list[SubvencionSchema] = []

        for item in CATALOGO_FUNDACIONES_PRIVADAS:
            if ambito_filtro != "Todos" and item["ambito"] != ambito_filtro:
                continue
            if sector_filtro != "Todos" and item["sector"] != sector_filtro:
                continue

            if terminos:
                kws = " ".join(item.get("keywords", []))
                texto_busqueda = (
                    f"{item['entidad']} {item['titulo_base']} "
                    f"{kws} {item['ambito']} {item['sector']}"
                ).lower()
                if not all(term in texto_busqueda for term in terminos):
                    continue

            esquema = SubvencionSchema(
                Tipo_Subvencion=item["titulo_base"],
                Cuantia=float(item["cuantia_defecto"]),
                Fecha_Vigencia=datetime.date.fromisoformat(item["fecha_vigencia"]),
                Entidad_Convocante=item["entidad"],
                Ambito_Territorial=item["ambito"],
                Actividad_Relacionada=item["sector"],
                URL_Convocatoria=item["url"],
                Tipo_Financiacion="Privada",
                Es_Simulado=False,
            )
            resultados.append(esquema)

        return resultados

    @staticmethod
    def inspeccionar_url_en_vivo(
        url: str,
        ambito: str = "España",
        entidad_manual: str = "",
    ) -> tuple[list[SubvencionSchema], str]:
        """
        Conecta en vivo a la URL de una fundación o entidad privada, analiza su
        estructura HTML para detectar convocatorias, importes y plazos, y devuelve
        objetos validados listos para persistencia.
        """
        es_segura, motivo = validar_url_segura(url)
        if not es_segura:
            return [], motivo

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

        try:
            with httpx.Client(
                timeout=12.0, headers=headers, follow_redirects=True
            ) as client:
                response = client.get(url.strip())
                response.raise_for_status()
                html_text = response.text
        except httpx.HTTPError as exc:
            logger.warning(f"[PrivateWebHunter] Error HTTP al consultar '{url}': {exc}")
            return [], f"No se pudo conectar con la URL indicada: {exc}"

        soup = BeautifulSoup(html_text, "html.parser")
        parsed_url = urlparse(url.strip())
        dominio = (parsed_url.hostname or "Entidad Privada").replace("www.", "")

        entidad, candidatos_titulos = _extraer_entidad_y_titulos(
            soup, dominio, entidad_manual
        )
        texto_completo = soup.get_text(" ", strip=True)
        cuantia_detectada = extraer_importe_texto(texto_completo, fallback=0.0)
        fecha_detectada = extraer_fecha_texto(texto_completo)

        ambitos_validos = ("Europa", "España", "Navarra", "Pamplona")
        ambito_valido = ambito if ambito in ambitos_validos else "España"

        subvenciones_detectadas: list[SubvencionSchema] = []
        for titulo in candidatos_titulos[:5]:
            sector_inferido = SemanticClassifier.clasificar(titulo, entidad)
            esquema = SubvencionSchema(
                Tipo_Subvencion=titulo,
                Cuantia=cuantia_detectada,
                Fecha_Vigencia=fecha_detectada,
                Entidad_Convocante=entidad,
                Ambito_Territorial=ambito_valido,  # type: ignore
                Actividad_Relacionada=sector_inferido,  # type: ignore
                URL_Convocatoria=url.strip(),
                Tipo_Financiacion="Privada",
                Es_Simulado=False,
            )
            subvenciones_detectadas.append(esquema)

        mensaje = (
            f"Se han detectado {len(subvenciones_detectadas)} "
            f"convocatoria(s) en {dominio}."
        )
        return subvenciones_detectadas, mensaje


# Ejemplo mínimo de uso:
# >>> from src.ingestion.web_hunter import validar_url_segura
# >>> validar_url_segura("https://fondationcarasso.org/es/arte-ciudadano/")[0]
# True
# >>> validar_url_segura("http://127.0.0.1/admin")[0]
# False
