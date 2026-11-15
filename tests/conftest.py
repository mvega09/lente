"""Utilidades de prueba que no necesitan PostgreSQL ni Ollama.

- `cliente`: TestClient con la conexión a la base reemplazada por un objeto
  falso; los servicios se reemplazan con monkeypatch en cada prueba.
- `cabeceras(rol, id)`: token válido para el rol indicado.
- `ConexionFalsa`: registra las consultas y devuelve filas preparadas, para
  probar los servicios sin base de datos.
"""

import pytest
from fastapi.testclient import TestClient

from app.core.db import get_conn
from app.core.security import crear_token
from app.main import app
from app.schemas.auth import UsuarioSesion


class _CursorFalso:
    def __init__(self, conexion):
        self.c = conexion

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    rowcount = 1

    async def execute(self, sql, params=None):
        self.c.consultas.append((sql, params))

    async def fetchone(self):
        return self.c.filas.pop(0) if self.c.filas else None

    async def fetchall(self):
        return self.c.filas.pop(0) if self.c.filas else []


class ConexionFalsa:
    """`filas` es una lista de respuestas, una por consulta, en orden."""

    def __init__(self, *filas):
        self.filas = list(filas)
        self.consultas: list[tuple[str, object]] = []

    def cursor(self):
        return _CursorFalso(self)


@pytest.fixture
def cliente():
    async def _conn_falsa():
        yield ConexionFalsa()

    app.dependency_overrides[get_conn] = _conn_falsa
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def cabeceras(rol: str = "profesor", id_: int = 7) -> dict:
    token = crear_token(UsuarioSesion(id=id_, rol=rol, nombre=f"{rol} de prueba"))
    return {"Authorization": f"Bearer {token}"}
