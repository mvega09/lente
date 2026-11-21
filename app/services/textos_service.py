"""Biblioteca de textos del profesor (RF-09) y su paquete de contenido.

Ciclo de vida de un texto:
  borrador → preparando (la IA trabaja) → en_revision → aprobado → archivado
- Al pasar a 'preparando', un trigger deja el trabajo en la cola de la IA.
- Solo se edita el paquete (idea, preguntas, palabras) en borrador o en revisión.
- Un texto no se aprueba sin idea principal (CHECK en la base).
- El cuerpo nunca se modifica. Si el texto llegó solo con enlace, el cuerpo se lee
  de la página al prepararlo (o el profesor lo pega una sola vez).
"""

from psycopg import AsyncConnection

from app.core.db import ejecutar, uno, varios
from app.core.errores import Conflicto, DatoInvalido, NoEncontrado
from app.services import extraccion

EDITABLES = ("borrador", "en_revision")

SQL_LISTAR_TEXTOS = """
SELECT t.id, t.tipo, t.titulo, t.fuente, t.nota, t.estado, t.preparado_por_ia, t.aprobado_en, t.creado_en
  FROM lente.textos t
 WHERE t.profesor_id = %(profesor)s
   AND (%(estado)s::text IS NULL OR t.estado = %(estado)s::text)
 ORDER BY t.creado_en DESC
"""

SQL_OBTENER_TEXTO = """
SELECT t.id, t.tipo, t.titulo, t.cuerpo, t.enlace, t.fuente, t.nota, t.estado,
       t.idea_principal, t.elementos_clave, t.consejo_macro, t.consejo_super, t.consejo_micro,
       t.preparado_por_ia, t.aprobado_en, t.creado_en
  FROM lente.textos t
 WHERE t.id = %(id)s AND t.profesor_id = %(profesor)s
"""

SQL_CREAR_TEXTO = """
INSERT INTO lente.textos (profesor_id, tipo, titulo, cuerpo, enlace, fuente, nota, estado)
VALUES (%(profesor)s, %(tipo)s, %(titulo)s, %(cuerpo)s, %(enlace)s, %(fuente)s, %(nota)s, %(estado)s)
RETURNING id
"""

SQL_ACTUALIZAR_DATOS = """
UPDATE lente.textos
   SET titulo = coalesce(%(titulo)s::text, titulo),
       cuerpo = CASE WHEN cuerpo IS NULL THEN %(cuerpo)s::text ELSE cuerpo END,
       enlace = coalesce(%(enlace)s::text, enlace),
       fuente = coalesce(%(fuente)s::text, fuente),
       nota   = coalesce(%(nota)s::text, nota)
 WHERE id = %(id)s AND profesor_id = %(profesor)s
RETURNING id
"""

SQL_ACTUALIZAR_PAQUETE = """
UPDATE lente.textos
   SET idea_principal  = coalesce(%(idea_principal)s::text, idea_principal),
       elementos_clave = coalesce(%(elementos_clave)s::text[], elementos_clave),
       consejo_macro   = coalesce(%(consejo_macro)s::text, consejo_macro),
       consejo_super   = coalesce(%(consejo_super)s::text, consejo_super),
       consejo_micro   = coalesce(%(consejo_micro)s::text, consejo_micro)
 WHERE id = %(id)s AND profesor_id = %(profesor)s AND estado IN ('borrador', 'en_revision')
RETURNING id
"""

# El cuerpo leído del enlace se guarda una sola vez (después ya no cambia)
SQL_PONER_CUERPO = """
UPDATE lente.textos SET cuerpo = %(cuerpo)s
 WHERE id = %(id)s AND profesor_id = %(profesor)s AND cuerpo IS NULL AND estado IN ('borrador', 'en_revision')
RETURNING id
"""

SQL_CAMBIAR_ESTADO = """
UPDATE lente.textos
   SET estado = %(nuevo)s::text,
       aprobado_en = CASE WHEN %(nuevo)s::text = 'aprobado' THEN now() ELSE aprobado_en END
 WHERE id = %(id)s AND profesor_id = %(profesor)s AND estado = ANY(%(desde)s::text[])
RETURNING id
"""

SQL_ACTIVIDADES_DEL_TEXTO = "SELECT count(*) AS n FROM lente.actividades WHERE texto_id = %(id)s"

# Borra el texto con sus preguntas, palabras, resaltados, activaciones y trabajos de IA (ON DELETE CASCADE)
SQL_BORRAR_TEXTO = """
DELETE FROM lente.textos WHERE id = %(id)s AND profesor_id = %(profesor)s
RETURNING id
"""

SQL_RETIRAR_DE_CURSOS = """
UPDATE lente.textos_del_curso SET activo = false
 WHERE texto_id = %(id)s AND activo
   AND texto_id IN (SELECT id FROM lente.textos WHERE profesor_id = %(profesor)s)
"""

# ---------------------------------------------------------------- preguntas

_DEL_PROFESOR_EDITABLE = """
  FROM lente.textos t
 WHERE t.id = %(texto)s AND t.profesor_id = %(profesor)s AND t.estado IN ('borrador', 'en_revision')
"""

SQL_PREGUNTAS = """
SELECT q.id, q.orden, q.pregunta, q.opciones, q.correcta, q.dificultad
  FROM lente.preguntas q JOIN lente.textos t ON t.id = q.texto_id
 WHERE q.texto_id = %(texto)s AND t.profesor_id = %(profesor)s
 ORDER BY q.orden
"""

SQL_CREAR_PREGUNTA = """
INSERT INTO lente.preguntas (texto_id, orden, pregunta, opciones, correcta, dificultad)
SELECT t.id,
       coalesce(%(orden)s::smallint,
                (SELECT coalesce(max(orden), 0) + 1 FROM lente.preguntas WHERE texto_id = t.id)::smallint),
       %(pregunta)s, %(opciones)s::text[], %(correcta)s, %(dificultad)s
""" + _DEL_PROFESOR_EDITABLE + """
RETURNING id, orden, pregunta, opciones, correcta, dificultad
"""

SQL_ACTUALIZAR_PREGUNTA = """
UPDATE lente.preguntas q
   SET pregunta   = coalesce(%(pregunta)s::text, q.pregunta),
       opciones   = coalesce(%(opciones)s::text[], q.opciones),
       correcta   = coalesce(%(correcta)s::smallint, q.correcta),
       dificultad = coalesce(%(dificultad)s::smallint, q.dificultad)
  FROM lente.textos t
 WHERE q.id = %(id)s AND q.texto_id = %(texto)s AND t.id = q.texto_id
   AND t.profesor_id = %(profesor)s AND t.estado IN ('borrador', 'en_revision')
RETURNING q.id, q.orden, q.pregunta, q.opciones, q.correcta, q.dificultad
"""

SQL_BORRAR_PREGUNTA = """
DELETE FROM lente.preguntas q USING lente.textos t
 WHERE q.id = %(id)s AND q.texto_id = %(texto)s AND t.id = q.texto_id
   AND t.profesor_id = %(profesor)s AND t.estado IN ('borrador', 'en_revision')
RETURNING q.id
"""

# ---------------------------------------------------------------- palabras cargadas

SQL_PALABRAS = """
SELECT p.id, p.palabra, p.tipo, p.inicio, p.fin, p.explicacion
  FROM lente.palabras_cargadas p JOIN lente.textos t ON t.id = p.texto_id
 WHERE p.texto_id = %(texto)s AND t.profesor_id = %(profesor)s
 ORDER BY p.inicio
"""

SQL_CREAR_PALABRA = """
INSERT INTO lente.palabras_cargadas (texto_id, palabra, tipo, inicio, fin, explicacion)
SELECT t.id, %(palabra)s, %(tipo)s, %(inicio)s, %(fin)s, %(explicacion)s
""" + _DEL_PROFESOR_EDITABLE + """
RETURNING id, palabra, tipo, inicio, fin, explicacion
"""

SQL_BORRAR_PALABRA = """
DELETE FROM lente.palabras_cargadas p USING lente.textos t
 WHERE p.id = %(id)s AND p.texto_id = %(texto)s AND t.id = p.texto_id
   AND t.profesor_id = %(profesor)s AND t.estado IN ('borrador', 'en_revision')
RETURNING p.id
"""

# ---------------------------------------------------------------- resaltados (RF-13, RF-14)

SQL_RESALTADOS = """
SELECT r.id, r.nivel, r.inicio, r.fin, r.fragmento, r.explicacion, r.es_idea_principal, r.creado_en
  FROM lente.resaltados r JOIN lente.textos t ON t.id = r.texto_id
 WHERE r.texto_id = %(texto)s AND t.profesor_id = %(profesor)s
 ORDER BY r.inicio
"""

# El fragmento se copia del cuerpo: el texto original nunca se altera
SQL_CREAR_RESALTADO = """
INSERT INTO lente.resaltados (texto_id, nivel, inicio, fin, fragmento, explicacion, es_idea_principal)
SELECT t.id, %(nivel)s, %(inicio)s, %(fin)s,
       substr(t.cuerpo, %(inicio)s::int + 1, %(fin)s::int - %(inicio)s::int),
       %(explicacion)s, %(es_idea_principal)s
  FROM lente.textos t
 WHERE t.id = %(texto)s AND t.profesor_id = %(profesor)s
   AND t.cuerpo IS NOT NULL AND %(fin)s::int <= length(t.cuerpo)
RETURNING id, nivel, inicio, fin, fragmento, explicacion, es_idea_principal, creado_en
"""

SQL_ACTUALIZAR_RESALTADO = """
UPDATE lente.resaltados r
   SET nivel = coalesce(%(nivel)s::text, r.nivel),
       explicacion = CASE WHEN %(cambiar_explicacion)s::boolean THEN %(explicacion)s::text ELSE r.explicacion END,
       es_idea_principal = coalesce(%(es_idea_principal)s::boolean, r.es_idea_principal)
  FROM lente.textos t
 WHERE r.id = %(id)s AND r.texto_id = %(texto)s AND t.id = r.texto_id AND t.profesor_id = %(profesor)s
RETURNING r.id, r.nivel, r.inicio, r.fin, r.fragmento, r.explicacion, r.es_idea_principal, r.creado_en
"""

SQL_BORRAR_RESALTADO = """
DELETE FROM lente.resaltados r USING lente.textos t
 WHERE r.id = %(id)s AND r.texto_id = %(texto)s AND t.id = r.texto_id AND t.profesor_id = %(profesor)s
RETURNING r.id
"""

# ---------------------------------------------------------------- textos en cursos

SQL_TEXTOS_CURSO = """
SELECT t.id, t.titulo, t.tipo, t.fuente, tc.activo, tc.activado_en
  FROM lente.textos_del_curso tc
  JOIN lente.textos t ON t.id = tc.texto_id
  JOIN lente.cursos c ON c.id = tc.curso_id
 WHERE tc.curso_id = %(curso)s AND c.profesor_id = %(profesor)s
 ORDER BY tc.activo DESC, tc.activado_en DESC
"""

# El trigger texto_activar exige que el texto esté aprobado y sea del mismo profesor
SQL_ACTIVAR_EN_CURSO = """
INSERT INTO lente.textos_del_curso (curso_id, texto_id)
SELECT c.id, %(texto)s FROM lente.cursos c
 WHERE c.id = %(curso)s AND c.profesor_id = %(profesor)s
ON CONFLICT (curso_id, texto_id) DO UPDATE SET activo = true, activado_en = now()
RETURNING curso_id
"""

SQL_DESACTIVAR_EN_CURSO = """
UPDATE lente.textos_del_curso tc SET activo = false
  FROM lente.cursos c
 WHERE tc.curso_id = c.id AND c.id = %(curso)s AND c.profesor_id = %(profesor)s
   AND tc.texto_id = %(texto)s
RETURNING tc.texto_id
"""


# ================================================================ funciones

async def listar(conn: AsyncConnection, profesor_id: int, estado: str | None) -> list[dict]:
    return await varios(conn, SQL_LISTAR_TEXTOS, {"profesor": profesor_id, "estado": estado})


async def obtener(conn: AsyncConnection, profesor_id: int, texto_id: int, completo: bool = True) -> dict:
    p = {"id": texto_id, "profesor": profesor_id}
    texto = await uno(conn, SQL_OBTENER_TEXTO, p)
    if texto is None:
        raise NoEncontrado("El texto")
    if completo:
        q = {"texto": texto_id, "profesor": profesor_id}
        texto["preguntas"] = await varios(conn, SQL_PREGUNTAS, q)
        texto["palabras"] = await varios(conn, SQL_PALABRAS, q)
    return texto


async def crear(conn: AsyncConnection, profesor_id: int, datos: dict) -> dict:
    cuerpo = (datos.get("cuerpo") or "").strip() or None
    enlace = (datos.get("enlace") or "").strip() or None
    quiere_ia = datos.pop("preparar_con_ia", True)
    nota = datos.get("nota")
    if cuerpo is None and enlace and quiere_ia:
        # Solo enlace: se lee la noticia de la página para que la IA pueda prepararla
        try:
            cuerpo = await extraccion.texto_desde_enlace(enlace)
        except extraccion.NoSePudoLeer as e:
            nota = f"No se pudo leer la noticia del enlace: {e.mensaje}. Pegue el texto."[:300]
    params = {**datos, "cuerpo": cuerpo, "enlace": enlace, "nota": nota, "profesor": profesor_id,
              "estado": "preparando" if quiere_ia and cuerpo is not None else "borrador"}
    nuevo = await uno(conn, SQL_CREAR_TEXTO, params)
    return await obtener(conn, profesor_id, nuevo["id"])


async def actualizar_datos(conn: AsyncConnection, profesor_id: int, texto_id: int, cambios: dict) -> dict:
    params = {"id": texto_id, "profesor": profesor_id, "titulo": None, "enlace": None, "fuente": None, "nota": None,
              "cuerpo": None}
    params.update(cambios)
    if params["cuerpo"] is not None:
        params["cuerpo"] = params["cuerpo"].strip() or None
    if await uno(conn, SQL_ACTUALIZAR_DATOS, params) is None:
        raise NoEncontrado("El texto")
    return await obtener(conn, profesor_id, texto_id)


async def _exigir_editable(conn: AsyncConnection, profesor_id: int, texto_id: int) -> None:
    """Distingue 'no existe' (404) de 'no se puede editar en este estado' (409)."""
    texto = await obtener(conn, profesor_id, texto_id, completo=False)
    if texto["estado"] not in EDITABLES:
        raise Conflicto(f"El texto está '{texto['estado']}': solo se edita en borrador o en revisión")


async def actualizar_paquete(conn: AsyncConnection, profesor_id: int, texto_id: int, cambios: dict) -> dict:
    params = {"id": texto_id, "profesor": profesor_id, "idea_principal": None, "elementos_clave": None,
              "consejo_macro": None, "consejo_super": None, "consejo_micro": None}
    params.update(cambios)
    if await uno(conn, SQL_ACTUALIZAR_PAQUETE, params) is None:
        await _exigir_editable(conn, profesor_id, texto_id)
    return await obtener(conn, profesor_id, texto_id)


async def _cambiar_estado(conn: AsyncConnection, profesor_id: int, texto_id: int,
                          nuevo: str, desde: tuple[str, ...], mensaje: str) -> dict:
    params = {"id": texto_id, "profesor": profesor_id, "nuevo": nuevo, "desde": list(desde)}
    if await uno(conn, SQL_CAMBIAR_ESTADO, params) is None:
        await obtener(conn, profesor_id, texto_id, completo=False)     # 404 si no existe
        raise Conflicto(mensaje)
    return await obtener(conn, profesor_id, texto_id)


async def preparar(conn: AsyncConnection, profesor_id: int, texto_id: int) -> dict:
    texto = await obtener(conn, profesor_id, texto_id, completo=False)
    if not texto["cuerpo"]:
        if not texto["enlace"]:
            raise Conflicto("El texto no tiene cuerpo ni enlace: la IA no puede prepararlo")
        if texto["estado"] not in EDITABLES:
            raise Conflicto("Solo se manda a la IA un texto en borrador o en revisión")
        try:
            cuerpo = await extraccion.texto_desde_enlace(texto["enlace"])
        except extraccion.NoSePudoLeer as e:
            raise DatoInvalido(f"No se pudo leer la noticia del enlace: {e.mensaje}. "
                               "Pegue el texto de la noticia en el campo cuerpo.") from None
        await uno(conn, SQL_PONER_CUERPO, {"id": texto_id, "profesor": profesor_id, "cuerpo": cuerpo})
    return await _cambiar_estado(conn, profesor_id, texto_id, "preparando", EDITABLES,
                                 "Solo se manda a la IA un texto en borrador o en revisión")


async def aprobar(conn: AsyncConnection, profesor_id: int, texto_id: int) -> dict:
    return await _cambiar_estado(conn, profesor_id, texto_id, "aprobado", EDITABLES,
                                 "Solo se aprueba un texto en borrador o en revisión")


async def volver_a_revision(conn: AsyncConnection, profesor_id: int, texto_id: int) -> dict:
    """Permite corregir un texto aprobado. Se retira de los cursos mientras tanto."""
    await ejecutar(conn, SQL_RETIRAR_DE_CURSOS, {"id": texto_id, "profesor": profesor_id})
    return await _cambiar_estado(conn, profesor_id, texto_id, "en_revision", ("aprobado",),
                                 "Solo un texto aprobado vuelve a revisión")


async def archivar(conn: AsyncConnection, profesor_id: int, texto_id: int) -> dict:
    # Primero se retira de los cursos (el trigger exige que siga aprobado al tocarlo)
    await ejecutar(conn, SQL_RETIRAR_DE_CURSOS, {"id": texto_id, "profesor": profesor_id})
    return await _cambiar_estado(conn, profesor_id, texto_id, "archivado",
                                 ("borrador", "en_revision", "aprobado"),
                                 "Este texto no se puede archivar en su estado actual")


async def eliminar(conn: AsyncConnection, profesor_id: int, texto_id: int) -> None:
    """Borra definitivamente un texto que ningún estudiante ha usado.

    Si ya tiene actividades, se conserva para no perder el historial de los estudiantes
    (RF-07, RNF-04): en ese caso solo se puede archivar.
    """
    texto = await obtener(conn, profesor_id, texto_id, completo=False)        # 404 si no es suyo
    if texto["estado"] == "preparando":
        raise Conflicto("La IA está preparando este texto; espere a que termine para borrarlo")
    if (await uno(conn, SQL_ACTIVIDADES_DEL_TEXTO, {"id": texto_id}))["n"]:
        raise Conflicto("Este texto ya tiene actividades de estudiantes y no se puede borrar "
                        "sin perder su historial. Archívelo para ocultarlo")
    await uno(conn, SQL_BORRAR_TEXTO, {"id": texto_id, "profesor": profesor_id})


# ---------------------------------------------------------------- preguntas

async def crear_pregunta(conn: AsyncConnection, profesor_id: int, texto_id: int, datos: dict) -> dict:
    fila = await uno(conn, SQL_CREAR_PREGUNTA, {**datos, "texto": texto_id, "profesor": profesor_id})
    if fila is None:
        await _exigir_editable(conn, profesor_id, texto_id)
        raise NoEncontrado("El texto")
    return fila


async def actualizar_pregunta(conn: AsyncConnection, profesor_id: int, texto_id: int,
                              pregunta_id: int, cambios: dict) -> dict:
    params = {"id": pregunta_id, "texto": texto_id, "profesor": profesor_id,
              "pregunta": None, "opciones": None, "correcta": None, "dificultad": None}
    params.update(cambios)
    fila = await uno(conn, SQL_ACTUALIZAR_PREGUNTA, params)
    if fila is None:
        await _exigir_editable(conn, profesor_id, texto_id)
        raise NoEncontrado("La pregunta")
    if not 1 <= fila["correcta"] <= len(fila["opciones"]):
        raise DatoInvalido("La opción correcta no está entre las opciones")
    return fila


async def borrar_pregunta(conn: AsyncConnection, profesor_id: int, texto_id: int, pregunta_id: int) -> None:
    if await uno(conn, SQL_BORRAR_PREGUNTA, {"id": pregunta_id, "texto": texto_id, "profesor": profesor_id}) is None:
        await _exigir_editable(conn, profesor_id, texto_id)
        raise NoEncontrado("La pregunta")


# ---------------------------------------------------------------- palabras

def ubicar_palabra(cuerpo: str, palabra: str, inicio: int | None, ocupadas: set[int]) -> int:
    """Devuelve la posición de la palabra en el cuerpo, comprobando que esté ahí de verdad."""
    if inicio is not None:
        if cuerpo[inicio:inicio + len(palabra)] != palabra:
            raise DatoInvalido("La palabra no está en esa posición del texto")
        return inicio
    pos = cuerpo.find(palabra)
    while pos >= 0 and pos in ocupadas:
        pos = cuerpo.find(palabra, pos + 1)
    if pos < 0:
        raise DatoInvalido("La palabra no aparece (tal cual) en el texto")
    return pos


async def crear_palabra(conn: AsyncConnection, profesor_id: int, texto_id: int, datos: dict) -> dict:
    texto = await obtener(conn, profesor_id, texto_id)
    if texto["estado"] not in EDITABLES:
        raise Conflicto(f"El texto está '{texto['estado']}': solo se edita en borrador o en revisión")
    if not texto["cuerpo"]:
        raise Conflicto("El texto no tiene cuerpo")
    ocupadas = {p["inicio"] for p in texto["palabras"]}
    inicio = ubicar_palabra(texto["cuerpo"], datos["palabra"], datos.get("inicio"), ocupadas)
    params = {"texto": texto_id, "profesor": profesor_id, "palabra": datos["palabra"], "tipo": datos["tipo"],
              "inicio": inicio, "fin": inicio + len(datos["palabra"]), "explicacion": datos.get("explicacion")}
    return await uno(conn, SQL_CREAR_PALABRA, params)


async def borrar_palabra(conn: AsyncConnection, profesor_id: int, texto_id: int, palabra_id: int) -> None:
    if await uno(conn, SQL_BORRAR_PALABRA, {"id": palabra_id, "texto": texto_id, "profesor": profesor_id}) is None:
        await _exigir_editable(conn, profesor_id, texto_id)
        raise NoEncontrado("La palabra")


# ---------------------------------------------------------------- resaltados

async def listar_resaltados(conn: AsyncConnection, profesor_id: int, texto_id: int) -> list[dict]:
    await obtener(conn, profesor_id, texto_id, completo=False)
    return await varios(conn, SQL_RESALTADOS, {"texto": texto_id, "profesor": profesor_id})


async def crear_resaltado(conn: AsyncConnection, profesor_id: int, texto_id: int, datos: dict) -> dict:
    fila = await uno(conn, SQL_CREAR_RESALTADO, {**datos, "texto": texto_id, "profesor": profesor_id})
    if fila is None:
        texto = await obtener(conn, profesor_id, texto_id, completo=False)
        if not texto["cuerpo"]:
            raise Conflicto("El texto no tiene cuerpo para resaltar")
        raise DatoInvalido("El fragmento se sale del texto")
    return fila


async def actualizar_resaltado(conn: AsyncConnection, profesor_id: int, texto_id: int,
                               resaltado_id: int, cambios: dict) -> dict:
    params = {"id": resaltado_id, "texto": texto_id, "profesor": profesor_id,
              "nivel": cambios.get("nivel"), "es_idea_principal": cambios.get("es_idea_principal"),
              "cambiar_explicacion": "explicacion" in cambios, "explicacion": cambios.get("explicacion")}
    fila = await uno(conn, SQL_ACTUALIZAR_RESALTADO, params)
    if fila is None:
        raise NoEncontrado("El resaltado")
    return fila


async def borrar_resaltado(conn: AsyncConnection, profesor_id: int, texto_id: int, resaltado_id: int) -> None:
    if await uno(conn, SQL_BORRAR_RESALTADO,
                 {"id": resaltado_id, "texto": texto_id, "profesor": profesor_id}) is None:
        raise NoEncontrado("El resaltado")


# ---------------------------------------------------------------- textos en cursos

async def textos_del_curso(conn: AsyncConnection, profesor_id: int, curso_id: int) -> list[dict]:
    return await varios(conn, SQL_TEXTOS_CURSO, {"curso": curso_id, "profesor": profesor_id})


async def activar_en_curso(conn: AsyncConnection, profesor_id: int, curso_id: int, texto_id: int) -> None:
    if await uno(conn, SQL_ACTIVAR_EN_CURSO,
                 {"curso": curso_id, "texto": texto_id, "profesor": profesor_id}) is None:
        raise NoEncontrado("El curso")


async def desactivar_en_curso(conn: AsyncConnection, profesor_id: int, curso_id: int, texto_id: int) -> None:
    if await uno(conn, SQL_DESACTIVAR_EN_CURSO,
                 {"curso": curso_id, "texto": texto_id, "profesor": profesor_id}) is None:
        raise NoEncontrado("El texto en ese curso")
