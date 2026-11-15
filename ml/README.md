# ml

Modelos de machine learning de Bogotá Vial. Cada modelo vive en su propia carpeta; aquí solo queda lo común.

```
ml/
├── Dockerfile          imagen del servicio "ml" de docker-compose (Python 3.12)
├── requirements.txt    librerías comunes (scikit-learn, shap, pandas, psycopg2...)
├── run_ml.py           entrena uno o todos los modelos: python run_ml.py <modelo>
├── comun/              utilidades compartidas (conexión a PostGIS)
├── riesgo_prorroga/    modelo 1: riesgo de atraso (probabilidad de prórroga del contrato)
├── models/             modelos entrenados, una carpeta por modelo (no se suben a git)
└── notebooks/          exploración y prototipos (Jupyter)
```

Los modelos leen las vistas que deja el ETL en PostGIS y escriben sus resultados en tablas `ml_*`
(creadas por `etl/sql/06_ml.sql`). El backend solo lee esas tablas; nunca carga un modelo.

## Entrenar

Siempre después del ETL:

```bash
# Con Docker
docker compose run --rm etl
docker compose run --rm ml riesgo_prorroga     # o sin argumento: todos los modelos

# En local (Python 3.12)
pip install -r ml/requirements.txt
python ml/run_ml.py riesgo_prorroga
```

Los modelos entrenados quedan en `ml/models/<modelo>/` (en Docker, la carpeta está montada como volumen).

## Modelos

| Modelo | Qué estima | Tablas que escribe |
|---|---|---|
| [riesgo_prorroga](riesgo_prorroga/README.md) | Probabilidad de que un contrato del IDU sea prorrogado y riesgo de atraso de cada obra | `ml_prorroga_metricas`, `ml_prorroga_contrato`, `ml_riesgo_obra` |

## Agregar un modelo nuevo

1. Crear `ml/<modelo>/` con un `entrenar.py` que tenga una función `main()`.
2. Registrarlo en `MODELOS` de `run_ml.py`.
3. Si necesita vistas o tablas, agregar su sección en `etl/sql/06_ml.sql` (tablas con `CREATE TABLE IF NOT
   EXISTS` y prefijo propio, para que el ETL no borre los resultados).
4. Si necesita librerías nuevas, sumarlas a `requirements.txt`.
