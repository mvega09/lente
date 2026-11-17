"""Prueba de punta a punta contra la API REAL, la base REAL y Ollama REAL.

Recorre lo que hará un profesor en clase: crea un curso y un estudiante, sube
una noticia que la IA prepara (qwen3:14b), la aprueba y la activa, y hace una
actividad completa: macro (revisada por la IA, qwen3:4b), super, micro,
resultado, ánimo (IA en segundo plano), progreso y panel.

ESCRIBE DATOS en la base: todo lo que crea lleva «PRUEBA» en el nombre para
poder reconocerlo y borrarlo después. Necesita un profesor (scripts.crear_profesor)
y sus credenciales en LENTE_PRUEBA_USUARIO / LENTE_PRUEBA_CLAVE.

    set -a; . ~/.lente_profesor_prueba; set +a
    python -m scripts.prueba_flujo_real --api http://localhost:8000
"""

import argparse
import json
import os
import pathlib
import sys
import time
import uuid
from datetime import datetime, timezone

import httpx

CASOS = pathlib.Path(__file__).with_name("casos_validacion.json")


class Fallo(Exception):
    pass


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


def codigo() -> str:
    return str(uuid.uuid4())


def paso(n: int, texto: str) -> None:
    print(f"\n[{n}] {texto}", flush=True)


def ok(texto: str) -> None:
    print(f"    OK  {texto}", flush=True)


def esperar(descripcion: str, consulta, listo, limite_s: int, cada_s: float = 2.0):
    inicio = time.perf_counter()
    while True:
        valor = consulta()
        if listo(valor):
            return valor, time.perf_counter() - inicio
        if time.perf_counter() - inicio > limite_s:
            raise Fallo(f"{descripcion}: no terminó en {limite_s} s (último estado: {json.dumps(valor, ensure_ascii=False)[:300]})")
        time.sleep(cada_s)


def correr(api: httpx.Client, usuario: str, clave: str) -> None:
    def pedir(metodo: str, ruta: str, esperado: int = 200, **kw):
        r = api.request(metodo, ruta, **kw)
        if r.status_code != esperado:
            raise Fallo(f"{metodo} {ruta} → HTTP {r.status_code} (se esperaba {esperado}): {r.text[:300]}")
        return r.json() if r.content else None

    noticia = json.loads(CASOS.read_text(encoding="utf-8"))["noticias"][1]      # río Claro, secundaria
    marca = datetime.now().strftime("%Y-%m-%d %H:%M")

    paso(1, "Inicio de sesión del profesor (RF-01)")
    token = pedir("POST", "/auth/login", json={"usuario": usuario, "clave": clave})["access_token"]
    api.headers["Authorization"] = f"Bearer {token}"
    yo = pedir("GET", "/auth/yo")
    ok(f"sesión de {yo['nombre']} (rol {yo['rol']})")

    paso(2, "Curso y estudiante (RF-03, RF-05)")
    curso = pedir("POST", "/cursos", 201, json={"nombre": f"PRUEBA 8A {marca}"})
    est = pedir("POST", f"/cursos/{curso['id']}/estudiantes", 201, json={"nombre": "Estudiante PRUEBA", "grado": 8})
    ok(f"curso {curso['id']} y estudiante {est['id']} (nivel {est['nivel_escolar']})")

    paso(3, "El profesor sube la noticia y la IA la prepara (RF-09, qwen3:14b; puede tardar ~5 min)")
    texto = pedir("POST", "/textos", 201, json={"titulo": f"PRUEBA - {noticia['titulo']}", "cuerpo": noticia["texto"],
                                                "fuente": "Noticia ficticia de prueba", "preparar_con_ia": True})
    tid = texto["id"]
    ok(f"texto {tid} en estado «{texto['estado']}»")
    detalle, seg = esperar("Preparación con IA", lambda: pedir("GET", f"/textos/{tid}"),
                           lambda t: t["estado"] not in ("borrador", "preparando"), limite_s=1200, cada_s=10)
    if detalle["estado"] != "en_revision":
        raise Fallo(f"La preparación terminó en estado «{detalle['estado']}»")
    ok(f"preparado en {seg:.0f} s → estado «en_revision»")
    print(f"    Idea principal propuesta: {detalle['idea_principal']}")
    print(f"    Elementos clave: {detalle['elementos_clave']}")
    print(f"    Preguntas: {len(detalle['preguntas'])} · Palabras cargadas: "
          f"{[p['palabra'] for p in detalle['palabras']]}")
    if not detalle["preguntas"] or not detalle["palabras"]:
        raise Fallo("La IA no dejó preguntas o palabras cargadas")

    paso(4, "El profesor aprueba el texto y lo activa en el curso (RF-09)")
    pedir("POST", f"/textos/{tid}/aprobar")
    pedir("POST", f"/cursos/{curso['id']}/textos", 204, json={"texto_id": tid})
    ok("aprobado y activo en el curso")

    paso(5, "El profesor abre la actividad para el estudiante (modo aula)")
    act = pedir("POST", "/actividades", 201, json={"estudiante_id": est["id"], "texto_id": tid})
    aid = act["id"]
    ok(f"actividad {aid}, paso «{act['paso']}»")

    paso(6, "Macroestructura: el estudiante escribe la idea principal y la IA la revisa (RF-10, qwen3:4b)")
    envio = {"texto": "Los pescadores denuncian que la mina contamina el río Claro y se mueren los peces.",
             "codigo_envio": codigo(), "enviada_en": ahora()}
    m = pedir("POST", f"/actividades/{aid}/macro", json=envio)
    if m.get("idea_principal"):
        raise Fallo("La idea principal se reveló antes de la revisión (RF-10)")
    ok(f"recibida, «analizando»={m['analizando']} y sin revelar la idea")
    pedir("POST", f"/actividades/{aid}/macro", json=envio)          # RNF-03: reenvío idéntico
    ok("reenvío del mismo código aceptado sin duplicar (RNF-03)")
    m, seg = esperar("Revisión de la idea", lambda: pedir("GET", f"/actividades/{aid}/macro"),
                     lambda x: not x["analizando"], limite_s=180, cada_s=1)
    ok(f"revisada en {seg:.1f} s ({'cumple' if seg <= 15 else 'NO cumple'} los 15 s de RNF-01)")
    print(f"    Veredicto: {m['veredicto']} · Faltó: {m['faltantes']}")
    print(f"    Explicación: {m['explicacion']}")
    print(f"    Cita: {m['cita']!r} · Idea revelada: {bool(m['idea_principal'])}")

    paso(7, "Superestructura: preguntas (RF-11), calificadas por la base")
    vista = pedir("GET", f"/actividades/{aid}")
    if any("correcta" in p for p in vista["preguntas"]):
        raise Fallo("La vista del estudiante expone la respuesta correcta")
    correctas = {p["id"]: p["correcta"] for p in detalle["preguntas"]}
    respuestas = []
    for i, p in enumerate(vista["preguntas"]):
        elegida = correctas[p["id"]] if i < len(vista["preguntas"]) - 1 else (correctas[p["id"]] % len(p["opciones"])) + 1
        respuestas.append({"codigo_envio": codigo(), "pregunta_id": p["id"], "opcion_elegida": elegida})
    s = pedir("POST", f"/actividades/{aid}/super", json={"respuestas": respuestas, "enviada_en": ahora()})
    ok(f"{len(respuestas)} respuestas (la última equivocada a propósito): "
       f"{[r['es_correcta'] for r in s['resultados']]} → paso «{s['paso']}»")

    paso(8, "Microestructura: marcar palabras cargadas (RF-12), calificadas por la base")
    cuerpo = detalle["cuerpo"]
    cargadas = detalle["palabras"][:2]
    neutra = "pescadores"
    j = cuerpo.find(neutra)
    if any(p["inicio"] <= j < p["fin"] for p in detalle["palabras"]):
        neutra, j = "semana", cuerpo.find("semana")
    # Secundaria: el estudiante clasifica cada palabra (RF-12); la segunda, mal a propósito
    otro_tipo = {"adjetivo": "verbo", "verbo": "adjetivo", "expresion": "adjetivo"}
    marcas = [{"codigo_envio": codigo(), "texto": p["palabra"], "inicio": p["inicio"], "fin": p["fin"],
               "tipo_palabra": p["tipo"] if i == 0 else otro_tipo[p["tipo"]]} for i, p in enumerate(cargadas)]
    marcas.append({"codigo_envio": codigo(), "texto": neutra, "inicio": j, "fin": j + len(neutra)})
    r = pedir("POST", f"/actividades/{aid}/micro", json={"marcas": marcas, "enviada_en": ahora()})
    ok(f"{r['recibidas']} marcas: {[p['palabra'] for p in cargadas]} (cargadas) + «{neutra}» (neutra, a propósito)")

    paso(9, "Terminar y ver el resultado (RF-16, RF-17, RF-18)")
    res = pedir("POST", f"/actividades/{aid}/terminar")
    ok(f"macro={res['macro']['resultado']} · super={res['super']['resultado']} · micro={res['micro']['resultado']} "
       f"· puntos={res['puntos_ganados']} · logros={[l['nombre'] for l in res['logros_nuevos']]}")
    m = res["micro"]
    ok(f"tipo de palabra: {m['tipos_correctos']} de {m['tipos_evaluados']} bien clasificadas "
       f"{[(a['palabra'], a['tu_tipo'], a['tipo_correcto']) for a in m['aciertos']]}")

    paso(10, "Ánimo en segundo plano (RF-21, qwen3:4b) y seguimiento del profesor (RF-06 a RF-08)")
    prog, seg = esperar("Análisis de ánimo", lambda: pedir("GET", f"/estudiantes/{est['id']}/progreso"),
                        lambda p: p.get("animo") is not None, limite_s=180, cada_s=2)
    ok(f"ánimo «{prog['animo']}» en {seg:.0f} s · actividades hechas: {prog['actividades_hechas']}")
    hist = pedir("GET", f"/estudiantes/{est['id']}/historial")
    panel = pedir("GET", f"/cursos/{curso['id']}/panel")
    ok(f"historial con niveles {sorted({h['nivel'] for h in hist})} · panel: participaron {panel['participaron']}, "
       f"clima {panel['clima']}")

    print(f"\nFLUJO COMPLETO OK. Datos creados: curso {curso['id']}, estudiante {est['id']}, texto {tid}, actividad {aid}.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--api", default="http://localhost:8000")
    args = ap.parse_args()
    usuario, clave = os.getenv("LENTE_PRUEBA_USUARIO"), os.getenv("LENTE_PRUEBA_CLAVE")
    if not usuario or not clave:
        raise SystemExit("Faltan LENTE_PRUEBA_USUARIO y LENTE_PRUEBA_CLAVE")
    with httpx.Client(base_url=args.api, timeout=30) as api:
        try:
            correr(api, usuario, clave)
        except Fallo as e:
            print(f"\nFALLÓ: {e}", file=sys.stderr)
            raise SystemExit(1) from None


if __name__ == "__main__":
    main()
