"""Mide el tiempo de la validación de la idea principal (RF-10) contra Ollama.

Criterio RNF-01: 15 s o menos en el percentil 95. Usa los mismos prompts y el
mismo formato estructurado que el worker. El texto de prueba es ficticio.

    python -m scripts.benchmark_ia --modelos qwen3:14b gemma3:12b --repeticiones 3
    python -m scripts.benchmark_ia --modelos qwen3:14b --simultaneos 5
"""

import argparse
import json
import statistics
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor

from ollama import Client

from app.core.config import get_settings
from worker import prompts
from worker.modelos import RevisionIdea

NOTICIA = (
    "Villa Serena, 3 de marzo. El concejo municipal aprobó anoche, por siete votos contra cuatro, "
    "el polémico plan que convertirá el parque central en un parqueadero de tres pisos. "
    "Según el alcalde, la obra «acabará por fin con el caos vehicular» que, a su juicio, asfixia al comercio. "
    "Los comerciantes del centro celebraron la decisión y aseguraron que sus ventas caen cada vez que "
    "los clientes no encuentran dónde estacionar. En cambio, un grupo de vecinos denunció que el parque es "
    "el único espacio verde del barrio y que nadie les preguntó su opinión antes de la votación. "
    "La obra costará 4.000 millones de pesos y empezará en junio. El concejo no informó cuántos árboles "
    "serán talados ni si se construirá otro parque en reemplazo."
)
IDEA = ("El concejo de Villa Serena aprobó convertir el parque central en un parqueadero, decisión que "
        "apoyan el alcalde y los comerciantes pero que rechazan los vecinos por perder su único espacio verde.")
ELEMENTOS = ["aprobación del concejo", "parque convertido en parqueadero", "apoyo de alcalde y comerciantes",
             "rechazo de los vecinos"]
RESPUESTAS = [
    "Aprobaron cambiar el parque por un parqueadero y los vecinos están en contra aunque los comerciantes lo apoyan.",
    "Van a hacer un parqueadero en el centro.",
    "La noticia habla de los árboles del barrio.",
]


def _normalizar(t: str) -> str:
    t = unicodedata.normalize("NFD", t.lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn" and (c.isalnum() or c.isspace()))


def una_validacion(cliente: Client, modelo: str, respuesta: str) -> dict:
    inicio = time.perf_counter()
    r = cliente.chat(
        model=modelo,
        messages=prompts.mensajes_revisar_idea(NOTICIA, IDEA, ELEMENTOS, "secundaria", respuesta),
        format=RevisionIdea.model_json_schema(),
        think=False,
        keep_alive="30m",
        options={"temperature": 0, "num_predict": 250},
    )
    segundos = time.perf_counter() - inicio
    try:
        rev = RevisionIdea.model_validate_json(r.message.content)
        valido, veredicto = True, rev.veredicto
        cita_ok = bool(rev.cita.strip()) and _normalizar(rev.cita.strip()) in _normalizar(NOTICIA)
    except Exception:  # noqa: BLE001
        valido, veredicto, cita_ok = False, None, False
    return {
        "segundos": round(segundos, 2),
        "tokens_salida": getattr(r, "eval_count", None),
        "tokens_entrada": getattr(r, "prompt_eval_count", None),
        # Desglose (Ollama lo da en nanosegundos): leer el prompt vs. generar la respuesta
        "leer_prompt_s": round((getattr(r, "prompt_eval_duration", 0) or 0) / 1e9, 2),
        "generar_s": round((getattr(r, "eval_duration", 0) or 0) / 1e9, 2),
        "carga_s": round((getattr(r, "load_duration", 0) or 0) / 1e9, 2),
        "json_valido": valido,
        "veredicto": veredicto,
        "cita_en_texto": cita_ok,
    }


def p95(valores: list[float]) -> float:
    if len(valores) < 2:
        return valores[0]
    return statistics.quantiles(valores, n=20, method="inclusive")[18]


def medir(modelo: str, repeticiones: int, simultaneos: int) -> dict:
    cliente = Client(host=get_settings().ollama_url, timeout=600)
    calentamiento = una_validacion(cliente, modelo, RESPUESTAS[0])   # carga el modelo en memoria
    tareas = [RESPUESTAS[i % len(RESPUESTAS)] for i in range(repeticiones * simultaneos)]
    inicio = time.perf_counter()
    with ThreadPoolExecutor(max_workers=simultaneos) as pool:
        resultados = list(pool.map(lambda resp: una_validacion(cliente, modelo, resp), tareas))
    tiempos = [r["segundos"] for r in resultados]
    return {
        "modelo": modelo,
        "simultaneos": simultaneos,
        "solicitudes": len(resultados),
        "calentamiento_s": calentamiento["segundos"],
        "mediana_s": round(statistics.median(tiempos), 2),
        "p95_s": round(p95(tiempos), 2),
        "maximo_s": max(tiempos),
        "duracion_total_s": round(time.perf_counter() - inicio, 2),
        "json_valido_pct": round(100 * sum(r["json_valido"] for r in resultados) / len(resultados)),
        "cita_valida_pct": round(100 * sum(r["cita_en_texto"] for r in resultados) / len(resultados)),
        "cumple_rnf01": p95(tiempos) <= 15,
        "detalle": resultados,
    }


def medir_preparacion(modelo: str) -> dict:
    """RF-09: preparación del paquete (segundo plano, sin límite de 15 s)."""
    from worker.modelos import PreparacionTexto

    cliente = Client(host=get_settings().ollama_url, timeout=1800)
    inicio = time.perf_counter()
    r = cliente.chat(model=modelo, messages=prompts.mensajes_preparar_texto("Parque central", NOTICIA),
                     format=PreparacionTexto.model_json_schema(), think=False, keep_alive="30m",
                     options={"temperature": 0, "num_predict": 2000})
    segundos = round(time.perf_counter() - inicio, 1)
    salida = {"modelo": modelo, "segundos": segundos, "tokens_salida": getattr(r, "eval_count", None),
              "generar_s": round((getattr(r, "eval_duration", 0) or 0) / 1e9, 1)}
    try:
        p = PreparacionTexto.model_validate_json(r.message.content)
    except Exception as e:  # noqa: BLE001
        return salida | {"json_valido": False, "error": str(e)[:200]}
    en_texto = [w.palabra for w in p.palabras_cargadas if w.palabra in NOTICIA]
    return salida | {
        "json_valido": True,
        "idea_principal": p.idea_principal,
        "elementos_clave": p.elementos_clave,
        "preguntas": len(p.preguntas),
        "preguntas_validas": sum(1 <= q.correcta <= len(q.opciones) for q in p.preguntas),
        "palabras": [w.palabra for w in p.palabras_cargadas],
        "palabras_en_texto_pct": round(100 * len(en_texto) / max(1, len(p.palabras_cargadas))),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--modelos", nargs="+", default=["qwen3:14b"])
    ap.add_argument("--repeticiones", type=int, default=3)
    ap.add_argument("--simultaneos", type=int, default=1)
    ap.add_argument("--preparar", action="store_true", help="Medir la preparación de un texto (RF-09)")
    args = ap.parse_args()
    for modelo in args.modelos:
        resultado = medir_preparacion(modelo) if args.preparar else medir(modelo, args.repeticiones, args.simultaneos)
        print(json.dumps(resultado, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
