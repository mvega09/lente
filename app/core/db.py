"""Pool de conexiones a PostgreSQL para la API (rol lente_app).

Cada petición toma una conexión del pool. Al salir del bloque sin errores
se hace COMMIT automáticamente; si hay una excepción, ROLLBACK.
Use SIEMPRE consultas parametrizadas (%s / %(nombre)s), nunca f-strings con
datos del usuario.
"""

from collections.abc import AsyncIterator
from typing import Any

from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from app.core.config import get_settings

_pool: AsyncConnectionPool | None = None


async def abrir_pool() -> None:
    global _pool
    _pool = AsyncConnectionPool(
        conninfo=get_settings().conninfo_app,
        min_size=1,
        max_size=10,
        open=False,
        kwargs={"row_factory": dict_row},
    )
    await _pool.open()


async def cerrar_pool() -> None:
    if _pool is not None:
        await _pool.close()


async def get_conn() -> AsyncIterator[AsyncConnection]:
    """Dependencia de FastAPI: entrega una conexión del pool."""
    if _pool is None:
        raise RuntimeError("El pool de base de datos no está abierto")
    async with _pool.connection() as conn:
        yield conn


async def ejecutar(conn: AsyncConnection, sql: str, params: Any = None) -> int:
    """Ejecuta una sentencia sin RETURNING y devuelve cuántas filas afectó."""
    async with conn.cursor() as cur:
        await cur.execute(sql, params)
        return cur.rowcount


async def uno(conn: AsyncConnection, sql: str, params: Any = None) -> dict | None:
    """Ejecuta una consulta y devuelve la primera fila (o None)."""
    async with conn.cursor() as cur:
        await cur.execute(sql, params)
        return await cur.fetchone()


async def varios(conn: AsyncConnection, sql: str, params: Any = None) -> list[dict]:
    """Ejecuta una consulta y devuelve todas las filas."""
    async with conn.cursor() as cur:
        await cur.execute(sql, params)
        return await cur.fetchall()
