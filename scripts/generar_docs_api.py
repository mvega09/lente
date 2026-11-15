"""Genera docs/api.md a partir del OpenAPI de FastAPI, para que la
documentación nunca se desactualice respecto al código.

    python -m scripts.generar_docs_api
"""

import pathlib
from collections import defaultdict

from app.main import app

SALIDA = pathlib.Path(__file__).resolve().parent.parent / "docs" / "api.md"
ORDEN_METODOS = ["get", "post", "put", "patch", "delete"]

ENCABEZADO = """# API

> Generado automáticamente con `python -m scripts.generar_docs_api`. No editar a mano.

La referencia interactiva completa (esquemas de entrada y salida, ejemplos y
pruebas en vivo) está en **`/docs`** (Swagger) y **`/redoc`** de la API.

## Autenticación

`POST /auth/login` devuelve un token. Envíelo en cada solicitud con la
cabecera `Authorization: Bearer <token>`. El rol del token decide qué rutas
puede usar: **administrador** (rutas `/admin`) o **profesor** (el resto).
Un profesor solo ve sus propios cursos, estudiantes, textos y resultados: si
pide algo de otro profesor recibe **404** (RNF-05).

## Errores

| Código | Cuándo |
|---|---|
| 401 | Sin token o token vencido |
| 403 | El rol no puede usar esa ruta |
| 404 | No existe o es de otro profesor |
| 409 | La operación no se puede hacer en el estado actual (por ejemplo, saltar un paso) |
| 422 | Algún dato no es válido |

## Rutas
"""


def generar() -> str:
    esquema = app.openapi()
    por_grupo: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for ruta, operaciones in esquema["paths"].items():
        for metodo in ORDEN_METODOS:
            op = operaciones.get(metodo)
            if op:
                grupo = (op.get("tags") or ["general"])[0]
                por_grupo[grupo].append((metodo.upper(), ruta, op.get("summary", "")))
    partes = [ENCABEZADO]
    for grupo in sorted(por_grupo):
        partes.append(f"\n### {grupo.capitalize()}\n\n| Método | Ruta | Descripción |\n|---|---|---|")
        for metodo, ruta, resumen in sorted(por_grupo[grupo], key=lambda x: (x[1], ORDEN_METODOS.index(x[0].lower()))):
            partes.append(f"| `{metodo}` | `{ruta}` | {resumen} |")
    return "\n".join(partes) + "\n"


if __name__ == "__main__":
    SALIDA.write_text(generar(), encoding="utf-8")
    print(f"Escrito {SALIDA}")
