"""API de Bogotá Vial: expone las obras y los indicadores que deja el ETL en PostGIS."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import fetch_one, pool
from app.routers import calidad, dashboard, localidades, obras


@asynccontextmanager
async def lifespan(_: FastAPI):
    pool.open()
    yield
    pool.close()


app = FastAPI(
    title="Bogotá Vial API",
    description="Obras viales de Bogotá (IDU + SECOP) listas para el mapa y el dashboard.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/api/health", tags=["sistema"])
def health():
    fetch_one("SELECT 1")
    return {"status": "ok"}


app.include_router(obras.router, prefix="/api")
app.include_router(localidades.router, prefix="/api")
app.include_router(calidad.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
