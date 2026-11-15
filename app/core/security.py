"""Tokens de sesión (JWT) y control de roles.

La contraseña la valida PostgreSQL con lente.iniciar_sesion (pgcrypto);
aquí solo se emite y se verifica el token.
"""

from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings
from app.schemas.auth import UsuarioSesion

_bearer = HTTPBearer(auto_error=False)


def crear_token(usuario: UsuarioSesion) -> str:
    s = get_settings()
    ahora = datetime.now(timezone.utc)
    datos = {
        "sub": str(usuario.id),
        "rol": usuario.rol,
        "nombre": usuario.nombre,
        "iat": ahora,
        "exp": ahora + timedelta(minutes=s.jwt_minutos),
    }
    return jwt.encode(datos, s.jwt_secreto, algorithm=s.jwt_algoritmo)


def usuario_actual(
    cred: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> UsuarioSesion:
    no_autorizado = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Sesión no válida o vencida",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if cred is None:
        raise no_autorizado
    s = get_settings()
    try:
        datos = jwt.decode(cred.credentials, s.jwt_secreto, algorithms=[s.jwt_algoritmo])
    except jwt.PyJWTError:
        raise no_autorizado
    return UsuarioSesion(id=int(datos["sub"]), rol=datos["rol"], nombre=datos["nombre"])


def requiere_rol(*roles: str):
    """Dependencia que exige uno de los roles indicados (p. ej. 'administrador', 'profesor')."""

    def _verificar(usuario: UsuarioSesion = Depends(usuario_actual)) -> UsuarioSesion:
        if usuario.rol not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tiene permiso")
        return usuario

    return _verificar
