from pydantic import BaseModel, Field


class CursoNuevo(BaseModel):
    nombre: str = Field(min_length=1, max_length=80, examples=["7°B"])
    institucion: str | None = Field(default=None, max_length=120)
    anio: int | None = Field(default=None, ge=2020, le=2100, description="Vacío = año actual")


class CursoCambios(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=80)
    institucion: str | None = Field(default=None, max_length=120)
    activo: bool | None = None


class CursoSalida(BaseModel):
    id: int
    nombre: str
    institucion: str | None
    anio: int
    activo: bool
    estudiantes: int


class EstudianteNuevo(BaseModel):
    """RF-03: solo se pide el nombre. El grado es opcional (RF-20)."""

    nombre: str = Field(min_length=1, max_length=80)
    grado: int | None = Field(default=None, ge=3, le=11)


class EstudianteCambios(BaseModel):
    """Solo se cambian los campos enviados. Enviar "grado": null lo deja "Sin grado"."""

    nombre: str | None = Field(default=None, min_length=1, max_length=80)
    grado: int | None = Field(default=None, ge=3, le=11)
    activo: bool | None = None
    curso_id: int | None = Field(default=None, description="Mover a otro curso del mismo profesor")


class EstudianteSalida(BaseModel):
    id: int
    nombre: str
    curso_id: int
    curso: str
    grado: int | None
    grado_texto: str
    nivel_escolar: str
    estado: str
    puntos: int
    nivel: int
    racha: int
    mejor_racha: int


class EstudianteAdmin(EstudianteSalida):
    profesor_id: int
    profesor: str
