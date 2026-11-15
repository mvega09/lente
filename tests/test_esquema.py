"""Comprueba, sin base de datos, que las columnas usadas en el SQL de los
servicios existan en el esquema (db/schema.sql).

Se analiza el esquema y cada consulta con el analizador real de PostgreSQL
(pglast). Se verifican:
  - columnas calificadas con alias o tabla (a.columna),
  - columnas de INSERT (...) y de UPDATE ... SET,
  - columnas sin calificar cuando la consulta usa una sola tabla o vista.
"""

import pathlib

import pglast
import pytest

from tests.test_sql import CONSULTAS, _a_postgres

ESQUEMA = pathlib.Path(__file__).resolve().parent.parent / "db" / "schema.sql"


# ---------------------------------------------------------------- recorrido del árbol

def _nodos(x):
    """Recorre el árbol (en forma de diccionarios) y entrega cada nodo con tipo."""
    if isinstance(x, dict):
        if "@" in x:
            yield x
        for v in x.values():
            yield from _nodos(v)
    elif isinstance(x, (list, tuple)):
        for v in x:
            yield from _nodos(v)


def _texto(campo) -> str | None:
    if isinstance(campo, dict) and campo.get("@") == "String":
        return campo.get("sval") or campo.get("str")
    return None


def _arbol(sql: str) -> list[dict]:
    return [s() for s in pglast.parse_sql(sql)]


# ---------------------------------------------------------------- catálogo del esquema

def _catalogo() -> dict[str, set[str]]:
    lineas = [l for l in ESQUEMA.read_text(encoding="utf-8").splitlines() if not l.lstrip().startswith("\\")]
    cat: dict[str, set[str]] = {}
    for stmt in _arbol("\n".join(lineas)):
        for n in _nodos(stmt):
            if n["@"] == "CreateStmt":
                cat[n["relation"]["relname"]] = {c["colname"] for c in n.get("tableElts", ())
                                                 if c.get("@") == "ColumnDef"}
            elif n["@"] == "ViewStmt":
                cols = set()
                for t in n["query"].get("targetList", ()):
                    if t.get("name"):
                        cols.add(t["name"])
                    elif t.get("val", {}).get("@") == "ColumnRef":
                        ultimo = _texto(t["val"]["fields"][-1])
                        if ultimo:
                            cols.add(ultimo)
                cat[n["view"]["relname"]] = cols
    return cat


CATALOGO = _catalogo() if ESQUEMA.exists() else {}


def test_catalogo_cargado():
    assert {"usuarios", "textos", "actividades", "respuestas", "vista_panel", "vista_estudiantes"} <= set(CATALOGO)
    assert "idea_principal" in CATALOGO["textos"]
    assert "porcentaje_acierto" in CATALOGO["vista_progreso"]


# ---------------------------------------------------------------- verificación de consultas

def _problemas(sql: str) -> list[str]:
    errores = []
    for stmt in _arbol(_a_postgres(sql)):
        alias: dict[str, str] = {}
        relaciones = []
        for n in _nodos(stmt):
            if n["@"] == "RangeVar" and n["relname"] in CATALOGO:
                relaciones.append(n["relname"])
                alias[n["relname"]] = n["relname"]
                if n.get("alias"):
                    alias[n["alias"]["aliasname"]] = n["relname"]

        for n in _nodos(stmt):
            if n["@"] == "ColumnRef":
                partes = [_texto(f) for f in n["fields"]]
                if None in partes:              # a.* u otras formas
                    continue
                if len(partes) == 2 and partes[0] in alias:
                    tabla = alias[partes[0]]
                    if partes[1] not in CATALOGO[tabla]:
                        errores.append(f"{partes[0]}.{partes[1]} no existe en {tabla}")
                elif len(partes) == 1 and len(set(relaciones)) == 1:
                    tabla = relaciones[0]
                    if partes[0] not in CATALOGO[tabla]:
                        errores.append(f"{partes[0]} no existe en {tabla}")

            elif n["@"] in ("InsertStmt", "UpdateStmt"):
                tabla = n["relation"]["relname"]
                if tabla not in CATALOGO:
                    continue
                destinos = n.get("cols", ()) if n["@"] == "InsertStmt" else n.get("targetList", ())
                for t in destinos:
                    if t.get("name") and t["name"] not in CATALOGO[tabla]:
                        errores.append(f"columna destino {t['name']} no existe en {tabla}")
    return errores


@pytest.mark.skipif(not ESQUEMA.exists(), reason="Falta db/schema.sql")
@pytest.mark.parametrize(("nombre", "sql"), CONSULTAS, ids=[n for n, _ in CONSULTAS])
def test_columnas_existen(nombre, sql):
    assert _problemas(sql) == []


def test_el_verificador_detecta_errores():
    assert _problemas("SELECT t.titulo_mal FROM lente.textos t") == ["t.titulo_mal no existe en textos"]
    assert _problemas("UPDATE lente.cursos SET nombre_x = 1 WHERE id = 1") != []
    assert _problemas("INSERT INTO lente.alertas (estudiante_id, motivox) VALUES (1, 'x')") != []
