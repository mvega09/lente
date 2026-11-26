"""Worker de IA de LENTE.

Toma trabajos de lente.cola_ia, llama a Ollama y guarda el resultado con las
funciones de la base. Se conecta con el rol lente_ia, que NO ve nombres de
estudiantes (RNF-06). Se pueden correr varios workers: la cola usa
FOR UPDATE SKIP LOCKED.

Ejecutar:  python -m worker.ia_worker
"""

import logging
import random
import re
import signal
import time
from typing import TypeVar

import psycopg
from ollama import Client
from psycopg.rows import dict_row
from pydantic import BaseModel

from app.core.config import get_settings
from worker import gramatica, prompts, revision
from worker.modelos import Animo, PreparacionTexto, RevisionIdea

log = logging.getLogger("lente.worker")
settings = get_settings()
# Dos clientes: la revisión de la idea tiene un estudiante esperando; la preparación no
cliente_revision = Client(host=settings.ollama_url, timeout=settings.ollama_timeout_revision_s)
cliente_preparacion = Client(host=settings.ollama_url, timeout=settings.ollama_timeout_preparacion_s)

ESPERA_SIN_TRABAJO_S = 1.0
ESPERA_RECONEXION_S = 5.0
_detener = False

M = TypeVar("M", bound=BaseModel)


def _pedir_detener(*_):
    global _detener
    _detener = True
    log.info("Señal recibida: se detendrá al terminar el trabajo actual")


def preguntar(modelo: str, mensajes: list[dict], esquema: type[M], num_predict: int,
              cliente: Client | None = None, keep_alive: str | None = None) -> M:
    """Llama a Ollama con salida estructurada y valida el JSON con Pydantic.

    Nunca se registra el contenido del prompt (RNF-06): solo ids y tiempos.
    """
    r = (cliente or cliente_revision).chat(
        model=modelo,
        messages=mensajes,
        format=esquema.model_json_schema(),
        think=False,                       # Qwen3 sin razonamiento (más rápido)
        keep_alive=keep_alive or settings.ollama_keep_alive,
        options={"temperature": 0, "num_predict": num_predict},
    )
    return esquema.model_validate_json(r.message.content)


def ajuste(conn: psycopg.Connection, clave: str) -> str | None:
    """Lee un ajuste general como texto (RNF-08: modelo y prompts sin tocar código)."""
    fila = conn.execute("SELECT ajuste(%s) #>> '{}' AS valor", (clave,)).fetchone()
    return fila["valor"] if fila and fila["valor"] else None


def modelo_validacion(conn: psycopg.Connection) -> str:
    return ajuste(conn, "ia_modelo_validacion") or settings.ollama_modelo_validacion


def precalentar(conn: psycopg.Connection) -> bool:
    """Carga el modelo de validación en Ollama y lo deja en memoria.

    Una solicitud sin texto solo carga el modelo (si ya está cargado, responde al
    instante). Si Ollama no responde, el worker sigue: la revisión lo cargará.
    """
    modelo = modelo_validacion(conn)
    try:
        cliente_revision.generate(model=modelo, prompt="", keep_alive=settings.ollama_keep_alive_validacion)
        log.info("Modelo %s cargado y listo", modelo)
        return True
    except Exception as e:  # noqa: BLE001
        log.warning("No se pudo precargar %s: %s", modelo, e)
        return False


# ---------------------------------------------------------------- tareas

def revisar_idea(conn: psycopg.Connection, trabajo_id: int) -> None:
    d = conn.execute("SELECT * FROM ia_ideas WHERE trabajo_id = %s", (trabajo_id,)).fetchone()
    if d is None:
        raise ValueError("No se encontraron datos para la revisión")
    respuesta = d["respuesta_estudiante"] or ""
    if not revision.tiene_sentido(respuesta):
        # Teclazos o letras al azar: no se gasta la IA (y no puede aprobarlos por error)
        conn.execute(
            "SELECT guardar_revision_idea(%s, %s, %s, %s, %s, %s) AS ok",
            (trabajo_id, "por_mejorar", "", revision.EXPLICACION_SIN_SENTIDO,
             revision.primera_frase(d["texto"]), 0),
        )
        log.info("revisar_idea %s: por_mejorar sin IA (la respuesta no tiene palabras reconocibles)", trabajo_id)
        return
    modelo = modelo_validacion(conn)
    instrucciones = ajuste(conn, "ia_instrucciones_revisar")
    inicio = time.perf_counter()
    rev = preguntar(
        modelo,
        prompts.mensajes_revisar_idea(d["texto"], d["idea_principal"], d["elementos_clave"],
                                      d["nivel_escolar"], d["respuesta_estudiante"], instrucciones),
        RevisionIdea,
        num_predict=250,
        keep_alive=settings.ollama_keep_alive_validacion,
    )
    ms = int((time.perf_counter() - inicio) * 1000)
    en_comun = revision.palabras_en_comun(respuesta, d["texto"], d["idea_principal"] or "",
                                          " ".join(d["elementos_clave"] or []))
    veredicto, explicacion_nueva = revision.ajustar_veredicto(rev.veredicto, rev.faltantes, rev.explicacion, en_comun)
    explicacion, cita = rev.explicacion, rev.cita
    if explicacion_nueva:
        explicacion, cita = explicacion_nueva, revision.primera_frase(d["texto"])
    if veredicto != rev.veredicto:
        log.info("revisar_idea %s: la IA dijo %s, se corrige a %s (%d palabras en común)",
                 trabajo_id, rev.veredicto, veredicto, en_comun)
    # guardar_revision_idea verifica en la base que la cita exista en el texto
    cita_ok = conn.execute(
        "SELECT guardar_revision_idea(%s, %s, %s, %s, %s, %s) AS ok",
        (trabajo_id, veredicto, rev.faltantes, explicacion, cita, ms),
    ).fetchone()["ok"]
    log.info("revisar_idea %s: %s en %d ms (cita válida: %s)", trabajo_id, veredicto, ms, cita_ok)


NUM_PREDICT_PREPARACION = 1400


def mezclar_opciones(preguntas: list, semilla: int) -> list[tuple[object, list[str], int]]:
    """Cambia de lugar la respuesta correcta de cada pregunta.

    El modelo casi siempre pone la correcta de primera; un estudiante aprendería a marcar
    siempre la opción 1. Aquí cada pregunta la recibe en otra posición (nunca la misma que
    la pregunta anterior) y los distractores se mezclan. Con la misma semilla (el id del
    texto) el resultado es siempre igual. Se omiten las preguntas con `correcta` inválida.
    """
    azar = random.Random(semilla)
    salida, anterior = [], None
    for p in preguntas:
        if not 1 <= p.correcta <= len(p.opciones):
            continue
        correcta = p.opciones[p.correcta - 1]
        otras = [o for i, o in enumerate(p.opciones) if i != p.correcta - 1]
        azar.shuffle(otras)
        lugares = [i for i in range(len(p.opciones)) if i != anterior] or list(range(len(p.opciones)))
        lugar = azar.choice(lugares)
        otras.insert(lugar, correcta)
        salida.append((p, otras, lugar + 1))
        anterior = lugar
    return salida


_AJENOS = re.compile(r"[^\x20-\x7E -ɏ‐-‟…]")


def explicacion_limpia(texto: str, limite: int = 110) -> str | None:
    """Sin caracteres ajenos al español (la gramática a veces corta un token a la mitad y
    queda basura como «malest嚣») y, si llegó al límite, cortada en la última palabra completa."""
    texto = " ".join(_AJENOS.sub("", texto).split())
    if len(texto) >= limite - 2 and " " in texto:
        texto = texto[: texto.rfind(" ")].rstrip(",;: ") + "…"
    return texto or None


def palabras_validas(prep: PreparacionTexto, cuerpo: str) -> list[dict]:
    """Palabras cargadas que se guardan.

    - Deben existir en el texto (si la IA cambió mayúsculas, se toma la forma real del texto).
    - El tipo lo decide el análisis gramatical (worker/gramatica.py), no la IA.
    - Se descartan nombres propios, cifras y palabras que no pueden tener carga por sí solas.
    """
    nlp = gramatica.analizador()
    doc = nlp(cuerpo) if nlp else None
    minusculas = cuerpo.lower()
    salida, ocupados = [], []
    for w in prep.palabras_cargadas:
        palabra = w.palabra.strip()
        pos = cuerpo.find(palabra)
        if pos < 0:
            pos = minusculas.find(palabra.lower())
        if pos < 0 or not palabra:
            continue
        fin = pos + len(palabra)
        if any(pos < f and i < fin for i, f in ocupados):      # se cruza con otra ya elegida
            continue
        tipo = gramatica.tipo_de(doc, pos, fin, w.tipo)
        if tipo is None:
            continue
        ocupados.append((pos, fin))
        salida.append({"palabra": cuerpo[pos:fin], "tipo": tipo, "inicio": pos, "fin": fin,
                       "explicacion": explicacion_limpia(w.explicacion)})
    return salida


def preparar_texto(conn: psycopg.Connection, trabajo_id: int) -> None:
    d = conn.execute("SELECT * FROM ia_textos WHERE trabajo_id = %s", (trabajo_id,)).fetchone()
    if d is None or not d["cuerpo"]:
        raise ValueError("El texto no tiene cuerpo para preparar")
    prep = preguntar(
        ajuste(conn, "ia_modelo") or settings.ollama_modelo_preparacion,
        prompts.mensajes_preparar_texto(d["titulo"], d["cuerpo"], ajuste(conn, "ia_instrucciones_preparar")),
        PreparacionTexto,
        num_predict=NUM_PREDICT_PREPARACION,
        cliente=cliente_preparacion,
    )
    texto_id, cuerpo = d["texto_id"], d["cuerpo"]
    with conn.transaction():
        conn.execute(
            """UPDATE textos SET idea_principal = %s, elementos_clave = %s,
                      consejo_macro = %s, consejo_super = %s, consejo_micro = %s
                WHERE id = %s""",
            (prep.idea_principal, prep.elementos_clave, prep.consejo_macro,
             prep.consejo_super, prep.consejo_micro, texto_id),
        )
        conn.execute("DELETE FROM preguntas WHERE texto_id = %s", (texto_id,))
        conn.execute("DELETE FROM palabras_cargadas WHERE texto_id = %s", (texto_id,))
        for orden, (p, opciones, correcta) in enumerate(mezclar_opciones(prep.preguntas, texto_id), start=1):
            conn.execute(
                """INSERT INTO preguntas (texto_id, orden, pregunta, opciones, correcta, dificultad)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (texto_id, orden, p.pregunta[:300], opciones, correcta, p.dificultad),
            )
        for w in palabras_validas(prep, cuerpo):
            conn.execute(
                """INSERT INTO palabras_cargadas (texto_id, palabra, tipo, inicio, fin, explicacion)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (texto_id, w["palabra"], w["tipo"], w["inicio"], w["fin"], w["explicacion"]),
            )
        conn.execute("SELECT terminar_preparacion(%s)", (trabajo_id,))
    log.info("preparar_texto %s: texto %s listo para revisión del profesor", trabajo_id, texto_id)


def analizar_animo(conn: psycopg.Connection, trabajo_id: int) -> None:
    # TODO (RF-21): reemplazar por un clasificador ligero de sentimientos en español.
    d = conn.execute("SELECT * FROM ia_animo WHERE trabajo_id = %s", (trabajo_id,)).fetchone()
    if d is None:
        raise ValueError("No se encontraron datos de la actividad")
    res = preguntar(
        modelo_validacion(conn),
        prompts.mensajes_analizar_animo(d["respuesta_abierta"], d["resultado_macro"],
                                        d["resultado_super"], d["resultado_micro"], d["segundos"],
                                        bool(d.get("abandonada")), d.get("paso")),
        Animo,
        num_predict=30,
        keep_alive=settings.ollama_keep_alive_validacion,
    )
    conn.execute("SELECT guardar_animo(%s, %s)", (trabajo_id, res.animo))
    log.info("analizar_animo %s: %s", trabajo_id, res.animo)


TAREAS = {
    "revisar_idea": revisar_idea,
    "preparar_texto": preparar_texto,
    "analizar_animo": analizar_animo,
}


# ---------------------------------------------------------------- bucle

def procesar_siguiente(conn: psycopg.Connection) -> bool:
    """Procesa un trabajo. Devuelve False si la cola está vacía."""
    trabajo = conn.execute("SELECT * FROM tomar_trabajo_ia()").fetchone()
    if trabajo is None:
        return False
    tid, tarea = trabajo["id"], trabajo["tarea"]
    try:
        TAREAS[tarea](conn, tid)
    except Exception as e:  # noqa: BLE001 - cualquier fallo se reporta y se reintenta
        log.exception("Falló %s %s", tarea, tid)
        conn.execute("SELECT reportar_error_ia(%s, %s)", (tid, f"{type(e).__name__}: {e}"[:500]))
    return True


def mantenimiento(conn: psycopg.Connection) -> int:
    """Marca las actividades abandonadas (RF-21). Nunca detiene al worker."""
    try:
        n = conn.execute("SELECT marcar_abandonadas() AS n").fetchone()["n"]
    except psycopg.errors.UndefinedFunction:
        log.warning("La base aún no tiene marcar_abandonadas(): aplique db/migraciones/001")
        return 0
    except psycopg.Error as e:
        log.warning("No se pudieron revisar las actividades abandonadas: %s", e)
        return 0
    if n:
        log.info("%d actividad(es) marcadas como abandonadas", n)
    return n


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    signal.signal(signal.SIGTERM, _pedir_detener)
    signal.signal(signal.SIGINT, _pedir_detener)
    log.info("Worker de IA iniciado (Ollama: %s)", settings.ollama_url)

    while not _detener:
        try:
            with psycopg.connect(settings.conninfo_ia, autocommit=True, row_factory=dict_row) as conn:
                precalentar(conn)
                ultimo_calentamiento = time.monotonic()
                ultimo_mantenimiento = 0.0
                while not _detener:
                    if time.monotonic() - ultimo_mantenimiento > settings.mantenimiento_cada_s:
                        mantenimiento(conn)
                        ultimo_mantenimiento = time.monotonic()
                    if not procesar_siguiente(conn):
                        # Si Ollama se reinició, el modelo vuelve a cargarse antes del próximo estudiante
                        if time.monotonic() - ultimo_calentamiento > settings.ollama_precalentar_cada_s:
                            precalentar(conn)
                            ultimo_calentamiento = time.monotonic()
                        time.sleep(ESPERA_SIN_TRABAJO_S)
        except psycopg.OperationalError:
            log.exception("Sin conexión con PostgreSQL; reintentando en %s s", ESPERA_RECONEXION_S)
            time.sleep(ESPERA_RECONEXION_S)
    log.info("Worker detenido")


if __name__ == "__main__":
    main()
