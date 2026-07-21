"""
Módulo de Heurísticas Clásicas.
"""

def clasificar_actividad_clasica(titulo: str, organo: str) -> str:
    """
    Clasifica de forma automatizada la subvención en uno de los 5 sectores estratégicos
    basándose en el análisis de palabras clave en el título y órgano emisor.
    """
    texto = (titulo + " " + organo).lower()

    # 1. Digitalización / Robótica
    patrones_digital = [
        "digital", "robotic", "ia", "inteligencia artificial", "software",
        "comput", "comunicaciones", "conectividad", "ciberseguridad",
        "tecnologias de la informacion", "tic", "internet", "redes", "sensor",
    ]
    if any(p in texto for p in patrones_digital):
        return "Digitalización/Robótica"

    # 2. Transición Verde / Sostenibilidad
    patrones_verde = [
        "verde", "sostenib", "clima", "energia", "circular", "ambiental",
        "ecolog", "descarboni", "renovab", "residuo", "agua", "emisiones",
        "biodiversidad", "conservacion", "eficiencia energetica",
    ]
    if any(p in texto for p in patrones_verde):
        return "Transición Verde/Sostenibilidad"

    # 3. Agroalimentario
    patrones_agro = [
        "agro", "agrari", "agricult", "pesca", "aliment", "cultiv", "ganad",
        "rural", "granja", "vitivinicola", "feader", "pac ",
    ]
    if any(p in texto for p in patrones_agro):
        return "Agroalimentario"

    # 4. Educación / Social
    patrones_social = [
        "empleo", "taller", "laboral", "educa", "joven", "social", "formacion",
        "capacita", "integra", "beca", "inclusion", "cohesion", "igualdad",
        "vulnerab", "escuela", "enseñanza",
    ]
    if any(p in texto for p in patrones_social):
        return "Educación/Social"

    # 5. Emprendimiento / Startups
    patrones_emprendimiento = [
        "emprend", "startup", "creación de empresas", "aceleradora", "incubadora",
        "negocio", "pyme", "autónom", "inversión semilla", "business angel"
    ]
    if any(p in texto for p in patrones_emprendimiento):
        return "Emprendimiento/Startups"

    # 6. I+D+i Científica (Fallback para investigación técnica)
    patrones_idi = [
        "ciencia", "cienti", "investig", "tecnolog", "innovac", "universi",
        "i+d", "desarrollo experimental", "patente",
    ]
    if any(p in texto for p in patrones_idi):
        return "I+D+i Científica"

    # Si no se detectan patrones específicos, clasificamos en I+D+i por defecto
    return "I+D+i Científica"
