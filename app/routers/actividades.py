"""Actividad de análisis del estudiante (RF-10 a RF-17, RF-19, RNF-03).

Modo aula: el profesor abre la actividad para un estudiante y este responde
en el mismo dispositivo. Orden obligatorio: macro → super → micro → resultado.
"""

from fastapi import APIRouter, status

from app.core.deps import Conn, Profesor
from app.schemas.actividades import (ActividadNueva, ActividadVista, EstadoMacro, EstadoSuper, Recibido,
                                     RespuestaMacro, RespuestaMicro, RespuestaSuper, ResultadoActividad)
from app.services import actividades_service as svc

router = APIRouter(prefix="/actividades", tags=["actividad del estudiante"])


@router.post("", response_model=ActividadVista, status_code=status.HTTP_201_CREATED,
             summary="Abrir (o retomar) la actividad de un estudiante con un texto activo")
async def abrir(datos: ActividadNueva, yo: Profesor, conn: Conn):
    return await svc.abrir(conn, yo.id, datos.estudiante_id, datos.texto_id)


@router.get("/{actividad_id}", response_model=ActividadVista,
            summary="Estado de la actividad: paso actual, texto e instrucción según el grado")
async def ver(actividad_id: int, yo: Profesor, conn: Conn):
    return await svc.ver(conn, yo.id, actividad_id)


@router.post("/{actividad_id}/macro", response_model=EstadoMacro,
             summary="Enviar la idea principal; la IA la revisa en segundo plano (RF-10)")
async def responder_macro(actividad_id: int, datos: RespuestaMacro, yo: Profesor, conn: Conn):
    return await svc.responder_macro(conn, yo.id, actividad_id, datos.texto, datos.codigo_envio, datos.enviada_en)


@router.get("/{actividad_id}/macro", response_model=EstadoMacro,
            summary="Consultar la revisión de la idea principal ('analizando' mientras la IA trabaja)")
async def estado_macro(actividad_id: int, yo: Profesor, conn: Conn):
    return await svc.estado_macro(conn, yo.id, actividad_id)


@router.post("/{actividad_id}/super", response_model=EstadoSuper,
             summary="Responder las preguntas de superestructura (RF-11)")
async def responder_super(actividad_id: int, datos: RespuestaSuper, yo: Profesor, conn: Conn):
    return await svc.responder_super(conn, yo.id, actividad_id,
                                     [r.model_dump() for r in datos.respuestas], datos.enviada_en)


@router.post("/{actividad_id}/micro", response_model=Recibido,
             summary="Marcar palabras y expresiones con carga emocional (RF-12)")
async def responder_micro(actividad_id: int, datos: RespuestaMicro, yo: Profesor, conn: Conn):
    return await svc.responder_micro(conn, yo.id, actividad_id,
                                     [m.model_dump() for m in datos.marcas], datos.enviada_en)


@router.delete("/{actividad_id}/micro/{inicio}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Quitar una marca antes de terminar")
async def quitar_marca(actividad_id: int, inicio: int, yo: Profesor, conn: Conn):
    await svc.quitar_marca(conn, yo.id, actividad_id, inicio)


@router.post("/{actividad_id}/terminar", response_model=ResultadoActividad,
             summary="«Ver mi resultado»: calcula resultados, puntos, racha y logros (RF-16, RF-17, RF-18)")
async def terminar(actividad_id: int, yo: Profesor, conn: Conn):
    return await svc.terminar(conn, yo.id, actividad_id)


@router.get("/{actividad_id}/resultado", response_model=ResultadoActividad,
            summary="Resultado de una actividad terminada (RF-16)")
async def resultado(actividad_id: int, yo: Profesor, conn: Conn):
    return await svc.resultado(conn, yo.id, actividad_id)
