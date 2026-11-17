"""Seguimiento del profesor: progreso, historial, panel, alertas y ajustes del curso."""

from typing import Annotated, Literal

from fastapi import APIRouter, Query, status

from app.core.deps import Conn, Profesor
from app.schemas.seguimiento import Ajuste, Alerta, AtenderAlerta, Historial, NuevoValor, Panel, Progreso
from app.services import ajustes_service, seguimiento_service as svc

router = APIRouter(tags=["seguimiento del profesor"])


@router.get("/estudiantes/{estudiante_id}/progreso", response_model=Progreso,
            summary="Progreso individual, estadísticas, logros y evolución (RF-06, RF-08, RF-18)")
async def progreso(estudiante_id: int, yo: Profesor, conn: Conn):
    return await svc.progreso(conn, yo.id, estudiante_id)


@router.get("/estudiantes/{estudiante_id}/historial", response_model=list[Historial],
            summary="Historial de respuestas del estudiante (RF-07)")
async def historial(estudiante_id: int, yo: Profesor, conn: Conn,
                    limite: Annotated[int, Query(ge=1, le=500)] = 100,
                    desde: Annotated[int, Query(ge=0)] = 0,
                    nivel: Annotated[Literal["macro", "super", "micro"] | None,
                                     Query(description="Solo un nivel; vacío = todos")] = None):
    return await svc.historial(conn, yo.id, estudiante_id, limite, desde, nivel)


@router.get("/cursos/{curso_id}/panel", response_model=Panel,
            summary="Panel del docente: participación, avance, recompensas y clima del curso")
async def panel(curso_id: int, yo: Profesor, conn: Conn):
    return await svc.panel(conn, yo.id, curso_id)


@router.get("/alertas", response_model=list[Alerta], summary="Alertas de acompañamiento (RF-21)")
async def alertas(yo: Profesor, conn: Conn, atendida: bool | None = None):
    return await svc.alertas(conn, yo.id, atendida)


@router.post("/alertas/{alerta_id}/atender", status_code=status.HTTP_204_NO_CONTENT,
             summary="Marcar la alerta como atendida, con una nota opcional")
async def atender(alerta_id: int, datos: AtenderAlerta, yo: Profesor, conn: Conn):
    await svc.atender_alerta(conn, yo.id, alerta_id, datos.nota_profesor)


@router.get("/cursos/{curso_id}/ajustes", response_model=list[Ajuste],
            summary="Reglas de puntos, niveles y alertas que usa el curso (RF-18, RNF-08)")
async def ajustes_curso(curso_id: int, yo: Profesor, conn: Conn):
    return await ajustes_service.del_curso(conn, yo.id, curso_id)


@router.put("/cursos/{curso_id}/ajustes/{clave}", response_model=list[Ajuste],
            summary="Cambiar una regla solo para este curso")
async def guardar_ajuste(curso_id: int, clave: str, datos: NuevoValor, yo: Profesor, conn: Conn):
    return await ajustes_service.guardar_en_curso(conn, yo.id, curso_id, clave, datos.valor)


@router.delete("/cursos/{curso_id}/ajustes/{clave}", response_model=list[Ajuste],
               summary="Volver al valor general de una regla")
async def quitar_ajuste(curso_id: int, clave: str, yo: Profesor, conn: Conn):
    return await ajustes_service.quitar_de_curso(conn, yo.id, curso_id, clave)
