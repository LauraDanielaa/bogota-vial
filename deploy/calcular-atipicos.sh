#!/usr/bin/env bash
# =====================================================================
# Contratos atípicos (ml/atipicos): corre el ETL y luego el modelo, UNA vez por commit.
#
# Lo ejecuta el workflow de despliegue (.github/workflows/deploy.yml) en cada push a main,
# después de levantar los contenedores y de verificar que la API responda.
#
# - Si ya hay una ejecución exitosa para el commit (p. ej. alguien volvió a lanzar el
#   workflow), no hace nada: ni ETL ni modelo. El script de Python vuelve a revisarlo
#   dentro de su transacción, por si dos despliegues coinciden.
# - El modelo escribe todo en una sola transacción: si falla, la web sigue mostrando la
#   ejecución anterior. Este script sale con error y el workflow muestra una advertencia,
#   pero el despliegue no se cae.
#
# Uso manual (en el servidor):
#   bash deploy/calcular-atipicos.sh <commit>       # p. ej. $(git rev-parse HEAD)
# =====================================================================
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$APP_DIR"

COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml"
COMMIT="${1:-$(git rev-parse HEAD)}"

# Consulta de una sola respuesta en la base (credenciales dentro del contenedor)
consulta() {
  $COMPOSE exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "$1"' _ "$1"
}

# El commit es un hash hexadecimal: se valida antes de ponerlo en la consulta
if [[ ! "$COMMIT" =~ ^[0-9a-f]{7,40}$ ]]; then
  echo "Contratos atípicos: commit inválido ('$COMMIT')."
  exit 1
fi

# Dos consultas separadas: si la tabla no existe, la segunda fallaría
existe=$(consulta "SELECT to_regclass('public.ml_atipicos_ejecucion') IS NOT NULL")
if [[ "$existe" == "t" ]]; then
  version=$(consulta "SELECT version FROM ml_atipicos_ejecucion WHERE commit_git = '$COMMIT' AND exitosa LIMIT 1")
  if [[ -n "$version" ]]; then
    echo "Contratos atípicos: ya hay una ejecución exitosa para el commit ${COMMIT:0:12} (versión $version). No se repite."
    exit 0
  fi
fi

if [[ ! -f data/raw/secop_contratos_idu_completo.csv ]]; then
  echo "Contratos atípicos: no está data/raw/secop_contratos_idu_completo.csv en el servidor."
  echo "Copia la carpeta data (ver README). La web sigue sin mostrar contratos atípicos."
  exit 1
fi

echo "Contratos atípicos: commit ${COMMIT:0:12}. Se corre el ETL y luego el modelo."
$COMPOSE build etl ml
$COMPOSE run --rm etl
$COMPOSE run --rm -e COMMIT_GIT="$COMMIT" ml atipicos
echo "Contratos atípicos: listo."
