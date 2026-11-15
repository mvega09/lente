# Hoja de ruta del backend

Basada en el *Levantamiento de requerimientos v1.1 (IA)*, el esquema
`Info_bd/schema.sql` y los documentos técnicos del proyecto.

## Principios

- **La lógica vive en PostgreSQL.** Calificación de super y micro, cola de IA,
  puntos, rachas, logros y alertas ya están en triggers y funciones. El backend
  llama esas funciones y lee las vistas; no las duplica.
- **Aislamiento por profesor (RNF-05).** Toda consulta de un profesor filtra por
  el `profesor_id` del token. Un recurso de otro profesor responde **404**.
- **Privacidad (RNF-06).** Al modelo solo van texto y respuesta; el worker usa el
  rol `lente_ia`, que no ve nombres. No se guardan prompts completos.
- **Configurable sin código (RNF-08).** Puntos, umbrales, modelo y prompts se
  leen de la tabla `ajustes`.

## Módulos y estado

| # | Módulo | Requisitos | Endpoints principales | Estado |
|---|---|---|---|---|
| 1 | Sesión | RF-01 | `POST /auth/login`, `GET /auth/yo`, `POST /auth/cambiar-clave` | Hecho* |
| 2 | Administración | RF-02, RF-04 | `/admin/profesores`, `/admin/resumen`, `/admin/estudiantes` | Hecho* |
| 3 | Cursos y estudiantes | RF-03, RF-05, RF-20 | `/cursos`, `/cursos/{id}/estudiantes`, `/estudiantes/{id}` | Hecho* |
| 4 | Biblioteca de textos | RF-09, RF-11, RF-12 | `/textos`, `/preparar`, `/aprobar`, `/revisar`, `/paquete`, preguntas y palabras | Hecho* |
| 5 | Activación en curso | RF-09 | `/cursos/{id}/textos` | Hecho* |
| 6 | Actividad del estudiante | RF-10, RF-11, RF-12, RF-15, RNF-03 | `/actividades`, `/actividades/{id}/macro|super|micro`, `/actividades/{id}/terminar` | Hecho* |
| 7 | Resultado | RF-16, RF-17 | `/actividades/{id}/resultado` | Hecho* |
| 8 | Progreso y estadísticas | RF-06, RF-07, RF-08 | `/estudiantes/{id}/progreso`, `/estudiantes/{id}/historial` | Hecho* |
| 9 | Resaltado y explicación | RF-13, RF-14 | `/textos/{id}/resaltados` | Hecho* |
| 10 | Gamificación | RF-18, RNF-08 | Logros en el progreso, `/cursos/{id}/ajustes`, `/admin/ajustes` | Hecho* |
| 11 | Adaptación por grado | RF-19 | Instrucciones por nivel escolar y preguntas filtradas por dificultad | Hecho* |
| 12 | Panel del docente y ánimo | RF-21 | `/cursos/{id}/panel`, `/alertas` | Hecho* |
| 13 | Worker de IA | RF-09, RF-10, RF-21, RNF-08 | Proceso `worker.ia_worker` (modelo y prompts desde `ajustes`) | Primera versión |

\* Probado con pruebas unitarias y validación de SQL; falta la prueba de
integración contra una base de pruebas con `schema.sql`.

## Decisiones abiertas (para el equipo)

1. **Cómo entra el estudiante sin cuenta.** El v1.1 dice que no inicia sesión.
   Propuesta inicial: el profesor abre la actividad para un estudiante desde su
   sesión (modo aula / videobeam) y el estudiante responde en ese dispositivo.
   Un código de curso para dispositivos propios queda como mejora futura.
2. **Clasificador de ánimo (RF-21).** Por ahora usa el modelo de Ollama con
   salida de tres categorías; el v1.1 pide un clasificador ligero en español.
3. **Modelo para validar la macro.** Solo hay `qwen3:14b` y `gemma3:12b` en la
   VM-IA; falta medir si cumplen 15 s en el percentil 95 (RNF-01).

## Pruebas

- **Unitarias** (sin base ni IA): `pytest -m "not integracion"`.
- **Integración**: PostgreSQL desechable en la VM-APP con `schema.sql`
  cargado, nunca contra la base real.
