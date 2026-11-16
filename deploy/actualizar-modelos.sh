#!/usr/bin/env bash
# =====================================================================
# Actualiza los datos (ETL) y los modelos de ML en el servidor.
#
# Lo llama el workflow de despliegue después de levantar los contenedores, pero también
# se puede correr a mano en el servidor.
#
# Cada modelo decide si le toca correr (ver las funciones toca_<modelo>):
#   riesgo_prorroga   solo si la base todavía no tiene un modelo entrenado, o con --recalcular
#   atipicos          una vez por commit
# Si a alguno le toca, se corre el ETL una sola vez y después esos modelos. Si a ninguno
# le toca, no se hace nada.
#
# Si un modelo falla, los demás igual corren y la web conserva los resultados que ya tenía
# (cada modelo escribe en una sola transacción). Al final el script sale con error para que
# el workflow muestre una advertencia.
#
# Uso:
#   bash deploy/actualizar-modelos.sh                          # commit actual del repo
#   bash deploy/actualizar-modelos.sh --commit <hash>          # lo que hace el workflow
#   bash deploy/actualizar-modelos.sh --recalcular             # vuelve a entrenar el riesgo
#
# Para probarlo en local, sin el compose de producción:
#   COMPOSE="docker compose" bash deploy/actualizar-modelos.sh
#
# Para agregar un modelo: escribir su función toca_<modelo> y sumarlo a MODELOS.
# =====================================================================
set -uo pipefail

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$APP_DIR"

COMPOSE="${COMPOSE:-docker compose -f docker-compose.yml -f docker-compose.prod.yml}"
MODELOS=(riesgo_prorroga atipicos)

COMMIT=""
RECALCULAR=no
while [[ $# -gt 0 ]]; do
  case "$1" in
    --commit) COMMIT="${2:-}"; shift 2 ;;
    --recalcular) RECALCULAR=si; shift ;;
    *) echo "Opción desconocida: $1"; exit 1 ;;
  esac
done
[[ -z "$COMMIT" ]] && COMMIT="$(git rev-parse HEAD)"

# El commit va dentro de una consulta SQL: solo se acepta un hash hexadecimal
if [[ ! "$COMMIT" =~ ^[0-9a-f]{7,40}$ ]]; then
  echo "Commit inválido: '$COMMIT'"
  exit 1
fi

# Consulta de una sola respuesta en la base (las credenciales están dentro del contenedor)
consulta() {
  $COMPOSE exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "$1"' _ "$1"
}

tabla_existe() {
  [[ "$(consulta "SELECT to_regclass('public.$1') IS NOT NULL")" == "t" ]]
}

# ---------------------------------------------------------------------
# ¿Le toca correr? Cada función imprime el motivo y devuelve 0 (sí) o 1 (no).
# ---------------------------------------------------------------------
toca_riesgo_prorroga() {
  if [[ "$RECALCULAR" == si ]]; then
    echo "se pidió volver a entrenarlo"
    return 0
  fi
  if tabla_existe ml_prorroga_metricas; then
    local version
    version=$(consulta "SELECT version FROM ml_prorroga_metricas WHERE seleccionado ORDER BY entrenado_en DESC LIMIT 1")
    if [[ -n "$version" ]]; then
      echo "ya hay un modelo entrenado (versión $version), se conserva"
      return 1
    fi
  fi
  echo "la base todavía no tiene un modelo entrenado"
  return 0
}

toca_atipicos() {
  if tabla_existe ml_atipicos_ejecucion; then
    local version
    version=$(consulta "SELECT version FROM ml_atipicos_ejecucion WHERE commit_git = '$COMMIT' AND exitosa LIMIT 1")
    if [[ -n "$version" ]]; then
      echo "el commit ${COMMIT:0:12} ya tiene una ejecución (versión $version)"
      return 1
    fi
  fi
  echo "el commit ${COMMIT:0:12} todavía no tiene una ejecución"
  return 0
}

# ---------------------------------------------------------------------
if ! consulta "SELECT 1" >/dev/null; then
  echo "No se pudo consultar la base de datos."
  exit 1
fi

echo "Commit ${COMMIT:0:12}. ¿Qué modelos hay que correr?"
pendientes=()
for modelo in "${MODELOS[@]}"; do
  if motivo=$(toca_"$modelo"); then
    echo "  - $modelo: sí, $motivo"
    pendientes+=("$modelo")
  else
    echo "  - $modelo: no, $motivo"
  fi
done

if [[ ${#pendientes[@]} -eq 0 ]]; then
  echo "No hay nada que actualizar."
  exit 0
fi

# El ETL lee los archivos de ./data, que se copian a mano al servidor (ver README)
if [[ ! -f data/raw/secop_contratos_idu_completo.csv ]]; then
  echo "Falta data/raw/secop_contratos_idu_completo.csv en el servidor: copia la carpeta data."
  echo "La web sigue mostrando los resultados que ya tenía."
  exit 1
fi

$COMPOSE build etl ml || exit 1
echo "Corriendo el ETL..."
if ! $COMPOSE run --rm etl; then
  echo "El ETL falló; no se corre ningún modelo."
  exit 1
fi

fallidos=()
for modelo in "${pendientes[@]}"; do
  echo "Corriendo el modelo $modelo..."
  # COMMIT_GIT lo usa atipicos para no repetir la ejecución; los demás lo ignoran
  if ! $COMPOSE run --rm -e COMMIT_GIT="$COMMIT" ml "$modelo"; then
    fallidos+=("$modelo")
  fi
done

if [[ ${#fallidos[@]} -gt 0 ]]; then
  echo "Fallaron: ${fallidos[*]}. La web sigue mostrando sus resultados anteriores."
  exit 1
fi
echo "Datos y modelos actualizados: ${pendientes[*]}."
