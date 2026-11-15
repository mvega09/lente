"""Inicio de sesión y cambio de contraseña.

lente.iniciar_sesion compara la clave con pgcrypto, cuenta los intentos
fallidos y bloquea al quinto. Devuelve una fila si la clave es correcta.
"""

from psycopg import AsyncConnection

from app.core.db import uno
from app.schemas.auth import UsuarioSesion

SQL_INICIAR_SESION = "SELECT * FROM lente.iniciar_sesion(%(usuario)s, %(clave)s)"

SQL_CAMBIAR_CLAVE = """
UPDATE lente.usuarios
   SET clave_cifrada = public.crypt(%(nueva)s, public.gen_salt('bf', 10)),
       debe_cambiar_clave = false
 WHERE id = %(id)s
   AND activo
   AND clave_cifrada = public.crypt(%(actual)s, clave_cifrada)
RETURNING id
"""


async def iniciar_sesion(conn: AsyncConnection, usuario: str, clave: str) -> UsuarioSesion | None:
    fila = await uno(conn, SQL_INICIAR_SESION, {"usuario": usuario, "clave": clave})
    return UsuarioSesion(**fila) if fila else None


async def cambiar_clave(conn: AsyncConnection, usuario_id: int, actual: str, nueva: str) -> bool:
    """Devuelve False si la contraseña actual no es correcta."""
    return await uno(conn, SQL_CAMBIAR_CLAVE, {"id": usuario_id, "actual": actual, "nueva": nueva}) is not None
