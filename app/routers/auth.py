from fastapi import APIRouter, Depends, HTTPException, status
from psycopg import AsyncConnection

from app.core.db import get_conn
from app.core.security import crear_token, usuario_actual
from app.schemas.auth import LoginEntrada, TokenSalida, UsuarioSesion
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["autenticación"])


@router.post("/login", response_model=TokenSalida, summary="Inicio de sesión de administrador o profesor")
async def login(datos: LoginEntrada, conn: AsyncConnection = Depends(get_conn)) -> TokenSalida:
    usuario = await auth_service.iniciar_sesion(conn, datos.usuario, datos.clave)
    if usuario is None:
        # Mismo mensaje para usuario inexistente, clave errada o cuenta bloqueada
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario o clave incorrectos")
    return TokenSalida(access_token=crear_token(usuario), usuario=usuario)


@router.get("/yo", response_model=UsuarioSesion, summary="Datos del usuario de la sesión actual")
async def yo(usuario: UsuarioSesion = Depends(usuario_actual)) -> UsuarioSesion:
    return usuario
