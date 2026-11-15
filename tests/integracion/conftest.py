"""Pruebas de integración contra la base de pruebas real (PostgreSQL + schema.sql).

Se OMITEN salvo que:
  - LENTE_PRUEBAS_INTEGRACION=1, y
  - DB_NAME contenga "prueba" (salvaguarda: nunca se corren contra la base real).

La base se crea con deploy/crear_base_pruebas.sh. Ollama NO se usa: la
respuesta del modelo se simula para que las pruebas sean rápidas y estables.
"""

import os
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings

ACTIVAS = os.getenv("LENTE_PRUEBAS_INTEGRACION") == "1"


def pytest_collection_modifyitems(config, items):
    for item in items:
        if "integracion" in str(item.fspath):
            item.add_marker(pytest.mark.integracion)


@pytest.fixture(scope="session")
def ajustes_prueba():
    if not ACTIVAS:
        pytest.skip("Pruebas de integración desactivadas (LENTE_PRUEBAS_INTEGRACION=1 para activarlas)")
    s = get_settings()
    if "prueba" not in s.db_name:
        pytest.exit(f"DB_NAME='{s.db_name}' no parece una base de pruebas; no se corre nada.", returncode=2)
    return s


@pytest.fixture(scope="session")
def api(ajustes_prueba):
    from app.main import app
    with TestClient(app) as cliente:          # con "with" se abre el pool real
        yield cliente


@pytest.fixture(scope="session")
def sufijo():
    return uuid.uuid4().hex[:8]


def entrar(api, usuario: str, clave: str) -> dict:
    r = api.post("/auth/login", json={"usuario": usuario, "clave": clave})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="session")
def admin(api):
    clave = os.getenv("LENTE_PRUEBAS_ADMIN_CLAVE", "um2027")    # clave inicial de schema.sql
    return entrar(api, os.getenv("LENTE_PRUEBAS_ADMIN_USUARIO", "admin"), clave)
