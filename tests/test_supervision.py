"""Administrador en modo supervisión y borrado definitivo de textos."""

import asyncio

import pytest

from app.core.errores import Conflicto
from app.core.security import crear_token
from app.schemas.auth import UsuarioSesion
from app.services import cursos_service, textos_service
from tests.conftest import ConexionFalsa, cabeceras


def _cliente_con(conn):
    from fastapi.testclient import TestClient

    from app.core.db import get_conn
    from app.main import app

    async def _conn():
        yield conn
    app.dependency_overrides[get_conn] = _conn
    return TestClient(app), app


def _recibir_profesor(monkeypatch):
    recibido = {}

    async def falso(conn, profesor_id):
        recibido["profesor"] = profesor_id
        return []
    monkeypatch.setattr(cursos_service, "listar_cursos", falso)
    return recibido


def test_admin_trabaja_como_el_profesor_elegido(monkeypatch):
    recibido = _recibir_profesor(monkeypatch)
    cli, app = _cliente_con(ConexionFalsa({"id": 2, "nombre": "Profesor PRUEBA"}))
    try:
        r = cli.get("/cursos", headers=cabeceras("administrador", 1) | {"X-Como-Profesor": "2"})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200 and recibido["profesor"] == 2


def test_admin_sin_elegir_profesor_recibe_un_mensaje_claro(cliente):
    r = cliente.get("/cursos", headers=cabeceras("administrador", 1))
    assert r.status_code == 400 and "Elija el profesor" in r.json()["detail"]


def test_admin_con_un_profesor_inexistente_recibe_404():
    cli, app = _cliente_con(ConexionFalsa(None))
    try:
        r = cli.get("/cursos", headers=cabeceras("administrador", 1) | {"X-Como-Profesor": "99"})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 404


def test_un_profesor_no_puede_hacerse_pasar_por_otro(monkeypatch):
    recibido = _recibir_profesor(monkeypatch)
    cli, app = _cliente_con(ConexionFalsa())
    try:
        r = cli.get("/cursos", headers=cabeceras("profesor", 7) | {"X-Como-Profesor": "2"})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200 and recibido["profesor"] == 7       # la cabecera se ignora


def test_la_supervision_solo_acepta_cuentas_de_profesor():
    from app.services.admin_service import SQL_PROFESOR_A_SUPERVISAR
    assert "rol = 'profesor'" in SQL_PROFESOR_A_SUPERVISAR


# ---------------------------------------------------------------- borrar textos

def _texto(estado="borrador"):
    return {"id": 9, "tipo": "noticia", "titulo": "T", "cuerpo": "x", "enlace": None, "fuente": None, "nota": None,
            "estado": estado, "idea_principal": None, "elementos_clave": [], "consejo_macro": None,
            "consejo_super": None, "consejo_micro": None, "preparado_por_ia": False, "aprobado_en": None,
            "creado_en": "2026-11-20T10:00:00Z"}


def test_borrar_un_texto_sin_actividades():
    conn = ConexionFalsa(_texto(), {"n": 0}, {"id": 9})
    asyncio.run(textos_service.eliminar(conn, 7, 9))
    assert conn.consultas[-1][0] == textos_service.SQL_BORRAR_TEXTO
    assert conn.consultas[-1][1] == {"id": 9, "profesor": 7}


def test_no_se_borra_un_texto_con_historial_de_estudiantes():
    with pytest.raises(Conflicto, match="Archívelo"):
        asyncio.run(textos_service.eliminar(ConexionFalsa(_texto("aprobado"), {"n": 3}), 7, 9))


def test_no_se_borra_mientras_la_ia_lo_prepara():
    with pytest.raises(Conflicto, match="preparando"):
        asyncio.run(textos_service.eliminar(ConexionFalsa(_texto("preparando")), 7, 9))


def test_borrar_texto_ajeno_responde_404(cliente):
    assert cliente.delete("/textos/9/definitivo", headers=cabeceras("profesor", 7)).status_code == 404
