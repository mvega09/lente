from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.schemas.textos import TipoPalabra


class ActividadNueva(BaseModel):
    estudiante_id: int
    texto_id: int


class PreguntaActividad(BaseModel):
    """Pregunta tal como la ve el estudiante: sin la respuesta correcta."""

    id: int
    orden: int
    pregunta: str
    opciones: list[str]
    dificultad: int


class ActividadVista(BaseModel):
    id: int
    estudiante_id: int
    estudiante: str
    texto_id: int
    titulo: str
    cuerpo: str | None
    fuente: str | None
    numero: int
    estado: str
    paso: str
    grado: int | None
    nivel_escolar: str
    instruccion: str = Field(description="Instrucción adaptada al grado (RF-19)")
    preguntas: list[PreguntaActividad] = Field(default=[], description="Solo en el paso de superestructura")
    iniciada_en: datetime


# ---------------------------------------------------------------- respuestas (RNF-03)

class _Envio(BaseModel):
    codigo_envio: UUID = Field(description="Lo genera el navegador; reenviar el mismo código no duplica")


class RespuestaMacro(_Envio):
    texto: str = Field(min_length=1, max_length=2000)
    enviada_en: datetime = Field(description="Hora del dispositivo al responder")


class EstadoMacro(BaseModel):
    """Mientras estado_ia sea 'pendiente' o 'procesando', el estudiante ve 'analizando'."""

    estado_ia: str
    analizando: bool
    mensaje: str | None = Field(default=None, description="Aviso si tarda más de lo normal o si la IA falló")
    veredicto: str | None = None
    faltantes: str | None = None
    explicacion: str | None = None
    cita: str | None = None
    idea_principal: str | None = Field(default=None, description="Solo se revela después de la revisión (RF-10)")


class RespuestaPregunta(_Envio):
    pregunta_id: int
    opcion_elegida: int = Field(ge=1, le=6)


class RespuestaSuper(BaseModel):
    respuestas: list[RespuestaPregunta] = Field(min_length=1)
    enviada_en: datetime


class ResultadoPregunta(BaseModel):
    pregunta_id: int
    es_correcta: bool
    correcta: int
    opcion_correcta: str


class EstadoSuper(BaseModel):
    paso: str
    resultados: list[ResultadoPregunta]
    faltan: int = Field(description="Preguntas que aún no ha respondido")
    consejo: str | None


class Marca(_Envio):
    texto: str = Field(min_length=1, max_length=200)
    inicio: int = Field(ge=0)
    fin: int = Field(gt=0)
    tipo_palabra: TipoPalabra | None = None

    @model_validator(mode="after")
    def _rango(self):
        if self.fin <= self.inicio:
            raise ValueError("'fin' debe ser mayor que 'inicio'")
        return self


class RespuestaMicro(BaseModel):
    marcas: list[Marca] = Field(min_length=1, max_length=60)
    enviada_en: datetime


class Recibido(BaseModel):
    recibidas: int
    paso: str


# ---------------------------------------------------------------- resultado (RF-16)

class NivelResultado(BaseModel):
    resultado: float = Field(description="0 a 1")
    logrado: bool


class ResultadoMacro(NivelResultado):
    tu_respuesta: str
    veredicto: str | None
    faltantes: str | None
    explicacion: str | None
    cita: str | None
    idea_principal: str | None


class DetallePregunta(BaseModel):
    orden: int
    pregunta: str
    tu_opcion: str
    opcion_correcta: str
    es_correcta: bool


class ResultadoSuper(NivelResultado):
    preguntas: list[DetallePregunta]
    explicacion: str | None


class PalabraResultado(BaseModel):
    palabra: str
    tipo: str | None = None
    explicacion: str | None = None


class ResultadoMicro(NivelResultado):
    aciertos: list[PalabraResultado]
    omisiones: list[PalabraResultado]
    neutras_marcadas: list[PalabraResultado]
    explicacion: str | None


class Logro(BaseModel):
    nombre: str
    descripcion: str


class ResultadoActividad(BaseModel):
    actividad_id: int
    titulo: str
    puntos_ganados: int
    macro: ResultadoMacro
    super: ResultadoSuper
    micro: ResultadoMicro
    recomendaciones: list[str]
    logros_nuevos: list[Logro]
    instruccion: str


EstadoActividad = Literal["en_curso", "terminada", "abandonada"]
