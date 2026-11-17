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
    assert conn.consultas[-1][0] == seguimiento_service.SQL_PENDIENTES
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
