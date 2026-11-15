---
name: lente-nuevo-endpoint
description: Agrega o modifica endpoints de la API FastAPI de LENTE con sus pruebas, sin necesitar base de datos. Úsala siempre que haya que crear una ruta nueva, cambiar una consulta SQL, un servicio o un esquema Pydantic del backend, o implementar un requisito RF/RNF del levantamiento, aunque el usuario solo diga "agrega que el profesor pueda…".
---

# Agregar un endpoint en LENTE

La lógica de negocio (puntos, calificación, cola de IA, rachas, alertas) vive
en PostgreSQL: triggers, funciones y vistas de `db/schema.sql`. El backend
**llama** esas funciones y **lee** esas vistas; no las duplica en Python.
Antes de escribir, buscar en el esquema si ya existe la función o vista.

## Estructura de cada endpoint

| Capa | Archivo | Qué va |
|---|---|---|
| Esquema | `app/schemas/<modulo>.py` | Modelos Pydantic de entrada y salida |
| Servicio | `app/services/<modulo>_service.py` | SQL en constantes `SQL_*` + funciones async |
| Ruta | `app/routers/<modulo>.py` | Ruta fina: dependencias, llamada al servicio, `summary` con el RF |

Dependencias de `app/core/deps.py`: `Conn`, `Sesion`, `Admin`, `Profesor`.
Ayudantes de `app/core/db.py`: `uno()` (una fila o None), `varios()` (lista),
`ejecutar()` (filas afectadas). **`ejecutar()` para UPDATE/DELETE sin
RETURNING**: `uno()` sobre una sentencia sin resultados hace fallar a psycopg.

## Reglas que no se negocian

- **Aislamiento por profesor (RNF-05):** toda consulta de un profesor filtra por
  `profesor_id` del token, normalmente con JOIN a `lente.cursos`. Si el recurso
  es de otro profesor, responder 404 (`NoEncontrado`), nunca 403: no se debe
  revelar que existe.
- **Esquema explícito:** escribir siempre `lente.tabla`; hay una prueba que lo exige.
- **Parámetros con nombre** `%(x)s`, nunca f-strings con datos del usuario.
- **Envíos idempotentes (RNF-03):** las respuestas del estudiante llevan
  `codigo_envio` (UUID) e `INSERT … ON CONFLICT DO NOTHING`.
- **Errores:** `NoEncontrado` → 404, `Conflicto` → 409, `DatoInvalido` → 422;
  los errores de PostgreSQL ya se traducen en `app/core/errores.py`.
- **Lenguaje no clínico** en ánimo y alertas (`app/core/animo.py`).

## Pruebas (sin PostgreSQL ni Ollama)

1. Servicio: `ConexionFalsa(fila1, fila2, …)` de `tests/conftest.py` devuelve
   una respuesta por consulta, en orden, y guarda `consultas` para revisar los
   parámetros (por ejemplo, que se pasó el `profesor_id`).
2. Ruta: fixture `cliente` + `cabeceras("profesor", 7)`; reemplazar el servicio
   con `monkeypatch`. Probar el caso feliz, el 404 de otro profesor y el 403 de
   un rol sin permiso.
3. Automático: toda constante `SQL_*` pasa por `tests/test_sql.py` (sintaxis
   real de PostgreSQL con pglast) y `tests/test_esquema.py` (cada columna existe
   en `db/schema.sql`). Si fallan, el SQL está mal; no tocar el verificador.

## Al terminar

1. `python -m scripts.generar_docs_api` en la VM-APP para actualizar `docs/api.md`.
2. Actualizar el estado del módulo en `docs/hoja-de-ruta.md` si corresponde.
3. Publicar con la skill `lente-publicar`.
