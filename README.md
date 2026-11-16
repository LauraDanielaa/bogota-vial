# Bogotá Vial

Bogotá Vial reúne en un solo lugar la información de las obras viales del IDU en Bogotá. Cruzamos el visor
de proyectos del IDU con los contratos publicados en SECOP II y con las localidades de la ciudad, y lo
mostramos en una aplicación web con tres vistas:

- **Mapa**: cada obra es un punto coloreado según su avance físico o su riesgo de atraso, con filtros por
  localidad, tipo de contrato, estado y avance.
- **Dashboard**: cómo va el avance frente a lo programado, por año y por localidad, en qué estado están las
  obras, dónde está el riesgo de atraso y qué contratos se salen de lo común.
- **Listado**: todas las obras agrupadas por localidad, con la ficha completa de cada una y el enlace a su
  contrato en SECOP.

Además tiene dos modelos de machine learning: uno estima el riesgo de que el contrato de una obra se prorrogue
y otro señala los contratos atípicos. Los dos se explican en [ml/README.md](ml/README.md).

## Cómo está organizado

```
bogota-vial/
├── etl/            descarga, limpieza y carga de los datos en PostGIS (Python + SQL)
├── backend/        API en FastAPI; solo lee las tablas y vistas que deja el ETL
├── frontend/       aplicación web en React + Vite + Leaflet (gráficos con Plotly)
├── ml/             modelos de machine learning, uno por carpeta
├── deploy/         scripts y configuración del servidor de producción
├── data/           datos crudos e intermedios (no se suben a git)
├── docker-compose.yml        entorno local
└── docker-compose.prod.yml   ajustes para producción (HTTPS con Caddy, sin puertos expuestos)
```

El flujo es siempre el mismo: el ETL deja tablas limpias y vistas en PostGIS, los modelos leen esas vistas y
guardan sus resultados en tablas `ml_*`, y el backend solo consulta la base. Nada se recalcula cuando alguien
abre la página.

## Datos

La carpeta `data/` no está en el repositorio. El ETL espera estos archivos:

| Archivo | Qué es |
|---|---|
| `data/interim/obras_idu_final.csv` | Obras del visor del IDU con los datos de su ficha |
| `data/raw/secop_contratos_idu_completo.csv` | Contratos del IDU en SECOP II |
| `data/raw/secop_ejecucion_idu.csv` | Ejecución de contratos en SECOP II |
| `data/raw/datos_abiertos_bogota.csv` | Datos abiertos de Bogotá |
| `data/geo/localidades.geojson` | Polígonos de las 20 localidades |

Los scripts de `etl/src/extraccion/` descargan los datos del visor del IDU y de datos.gov.co, y
`etl/src/transformacion/separar_tablas_idu.py` convierte la ficha de cada obra en columnas. Se corren desde la
raíz del repositorio para que guarden en `data/raw/`.

## Correr el proyecto con Docker

Hace falta Docker con Docker Compose y la carpeta `data/`.

```bash
cp .env.example .env            # cambiar al menos la clave de la base
docker compose up -d --build    # base de datos, backend y frontend
docker compose run --rm etl     # carga los datos en la base
```

Con eso ya se puede abrir:

- La aplicación en http://localhost:3000
- La API y su documentación en http://localhost:8000/docs
- La base en `localhost`, en el puerto `DB_PORT` del `.env` (5433 en el ejemplo)

Los modelos no corren con `docker compose up`; se corren a mano después del ETL:

```bash
docker compose run --rm ml riesgo_prorroga
docker compose run --rm -e COMMIT_GIT=$(git rev-parse HEAD) ml atipicos
```

Mientras no se hayan corrido, la web muestra el riesgo como "Sin calcular" y no muestra nada de contratos
atípicos. Volver a correr el ETL no borra los resultados de los modelos.

Si solo se quiere repetir una etapa del ETL: `docker compose run --rm etl --etapa calidad` (también `cargar`
y `transformar`).

## Desarrollo sin Docker

Solo la base va en Docker; el resto corre en la máquina (Python 3.12 y Node 20):

```bash
docker compose up -d db

pip install -r etl/requirements.txt
python etl/run_etl.py

pip install -r ml/requirements.txt
python ml/run_ml.py riesgo_prorroga
python ml/run_ml.py atipicos

pip install -r backend/requirements.txt
cd backend && uvicorn app.main:app --reload

cd frontend && npm install && npm run dev     # http://localhost:5173
```

Los scripts leen la conexión del `.env` de la raíz. En desarrollo, Vite reenvía `/api` al backend.

## El ETL

`etl/run_etl.py` corre tres etapas: carga los CSV y el GeoJSON en tablas `stg_*` (todo como texto), ejecuta
los archivos SQL en orden y al final imprime un reporte de calidad.

| Archivo | Qué hace |
|---|---|
| `01_limpieza.sql` | Pasa las tablas `stg_*` a tablas `clean_*` con tipos reales. Deja 124 obras y 913 contratos (se excluye la prestación de servicios) |
| `02_cruce.sql` | Une cada obra con su contrato de SECOP por número de contrato y completa lo que le falta al visor |
| `03_localidad.sql` | Asigna la localidad de cada obra según sus coordenadas |
| `04_vistas.sql` | Vistas para el mapa y las localidades |
| `05_indicadores.sql` | Estado de seguimiento de cada obra (una obra en ejecución está retrasada si va 10 puntos o más por debajo de lo programado) y los indicadores de la página principal |
| `06_ml.sql` | Insumos y tablas de resultados de los modelos |
| `99_calidad.sql` | Reporte de calidad: conteos, cruces que no se lograron y datos faltantes |

El ETL se puede correr las veces que se quiera: borra y recrea sus propias tablas, pero nunca toca las tablas
`ml_*`.

## Despliegue

En producción todo corre con Docker en un servidor Ubuntu 24.04 (por ejemplo una instancia `t3.small` de AWS),
detrás de [Caddy](https://caddyserver.com), que se encarga del certificado HTTPS. Ni la base ni el backend
quedan expuestos a internet:

```
Internet ─HTTPS→ Caddy (80/443) → frontend (nginx, /api) → backend (FastAPI) → db (PostGIS)
```

| Archivo | Para qué sirve |
|---|---|
| `docker-compose.prod.yml` | Se suma al compose normal: cierra los puertos y agrega Caddy |
| `deploy/Caddyfile` | HTTPS para el dominio de `DOMINIO`; `www.` redirige al dominio |
| `deploy/setup-servidor.sh` | Prepara el servidor: Docker, swap, llaves, clon del repositorio y copias de seguridad |
| `deploy/backup.sh` | Copia de seguridad diaria de la base con `pg_dump`; guarda las últimas 7 |
| `deploy/actualizar-modelos.sh` | Corre el ETL y los modelos que necesiten actualizarse |
| `.github/workflows/deploy.yml` | Verifica el proyecto en cada push o pull request y despliega los push a `main` |

### Primera vez

```bash
bash setup-servidor.sh                   # una sola vez; al final imprime las llaves para GitHub
cd /opt/bogota-vial && nano .env         # ver .env.example: clave fuerte, DOMINIO y MAPBOX_API_KEY
# desde tu computador: scp -r data ubuntu@IP:/opt/bogota-vial/
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
bash deploy/actualizar-modelos.sh        # ETL y modelos, sin esperar al primer push
```

Para activar el despliegue automático, en GitHub → Settings → Secrets and variables → Actions se crean los
secrets `VPS_HOST`, `VPS_USER` y `VPS_SSH_KEY` y la variable `DESPLIEGUE_ACTIVO=true`.

### Qué pasa en cada push a `main`

El workflow *Verificar y desplegar* tiene dos trabajos. El primero corre también en los pull requests:
compila el frontend, revisa la sintaxis de todo el código Python y de los scripts de `deploy/`, y valida el
compose de producción. El segundo solo corre en los push a `main` y entra al servidor por SSH:

1. Baja el código, reconstruye los contenedores y espera a que la API responda. Si la API no responde, el
   despliegue falla.
2. Corre `deploy/actualizar-modelos.sh` con el commit del push. Cada modelo decide si le toca: el de riesgo
   de atraso solo se entrena si la base todavía no tiene uno, y el de contratos atípicos corre una vez por
   commit. Si a alguno le toca, se corre el ETL una vez y después esos modelos; si a ninguno, no se hace nada.
   Por eso volver a lanzar el workflow sobre el mismo commit no repite trabajo.
3. Si ese paso falla, el sitio sigue en línea con los resultados que ya tenía, y el workflow termina con una
   advertencia en el resumen del run.

Para volver a entrenar el riesgo de atraso (por ejemplo, después de copiar datos nuevos al servidor):
Actions → *Verificar y desplegar* → **Run workflow** → marcar *Volver a entrenar los modelos que se conservan
entre despliegues*. En el servidor da lo mismo correr `bash deploy/actualizar-modelos.sh --recalcular`.

## API

| Ruta | Qué devuelve |
|---|---|
| `GET /api/health` | Estado de la API y de la conexión a la base |
| `GET /api/obras` | Obras, con filtros `localidad` y `estado` |
| `GET /api/obras/geojson` | Obras como GeoJSON de puntos |
| `GET /api/obras/mapa` | Obras con estado de seguimiento, riesgo de atraso y si su contrato es atípico; la usan el mapa y el listado |
| `GET /api/obras/indicadores` | Totales de la página principal (`?localidad=08`) |
| `GET /api/obras/estados` | Estados de contrato y cuántas obras hay en cada uno |
| `GET /api/obras/{objectid}` | Detalle de una obra |
| `GET /api/obras/{objectid}/riesgo` | Riesgo de atraso de una obra y los tres factores que más pesan |
| `GET /api/localidades` | Indicadores por localidad |
| `GET /api/localidades/geojson` | Polígonos de las localidades con sus indicadores |
| `GET /api/dashboard` | Indicadores y gráficos del dashboard (acepta `localidad`, `tipo` y `periodo`) |
| `GET /api/modelo/metricas` | Métricas del modelo de riesgo activo |
| `GET /api/atipicos/ejecucion` | Última ejecución del modelo de contratos atípicos: fecha, contratos, atípicos y estabilidad |
| `GET /api/atipicos/dispersion` | Valor contra plazo pactado de los 913 contratos, para el gráfico del dashboard |
| `GET /api/calidad` | Reporte de calidad del ETL |

La documentación interactiva completa está en `/docs`.
