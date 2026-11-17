# CLAUDE.md · Frontend de LENTE

> Copia este archivo a la raíz del repositorio del frontend con el nombre `CLAUDE.md`.
> Claude Code (y otros asistentes que leen `CLAUDE.md` o `AGENTS.md`) lo cargan solos al
> empezar y así conocen el proyecto sin que haya que explicarlo cada vez.
> Mantenido por el equipo de backend: si la API cambia, se actualiza aquí y en
> `docs/frontend/CLAUDE.md` del repositorio `mvega09/lente`.

## Qué es LENTE

Herramienta de alfabetización mediática para estudiantes de colegio (3.° a 11.°) en Colombia.
El estudiante lee una noticia y la analiza en tres niveles, según el análisis crítico del
discurso de Teun van Dijk:

1. **Macroestructura**: escribe con sus palabras la idea principal. Una IA la compara con la
   idea aprobada por el profesor y le explica qué le faltó, citando la noticia.
2. **Superestructura**: responde preguntas de selección múltiple sobre cómo está organizada.
3. **Microestructura**: marca en el texto las palabras cargadas (adjetivos, verbos, expresiones).

Al final ve su resultado, puntos y logros. El profesor sigue el progreso de cada estudiante y
del curso.

Este repositorio es **solo el frontend**. La tecnología del frontend aún no está definida: no
asumas un framework; si hace falta elegir, pregunta. El backend (API, base de datos e IA) ya
existe y no se modifica desde aquí.

## Usuarios y modo aula

- Solo inician sesión **administrador** y **profesor**. El **estudiante no tiene cuenta**.
- **Modo aula:** el profesor, con su sesión abierta, abre la actividad para un estudiante y el
  estudiante responde en ese mismo dispositivo. La vista de actividad debe ocupar la pantalla
  completa y ocultar el panel del profesor mientras el estudiante trabaja.
- Público de colegio: lenguaje claro, letra legible, botones grandes, mensajes amables.
  Todo en español de Colombia.

## La API

- Dirección: `http://10.60.14.182:8000` (red de la universidad o VPN). Ponla en una variable
  de entorno, nunca en el código.
- Documentación interactiva: `http://10.60.14.182:8000/docs`. Contrato completo:
  `http://10.60.14.182:8000/openapi.json`. **Consulta el contrato antes de inventar un campo**
  y, si la tecnología lo permite, genera los tipos o el cliente desde ese archivo.
- Todo es JSON. Fechas en ISO 8601 con zona horaria. Ids enteros.
- CORS: el backend solo acepta orígenes registrados. Si una petición falla por CORS, pide al
  equipo de backend que agregue la dirección del frontend; no lo resuelvas desde aquí.
- `GET /salud` responde sin sesión y sirve para mostrar si el servidor está disponible.

## Sesión

1. `POST /auth/login` con `{"usuario", "clave"}` → `{"access_token", "token_type": "bearer", "usuario": {"id", "rol", "nombre", "debe_cambiar_clave"}}`.
2. Enviar `Authorization: Bearer <access_token>` en todas las demás peticiones.
3. Según `usuario.rol`: `administrador` → panel de administración; `profesor` → sus cursos.
4. Si `debe_cambiar_clave` es `true`, mostrar primero `POST /auth/cambiar-clave` con
   `{"actual", "nueva"}` (mínimo 8 caracteres, distinta a la actual; responde 204) y luego
   volver a iniciar sesión.
5. Al recargar, `GET /auth/yo` devuelve el usuario; un 401 significa sesión vencida (8 h).
6. Cerrar sesión = borrar el token. No hay endpoint de cierre.
7. Login fallido, cuenta bloqueada (5 intentos) o desactivada responden igual: 401
   «Usuario o clave incorrectos». Muestra ese mensaje sin precisar la causa.

Guarda el token de la forma más segura que permita la tecnología elegida (idealmente una
cookie httpOnly manejada por un servidor; si no, `sessionStorage`, porque los computadores
del colegio son compartidos). Nunca en el código ni en registros.

## Pantallas y endpoints

| Pantalla | Rol | Endpoints |
|---|---|---|
| Inicio de sesión y cambio de clave | todos | `POST /auth/login`, `GET /auth/yo`, `POST /auth/cambiar-clave` |
| Panel de administración | administrador | `GET /admin/resumen`, `GET/POST /admin/profesores`, `PATCH /admin/profesores/{id}`, `POST /admin/profesores/{id}/clave`, `GET /admin/estudiantes`, `GET/PUT /admin/ajustes` |
| Mis cursos y estudiantes | profesor | `GET/POST /cursos`, `PATCH /cursos/{id}`, `GET/POST /cursos/{id}/estudiantes`, `GET/PATCH/DELETE /estudiantes/{id}` |
| Biblioteca de textos | profesor | `GET/POST /textos`, `GET/PATCH/DELETE /textos/{id}` |
| Revisar lo que propuso la IA | profesor | `PATCH /textos/{id}/paquete`, `POST/PATCH/DELETE /textos/{id}/preguntas`, `POST/DELETE /textos/{id}/palabras`, `POST /textos/{id}/preparar`, `POST /textos/{id}/aprobar`, `POST /textos/{id}/revisar` |
| Modo explicación (resaltados) | profesor | `GET/POST /textos/{id}/resaltados`, `PATCH/DELETE /textos/{id}/resaltados/{id}` (el PATCH cambia nivel o explicación) |
| Textos activos del curso | profesor | `GET/POST/DELETE /cursos/{id}/textos` |
| Actividad del estudiante | profesor (modo aula) | `POST /actividades`, `GET /actividades/{id}`, `POST/GET /actividades/{id}/macro`, `POST /actividades/{id}/super`, `POST /actividades/{id}/micro`, `DELETE /actividades/{id}/micro/{inicio}`, `POST /actividades/{id}/terminar`, `GET /actividades/{id}/resultado` |
| Progreso del estudiante | profesor | `GET /estudiantes/{id}/progreso` (incluye `pendientes` con título), `GET /estudiantes/{id}/historial?nivel=macro\|super\|micro` |
| Panel del curso y alertas | profesor | `GET /cursos/{id}/panel`, `GET /alertas`, `POST /alertas/{id}/atender` |
| Reglas del curso (puntos y niveles) | profesor | `GET /cursos/{id}/ajustes`, `PUT/DELETE /cursos/{id}/ajustes/{clave}` |

### Ciclo de un texto

Estados: `borrador` → `preparando` (la IA trabaja, unos 5 min) → `en_revision` (el profesor
revisa y corrige) → `aprobado` → `archivado`. Mientras está `preparando`, consulta
`GET /textos/{id}` cada 10 s y muestra que la IA está trabajando. Solo un texto `aprobado` se
puede activar en un curso, y sin idea principal no se aprueba.

### Actividad (el flujo más importante)

El orden es obligatorio: macro → super → micro → resultado. Un paso fuera de orden responde
409. Usa siempre el `paso` que devuelve la API para decidir qué mostrar.

1. `POST /actividades` con `{"estudiante_id", "texto_id"}` → `paso`, `cuerpo`, `instruccion`
   (ya adaptada al grado: muéstrala tal cual). Si había una actividad sin terminar, la retoma.
2. **Macro:** `POST /actividades/{id}/macro` con `{"texto", "codigo_envio", "enviada_en"}`.
   Responde enseguida con `analizando: true`.
3. Consulta `GET /actividades/{id}/macro` cada 2 s mientras `analizando` sea `true` y muestra
   un estado de espera amable (tarda de 12 a 22 s). Si llega `mensaje`, muéstralo: avisa que va
   lento o que la IA falló. Al terminar llegan `veredicto` (`coincide`, `coincide_en_parte`,
   `por_mejorar`), `faltantes`, `explicacion` (ya escrita para el estudiante, en «tú»), `cita`
   (fragmento de la noticia: puedes resaltarlo en el texto) e `idea_principal`.
4. **Super:** `GET /actividades/{id}` trae `preguntas` (sin la respuesta correcta). Envía
   `POST /actividades/{id}/super` con `{"respuestas": [{"codigo_envio", "pregunta_id",
   "opcion_elegida"}], "enviada_en"}`; las opciones se numeran desde 1.
5. **Micro:** el estudiante selecciona palabras del `cuerpo`. Envía
   `POST /actividades/{id}/micro` con `{"marcas": [{"codigo_envio", "texto", "inicio", "fin"}],
   "enviada_en"}`. `inicio` y `fin` son posiciones de carácter dentro de `cuerpo` (`fin` no
   incluido) y `texto` debe ser exactamente `cuerpo[inicio:fin]`.
6. `POST /actividades/{id}/terminar` → resultados por nivel, `puntos_ganados`,
   `logros_nuevos` y `recomendaciones`. Después: `GET /actividades/{id}/resultado`.

### Datos listos para las pantallas

- Lista de estudiantes: cada uno trae `porcentaje_macro`, `porcentaje_super` y
  `porcentaje_micro` (0-100, vacío si no ha hecho actividades) para las barras.
- Panel del curso: `avance_macro`, `avance_super`, `avance_micro` (promedio del curso).
- Crear profesor: `usuario` y `clave` son opcionales. Si no se envían, la API
  propone el usuario a partir del nombre y genera una clave temporal que llega
  **una sola vez** en `clave_temporal`: muéstrala al administrador para que la
  entregue y no la guardes. Restablecer la clave funciona igual (responde 200).

## Reglas que el frontend debe respetar

- **No calcules nada en el navegador.** Calificaciones, puntos, niveles, rachas y logros los
  calcula la base de datos. Muestra lo que devuelve la API.
- **Nunca llames a la IA (Ollama) directamente.** Todo pasa por la API.
- **No reveles la idea principal antes de tiempo.** La API solo la envía después de la revisión
  de la macro; no la busques por otros endpoints para mostrarla antes.
- **Envíos sin duplicados:** cada respuesta lleva un `codigo_envio` UUID generado en el
  navegador (`crypto.randomUUID()`). Si la red falla, reintenta con el **mismo** código.
  Genera uno nuevo solo para una respuesta nueva.
- **Ánimo del estudiante: lenguaje no clínico.** Las etiquetas son exactamente «Motivación
  alta», «Neutral» y «Podría necesitar acompañamiento», siempre junto al aviso «Solo apoyo
  pedagógico. No es un diagnóstico y no afecta puntos ni calificación.» (llega como
  `aviso_animo`). Nunca uses palabras como diagnóstico, depresión, ansiedad, trastorno,
  patología, síntoma o terapia. El ánimo no se muestra al estudiante.
- **Privacidad:** un profesor solo ve lo suyo. Un 404 puede significar «es de otro profesor»;
  trátalo como «no encontrado», sin más detalle.
- **Secretos:** ni claves, ni tokens, ni direcciones fijas en el código ni en el repositorio.
  Las cuentas de prueba las entrega el equipo de backend por un canal privado.

## Errores

Todo error trae `detail`: un texto en español listo para mostrar, salvo el 422 de validación,
donde `detail` es una lista con el campo que falló (`loc`).

| Código | Qué hacer |
|---|---|
| 401 | Borrar el token e ir al inicio de sesión (en el login: mostrar `detail`) |
| 403 | El rol no tiene permiso: no muestres esa opción a ese rol |
| 404 | «No encontrado» |
| 409 | Regla del negocio (paso equivocado, duplicado, texto no aprobado): mostrar `detail` |
| 422 | Marcar el campo indicado en `detail` |
| 400 | Mostrar `detail` (p. ej. clave actual incorrecta) |

Centraliza las llamadas en un solo módulo que agregue el token y maneje el 401.

## Cuentas y datos de prueba

En la base hay un profesor y un administrador de prueba, con 2 cursos, 2 estudiantes, 2 textos
aprobados y 2 actividades terminadas, todos marcados «PRUEBA». Las credenciales están en la
guía privada que entrega el equipo de backend; no las copies a este repositorio.

## Al trabajar con IA en este repositorio

- Antes de usar un endpoint, revisa su forma real en `/openapi.json` o `/docs`.
- Si algo de la API falta o no sirve para una pantalla, no lo simules en el frontend: anótalo
  para el equipo de backend.
- Escribe los textos de la interfaz en español y pensando en estudiantes de colegio.
- Pregunta antes de elegir tecnología, librerías o estructura del proyecto: aún no están
  definidas.
