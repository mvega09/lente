# Worker de IA

Proceso independiente que atiende la tabla `cola_ia`.

```bash
python -m worker.ia_worker
```

## Flujo

1. `tomar_trabajo_ia()` entrega el trabajo más urgente (prioridad 1 = un
   estudiante está esperando). Usa `FOR UPDATE SKIP LOCKED`, así que se
   pueden correr varios workers.
2. Según la tarea, lee la vista `ia_textos`, `ia_ideas` o `ia_animo`.
3. Llama a Ollama con salida estructurada (JSON Schema de Pydantic).
4. Guarda con `guardar_revision_idea`, `terminar_preparacion` o `guardar_animo`.
5. Si algo falla, `reportar_error_ia` lo reintenta más tarde.

| Tarea | Modelo | Quién espera |
|---|---|---|
| `revisar_idea` (RF-10) | `OLLAMA_MODELO_VALIDACION` | El estudiante (meta ≤ 15 s, RNF-01) |
| `preparar_texto` (RF-09) | `OLLAMA_MODELO_PREPARACION` | Nadie; el profesor lo aprueba después |
| `analizar_animo` (RF-21) | `OLLAMA_MODELO_VALIDACION` | Nadie |

## Velocidad

- Sin razonamiento (`think=False`), temperatura 0 y `num_predict` limitado.
- La noticia va al inicio del prompt y la respuesta del estudiante al final,
  para aprovechar la caché de prefijo de Ollama.
- `keep_alive` mantiene el modelo cargado durante la clase.

!!! note "Pendiente"
    `analizar_animo` usa el LLM de forma provisional; RF-21 pide un
    clasificador ligero de sentimientos en español.
