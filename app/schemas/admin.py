from datetime import datetime

from pydantic import BaseModel, Field

# Mismo patrón que el CHECK de lente.usuarios.usuario
PATRON_USUARIO = r"^[a-z0-9._-]{3,40}$"


class ProfesorNuevo(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    usuario: str = Field(pattern=PATRON_USUARIO, description="3 a 40 caracteres: minúsculas, números, punto, guion")
    clave: str = Field(min_length=8, max_length=200, description="Contraseña temporal; se pide cambiarla al entrar")


class ProfesorCambios(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=120)
    activo: bool | None = None


class ClaveTemporal(BaseModel):
    clave: str = Field(min_length=8, max_length=200)


class ProfesorSalida(BaseModel):
    id: int
    nombre: str
    usuario: str
    activo: bool
    ultimo_ingreso: datetime | None
    cursos: int
    estudiantes: int


class ResumenAdmin(BaseModel):
    """RF-04: totales y estado de las cuentas."""

    total_profesores: int
    profesores_activos: int
    total_estudiantes: int
    estudiantes_activos: int
