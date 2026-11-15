from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

TipoTexto = Literal["noticia", "publicacion", "video", "aportado_en_clase"]
EstadoTexto = Literal["borrador", "preparando", "en_revision", "aprobado", "archivado"]
TipoPalabra = Literal["adjetivo", "verbo", "expresion"]
Nivel = Literal["macro", "super", "micro"]


# ---------------------------------------------------------------- textos

class TextoNuevo(BaseModel):
    tipo: TipoTexto = "noticia"
    titulo: str = Field(min_length=1, max_length=250)
    cuerpo: str | None = Field(default=None, description="Texto completo. No se puede modificar después.")
    enlace: str | None = None
    fuente: str | None = Field(default=None, max_length=120)
    nota: str | None = Field(default=None, max_length=300)
    preparar_con_ia: bool = Field(default=True, description="Si hay cuerpo, la IA prepara el paquete en segundo plano")

    @model_validator(mode="after")
    def _cuerpo_o_enlace(self):
        if not (self.cuerpo and self.cuerpo.strip()) and not self.enlace:
            raise ValueError("El texto necesita el cuerpo o un enlace")
        return self


class TextoCambios(BaseModel):
    titulo: str | None = Field(default=None, min_length=1, max_length=250)
    enlace: str | None = None
    fuente: str | None = Field(default=None, max_length=120)
    nota: str | None = Field(default=None, max_length=300)


class PaqueteCambios(BaseModel):
    """Lo que preparó la IA y el profesor revisa (RF-09)."""

    idea_principal: str | None = Field(default=None, min_length=1)
    elementos_clave: list[str] | None = Field(default=None, max_length=10)
    consejo_macro: str | None = None
    consejo_super: str | None = None
    consejo_micro: str | None = None


class TextoResumen(BaseModel):
    id: int
    tipo: str
    titulo: str
    fuente: str | None
    nota: str | None
    estado: str
    preparado_por_ia: bool
    aprobado_en: datetime | None
    creado_en: datetime


class Pregunta(BaseModel):
    id: int
    orden: int
    pregunta: str
    opciones: list[str]
    correcta: int
    dificultad: int


class Palabra(BaseModel):
    id: int
    palabra: str
    tipo: str
    inicio: int
    fin: int
    explicacion: str | None


class TextoDetalle(TextoResumen):
    cuerpo: str | None
    enlace: str | None
    idea_principal: str | None
    elementos_clave: list[str]
    consejo_macro: str | None
    consejo_super: str | None
    consejo_micro: str | None
    preguntas: list[Pregunta] = []
    palabras: list[Palabra] = []


# ---------------------------------------------------------------- preguntas y palabras

class PreguntaNueva(BaseModel):
    pregunta: str = Field(min_length=1, max_length=300)
    opciones: list[str] = Field(min_length=2, max_length=6)
    correcta: int = Field(ge=1, le=6, description="Número de la opción correcta, desde 1")
    dificultad: int = Field(default=1, ge=1, le=3)
    orden: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _correcta_existe(self):
        if self.correcta > len(self.opciones):
            raise ValueError("La opción correcta no está entre las opciones")
        return self


class PreguntaCambios(BaseModel):
    pregunta: str | None = Field(default=None, min_length=1, max_length=300)
    opciones: list[str] | None = Field(default=None, min_length=2, max_length=6)
    correcta: int | None = Field(default=None, ge=1, le=6)
    dificultad: int | None = Field(default=None, ge=1, le=3)


class PalabraNueva(BaseModel):
    palabra: str = Field(min_length=1, max_length=120, description="Tal como aparece en el texto")
    tipo: TipoPalabra
    inicio: int | None = Field(default=None, ge=0, description="Posición en el texto; vacío = primera aparición libre")
    explicacion: str | None = None


# ---------------------------------------------------------------- resaltados

class ResaltadoNuevo(BaseModel):
    """RF-13 / RF-14: se marca un fragmento por posición; el texto original no cambia."""

    nivel: Nivel
    inicio: int = Field(ge=0)
    fin: int = Field(gt=0)
    explicacion: str | None = None
    es_idea_principal: bool = False

    @model_validator(mode="after")
    def _rango(self):
        if self.fin <= self.inicio:
            raise ValueError("'fin' debe ser mayor que 'inicio'")
        return self


class Resaltado(BaseModel):
    id: int
    nivel: str
    inicio: int
    fin: int
    fragmento: str
    explicacion: str | None
    es_idea_principal: bool
    creado_en: datetime


# ---------------------------------------------------------------- textos en cursos

class Activacion(BaseModel):
    texto_id: int


class TextoEnCurso(BaseModel):
    id: int
    titulo: str
    tipo: str
    fuente: str | None
    activo: bool
    activado_en: datetime
