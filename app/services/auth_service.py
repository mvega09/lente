"""Inicio de sesión: delega la verificación de la clave a PostgreSQL.

lente.iniciar_sesion compara la clave con pgcrypto, cuenta los intentos
fallidos y bloquea al quinto. Devuelve una fila si la clave es correcta.
"""

from psycopg import AsyncConnection

from app.schemas.auth import UsuarioSesion


async def iniciar_sesion(conn: AsyncConnection, usuario: str, clave: str) -> UsuarioSesion | None:
    async with conn.cursor() as cur:
        await cur.execute("SELECT * FROM lente.iniciar_sesion(%s, %s)", (usuario, clave))
        fila = await cur.fetchone()
    return UsuarioSesion(**fila) if fila else None
