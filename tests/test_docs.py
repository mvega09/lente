"""La documentación de la API debe coincidir con el código."""

from scripts.generar_docs_api import SALIDA, generar


def test_docs_api_al_dia():
    assert SALIDA.read_text(encoding="utf-8") == generar(), (
        "docs/api.md está desactualizado: ejecute  python -m scripts.generar_docs_api")
