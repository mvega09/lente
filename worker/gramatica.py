"""Tipo gramatical de las palabras cargadas con un analizador de español (spaCy).

La IA decide QUÉ palabras tienen carga; el tipo (adjetivo, verbo o expresión) lo
decide un analizador gramatical, que no se equivoca con casos como «falsificación»
(sustantivo, no verbo). Tarda milisegundos. Si spaCy no está instalado, se deja el
tipo que propuso la IA.
"""

import logging
from functools import lru_cache

log = logging.getLogger("lente.worker")

MODELOS = ("es_core_news_md", "es_core_news_sm")

# Categorías que por sí solas no expresan valoración: nombres propios, cifras, artículos…
SIN_CARGA = {"PROPN", "NUM", "DET", "PRON", "ADP", "CCONJ", "SCONJ", "SYM", "PUNCT", "SPACE", "X", "PART"}


@lru_cache(maxsize=1)
def analizador():
    try:
        import spacy
    except ImportError:
        log.warning("spaCy no está instalado: se usa el tipo de palabra que propone la IA")
        return None
    for nombre in MODELOS:
        try:
            return spacy.load(nombre, disable=["ner", "parser", "lemmatizer"])
        except OSError:
            continue
    log.warning("No hay modelo de spaCy en español (%s): se usa el tipo de la IA", ", ".join(MODELOS))
    return None


def tipo_de(doc, inicio: int, fin: int, tipo_ia: str) -> str | None:
    """Tipo según la gramática del texto, o None si la palabra no puede tener carga."""
    if doc is None:
        return tipo_ia
    tramo = doc.char_span(inicio, fin, alignment_mode="expand")
    if tramo is None:
        return tipo_ia
    tokens = [t for t in tramo if not (t.is_punct or t.is_space)]
    if not tokens or all(t.pos_ in SIN_CARGA or t.like_num for t in tokens):
        return None             # vacío, o solo nombres propios, cifras o artículos («Pacto Histórico», «2021»)
    if len(tokens) > 1:
        return "expresion"
    pos = tokens[0].pos_
    if pos in SIN_CARGA or tokens[0].like_num:
        return None
    if pos == "ADJ":
        return "adjetivo"
    if pos in ("VERB", "AUX"):
        return "verbo"
    return "expresion"          # sustantivos con carga (escándalo, caos), adverbios, interjecciones
