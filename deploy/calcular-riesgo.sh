#!/usr/bin/env bash
# =====================================================================
# Calcula el riesgo de atraso de las obras (ETL + modelo ml/riesgo_prorroga)
# SOLO si la base del servidor todavía no tiene un modelo entrenado.
#
# - Primer despliegue: corre el ETL (crea las tablas ml_*) y entrena el modelo.
# - Despliegues siguientes: no hace nada; se conserva el riesgo ya calculado
#   (las tablas ml_* no se borran al desplegar ni al correr el ETL).
#
# Lo ejecuta el workflow de despliegue (.github/workflows/deploy.yml) después de
# levantar los contenedores.
#
# Uso manual (en el servidor):
#   bash deploy/calcular-riesgo.sh            # solo si aún no hay modelo
#   bash deploy/calcular-riesgo.sh --forzar   # vuelve a correr ETL y modelo (p. ej. con datos nuevos)
# =====================================================================
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$APP_DIR"

COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml"
FORZAR="${1:-}"

# Consulta de una sola respuesta en la base (credenciales dentro del contenedor)
consulta() {
  $COMPOSE exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "$1"' _ "$1"
}

if [[ "$FORZAR" != "--forzar" ]]; then
  # Dos consultas separadas: si la tabla no existe, la segunda fallaría
  existe=$(consulta "SELECT to_regclass('public.ml_prorroga_metricas') IS NOT NULL")
  if [[ "$existe" == "t" ]]; then
    version=$(consulta "SELECT version FROM ml_prorroga_metricas WHERE seleccionado ORDER BY entrenado_en DESC LIMIT 1")
    if [[ -n "$version" ]]; then
      echo "Riesgo de atraso: ya hay un modelo entrenado (versión $version). Se conserva."
      exit 0
    fi
  fi
  echo "Riesgo de atraso: la base aún no tiene un modelo entrenado. Se calcula ahora."
else
  echo "Riesgo de atraso: se vuelve a calcular (--forzar)."
fi

# El ETL y el modelo leen los archivos de ./data (se copian a mano al servidor)
if [[ ! -f data/raw/secop_contratos_idu_completo.csv ]]; then
  echo "AVISO: no está data/raw/secop_contratos_idu_completo.csv en el servidor."
  echo "       Copia la carpeta data (ver README) y vuelve a desplegar. El riesgo queda 'Sin calcular'."
  exit 0
fi

$COMPOSE build etl ml
$COMPOSE run --rm etl
$COMPOSE run --rm ml riesgo_prorroga
echo "Riesgo de atraso calculado."
