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
            "- faltantes: los elementos clave que no mencionó, separados por comas, máximo 8 palabras "
            "en total (vacío si no falta nada).\n"
            "- explicacion: UNA frase corta (máximo 18 palabras) dirigida AL ESTUDIANTE, en segunda "
            "persona (tú), por ejemplo «Mencionas…, pero te faltó…». Nunca escribas «el estudiante». "
            f"Lenguaje adecuado para nivel {nivel_escolar or 'escolar'}.\n"
            "- cita: un fragmento corto (máximo 12 palabras) copiado EXACTAMENTE de la noticia.\n"
            "Sé breve: el estudiante está esperando.\n\n"
            f"IDEA PRINCIPAL DEL ESTUDIANTE:\n{respuesta}"
        )},
    ]


def mensajes_preparar_texto(titulo: str, cuerpo: str, instrucciones: str | None = None) -> list[dict]:
    return [
        {"role": "system", "content": sistema(instrucciones)},
        {"role": "user", "content": (
            f"TÍTULO: {titulo}\n\nNOTICIA:\n{cuerpo}\n\n"
            "Prepara el material para que el profesor lo revise. Sé preciso y breve.\n\n"
            "1. idea_principal: la macroestructura en una o dos frases (máximo 40 palabras): qué pasó, "
            "quiénes y el conflicto o postura central.\n"
            "2. elementos_clave: de 3 a 5 elementos (máximo 8 palabras cada uno) que una buena idea "
            "principal debe mencionar.\n"
            "3. consejo_macro, consejo_super, consejo_micro: una frase cada uno (máximo 30 palabras), "
            "dirigida al estudiante en segunda persona (tú).\n"
            "4. preguntas: 3 o 4 preguntas sobre la SUPERESTRUCTURA (qué aparece primero, qué fuente tiene "
            "más espacio, qué se omite, qué queda al final, qué destaca el titular). 3 opciones cada una y "
            "una sola correcta según el texto. dificultad: 1 literal, 2 inferencia, 3 crítica.\n"
            "5. palabras_cargadas: de 3 a 8 palabras o expresiones con CARGA VALORATIVA O EMOCIONAL: las que "
            "juzgan, exageran, alarman o buscan provocar una emoción en vez de solo informar. Prueba: si una "
            "palabra neutra diría lo mismo sin juzgar, la original tiene carga (invadieron frente a llegaron, "
            "escándalo frente a caso, confesó frente a dijo, desolador, estalla, falso).\n"
            "   - NO incluyas palabras que solo nombran hechos, objetos, lugares, personas, cargos o el clima "
            "(lluvia, cuerpo, vía, parque, muerte, universidad, congresista), ni nombres propios, cifras o fechas.\n"
            "   - Revisa TODO el texto, también las citas, y busca adjetivos valorativos y verbos con carga; "
            "inclúyelos si existen. Si el texto es informativo y tiene poca carga, propón menos: es mejor 3 "
            "correctas que 8 dudosas.\n"
            "   - Prefiere UNA palabra. Usa una expresión de 2 a 5 palabras solo si la carga está en la frase completa.\n"
            "   - palabra: copiada EXACTAMENTE como aparece en la noticia (mismas letras, tildes y mayúsculas).\n"
            "   - tipo: adjetivo (califica a un sustantivo: delicado, falso, indignados), verbo (forma verbal: "
            "estalla, confesó, invadieron) o expresion (sustantivo con carga: escándalo, falsificación, caos; "
            "o una frase de varias palabras).\n"
            "   - explicacion: máximo 15 palabras sobre por qué carga el texto."
        )},
    ]


PASOS = {"macro": "la idea principal", "super": "las preguntas de organización",
         "micro": "las palabras cargadas", "resultado": "el resultado"}


def mensajes_analizar_animo(respuesta_abierta: str | None, macro, super_, micro, segundos,
                            abandonada: bool = False, paso: str | None = None) -> list[dict]:
    if abandonada:
        # RF-21: el abandono anticipado es una de las señales de conducta
        situacion = (f"El estudiante ABANDONÓ la actividad sin terminarla, cuando iba en "
                     f"{PASOS.get(paso or '', 'un paso intermedio')}.\n")
    else:
        situacion = "El estudiante terminó la actividad.\n"
    return [
        {"role": "system", "content": SISTEMA},
        {"role": "user", "content": (
            "Clasifica el ánimo del estudiante como 'motivacion_alta', 'neutral' o 'requiere_apoyo'.\n"
            + situacion +
            f"Resultados (0 a 1; vacío = no lo hizo): macro={macro}, super={super_}, micro={micro}. "
            f"Tiempo: {segundos} segundos.\n"
            f"Lo que escribió: {respuesta_abierta or '(nada)'}"
        )},
    ]
