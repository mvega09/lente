# Instalación (desarrollo)

```bash
sudo apt install -y python3-venv python3-pip git
cd ~/lente
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # y editar las claves
```

## Levantar la API

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- Documentación interactiva (Swagger): `http://<ip>:8000/docs`
- Comprobar base de datos: `GET /salud`

## Levantar el worker de IA

```bash
python -m worker.ia_worker
```

## Pruebas

```bash
pytest
```

## Documentación

```bash
mkdocs serve -a 0.0.0.0:8001   # vista previa
mkdocs gh-deploy               # publicar en GitHub Pages
```

## Producción

Los archivos de `deploy/` son servicios de systemd para la API y el worker.
