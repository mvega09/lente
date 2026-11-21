"""Formatos fijos que debe devolver el modelo (salida estructurada de Ollama).

Ollama recibe el JSON Schema de cada clase y Pydantic valida la respuesta.
Si el modelo no cumple el formato, la tarea se reporta como error y se reintenta.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator

LIMITE_FALTANTES = 80


class RevisionIdea(BaseModel):
    """RNF-04: veredicto, elementos faltantes, justificación y cita del texto.

    Los límites de longitud (que Ollama aplica como gramática) mantienen la
    respuesta corta: en CPU el tiempo lo domina la cantidad de tokens que se
    generan, y el estudiante está esperando (RNF-01).
    """

    veredicto: Literal["coincide", "coincide_en_parte", "por_mejorar"]
    faltantes: str = Field(max_length=LIMITE_FALTANTES, description="Elementos clave que faltaron, separados por comas, "
                                                     "máximo 8 palabras; vacío si no falta nada")
    explicacion: str = Field(max_length=120, description="Una frase corta dirigida al estudiante en segunda persona (tú)")
    cita: str = Field(max_length=90, description="Fragmento corto copiado TEXTUALMENTE de la noticia")

    @field_validator("faltantes")
    @classmethod
    def _sin_cortes(cls, v: str) -> str:
        """La gramática corta la salida en el límite, a veces a mitad de palabra:
        en ese caso se conserva solo hasta el último elemento completo."""
        v = v.strip()
        if len(v) >= LIMITE_FALTANTES - 5 and "," in v:
            v = v[: v.rfind(",")].strip()
        return v


class Animo(BaseModel):
    animo: Literal["motivacion_alta", "neutral", "requiere_apoyo"]


# Los límites de longitud los aplica Ollama como gramática: en CPU el tiempo depende de
# cuántos tokens se generan, así que respuestas cortas = preparación más rápida.
Opcion = Annotated[str, Field(min_length=1, max_length=100)]
Elemento = Annotated[str, Field(min_length=1, max_length=70)]


class PreguntaIA(BaseModel):
    pregunta: str = Field(max_length=180)
    opciones: list[Opcion] = Field(min_length=3, max_length=4)
    correcta: int = Field(ge=1, le=4, description="Número de la opción correcta, empezando en 1")
    dificultad: int = Field(ge=1, le=3)


class PalabraIA(BaseModel):
    palabra: str = Field(max_length=60, description="Copiada TEXTUALMENTE de la noticia")
    tipo: Literal["adjetivo", "verbo", "expresion"]
    explicacion: str = Field(max_length=110)


class PreparacionTexto(BaseModel):
    """RF-09: lo que la IA propone y el profesor revisa antes de aprobar."""

    idea_principal: str = Field(max_length=320)
    elementos_clave: list[Elemento] = Field(min_length=2, max_length=5)
    consejo_macro: str = Field(max_length=200)
    consejo_super: str = Field(max_length=200)
    consejo_micro: str = Field(max_length=200)
    preguntas: list[PreguntaIA] = Field(min_length=3, max_length=4)
    palabras_cargadas: list[PalabraIA] = Field(min_length=1, max_length=8)
