#!/usr/bin/env bash
# Crea la base de pruebas "lente_pruebas" en la VM-BD para las pruebas de integración.
#
#   sudo bash crear_base_pruebas.sh /ruta/a/schema.sql 10.60.14.182
#
# Seguridad:
# - No toca la base real "lente": todo ocurre dentro de "lente_pruebas".
# - Quita del script las líneas "ALTER ROLE ... PASSWORD": los roles lente_app y
#   lente_ia son de todo el servidor, y volver a correr schema.sql cambiaría
#   también las contraseñas con las que la aplicación entra a la base real.
# - Si "lente_pruebas" ya existe, no hace nada.
# - Solo permite conexiones a "lente_pruebas" desde la IP de la VM-APP.
set -euo pipefail

ESQUEMA="${1:?Indique la ruta de schema.sql}"
IP_APP="${2:?Indique la IP de la VM-APP, por ejemplo 10.60.14.182}"
BASE="lente_pruebas"

if sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname = '$BASE'" | grep -q 1; then
  echo "La base $BASE ya existe; no se cambió nada."
  exit 1
fi

TMP="$(mktemp --suffix=.sql)"
trap 'rm -f "$TMP"' EXIT
sed -E '/ALTER ROLE lente_(app|ia) +LOGIN PASSWORD/d' "$ESQUEMA" > "$TMP"
chmod 644 "$TMP"
if grep -qE 'ALTER ROLE lente_(app|ia) .*PASSWORD' "$TMP"; then
  echo "No se pudieron quitar los cambios de contraseña; se detiene por seguridad."
  exit 1
fi

sudo -u postgres createdb "$BASE"
sudo -u postgres psql -d "$BASE" -v ON_ERROR_STOP=1 -q -f "$TMP"
echo "Esquema cargado en $BASE."

HBA="$(sudo -u postgres psql -tAc 'SHOW hba_file')"
REGLA="host $BASE lente_app,lente_ia $IP_APP/32 scram-sha-256"
if ! grep -qF "$REGLA" "$HBA"; then
  echo "$REGLA" >> "$HBA"
  sudo -u postgres psql -qc 'SELECT pg_reload_conf()'
  echo "Acceso permitido a $BASE desde $IP_APP."
fi

echo "Listo. En la VM-APP ejecute las pruebas con:"
echo "  DB_HOST=<ip VM-BD> DB_NAME=$BASE DB_APP_PASSWORD=... DB_IA_PASSWORD=... \\"
echo "  LENTE_PRUEBAS_INTEGRACION=1 .venv/bin/python -m pytest -m integracion -v"
