from datetime import datetime
from typing import Literal

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


ReglaLogro = Literal["actividades_terminadas", "racha", "micro_perfecto", "idea_correcta", "nivel"]


class LogroSalida(BaseModel):
    id: int
    nombre: str
    descripcion: str
    regla: ReglaLogro
    meta: int
    activo: bool
    ganados: int = Field(description="Cuántos estudiantes lo han ganado")


class LogroNuevo(BaseModel):
    """RF-18 / RNF-08: la regla es una de las que calcula la base al terminar cada actividad."""

    nombre: str = Field(min_length=1, max_length=60)
    descripcion: str = Field(min_length=1, max_length=160)
    regla: ReglaLogro = Field(description="actividades_terminadas · racha (días) · micro_perfecto · "
                                          "idea_correcta · nivel")
    meta: int = Field(default=1, ge=1, le=1000, description="Cuánto hace falta: actividades, días o nivel")


class LogroCambios(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=60)
    descripcion: str | None = Field(default=None, min_length=1, max_length=160)
    meta: int | None = Field(default=None, ge=1, le=1000)
    activo: bool | None = Field(default=None, description="Desactivar lo oculta; los ya ganados se conservan")


class ResumenAdmin(BaseModel):
    """RF-04: totales y estado de las cuentas."""

    total_profesores: int
    profesores_activos: int
    total_estudiantes: int
    estudiantes_activos: int
