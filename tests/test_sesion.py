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


def test_la_conexion_confirma_antes_de_responder():
    """El COMMIT debe ocurrir antes de enviar la respuesta: si no, el frontend puede pedir
    el paso siguiente antes de que el anterior esté guardado (se vio con /terminar)."""
    import typing

    from app.core.deps import Conn
    dependencia = typing.get_args(Conn)[1]
    assert dependencia.scope == "function"


def test_ninguna_ruta_pide_la_conexion_sin_el_atajo():
    import pathlib
    raiz = pathlib.Path(__file__).resolve().parent.parent / "app" / "routers"
    for archivo in raiz.glob("*.py"):
        assert "Depends(get_conn" not in archivo.read_text(encoding="utf-8"), archivo.name
