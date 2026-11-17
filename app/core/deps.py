"""Atajos de dependencias para los routers."""

from typing import Annotated

from fastapi import Depends
from psycopg import AsyncConnection

from app.core.db import get_conn
from app.core.security import requiere_rol, usuario_actual
from app.schemas.auth import UsuarioSesion

# scope="function": el COMMIT ocurre ANTES de enviar la respuesta. Con el valor por
# defecto ("request") FastAPI responde primero y confirma después: el frontend podía
# pedir el siguiente paso antes de que se guardara el anterior, y un COMMIT fallido
# llegaba al cliente como éxito (RNF-04).
Conn = Annotated[AsyncConnection, Depends(get_conn, scope="function")]
Sesion = Annotated[UsuarioSesion, Depends(usuario_actual)]
Admin = Annotated[UsuarioSesion, Depends(requiere_rol("administrador"))]
Profesor = Annotated[UsuarioSesion, Depends(requiere_rol("profesor"))]
