"""Instrucciones para el modelo, basadas en el análisis crítico del discurso de Van Dijk.

Orden pensado para la caché de prefijo de Ollama: primero lo que es igual
para todos los estudiantes (noticia, idea esperada) y al final lo que cambia.
"""

SISTEMA = (
    "Eres un asistente pedagógico de alfabetización mediática para estudiantes de colegio en Colombia. "
    "Aplicas el análisis crítico del discurso de Teun van Dijk: macroestructura (idea principal), "
    "superestructura (organización del texto) y microestructura (palabras y expresiones con carga). "
    "Respondes siempre en español, con frases cortas y claras, y SOLO con el JSON pedido."
)


def sistema(instrucciones: str | None = None) -> str:
    """Mensaje de sistema: base fija + instrucciones editables desde la tabla ajustes (RNF-08)."""
    return f"{SISTEMA}\n\n{instrucciones.strip()}" if instrucciones and instrucciones.strip() else SISTEMA


def mensajes_revisar_idea(texto: str, idea_principal: str, elementos_clave: list[str],
                          nivel_escolar: str | None, respuesta: str,
                          instrucciones: str | None = None) -> list[dict]:
    claves = "\n".join(f"- {e}" for e in elementos_clave) or "- (no definidos)"
    return [
        {"role": "system", "content": sistema(instrucciones)},
        {"role": "user", "content": (
            f"NOTICIA:\n{texto}\n\n"
            f"IDEA PRINCIPAL ESPERADA (aprobada por el profesor):\n{idea_principal}\n\n"
            f"ELEMENTOS CLAVE QUE DEBE MENCIONAR:\n{claves}\n\n"
            "Compara la idea principal escrita por el estudiante con la esperada.\n"
            "- veredicto: 'coincide', 'coincide_en_parte' o 'por_mejorar'.\n"
            "- faltantes: elementos clave que no mencionó (vacío si no falta nada).\n"
            f"- explicacion: una o dos frases para un estudiante de nivel {nivel_escolar or 'escolar'}.\n"
            "- cita: un fragmento corto copiado EXACTAMENTE de la noticia que respalde tu explicación.\n\n"
            f"IDEA PRINCIPAL DEL ESTUDIANTE:\n{respuesta}"
        )},
    ]


def mensajes_preparar_texto(titulo: str, cuerpo: str, instrucciones: str | None = None) -> list[dict]:
    return [
        {"role": "system", "content": sistema(instrucciones)},
        {"role": "user", "content": (
            f"TÍTULO: {titulo}\n\nNOTICIA:\n{cuerpo}\n\n"
            "Prepara el material para que el profesor lo revise:\n"
            "- idea_principal: la macroestructura en una o dos frases.\n"
            "- elementos_clave: de 2 a 5 elementos que una buena idea principal debe mencionar.\n"
            "- consejo_macro: cómo encontrar la idea principal de este texto.\n"
            "- consejo_super: cómo está organizado el texto y qué información omite.\n"
            "- consejo_micro: cómo reconocer las palabras con carga emocional de este texto.\n"
            "- preguntas: de 3 a 5 preguntas de opción múltiple sobre la superestructura "
            "(titular, entradilla, fuentes, orden de la información), con dificultad 1 a 3.\n"
            "- palabras_cargadas: adjetivos, verbos o expresiones con carga emocional o valorativa, "
            "copiados EXACTAMENTE como aparecen en la noticia, con una explicación breve."
        )},
    ]


def mensajes_analizar_animo(respuesta_abierta: str | None, macro, super_, micro, segundos) -> list[dict]:
    return [
        {"role": "system", "content": SISTEMA},
        {"role": "user", "content": (
            "Clasifica el ánimo del estudiante al terminar la actividad como "
            "'motivacion_alta', 'neutral' o 'requiere_apoyo'.\n"
            f"Resultados (0 a 1): macro={macro}, super={super_}, micro={micro}. "
            f"Tiempo: {segundos} segundos.\n"
            f"Lo que escribió: {respuesta_abierta or '(nada)'}"
        )},
    ]
