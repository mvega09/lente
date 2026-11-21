"""Biblioteca de textos y paquete de contenido (RF-09, RF-11, RF-12), resaltado
y modo explicación (RF-13, RF-14) y activación en cursos. Solo rol 'profesor'."""

from fastapi import APIRouter, Query, status

from app.core.deps import Conn, Profesor
from app.schemas.textos import (Activacion, EstadoTexto, PaqueteCambios, Palabra, PalabraNueva, Pregunta,
                                PreguntaCambios, PreguntaNueva, Resaltado, ResaltadoCambios, ResaltadoNuevo, TextoCambios,
                                TextoDetalle, TextoEnCurso, TextoNuevo, TextoResumen)
from app.services import textos_service as svc

router = APIRouter(tags=["textos"])
NC = status.HTTP_204_NO_CONTENT


# ---------------------------------------------------------------- textos

@router.get("/textos", response_model=list[TextoResumen], summary="Mi biblioteca de textos")
async def listar(yo: Profesor, conn: Conn, estado: EstadoTexto | None = Query(default=None)):
    return await svc.listar(conn, yo.id, estado)


@router.post("/textos", response_model=TextoDetalle, status_code=status.HTTP_201_CREATED,
             summary="Cargar un texto; con cuerpo, la IA prepara el paquete en segundo plano (RF-09)")
async def crear(datos: TextoNuevo, yo: Profesor, conn: Conn):
    return await svc.crear(conn, yo.id, datos.model_dump())


@router.get("/textos/{texto_id}", response_model=TextoDetalle, summary="Texto con su paquete, preguntas y palabras")
async def obtener(texto_id: int, yo: Profesor, conn: Conn):
    return await svc.obtener(conn, yo.id, texto_id)


@router.patch("/textos/{texto_id}", response_model=TextoDetalle, summary="Editar título, fuente, nota o enlace")
async def actualizar(texto_id: int, datos: TextoCambios, yo: Profesor, conn: Conn):
    return await svc.actualizar_datos(conn, yo.id, texto_id, datos.model_dump(exclude_unset=True))


@router.patch("/textos/{texto_id}/paquete", response_model=TextoDetalle,
              summary="Revisar la idea principal, los elementos clave y los consejos (RF-09)")
async def actualizar_paquete(texto_id: int, datos: PaqueteCambios, yo: Profesor, conn: Conn):
    return await svc.actualizar_paquete(conn, yo.id, texto_id, datos.model_dump(exclude_unset=True))


@router.post("/textos/{texto_id}/preparar", response_model=TextoDetalle,
             summary="Pedir a la IA que (re)prepare el paquete")
async def preparar(texto_id: int, yo: Profesor, conn: Conn):
    return await svc.preparar(conn, yo.id, texto_id)


@router.post("/textos/{texto_id}/aprobar", response_model=TextoDetalle,
             summary="Aprobar el paquete; sin idea principal no se aprueba (RF-09)")
async def aprobar(texto_id: int, yo: Profesor, conn: Conn):
    return await svc.aprobar(conn, yo.id, texto_id)


@router.post("/textos/{texto_id}/revisar", response_model=TextoDetalle,
             summary="Volver un texto aprobado a revisión (se retira de los cursos)")
async def volver_a_revision(texto_id: int, yo: Profesor, conn: Conn):
    return await svc.volver_a_revision(conn, yo.id, texto_id)


@router.delete("/textos/{texto_id}", response_model=TextoDetalle, summary="Archivar el texto")
async def archivar(texto_id: int, yo: Profesor, conn: Conn):
    return await svc.archivar(conn, yo.id, texto_id)

@router.delete("/textos/{texto_id}/definitivo", status_code=NC,
               summary="Borrar definitivamente un texto que ningún estudiante ha usado")
async def eliminar(texto_id: int, yo: Profesor, conn: Conn):
    await svc.eliminar(conn, yo.id, texto_id)


# ---------------------------------------------------------------- preguntas (superestructura)

@router.post("/textos/{texto_id}/preguntas", response_model=Pregunta, status_code=status.HTTP_201_CREATED,
             summary="Agregar pregunta orientadora de superestructura (RF-11)")
async def crear_pregunta(texto_id: int, datos: PreguntaNueva, yo: Profesor, conn: Conn):
    return await svc.crear_pregunta(conn, yo.id, texto_id, datos.model_dump())


@router.patch("/textos/{texto_id}/preguntas/{pregunta_id}", response_model=Pregunta, summary="Editar pregunta")
async def actualizar_pregunta(texto_id: int, pregunta_id: int, datos: PreguntaCambios, yo: Profesor, conn: Conn):
    return await svc.actualizar_pregunta(conn, yo.id, texto_id, pregunta_id, datos.model_dump(exclude_unset=True))


@router.delete("/textos/{texto_id}/preguntas/{pregunta_id}", status_code=NC, summary="Quitar pregunta")
async def borrar_pregunta(texto_id: int, pregunta_id: int, yo: Profesor, conn: Conn):
    await svc.borrar_pregunta(conn, yo.id, texto_id, pregunta_id)


# ---------------------------------------------------------------- palabras (microestructura)

@router.post("/textos/{texto_id}/palabras", response_model=Palabra, status_code=status.HTTP_201_CREATED,
             summary="Agregar palabra o expresión con carga emocional (RF-12)")
async def crear_palabra(texto_id: int, datos: PalabraNueva, yo: Profesor, conn: Conn):
    return await svc.crear_palabra(conn, yo.id, texto_id, datos.model_dump())


@router.delete("/textos/{texto_id}/palabras/{palabra_id}", status_code=NC, summary="Quitar palabra")
async def borrar_palabra(texto_id: int, palabra_id: int, yo: Profesor, conn: Conn):
    await svc.borrar_palabra(conn, yo.id, texto_id, palabra_id)


# ---------------------------------------------------------------- resaltado y explicación

@router.get("/textos/{texto_id}/resaltados", response_model=list[Resaltado],
            summary="Resaltados del modo explicación (RF-13, RF-14)")
async def listar_resaltados(texto_id: int, yo: Profesor, conn: Conn):
    return await svc.listar_resaltados(conn, yo.id, texto_id)


@router.post("/textos/{texto_id}/resaltados", response_model=Resaltado, status_code=status.HTTP_201_CREATED,
             summary="Resaltar un fragmento con su explicación; el texto original no cambia")
async def crear_resaltado(texto_id: int, datos: ResaltadoNuevo, yo: Profesor, conn: Conn):
    return await svc.crear_resaltado(conn, yo.id, texto_id, datos.model_dump())


@router.patch("/textos/{texto_id}/resaltados/{resaltado_id}", response_model=Resaltado,
              summary="Cambiar el nivel o la explicación de un resaltado (RF-14)")
async def actualizar_resaltado(texto_id: int, resaltado_id: int, datos: ResaltadoCambios, yo: Profesor, conn: Conn):
    return await svc.actualizar_resaltado(conn, yo.id, texto_id, resaltado_id, datos.model_dump(exclude_unset=True))


@router.delete("/textos/{texto_id}/resaltados/{resaltado_id}", status_code=NC, summary="Quitar resaltado")
async def borrar_resaltado(texto_id: int, resaltado_id: int, yo: Profesor, conn: Conn):
    await svc.borrar_resaltado(conn, yo.id, texto_id, resaltado_id)


# ---------------------------------------------------------------- textos en cursos

@router.get("/cursos/{curso_id}/textos", response_model=list[TextoEnCurso], summary="Textos del curso")
async def textos_del_curso(curso_id: int, yo: Profesor, conn: Conn):
    return await svc.textos_del_curso(conn, yo.id, curso_id)


@router.post("/cursos/{curso_id}/textos", status_code=NC,
             summary="Activar un texto aprobado en el curso")
async def activar(curso_id: int, datos: Activacion, yo: Profesor, conn: Conn):
    await svc.activar_en_curso(conn, yo.id, curso_id, datos.texto_id)


@router.delete("/cursos/{curso_id}/textos/{texto_id}", status_code=NC, summary="Retirar un texto del curso")
async def desactivar(curso_id: int, texto_id: int, yo: Profesor, conn: Conn):
    await svc.desactivar_en_curso(conn, yo.id, curso_id, texto_id)
