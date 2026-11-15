# API

FastAPI genera la referencia completa automáticamente en `/docs` (Swagger) y
`/redoc`. Aquí se resumen los endpoints disponibles.

| Método | Ruta | Descripción | Autenticación |
|---|---|---|---|
| GET | `/` | Información básica | No |
| GET | `/salud` | Comprueba API y base de datos | No |
| POST | `/auth/login` | Inicio de sesión (usa `lente.iniciar_sesion`) | No |
| GET | `/auth/yo` | Usuario de la sesión | Bearer |

## Inicio de sesión

```http
POST /auth/login
{"usuario": "admin", "clave": "..."}
```

Respuesta: `access_token` (JWT) y los datos del usuario. Envíe el token en
la cabecera `Authorization: Bearer <token>`. Tras 5 intentos fallidos la
cuenta queda bloqueada (regla de la base de datos).

## Pendiente

- Cursos y estudiantes del profesor
- Biblioteca de textos y aprobación de lo preparado por la IA
- Actividad del estudiante (macro → super → micro → resultado)
- Panel del docente (`vista_panel`, `vista_progreso`, `vista_historial`)
