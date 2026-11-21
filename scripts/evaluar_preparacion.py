"""Evalúa la preparación con IA (RF-09) sobre textos reales de la base, SIN guardar nada.

Corre el mismo prompt, modelo y validación que el worker y muestra el tiempo, las
palabras cargadas propuestas con su tipo y, si existe una anotación de referencia
(scripts/referencia_palabras.json), la precisión y la cobertura frente a ella.

    python -m scripts.evaluar_preparacion --textos 6 7
"""

import argparse
import json
import pathlib
import time
from collections import Counter

import psycopg
from psycopg.rows import dict_row

from app.core.config import get_settings
from worker import ia_worker, prompts
from worker.modelos import PreparacionTexto

REFERENCIA = pathlib.Path(__file__).with_name("referencia_palabras.json")


def _norm(t: str) -> str:
    return " ".join(t.lower().split())


def evaluar(texto: dict, modelo: str, referencia: dict | None) -> dict:
    inicio = time.perf_counter()
    r = ia_worker.cliente_preparacion.chat(
        model=modelo, messages=prompts.mensajes_preparar_texto(texto["titulo"], texto["cuerpo"]),
        format=PreparacionTexto.model_json_schema(), think=False, keep_alive=ia_worker.settings.ollama_keep_alive,
        options={"temperature": 0, "num_predict": ia_worker.NUM_PREDICT_PREPARACION})
    segundos = round(time.perf_counter() - inicio, 1)
    prep = PreparacionTexto.model_validate_json(r.message.content)
    palabras = ia_worker.palabras_validas(prep, texto["cuerpo"])
    salida = {
        "texto": texto["id"], "titulo": texto["titulo"], "segundos": segundos,
        "tokens_entrada": getattr(r, "prompt_eval_count", None),
        "tokens_salida": getattr(r, "eval_count", None),
        "seg_lectura": round((getattr(r, "prompt_eval_duration", 0) or 0) / 1e9, 1),
        "seg_escritura": round((getattr(r, "eval_duration", 0) or 0) / 1e9, 1),
        "propuestas_por_la_ia": len(prep.palabras_cargadas), "guardadas": len(palabras),
        "por_tipo": dict(Counter(p["tipo"] for p in palabras)),
        "palabras": [(p["palabra"], p["tipo"]) for p in palabras],
        "preguntas": len(prep.preguntas), "idea_principal": prep.idea_principal,
    }
    if referencia:
        esperadas = {_norm(k): v for k, v in referencia.items()}
        encontradas = [p for p in palabras if _norm(p["palabra"]) in esperadas
                       or any(_norm(p["palabra"]) in e or e in _norm(p["palabra"]) for e in esperadas)]
        bien_tipo = [p for p in encontradas if esperadas.get(_norm(p["palabra"])) == p["tipo"]]
        salida |= {
            "precision": round(len(encontradas) / max(1, len(palabras)), 2),
            "tipo_correcto": f"{len(bien_tipo)}/{len(encontradas)}",
            "sobran": [p["palabra"] for p in palabras if p not in encontradas],
        }
    return salida


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--textos", type=int, nargs="+", required=True)
    ap.add_argument("--modelo", default=None)
    args = ap.parse_args()
    s = get_settings()
    modelo = args.modelo or s.ollama_modelo_preparacion
    referencias = json.loads(REFERENCIA.read_text(encoding="utf-8")) if REFERENCIA.exists() else {}
    with psycopg.connect(s.conninfo_app, row_factory=dict_row) as conn:
        conn.read_only = True
        for tid in args.textos:
            texto = conn.execute("SELECT id, titulo, cuerpo FROM lente.textos WHERE id = %s", (tid,)).fetchone()
            print(json.dumps(evaluar(texto, modelo, referencias.get(str(tid))), ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
