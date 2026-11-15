from psycopg import errors

from app.core.errores import NoEncontrado
from app.services import admin_service
from tests.conftest import cabeceras

PROFESOR = {"id": 3, "nombre": "Ana", "usuario": "ana", "activo": True,
            "ultimo_ingreso": None, "cursos": 0, "estudiantes": 0}


def test_sin_token_401(cliente):
    assert cliente.get("/admin/profesores").status_code == 401


def test_profesor_no_entra_al_panel_admin(cliente):
    assert cliente.get("/admin/profesores", headers=cabeceras("profesor")).status_code == 403


def test_crear_profesor(cliente, monkeypatch):
    recibido = {}

    async def falso(conn, nombre, usuario, clave):
        recibido.update(nombre=nombre, usuario=usuario, clave=clave)
        return PROFESOR

    monkeypatch.setattr(admin_service, "crear_profesor", falso)
    r = cliente.post("/admin/profesores", headers=cabeceras("administrador", 1),
                     json={"nombre": "Ana", "usuario": "ana", "clave": "temporal123"})
    assert r.status_code == 201
    assert r.json()["usuario"] == "ana"
    assert recibido["clave"] == "temporal123"


def test_crear_profesor_valida_usuario_y_clave(cliente):
    h = cabeceras("administrador", 1)
    assert cliente.post("/admin/profesores", headers=h,
                        json={"nombre": "Ana", "usuario": "Ana Pérez", "clave": "temporal123"}).status_code == 422
    assert cliente.post("/admin/profesores", headers=h,
                        json={"nombre": "Ana", "usuario": "ana", "clave": "corta"}).status_code == 422


def test_usuario_duplicado_409(cliente, monkeypatch):
    async def falso(*a, **k):
        raise errors.UniqueViolation("duplicado")

    monkeypatch.setattr(admin_service, "crear_profesor", falso)
    r = cliente.post("/admin/profesores", headers=cabeceras("administrador", 1),
                     json={"nombre": "Ana", "usuario": "ana", "clave": "temporal123"})
    assert r.status_code == 409


def test_profesor_inexistente_404(cliente, monkeypatch):
    async def falso(*a, **k):
        raise NoEncontrado("El profesor")

    monkeypatch.setattr(admin_service, "obtener_profesor", falso)
    r = cliente.get("/admin/profesores/99", headers=cabeceras("administrador", 1))
    assert r.status_code == 404
    assert r.json()["detail"] == "El profesor no existe"


def test_resumen(cliente, monkeypatch):
    async def falso(conn):
        return {"total_profesores": 2, "profesores_activos": 1, "total_estudiantes": 40, "estudiantes_activos": 38}

    monkeypatch.setattr(admin_service, "resumen", falso)
    r = cliente.get("/admin/resumen", headers=cabeceras("administrador", 1))
    assert r.status_code == 200
    assert r.json()["total_estudiantes"] == 40
