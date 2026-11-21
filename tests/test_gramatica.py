"""Tipo gramatical de las palabras cargadas (worker/gramatica.py) y filtrado del worker."""

import pytest

from worker import gramatica, ia_worker
from worker.modelos import PalabraIA, PreparacionTexto

TEXTO = ("El escándalo estalla en un momento delicado para el Pacto Histórico. La universidad asegura que "
         "el diploma es falso y anunció acciones por falsificación en 2021. Ante la indignación y la lluvia, "
         "los vecinos, indignados, denunciaron el plan polémico que asfixia al comercio.")


def _prep(*palabras):
    return PreparacionTexto(
        idea_principal="x", elementos_clave=["a", "b"], consejo_macro="x", consejo_super="x", consejo_micro="x",
        preguntas=[{"pregunta": "p", "opciones": ["a", "b", "c"], "correcta": 1, "dificultad": 1}] * 3,
        palabras_cargadas=[PalabraIA(palabra=p, tipo=t, explicacion="x") for p, t in palabras])


@pytest.fixture(scope="module")
def nlp():
    pytest.importorskip("spacy")
    modelo = gramatica.analizador()
    if modelo is None:
        pytest.skip("Falta el modelo de spaCy en español")
    return modelo


@pytest.mark.parametrize(("palabra", "tipo_ia", "esperado"), [
    ("falsificación", "verbo", "expresion"),     # sustantivo: la IA lo había marcado como verbo
    ("escándalo", "expresion", "expresion"),
    ("delicado", "expresion", "adjetivo"),
    ("falso", "expresion", "adjetivo"),
    ("indignados", "expresion", "adjetivo"),
    ("denunciaron", "expresion", "verbo"),
    ("asfixia", "expresion", "verbo"),
    ("plan polémico", "adjetivo", "expresion"),  # varias palabras
    ("Pacto Histórico", "expresion", None),      # solo nombre propio: no es carga
    ("2021", "expresion", None),                 # cifra
])
def test_tipo_segun_la_gramatica(nlp, palabra, tipo_ia, esperado):
    doc = nlp(TEXTO)
    i = TEXTO.index(palabra)
    assert gramatica.tipo_de(doc, i, i + len(palabra), tipo_ia) == esperado


def test_sin_analizador_se_usa_el_tipo_de_la_ia():
    assert gramatica.tipo_de(None, 0, 5, "verbo") == "verbo"


def test_palabras_validas_corrige_tipo_mayusculas_y_cruces(nlp):
    prep = _prep(("Escándalo", "expresion"),          # la IA cambió la mayúscula: se toma la forma del texto
                 ("falsificación", "verbo"),          # se corrige a expresión
                 ("estalla en un momento", "verbo"),  # se cruza con… nada: queda como expresión
                 ("Pacto Histórico", "expresion"),    # nombre propio: se descarta
                 ("no existe en el texto", "verbo"),  # no está: se descarta
                 ("estalla", "verbo"))                # se cruza con la expresión anterior: se descarta
    palabras = ia_worker.palabras_validas(prep, TEXTO)
    assert [(p["palabra"], p["tipo"]) for p in palabras] == [
        ("escándalo", "expresion"), ("falsificación", "expresion"), ("estalla en un momento", "expresion")]
    for p in palabras:
        assert TEXTO[p["inicio"]:p["fin"]] == p["palabra"]


def test_el_esquema_limita_la_respuesta_para_ahorrar_tiempo():
    esquema = PreparacionTexto.model_json_schema()
    props = esquema["properties"]
    assert props["palabras_cargadas"]["maxItems"] == 8 and props["preguntas"]["maxItems"] == 4
    assert props["idea_principal"]["maxLength"] == 320
    assert ia_worker.NUM_PREDICT_PREPARACION <= 1500
