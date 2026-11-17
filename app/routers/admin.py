"""Panel del administrador (RF-02, RF-04). Solo rol 'administrador' (RNF-05)."""

from fastapi import APIRouter, status

from app.core.deps import Admin, Conn
from app.schemas.admin import (ClaveGenerada, ClaveTemporal, LogroCambios, LogroNuevo, LogroSalida, ProfesorCambios,
                               ProfesorCreado, ProfesorNuevo, ProfesorSalida, ResumenAdmin)
from app.schemas.cursos import EstudianteAdmin
from app.schemas.seguimiento import Ajuste, NuevoValor
from app.services import admin_service as svc
from app.services import ajustes_service

router = APIRouter(prefix="/admin", tags=["administración"])


@router.get("/resumen", response_model=ResumenAdmin, summary="Totales de profesores y estudiantes (RF-04)")
async def resumen(_: Admin, conn: Conn):
    return await svc.resumen(conn)


@router.get("/profesores", response_model=list[ProfesorSalida], summary="Profesores registrados (RF-02, RF-04)")
async def listar_profesores(_: Admin, conn: Conn):
    return await svc.listar_profesores(conn)


@router.post("/profesores", response_model=ProfesorCreado, status_code=status.HTTP_201_CREATED,
             summary="Crear cuenta de profesor; usuario y clave temporal se generan si no se envían (RF-02)")
async def crear_profesor(datos: ProfesorNuevo, _: Admin, conn: Conn):
    return await svc.crear_profesor(conn, datos.nombre, datos.usuario, datos.clave)


@router.get("/profesores/{profesor_id}", response_model=ProfesorSalida, summary="Ver un profesor")
async def obtener_profesor(profesor_id: int, _: Admin, conn: Conn):
    return await svc.obtener_profesor(conn, profesor_id)


@router.patch("/profesores/{profesor_id}", response_model=ProfesorSalida,
              summary="Modificar nombre o activar/desactivar la cuenta (RF-02)")
async def actualizar_profesor(profesor_id: int, datos: ProfesorCambios, _: Admin, conn: Conn):
    return await svc.actualizar_profesor(conn, profesor_id, datos.nombre, datos.activo)


@router.post("/profesores/{profesor_id}/clave", response_model=ClaveGenerada,
             summary="Restablecer contraseña temporal y desbloquear; sin clave, el sistema la genera (RF-02)")
async def restablecer_clave(profesor_id: int, datos: ClaveTemporal, _: Admin, conn: Conn):
    return await svc.restablecer_clave(conn, profesor_id, datos.clave)


@router.get("/estudiantes", response_model=list[EstudianteAdmin], summary="Estudiantes registrados (RF-04)")
async def listar_estudiantes(_: Admin, conn: Conn):
    return await svc.listar_estudiantes(conn)


@router.get("/logros", response_model=list[LogroSalida], summary="Logros que se pueden ganar (RF-18)")
async def listar_logros(_: Admin, conn: Conn):
    return await svc.listar_logros(conn)


@router.post("/logros", response_model=LogroSalida, status_code=status.HTTP_201_CREATED,
             summary="Crear un logro con una de las reglas existentes (RF-18, RNF-08)")
async def crear_logro(datos: LogroNuevo, _: Admin, conn: Conn):
    return await svc.crear_logro(conn, datos.model_dump())


@router.patch("/logros/{logro_id}", response_model=LogroSalida,
              summary="Cambiar nombre, descripción o meta de un logro, o desactivarlo (RNF-08)")
async def actualizar_logro(logro_id: int, datos: LogroCambios, _: Admin, conn: Conn):
    return await svc.actualizar_logro(conn, logro_id, datos.model_dump(exclude_unset=True))


@router.get("/ajustes", response_model=list[Ajuste], summary="Valores generales: puntos, umbrales, modelo y prompts")
async def ajustes(_: Admin, conn: Conn):
    return await ajustes_service.generales(conn)


@router.put("/ajustes/{clave}", response_model=list[Ajuste],
            summary="Cambiar un valor general sin tocar código (RNF-08)")
async def guardar_ajuste(clave: str, datos: NuevoValor, yo: Admin, conn: Conn):
    return await ajustes_service.guardar_general(conn, yo.id, clave, datos.valor)
