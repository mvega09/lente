import asyncio

import pytest

from app.core.errores import NoEncontrado
from app.services import cursos_service
from tests.conftest import ConexionFalsa, cabeceras

ESTUDIANTE = {"id": 5, "nombre": "Luis", "curso_id": 2, "curso": "7°B", "grado": 7, "grado_texto": "7°",
              "nivel_escolar": "secundaria", "estado": "Activo", "puntos": 0, "nivel": 1,
              "racha": 0, "mejor_racha": 0}


def test_admin_no_ve_cursos_de_profesor(cliente):
    assert cliente.get("/cursos", headers=cabeceras("administrador")).status_code == 403


def test_listar_cursos_usa_el_profesor_del_token(cliente, monkeypatch):
    usado = {}

    async def falso(conn, profesor_id):
        usado["profesor"] = profesor_id
        return []

    monkeypatch.setattr(cursos_service, "listar_cursos", falso)
    assert cliente.get("/cursos", headers=cabeceras("profesor", 42)).status_code == 200
    assert usado["profesor"] == 42


def test_estudiante_solo_con_nombre(cliente, monkeypatch):
    async def falso(conn, profesor_id, curso_id, nombre, grado):
        assert (profesor_id, curso_id, nombre, grado) == (7, 2, "Luis", None)
        return ESTUDIANTE

    monkeypatch.setattr(cursos_service, "crear_estudiante", falso)
    r = cliente.post("/cursos/2/estudiantes", headers=cabeceras(), json={"nombre": "Luis"})
    assert r.status_code == 201
    assert r.json()["nivel_escolar"] == "secundaria"


def test_grado_fuera_de_rango_422(cliente):
    r = cliente.post("/cursos/2/estudiantes", headers=cabeceras(), json={"nombre": "Luis", "grado": 2})
    assert r.status_code == 422


def test_patch_distingue_grado_nulo_de_no_enviado(cliente, monkeypatch):
    recibidos = []

    async def falso(conn, profesor_id, estudiante_id, cambios):
        recibidos.append(cambios)
        return ESTUDIANTE

    monkeypatch.setattr(cursos_service, "actualizar_estudiante", falso)
    cliente.patch("/estudiantes/5", headers=cabeceras(), json={"nombre": "Luis A."})
    cliente.patch("/estudiantes/5", headers=cabeceras(), json={"grado": None})
    assert recibidos[0] == {"nombre": "Luis A."}
    assert recibidos[1] == {"grado": None}


def test_borrar_estudiante_solo_desactiva(cliente, monkeypatch):
    async def falso(conn, profesor_id, estudiante_id, cambios):
        assert cambios == {"activo": False}
        return ESTUDIANTE | {"estado": "Inactivo"}

    monkeypatch.setattr(cursos_service, "actualizar_estudiante", falso)
    assert cliente.delete("/estudiantes/5", headers=cabeceras()).json()["estado"] == "Inactivo"


# ---------------------------------------------------------------- servicio

def test_servicio_marca_cambio_de_grado():
    conn = ConexionFalsa({"id": 5}, ESTUDIANTE)
    asyncio.run(cursos_service.actualizar_estudiante(conn, 7, 5, {"grado": None}))
    params = conn.consultas[0][1]
    assert params["cambiar_grado"] is True and params["grado"] is None and params["profesor"] == 7

    conn = ConexionFalsa({"id": 5}, ESTUDIANTE)
    asyncio.run(cursos_service.actualizar_estudiante(conn, 7, 5, {"nombre": "X"}))
    assert conn.consultas[0][1]["cambiar_grado"] is False


def test_servicio_curso_ajeno_da_404():
    conn = ConexionFalsa(None)          # el INSERT ... SELECT no encontró el curso del profesor
    with pytest.raises(NoEncontrado):
        asyncio.run(cursos_service.crear_estudiante(conn, 7, 99, "Luis", None))
