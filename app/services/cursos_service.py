"""Cursos y estudiantes del profesor (RF-03, RF-05, RF-20).

Toda consulta filtra por el profesor de la sesión (RNF-05). Si el curso o
el estudiante es de otro profesor, se responde como si no existiera.
"""

from psycopg import AsyncConnection

from app.core.db import uno, varios
from app.core.errores import NoEncontrado

_COLUMNAS_CURSO = """
SELECT c.id, c.nombre, c.institucion, c.anio, c.activo,
       (SELECT count(*) FROM lente.estudiantes s WHERE s.curso_id = c.id AND s.activo) AS estudiantes
  FROM lente.cursos c
"""

SQL_LISTAR_CURSOS = _COLUMNAS_CURSO + """
 WHERE c.profesor_id = %(profesor)s
 ORDER BY c.anio DESC, c.nombre
"""

SQL_OBTENER_CURSO = _COLUMNAS_CURSO + """
 WHERE c.id = %(id)s AND c.profesor_id = %(profesor)s
"""

SQL_CREAR_CURSO = """
INSERT INTO lente.cursos (profesor_id, nombre, institucion, anio)
VALUES (%(profesor)s, %(nombre)s, %(institucion)s,
        coalesce(%(anio)s::smallint, extract(year FROM now())::smallint))
RETURNING id
"""

SQL_ACTUALIZAR_CURSO = """
UPDATE lente.cursos
   SET nombre      = coalesce(%(nombre)s::text, nombre),
       institucion = coalesce(%(institucion)s::text, institucion),
       activo      = coalesce(%(activo)s::boolean, activo)
 WHERE id = %(id)s AND profesor_id = %(profesor)s
RETURNING id
"""

_COLUMNAS_ESTUDIANTE = """
SELECT id, nombre, curso_id, curso, grado, grado_texto, nivel_escolar, estado,
       puntos, nivel, racha, mejor_racha
  FROM lente.vista_estudiantes
"""

SQL_ESTUDIANTES_CURSO = _COLUMNAS_ESTUDIANTE + """
 WHERE curso_id = %(curso)s AND profesor_id = %(profesor)s
 ORDER BY nombre
"""

SQL_OBTENER_ESTUDIANTE = _COLUMNAS_ESTUDIANTE + """
 WHERE id = %(id)s AND profesor_id = %(profesor)s
"""

# El INSERT ... SELECT garantiza que el curso sea del profesor de la sesión
SQL_CREAR_ESTUDIANTE = """
INSERT INTO lente.estudiantes (curso_id, nombre, grado)
SELECT c.id, %(nombre)s, %(grado)s::smallint
  FROM lente.cursos c
 WHERE c.id = %(curso)s AND c.profesor_id = %(profesor)s
RETURNING id
"""

SQL_ACTUALIZAR_ESTUDIANTE = """
UPDATE lente.estudiantes s
   SET nombre   = coalesce(%(nombre)s::text, s.nombre),
       grado    = CASE WHEN %(cambiar_grado)s::boolean THEN %(grado)s::smallint ELSE s.grado END,
       activo   = coalesce(%(activo)s::boolean, s.activo),
       curso_id = coalesce(%(curso)s::bigint, s.curso_id)
 WHERE s.id = %(id)s
   AND s.curso_id IN (SELECT id FROM lente.cursos WHERE profesor_id = %(profesor)s)
   AND (%(curso)s::bigint IS NULL
        OR EXISTS (SELECT 1 FROM lente.cursos WHERE id = %(curso)s::bigint AND profesor_id = %(profesor)s))
RETURNING s.id
"""


# ---------------------------------------------------------------- cursos

async def listar_cursos(conn: AsyncConnection, profesor_id: int) -> list[dict]:
    return await varios(conn, SQL_LISTAR_CURSOS, {"profesor": profesor_id})


async def obtener_curso(conn: AsyncConnection, profesor_id: int, curso_id: int) -> dict:
    fila = await uno(conn, SQL_OBTENER_CURSO, {"id": curso_id, "profesor": profesor_id})
    if fila is None:
        raise NoEncontrado("El curso")
    return fila


async def crear_curso(conn: AsyncConnection, profesor_id: int, nombre: str,
                      institucion: str | None, anio: int | None) -> dict:
    nuevo = await uno(conn, SQL_CREAR_CURSO, {"profesor": profesor_id, "nombre": nombre,
                                              "institucion": institucion, "anio": anio})
    return await obtener_curso(conn, profesor_id, nuevo["id"])


async def actualizar_curso(conn: AsyncConnection, profesor_id: int, curso_id: int, cambios: dict) -> dict:
    params = {"id": curso_id, "profesor": profesor_id, "nombre": None, "institucion": None, "activo": None}
    params.update(cambios)
    if await uno(conn, SQL_ACTUALIZAR_CURSO, params) is None:
        raise NoEncontrado("El curso")
    return await obtener_curso(conn, profesor_id, curso_id)


# ---------------------------------------------------------------- estudiantes

async def listar_estudiantes(conn: AsyncConnection, profesor_id: int, curso_id: int) -> list[dict]:
    await obtener_curso(conn, profesor_id, curso_id)          # 404 si no es suyo
    return await varios(conn, SQL_ESTUDIANTES_CURSO, {"curso": curso_id, "profesor": profesor_id})


async def obtener_estudiante(conn: AsyncConnection, profesor_id: int, estudiante_id: int) -> dict:
    fila = await uno(conn, SQL_OBTENER_ESTUDIANTE, {"id": estudiante_id, "profesor": profesor_id})
    if fila is None:
        raise NoEncontrado("El estudiante")
    return fila


async def crear_estudiante(conn: AsyncConnection, profesor_id: int, curso_id: int,
                           nombre: str, grado: int | None) -> dict:
    nuevo = await uno(conn, SQL_CREAR_ESTUDIANTE, {"curso": curso_id, "profesor": profesor_id,
                                                   "nombre": nombre.strip(), "grado": grado})
    if nuevo is None:
        raise NoEncontrado("El curso")
    return await obtener_estudiante(conn, profesor_id, nuevo["id"])


async def actualizar_estudiante(conn: AsyncConnection, profesor_id: int, estudiante_id: int,
                                cambios: dict) -> dict:
    params = {
        "id": estudiante_id, "profesor": profesor_id,
        "nombre": cambios.get("nombre"),
        "cambiar_grado": "grado" in cambios,
        "grado": cambios.get("grado"),
        "activo": cambios.get("activo"),
        "curso": cambios.get("curso_id"),
    }
    if await uno(conn, SQL_ACTUALIZAR_ESTUDIANTE, params) is None:
        raise NoEncontrado("El estudiante o el curso de destino")
    return await obtener_estudiante(conn, profesor_id, estudiante_id)
