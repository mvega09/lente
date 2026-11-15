"""Crea un profesor directamente en la base (sin pasar por la sesión del admin).

Sirve para preparar cuentas de prueba o arrancar cuando aún no se tiene la clave
del administrador. Usa el mismo SQL que POST /admin/profesores. La clave se genera
al azar y se guarda en un archivo que solo puede leer el usuario actual; nunca se
imprime en pantalla.

    python -m scripts.crear_profesor --usuario prof.prueba --nombre "Profesor PRUEBA" \
        --archivo-clave ~/.lente_profesor_prueba
"""

import argparse
import os
import pathlib
import secrets

import psycopg

from app.core.config import get_settings
from app.services.admin_service import SQL_CREAR_PROFESOR


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--usuario", required=True)
    ap.add_argument("--nombre", required=True)
    ap.add_argument("--archivo-clave", type=pathlib.Path, required=True)
    args = ap.parse_args()

    archivo = args.archivo_clave.expanduser()
    if archivo.exists():
        raise SystemExit(f"{archivo} ya existe; no se sobrescribe.")
    clave = secrets.token_urlsafe(16)

    with psycopg.connect(get_settings().conninfo_app) as conn:
        existe = conn.execute("SELECT 1 FROM lente.usuarios WHERE usuario = lower(%s)", (args.usuario,)).fetchone()
        if existe:
            raise SystemExit(f"El usuario {args.usuario} ya existe.")
        pid = conn.execute(SQL_CREAR_PROFESOR, {"nombre": args.nombre, "usuario": args.usuario,
                                                "clave": clave}).fetchone()[0]

    fd = os.open(archivo, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(f"LENTE_PRUEBA_USUARIO={args.usuario.lower()}\nLENTE_PRUEBA_CLAVE={clave}\n")
    print(f"Profesor creado: id={pid}, usuario={args.usuario.lower()}. Clave guardada en {archivo} (solo lectura del dueño).")


if __name__ == "__main__":
    main()
