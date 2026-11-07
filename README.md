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
