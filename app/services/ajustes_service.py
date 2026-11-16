"""Reglas que se cambian sin tocar código (RNF-08, RF-18).

- El profesor ajusta la gamificación y el umbral de alertas de cada curso; un
  valor propio del curso reemplaza al general y se puede quitar.
- El administrador cambia los valores generales, incluidos modelo y prompts.
Cada valor se valida antes de guardarse.
"""

from typing import Any

from psycopg import AsyncConnection
from psycopg.types.json import Jsonb

from app.core.db import uno, varios
from app.core.errores import DatoInvalido, NoEncontrado


def _entero(minimo: int, maximo: int):
    def v(x: Any):
        if isinstance(x, bool) or not isinstance(x, int) or not minimo <= x <= maximo:
            raise DatoInvalido(f"Debe ser un número entero entre {minimo} y {maximo}")
        return x
    return v


def _decimal(minimo: float, maximo: float):
    def v(x: Any):
        if isinstance(x, bool) or not isinstance(x, (int, float)) or not minimo <= x <= maximo:
            raise DatoInvalido(f"Debe ser un número entre {minimo} y {maximo}")
        return x
    return v


def _texto(maximo: int):
    def v(x: Any):
        if not isinstance(x, str) or not x.strip() or len(x) > maximo:
            raise DatoInvalido(f"Debe ser un texto de 1 a {maximo} caracteres")
        return x.strip()
    return v


def _lista_textos(x: Any):
    if not isinstance(x, list) or not 1 <= len(x) <= 20 or not all(isinstance(i, str) and i.strip() for i in x):
        raise DatoInvalido("Debe ser una lista de 1 a 20 nombres")
    return [i.strip() for i in x]


# Lo que el profesor puede ajustar en su curso
POR_CURSO = {
    "puntos_por_acierto": _entero(0, 100),
    "puntos_por_terminar": _entero(0, 50),
    "puntos_por_nivel": _entero(10, 1000),
    "minimo_para_logrado": _decimal(0, 1),
    "descuento_palabra_neutra": _decimal(0, 1),
    "alerta_veces_seguidas": _entero(1, 10),
    "horas_para_abandono": _entero(1, 168),
    "nombres_de_niveles": _lista_textos,
}

# Lo que además puede ajustar el administrador (valor general)
GENERALES = POR_CURSO | {
    "ia_modelo": _texto(100),
    "ia_modelo_validacion": _texto(100),
    "ia_tiempo_maximo_seg": _entero(5, 120),
    "ia_instrucciones_preparar": _texto(4000),
    "ia_instrucciones_revisar": _texto(4000),
}

SQL_EFECTIVOS_CURSO = """
SELECT g.clave, g.descripcion, coalesce(p.valor, g.valor) AS valor, (p.id IS NOT NULL) AS propio_del_curso
  FROM lente.ajustes g
  LEFT JOIN lente.ajustes p ON p.clave = g.clave AND p.curso_id = %(curso)s
 WHERE g.curso_id IS NULL AND g.clave = ANY(%(claves)s::text[])
 ORDER BY g.clave
"""

SQL_CURSO_DEL_PROFESOR = "SELECT id FROM lente.cursos WHERE id = %(curso)s AND profesor_id = %(profesor)s"

# Solo existe un valor por curso si existe el general (también lo exige un trigger)
SQL_GUARDAR_EN_CURSO = """
INSERT INTO lente.ajustes (clave, curso_id, valor, descripcion, actualizado_por)
SELECT g.clave, c.id, %(valor)s, g.descripcion, %(usuario)s
  FROM lente.cursos c
  JOIN lente.ajustes g ON g.clave = %(clave)s AND g.curso_id IS NULL
 WHERE c.id = %(curso)s AND c.profesor_id = %(usuario)s
ON CONFLICT (clave, curso_id) WHERE curso_id IS NOT NULL
DO UPDATE SET valor = EXCLUDED.valor, actualizado_por = EXCLUDED.actualizado_por
RETURNING clave
"""

SQL_QUITAR_DE_CURSO = """
DELETE FROM lente.ajustes a USING lente.cursos c
 WHERE a.clave = %(clave)s AND a.curso_id = c.id AND c.id = %(curso)s AND c.profesor_id = %(profesor)s
RETURNING a.clave
"""

SQL_GENERALES = """
SELECT clave, descripcion, valor, false AS propio_del_curso
  FROM lente.ajustes
 WHERE curso_id IS NULL
 ORDER BY clave
"""

SQL_GUARDAR_GENERAL = """
UPDATE lente.ajustes SET valor = %(valor)s, actualizado_por = %(usuario)s
 WHERE clave = %(clave)s AND curso_id IS NULL
RETURNING clave
"""


def validar(permitidos: dict, clave: str, valor: Any) -> Any:
    if clave not in permitidos:
        raise NoEncontrado(f"El ajuste '{clave}'")
    return permitidos[clave](valor)


async def _exigir_curso(conn: AsyncConnection, profesor_id: int, curso_id: int) -> None:
    if await uno(conn, SQL_CURSO_DEL_PROFESOR, {"curso": curso_id, "profesor": profesor_id}) is None:
        raise NoEncontrado("El curso")


async def del_curso(conn: AsyncConnection, profesor_id: int, curso_id: int) -> list[dict]:
    await _exigir_curso(conn, profesor_id, curso_id)
    return await varios(conn, SQL_EFECTIVOS_CURSO, {"curso": curso_id, "claves": list(POR_CURSO)})


async def guardar_en_curso(conn: AsyncConnection, profesor_id: int, curso_id: int, clave: str, valor: Any) -> list[dict]:
    limpio = validar(POR_CURSO, clave, valor)
    params = {"curso": curso_id, "usuario": profesor_id, "clave": clave, "valor": Jsonb(limpio)}
    if await uno(conn, SQL_GUARDAR_EN_CURSO, params) is None:
        await _exigir_curso(conn, profesor_id, curso_id)
        raise NoEncontrado(f"El ajuste general '{clave}'")
    return await del_curso(conn, profesor_id, curso_id)


async def quitar_de_curso(conn: AsyncConnection, profesor_id: int, curso_id: int, clave: str) -> list[dict]:
    """Vuelve a usar el valor general."""
    await _exigir_curso(conn, profesor_id, curso_id)
    await uno(conn, SQL_QUITAR_DE_CURSO, {"curso": curso_id, "profesor": profesor_id, "clave": clave})
    return await del_curso(conn, profesor_id, curso_id)


async def generales(conn: AsyncConnection) -> list[dict]:
    return await varios(conn, SQL_GENERALES)


async def guardar_general(conn: AsyncConnection, admin_id: int, clave: str, valor: Any) -> list[dict]:
    limpio = validar(GENERALES, clave, valor)
    if await uno(conn, SQL_GUARDAR_GENERAL, {"clave": clave, "valor": Jsonb(limpio), "usuario": admin_id}) is None:
        raise NoEncontrado(f"El ajuste general '{clave}'")
    return await generales(conn)
