"""Pruebas que no necesitan base de datos ni Ollama.  Ejecutar: pytest"""

from fastapi.testclient import TestClient

from app.core.security import crear_token, usuario_actual
from app.main import app
from app.schemas.auth import UsuarioSesion
from worker.modelos import RevisionIdea

# Sin "with", TestClient no ejecuta el lifespan: no abre el pool de PostgreSQL.
cliente = TestClient(app)


def test_raiz():
    r = cliente.get("/")
    assert r.status_code == 200
    assert r.json()["docs"] == "/docs"


def test_yo_sin_token_da_401():
    assert cliente.get("/auth/yo").status_code == 401


def test_yo_con_token():
    token = crear_token(UsuarioSesion(id=1, rol="profesor", nombre="Prueba"))
    r = cliente.get("/auth/yo", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["rol"] == "profesor"


def test_formato_revision_idea():
    rev = RevisionIdea.model_validate_json(
        '{"veredicto":"coincide_en_parte","faltantes":"la causa","explicacion":"Bien.","cita":"texto"}'
    )
    assert rev.veredicto == "coincide_en_parte"


def test_dependencia_existe():
    assert callable(usuario_actual)
