import asyncio
import uuid
from datetime import datetime, timezone

import pytest

from app.core.errores import Conflicto, DatoInvalido
from app.core.grados import instruccion
from app.services import actividades_service as svc
from tests.conftest import ConexionFalsa, cabeceras

CUERPO = "El gobierno anunció un brutal recorte. Los ciudadanos protestaron indignados."
AHORA = datetime(2026, 11, 14, tzinfo=timezone.utc)


def act(**cambios):
    base = {"id": 10, "estudiante_id": 5, "estudiante": "Luis", "curso_id": 2, "texto_id": 1, "numero": 1,
            "estado": "en_curso", "paso": "macro", "grado": 7, "nivel_escolar": "secundaria",
            "dificultad_maxima": 2, "resultado_macro": None, "resultado_super": None, "resultado_micro": None,
            "puntos_ganados": 0, "iniciada_en": AHORA, "terminada_en": None, "titulo": "Recorte",
            "cuerpo": CUERPO, "fuente": None}
    return base | cambios


PREGUNTAS = [
    {"id": 1, "orden": 1, "pregunta": "¿Qué va primero?", "opciones": ["Titular", "Cierre"], "correcta": 1, "dificultad": 1},
    {"id": 2, "orden": 2, "pregunta": "¿Qué se omite?", "opciones": ["A", "B", "C"], "correcta": 2, "dificultad": 3},
]


# ---------------------------------------------------------------- RF-10: la idea no se revela antes

def test_idea_principal_oculta_mientras_analiza():
    fila = {"texto": "mi idea", "estado_ia": "pendiente", "veredicto_ia": None, "faltantes_ia": None,
            "explicacion_ia": None, "cita_ia": None, "cita_valida": None, "idea_principal": "LA RESPUESTA"}
    salida = asyncio.run(svc.estado_macro(ConexionFalsa(fila), 7, 10))
    assert salida["analizando"] is True
    assert "idea_principal" not in salida


def test_idea_principal_se_muestra_tras_la_revision():
    fila = {"texto": "mi idea", "estado_ia": "lista", "veredicto_ia": "coincide_en_parte", "faltantes_ia": "la causa",
            "explicacion_ia": None, "cita_ia": None, "cita_valida": False, "idea_principal": "LA RESPUESTA"}
    salida = asyncio.run(svc.estado_macro(ConexionFalsa(fila), 7, 10))
    assert salida["idea_principal"] == "LA RESPUESTA"
    assert salida["cita"] is None                    # cita inválida: no se muestra (RNF-04)


def test_vista_no_expone_la_opcion_correcta(cliente, monkeypatch):
    async def falso(conn, profesor_id, actividad_id):
        return svc._vista(act(paso="super"), PREGUNTAS)

    monkeypatch.setattr(svc, "ver", falso)
    r = cliente.get("/actividades/10", headers=cabeceras())
    assert r.status_code == 200
    assert all("correcta" not in q for q in r.json()["preguntas"])


def test_aviso_cuando_la_revision_tarda():
    fila = {"texto": "x", "estado_ia": "procesando", "veredicto_ia": None, "faltantes_ia": None,
            "explicacion_ia": None, "cita_ia": None, "cita_valida": None, "idea_principal": "R",
            "segundos_esperando": 40, "tiempo_maximo": 15}
    salida = asyncio.run(svc.estado_macro(ConexionFalsa(fila), 7, 10))
    assert "tardando" in salida["mensaje"] and "idea_principal" not in salida
    rapida = asyncio.run(svc.estado_macro(ConexionFalsa(fila | {"segundos_esperando": 5}), 7, 10))
    assert "mensaje" not in rapida


# ---------------------------------------------------------------- RF-15: secuencia

def test_no_se_salta_pasos():
    with pytest.raises(Conflicto, match="Primero"):
        svc._exigir_paso(act(paso="macro"), "super")
    with pytest.raises(Conflicto, match="ya se respondió"):
        svc._exigir_paso(act(paso="micro"), "macro")
    with pytest.raises(Conflicto, match="terminó"):
        svc._exigir_paso(act(estado="terminada", paso="resultado"), "micro")
    svc._exigir_paso(act(paso="micro"), "micro")


# ---------------------------------------------------------------- RF-19: adaptación por grado

def test_preguntas_filtradas_por_grado_con_respaldo():
    assert [q["id"] for q in svc.preguntas_para_grado(PREGUNTAS, 1)] == [1]
    assert [q["id"] for q in svc.preguntas_para_grado(PREGUNTAS, 3)] == [1, 2]
    solo_dificiles = [PREGUNTAS[1]]
    assert svc.preguntas_para_grado(solo_dificiles, 1) == solo_dificiles   # nunca queda sin preguntas


def test_instrucciones_cambian_con_el_grado():
    assert instruccion("primaria", "macro") != instruccion("media", "macro")
    assert instruccion(None, "micro") == instruccion("media", "micro")


# ---------------------------------------------------------------- RNF-03: reenvíos sin duplicar

def test_reenvio_de_macro_no_inserta_de_nuevo():
    codigo = uuid.uuid4()
    macro = {"texto": "x", "estado_ia": "procesando", "veredicto_ia": None, "faltantes_ia": None,
             "explicacion_ia": None, "cita_ia": None, "cita_valida": None, "idea_principal": "R"}
    conn = ConexionFalsa(act(paso="super"), [{"codigo_envio": codigo}], macro)
    salida = asyncio.run(svc.responder_macro(conn, 7, 10, "x", codigo, AHORA))
    assert salida["analizando"] is True
    assert not any("INSERT" in sql for sql, _ in conn.consultas)


def test_marca_que_no_coincide_con_el_texto():
    conn = ConexionFalsa(act(paso="micro"), [])
    marca = {"codigo_envio": uuid.uuid4(), "texto": "brutal", "inicio": 0, "fin": 6, "tipo_palabra": "adjetivo"}
    with pytest.raises(DatoInvalido):
        asyncio.run(svc.responder_micro(conn, 7, 10, [marca], AHORA))


def test_super_rechaza_pregunta_ajena():
    conn = ConexionFalsa(act(paso="super"), [], PREGUNTAS)
    r = {"codigo_envio": uuid.uuid4(), "pregunta_id": 99, "opcion_elegida": 1}
    with pytest.raises(DatoInvalido):
        asyncio.run(svc.responder_super(conn, 7, 10, [r], AHORA))


# ---------------------------------------------------------------- RF-12 / RF-16: microestructura

def test_analisis_micro():
    i = CUERPO.find("brutal")
    j = CUERPO.find("indignados")
    palabras = [{"palabra": "brutal", "tipo": "adjetivo", "inicio": i, "fin": i + 6, "explicacion": None},
                {"palabra": "indignados", "tipo": "adjetivo", "inicio": j, "fin": j + 10, "explicacion": None}]
    marcas = [{"texto": "brutal", "inicio": i, "fin": i + 6, "es_correcta": True},
              {"texto": "gobierno", "inicio": 3, "fin": 11, "es_correcta": False}]
    aciertos, omisiones, neutras = svc.analizar_micro(palabras, marcas)
    assert [p["palabra"] for p in aciertos] == ["brutal"]
    assert [p["palabra"] for p in omisiones] == ["indignados"]
    assert neutras == [{"palabra": "gobierno"}]


def test_recomendaciones_segun_niveles():
    consejos = {"consejo_macro": "Busca el quién y el qué.", "consejo_super": "Mira el titular.",
                "consejo_micro": "Fíjate en los adjetivos."}
    rec = svc.recomendaciones({"macro": 0.5, "super": 1.0, "micro": 0.2}, 0.6, consejos, "la causa")
    assert rec == ["En la idea principal te faltó: la causa", "Busca el quién y el qué.", "Fíjate en los adjetivos."]
    assert "Muy bien" in svc.recomendaciones({"macro": 1, "super": 1, "micro": 1}, 0.6, consejos, None)[0]


def test_terminar_exige_al_menos_una_marca():
    conn = ConexionFalsa(act(paso="micro"), [])
    with pytest.raises(Conflicto, match="al menos una"):
        asyncio.run(svc.terminar(conn, 7, 10))
