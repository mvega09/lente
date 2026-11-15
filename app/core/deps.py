"""Atajos de dependencias para los routers."""

from typing import Annotated

from fastapi import Depends
from psycopg import AsyncConnection

from app.core.db import get_conn
from app.core.security import requiere_rol, usuario_actual
from app.schemas.auth import UsuarioSesion

Conn = Annotated[AsyncConnection, Depends(get_conn)]
Sesion = Annotated[UsuarioSesion, Depends(usuario_actual)]
Admin = Annotated[UsuarioSesion, Depends(requiere_rol("administrador"))]
Profesor = Annotated[UsuarioSesion, Depends(requiere_rol("profesor"))]
