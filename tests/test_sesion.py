"""El token de sesión conserva si el usuario debe cambiar la clave."""

from app.core.security import crear_token
from app.schemas.auth import UsuarioSesion


def _yo(cliente, usuario: UsuarioSesion) -> dict:
    r = cliente.get("/auth/yo", headers={"Authorization": f"Bearer {crear_token(usuario)}"})
    assert r.status_code == 200
    return r.json()


def test_yo_indica_si_debe_cambiar_la_clave(cliente):
    nuevo = UsuarioSesion(id=3, rol="administrador", nombre="Admin", debe_cambiar_clave=True)
    assert _yo(cliente, nuevo)["debe_cambiar_clave"] is True
    al_dia = UsuarioSesion(id=2, rol="profesor", nombre="Prof", debe_cambiar_clave=False)
    assert _yo(cliente, al_dia)["debe_cambiar_clave"] is False
