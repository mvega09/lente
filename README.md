# LENTE · Backend

API en **FastAPI** y worker de IA (**Ollama**) para la herramienta de
alfabetización mediática basada en el análisis crítico del discurso de
Teun van Dijk. Semillero · Universidad de Manizales.

## Inicio rápido

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # edite las claves
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Swagger: `http://<ip>:8000/docs`

Worker de IA: `python -m worker.ia_worker` · Pruebas: `pytest`

## Documentación

La documentación está en `docs/` (MkDocs Material):

```bash
mkdocs serve -a 0.0.0.0:8001
```
