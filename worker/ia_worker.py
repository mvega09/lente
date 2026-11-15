"""Worker de IA de LENTE.

Toma trabajos de lente.cola_ia, llama a Ollama y guarda el resultado con las
funciones de la base. Se conecta con el rol lente_ia, que NO ve nombres de
estudiantes (RNF-06). Se pueden correr varios workers: la cola usa
FOR UPDATE SKIP LOCKED.

Ejecutar:  python -m worker.ia_worker
"""

import logging
import signal
import time
from typing import TypeVar

import psycopg
from ollama import Client
from psycopg.rows import dict_row
from pydantic import BaseModel

from app.core.config import get_settings
from worker import prompts
from worker.modelos import Animo, PreparacionTexto, RevisionIdea

log = logging.getLogger("lente.worker")
settings = get_settings()
ollama = Client(host=settings.ollama_url)

ESPERA_SIN_TRABAJO_S = 1.0
ESPERA_RECONEXION_S = 5.0
_detener = False

M = TypeVar("M", bound=BaseModel)


def _pedir_detener(*_):
    global _detener
    _detener = True
    log.info("Señal recibida: se detendrá al terminar el trabajo actual")


def preguntar(modelo: str, mensajes: list[dict], esquema: type[M], num_predict: int) -> M:
    """Llama a Ollama con salida estructurada y valida el JSON con Pydantic."""
    r = ollama.chat(
        model=modelo,
        messages=mensajes,
        format=esquema.model_json_schema(),
        think=False,                       # Qwen3 sin razonamiento (más rápido)
        keep_alive=settings.ollama_keep_alive,
        options={"temperature": 0, "num_predict": num_predict},
    )
    return esquema.model_validate_json(r.message.content)


def ajuste(conn: psycopg.Connection, clave: str) -> str | None:
    """Lee un ajuste general como texto (RNF-08: modelo y prompts sin tocar código)."""
    fila = conn.execute("SELECT ajuste(%s) #>> '{}' AS valor", (clave,)).fetchone()
    return fila["valor"] if fila and fila["valor"] else None


# ---------------------------------------------------------------- tareas

def revisar_idea(conn: psycopg.Connection, trabajo_id: int) -> None:
    d = conn.execute("SELECT * FROM ia_ideas WHERE trabajo_id = %s", (trabajo_id,)).fetchone()
    if d is None:
        raise ValueError("No se encontraron datos para la revisión")
    modelo = ajuste(conn, "ia_modelo_validacion") or settings.ollama_modelo_validacion
    instrucciones = ajuste(conn, "ia_instrucciones_revisar")
    inicio = time.perf_counter()
    rev = preguntar(
        modelo,
        prompts.mensajes_revisar_idea(d["texto"], d["idea_principal"], d["elementos_clave"],
                                      d["nivel_escolar"], d["respuesta_estudiante"], instrucciones),
        RevisionIdea,
        num_predict=250,
    )
    ms = int((time.perf_counter() - inicio) * 1000)
    # guardar_revision_idea verifica en la base que la cita exista en el texto
    cita_ok = conn.execute(
        "SELECT guardar_revision_idea(%s, %s, %s, %s, %s, %s) AS ok",
        (trabajo_id, rev.veredicto, rev.faltantes, rev.explicacion, rev.cita, ms),
    ).fetchone()["ok"]
    log.info("revisar_idea %s: %s en %d ms (cita válida: %s)", trabajo_id, rev.veredicto, ms, cita_ok)


def preparar_texto(conn: psycopg.Connection, trabajo_id: int) -> None:
    d = conn.execute("SELECT * FROM ia_textos WHERE trabajo_id = %s", (trabajo_id,)).fetchone()
    if d is None or not d["cuerpo"]:
        raise ValueError("El texto no tiene cuerpo para preparar")
    prep = preguntar(
        ajuste(conn, "ia_modelo") or settings.ollama_modelo_preparacion,
        prompts.mensajes_preparar_texto(d["titulo"], d["cuerpo"], ajuste(conn, "ia_instrucciones_preparar")),
        PreparacionTexto,
        num_predict=2000,
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
        for orden, p in enumerate(prep.preguntas, start=1):
            if not 1 <= p.correcta <= len(p.opciones):
                continue
            conn.execute(
                """INSERT INTO preguntas (texto_id, orden, pregunta, opciones, correcta, dificultad)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (texto_id, orden, p.pregunta[:300], p.opciones, p.correcta, p.dificultad),
            )
        usados: set[int] = set()
        for w in prep.palabras_cargadas:
            pos = cuerpo.find(w.palabra)          # solo palabras que existan en el texto
            if pos < 0 or pos in usados or len(w.palabra) > 120:
                continue
            usados.add(pos)
            conn.execute(
                """INSERT INTO palabras_cargadas (texto_id, palabra, tipo, inicio, fin, explicacion)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (texto_id, w.palabra, w.tipo, pos, pos + len(w.palabra), w.explicacion),
            )
        conn.execute("SELECT terminar_preparacion(%s)", (trabajo_id,))
    log.info("preparar_texto %s: texto %s listo para revisión del profesor", trabajo_id, texto_id)


def analizar_animo(conn: psycopg.Connection, trabajo_id: int) -> None:
    # TODO (RF-21): reemplazar por un clasificador ligero de sentimientos en español.
    d = conn.execute("SELECT * FROM ia_animo WHERE trabajo_id = %s", (trabajo_id,)).fetchone()
    if d is None:
        raise ValueError("No se encontraron datos de la actividad")
    res = preguntar(
        settings.ollama_modelo_validacion,
        prompts.mensajes_analizar_animo(d["respuesta_abierta"], d["resultado_macro"],
                                        d["resultado_super"], d["resultado_micro"], d["segundos"]),
        Animo,
        num_predict=30,
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


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    signal.signal(signal.SIGTERM, _pedir_detener)
    signal.signal(signal.SIGINT, _pedir_detener)
    log.info("Worker de IA iniciado (Ollama: %s)", settings.ollama_url)

    while not _detener:
        try:
            with psycopg.connect(settings.conninfo_ia, autocommit=True, row_factory=dict_row) as conn:
                while not _detener:
                    if not procesar_siguiente(conn):
                        time.sleep(ESPERA_SIN_TRABAJO_S)
        except psycopg.OperationalError:
            log.exception("Sin conexión con PostgreSQL; reintentando en %s s", ESPERA_RECONEXION_S)
            time.sleep(ESPERA_RECONEXION_S)
    log.info("Worker detenido")


if __name__ == "__main__":
    main()
