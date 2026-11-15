import asyncio

import pytest

from app.core.errores import Conflicto, DatoInvalido
from app.services import textos_service as svc
from tests.conftest import ConexionFalsa, cabeceras
from worker import prompts

CUERPO = "El alcalde anunció una medida polémica. La medida fue criticada duramente."
TEXTO = {"id": 1, "tipo": "noticia", "titulo": "T", "cuerpo": CUERPO, "enlace": None, "fuente": None,
         "nota": None, "estado": "en_revision", "idea_principal": None, "elementos_clave": [],
         "consejo_macro": None, "consejo_super": None, "consejo_micro": None, "preparado_por_ia": True,
         "aprobado_en": None, "creado_en": "2026-11-14T00:00:00Z"}


# ---------------------------------------------------------------- validación de entrada

def test_texto_necesita_cuerpo_o_enlace(cliente):
    r = cliente.post("/textos", headers=cabeceras(), json={"titulo": "Sin nada"})
    assert r.status_code == 422


def test_pregunta_correcta_debe_existir(cliente):
    r = cliente.post("/textos/1/preguntas", headers=cabeceras(),
                     json={"pregunta": "¿Qué va primero?", "opciones": ["A", "B"], "correcta": 3})
    assert r.status_code == 422


def test_resaltado_rango_invalido(cliente):
    r = cliente.post("/textos/1/resaltados", headers=cabeceras(), json={"nivel": "macro", "inicio": 5, "fin": 5})
    assert r.status_code == 422


def test_admin_no_gestiona_textos(cliente):
    assert cliente.get("/textos", headers=cabeceras("administrador")).status_code == 403


# ---------------------------------------------------------------- servicio

def test_crear_con_cuerpo_pide_preparacion_ia():
    conn = ConexionFalsa({"id": 1}, TEXTO, [], [])
    asyncio.run(svc.crear(conn, 7, {"tipo": "noticia", "titulo": "T", "cuerpo": CUERPO, "enlace": None,
                                   "fuente": None, "nota": None, "preparar_con_ia": True}))
    assert conn.consultas[0][1]["estado"] == "preparando"


def test_crear_sin_cuerpo_queda_en_borrador():
    conn = ConexionFalsa({"id": 1}, TEXTO, [], [])
    asyncio.run(svc.crear(conn, 7, {"tipo": "noticia", "titulo": "T", "cuerpo": "  ", "enlace": "http://x",
                                   "fuente": None, "nota": None, "preparar_con_ia": True}))
    params = conn.consultas[0][1]
    assert params["estado"] == "borrador" and params["cuerpo"] is None


def test_aprobar_en_estado_incorrecto_da_409():
    conn = ConexionFalsa(None, TEXTO | {"estado": "preparando"})   # el UPDATE no aplica; el texto sí existe
    with pytest.raises(Conflicto):
        asyncio.run(svc.aprobar(conn, 7, 1))


def test_archivar_retira_primero_de_los_cursos():
    # ejecutar() no consume filas: la primera respuesta es la del cambio de estado
    conn = ConexionFalsa({"id": 1}, TEXTO | {"estado": "archivado"}, [], [])
    asyncio.run(svc.archivar(conn, 7, 1))
    assert "textos_del_curso" in conn.consultas[0][0]
    assert "SET estado" in conn.consultas[1][0]


def test_paquete_no_editable_en_aprobado():
    conn = ConexionFalsa(None, TEXTO | {"estado": "aprobado"})
    with pytest.raises(Conflicto):
        asyncio.run(svc.actualizar_paquete(conn, 7, 1, {"idea_principal": "x"}))


# ---------------------------------------------------------------- palabras en el texto

def test_ubicar_palabra_busca_la_primera_libre():
    assert svc.ubicar_palabra(CUERPO, "medida", None, set()) == CUERPO.find("medida")
    segunda = CUERPO.find("medida", CUERPO.find("medida") + 1)
    assert svc.ubicar_palabra(CUERPO, "medida", None, {CUERPO.find("medida")}) == segunda


def test_ubicar_palabra_valida_posicion_y_existencia():
    with pytest.raises(DatoInvalido):
        svc.ubicar_palabra(CUERPO, "polémica", 0, set())
    with pytest.raises(DatoInvalido):
        svc.ubicar_palabra(CUERPO, "inexistente", None, set())
    assert svc.ubicar_palabra(CUERPO, "polémica", CUERPO.find("polémica"), set()) == CUERPO.find("polémica")


def test_crear_palabra_calcula_inicio_y_fin():
    conn = ConexionFalsa(TEXTO, [], [], {"id": 9})
    asyncio.run(svc.crear_palabra(conn, 7, 1, {"palabra": "duramente", "tipo": "expresion", "inicio": None,
                                              "explicacion": None}))
    params = conn.consultas[-1][1]
    assert CUERPO[params["inicio"]:params["fin"]] == "duramente"


# ---------------------------------------------------------------- prompts configurables

def test_instrucciones_de_ajustes_se_agregan_al_sistema():
    assert prompts.sistema(None) == prompts.SISTEMA
    assert prompts.sistema("  Responde breve. ").endswith("Responde breve.")
    m = prompts.mensajes_revisar_idea("txt", "idea", ["a"], "media", "resp", "EXTRA")
    assert m[0]["content"].endswith("EXTRA")
    assert m[-1]["content"].endswith("resp")      # la respuesta del estudiante va al final (caché de prefijo)
