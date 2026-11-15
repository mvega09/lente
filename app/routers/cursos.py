"""Cursos y estudiantes del profesor (RF-03, RF-05, RF-20). Solo rol 'profesor'."""

from fastapi import APIRouter, status

from app.core.deps import Conn, Profesor
from app.schemas.cursos import (CursoCambios, CursoNuevo, CursoSalida, EstudianteCambios,
                                EstudianteNuevo, EstudianteSalida)
from app.services import cursos_service as svc

router = APIRouter(tags=["cursos y estudiantes"])


@router.get("/cursos", response_model=list[CursoSalida], summary="Mis cursos")
async def listar_cursos(yo: Profesor, conn: Conn):
    return await svc.listar_cursos(conn, yo.id)


@router.post("/cursos", response_model=CursoSalida, status_code=status.HTTP_201_CREATED, summary="Crear curso")
async def crear_curso(datos: CursoNuevo, yo: Profesor, conn: Conn):
    return await svc.crear_curso(conn, yo.id, datos.nombre, datos.institucion, datos.anio)


@router.get("/cursos/{curso_id}", response_model=CursoSalida, summary="Ver un curso")
async def obtener_curso(curso_id: int, yo: Profesor, conn: Conn):
    return await svc.obtener_curso(conn, yo.id, curso_id)


@router.patch("/cursos/{curso_id}", response_model=CursoSalida, summary="Modificar o desactivar un curso")
async def actualizar_curso(curso_id: int, datos: CursoCambios, yo: Profesor, conn: Conn):
    return await svc.actualizar_curso(conn, yo.id, curso_id, datos.model_dump(exclude_unset=True))


@router.get("/cursos/{curso_id}/estudiantes", response_model=list[EstudianteSalida],
            summary="Estudiantes del curso (RF-05)")
async def listar_estudiantes(curso_id: int, yo: Profesor, conn: Conn):
    return await svc.listar_estudiantes(conn, yo.id, curso_id)


@router.post("/cursos/{curso_id}/estudiantes", response_model=EstudianteSalida,
             status_code=status.HTTP_201_CREATED, summary="Agregar estudiante solo con su nombre (RF-03)")
async def crear_estudiante(curso_id: int, datos: EstudianteNuevo, yo: Profesor, conn: Conn):
    return await svc.crear_estudiante(conn, yo.id, curso_id, datos.nombre, datos.grado)


@router.get("/estudiantes/{estudiante_id}", response_model=EstudianteSalida, summary="Ver un estudiante")
async def obtener_estudiante(estudiante_id: int, yo: Profesor, conn: Conn):
    return await svc.obtener_estudiante(conn, yo.id, estudiante_id)


@router.patch("/estudiantes/{estudiante_id}", response_model=EstudianteSalida,
              summary="Editar nombre, grado (RF-20), curso o activar/desactivar (RF-03)")
async def actualizar_estudiante(estudiante_id: int, datos: EstudianteCambios, yo: Profesor, conn: Conn):
    return await svc.actualizar_estudiante(conn, yo.id, estudiante_id, datos.model_dump(exclude_unset=True))


@router.delete("/estudiantes/{estudiante_id}", response_model=EstudianteSalida,
               summary="Desactivar estudiante (se conserva su historial)")
async def desactivar_estudiante(estudiante_id: int, yo: Profesor, conn: Conn):
    return await svc.actualizar_estudiante(conn, yo.id, estudiante_id, {"activo": False})
