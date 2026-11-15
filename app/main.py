"""Punto de entrada de la API de LENTE.

Desarrollo:  uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
Documentación interactiva: http://<ip>:8000/docs
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core import errores
from app.core.db import abrir_pool, cerrar_pool
from app.routers import actividades, admin, auth, cursos, salud, seguimiento, textos


@asynccontextmanager
async def lifespan(_: FastAPI):
    await abrir_pool()
    yield
    await cerrar_pool()


settings = get_settings()

app = FastAPI(
    title=settings.app_nombre,
    version="0.1.0",
    description="Backend de LENTE: análisis crítico del discurso (Van Dijk) asistido por IA.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origenes,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

errores.registrar(app)

app.include_router(salud.router)
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(cursos.router)
app.include_router(textos.router)
app.include_router(actividades.router)
app.include_router(seguimiento.router)


@app.get("/", tags=["salud"], summary="Información básica de la API")
def raiz() -> dict:
    return {"app": settings.app_nombre, "version": app.version, "docs": "/docs"}
