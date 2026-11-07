# bogota-vial

Plataforma de datos para analizar y visualizar las obras viales de Bogotá: ETL de datos abiertos,
mapa interactivo y modelos de machine learning.

## Estructura

```
bogota-vial/
├── etl/                 pipeline de datos (Python + SQL)
│   ├── src/extraccion/      descarga de datos (visor IDU, SECOP)
│   ├── src/transformacion/  preparación de CSV
│   ├── src/carga/           carga a PostGIS (tablas stg_*)
│   ├── sql/                 limpieza, cruce, localidades, vistas y calidad
│   └── run_etl.py           ejecuta cargar -> transformar -> calidad
├── backend/             API REST (FastAPI) que lee las vistas de PostGIS
├── frontend/            aplicación web (React + Vite + Leaflet)
├── ml/                  modelos de machine learning (próximamente)
├── data/                datos crudos e intermedios (no se suben a git)
└── docker-compose.yml
```

## Puesta en marcha con Docker

```bash
cp .env.example .env          # y editar la clave
docker compose up -d --build  # base de datos + backend + frontend
docker compose run --rm etl   # carga los datos de ./data en la base
```

- Frontend: http://localhost:3000
- API y documentación: http://localhost:8000/docs
- PostGIS: `localhost:5432`

Para correr solo una etapa del ETL: `docker compose run --rm etl --etapa calidad`.

## Desarrollo local (sin Docker para la app)

```bash
docker compose up -d db

# ETL
pip install -r etl/requirements.txt
python etl/run_etl.py

# Backend
pip install -r backend/requirements.txt
cd backend && uvicorn app.main:app --reload

# Frontend (en otra terminal)
cd frontend && npm install && npm run dev   # http://localhost:5173
```

Los scripts de descarga (`etl/src/extraccion/`) se ejecutan desde la raíz del repo, para que
guarden en `data/raw/`.

## Despliegue en producción

En el servidor (Ubuntu 24.04, p. ej. AWS EC2 `t3.small`) la app corre con Docker detrás de
[Caddy](https://caddyserver.com), que se encarga del HTTPS. La base y el backend no tienen puertos públicos.

```
Internet ─HTTPS→ Caddy (80/443) → frontend (nginx, /api) → backend (FastAPI) → db (PostGIS)
```

| Archivo | Para qué sirve |
|---|---|
| `docker-compose.prod.yml` | Se suma al compose normal: cierra puertos y agrega Caddy |
| `deploy/Caddyfile` | HTTPS automático para `DOMINIO` (y `www.` redirige) |
| `deploy/setup-servidor.sh` | Prepara el servidor: Docker, swap, llaves, clon del repo, backups |
| `deploy/backup.sh` | Respaldo diario de la base (`pg_dump`), guarda los últimos 7 |
| `.github/workflows/deploy.yml` | En cada push a `main`: verifica y, si está activo, despliega por SSH |

Primer despliegue (en el servidor):

```bash
bash setup-servidor.sh                 # una vez; imprime las llaves que hay que copiar a GitHub
cd /opt/bogota-vial && nano .env       # ver .env.example (clave fuerte, DOMINIO, MAPBOX_API_KEY)
# desde tu PC: scp -r data ubuntu@IP:/opt/bogota-vial/
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm etl
```

Despliegue automático: en GitHub → Settings → Secrets and variables → Actions, crear los secrets
`VPS_HOST`, `VPS_USER` y `VPS_SSH_KEY`, y la variable `DESPLIEGUE_ACTIVO=true`. Desde ahí, cada push a
`main` se publica solo (pestaña **Actions** para ver el resultado).

## Endpoints principales

| Método | Ruta                       | Descripción                                      |
|--------|----------------------------|--------------------------------------------------|
| GET    | `/api/health`              | Estado de la API y la conexión a la base         |
| GET    | `/api/obras`               | Lista de obras (filtros `localidad`, `estado`)   |
| GET    | `/api/obras/geojson`       | Obras como GeoJSON de puntos                     |
| GET    | `/api/obras/estados`       | Estados de contrato y su conteo                  |
| GET    | `/api/obras/{objectid}`    | Detalle de una obra                              |
| GET    | `/api/localidades`         | Indicadores por localidad                        |
| GET    | `/api/localidades/geojson` | Polígonos de localidades con indicadores         |
| GET    | `/api/calidad`             | Reporte de calidad del ETL                       |
| GET    | `/api/obras/mapa`          | Obras con estado de seguimiento (mapa y listado) |
| GET    | `/api/obras/indicadores`   | Totales de la página principal (`?localidad=08`) |
| GET    | `/api/dashboard`           | Indicadores y gráficos Plotly del dashboard      |
