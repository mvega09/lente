"""RF-21: cómo se nombra el ánimo frente al profesor.

Solo apoyo pedagógico. Ningún texto puede sugerir un diagnóstico clínico o
psicológico, y el resultado no cambia puntos, nivel ni calificación.
"""

AVISO = "Solo apoyo pedagógico. No es un diagnóstico y no afecta puntos ni calificación."

ETIQUETAS = {
    "motivacion_alta": "Motivación alta",
    "neutral": "Neutral",
    "requiere_apoyo": "Podría necesitar acompañamiento",
}

# Palabras que nunca deben aparecer en mensajes de ánimo (criterio de aceptación RF-21)
PALABRAS_PROHIBIDAS = ("diagnóstico", "depresión", "ansiedad", "trastorno", "patología", "síntoma", "terapia")


def etiqueta(animo: str | None) -> str | None:
    return ETIQUETAS.get(animo) if animo else None
