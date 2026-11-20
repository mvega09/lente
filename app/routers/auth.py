from fastapi import APIRouter, HTTPException, status

from app.core.deps import Conn, Sesion
from app.core.security import crear_token
from app.schemas.auth import CambioClave, LoginEntrada, TokenSalida, UsuarioSesion
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["autenticación"])


@router.post("/login", response_model=TokenSalida, summary="Inicio de sesión de administrador o profesor (RF-01)")
async def login(datos: LoginEntrada, conn: Conn) -> TokenSalida:
    usuario = await auth_service.iniciar_sesion(conn, datos.usuario, datos.clave)
    if usuario is None:
        # La base ya sumó el intento fallido (con 5 se bloquea la cuenta). Se confirma ANTES
        # de responder: el 401 es una excepción y, sin este commit, la transacción se
        # deshacía con todo y el intento, así que el bloqueo nunca llegaba.
        await conn.commit()
        # Mismo mensaje para usuario inexistente, clave errada o cuenta bloqueada
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario o clave incorrectos")
    return TokenSalida(access_token=crear_token(usuario), usuario=usuario)


@router.get("/yo", response_model=UsuarioSesion, summary="Datos del usuario de la sesión actual")
async def yo(usuario: Sesion) -> UsuarioSesion:
    return usuario


@router.post("/cambiar-clave", status_code=status.HTTP_204_NO_CONTENT,
             summary="Cambiar la contraseña (obligatorio tras una clave temporal)")
async def cambiar_clave(datos: CambioClave, usuario: Sesion, conn: Conn) -> None:
    if not await auth_service.cambiar_clave(conn, usuario.id, datos.actual, datos.nueva):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La contraseña actual no es correcta")
