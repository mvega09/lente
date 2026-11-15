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

## Con generación en paralelo (`OLLAMA_NUM_PARALLEL=4`)

Activado el 15 de noviembre de 2026 en la VM-IA
(`/etc/systemd/system/ollama.service.d/paralelo.conf`). Ollama genera hasta 4
respuestas a la vez; cada una sale más lenta, pero el total sube.

| Estudiantes a la vez | Tiempos (s) | Máximo | ¿Cumple 15 s? |
|---|---|---|---|
| 1 | 11,2 · 12,2 · 12,3 · 12,8 · 13,8 | 13,8 s | Sí |
| 2 | 17,5 · 17,8 | 17,8 s | No (por poco) |
| 5 | 25,0 · 25,2 · 26,1 · 26,3 · 37,9 | 37,9 s | No |
| 10 | 22,9 … 27,2 · 47,8 … 51,0 · 71,3 · 72,4 | 72,4 s | No |
| 20 | 22,8 … 26,2 · 46,4 … 51,0 · 71,7 … 74,9 · 94,8 … 99,1 · 118,8 … 121,3 | 121,3 s | No |

- Las solicitudes salen en **grupos de 4 cada ≈ 24 s**: el rendimiento pasó de
  1 respuesta cada ≈ 13 s (en fila) a **1 cada ≈ 6 s (≈ 10 por minuto)**.
  Con 20 estudiantes el último espera ≈ 2 min en lugar de ≈ 4,5 min.
- Regla práctica: espera máxima ≈ **24 s × (estudiantes a la vez ÷ 4, redondeado
  hacia arriba)**.
- La primera vez que se usan los 4 espacios hay que leer la noticia en cada uno
  (en una medición en frío, 5 a la vez tardaron hasta 69 s). Después la noticia
  queda en caché; por eso conviene que el curso trabaje sobre el mismo texto.
- JSON válido y cita encontrada en el texto: 100 % en todas las mediciones.
- Si se prepara un texto con `qwen3:14b` al mismo tiempo, compite por la CPU:
  conviene preparar textos fuera de la clase.

**Conclusión:** con esta VM (solo CPU) RNF-01 se cumple con 1 validación a la
vez. Para 5 o 20 simultáneos dentro de 15 s se necesita GPU (ver recomendación 4).

### Capacidad recomendada con el hardware actual

| Situación | Espera de la idea principal |
|---|---|
| Envíos escalonados (lo normal: cada estudiante lee a su ritmo) | ≈ 12–25 s |
| Hasta 4 envíos al mismo tiempo | ≈ 25 s |
| 10 al mismo tiempo | ≈ 1 min el último |
| 20 al mismo tiempo | ≈ 2 min el último |
| 30 al mismo tiempo | ≈ 3 min el último |

La API y la base no son el límite (atienden cientos de estudiantes conectados);
el límite es solo la validación con IA, que procesa ≈ 10 respuestas por minuto.

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
2. **Generación en paralelo: activada** (`OLLAMA_NUM_PARALLEL=4`, ver arriba).
   Correr 4 copias del worker para aprovecharla (la cola usa
   `FOR UPDATE SKIP LOCKED` y atiende primero la prioridad 1):
   ```bash
   sudo systemctl enable --now lente-worker@{1..4}
   ```
3. **En el aula**, el profesor puede escalonar el envío de la idea principal
   por grupos; mientras tanto el estudiante ve «analizando» y la API avisa
   si se pasa del tiempo máximo.
4. Si con lo anterior no se cumple con 20 estudiantes: más vCPU o una GPU,
   como prevé el documento de infraestructura.
