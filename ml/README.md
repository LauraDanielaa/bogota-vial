# ml

Modelos de machine learning de Bogotá Vial. Cada modelo vive en su propia carpeta; aquí solo queda lo común.

```
ml/
├── Dockerfile          imagen del servicio "ml" de docker-compose (Python 3.12)
├── requirements.txt    librerías comunes (scikit-learn, shap, pandas, psycopg2...)
├── run_ml.py           entrena uno o todos los modelos: python run_ml.py <modelo>
├── comun/              utilidades compartidas (conexión a PostGIS)
├── riesgo_prorroga/    modelo 1: riesgo de atraso (probabilidad de prórroga del contrato)
├── atipicos/           modelo 2: contratos atípicos (IsolationForest, no supervisado)
└── models/             archivo entrenado del modelo de riesgo (no se sube a git)
```

Los modelos leen las vistas que deja el ETL en PostGIS y escriben sus resultados en tablas `ml_*`
(creadas por `etl/sql/06_ml.sql`). El backend solo lee esas tablas; nunca carga un modelo.

## Entrenar

Siempre después del ETL:

```bash
# Con Docker
docker compose run --rm etl
docker compose run --rm ml riesgo_prorroga     # o sin argumento: todos los modelos
docker compose run --rm -e COMMIT_GIT=$(git rev-parse HEAD) ml atipicos

# En local (Python 3.12)
pip install -r ml/requirements.txt
python ml/run_ml.py riesgo_prorroga
python ml/run_ml.py atipicos
```

El modelo de riesgo guarda su archivo entrenado en `ml/models/riesgo_prorroga/` (en Docker, la carpeta está
montada como volumen). El de atípicos no guarda modelo: se vuelve a calcular en cada push y sus resultados y
métricas quedan en la base.

## Ejecución automática (workflow de despliegue)

| Modelo | Cuándo corre en producción |
|---|---|
| `riesgo_prorroga` | Solo en el primer despliegue (o a pedido, con *Run workflow* → *Volver a calcular el riesgo de atraso*), con `deploy/calcular-riesgo.sh` |
| `atipicos` | Una vez por cada push a `main`, con `deploy/calcular-atipicos.sh <commit>`: ETL + modelo. Si el commit ya tiene una ejecución exitosa, no hace nada; si falla, la web conserva la ejecución anterior y el workflow muestra una advertencia sin tumbar el despliegue |

En local ninguno corre solo: ni con `docker compose up` (el servicio `ml` tiene el perfil `ml`) ni en los
pull requests.

## Modelos

| Modelo | Qué estima | Tablas que escribe |
|---|---|---|
| [riesgo_prorroga](riesgo_prorroga/README.md) | Probabilidad de que un contrato del IDU sea prorrogado y riesgo de atraso de cada obra | `ml_prorroga_metricas`, `ml_prorroga_contrato`, `ml_riesgo_obra` |
| [atipicos](atipicos/README.md) | Contratos que se salen de lo habitual frente a los 913 contratos del IDU, con sus motivos | `ml_atipicos_ejecucion`, `ml_atipicos_contrato` |

## Agregar un modelo nuevo

1. Crear `ml/<modelo>/` con un `entrenar.py` que tenga una función `main()`.
2. Registrarlo en `MODELOS` de `run_ml.py`.
3. Si necesita vistas o tablas, agregar su sección en `etl/sql/06_ml.sql` (tablas con `CREATE TABLE IF NOT
   EXISTS` y prefijo propio, para que el ETL no borre los resultados).
4. Si necesita librerías nuevas, sumarlas a `requirements.txt`.
