-- =====================================================================
-- 99_calidad.sql
-- Reporte de calidad: cómo quedó la base después de la limpieza.
--
-- Crea dos vistas:
--   v_calidad            resumen en una sola lista (sección, métrica, valor)
--   v_calidad_columnas   % de nulos por columna de las tablas finales
--
-- Para verlas:
--   SELECT seccion, metrica, valor, nota FROM v_calidad ORDER BY orden;
--   SELECT * FROM v_calidad_columnas ORDER BY tabla, pct_nulos DESC;
-- =====================================================================

CREATE OR REPLACE VIEW v_calidad AS
SELECT row_number() OVER ()::int AS orden, seccion, metrica, valor::numeric AS valor, nota
FROM (
    -- 1. Qué entró y qué quedó
    SELECT '1. Carga y limpieza' AS seccion, 'stg_obras (visor)' AS metrica, (SELECT count(*) FROM stg_obras) AS valor, NULL::text AS nota
    UNION ALL SELECT '1. Carga y limpieza', 'stg_secop_contratos',  (SELECT count(*) FROM stg_secop_contratos), 'todos los contratos del IDU'
    UNION ALL SELECT '1. Carga y limpieza', 'stg_secop_ejecucion',  (SELECT count(*) FROM stg_secop_ejecucion), NULL
    UNION ALL SELECT '1. Carga y limpieza', 'stg_cost',             (SELECT count(*) FROM stg_cost), NULL
    UNION ALL SELECT '1. Carga y limpieza', 'stg_localidades',      (SELECT count(*) FROM stg_localidades), 'deben ser 20'
    UNION ALL SELECT '1. Carga y limpieza', 'clean_obras',          (SELECT count(*) FROM clean_obras), 'debe ser igual a stg_obras'
    UNION ALL SELECT '1. Carga y limpieza', 'clean_obras_metas',    (SELECT count(*) FROM clean_obras_metas), 'metas físicas en formato largo'
    UNION ALL SELECT '1. Carga y limpieza', 'clean_secop',          (SELECT count(*) FROM clean_secop), 'sin prestación de servicios'
    UNION ALL SELECT '1. Carga y limpieza', 'contratos SECOP excluidos',
                     (SELECT count(*) FROM stg_secop_contratos) - (SELECT count(*) FROM clean_secop), 'prestación de servicios'
    UNION ALL SELECT '1. Carga y limpieza', 'obras_integradas',     (SELECT count(*) FROM obras_integradas), 'debe ser igual a clean_obras'

    -- 2. Problemas de los datos de origen
    UNION ALL SELECT '2. Datos de origen', 'obras sin estado',            (SELECT count(*) FROM clean_obras WHERE estado_contrato IS NULL), 'ficha sin información de contrato'
    UNION ALL SELECT '2. Datos de origen', 'obras sin fecha de actualización', (SELECT count(*) FROM clean_obras WHERE fecha_actualizacion IS NULL), NULL
    UNION ALL SELECT '2. Datos de origen', 'obras sin coordenadas válidas',    (SELECT count(*) FROM obras_integradas WHERE geom IS NULL), 'no se dibujan en el mapa'
    UNION ALL SELECT '2. Datos de origen', 'obras con valor de contrato = 0',  (SELECT count(*) FROM obras_integradas WHERE valor_contrato = 0), 'convenios u obras sin valor'
    UNION ALL SELECT '2. Datos de origen', 'contratos SECOP sin llave (formato raro)', (SELECT count(*) FROM clean_secop WHERE contrato IS NULL), 'no se pueden cruzar por número'
    UNION ALL SELECT '2. Datos de origen', 'llaves de SECOP repetidas',
                     (SELECT count(*) - count(DISTINCT contrato) FROM clean_secop WHERE contrato IS NOT NULL), 'el cruce toma una sola'

    -- 3. Cruce con SECOP
    UNION ALL SELECT '3. Cruce con SECOP', 'obras con contrato en SECOP', (SELECT count(*) FROM obras_integradas WHERE en_secop), NULL
    UNION ALL SELECT '3. Cruce con SECOP', 'obras sin cruce',              (SELECT count(*) FROM obras_integradas WHERE NOT en_secop), 'ver v_obras_sin_cruce'
    UNION ALL SELECT '3. Cruce con SECOP', 'contratos distintos en las obras', (SELECT count(DISTINCT contrato) FROM obras_integradas), NULL
    UNION ALL SELECT '3. Cruce con SECOP', 'contratos distintos con cruce',    (SELECT count(DISTINCT contrato) FROM obras_integradas WHERE en_secop), NULL

    -- 4. Datos completados
    UNION ALL SELECT '4. Datos completados', 'obras con algún dato tomado de SECOP',
                     (SELECT count(*) FROM obras_integradas i JOIN clean_obras o USING (objectid)
                      WHERE i.contratista   IS DISTINCT FROM o.contratista
                         OR i.valor_contrato IS DISTINCT FROM o.valor_contrato
                         OR i.fecha_inicio  IS DISTINCT FROM o.fecha_inicio
                         OR i.fecha_fin     IS DISTINCT FROM o.fecha_fin), 'valor, fechas o contratista que el visor no traía'
    UNION ALL SELECT '4. Datos completados', 'obras que siguen sin valor',         (SELECT count(*) FROM obras_integradas WHERE valor_contrato IS NULL), 'ninguna fuente lo tiene'
    UNION ALL SELECT '4. Datos completados', 'obras que siguen sin fecha de inicio', (SELECT count(*) FROM obras_integradas WHERE fecha_inicio IS NULL), 'ninguna fuente lo tiene'
    UNION ALL SELECT '4. Datos completados', 'obras que siguen sin fecha de fin',   (SELECT count(*) FROM obras_integradas WHERE fecha_fin IS NULL), 'ninguna fuente lo tiene'
    UNION ALL SELECT '4. Datos completados', 'obras que siguen sin contratista',    (SELECT count(*) FROM obras_integradas WHERE contratista IS NULL), 'ninguna fuente lo tiene'

    -- 5. Localidad
    UNION ALL SELECT '5. Localidad', 'obras con localidad',     (SELECT count(*) FROM obras_integradas WHERE localidad_codigo IS NOT NULL), NULL
    UNION ALL SELECT '5. Localidad', 'obras sin localidad',     (SELECT count(*) FROM obras_integradas WHERE localidad_codigo IS NULL), 'punto fuera de los polígonos o sin coordenadas'
    UNION ALL SELECT '5. Localidad', 'localidades sin obras',   (SELECT count(*) FROM v_localidad_stats WHERE n_obras = 0), NULL
) t;


-- Obras que no cruzaron con SECOP (para revisarlas una por una)
CREATE OR REPLACE VIEW v_obras_sin_cruce AS
SELECT objectid, contrato, nombre, etapa, estado_contrato, contrato_tipo
FROM obras_integradas
WHERE NOT en_secop
ORDER BY contrato;


-- % de nulos por columna
CREATE OR REPLACE VIEW v_calidad_columnas AS
SELECT 'obras_integradas' AS tabla,
       j.key              AS columna,
       count(*) FILTER (WHERE jsonb_typeof(j.value) = 'null') AS nulos,
       count(*)           AS total,
       round(100.0 * count(*) FILTER (WHERE jsonb_typeof(j.value) = 'null') / count(*), 1) AS pct_nulos
FROM obras_integradas t, jsonb_each(to_jsonb(t) - 'geom') AS j(key, value)
GROUP BY j.key
UNION ALL
SELECT 'clean_secop',
       j.key,
       count(*) FILTER (WHERE jsonb_typeof(j.value) = 'null'),
       count(*),
       round(100.0 * count(*) FILTER (WHERE jsonb_typeof(j.value) = 'null') / count(*), 1)
FROM clean_secop t, jsonb_each(to_jsonb(t)) AS j(key, value)
GROUP BY j.key;