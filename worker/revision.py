"""Controles sin IA para la revisión de la idea principal (RF-10).

El modelo pequeño (qwen3:4b) a veces aprueba lo que no debe: calificó «sADSDFDSAasd» como
«coincide» y además escribió «te faltó…». Estos controles son reglas fijas, rápidas y
predecibles que van antes y después de la IA:

1. Antes: si la respuesta no tiene palabras reales del español (teclazos, letras al azar)
   o es demasiado corta, no se gasta la IA: queda «por mejorar» con una pista amable.
2. Después: si la respuesta no comparte ni una palabra de contenido con la noticia, la idea
   esperada o sus elementos clave, no puede «coincidir»; y si la IA dice «coincide» pero
   también dice que algo faltó, queda «coincide en parte».
"""

import re
import unicodedata

from worker import gramatica

MIN_PALABRAS_CON_CONTENIDO = 2
PROPORCION_REAL_MINIMA = 0.5

EXPLICACION_SIN_SENTIDO = ("No logramos entender tu respuesta. Lee otra vez el comienzo de la noticia "
                           "y escribe con tus palabras de qué trata.")
EXPLICACION_SIN_RELACION = ("Tu respuesta no habla de lo que cuenta la noticia. Vuelve a leerla y "
                            "escribe quién hizo qué y por qué es importante.")

# Palabras que no cuentan como contenido al comparar con la noticia
VACIAS = set("""
a al algo algun alguna alguno algunos ante antes aqui asi aun bien cada como con contra cual
cuando de del desde donde dos el ella ellas ello ellos en entre era eran es esa esas ese eso
esos esta estaba estan estas este esto estos fue fueron ha hace hacia han hasta hay la las le
les lo los mas me mi muy nada ni no nos o otra otras otro otros para pero poco por porque que
quien se segun ser si sin sobre son su sus tambien tan te tiene tienen todo todos tu un una
uno unos y ya yo noticia texto trata habla dice dicen
""".split())

_PALABRA = re.compile(r"[^\W\d_]+")
_FIN_DE_FRASE = re.compile(r"[.!?]\s")


def _norm(palabra: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", palabra.lower())
    return "".join(c for c in sin_tildes if not unicodedata.combining(c))


def _raiz(palabra: str) -> str:
    """Comparación tolerante a la forma: «falleció», «fallecimiento» y «fallecido» → «falle»."""
    return _norm(palabra)[:5]


def _contenido(texto: str) -> list[str]:
    return [p for p in _PALABRA.findall(texto or "") if len(p) >= 4 and _norm(p) not in VACIAS]


def tiene_sentido(respuesta: str) -> bool:
    """¿Hay palabras reales del español en la respuesta?

    Usa el vocabulario del analizador (las palabras que conoce); sin analizador solo
    exige un mínimo de palabras con contenido.
    """
    palabras = _PALABRA.findall(respuesta or "")
    if not palabras:
        return False
    nlp = gramatica.analizador()
    if nlp is None or not nlp.vocab.vectors.shape[0]:
        return len(_contenido(respuesta)) >= MIN_PALABRAS_CON_CONTENIDO
    doc = nlp(respuesta)
    letras = [t for t in doc if t.is_alpha]
    reales = [t for t in letras if not t.is_oov]
    con_contenido = [t for t in reales if not t.is_stop and len(t.text) >= 3]
    return (len(con_contenido) >= MIN_PALABRAS_CON_CONTENIDO
            and len(reales) / max(1, len(letras)) >= PROPORCION_REAL_MINIMA)


def palabras_en_comun(respuesta: str, *referencias: str) -> int:
    """Cuántas palabras de contenido de la respuesta aparecen en la noticia o en la idea esperada."""
    claves = {_raiz(p) for r in referencias for p in _contenido(r)}
    return sum(1 for p in _contenido(respuesta) if _raiz(p) in claves)


def primera_frase(texto: str, max_palabras: int = 12) -> str:
    """El comienzo de la noticia, copiado tal cual (sirve de cita: existe en el texto)."""
    texto = (texto or "").strip()
    fin = _FIN_DE_FRASE.search(texto)
    frase = texto[: fin.start() + 1] if fin else texto
    palabras = list(re.finditer(r"\S+", frase))
    if len(palabras) > max_palabras:
        frase = frase[: palabras[max_palabras - 1].end()]
    return frase


def ajustar_veredicto(veredicto: str, faltantes: str, explicacion: str,
                      en_comun: int) -> tuple[str, str | None]:
    """Corrige lo que la IA no puede decir. Devuelve (veredicto, explicación nueva o None)."""
    if en_comun == 0 and veredicto != "por_mejorar":
        return "por_mejorar", EXPLICACION_SIN_RELACION
    if veredicto == "coincide" and ((faltantes or "").strip() or re.search(r"\bfalt", explicacion or "", re.I)):
        return "coincide_en_parte", None
    return veredicto, None
