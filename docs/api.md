# API

> Generado automáticamente con `python -m scripts.generar_docs_api`. No editar a mano.

La referencia interactiva completa (esquemas de entrada y salida, ejemplos y
pruebas en vivo) está en **`/docs`** (Swagger) y **`/redoc`** de la API.

## Autenticación

`POST /auth/login` devuelve un token. Envíelo en cada solicitud con la
cabecera `Authorization: Bearer <token>`. El rol del token decide qué rutas
puede usar: **administrador** (rutas `/admin`) o **profesor** (el resto).
Un profesor solo ve sus propios cursos, estudiantes, textos y resultados: si
pide algo de otro profesor recibe **404** (RNF-05).

## Errores

| Código | Cuándo |
|---|---|
| 401 | Sin token o token vencido |
| 403 | El rol no puede usar esa ruta |
| 404 | No existe o es de otro profesor |
| 409 | La operación no se puede hacer en el estado actual (por ejemplo, saltar un paso) |
| 422 | Algún dato no es válido |

## Rutas


### Actividad del estudiante

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/actividades` | Abrir (o retomar) la actividad de un estudiante con un texto activo |
| `GET` | `/actividades/{actividad_id}` | Estado de la actividad: paso actual, texto e instrucción según el grado |
| `GET` | `/actividades/{actividad_id}/macro` | Consultar la revisión de la idea principal ('analizando' mientras la IA trabaja) |
| `POST` | `/actividades/{actividad_id}/macro` | Enviar la idea principal; la IA la revisa en segundo plano (RF-10) |
| `POST` | `/actividades/{actividad_id}/micro` | Marcar palabras y expresiones con carga emocional (RF-12) |
| `DELETE` | `/actividades/{actividad_id}/micro/{inicio}` | Quitar una marca antes de terminar |
| `GET` | `/actividades/{actividad_id}/resultado` | Resultado de una actividad terminada (RF-16) |
| `POST` | `/actividades/{actividad_id}/super` | Responder las preguntas de superestructura (RF-11) |
| `POST` | `/actividades/{actividad_id}/terminar` | «Ver mi resultado»: calcula resultados, puntos, racha y logros (RF-16, RF-17, RF-18) |

### Administración

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/admin/ajustes` | Valores generales: puntos, umbrales, modelo y prompts |
| `PUT` | `/admin/ajustes/{clave}` | Cambiar un valor general sin tocar código (RNF-08) |
| `GET` | `/admin/estudiantes` | Estudiantes registrados (RF-04) |
| `GET` | `/admin/profesores` | Profesores registrados (RF-02, RF-04) |
| `POST` | `/admin/profesores` | Crear cuenta de profesor (RF-02) |
| `GET` | `/admin/profesores/{profesor_id}` | Ver un profesor |
| `PATCH` | `/admin/profesores/{profesor_id}` | Modificar nombre o activar/desactivar la cuenta (RF-02) |
| `POST` | `/admin/profesores/{profesor_id}/clave` | Restablecer contraseña temporal y desbloquear (RF-02) |
| `GET` | `/admin/resumen` | Totales de profesores y estudiantes (RF-04) |

### Autenticación

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/auth/cambiar-clave` | Cambiar la contraseña (obligatorio tras una clave temporal) |
| `POST` | `/auth/login` | Inicio de sesión de administrador o profesor (RF-01) |
| `GET` | `/auth/yo` | Datos del usuario de la sesión actual |

### Cursos y estudiantes

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/cursos` | Mis cursos |
| `POST` | `/cursos` | Crear curso |
| `GET` | `/cursos/{curso_id}` | Ver un curso |
| `PATCH` | `/cursos/{curso_id}` | Modificar o desactivar un curso |
| `GET` | `/cursos/{curso_id}/estudiantes` | Estudiantes del curso (RF-05) |
| `POST` | `/cursos/{curso_id}/estudiantes` | Agregar estudiante solo con su nombre (RF-03) |
| `GET` | `/estudiantes/{estudiante_id}` | Ver un estudiante |
| `PATCH` | `/estudiantes/{estudiante_id}` | Editar nombre, grado (RF-20), curso o activar/desactivar (RF-03) |
| `DELETE` | `/estudiantes/{estudiante_id}` | Desactivar estudiante (se conserva su historial) |

### Salud

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/` | Información básica de la API |
| `GET` | `/salud` | Comprueba que la API y la base de datos respondan |

### Seguimiento del profesor

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/alertas` | Alertas de acompañamiento (RF-21) |
| `POST` | `/alertas/{alerta_id}/atender` | Marcar la alerta como atendida, con una nota opcional |
| `GET` | `/cursos/{curso_id}/ajustes` | Reglas de puntos, niveles y alertas que usa el curso (RF-18, RNF-08) |
| `PUT` | `/cursos/{curso_id}/ajustes/{clave}` | Cambiar una regla solo para este curso |
| `DELETE` | `/cursos/{curso_id}/ajustes/{clave}` | Volver al valor general de una regla |
| `GET` | `/cursos/{curso_id}/panel` | Panel del docente: participación, avance, recompensas y clima del curso |
| `GET` | `/estudiantes/{estudiante_id}/historial` | Historial de respuestas del estudiante (RF-07) |
| `GET` | `/estudiantes/{estudiante_id}/progreso` | Progreso individual, estadísticas, logros y evolución (RF-06, RF-08, RF-18) |

### Textos

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/cursos/{curso_id}/textos` | Textos del curso |
| `POST` | `/cursos/{curso_id}/textos` | Activar un texto aprobado en el curso |
| `DELETE` | `/cursos/{curso_id}/textos/{texto_id}` | Retirar un texto del curso |
| `GET` | `/textos` | Mi biblioteca de textos |
| `POST` | `/textos` | Cargar un texto; con cuerpo, la IA prepara el paquete en segundo plano (RF-09) |
| `GET` | `/textos/{texto_id}` | Texto con su paquete, preguntas y palabras |
| `PATCH` | `/textos/{texto_id}` | Editar título, fuente, nota o enlace |
| `DELETE` | `/textos/{texto_id}` | Archivar el texto |
| `POST` | `/textos/{texto_id}/aprobar` | Aprobar el paquete; sin idea principal no se aprueba (RF-09) |
| `POST` | `/textos/{texto_id}/palabras` | Agregar palabra o expresión con carga emocional (RF-12) |
| `DELETE` | `/textos/{texto_id}/palabras/{palabra_id}` | Quitar palabra |
| `PATCH` | `/textos/{texto_id}/paquete` | Revisar la idea principal, los elementos clave y los consejos (RF-09) |
| `POST` | `/textos/{texto_id}/preguntas` | Agregar pregunta orientadora de superestructura (RF-11) |
| `PATCH` | `/textos/{texto_id}/preguntas/{pregunta_id}` | Editar pregunta |
| `DELETE` | `/textos/{texto_id}/preguntas/{pregunta_id}` | Quitar pregunta |
| `POST` | `/textos/{texto_id}/preparar` | Pedir a la IA que (re)prepare el paquete |
| `GET` | `/textos/{texto_id}/resaltados` | Resaltados del modo explicación (RF-13, RF-14) |
| `POST` | `/textos/{texto_id}/resaltados` | Resaltar un fragmento con su explicación; el texto original no cambia |
| `DELETE` | `/textos/{texto_id}/resaltados/{resaltado_id}` | Quitar resaltado |
| `POST` | `/textos/{texto_id}/revisar` | Volver un texto aprobado a revisión (se retira de los cursos) |
