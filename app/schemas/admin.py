from datetime import datetime

from pydantic import BaseModel, Field

# Mismo patrón que el CHECK de lente.usuarios.usuario
PATRON_USUARIO = r"^[a-z0-9._-]{3,40}$"


class ProfesorNuevo(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    usuario: str | None = Field(default=None, pattern=PATRON_USUARIO,
                                description="Vacío = se propone a partir del nombre (ana.maria.duque)")
    clave: str | None = Field(default=None, min_length=8, max_length=200,
                              description="Vacío = el sistema genera una clave temporal y la devuelve una sola vez")


class ProfesorCambios(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=120)
    activo: bool | None = None


class ClaveTemporal(BaseModel):
    clave: str | None = Field(default=None, min_length=8, max_length=200,
                              description="Vacío = el sistema genera una clave temporal")


class ClaveGenerada(BaseModel):
    clave_temporal: str | None = Field(description="Solo cuando la generó el sistema; no se vuelve a mostrar")


class ProfesorSalida(BaseModel):
    id: int
    nombre: str
    usuario: str
    activo: bool
    ultimo_ingreso: datetime | None
    cursos: int
    estudiantes: int


class ProfesorCreado(ProfesorSalida):
    clave_temporal: str | None = Field(default=None, description="Solo cuando la generó el sistema; no se vuelve a mostrar")


class ResumenAdmin(BaseModel):
    """RF-04: totales y estado de las cuentas."""

    total_profesores: int
    profesores_activos: int
    total_estudiantes: int
    estudiantes_activos: int
