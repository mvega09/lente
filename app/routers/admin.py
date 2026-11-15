"""Panel del administrador (RF-02, RF-04). Solo rol 'administrador' (RNF-05)."""

from fastapi import APIRouter, status

from app.core.deps import Admin, Conn
from app.schemas.admin import ClaveTemporal, ProfesorCambios, ProfesorNuevo, ProfesorSalida, ResumenAdmin
from app.schemas.cursos import EstudianteAdmin
from app.services import admin_service as svc

router = APIRouter(prefix="/admin", tags=["administración"])


@router.get("/resumen", response_model=ResumenAdmin, summary="Totales de profesores y estudiantes (RF-04)")
async def resumen(_: Admin, conn: Conn):
    return await svc.resumen(conn)


@router.get("/profesores", response_model=list[ProfesorSalida], summary="Profesores registrados (RF-02, RF-04)")
async def listar_profesores(_: Admin, conn: Conn):
    return await svc.listar_profesores(conn)


@router.post("/profesores", response_model=ProfesorSalida, status_code=status.HTTP_201_CREATED,
             summary="Crear cuenta de profesor (RF-02)")
async def crear_profesor(datos: ProfesorNuevo, _: Admin, conn: Conn):
    return await svc.crear_profesor(conn, datos.nombre, datos.usuario, datos.clave)


@router.get("/profesores/{profesor_id}", response_model=ProfesorSalida, summary="Ver un profesor")
async def obtener_profesor(profesor_id: int, _: Admin, conn: Conn):
    return await svc.obtener_profesor(conn, profesor_id)


@router.patch("/profesores/{profesor_id}", response_model=ProfesorSalida,
              summary="Modificar nombre o activar/desactivar la cuenta (RF-02)")
async def actualizar_profesor(profesor_id: int, datos: ProfesorCambios, _: Admin, conn: Conn):
    return await svc.actualizar_profesor(conn, profesor_id, datos.nombre, datos.activo)


@router.post("/profesores/{profesor_id}/clave", status_code=status.HTTP_204_NO_CONTENT,
             summary="Restablecer contraseña temporal y desbloquear (RF-02)")
async def restablecer_clave(profesor_id: int, datos: ClaveTemporal, _: Admin, conn: Conn):
    await svc.restablecer_clave(conn, profesor_id, datos.clave)


@router.get("/estudiantes", response_model=list[EstudianteAdmin], summary="Estudiantes registrados (RF-04)")
async def listar_estudiantes(_: Admin, conn: Conn):
    return await svc.listar_estudiantes(conn)
