"""Valida la sintaxis de todas las consultas SQL_* con el analizador real de
PostgreSQL (pglast / libpg_query), sin necesidad de una base de datos."""

import importlib
import pkgutil
import re

import pglast
import pytest

import app.services

PARAM = re.compile(r"%\((\w+)\)s|%s")


def _consultas():
    for mod in pkgutil.iter_modules(app.services.__path__):
        m = importlib.import_module(f"app.services.{mod.name}")
        for nombre, valor in vars(m).items():
            if nombre.startswith("SQL_") and isinstance(valor, str):
                yield f"{mod.name}.{nombre}", valor


def _a_postgres(sql: str) -> str:
    """Convierte %(x)s / %s de psycopg en $1, $2… para el analizador."""
    nombres: dict[str, int] = {}

    def cambio(m):
        clave = m.group(1) or f"_pos{len(nombres)}"
        nombres.setdefault(clave, len(nombres) + 1)
        return f"${nombres[clave]}"

    return PARAM.sub(cambio, sql)


CONSULTAS = list(_consultas())


def test_hay_consultas():
    assert len(CONSULTAS) >= 15


@pytest.mark.parametrize(("nombre", "sql"), CONSULTAS, ids=[n for n, _ in CONSULTAS])
def test_sql_valido(nombre, sql):
    pglast.parse_sql(_a_postgres(sql))


@pytest.mark.parametrize(("nombre", "sql"), CONSULTAS, ids=[n for n, _ in CONSULTAS])
def test_sql_usa_esquema_lente(nombre, sql):
    # Toda tabla o vista del proyecto se nombra con su esquema (lente.x)
    for tabla in ("usuarios", "cursos", "estudiantes", "textos", "actividades", "respuestas"):
        assert not re.search(rf"\b(FROM|JOIN|INTO|UPDATE)\s+{tabla}\b", sql, re.I), f"{nombre}: falta 'lente.'"
