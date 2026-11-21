"""RF-02 y RF-04: cuentas de profesores y consulta general (solo administrador)."""

import re
import secrets
import unicodedata

from psycopg import AsyncConnection

from app.core.db import uno, varios
from app.core.errores import Conflicto, NoEncontrado

_ALFABETO_CLAVE = "ABCDEFGHJKMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789"

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

# Administrador en modo supervisión: solo cuentas de profesor
SQL_PROFESOR_A_SUPERVISAR = "SELECT id, nombre FROM lente.usuarios WHERE id = %(id)s AND rol = 'profesor'"

SQL_USUARIOS_PARECIDOS = """
SELECT lower(usuario) AS usuario FROM lente.usuarios
 WHERE left(lower(usuario), length(%(base)s::text)) = %(base)s::text
"""

_COLUMNAS_LOGRO = """
SELECT l.id, l.nombre, l.descripcion, l.regla, l.meta, l.activo,
       (SELECT count(*) FROM lente.logros_ganados g WHERE g.logro_id = l.id) AS ganados
  FROM lente.logros l
"""

SQL_LOGROS = _COLUMNAS_LOGRO + " ORDER BY l.id"

SQL_OBTENER_LOGRO = _COLUMNAS_LOGRO + " WHERE l.id = %(id)s"

SQL_CREAR_LOGRO = """
INSERT INTO lente.logros (nombre, descripcion, regla, meta)
VALUES (%(nombre)s, %(descripcion)s, %(regla)s, %(meta)s)
RETURNING id
"""

SQL_ACTUALIZAR_LOGRO = """
UPDATE lente.logros
   SET nombre = coalesce(%(nombre)s::text, nombre),
       descripcion = coalesce(%(descripcion)s::text, descripcion),
       meta = coalesce(%(meta)s::smallint, meta),
       activo = coalesce(%(activo)s::boolean, activo)
 WHERE id = %(id)s
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


def proponer_usuario(nombre: str) -> str:
    """'Ana María Duque' → 'ana.maria.duque' (cumple el patrón de lente.usuarios)."""
    t = unicodedata.normalize("NFD", nombre.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    partes = re.findall(r"[a-z0-9]+", t)
    base = ".".join(partes)[:40].strip(".")
    return base if len(base) >= 3 else (base + ".profe")[:40]


def generar_clave() -> str:
    """Clave temporal legible, sin caracteres que se confundan (0/O, 1/l/I)."""
    return "Lente-" + "".join(secrets.choice(_ALFABETO_CLAVE) for _ in range(8))


async def _usuario_libre(conn: AsyncConnection, base: str) -> str:
    usados = {f["usuario"] for f in await varios(conn, SQL_USUARIOS_PARECIDOS, {"base": base})}
    if base not in usados:
        return base
    for n in range(2, 1000):
        candidato = f"{base[:40 - len(str(n))]}{n}"
        if candidato not in usados:
            return candidato
    raise Conflicto("No se encontró un nombre de usuario libre; escríbalo a mano")


async def crear_profesor(conn: AsyncConnection, nombre: str, usuario: str | None, clave: str | None) -> dict:
    usuario = usuario or await _usuario_libre(conn, proponer_usuario(nombre))
    generada = None if clave else generar_clave()
    nuevo = await uno(conn, SQL_CREAR_PROFESOR, {"nombre": nombre, "usuario": usuario, "clave": clave or generada})
    return await obtener_profesor(conn, nuevo["id"]) | {"clave_temporal": generada}


async def actualizar_profesor(conn: AsyncConnection, profesor_id: int, nombre: str | None,
                              activo: bool | None) -> dict:
    fila = await uno(conn, SQL_ACTUALIZAR_PROFESOR, {"id": profesor_id, "nombre": nombre, "activo": activo})
    if fila is None:
        raise NoEncontrado("El profesor")
    return await obtener_profesor(conn, profesor_id)


async def restablecer_clave(conn: AsyncConnection, profesor_id: int, clave: str | None) -> dict:
    generada = None if clave else generar_clave()
    if await uno(conn, SQL_RESTABLECER_CLAVE, {"id": profesor_id, "clave": clave or generada}) is None:
        raise NoEncontrado("El profesor")
    return {"clave_temporal": generada}


# ---------------------------------------------------------------- logros (RF-18, RNF-08)

async def listar_logros(conn: AsyncConnection) -> list[dict]:
    return await varios(conn, SQL_LOGROS)


async def obtener_logro(conn: AsyncConnection, logro_id: int) -> dict:
    fila = await uno(conn, SQL_OBTENER_LOGRO, {"id": logro_id})
    if fila is None:
        raise NoEncontrado("El logro")
    return fila


async def crear_logro(conn: AsyncConnection, datos: dict) -> dict:
    nuevo = await uno(conn, SQL_CREAR_LOGRO, datos)
    return await obtener_logro(conn, nuevo["id"])


async def actualizar_logro(conn: AsyncConnection, logro_id: int, cambios: dict) -> dict:
    params = {"id": logro_id, "nombre": None, "descripcion": None, "meta": None, "activo": None} | cambios
    if await uno(conn, SQL_ACTUALIZAR_LOGRO, params) is None:
        raise NoEncontrado("El logro")
    return await obtener_logro(conn, logro_id)


async def resumen(conn: AsyncConnection) -> dict:
    return await uno(conn, SQL_RESUMEN)


async def listar_estudiantes(conn: AsyncConnection) -> list[dict]:
    return await varios(conn, SQL_ESTUDIANTES_TODOS)
