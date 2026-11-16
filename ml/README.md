# Modelos de machine learning

Aquí viven los modelos del proyecto. Cada uno tiene su propia carpeta con su README; en la raíz de `ml/` solo
queda lo que comparten.

| Modelo | Qué hace | Tablas donde guarda sus resultados |
|---|---|---|
| [riesgo_prorroga](riesgo_prorroga/README.md) | Estima la probabilidad de que el contrato de una obra se prorrogue y la convierte en un nivel de riesgo de atraso | `ml_prorroga_metricas`, `ml_prorroga_contrato`, `ml_riesgo_obra` |
| [atipicos](atipicos/README.md) | Señala los contratos que se salen de lo habitual frente a los 913 contratos del IDU y explica por qué | `ml_atipicos_ejecucion`, `ml_atipicos_contrato` |

```
ml/
├── run_ml.py           punto de entrada: python run_ml.py <modelo>
├── comun/              conexión a PostGIS, compartida por los modelos
├── riesgo_prorroga/    modelo de riesgo de atraso
├── atipicos/           modelo de contratos atípicos
├── models/             archivos entrenados del modelo de riesgo (no se suben a git)
├── Dockerfile          imagen del servicio ml de docker-compose (Python 3.12)
└── requirements.txt    dependencias de todos los modelos
```

Los modelos leen las vistas que deja el ETL en PostGIS y escriben en tablas `ml_*`, que se crean en
`etl/sql/06_ml.sql`. El ETL nunca borra esas tablas, así que los resultados sobreviven a una recarga de datos.
El backend tampoco carga ningún modelo: solo lee esas tablas.

## Cómo correrlos

Siempre después del ETL, porque dependen de sus vistas.

```bash
# Con Docker
docker compose run --rm etl
docker compose run --rm ml riesgo_prorroga
docker compose run --rm -e COMMIT_GIT=$(git rev-parse HEAD) ml atipicos

# Sin Docker (Python 3.12)
pip install -r ml/requirements.txt
python ml/run_ml.py riesgo_prorroga
python ml/run_ml.py atipicos
```

`run_ml.py` sin argumentos corre todos los modelos. El servicio `ml` tiene el perfil `ml` en docker-compose,
así que no arranca con `docker compose up`.

`COMMIT_GIT` solo lo usa el modelo de atípicos, para no correr dos veces sobre el mismo commit. Sin Docker lo
toma de git automáticamente.

## En producción

Nadie los corre a mano. En cada push a `main`, el workflow de despliegue llama a
`deploy/actualizar-modelos.sh`, que pregunta a cada modelo si le toca:

| Modelo | Cuándo corre |
|---|---|
| `riesgo_prorroga` | Solo si la base todavía no tiene un modelo entrenado. Después se conserva el mismo riesgo hasta que alguien pida volver a entrenarlo (*Run workflow* con la casilla marcada, o `--recalcular` en el servidor) |
| `atipicos` | Una vez por commit. Si el commit ya tiene una ejecución exitosa, no se repite |

Si a algún modelo le toca, se corre el ETL una sola vez y después los modelos pendientes. Si uno falla, los
demás igual corren, la web sigue con los resultados que ya tenía y el workflow muestra una advertencia.

## Agregar un modelo

1. Crear `ml/<modelo>/` con un módulo que tenga una función `main()` y un README.
2. Registrarlo en `MODELOS` de `run_ml.py`.
3. Si necesita vistas o tablas, agregar su sección al final de `etl/sql/06_ml.sql`. Las tablas van con
   `CREATE TABLE IF NOT EXISTS` y un prefijo propio (`ml_<modelo>_`), para que el ETL no las borre.
4. Si necesita librerías nuevas, sumarlas a `requirements.txt`.
5. Para que corra en producción, escribir su función `toca_<modelo>` en `deploy/actualizar-modelos.sh` y
   agregarlo a la lista `MODELOS` de ese script.
