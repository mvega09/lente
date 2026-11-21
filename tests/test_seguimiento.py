import asyncio
import pathlib
import re

import pytest

from app.core.animo import ETIQUETAS, PALABRAS_PROHIBIDAS
from app.core.errores import DatoInvalido, NoEncontrado
from app.services import ajustes_service, seguimiento_service as svc
from tests.conftest import ConexionFalsa, cabeceras


# ---------------------------------------------------------------- RF-21: lenguaje no clínico

def test_etiquetas_de_animo_sin_lenguaje_clinico():
    for texto in ETIQUETAS.values():
        assert not any(p in texto.lower() for p in PALABRAS_PROHIBIDAS), texto


def test_mensajes_del_sistema_sin_lenguaje_clinico():
    """Revisa los textos de ánimo y alertas en el código (no el aviso, que lo niega explícitamente)."""
    raiz = pathlib.Path(__file__).resolve().parent.parent
    for archivo in [raiz / "worker" / "prompts.py", raiz / "app" / "services" / "seguimiento_service.py"]:
        contenido = archivo.read_text(encoding="utf-8").lower()
        for palabra in PALABRAS_PROHIBIDAS:
            assert not re.search(rf"\b{palabra}\b", contenido), f"{archivo.name}: '{palabra}'"


def test_panel_traduce_el_clima_a_etiquetas():
    fila = {"curso_id": 2, "curso": "7°B", "estudiantes_activos": 30, "participaron": 20, "acierto_promedio": 70,
            "puntos_del_curso": 900, "racha_mas_larga": 4, "animo_alto": 10, "animo_neutral": 8,
            "animo_requiere_apoyo": 2, "alertas_abiertas": 1}
    salida = asyncio.run(svc.panel(ConexionFalsa(fila, []), 7, 2))
    assert salida["clima"] == {"Motivación alta": 10, "Neutral": 8, "Podría necesitar acompañamiento": 2}
    assert "animo_requiere_apoyo" not in salida


# ---------------------------------------------------------------- RF-06 / RF-18

def test_nombre_del_nivel():
    nombres = ["Curioso", "Lector", "Analista"]
    assert svc.nombre_nivel(1, nombres) == "Curioso"
    assert svc.nombre_nivel(9, nombres) == "Analista"      # se queda en el último
    assert svc.nombre_nivel(2, None) is None


def test_progreso_ajeno_404():
    with pytest.raises(NoEncontrado):
        asyncio.run(svc.progreso(ConexionFalsa(None), 7, 99))


def test_progreso_pide_elegir_profesor_al_administrador(cliente):
    assert cliente.get("/estudiantes/1/progreso", headers=cabeceras("administrador")).status_code == 400


def test_historial_limita_paginas(cliente):
    assert cliente.get("/estudiantes/1/historial?limite=900", headers=cabeceras()).status_code == 422


# ---------------------------------------------------------------- RNF-08: ajustes validados

@pytest.mark.parametrize(("clave", "valor"), [
    ("puntos_por_acierto", 500), ("puntos_por_acierto", True), ("puntos_por_acierto", "20"),
    ("minimo_para_logrado", 1.5), ("alerta_veces_seguidas", 0), ("nombres_de_niveles", []),
])
def test_valores_invalidos(clave, valor):
    with pytest.raises(DatoInvalido):
        ajustes_service.validar(ajustes_service.POR_CURSO, clave, valor)


def test_valores_validos():
    assert ajustes_service.validar(ajustes_service.POR_CURSO, "minimo_para_logrado", 0.7) == 0.7
    assert ajustes_service.validar(ajustes_service.POR_CURSO, "nombres_de_niveles", [" A ", "B"]) == ["A", "B"]


def test_profesor_no_cambia_el_modelo_de_ia():
    with pytest.raises(NoEncontrado):
        ajustes_service.validar(ajustes_service.POR_CURSO, "ia_modelo", "otro")
    assert ajustes_service.validar(ajustes_service.GENERALES, "ia_modelo", " qwen3:14b ") == "qwen3:14b"


def test_ajuste_general_solo_admin(cliente):
    r = cliente.put("/admin/ajustes/puntos_por_acierto", headers=cabeceras("profesor"), json={"valor": 10})
    assert r.status_code == 403
