from pydantic import BaseModel, Field, model_validator


class LoginEntrada(BaseModel):
    usuario: str = Field(min_length=1, max_length=80)
    clave: str = Field(min_length=1, max_length=200)


class CambioClave(BaseModel):
    actual: str = Field(min_length=1, max_length=200)
    nueva: str = Field(min_length=8, max_length=200)

    @model_validator(mode="after")
    def _distinta(self):
        if self.actual == self.nueva:
            raise ValueError("La contraseña nueva debe ser distinta a la actual")
        return self


class UsuarioSesion(BaseModel):
    id: int
    rol: str
    nombre: str
    debe_cambiar_clave: bool = False


class TokenSalida(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario: UsuarioSesion
