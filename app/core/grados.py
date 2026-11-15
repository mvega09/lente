"""RF-19: adaptación del lenguaje y de las instrucciones según el nivel escolar.

La funcionalidad es la misma para todos; solo cambia cómo se explica.
El nivel sale de lente.nivel_escolar(grado): primaria (3°-5°), secundaria
(6°-9°) o media (10°-11°, y también "sin grado").
"""

INSTRUCCIONES: dict[str, dict[str, str]] = {
    "primaria": {
        "macro": "Lee la noticia con calma. ¿De qué trata? Escríbelo con tus palabras en una o dos frases.",
        "super": "Ahora mira cómo está armada la noticia. Elige la respuesta que te parezca correcta.",
        "micro": "Busca palabras que muestren emociones o que quieran convencerte. Tócalas para marcarlas.",
        "resultado": "¡Terminaste! Mira lo que hiciste muy bien y lo que puedes mejorar.",
    },
    "secundaria": {
        "macro": "Lee el texto y escribe cuál es su idea principal: el tema central que el autor quiere comunicar.",
        "super": "Analiza cómo se organiza la información: qué aparece primero, qué se destaca y qué se omite.",
        "micro": "Marca los adjetivos, verbos y expresiones con carga emocional que buscan influir en el lector.",
        "resultado": "Revisa tu resultado en cada nivel y las recomendaciones para seguir mejorando.",
    },
    "media": {
        "macro": "Identifica la macroestructura: formula la idea principal del texto de forma precisa.",
        "super": "Examina la superestructura: el orden de la información, la jerarquía y las posibles omisiones.",
        "micro": "Analiza la microestructura: señala las elecciones léxicas (adjetivos, verbos, expresiones) "
                 "que cargan valorativamente el texto.",
        "resultado": "Contrasta tu interpretación con el análisis del sistema en los tres niveles del discurso.",
    },
}


def instruccion(nivel_escolar: str | None, paso: str) -> str:
    return INSTRUCCIONES.get(nivel_escolar or "media", INSTRUCCIONES["media"]).get(paso, "")
