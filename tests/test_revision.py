"""Controles sin IA de la revisión de la idea principal (worker/revision.py)."""

from types import SimpleNamespace

import pytest

from worker import gramatica, ia_worker, revision
from worker.modelos import RevisionIdea

NOTICIA = ("Luz Karina Muñoz, líder del sector de Puertas del Sol, se comunicó con LA PATRIA para mostrar "
           "su indignación. Un adulto falleció en una esquina y la funeraria no llegaba. La comunidad tuvo "
           "que conseguir una manta para tapar el cadáver.")
IDEA = "Un ciudadano falleció en Manizales y no fue atendido a tiempo, lo que indignó a la comunidad."
CLAVES = ["fallecimiento en Puertas del Sol", "demora de la funeraria", "indignación de la comunidad"]


@pytest.fixture(scope="module")
def nlp():
    pytest.importorskip("spacy")
    if gramatica.analizador() is None:
        pytest.skip("Falta el modelo de spaCy en español")


@pytest.mark.parametrize("respuesta", ["sADSDFDSAasd", "DSFDSFsS", "asdf qwer zxcv", "", "   ", "123 456", "la el de"])
def test_teclazos_y_respuestas_vacias_no_tienen_sentido(nlp, respuesta):
    assert not revision.tiene_sentido(respuesta)


@pytest.mark.parametrize("respuesta", [
    "los pescadores dicen que la mina daño el rio y los peces se murieron",   # 4.°, sin tildes
    "Un señor murió y la funeraria se demoró mucho en llegar",
    "Petro critica el resultado electoral",
])
def test_respuestas_reales_si_tienen_sentido(nlp, respuesta):
    assert revision.tiene_sentido(respuesta)


def test_palabras_en_comun_tolera_formas_distintas():
    assert revision.palabras_en_comun("Hubo un fallecimiento y la comunidad se indignó", NOTICIA, IDEA) >= 2
    assert revision.palabras_en_comun("Me gusta jugar fútbol con mis primos", NOTICIA, IDEA, " ".join(CLAVES)) == 0


@pytest.mark.parametrize(("veredicto", "faltantes", "explicacion", "en_comun", "esperado", "cambia_texto"), [
    ("coincide", "", "Mencionas todo.", 0, "por_mejorar", True),                  # nada que ver con la noticia
    ("coincide_en_parte", "x", "Bien.", 0, "por_mejorar", True),
    ("coincide", "", "Mencionas el fallecimiento, pero te faltó la zona.", 3, "coincide_en_parte", False),
    ("coincide", "la zona", "Mencionas el fallecimiento.", 3, "coincide_en_parte", False),
    ("coincide", "", "Mencionas todos los elementos.", 3, "coincide", False),
    ("por_mejorar", "todo", "Te faltó casi todo.", 0, "por_mejorar", False),
])
def test_ajustar_veredicto(veredicto, faltantes, explicacion, en_comun, esperado, cambia_texto):
    nuevo, texto = revision.ajustar_veredicto(veredicto, faltantes, explicacion, en_comun)
    assert nuevo == esperado and (texto is not None) is cambia_texto


def test_primera_frase_es_un_fragmento_exacto_del_texto():
    frase = revision.primera_frase(NOTICIA)
    assert NOTICIA.startswith(frase) and len(frase.split()) <= 12
    assert revision.primera_frase("Corta. Otra.") == "Corta."


class _ConexionRevision:
    def __init__(self, respuesta):
        self.fila = {"texto": NOTICIA, "idea_principal": IDEA, "elementos_clave": CLAVES,
                     "nivel_escolar": "secundaria", "respuesta_estudiante": respuesta}
        self.guardado = None

    def execute(self, sql, params=None):
        if "guardar_revision_idea" in sql:
            self.guardado = params
            return SimpleNamespace(fetchone=lambda: {"ok": True})
        if "ajuste(" in sql:
            return SimpleNamespace(fetchone=lambda: {"valor": None})
        return SimpleNamespace(fetchone=lambda: self.fila)


def _ia_dice(monkeypatch, **campos):
    llamadas = []

    def falso(*a, **k):
        llamadas.append(1)
        return RevisionIdea(**({"veredicto": "coincide", "faltantes": "", "explicacion": "Bien.", "cita": "x"} | campos))

    monkeypatch.setattr(ia_worker, "preguntar", falso)
    return llamadas


def test_teclazos_quedan_por_mejorar_sin_llamar_a_la_ia(nlp, monkeypatch):
    llamadas = _ia_dice(monkeypatch)
    conn = _ConexionRevision("sADSDFDSAasd")
    ia_worker.revisar_idea(conn, 78)
    _, veredicto, _, explicacion, cita, ms = conn.guardado
    assert llamadas == [] and veredicto == "por_mejorar" and ms == 0
    assert explicacion == revision.EXPLICACION_SIN_SENTIDO and NOTICIA.startswith(cita)


def test_la_ia_no_puede_aprobar_algo_sin_relacion_con_la_noticia(nlp, monkeypatch):
    _ia_dice(monkeypatch, veredicto="coincide")
    conn = _ConexionRevision("Me gusta jugar fútbol con mis primos los domingos")
    ia_worker.revisar_idea(conn, 79)
    assert conn.guardado[1] == "por_mejorar" and conn.guardado[3] == revision.EXPLICACION_SIN_RELACION


def test_coincide_con_algo_faltante_queda_en_parte(nlp, monkeypatch):
    _ia_dice(monkeypatch, veredicto="coincide", explicacion="Mencionas el fallecimiento, pero te faltó la zona.",
             cita="Un adulto falleció en una esquina")
    conn = _ConexionRevision("Un adulto falleció y la funeraria no llegaba")
    ia_worker.revisar_idea(conn, 80)
    assert conn.guardado[1] == "coincide_en_parte"
    assert conn.guardado[3].startswith("Mencionas") and conn.guardado[4] == "Un adulto falleció en una esquina"
