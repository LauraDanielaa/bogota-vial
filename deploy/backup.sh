#!/usr/bin/env bash
# =====================================================================
# Copia de seguridad de la base de datos (pg_dump comprimido).
# Guarda las últimas 7 en /opt/bogota-vial-backups.
# La programa setup-servidor.sh para todos los días a las 3:00 a. m.
#
# Uso manual:     bash deploy/backup.sh
# Restaurar una:  gunzip -c ARCHIVO.sql.gz | docker compose -f docker-compose.yml -f docker-compose.prod.yml \
#                   exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
# =====================================================================
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${BACKUP_DIR:-/opt/bogota-vial-backups}"
MANTENER=7

mkdir -p "$DEST"
cd "$APP_DIR"

archivo="$DEST/bogota_vial_$(date +%Y%m%d_%H%M).sql.gz"
trap 'rm -f "$archivo"' ERR # si algo falla, no dejar un respaldo a medias

# Las credenciales se leen dentro del contenedor (POSTGRES_USER / POSTGRES_DB)
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T db \
  sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --clean --if-exists' |
  gzip >"$archivo"

# Borrar los más viejos
ls -1t "$DEST"/bogota_vial_*.sql.gz | tail -n +$((MANTENER + 1)) | xargs -r rm --

echo "$(date '+%F %T') respaldo creado: $archivo ($(du -h "$archivo" | cut -f1))"
