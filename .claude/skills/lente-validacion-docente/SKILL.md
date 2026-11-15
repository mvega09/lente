---
name: lente-validacion-docente
description: Genera la hoja de Excel con la que el docente valida la IA de LENTE (requisito de al menos 70 % de acuerdo en la revisión de la idea principal, RF-10) y analiza la hoja ya llenada. Úsala cuando se hable de validar la calidad de la IA, del 70 % de acuerdo, de comparar la IA con el profesor, de cambiar de modelo o de prompt de revisión, o cuando el usuario traiga la hoja validacion_docente.xlsx calificada.
---

# Validación de la IA con el docente

El levantamiento v1.1 exige que la IA coincida con el docente en ≥ 70 % de
los casos. La hoja es **a ciegas**: el docente califica cada respuesta sin ver
lo que dijo la IA (la IA está en otra hoja) y la hoja calcula el acuerdo con
fórmulas. Así el resultado no se deja influir y sirve como evidencia para el
proyecto de grado.

## Archivos

- `scripts/casos_validacion.json`: noticias ficticias (primaria, secundaria y
  media) con su idea principal y elementos clave, y 8 respuestas cada una que
  cubren buena, parcial, detalle suelto, opinión y fuera de tema.
- `scripts/validacion_docente.py`: paso `ia` (pide el veredicto usando el mismo
  prompt, formato y modelo que el worker) y paso `excel` (crea la hoja).
- `tests/test_validacion_docente.py`: comprueba los casos y la hoja.

## Generar la hoja

```bash
ssh lente-app 'cd ~/lente && OLLAMA_URL=http://10.60.14.181:11434 .venv/bin/python -m scripts.validacion_docente ia --salida /tmp/validacion_ia.json && .venv/bin/python -m scripts.validacion_docente excel --resultados /tmp/validacion_ia.json --salida /tmp/validacion_docente.xlsx'
scp lente-app:/tmp/validacion_docente.xlsx "PROYECTO GRADO/validacion_docente/"
scp lente-app:/tmp/validacion_ia.json "PROYECTO GRADO/validacion_docente/"
```

Con 24 casos y 4 en paralelo tarda unos 3–5 minutos. Para otro modelo:
`ia --modelo qwen3:14b`. Guardar cada resultado con el nombre del modelo para
poder compararlos.

Antes de entregarla, revisar el JSON: casos con `error`, citas que no están en
el texto (`cita_en_texto: false`) y explicaciones que no le hablen al
estudiante. Contárselo al usuario como hallazgos, sin cambiar el veredicto de
la IA a mano.

## Agregar o cambiar casos

Editar `casos_validacion.json` manteniendo la variedad de respuestas. Si cambia
el total de casos, actualizar `test_casos_completos`. Los casos deben ser
ficticios: no usar respuestas reales de estudiantes (RNF-06, privacidad).

## Analizar la hoja llenada por el docente

Leer la hoja `2. Respuestas de la IA` (columnas C = IA, H = docente,
I = coinciden, J = diferencia de un nivel) y la hoja `Resultado`. Reportar:
porcentaje de acuerdo y si cumple el 70 %; desacuerdos graves (Coincide frente
a Por mejorar) con la respuesta del estudiante; y si la IA tiende a ser más
estricta o más blanda que el docente. Con eso se decide si ajustar las
instrucciones (ajuste `ia_instrucciones_revisar`, sin tocar código) o el modelo.

Explicar todo al usuario en español sencillo.
