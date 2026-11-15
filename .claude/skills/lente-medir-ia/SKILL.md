---
name: lente-medir-ia
description: Mide los tiempos de la IA de LENTE (Ollama en la VM-IA 10.60.14.181) contra el requisito RNF-01 (validación de la idea principal en 15 s o menos, p95, con 1, 5 y 20 estudiantes). Úsala siempre que se cambie de modelo, prompt, límites de respuesta, OLLAMA_NUM_PARALLEL o hardware de la VM-IA, o cuando pregunten cuántos estudiantes soporta, qué tan rápida es la IA o si se cumple RNF-01.
---

# Medir la IA de LENTE

En la VM-IA no hay GPU: el tiempo lo domina **generar tokens** (≈ 8 tokens/s
con qwen3:4b, ≈ 2,5 con qwen3:14b); leer el prompt toma menos de 1 s gracias
a la caché de prefijo (la noticia va primero, la respuesta del estudiante al
final). Por eso las mejoras vienen de acortar la salida o de generar en
paralelo, y por eso hay que medir en lugar de suponer.

## Antes de medir

- Estado de Ollama (no requiere root):
  ```bash
  ssh lente-ia 'systemctl show ollama -p Environment; ollama list; curl -s localhost:11434/api/ps'
  ```
  Si hay modelos cargados haciendo trabajo real, avisar antes de medir.
- Los cambios de configuración de Ollama requieren root: darle al usuario los
  comandos en bloques separados, con la forma de deshacerlos, y esperar a que
  los ejecute en MobaXterm. No intentar usar `sudo` ni su contraseña.

## Medición de la validación (RF-10)

Desde la VM-APP, con el script del repositorio (mismo prompt y formato que el
worker). Resumir quitando el detalle por solicitud:

```bash
ssh lente-app 'cd ~/lente && export OLLAMA_URL=http://10.60.14.181:11434; for s in "5 1" "1 5" "1 10" "1 20"; do set -- $s; .venv/bin/python -m scripts.benchmark_ia --modelos qwen3:4b --repeticiones $1 --simultaneos $2 | .venv/bin/python -c "import json,sys; d=json.loads(sys.stdin.read()); t=sorted(x[\"segundos\"] for x in d.pop(\"detalle\")); print(d[\"simultaneos\"], \"p95\", d[\"p95_s\"], \"total\", d[\"duracion_total_s\"], \"json\", d[\"json_valido_pct\"], \"cita\", d[\"cita_valida_pct\"], t)"; done'
```

Tarda varios minutos: correrlo en segundo plano.

**Cuidado con la primera vuelta:** con `OLLAMA_NUM_PARALLEL` > 1, cada espacio
tiene que leer la noticia la primera vez y los tiempos salen inflados (en
nov-2026, 5 a la vez dieron 69 s en frío y 38 s después). Si una medición
contradice a las demás, repetirla antes de concluir.

Para la preparación de textos (RF-09, sin estudiante esperando):
`python -m scripts.benchmark_ia --modelos qwen3:14b --preparar`.

## Cómo interpretar

- Cumple RNF-01 si el p95 ≤ 15 s. Revisar también `json_valido_pct` y
  `cita_valida_pct` (deben ser 100 %): un modelo rápido que inventa citas no sirve.
- Con N espacios en paralelo, las respuestas salen en grupos de N. Espera
  máxima aproximada = tiempo de un grupo × ⌈estudiantes a la vez ÷ N⌉.
- Distinguir siempre: la API y la base aguantan cientos de estudiantes
  conectados; el límite es solo la validación con IA.

## Al terminar

1. Actualizar `docs/benchmark-ia.md` (fecha, configuración, tabla con tiempos,
   conclusión honesta) y la decisión 3 de `docs/hoja-de-ruta.md`.
2. Si cambia el número de espacios en paralelo, ajustar el número de copias del
   worker (`lente-worker@{1..N}`).
3. Publicar con la skill `lente-publicar`.
4. Explicar al usuario en español con una tabla sencilla: estudiantes a la vez,
   espera y si cumple.
