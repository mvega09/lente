# LENTE · Backend

Backend de la herramienta de alfabetización mediática del Semillero de la
Universidad de Manizales. Los estudiantes analizan noticias con el modelo de
análisis crítico del discurso de **Teun van Dijk** (macro, super y
microestructura) y una IA local (Ollama) revisa la idea principal.

| Pieza | Tecnología |
|---|---|
| API | Python 3.12 + FastAPI |
| Acceso a datos | psycopg 3 (SQL directo, sin ORM) |
| Base de datos | PostgreSQL 16 (esquema `lente`) |
| IA | Ollama (Qwen3) con salida estructurada |
| Frontend | Repositorio aparte (tecnología por definir) |

- [Instalación](instalacion.md)
- [Arquitectura](arquitectura.md)
- [API](api.md)
- [Worker de IA](worker.md)
