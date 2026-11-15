"""Verifica, SOLO CON LECTURA, que el backend llega a PostgreSQL y a Ollama.

Usa la configuración del archivo .env. No escribe nada en la base.

    python -m scripts.verificar_conexion
"""

import psycopg
from ollama import Client

from app.core.config import get_settings

TABLAS = ("usuarios", "cursos", "estudiantes", "textos", "actividades", "respuestas", "cola_ia", "ajustes")


def _primera_linea(e: Exception) -> str:
    return f"{type(e).__name__}: {(str(e).strip().splitlines() or [''])[0][:200]}"


def revisar_rol(rol: str, conninfo: str) -> bool:
    try:
        with psycopg.connect(conninfo, connect_timeout=5, autocommit=True) as c:
            c.execute("SET default_transaction_read_only = on")
            usuario, bd, ver = c.execute(
                "SELECT current_user, current_database(), current_setting('server_version')").fetchone()
            print(f"[OK] {rol}: conectado como {usuario} a la base {bd} (PostgreSQL {ver})")
            for t in TABLAS:
                try:
                    n = c.execute(f"SELECT count(*) FROM lente.{t}").fetchone()[0]
                    print(f"     lente.{t}: {n} filas")
                except psycopg.errors.InsufficientPrivilege:
                    print(f"     lente.{t}: sin permiso (esperado según el rol)")
            if rol == "lente_ia":
                for clave in ("ia_modelo", "ia_modelo_validacion", "ia_tiempo_maximo_seg"):
                    v = c.execute("SELECT ajuste(%s) #>> '{}'", (clave,)).fetchone()[0]
                    print(f"     ajuste {clave}: {v if v is not None else '(sin definir: usa el valor del .env)'}")
            return True
    except Exception as e:  # noqa: BLE001
        print(f"[FALLA] {rol}: {_primera_linea(e)}")
        return False


def revisar_ollama(url: str) -> bool:
    try:
        modelos = [m.model for m in Client(host=url, timeout=10).list().models]
        print(f"[OK] Ollama en {url}: {', '.join(modelos)}")
        return True
    except Exception as e:  # noqa: BLE001
        print(f"[FALLA] Ollama en {url}: {_primera_linea(e)}")
        return False


def main() -> None:
    s = get_settings()
    resultados = [
        revisar_rol("lente_app", s.conninfo_app),
        revisar_rol("lente_ia", s.conninfo_ia),
        revisar_ollama(s.ollama_url),
    ]
    print("\nTodo conectado." if all(resultados) else "\nHay conexiones que fallan (ver arriba).")
    raise SystemExit(0 if all(resultados) else 1)


if __name__ == "__main__":
    main()
