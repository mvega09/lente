"""Actividad del estudiante: macro → super → micro → resultado (RF-10 a RF-17).

Modo aula: el profesor abre la actividad para un estudiante desde su sesión
y el estudiante responde en ese dispositivo (el estudiante no inicia sesión).

Reglas que aplica este módulo (la calificación la hace la base de datos):
- Secuencia obligatoria (RF-15): cada paso exige que el anterior esté hecho.
- La idea principal aprobada no se muestra antes del intento (RF-10).
- Las preguntas se filtran por la dificultad que admite el grado (RF-19).
- Cada respuesta trae un `codigo_envio`; reenviarla no la duplica (RNF-03).
"""

import unicodedata
from datetime import datetime
from uuid import UUID

from psycopg import AsyncConnection

from app.core.db import ejecutar, uno, varios
from app.core.errores import Conflicto, DatoInvalido, NoEncontrado
from app.core.grados import instruccion

_DEL_PROFESOR = """
  JOIN lente.estudiantes s ON s.id = a.estudiante_id
  JOIN lente.cursos c ON c.id = s.curso_id
"""

SQL_ACTIVIDAD = """
SELECT a.id, a.estudiante_id, s.nombre AS estudiante, s.curso_id, a.texto_id, a.numero, a.estado, a.paso,
       a.grado, lente.nivel_escolar(a.grado) AS nivel_escolar,
       lente.dificultad_maxima(a.grado) AS dificultad_maxima,
       a.resultado_macro, a.resultado_super, a.resultado_micro, a.puntos_ganados,
       a.iniciada_en, a.terminada_en, t.titulo, t.cuerpo, t.fuente
  FROM lente.actividades a
""" + _DEL_PROFESOR + """
  JOIN lente.textos t ON t.id = a.texto_id
 WHERE a.id = %(actividad)s AND c.profesor_id = %(profesor)s
"""

SQL_EN_CURSO = """
SELECT a.id FROM lente.actividades a
""" + _DEL_PROFESOR + """
 WHERE a.estudiante_id = %(estudiante)s AND a.texto_id = %(texto)s AND a.estado = 'en_curso'
   AND c.profesor_id = %(profesor)s
 ORDER BY a.numero DESC
 LIMIT 1
"""

# El trigger actividad_abrir verifica que el texto esté activo en el curso del estudiante
SQL_ABRIR = """
INSERT INTO lente.actividades (estudiante_id, texto_id)
SELECT s.id, %(texto)s
  FROM lente.estudiantes s JOIN lente.cursos c ON c.id = s.curso_id
 WHERE s.id = %(estudiante)s AND c.profesor_id = %(profesor)s
RETURNING id
"""

SQL_AVANZAR = """
UPDATE lente.actividades SET paso = %(a)s
 WHERE id = %(actividad)s AND paso = %(de)s AND estado = 'en_curso'
"""

SQL_CODIGOS_EXISTENTES = """
SELECT codigo_envio FROM lente.respuestas
 WHERE actividad_id = %(actividad)s AND codigo_envio = ANY(%(codigos)s::uuid[])
"""

SQL_PREGUNTAS_TEXTO = """
SELECT id, orden, pregunta, opciones, correcta, dificultad
  FROM lente.preguntas
 WHERE texto_id = %(texto)s
 ORDER BY orden
"""

# ON CONFLICT DO NOTHING sin destino: cubre el código de envío repetido y las
# reglas "una idea principal / una respuesta por pregunta / una marca por palabra".
SQL_INSERTAR_MACRO = """
INSERT INTO lente.respuestas (actividad_id, nivel, codigo_envio, texto, enviada_en)
VALUES (%(actividad)s, 'macro', %(codigo)s, %(texto)s, %(enviada)s)
ON CONFLICT DO NOTHING
"""

SQL_INSERTAR_SUPER = """
INSERT INTO lente.respuestas (actividad_id, nivel, codigo_envio, pregunta_id, opcion_elegida, enviada_en)
VALUES (%(actividad)s, 'super', %(codigo)s, %(pregunta)s, %(opcion)s, %(enviada)s)
ON CONFLICT DO NOTHING
"""

SQL_INSERTAR_MICRO = """
INSERT INTO lente.respuestas (actividad_id, nivel, codigo_envio, texto, inicio, fin, tipo_palabra, enviada_en)
VALUES (%(actividad)s, 'micro', %(codigo)s, %(texto)s, %(inicio)s, %(fin)s, %(tipo)s, %(enviada)s)
ON CONFLICT DO NOTHING
"""

SQL_BORRAR_MARCA = """
DELETE FROM lente.respuestas r USING lente.actividades a
 WHERE r.actividad_id = a.id AND a.id = %(actividad)s AND a.estado = 'en_curso' AND a.paso = 'micro'
   AND r.nivel = 'micro' AND r.inicio = %(inicio)s
"""

SQL_MACRO = """
SELECT r.texto, r.estado_ia, r.veredicto_ia, r.faltantes_ia, r.explicacion_ia, r.cita_ia, r.cita_valida,
       t.idea_principal,
       extract(epoch FROM now() - r.recibida_en)::int AS segundos_esperando,
       coalesce((lente.ajuste('ia_tiempo_maximo_seg', s.curso_id))::int, 15) AS tiempo_maximo
  FROM lente.respuestas r
  JOIN lente.actividades a ON a.id = r.actividad_id
  JOIN lente.textos t ON t.id = a.texto_id
""" + _DEL_PROFESOR + """
 WHERE r.actividad_id = %(actividad)s AND r.nivel = 'macro' AND c.profesor_id = %(profesor)s
"""

SQL_SUPER = """
SELECT q.id AS pregunta_id, q.orden, q.pregunta, q.opciones, q.correcta, r.opcion_elegida, r.es_correcta
  FROM lente.respuestas r JOIN lente.preguntas q ON q.id = r.pregunta_id
 WHERE r.actividad_id = %(actividad)s AND r.nivel = 'super'
 ORDER BY q.orden
"""

SQL_MICRO = """
SELECT r.texto, r.inicio, r.fin, r.es_correcta
  FROM lente.respuestas r
 WHERE r.actividad_id = %(actividad)s AND r.nivel = 'micro'
 ORDER BY r.inicio
"""

SQL_PALABRAS_TEXTO = """
SELECT palabra, tipo, inicio, fin, explicacion
  FROM lente.palabras_cargadas
 WHERE texto_id = %(texto)s
 ORDER BY inicio
"""

SQL_CONSEJOS = """
SELECT idea_principal, consejo_macro, consejo_super, consejo_micro
  FROM lente.textos
 WHERE id = %(texto)s
"""

SQL_TERMINAR = "SELECT * FROM lente.terminar_actividad(%(actividad)s)"

SQL_MINIMO_LOGRADO = """
SELECT coalesce((lente.ajuste('minimo_para_logrado', %(curso)s::bigint))::numeric, 0.6) AS minimo
"""

SQL_LOGROS_NUEVOS = """
SELECT l.nombre, l.descripcion
  FROM lente.logros_ganados g JOIN lente.logros l ON l.id = g.logro_id
 WHERE g.estudiante_id = %(estudiante)s AND g.ganado_en >= %(desde)s
 ORDER BY g.ganado_en
"""


# ================================================================ apoyo

async def _actividad(conn: AsyncConnection, profesor_id: int, actividad_id: int) -> dict:
    act = await uno(conn, SQL_ACTIVIDAD, {"actividad": actividad_id, "profesor": profesor_id})
    if act is None:
        raise NoEncontrado("La actividad")
    return act


def _exigir_paso(act: dict, paso: str) -> None:
    if act["estado"] != "en_curso":
        raise Conflicto("La actividad ya terminó")
    if act["paso"] != paso:
        orden = ["macro", "super", "micro", "resultado"]
        if orden.index(act["paso"]) < orden.index(paso):
            raise Conflicto(f"Primero hay que terminar el paso '{act['paso']}' (RF-15)")
        raise Conflicto(f"El paso '{paso}' ya se respondió")


async def _codigos_existentes(conn: AsyncConnection, actividad_id: int, codigos: list[UUID]) -> set[UUID]:
    filas = await varios(conn, SQL_CODIGOS_EXISTENTES, {"actividad": actividad_id, "codigos": codigos})
    return {f["codigo_envio"] for f in filas}


def preguntas_para_grado(preguntas: list[dict], dificultad_maxima: int) -> list[dict]:
    """RF-19: solo las preguntas que admite el grado; si ninguna aplica, se muestran todas."""
    filtradas = [q for q in preguntas if q["dificultad"] <= dificultad_maxima]
    return filtradas or preguntas


async def _preguntas(conn: AsyncConnection, act: dict) -> list[dict]:
    todas = await varios(conn, SQL_PREGUNTAS_TEXTO, {"texto": act["texto_id"]})
    return preguntas_para_grado(todas, act["dificultad_maxima"])


def _normalizar(t: str) -> str:
    t = unicodedata.normalize("NFD", t.lower())
    t = "".join(ch for ch in t if unicodedata.category(ch) != "Mn")
    return "".join(ch for ch in t if ch.isalnum() or ch.isspace()).strip()


def _vista(act: dict, preguntas: list[dict] | None = None) -> dict:
    return {**act, "instruccion": instruccion(act["nivel_escolar"], act["paso"]),
            "preguntas": preguntas or []}


# ================================================================ flujo

async def abrir(conn: AsyncConnection, profesor_id: int, estudiante_id: int, texto_id: int) -> dict:
    """Abre la actividad o retoma la que quedó en curso (útil si se cayó la conexión)."""
    p = {"estudiante": estudiante_id, "texto": texto_id, "profesor": profesor_id}
    fila = await uno(conn, SQL_EN_CURSO, p) or await uno(conn, SQL_ABRIR, p)
    if fila is None:
        raise NoEncontrado("El estudiante")
    return await ver(conn, profesor_id, fila["id"])


async def ver(conn: AsyncConnection, profesor_id: int, actividad_id: int) -> dict:
    act = await _actividad(conn, profesor_id, actividad_id)
    preguntas = await _preguntas(conn, act) if act["paso"] == "super" else None
    return _vista(act, preguntas)


async def responder_macro(conn: AsyncConnection, profesor_id: int, actividad_id: int,
                          texto: str, codigo: UUID, enviada: datetime) -> dict:
    act = await _actividad(conn, profesor_id, actividad_id)
    if not await _codigos_existentes(conn, actividad_id, [codigo]):
        _exigir_paso(act, "macro")
        await ejecutar(conn, SQL_INSERTAR_MACRO, {"actividad": actividad_id, "codigo": codigo,
                                                  "texto": texto.strip(), "enviada": enviada})
        await ejecutar(conn, SQL_AVANZAR, {"actividad": actividad_id, "de": "macro", "a": "super"})
    return await estado_macro(conn, profesor_id, actividad_id)


async def estado_macro(conn: AsyncConnection, profesor_id: int, actividad_id: int) -> dict:
    r = await uno(conn, SQL_MACRO, {"actividad": actividad_id, "profesor": profesor_id})
    if r is None:
        raise NoEncontrado("La idea principal de esta actividad")
    analizando = r["estado_ia"] in ("pendiente", "procesando")
    salida = {"estado_ia": r["estado_ia"], "analizando": analizando}
    if analizando and (r.get("segundos_esperando") or 0) > (r.get("tiempo_maximo") or 15):
        # RNF-01: si se pasa del tiempo máximo se informa al estudiante y la cola reintenta
        salida["mensaje"] = "La revisión está tardando más de lo normal. Seguimos intentando; no se perdió tu respuesta."
    if r["estado_ia"] == "fallida":
        salida["mensaje"] = "No pudimos revisar tu idea con la IA. Compárala con la idea principal del texto."
    if not analizando:
        # Si la cita no existe en el texto, la base ya dejó explicación y cita vacías (RNF-04)
        salida |= {"veredicto": r["veredicto_ia"], "faltantes": r["faltantes_ia"],
                   "explicacion": r["explicacion_ia"], "cita": r["cita_ia"],
                   "idea_principal": r["idea_principal"]}
    return salida


async def responder_super(conn: AsyncConnection, profesor_id: int, actividad_id: int,
                          respuestas: list[dict], enviada: datetime) -> dict:
    act = await _actividad(conn, profesor_id, actividad_id)
    existentes = await _codigos_existentes(conn, actividad_id, [r["codigo_envio"] for r in respuestas])
    nuevas = [r for r in respuestas if r["codigo_envio"] not in existentes]
    preguntas = await _preguntas(conn, act)
    if nuevas:
        _exigir_paso(act, "super")
        validas = {q["id"]: q for q in preguntas}
        for r in nuevas:
            q = validas.get(r["pregunta_id"])
            if q is None:
                raise DatoInvalido(f"La pregunta {r['pregunta_id']} no es parte de esta actividad")
            if r["opcion_elegida"] > len(q["opciones"]):
                raise DatoInvalido(f"La opción {r['opcion_elegida']} no existe en la pregunta {q['orden']}")
        for r in nuevas:
            await ejecutar(conn, SQL_INSERTAR_SUPER, {"actividad": actividad_id, "codigo": r["codigo_envio"],
                                                      "pregunta": r["pregunta_id"],
                                                      "opcion": r["opcion_elegida"], "enviada": enviada})
    hechas = await varios(conn, SQL_SUPER, {"actividad": actividad_id})
    faltan = len({q["id"] for q in preguntas} - {h["pregunta_id"] for h in hechas})
    paso = act["paso"]
    if faltan == 0 and paso == "super":
        await ejecutar(conn, SQL_AVANZAR, {"actividad": actividad_id, "de": "super", "a": "micro"})
        paso = "micro"
    consejos = await uno(conn, SQL_CONSEJOS, {"texto": act["texto_id"]})
    return {
        "paso": paso,
        "faltan": faltan,
        "consejo": consejos["consejo_super"] if faltan == 0 else None,
        "resultados": [{"pregunta_id": h["pregunta_id"], "es_correcta": bool(h["es_correcta"]),
                        "correcta": h["correcta"], "opcion_correcta": h["opciones"][h["correcta"] - 1]}
                       for h in hechas],
    }


async def responder_micro(conn: AsyncConnection, profesor_id: int, actividad_id: int,
                          marcas: list[dict], enviada: datetime) -> dict:
    act = await _actividad(conn, profesor_id, actividad_id)
    existentes = await _codigos_existentes(conn, actividad_id, [m["codigo_envio"] for m in marcas])
    nuevas = [m for m in marcas if m["codigo_envio"] not in existentes]
    if nuevas:
        _exigir_paso(act, "micro")
        cuerpo = act["cuerpo"] or ""
        for m in nuevas:
            if cuerpo[m["inicio"]:m["fin"]] != m["texto"]:
                raise DatoInvalido(f"La marca «{m['texto']}» no coincide con el texto en esa posición")
        for m in nuevas:
            await ejecutar(conn, SQL_INSERTAR_MICRO, {"actividad": actividad_id, "codigo": m["codigo_envio"],
                                                      "texto": m["texto"], "inicio": m["inicio"],
                                                      "fin": m["fin"], "tipo": m.get("tipo_palabra"),
                                                      "enviada": enviada})
    total = len(await varios(conn, SQL_MICRO, {"actividad": actividad_id}))
    return {"recibidas": total, "paso": act["paso"]}


async def quitar_marca(conn: AsyncConnection, profesor_id: int, actividad_id: int, inicio: int) -> None:
    act = await _actividad(conn, profesor_id, actividad_id)
    _exigir_paso(act, "micro")
    if await ejecutar(conn, SQL_BORRAR_MARCA, {"actividad": actividad_id, "inicio": inicio}) == 0:
        raise NoEncontrado("La marca")


async def terminar(conn: AsyncConnection, profesor_id: int, actividad_id: int) -> dict:
    """"Ver mi resultado": la base calcula resultados, puntos, racha y logros (RF-17, RF-18)."""
    act = await _actividad(conn, profesor_id, actividad_id)
    if act["estado"] != "terminada":
        _exigir_paso(act, "micro")
        if not await varios(conn, SQL_MICRO, {"actividad": actividad_id}):
            raise Conflicto("Marca al menos una palabra o expresión antes de terminar")
        await uno(conn, SQL_TERMINAR, {"actividad": actividad_id})   # 409 si la IA aún revisa la macro
    return await resultado(conn, profesor_id, actividad_id)


# ================================================================ resultado (RF-16)

def analizar_micro(palabras: list[dict], marcas: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    """Aciertos, omisiones y palabras neutras marcadas por error."""
    def toca(p, m):
        return p["inicio"] < m["fin"] and m["inicio"] < p["fin"] or _normalizar(p["palabra"]) == _normalizar(m["texto"])

    correctas = [m for m in marcas if m["es_correcta"]]
    aciertos = [p for p in palabras if any(toca(p, m) for m in correctas)]
    omisiones = [p for p in palabras if p not in aciertos]
    neutras = [{"palabra": m["texto"]} for m in marcas if not m["es_correcta"]]
    return aciertos, omisiones, neutras


def recomendaciones(res: dict, minimo: float, consejos: dict, faltantes: str | None) -> list[str]:
    salida = []
    if res["macro"] < minimo:
        if faltantes:
            salida.append(f"En la idea principal te faltó: {faltantes}")
        if consejos.get("consejo_macro"):
            salida.append(consejos["consejo_macro"])
    if res["super"] < minimo and consejos.get("consejo_super"):
        salida.append(consejos["consejo_super"])
    if res["micro"] < minimo and consejos.get("consejo_micro"):
        salida.append(consejos["consejo_micro"])
    return salida or ["¡Muy bien! Lograste los tres niveles. Sigue practicando con textos nuevos."]


async def resultado(conn: AsyncConnection, profesor_id: int, actividad_id: int) -> dict:
    act = await _actividad(conn, profesor_id, actividad_id)
    if act["estado"] != "terminada":
        raise Conflicto("La actividad aún no termina")
    p = {"actividad": actividad_id}
    macro = await uno(conn, SQL_MACRO, p | {"profesor": profesor_id})
    super_ = await varios(conn, SQL_SUPER, p)
    marcas = await varios(conn, SQL_MICRO, p)
    palabras = await varios(conn, SQL_PALABRAS_TEXTO, {"texto": act["texto_id"]})
    consejos = await uno(conn, SQL_CONSEJOS, {"texto": act["texto_id"]})
    minimo = float((await uno(conn, SQL_MINIMO_LOGRADO, {"curso": act["curso_id"]}))["minimo"])
    logros = await varios(conn, SQL_LOGROS_NUEVOS, {"estudiante": act["estudiante_id"],
                                                    "desde": act["iniciada_en"]})

    res = {k: float(act[f"resultado_{k}"] or 0) for k in ("macro", "super", "micro")}
    aciertos, omisiones, neutras = analizar_micro(palabras, marcas)
    return {
        "actividad_id": actividad_id,
        "titulo": act["titulo"],
        "puntos_ganados": act["puntos_ganados"],
        "instruccion": instruccion(act["nivel_escolar"], "resultado"),
        "macro": {
            "resultado": res["macro"], "logrado": res["macro"] >= minimo,
            "tu_respuesta": macro["texto"], "veredicto": macro["veredicto_ia"],
            "faltantes": macro["faltantes_ia"], "explicacion": macro["explicacion_ia"],
            "cita": macro["cita_ia"], "idea_principal": macro["idea_principal"],
        },
        "super": {
            "resultado": res["super"], "logrado": res["super"] >= minimo,
            "explicacion": consejos["consejo_super"],
            "preguntas": [{"orden": q["orden"], "pregunta": q["pregunta"],
                           "tu_opcion": q["opciones"][q["opcion_elegida"] - 1],
                           "opcion_correcta": q["opciones"][q["correcta"] - 1],
                           "es_correcta": bool(q["es_correcta"])} for q in super_],
        },
        "micro": {
            "resultado": res["micro"], "logrado": res["micro"] >= minimo,
            "explicacion": consejos["consejo_micro"],
            "aciertos": aciertos, "omisiones": omisiones, "neutras_marcadas": neutras,
        },
        "recomendaciones": recomendaciones(res, minimo, consejos, macro["faltantes_ia"]),
        "logros_nuevos": logros,
    }
