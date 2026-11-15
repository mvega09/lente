# Tiempos de la IA (RNF-01)

**Criterio:** la validación de la idea principal (RF-10) debe resolverse en
15 s o menos en el percentil 95, con 1, 5 y 20 estudiantes simultáneos.

Medido el 14 de noviembre de 2026 desde la VM-APP contra la VM-IA
(8 vCPU con AVX2, 23 GB de RAM, sin GPU, Ollama 0.40.14), con el script
`scripts/benchmark_ia.py`, una noticia ficticia y tres respuestas de
estudiante (buena, parcial y pobre).

```bash
OLLAMA_URL=http://10.60.14.181:11434 python -m scripts.benchmark_ia \
    --modelos qwen3:4b --repeticiones 5 --simultaneos 1
```

## Resultados con 1 estudiante

| Modelo | Respuesta | Mediana | p95 | JSON válido | Cita existe en el texto | ¿Cumple? |
|---|---|---|---|---|---|---|
| qwen3:14b | sin límites | 56,8 s | 61,2 s | 100 % | 100 % | No |
| gemma3:12b | sin límites | 61,7 s | 65,3 s | 100 % | 100 % | No |
| qwen3:4b | sin límites | 22,5 s | 24,6 s | 100 % | 67 % | No |
| qwen3:4b | límites medios | 16,9 s | 18,5 s | 100 % | 100 % | No |
| **qwen3:4b** | **límites finales** | **13,7 s** | **14,2 s** | **100 %** | **100 %** | **Sí** |

Primera solicitud tras cargar el modelo: qwen3:14b 159 s, gemma3:12b 128 s,
qwen3:4b 37 s. Por eso el worker usa `keep_alive` (30 min) y un límite duro
de 90 s por solicitud.

## Qué determina el tiempo

El desglose de Ollama muestra que **leer el prompt toma menos de 1 s**: la
caché de prefijo funciona porque la noticia va primero y la respuesta del
estudiante al final. **Casi todo el tiempo es generar la respuesta**:
≈ 2,5 tokens/s con qwen3:14b y ≈ 8 tokens/s con qwen3:4b.

Por eso la mejora vino de acortar la salida: el esquema estructurado limita
`faltantes` (80 caracteres), `explicacion` (120) y `cita` (90), y Ollama lo
aplica como gramática. La respuesta bajó de ≈ 150 a ≈ 110 tokens.

## Con 5 estudiantes simultáneos (qwen3:4b)

Tiempos: 13,7 · 27,1 · 42,1 · 56,0 · 68,6 s → p95 66 s. **No cumple.**
Ollama atiende las solicitudes una tras otra (`OLLAMA_NUM_PARALLEL` sin
definir): cada una tarda lo mismo, pero hacen fila. Con 20 estudiantes el
último esperaría ≈ 4,5 min.

## Preparación de un texto (RF-09, qwen3:14b)

```bash
python -m scripts.benchmark_ia --modelos qwen3:14b --preparar
```

| Tiempo | Tokens generados | JSON válido | Preguntas válidas | Palabras que existen en el texto |
|---|---|---|---|---|
| 268,7 s (≈ 4,5 min) | 628 | Sí | 3 de 3 | 4 de 4 (100 %) |

La idea principal propuesta fue correcta y las palabras cargadas detectadas
fueron «polémico», «asfixia», «celebraron» y «denunció». Como nadie espera
esta tarea (el texto queda «preparando» y el profesor lo revisa después),
cumple RF-09; el límite del worker para preparar es de 15 min.

## Recomendaciones (en orden)

1. **Usar `qwen3:4b` para validar** la idea principal y dejar `qwen3:14b`
   para preparar textos (nadie espera). Ya es el valor por defecto
   (`OLLAMA_MODELO_VALIDACION`, o el ajuste `ia_modelo_validacion`).
   Falta validar la calidad: el v1.1 pide ≥ 70 % de acuerdo con el docente.
2. **Probar generación en paralelo** en la VM-IA (requiere root). En CPU,
   generar varias respuestas a la vez suele aumentar el rendimiento total:
   ```bash
   sudo systemctl edit ollama   # agregar en [Service]:
   # Environment="OLLAMA_NUM_PARALLEL=4"
   sudo systemctl restart ollama
   ```
   y correr 4 workers (la cola usa `FOR UPDATE SKIP LOCKED`). Luego repetir
   la medición con `--simultaneos 5` y `--simultaneos 20`.
3. **En el aula**, el profesor puede escalonar el envío de la idea principal
   por grupos; mientras tanto el estudiante ve «analizando» y la API avisa
   si se pasa del tiempo máximo.
4. Si con lo anterior no se cumple con 20 estudiantes: más vCPU o una GPU,
   como prevé el documento de infraestructura.
