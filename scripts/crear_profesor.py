"""Crea un profesor o un administrador directamente en la base.

Sirve para preparar cuentas de prueba o del equipo sin pasar por la sesión de
otro administrador. Usa el mismo cifrado que la API (pgcrypto, bcrypt). La clave
se genera al azar y se guarda en un archivo que solo puede leer el usuario
actual; nunca se imprime en pantalla. La cuenta queda marcada para cambiar la
clave en el primer ingreso (POST /auth/cambiar-clave).

    python -m scripts.crear_profesor --usuario prof.prueba --nombre "Profesor PRUEBA" \
        --archivo-clave ~/.lente_profesor_prueba
    python -m scripts.crear_profesor --rol administrador --usuario admin.equipo \
        --nombre "Administrador del equipo" --archivo-clave ~/.lente_admin_equipo
"""

import argparse
import os
import pathlib
import secrets

import psycopg

from app.core.config import get_settings

# Igual que SQL_CREAR_PROFESOR de admin_service, con el rol como parámetro
SQL_CREAR_USUARIO = """
INSERT INTO lente.usuarios (rol, nombre, usuario, clave_cifrada, debe_cambiar_clave)
VALUES (%(rol)s, %(nombre)s, lower(%(usuario)s),
        public.crypt(%(clave)s, public.gen_salt('bf', 10)), true)
RETURNING id
"""

PREFIJO = {"profesor": "LENTE_PRUEBA", "administrador": "LENTE_ADMIN"}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rol", choices=sorted(PREFIJO), default="profesor")
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
        uid = conn.execute(SQL_CREAR_USUARIO, {"rol": args.rol, "nombre": args.nombre, "usuario": args.usuario,
                                               "clave": clave}).fetchone()[0]

    fd = os.open(archivo, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        p = PREFIJO[args.rol]
        f.write(f"{p}_USUARIO={args.usuario.lower()}\n{p}_CLAVE={clave}\n")
    print(f"{args.rol.capitalize()} creado: id={uid}, usuario={args.usuario.lower()}. "
          f"Clave guardada en {archivo} (solo lectura del dueño).")


if __name__ == "__main__":
    main()
