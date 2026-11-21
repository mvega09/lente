"""Cómo guarda el worker lo que propone la IA al preparar un texto (RF-09)."""

from collections import Counter

from worker import ia_worker
from worker.modelos import PreguntaIA


def _preguntas(n=4, opciones=3, correcta=1):
    return [PreguntaIA(pregunta=f"P{i}", opciones=[f"op{i}-{j}" for j in range(1, opciones + 1)],
                       correcta=correcta, dificultad=1) for i in range(n)]


def test_la_correcta_no_queda_siempre_de_primera():
    preguntas = _preguntas()                      # la IA puso la correcta de primera en todas
    mezcladas = ia_worker.mezclar_opciones(preguntas, semilla=8)
    lugares = [c for _, _, c in mezcladas]
    assert all(a != b for a, b in zip(lugares, lugares[1:]))   # nunca dos seguidas en el mismo lugar
    for (p, opciones, c), original in zip(mezcladas, preguntas):
        assert opciones[c - 1] == original.opciones[0]          # sigue siendo la misma respuesta
        assert sorted(opciones) == sorted(original.opciones)    # no se pierde ni se repite ninguna
        assert p is original


def test_en_muchos_textos_la_correcta_queda_repartida():
    conteo = Counter(c for semilla in range(200) for _, _, c in ia_worker.mezclar_opciones(_preguntas(), semilla))
    assert set(conteo) == {1, 2, 3}
    assert min(conteo.values()) > 0.25 * sum(conteo.values())


def test_misma_semilla_mismo_orden_y_respeta_cuatro_opciones():
    a = ia_worker.mezclar_opciones(_preguntas(opciones=4, correcta=3), semilla=5)
    assert a == ia_worker.mezclar_opciones(_preguntas(opciones=4, correcta=3), semilla=5)
    assert all(len(o) == 4 and o[c - 1].endswith("-3") for _, o, c in a)


def test_explicacion_sin_caracteres_extranos_ni_palabras_cortadas():
    assert ia_worker.explicacion_limpia("Genera empatía y enfatiza el malest嚣") == "Genera empatía y enfatiza el malest"
    larga = "Refuerza la gravedad de la situación y el dolor de la pérdida de un ser muy querido por todos los vecinos"
    limpia = ia_worker.explicacion_limpia(larga[:80], limite=80)
    assert limpia.endswith("…") and limpia[:-1] in larga and not limpia[:-1].endswith(" ")
    assert ia_worker.explicacion_limpia("   ") is None


def test_descarta_preguntas_con_correcta_invalida():
    p = _preguntas(n=1)[0]
    p.correcta = 4                                 # solo hay 3 opciones
    assert ia_worker.mezclar_opciones([p], semilla=1) == []
