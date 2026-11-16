"""Migraciones de db/migraciones: sintaxis válida y mismas funciones que schema.sql.

Una base ya creada se actualiza con la migración; una nueva, con schema.sql.
Si las dos versiones de una función se separan, la base real y la de pruebas
quedarían distintas sin que nadie lo note.
"""

import pathlib
import re

import pglast
import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
ESQUEMA = (RAIZ / "db" / "schema.sql").read_text(encoding="utf-8")
MIGRACIONES = sorted((RAIZ / "db" / "migraciones").glob("*.sql"))


def _sin_meta_psql(sql: str) -> str:
    return "\n".join(l for l in sql.splitlines() if not l.lstrip().startswith("\\"))


def _funcion(sql: str, nombre: str) -> str:
    m = re.search(rf"CREATE (?:OR REPLACE )?FUNCTION {nombre}\(.*?END \$\$;", sql, re.S)
    assert m, f"No se encontró la función {nombre}"
    return " ".join(m.group(0).replace("OR REPLACE ", "").split())


def _vista(sql: str, nombre: str) -> str:
    m = re.search(rf"CREATE (?:OR REPLACE )?VIEW {nombre} AS.*?;", sql, re.S)
    assert m, f"No se encontró la vista {nombre}"
    return " ".join(m.group(0).replace("OR REPLACE ", "").split())


def test_hay_migraciones_numeradas():
    assert MIGRACIONES
    assert all(re.match(r"\d{3}_[a-z0-9_]+\.sql$", m.name) for m in MIGRACIONES)


@pytest.mark.parametrize("ruta", MIGRACIONES, ids=[m.name for m in MIGRACIONES])
def test_migracion_es_sql_valido_y_transaccional(ruta):
    sql = ruta.read_text(encoding="utf-8")
    pglast.parse_sql(_sin_meta_psql(sql))
    assert "BEGIN;" in sql and "COMMIT;" in sql
    assert "DROP SCHEMA" not in sql and "DROP TABLE" not in sql      # nunca borra datos


def test_migracion_001_coincide_con_schema():
    sql = (RAIZ / "db" / "migraciones" / "001_trabajos_atascados_y_abandono.sql").read_text(encoding="utf-8")
    for f in ("tomar_trabajo_ia", "marcar_abandonadas"):
        assert _funcion(sql, f) == _funcion(ESQUEMA, f), f
    assert _vista(sql, "ia_animo") == _vista(ESQUEMA, "ia_animo")
    assert "tomado_en" in ESQUEMA and "horas_para_abandono" in ESQUEMA
    assert "marcar_abandonadas()\n      TO lente_ia" in ESQUEMA


def test_trabajos_interrumpidos_se_recuperan_antes_de_tomar_uno_nuevo():
    cuerpo = _funcion(ESQUEMA, "tomar_trabajo_ia")
    assert cuerpo.index("reportar_error_ia") < cuerpo.index("estado = 'procesando', intentos")
    assert "interval '20 minutes'" in cuerpo          # más que el límite de 15 min de la preparación
    assert "FOR UPDATE SKIP LOCKED" in cuerpo
