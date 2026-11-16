#!/usr/bin/env bash
# Copia de seguridad de la base "lente" (RNF-04). Corre en la VM-BD como el
# usuario postgres, lanzada por lente-respaldo.timer todos los días.
#
#   DESTINO  carpeta de las copias   (por defecto /var/backups/lente)
#   DIAS     días que se conservan   (por defecto 14)
#
# Restaurar una copia en una base de prueba (no toca la base real):
#   sudo -u postgres createdb lente_restaurada
#   sudo -u postgres pg_restore -d lente_restaurada /var/backups/lente/lente-AAAAMMDD-HHMM.dump
set -euo pipefail

DESTINO="${DESTINO:-/var/backups/lente}"
DIAS="${DIAS:-14}"
mkdir -p "$DESTINO"
chmod 700 "$DESTINO"

archivo="$DESTINO/lente-$(date +%Y%m%d-%H%M).dump"
# Formato personalizado (-Fc): comprimido y restaurable tabla por tabla
pg_dump -d lente -Fc -f "$archivo.tmp"
# Solo se acepta la copia si pg_restore puede leerla completa
pg_restore -l "$archivo.tmp" > /dev/null
mv "$archivo.tmp" "$archivo"

find "$DESTINO" -maxdepth 1 -name 'lente-*.dump' -mtime +"$DIAS" -delete
echo "Respaldo listo: $archivo ($(du -h "$archivo" | cut -f1)); se conservan $DIAS días"
