"""Endpoints de obras (vista v_obras_mapa)."""

from fastapi import APIRouter, HTTPException, Query

from app.db import fetch_all, fetch_one

router = APIRouter(prefix="/obras", tags=["obras"])

COLUMNAS = """
    objectid, nombre, etapa, contrato, estado_contrato,
    avance_programado, avance_ejecutado, contratista, valor_contrato,
    fecha_inicio, fecha_fin, interventoria_contratista,
    localidad_codigo, localidad_nombre, en_secop, secop_url, lon, lat
"""

FILTROS = """
    WHERE (%(localidad)s::text IS NULL OR localidad_codigo::text = %(localidad)s)
      AND (%(estado)s::text   IS NULL OR estado_contrato = %(estado)s)
"""


@router.get("")
def listar_obras(
    localidad: str | None = Query(None, description="Código de localidad"),
    estado: str | None = Query(None, description="Estado del contrato, p. ej. 'EN EJECUCION'"),
    limit: int = Query(500, ge=1, le=5000),
    offset: int = Query(0, ge=0),
):
    params = {"localidad": localidad, "estado": estado, "limit": limit, "offset": offset}
    return fetch_all(
        f"SELECT {COLUMNAS} FROM v_obras_mapa {FILTROS} "
        "ORDER BY objectid LIMIT %(limit)s OFFSET %(offset)s",
        params,
    )


@router.get("/geojson")
def obras_geojson(localidad: str | None = None, estado: str | None = None):
    """FeatureCollection de puntos, listo para Leaflet / MapLibre."""
    fila = fetch_one(
        f"""
        SELECT json_build_object(
            'type', 'FeatureCollection',
            'features', coalesce(json_agg(json_build_object(
                'type', 'Feature',
                'geometry', ST_AsGeoJSON(t.geom)::json,
                'properties', to_jsonb(t) - 'geom'
            )), '[]'::json)
        ) AS fc
        FROM (SELECT {COLUMNAS}, geom FROM v_obras_mapa {FILTROS}) t
        """,
        {"localidad": localidad, "estado": estado},
    )
    return fila["fc"]


@router.get("/mapa")
def obras_mapa():
    """Obras con coordenadas (v_obras_mapa) + tipo de contrato y estado de seguimiento.

    Son ~120 filas: el frontend las carga una vez y filtra en el navegador.
    """
    return fetch_all(
        """
        SELECT m.objectid, m.nombre, m.etapa, m.contrato, m.estado_contrato,
               m.avance_programado, m.avance_ejecutado, m.contratista, m.valor_contrato,
               m.fecha_inicio, m.fecha_fin, m.interventoria_contratista,
               m.localidad_codigo, m.localidad_nombre, m.en_secop, m.secop_url,
               m.lon, m.lat,
               s.contrato_tipo, s.estado_seguimiento, s.brecha_pp,
               s.codigo_sigidu, s.total_pagado, s.fecha_actualizacion, s.interventoria_contrato
        FROM v_obras_mapa m
        JOIN v_obras_seguimiento s USING (objectid)
        ORDER BY m.objectid
        """
    )


@router.get("/indicadores")
def indicadores(
    localidad: str | None = Query(None, description="Código de localidad, p. ej. '08' (Kennedy)"),
):
    """Totales para las tarjetas de la página principal (función fn_indicadores_obras)."""
    return fetch_one(
        "SELECT * FROM fn_indicadores_obras(%(localidad)s)",
        {"localidad": localidad},
    )


@router.get("/estados")
def estados():
    """Valores distintos de estado_contrato con su conteo (para los filtros del frontend)."""
    return fetch_all(
        "SELECT estado_contrato, count(*) AS n FROM v_obras_mapa "
        "WHERE estado_contrato IS NOT NULL GROUP BY 1 ORDER BY 2 DESC"
    )


@router.get("/{objectid}")
def detalle_obra(objectid: str):
    fila = fetch_one(
        f"SELECT {COLUMNAS} FROM v_obras_mapa WHERE objectid::text = %(id)s",
        {"id": objectid},
    )
    if fila is None:
        raise HTTPException(status_code=404, detail="Obra no encontrada")
    return fila
