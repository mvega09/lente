"""Seguimiento del profesor: progreso (RF-06), historial (RF-07), estadísticas
(RF-08), panel del curso y alertas de acompañamiento (RF-21).

Todo se filtra por el profesor de la sesión (RNF-05): el ánimo y las alertas
solo los ve el profesor del estudiante.
"""

from psycopg import AsyncConnection

from app.core.animo import ETIQUETAS, etiqueta
from app.core.db import uno, varios
from app.core.errores import NoEncontrado

SQL_PROGRESO = """
SELECT e.id, e.nombre, e.curso, e.grado_texto, e.nivel_escolar, e.puntos, e.nivel, e.racha, e.mejor_racha,
       p.actividades_hechas, p.actividades_pendientes, p.preguntas_respondidas, p.correctas, p.incorrectas,
       p.porcentaje_acierto, p.porcentaje_macro, p.porcentaje_super, p.porcentaje_micro,
       lente.ajuste('nombres_de_niveles', e.curso_id) AS nombres_niveles,
       lente.ultimo_animo(e.id) AS animo
  FROM lente.vista_estudiantes e
  JOIN lente.vista_progreso p ON p.estudiante_id = e.id
 WHERE e.id = %(id)s AND e.profesor_id = %(profesor)s
"""

SQL_EVOLUCION = """
SELECT a.id, t.titulo, a.numero, a.estado, a.resultado_macro, a.resultado_super, a.resultado_micro,
       a.puntos_ganados, a.iniciada_en, a.terminada_en
  FROM lente.actividades a JOIN lente.textos t ON t.id = a.texto_id
 WHERE a.estudiante_id = %(id)s
 ORDER BY a.iniciada_en
"""

SQL_LOGROS_ESTUDIANTE = """
SELECT l.nombre, l.descripcion, g.ganado_en
  FROM lente.logros_ganados g JOIN lente.logros l ON l.id = g.logro_id
 WHERE g.estudiante_id = %(id)s
 ORDER BY g.ganado_en
"""

SQL_HISTORIAL = """
SELECT h.actividad_id, h.titulo, h.fecha, h.nivel, h.pregunta, h.respuesta, h.respuesta_esperada,
       h.resultado, h.es_correcta
  FROM lente.vista_historial h
 WHERE h.estudiante_id = %(id)s
   AND EXISTS (SELECT 1 FROM lente.vista_estudiantes e WHERE e.id = %(id)s AND e.profesor_id = %(profesor)s)
 ORDER BY h.fecha DESC
 LIMIT %(limite)s OFFSET %(desde)s
"""

SQL_PANEL = """
SELECT vp.curso_id, vp.curso, vp.estudiantes_activos, vp.participaron, vp.acierto_promedio,
       vp.puntos_del_curso, vp.racha_mas_larga, vp.animo_alto, vp.animo_neutral, vp.animo_requiere_apoyo,
       (SELECT count(*) FROM lente.alertas al JOIN lente.estudiantes s ON s.id = al.estudiante_id
         WHERE s.curso_id = vp.curso_id AND NOT al.atendida) AS alertas_abiertas
  FROM lente.vista_panel vp
 WHERE vp.curso_id = %(curso)s AND vp.profesor_id = %(profesor)s
"""

SQL_DESTACADOS = """
SELECT id, nombre, puntos, nivel, racha
  FROM lente.vista_estudiantes
 WHERE curso_id = %(curso)s AND profesor_id = %(profesor)s AND estado <> 'Inactivo'
 ORDER BY puntos DESC, racha DESC, nombre
 LIMIT 5
"""

SQL_ALERTAS = """
SELECT al.id, al.estudiante_id, s.nombre AS estudiante, c.nombre AS curso, al.motivo, al.atendida,
       al.nota_profesor, al.creada_en, al.atendida_en
  FROM lente.alertas al
  JOIN lente.estudiantes s ON s.id = al.estudiante_id
  JOIN lente.cursos c ON c.id = s.curso_id
 WHERE c.profesor_id = %(profesor)s
   AND (%(atendida)s::boolean IS NULL OR al.atendida = %(atendida)s::boolean)
 ORDER BY al.atendida, al.creada_en DESC
"""

SQL_ATENDER_ALERTA = """
UPDATE lente.alertas al
   SET atendida = true, atendida_en = now(), nota_profesor = %(nota)s
  FROM lente.estudiantes s JOIN lente.cursos c ON c.id = s.curso_id
 WHERE al.id = %(id)s AND s.id = al.estudiante_id AND c.profesor_id = %(profesor)s AND NOT al.atendida
RETURNING al.id
"""


def nombre_nivel(nivel: int, nombres) -> str | None:
    if not isinstance(nombres, list) or not nombres:
        return None
    return str(nombres[min(max(nivel, 1), len(nombres)) - 1])


async def progreso(conn: AsyncConnection, profesor_id: int, estudiante_id: int) -> dict:
    p = await uno(conn, SQL_PROGRESO, {"id": estudiante_id, "profesor": profesor_id})
    if p is None:
        raise NoEncontrado("El estudiante")
    p["nivel_nombre"] = nombre_nivel(p["nivel"], p.pop("nombres_niveles"))
    p["animo"] = etiqueta(p["animo"])
    p["logros"] = await varios(conn, SQL_LOGROS_ESTUDIANTE, {"id": estudiante_id})
    p["evolucion"] = await varios(conn, SQL_EVOLUCION, {"id": estudiante_id})
    return p


async def historial(conn: AsyncConnection, profesor_id: int, estudiante_id: int,
                    limite: int, desde: int) -> list[dict]:
    filas = await varios(conn, SQL_HISTORIAL, {"id": estudiante_id, "profesor": profesor_id,
                                               "limite": limite, "desde": desde})
    if not filas and desde == 0:
        await progreso(conn, profesor_id, estudiante_id)      # 404 si no es su estudiante
    return filas


async def panel(conn: AsyncConnection, profesor_id: int, curso_id: int) -> dict:
    fila = await uno(conn, SQL_PANEL, {"curso": curso_id, "profesor": profesor_id})
    if fila is None:
        raise NoEncontrado("El curso")
    fila["clima"] = {
        ETIQUETAS["motivacion_alta"]: fila.pop("animo_alto"),
        ETIQUETAS["neutral"]: fila.pop("animo_neutral"),
        ETIQUETAS["requiere_apoyo"]: fila.pop("animo_requiere_apoyo"),
    }
    fila["destacados"] = await varios(conn, SQL_DESTACADOS, {"curso": curso_id, "profesor": profesor_id})
    return fila


async def alertas(conn: AsyncConnection, profesor_id: int, atendida: bool | None) -> list[dict]:
    return await varios(conn, SQL_ALERTAS, {"profesor": profesor_id, "atendida": atendida})


async def atender_alerta(conn: AsyncConnection, profesor_id: int, alerta_id: int, nota: str | None) -> None:
    if await uno(conn, SQL_ATENDER_ALERTA, {"id": alerta_id, "profesor": profesor_id, "nota": nota}) is None:
        raise NoEncontrado("La alerta abierta")
