"""Datos que piden las pantallas del prototipo (B1 a B6 de la revisión del 16-nov-2026)."""

import asyncio
import re

from app.services import admin_service, cursos_service, seguimiento_service, textos_service
from tests.conftest import ConexionFalsa, cabeceras


# ---------------------------------------------------------------- B1 · panel con avance por nivel

def test_panel_trae_avance_promedio_por_nivel():
    fila = {"curso_id": 2, "curso": "7°B", "estudiantes_activos": 30, "participaron": 20, "acierto_promedio": 70,
            "puntos_del_curso": 900, "racha_mas_larga": 4, "animo_alto": 1, "animo_neutral": 2,
            "animo_requiere_apoyo": 0, "alertas_abiertas": 0,
            "avance_macro": 64, "avance_super": 71, "avance_micro": None}
    salida = asyncio.run(seguimiento_service.panel(ConexionFalsa(fila, []), 7, 2))
    assert (salida["avance_macro"], salida["avance_super"], salida["avance_micro"]) == (64, 71, None)
    assert "x.activo" in seguimiento_service.SQL_PANEL          # solo estudiantes activos


# ---------------------------------------------------------------- B2 · lista con barras por nivel

def test_lista_de_estudiantes_incluye_avance_por_nivel():
    assert "p.porcentaje_macro" in cursos_service.SQL_ESTUDIANTES_CURSO
    assert "LEFT JOIN lente.vista_progreso" in cursos_service.SQL_ESTUDIANTES_CURSO    # sin actividades también salen
    assert "e.profesor_id = %(profesor)s" in cursos_service.SQL_OBTENER_ESTUDIANTE


# ---------------------------------------------------------------- B3 · pendientes con título

def test_progreso_lista_los_textos_pendientes():
    fila = {"id": 1, "nombre": "Ana", "curso": "7°B", "grado_texto": "7°", "nivel_escolar": "secundaria",
            "puntos": 40, "nivel": 1, "racha": 1, "mejor_racha": 1, "actividades_hechas": 1,
            "actividades_pendientes": 1, "preguntas_respondidas": 4, "correctas": 2, "incorrectas": 2,
            "porcentaje_acierto": 50, "porcentaje_macro": 50, "porcentaje_super": 50, "porcentaje_micro": 50,
            "nombres_niveles": ["Curioso"], "animo": "neutral"}
    pendientes = [{"texto_id": 9, "titulo": "Río Claro"}]
    conn = ConexionFalsa(fila, [], [], pendientes)
    salida = asyncio.run(seguimiento_service.progreso(conn, 7, 1))
    assert salida["pendientes"] == pendientes
    sql_ejecutadas = [sql for sql, _ in conn.consultas]
    assert seguimiento_service.SQL_PENDIENTES in sql_ejecutadas
    assert "a.estado = 'terminada'" in seguimiento_service.SQL_PENDIENTES


# ---------------------------------------------------------------- B4 · historial por nivel

def test_historial_filtra_por_nivel(cliente, monkeypatch):
    recibido = {}

    async def falso(conn, profesor, estudiante, limite, desde, nivel=None):
        recibido["nivel"] = nivel
        return []

    monkeypatch.setattr(seguimiento_service, "historial", falso)
    h = cabeceras("profesor", 7)
    assert cliente.get("/estudiantes/1/historial?nivel=micro", headers=h).status_code == 200
    assert recibido["nivel"] == "micro"
    assert cliente.get("/estudiantes/1/historial?nivel=otro", headers=h).status_code == 422
    assert "%(nivel)s::text IS NULL" in seguimiento_service.SQL_HISTORIAL


# ---------------------------------------------------------------- B5 · editar resaltado

def test_editar_resaltado_solo_cambia_lo_enviado():
    fila = {"id": 3, "nivel": "super", "inicio": 0, "fin": 5, "fragmento": "Hola.", "explicacion": None,
            "es_idea_principal": False, "creado_en": "2026-11-16T10:00:00Z"}
    conn = ConexionFalsa(fila)
    asyncio.run(textos_service.actualizar_resaltado(conn, 7, 1, 3, {"nivel": "super", "explicacion": None}))
    params = conn.consultas[0][1]
    assert params["cambiar_explicacion"] is True and params["explicacion"] is None    # borrar la explicación
    assert params["profesor"] == 7

    conn = ConexionFalsa(fila)
    asyncio.run(textos_service.actualizar_resaltado(conn, 7, 1, 3, {"nivel": "macro"}))
    assert conn.consultas[0][1]["cambiar_explicacion"] is False                     # la conserva


def test_editar_resaltado_ajeno_responde_404(cliente):
    r = cliente.patch("/textos/1/resaltados/3", headers=cabeceras("profesor", 7), json={"nivel": "micro"})
    assert r.status_code == 404


# ---------------------------------------------------------------- B6 · usuario y clave automáticos

def test_proponer_usuario():
    assert admin_service.proponer_usuario("Ana María Duque") == "ana.maria.duque"
    assert admin_service.proponer_usuario("  José  Núñez ") == "jose.nunez"
    assert admin_service.proponer_usuario("Lu") == "lu.profe"
    assert len(admin_service.proponer_usuario("Nombre " * 20)) <= 40
    assert re.match(r"^[a-z0-9._-]{3,40}$", admin_service.proponer_usuario("Ñandú O'Brien-Pérez"))


def test_clave_generada_es_fuerte_y_sin_caracteres_confusos():
    claves = {admin_service.generar_clave() for _ in range(50)}
    assert len(claves) == 50
    for c in claves:
        assert c.startswith("Lente-") and len(c) == 14
        assert not set(c[6:]) & set("0O1lI")


def test_usuario_repetido_recibe_numero():
    usados = [{"usuario": "ana.duque"}, {"usuario": "ana.duque2"}]
    assert asyncio.run(admin_service._usuario_libre(ConexionFalsa(usados), "ana.duque")) == "ana.duque3"
    assert asyncio.run(admin_service._usuario_libre(ConexionFalsa([]), "ana.duque")) == "ana.duque"


def test_crear_profesor_sin_usuario_ni_clave(cliente, monkeypatch):
    prof = {"id": 5, "nombre": "Ana María Duque", "usuario": "ana.maria.duque", "activo": True,
            "ultimo_ingreso": None, "cursos": 0, "estudiantes": 0}

    async def obtener(conn, pid):
        return prof

    monkeypatch.setattr(admin_service, "obtener_profesor", obtener)
    conn = ConexionFalsa([], {"id": 5})
    salida = asyncio.run(admin_service.crear_profesor(conn, "Ana María Duque", None, None))
    assert salida["clave_temporal"].startswith("Lente-")
    insertado = conn.consultas[1][1]
    assert insertado["usuario"] == "ana.maria.duque" and insertado["clave"] == salida["clave_temporal"]

    # Si el administrador escribe la clave, no se devuelve
    conn = ConexionFalsa({"id": 5})
    salida = asyncio.run(admin_service.crear_profesor(conn, "Ana", "ana", "temporal123"))
    assert salida["clave_temporal"] is None


def test_restablecer_clave_devuelve_la_generada(cliente, monkeypatch):
    async def falso(conn, pid, clave):
        return {"clave_temporal": None if clave else "Lente-ABCDEFGH"}

    monkeypatch.setattr(admin_service, "restablecer_clave", falso)
    h = cabeceras("administrador", 1)
    r = cliente.post("/admin/profesores/2/clave", headers=h, json={})
    assert r.status_code == 200 and r.json() == {"clave_temporal": "Lente-ABCDEFGH"}
    r = cliente.post("/admin/profesores/2/clave", headers=h, json={"clave": "otra-clave-1"})
    assert r.json() == {"clave_temporal": None}


# ---------------------------------------------------------------- B7 · pista de primaria

def _actividad(nivel_escolar, paso):
    return {"id": 1, "estudiante_id": 1, "estudiante": "Ana", "curso_id": 1, "texto_id": 3, "numero": 1,
            "estado": "en_curso", "paso": paso, "grado": 4, "nivel_escolar": nivel_escolar,
            "dificultad_maxima": 1, "resultado_macro": None, "resultado_super": None, "resultado_micro": None,
            "puntos_ganados": 0, "iniciada_en": "2026-11-16T10:00:00Z", "terminada_en": None,
            "titulo": "T", "cuerpo": "Texto", "fuente": None}


def test_primaria_recibe_la_pista_de_palabras_en_micro():
    from app.services import actividades_service as act
    vista = asyncio.run(act.ver(ConexionFalsa(_actividad("primaria", "micro"), {"n": 6}), 7, 1))
    assert vista["palabras_esperadas"] == 6
    # Secundaria y media no reciben pista; tampoco primaria en otros pasos
    assert asyncio.run(act.ver(ConexionFalsa(_actividad("secundaria", "micro")), 7, 1))["palabras_esperadas"] is None
    assert asyncio.run(act.ver(ConexionFalsa(_actividad("primaria", "macro")), 7, 1))["palabras_esperadas"] is None


# ---------------------------------------------------------------- B8 · tipo de palabra

def test_resultado_micro_evalua_el_tipo_sin_cambiar_la_nota():
    from app.services import actividades_service as act
    palabras = [{"palabra": "brutal", "tipo": "adjetivo", "inicio": 0, "fin": 6, "explicacion": None},
                {"palabra": "arrasó", "tipo": "verbo", "inicio": 10, "fin": 16, "explicacion": None},
                {"palabra": "caos", "tipo": "expresion", "inicio": 20, "fin": 24, "explicacion": None}]
    marcas = [{"texto": "brutal", "inicio": 0, "fin": 6, "es_correcta": True, "tipo_palabra": "adjetivo"},
              {"texto": "arrasó", "inicio": 10, "fin": 16, "es_correcta": True, "tipo_palabra": "adjetivo"},
              {"texto": "caos", "inicio": 20, "fin": 24, "es_correcta": True, "tipo_palabra": None}]
    aciertos, omisiones, neutras = act.analizar_micro(palabras, marcas)
    assert [(a["palabra"], a["tu_tipo"], a["tipo_correcto"]) for a in aciertos] == [
        ("brutal", "adjetivo", True), ("arrasó", "adjetivo", False), ("caos", None, None)]
    assert omisiones == [] and neutras == []
    assert "r.tipo_palabra" in act.SQL_MICRO


# ---------------------------------------------------------------- B10 · logros configurables

def test_logros_solo_para_el_administrador(cliente):
    assert cliente.get("/admin/logros", headers=cabeceras("profesor", 7)).status_code == 403
    nuevo = {"nombre": "Lector constante", "descripcion": "Diez actividades", "regla": "actividades_terminadas", "meta": 10}
    h = cabeceras("administrador", 1)
    assert cliente.post("/admin/logros", headers=h, json=nuevo | {"regla": "inventada"}).status_code == 422
    assert cliente.post("/admin/logros", headers=h, json=nuevo | {"meta": 0}).status_code == 422


def test_crear_y_desactivar_logro():
    logro = {"id": 7, "nombre": "Lector constante", "descripcion": "Diez actividades",
             "regla": "actividades_terminadas", "meta": 10, "activo": True, "ganados": 0}
    conn = ConexionFalsa({"id": 7}, logro)
    salida = asyncio.run(admin_service.crear_logro(conn, {"nombre": "Lector constante", "descripcion": "Diez actividades",
                                                          "regla": "actividades_terminadas", "meta": 10}))
    assert salida["id"] == 7
    conn = ConexionFalsa({"id": 7}, logro | {"activo": False})
    asyncio.run(admin_service.actualizar_logro(conn, 7, {"activo": False}))
    assert conn.consultas[0][1] == {"id": 7, "nombre": None, "descripcion": None, "meta": None, "activo": False}


def test_progreso_trae_el_catalogo_de_logros():
    assert "WHERE l.activo OR g.estudiante_id IS NOT NULL" in seguimiento_service.SQL_CATALOGO_LOGROS
