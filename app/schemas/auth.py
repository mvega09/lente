from pydantic import BaseModel, Field


class LoginEntrada(BaseModel):
    usuario: str = Field(min_length=1, max_length=80)
    clave: str = Field(min_length=1, max_length=200)


class UsuarioSesion(BaseModel):
    id: int
    rol: str
    nombre: str
    debe_cambiar_clave: bool = False


class TokenSalida(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario: UsuarioSesion
