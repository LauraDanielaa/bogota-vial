-- =====================================================================
-- 04_vistas.sql
-- Vistas listas para consumir desde el mapa o el dashboard.
--
--   v_obras_mapa        1 fila por obra con punto, para dibujar el mapa
--   v_localidad_stats   1 fila por localidad (20), con indicadores y su polígono
--                       (contorno = lista [[lon,lat],...] del borde exterior, para el
--                        gráfico deck.gl Polygon de Superset; geom = geometría PostGIS)
-- =====================================================================

-- ---------------------------------------------------------------------
-- v_obras_mapa: las obras que tienen coordenadas válidas
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_obras_mapa AS
SELECT
    objectid,
    nombre,
    etapa,
    contrato,
    estado_contrato,
    avance_programado,
    avance_ejecutado,
    contratista,
    valor_contrato,
    fecha_inicio,
    fecha_fin,
    interventoria_contratista,
    localidad_codigo,
    localidad_nombre,
    en_secop,
    secop_url,
    lon,
    lat,
    geom
FROM obras_integradas
WHERE geom IS NOT NULL;


-- ---------------------------------------------------------------------
-- v_localidad_stats: indicadores por localidad
-- El valor se suma por contrato (no por obra): un contrato con varias obras
-- en la misma localidad se cuenta una sola vez.
-- Las localidades sin obras aparecen con ceros.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_localidad_stats AS
WITH por_contrato AS (
    SELECT localidad_codigo, contrato, max(valor_contrato) AS valor_contrato
    FROM obras_integradas
    WHERE localidad_codigo IS NOT NULL AND contrato IS NOT NULL
    GROUP BY localidad_codigo, contrato
),
valores AS (
    SELECT localidad_codigo,
           count(*)            AS n_contratos,
           sum(valor_contrato) AS valor_total
    FROM por_contrato
    GROUP BY localidad_codigo
),
obras AS (
    SELECT localidad_codigo,
           count(*)                                              AS n_obras,
           round(avg(avance_ejecutado), 2)                       AS avance_ejecutado_promedio,
           count(*) FILTER (WHERE estado_contrato = 'EN EJECUCION')      AS n_en_ejecucion,
           count(*) FILTER (WHERE estado_contrato = 'SUSPENDIDO')        AS n_suspendidas,
           count(*) FILTER (WHERE estado_contrato LIKE 'TERMINADO%'
                               OR estado_contrato = 'LIQUIDADO')         AS n_terminadas
    FROM obras_integradas
    WHERE localidad_codigo IS NOT NULL
    GROUP BY localidad_codigo
)
SELECT
    l.codigo                                  AS localidad_codigo,
    l.nombre                                  AS localidad_nombre,
    coalesce(o.n_obras, 0)                    AS n_obras,
    coalesce(v.n_contratos, 0)                AS n_contratos,
    v.valor_total,
    o.avance_ejecutado_promedio,
    coalesce(o.n_en_ejecucion, 0)             AS n_en_ejecucion,
    coalesce(o.n_suspendidas, 0)              AS n_suspendidas,
    coalesce(o.n_terminadas, 0)               AS n_terminadas,
    (ST_AsGeoJSON(l.geom)::json->'coordinates'->0->0)::text  AS contorno,   -- anillo exterior [[lon,lat],...] para Superset (deck.gl Polygon, formato JSON)
    l.geom                                                   -- para DBeaver y otras herramientas de mapas
FROM clean_localidades l
LEFT JOIN obras   o ON o.localidad_codigo = l.codigo
LEFT JOIN valores v ON v.localidad_codigo = l.codigo;