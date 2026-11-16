"""Endpoints de obras (vista v_obras_mapa)."""

from fastapi import APIRouter, HTTPException, Query

from app.db import fetch_all, fetch_one
from app.routers.atipicos import fuente_atipicos
from app.routers.modelo import NOMBRE_MODELO, NOTA_RIESGO, UMBRALES, fuentes_riesgo

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
    """Obras con coordenadas (v_obras_mapa) + tipo de contrato, estado de seguimiento
    y riesgo de atraso (modelo de prórroga; 'Sin calcular' si aún no se ha entrenado).

    contrato_atipico / atipico_motivos: si el contrato de la obra quedó atípico en la última
    ejecución del modelo de atípicos (todas las obras de ese contrato llevan la marca).
    Sin ejecución, false y [].

    Son ~120 filas: el frontend las carga una vez y filtra en el navegador.
    """
    f = fuentes_riesgo()
    atipicos = fuente_atipicos()
    return fetch_all(
        f"""
        SELECT m.objectid, m.nombre, m.etapa, m.contrato, m.estado_contrato,
               m.avance_programado, m.avance_ejecutado, m.contratista, m.valor_contrato,
               m.fecha_inicio, m.fecha_fin, m.interventoria_contratista,
               m.localidad_codigo, m.localidad_nombre, m.en_secop, m.secop_url,
               m.lon, m.lat,
               s.contrato_tipo, s.estado_seguimiento, s.brecha_pp,
               s.codigo_sigidu, s.total_pagado, s.fecha_actualizacion, s.interventoria_contrato,
               coalesce(r.nivel, 'Sin calcular') AS riesgo_nivel,
               r.probabilidad                    AS riesgo_probabilidad,
               c.dias_adicionados,
               (a.id_contrato IS NOT NULL)        AS contrato_atipico,
               coalesce(a.motivos, '[]'::jsonb)   AS atipico_motivos
        FROM v_obras_mapa m
        JOIN v_obras_seguimiento s USING (objectid)
        LEFT JOIN clean_secop c ON c.id_contrato = s.secop_id_contrato
        LEFT JOIN {f["riesgo_obra"]} r ON r.objectid = m.objectid AND r.version = {f["version"]}
        LEFT JOIN {atipicos} a ON a.id_contrato = s.secop_id_contrato
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


@router.get("/{objectid}/riesgo")
def riesgo_obra(objectid: str):
    """Riesgo de atraso de una obra: nivel, probabilidad de prórroga de su contrato y los
    tres factores que más influyen. Es una estimación estadística, no un dato oficial del IDU."""
    f = fuentes_riesgo()
    fila = fetch_one(
        f"""
        SELECT s.objectid, s.nombre, s.secop_id_contrato AS id_contrato, s.estado_seguimiento,
               c.dias_adicionados,
               coalesce(r.nivel, 'Sin calcular') AS nivel,
               r.probabilidad, r.factores,
               mm.version, mm.modelo, mm.supera_linea_base, mm.entrenado_en
        FROM v_obras_seguimiento s
        LEFT JOIN clean_secop c ON c.id_contrato = s.secop_id_contrato
        LEFT JOIN {f["metricas"]} mm ON mm.version = {f["version"]} AND mm.seleccionado
        LEFT JOIN {f["riesgo_obra"]} r ON r.objectid = s.objectid AND r.version = mm.version
        WHERE s.objectid::text = %(id)s
        """,
        {"id": objectid},
    )
    if fila is None:
        raise HTTPException(status_code=404, detail="Obra no encontrada")
    return {
        **fila,
        "probabilidad": None if fila["probabilidad"] is None else float(fila["probabilidad"]),
        "factores": fila["factores"] or [],
        "modelo_nombre": NOMBRE_MODELO.get(fila["modelo"]) if fila["modelo"] else None,
        "umbrales": UMBRALES,
        "nota": NOTA_RIESGO,
    }


@router.get("/{objectid}")
def detalle_obra(objectid: str):
    fila = fetch_one(
        f"SELECT {COLUMNAS} FROM v_obras_mapa WHERE objectid::text = %(id)s",
        {"id": objectid},
    )
    if fila is None:
        raise HTTPException(status_code=404, detail="Obra no encontrada")
    return fila
