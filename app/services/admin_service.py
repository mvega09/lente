"""RF-02 y RF-04: cuentas de profesores y consulta general (solo administrador)."""

from psycopg import AsyncConnection

from app.core.db import uno, varios
from app.core.errores import NoEncontrado

SQL_LISTAR_PROFESORES = """
SELECT id, nombre, usuario, activo, ultimo_ingreso, cursos, estudiantes
  FROM lente.vista_profesores
 ORDER BY nombre
"""

SQL_OBTENER_PROFESOR = """
SELECT id, nombre, usuario, activo, ultimo_ingreso, cursos, estudiantes
  FROM lente.vista_profesores
 WHERE id = %(id)s
"""

SQL_CREAR_PROFESOR = """
INSERT INTO lente.usuarios (rol, nombre, usuario, clave_cifrada, debe_cambiar_clave)
VALUES ('profesor', %(nombre)s, lower(%(usuario)s),
        public.crypt(%(clave)s, public.gen_salt('bf', 10)), true)
RETURNING id
"""

SQL_ACTUALIZAR_PROFESOR = """
UPDATE lente.usuarios
   SET nombre = coalesce(%(nombre)s::text, nombre),
       activo = coalesce(%(activo)s::boolean, activo)
 WHERE id = %(id)s AND rol = 'profesor'
RETURNING id
"""

SQL_RESTABLECER_CLAVE = """
UPDATE lente.usuarios
   SET clave_cifrada = public.crypt(%(clave)s, public.gen_salt('bf', 10)),
       debe_cambiar_clave = true,
       intentos_fallidos = 0
 WHERE id = %(id)s AND rol = 'profesor'
RETURNING id
"""

SQL_RESUMEN = """
SELECT (SELECT count(*) FROM lente.usuarios WHERE rol = 'profesor')              AS total_profesores,
       (SELECT count(*) FROM lente.usuarios WHERE rol = 'profesor' AND activo)   AS profesores_activos,
       (SELECT count(*) FROM lente.estudiantes)                                  AS total_estudiantes,
       (SELECT count(*) FROM lente.estudiantes WHERE activo)                     AS estudiantes_activos
"""

SQL_ESTUDIANTES_TODOS = """
SELECT id, nombre, curso_id, curso, profesor_id, profesor, grado, grado_texto,
       nivel_escolar, estado, puntos, nivel, racha, mejor_racha
  FROM lente.vista_estudiantes
 ORDER BY profesor, curso, nombre
"""


async def listar_profesores(conn: AsyncConnection) -> list[dict]:
    return await varios(conn, SQL_LISTAR_PROFESORES)


async def obtener_profesor(conn: AsyncConnection, profesor_id: int) -> dict:
    fila = await uno(conn, SQL_OBTENER_PROFESOR, {"id": profesor_id})
    if fila is None:
        raise NoEncontrado("El profesor")
    return fila


async def crear_profesor(conn: AsyncConnection, nombre: str, usuario: str, clave: str) -> dict:
    nuevo = await uno(conn, SQL_CREAR_PROFESOR, {"nombre": nombre, "usuario": usuario, "clave": clave})
    return await obtener_profesor(conn, nuevo["id"])


async def actualizar_profesor(conn: AsyncConnection, profesor_id: int, nombre: str | None,
                              activo: bool | None) -> dict:
    fila = await uno(conn, SQL_ACTUALIZAR_PROFESOR, {"id": profesor_id, "nombre": nombre, "activo": activo})
    if fila is None:
        raise NoEncontrado("El profesor")
    return await obtener_profesor(conn, profesor_id)


async def restablecer_clave(conn: AsyncConnection, profesor_id: int, clave: str) -> None:
    if await uno(conn, SQL_RESTABLECER_CLAVE, {"id": profesor_id, "clave": clave}) is None:
        raise NoEncontrado("El profesor")


async def resumen(conn: AsyncConnection) -> dict:
    return await uno(conn, SQL_RESUMEN)


async def listar_estudiantes(conn: AsyncConnection) -> list[dict]:
    return await varios(conn, SQL_ESTUDIANTES_TODOS)
