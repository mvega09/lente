"""Flujo completo contra PostgreSQL real: admin → profesor → curso → texto →
actividad (macro con el worker de IA simulado, super, micro) → resultado →
progreso y panel. Verifica también el aislamiento entre profesores (RNF-05)."""

import uuid
from datetime import datetime, timezone

import psycopg
import pytest
from psycopg.rows import dict_row

from tests.integracion.conftest import entrar
from worker import ia_worker
from worker.modelos import Animo, RevisionIdea

CUERPO = ("El concejo aprobó anoche un polémico plan para convertir el parque central en un parqueadero. "
          "Los comerciantes celebraron, pero los vecinos denunciaron que perderán su único espacio verde.")
AHORA = datetime.now(timezone.utc).isoformat()


def _codigo():
    return str(uuid.uuid4())


def _ia_simulada(modelo, mensajes, esquema, num_predict, cliente=None):
    """Sustituye a Ollama: misma interfaz, respuesta fija y válida."""
    if esquema is RevisionIdea:
        return RevisionIdea(veredicto="coincide_en_parte", faltantes="la postura de los vecinos",
                            explicacion="Vas bien, pero falta quién se opone.", cita="los vecinos denunciaron")
    if esquema is Animo:
        return Animo(animo="neutral")
    raise AssertionError("En esta prueba no se prepara ningún texto con IA")


def _correr_worker(ajustes, monkeypatch, maximo=20):
    monkeypatch.setattr(ia_worker, "preguntar", _ia_simulada)
    with psycopg.connect(ajustes.conninfo_ia, autocommit=True, row_factory=dict_row) as conn:
        for _ in range(maximo):
            if not ia_worker.procesar_siguiente(conn):
                break


@pytest.fixture(scope="module")
def escenario(api, admin, sufijo):
    """Crea un profesor con su curso, un estudiante y un texto aprobado y activo."""
    usuario = f"prof.{sufijo}"
    r = api.post("/admin/profesores", headers=admin,
                 json={"nombre": f"Profesor {sufijo}", "usuario": usuario, "clave": "temporal-123"})
    assert r.status_code == 201, r.text
    prof = entrar(api, usuario, "temporal-123")
    assert api.get("/auth/yo", headers=prof).json()["rol"] == "profesor"

    curso = api.post("/cursos", headers=prof, json={"nombre": f"7B-{sufijo}"}).json()
    est = api.post(f"/cursos/{curso['id']}/estudiantes", headers=prof, json={"nombre": "Ana", "grado": 7}).json()
    assert est["nivel_escolar"] == "secundaria"

    texto = api.post("/textos", headers=prof, json={"titulo": "Parque", "cuerpo": CUERPO,
                                                     "preparar_con_ia": False}).json()
    assert texto["estado"] == "borrador"
    tid = texto["id"]

    # Sin idea principal no se aprueba (CHECK de la base)
    assert api.post(f"/textos/{tid}/aprobar", headers=prof).status_code == 422

    api.patch(f"/textos/{tid}/paquete", headers=prof, json={
        "idea_principal": "Aprobaron cambiar el parque por un parqueadero y los vecinos se oponen.",
        "elementos_clave": ["parque a parqueadero", "oposición de vecinos"],
        "consejo_super": "El texto pone primero la decisión y deja al final a los afectados.",
    }).raise_for_status()
    assert api.post(f"/textos/{tid}/preguntas", headers=prof, json={
        "pregunta": "¿Qué aparece primero?", "opciones": ["La decisión", "La opinión de los vecinos"],
        "correcta": 1, "dificultad": 1}).status_code == 201
    palabra = api.post(f"/textos/{tid}/palabras", headers=prof,
                       json={"palabra": "polémico", "tipo": "adjetivo"}).json()
    assert CUERPO[palabra["inicio"]:palabra["fin"]] == "polémico"

    # Un texto no aprobado no se activa (trigger)
    assert api.post(f"/cursos/{curso['id']}/textos", headers=prof, json={"texto_id": tid}).status_code == 409
    assert api.post(f"/textos/{tid}/aprobar", headers=prof).json()["estado"] == "aprobado"
    assert api.post(f"/cursos/{curso['id']}/textos", headers=prof, json={"texto_id": tid}).status_code == 204
    return {"prof": prof, "curso": curso, "est": est, "texto_id": tid}


def test_actividad_completa(api, escenario, ajustes_prueba, monkeypatch):
    prof, est, tid = escenario["prof"], escenario["est"], escenario["texto_id"]

    act = api.post("/actividades", headers=prof, json={"estudiante_id": est["id"], "texto_id": tid}).json()
    aid = act["id"]
    assert act["paso"] == "macro" and act["preguntas"] == []

    # RF-15: no se puede saltar a super
    r = api.post(f"/actividades/{aid}/super", headers=prof, json={"respuestas": [
        {"codigo_envio": _codigo(), "pregunta_id": 1, "opcion_elegida": 1}], "enviada_en": AHORA})
    assert r.status_code in (409, 422)

    # RF-10: macro → "analizando" sin revelar la idea
    codigo_macro = _codigo()
    m = api.post(f"/actividades/{aid}/macro", headers=prof,
                 json={"texto": "Van a quitar el parque para hacer parqueadero.", "codigo_envio": codigo_macro,
                       "enviada_en": AHORA}).json()
    assert m["analizando"] is True and m.get("idea_principal") is None
    # RNF-03: reenviar el mismo código no duplica ni falla
    assert api.post(f"/actividades/{aid}/macro", headers=prof,
                    json={"texto": "otra cosa", "codigo_envio": codigo_macro, "enviada_en": AHORA}).status_code == 200

    _correr_worker(ajustes_prueba, monkeypatch)
    m = api.get(f"/actividades/{aid}/macro", headers=prof).json()
    assert m["analizando"] is False and m["veredicto"] == "coincide_en_parte"
    assert m["cita"] == "los vecinos denunciaron"                    # la base verificó que existe
    assert m["idea_principal"].startswith("Aprobaron")

    # Super: la vista no expone la respuesta correcta
    vista = api.get(f"/actividades/{aid}", headers=prof).json()
    assert vista["paso"] == "super" and "correcta" not in vista["preguntas"][0]
    s = api.post(f"/actividades/{aid}/super", headers=prof, json={"respuestas": [
        {"codigo_envio": _codigo(), "pregunta_id": vista["preguntas"][0]["id"], "opcion_elegida": 1}],
        "enviada_en": AHORA}).json()
    assert s["paso"] == "micro" and s["resultados"][0]["es_correcta"] is True

    # Micro: una palabra cargada y una neutra
    i, j = CUERPO.find("polémico"), CUERPO.find("concejo")
    r = api.post(f"/actividades/{aid}/micro", headers=prof, json={"marcas": [
        {"codigo_envio": _codigo(), "texto": "polémico", "inicio": i, "fin": i + 8},
        {"codigo_envio": _codigo(), "texto": "concejo", "inicio": j, "fin": j + 7}], "enviada_en": AHORA})
    assert r.json()["recibidas"] == 2

    res = api.post(f"/actividades/{aid}/terminar", headers=prof).json()
    assert res["macro"]["resultado"] == 0.5 and res["super"]["resultado"] == 1.0
    assert res["micro"]["resultado"] == 0.5                         # (1 acierto − 0,5 × 1 neutra) / 1
    assert res["puntos_ganados"] > 0
    assert [p["palabra"] for p in res["micro"]["neutras_marcadas"]] == ["concejo"]
    assert any(l["nombre"] == "Primer análisis" for l in res["logros_nuevos"])

    # Ánimo en segundo plano (RF-21) y seguimiento del profesor
    _correr_worker(ajustes_prueba, monkeypatch)
    prog = api.get(f"/estudiantes/{est['id']}/progreso", headers=prof).json()
    assert prog["actividades_hechas"] == 1 and prog["animo"] == "Neutral"
    hist = api.get(f"/estudiantes/{est['id']}/historial", headers=prof).json()
    assert {h["nivel"] for h in hist} == {"macro", "super", "micro"}
    panel = api.get(f"/cursos/{escenario['curso']['id']}/panel", headers=prof).json()
    assert panel["participaron"] == 1 and panel["clima"]["Neutral"] == 1


def test_aislamiento_entre_profesores(api, admin, escenario, sufijo):
    """RNF-05: otro profesor no ve ni modifica nada del primero."""
    usuario = f"otro.{sufijo}"
    api.post("/admin/profesores", headers=admin,
             json={"nombre": "Otro", "usuario": usuario, "clave": "temporal-456"}).raise_for_status()
    otro = entrar(api, usuario, "temporal-456")
    est, curso, tid = escenario["est"], escenario["curso"], escenario["texto_id"]

    assert api.get(f"/estudiantes/{est['id']}", headers=otro).status_code == 404
    assert api.get(f"/estudiantes/{est['id']}/progreso", headers=otro).status_code == 404
    assert api.get(f"/cursos/{curso['id']}/panel", headers=otro).status_code == 404
    assert api.get(f"/textos/{tid}", headers=otro).status_code == 404
    assert api.post(f"/cursos/{curso['id']}/estudiantes", headers=otro, json={"nombre": "Intruso"}).status_code == 404
    assert api.post("/actividades", headers=otro,
                    json={"estudiante_id": est["id"], "texto_id": tid}).status_code == 404
    assert api.get("/alertas", headers=otro).json() == []
