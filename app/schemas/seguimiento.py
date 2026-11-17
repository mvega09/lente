from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.core.animo import AVISO


class LogroGanado(BaseModel):
    nombre: str
    descripcion: str
    ganado_en: datetime


class ActividadResumen(BaseModel):
    id: int
    titulo: str
    numero: int
    estado: str
    resultado_macro: float | None
    resultado_super: float | None
    resultado_micro: float | None
    puntos_ganados: int
    iniciada_en: datetime
    terminada_en: datetime | None


class LogroCatalogo(BaseModel):
    nombre: str
    descripcion: str
    regla: str
    meta: int
    ganado: bool
    ganado_en: datetime | None


class TextoPendiente(BaseModel):
    texto_id: int
    titulo: str


class Progreso(BaseModel):
    """RF-06 y RF-08: progreso individual y estadísticas de desempeño."""

    id: int
    nombre: str
    curso: str
    grado_texto: str
    nivel_escolar: str
    puntos: int
    nivel: int
    nivel_nombre: str | None
    racha: int
    mejor_racha: int
    actividades_hechas: int
    actividades_pendientes: int
    preguntas_respondidas: int
    correctas: int
    incorrectas: int
    porcentaje_acierto: float | None
    porcentaje_macro: float | None
    porcentaje_super: float | None
    porcentaje_micro: float | None
    animo: str | None = Field(description="Última tendencia registrada (RF-21)")
    aviso_animo: str = AVISO
    pendientes: list[TextoPendiente] = Field(default=[], description="Textos activos que aún no termina (RF-06)")
    logros_catalogo: list[LogroCatalogo] = Field(default=[], description="Todos los logros activos y si ya los ganó (RF-18)")
    logros: list[LogroGanado]
    evolucion: list[ActividadResumen]


class Historial(BaseModel):
    """RF-07: una fila por pregunta respondida."""

    actividad_id: int
    titulo: str
    fecha: datetime
    nivel: str
    pregunta: str
    respuesta: str | None
    respuesta_esperada: str | None
    resultado: str | None
    es_correcta: bool | None


class Destacado(BaseModel):
    id: int
    nombre: str
    puntos: int
    nivel: int
    racha: int


class Panel(BaseModel):
    """Panel del docente: participación, avance, recompensas y clima del curso."""

    curso_id: int
    curso: str
    estudiantes_activos: int
    participaron: int
    acierto_promedio: float | None
    puntos_del_curso: int
    racha_mas_larga: int
    clima: dict[str, int] = Field(description="Cuántos estudiantes en cada tendencia (RF-21)")
    aviso_clima: str = AVISO
    alertas_abiertas: int
    avance_macro: float | None = Field(default=None, description="Promedio del curso en macroestructura (0-100)")
    avance_super: float | None = Field(default=None, description="Promedio del curso en superestructura (0-100)")
    avance_micro: float | None = Field(default=None, description="Promedio del curso en microestructura (0-100)")
    destacados: list[Destacado]


class Alerta(BaseModel):
    id: int
    estudiante_id: int
    estudiante: str
    curso: str
    motivo: str
    atendida: bool
    nota_profesor: str | None
    creada_en: datetime
    atendida_en: datetime | None
    aviso: str = AVISO


class AtenderAlerta(BaseModel):
    nota_profesor: str | None = Field(default=None, max_length=1000)


class Ajuste(BaseModel):
    clave: str
    descripcion: str
    valor: Any
    propio_del_curso: bool = False


class NuevoValor(BaseModel):
    valor: Any
