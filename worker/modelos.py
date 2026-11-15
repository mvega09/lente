"""Formatos fijos que debe devolver el modelo (salida estructurada de Ollama).

Ollama recibe el JSON Schema de cada clase y Pydantic valida la respuesta.
Si el modelo no cumple el formato, la tarea se reporta como error y se reintenta.
"""

from typing import Literal

from pydantic import BaseModel, Field


class RevisionIdea(BaseModel):
    """RNF-04: veredicto, elementos faltantes, justificación y cita del texto."""

    veredicto: Literal["coincide", "coincide_en_parte", "por_mejorar"]
    faltantes: str = Field(description="Elementos clave que no mencionó el estudiante; vacío si no falta nada")
    explicacion: str = Field(description="Una o dos frases para el estudiante, adecuadas a su nivel escolar")
    cita: str = Field(description="Fragmento copiado TEXTUALMENTE de la noticia que respalda la explicación")


class Animo(BaseModel):
    animo: Literal["motivacion_alta", "neutral", "requiere_apoyo"]


class PreguntaIA(BaseModel):
    pregunta: str
    opciones: list[str] = Field(min_length=2, max_length=6)
    correcta: int = Field(ge=1, le=6, description="Número de la opción correcta, empezando en 1")
    dificultad: int = Field(ge=1, le=3)


class PalabraIA(BaseModel):
    palabra: str = Field(description="Copiada TEXTUALMENTE de la noticia")
    tipo: Literal["adjetivo", "verbo", "expresion"]
    explicacion: str


class PreparacionTexto(BaseModel):
    """RF-09: lo que la IA propone y el profesor revisa antes de aprobar."""

    idea_principal: str
    elementos_clave: list[str] = Field(min_length=1, max_length=6)
    consejo_macro: str
    consejo_super: str
    consejo_micro: str
    preguntas: list[PreguntaIA] = Field(min_length=1, max_length=6)
    palabras_cargadas: list[PalabraIA] = Field(max_length=15)
