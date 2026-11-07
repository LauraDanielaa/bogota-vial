"""Endpoints de indicadores por localidad (vista v_localidad_stats)."""

from fastapi import APIRouter

from app.db import fetch_all, fetch_one

router = APIRouter(prefix="/localidades", tags=["localidades"])

COLUMNAS = """
    localidad_codigo, localidad_nombre, n_obras, n_contratos, valor_total,
    avance_ejecutado_promedio, n_en_ejecucion, n_suspendidas, n_terminadas
"""


@router.get("")
def listar_localidades():
    return fetch_all(f"SELECT {COLUMNAS} FROM v_localidad_stats ORDER BY localidad_nombre")


@router.get("/geojson")
def localidades_geojson():
    """Polígonos de las 20 localidades con sus indicadores como propiedades."""
    fila = fetch_one(
        f"""
        SELECT json_build_object(
            'type', 'FeatureCollection',
            'features', coalesce(json_agg(json_build_object(
                'type', 'Feature',
                'geometry', ST_AsGeoJSON(t.geom, 6)::json,
                'properties', to_jsonb(t) - 'geom'
            )), '[]'::json)
        ) AS fc
        FROM (SELECT {COLUMNAS}, geom FROM v_localidad_stats) t
        """
    )
    return fila["fc"]
