"""Atajos de dependencias para los routers."""

from typing import Annotated

import logging

from fastapi import Depends, Header, HTTPException, status
from psycopg import AsyncConnection

from app.core.db import get_conn, uno
from app.core.security import requiere_rol, usuario_actual
from app.schemas.auth import UsuarioSesion
from app.services.admin_service import SQL_PROFESOR_A_SUPERVISAR

log = logging.getLogger("lente.api")

# scope="function": el COMMIT ocurre ANTES de enviar la respuesta. Con el valor por
# defecto ("request") FastAPI responde primero y confirma después: el frontend podía
# pedir el siguiente paso antes de que se guardara el anterior, y un COMMIT fallido
# llegaba al cliente como éxito (RNF-04).
Conn = Annotated[AsyncConnection, Depends(get_conn, scope="function")]
Sesion = Annotated[UsuarioSesion, Depends(usuario_actual)]
Admin = Annotated[UsuarioSesion, Depends(requiere_rol("administrador"))]


async def profesor_efectivo(
    usuario: Annotated[UsuarioSesion, Depends(usuario_actual)],
    conn: Annotated[AsyncConnection, Depends(get_conn, scope="function")],
    como_profesor: Annotated[int | None, Header(
        alias="X-Como-Profesor",
        description="Solo administrador: id del profesor cuyos módulos quiere ver y editar")] = None,
) -> UsuarioSesion:
    """Quién es «el profesor» de la petición.

    - Un profesor es siempre él mismo: la cabecera se ignora (no puede hacerse pasar por otro).
    - Un administrador elige un profesor con la cabecera X-Como-Profesor y trabaja en sus
      cursos, estudiantes, textos y actividades con los mismos permisos que él (supervisión).
    """
    if usuario.rol == "profesor":
        return usuario
    if usuario.rol != "administrador":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tiene permiso")
    if como_profesor is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Elija el profesor cuyos módulos quiere ver (cabecera X-Como-Profesor)")
    fila = await uno(conn, SQL_PROFESOR_A_SUPERVISAR, {"id": como_profesor})
    if fila is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="El profesor no existe")
    log.info("Administrador %s actúa como profesor %s", usuario.id, fila["id"])
    return UsuarioSesion(id=fila["id"], rol="profesor", nombre=fila["nombre"])


# Rutas del profesor: también las usa el administrador eligiendo un profesor
Profesor = Annotated[UsuarioSesion, Depends(profesor_efectivo)]
