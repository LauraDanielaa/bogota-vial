-- =====================================================================
-- 01_limpieza.sql
-- Convierte las tablas crudas (stg_*, todo texto) en tablas limpias
-- (clean_*, con tipos reales). Las stg_* NO se modifican.
--
-- Crea:
--   clean_obras        1 fila por obra del visor del IDU (124)
--   clean_obras_metas  metas físicas de cada obra, en formato largo
--   clean_secop        contratos de SECOP II del IDU, sin prestación de servicios
--
-- Es repetible: borra y recrea las tablas clean_* en cada corrida.
-- No usa PostGIS (la geometría se agrega en 03_localidad.sql).
-- =====================================================================


-- ---------------------------------------------------------------------
-- Funciones de limpieza
-- ---------------------------------------------------------------------

-- '98,89%'  ->  98.89
CREATE OR REPLACE FUNCTION limpiar_pct(t text) RETURNS numeric
LANGUAGE sql IMMUTABLE AS $$
    SELECT NULLIF(replace(regexp_replace(coalesce(t, ''), '[^0-9,.\-]', '', 'g'), ',', '.'), '')::numeric
$$;

-- '$ 12.214.197.061,00'  /  'COP 2.341.801.612,00'  ->  12214197061.00
CREATE OR REPLACE FUNCTION limpiar_pesos(t text) RETURNS numeric
LANGUAGE sql IMMUTABLE AS $$
    SELECT NULLIF(replace(regexp_replace(coalesce(t, ''), '[^0-9,]', '', 'g'), ',', '.'), '')::numeric
$$;

-- '05/12/2017'  ->  2017-12-05
CREATE OR REPLACE FUNCTION limpiar_fecha(t text) RETURNS date
LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE WHEN trim(t) ~ '^\d{2}/\d{2}/\d{4}$' THEN to_date(trim(t), 'DD/MM/YYYY') END
$$;

-- '52'  ->  52
CREATE OR REPLACE FUNCTION limpiar_entero(t text) RETURNS integer
LANGUAGE sql IMMUTABLE AS $$
    SELECT NULLIF(regexp_replace(coalesce(t, ''), '[^0-9]', '', 'g'), '')::integer
$$;

-- 'NO APLICA', 'No aplica', '' -> NULL
CREATE OR REPLACE FUNCTION limpiar_texto(t text) RETURNS text
LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE WHEN upper(trim(coalesce(t, ''))) IN ('', 'NO APLICA', 'N/A', 'NA') THEN NULL ELSE trim(t) END
$$;

-- Llave de contrato: 'IDU-1739- 2023', 'IDU1591-2025', 'idu-1596 -2025'  ->  'IDU-1739-2023'
-- Lo que no tiene forma PREFIJO-NUMERO-AÑO (por ejemplo 'CO1.PCCNTR.265317') queda en NULL.
CREATE OR REPLACE FUNCTION normalizar_contrato(t text) RETURNS text
LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE WHEN m IS NULL THEN NULL ELSE m[1] || '-' || m[2] || '-' || m[3] END
    FROM (SELECT regexp_match(upper(coalesce(t, '')), '^\s*([A-Z]+)[\s-]*(\d+)[\s-]*(\d{4})\s*$') AS m) x
$$;


-- ---------------------------------------------------------------------
-- clean_obras
-- Se descartan: foto2 e informacion (texto largo, sigue en stg_obras),
-- el número del contrato principal (igual a contrato) y el tipo y los
-- empleos de la interventoría.
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS clean_obras CASCADE;

CREATE TABLE clean_obras AS
WITH base AS (
    SELECT o.*,
           replace(o.informacion, chr(160), ' ') AS info
    FROM stg_obras o
)
SELECT
    objectid::integer                                             AS objectid,
    nombre,
    etapa,
    normalizar_contrato(contrato)                                 AS contrato,
    codigo_sigidu,
    NULLIF(lon, '')::numeric                                      AS lon,
    NULLIF(lat, '')::numeric                                      AS lat,

    -- Sacado del texto de la ficha
    trim(substring(info FROM 'Estado del contrato:\s*([^\n\r]+)')) AS estado_contrato,
    limpiar_fecha(substring(info FROM 'Fecha de actualizaci.n:\s*(\d{2}/\d{2}/\d{4})'))
                                                                  AS fecha_actualizacion,

    -- Avance (%)
    limpiar_pct(avance_programado_del_contrato)                   AS avance_programado,
    limpiar_pct(avance_ejecutado_del_contrato)                    AS avance_ejecutado,
    limpiar_pct(avance_etapa_actual_programado)                   AS avance_etapa_programado,
    limpiar_pct(avance_etapa_actual_ejecutado)                    AS avance_etapa_ejecutado,

    -- Contrato principal
    limpiar_texto(contrato_principal_tipo)                        AS contrato_tipo,
    limpiar_texto(contrato_principal_contratista)                 AS contratista,
    limpiar_pesos(contrato_principal_valor_total)                 AS valor_contrato,
    limpiar_fecha(contrato_principal_fecha_de_inicio)             AS fecha_inicio,
    limpiar_fecha(contrato_principal_fecha_de_finalizacion)       AS fecha_fin,
    limpiar_entero(contrato_principal_empleos_generados)          AS empleos,
    limpiar_pesos(total_pagado_contrato_principal)                AS total_pagado,

    -- Interventoría
    normalizar_contrato(limpiar_texto(interventoria_numero_de_contrato)) AS interventoria_contrato,
    limpiar_texto(interventoria_contratista)                      AS interventoria_contratista,
    limpiar_pesos(interventoria_valor_total)                      AS interventoria_valor,
    limpiar_fecha(interventoria_fecha_de_inicio)                  AS interventoria_fecha_inicio,
    limpiar_fecha(interventoria_fecha_de_finalizacion)            AS interventoria_fecha_fin,
    limpiar_pesos(total_pagado_interventoria)                     AS interventoria_total_pagado,

    -- Predios
    limpiar_entero(no_predios_requeridos)                         AS predios_requeridos,
    limpiar_entero(no_predios_entregados)                         AS predios_entregados,
    limpiar_entero(no_predios_pendientes)                         AS predios_pendientes,
    limpiar_entero(no_predios_disponibles)                        AS predios_disponibles,
    limpiar_pesos(valor_estimado_de_predios)                      AS predios_valor_estimado,
    limpiar_pesos(valor_ejecutado_de_predios)                     AS predios_valor_ejecutado,
    limpiar_pesos(valor_girado_de_predios)                        AS predios_valor_girado
FROM base;

ALTER TABLE clean_obras ADD PRIMARY KEY (objectid);
CREATE INDEX ON clean_obras (contrato);


-- ---------------------------------------------------------------------
-- clean_obras_metas
-- Las ~46 columnas "meta_fisica_*" (casi todas vacías) pasan a formato largo:
-- una fila por obra y tipo de meta.   '3.5 Km'  ->  cantidad 3.5, unidad 'Km'
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS clean_obras_metas CASCADE;

CREATE TABLE clean_obras_metas AS
SELECT
    o.objectid::integer                                  AS objectid,
    substring(j.key FROM '^meta_fisica_(.*)$')           AS tipo_meta,
    (m)[1]::numeric                                      AS cantidad,
    NULLIF(trim((m)[2]), '')                             AS unidad
FROM stg_obras o
CROSS JOIN LATERAL jsonb_each_text(to_jsonb(o)) AS j(key, value)
CROSS JOIN LATERAL regexp_match(replace(j.value, chr(160), ' '),
                                '^\s*(-?\d+(?:\.\d+)?)\s*(.*)$') AS m
WHERE j.key LIKE 'meta\_fisica\_%'
  AND j.value IS NOT NULL
  AND m IS NOT NULL;

CREATE INDEX ON clean_obras_metas (objectid);


-- ---------------------------------------------------------------------
-- clean_secop
-- - Se excluyen los contratos de prestación de servicios.
-- - Una fila por id_contrato (si hubiera repetidos, queda el más reciente).
-- - 'contrato' es la llave normalizada para cruzar con clean_obras.contrato.
-- - Las fechas de SECOP vienen como '2019-10-16T20:36:31.076'; se guarda la fecha.
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS clean_secop CASCADE;

CREATE TABLE clean_secop AS
SELECT DISTINCT ON (id_contrato)
    id_contrato,
    proceso_de_compra,
    referencia_del_contrato,
    normalizar_contrato(referencia_del_contrato)              AS contrato,
    estado_contrato,
    tipo_de_contrato,
    modalidad_de_contratacion,
    descripcion_del_proceso,
    objeto_del_contrato,
    proveedor_adjudicado,
    NULLIF(left(fecha_de_firma, 10), '')::date                AS fecha_firma,
    NULLIF(left(fecha_de_inicio_del_contrato, 10), '')::date  AS fecha_inicio,
    NULLIF(left(fecha_de_fin_del_contrato, 10), '')::date     AS fecha_fin,
    NULLIF(dias_adicionados, '')::integer                     AS dias_adicionados,
    NULLIF(valor_del_contrato, '')::numeric                   AS valor_contrato,
    NULLIF(valor_facturado, '')::numeric                      AS valor_facturado,
    NULLIF(valor_pagado, '')::numeric                         AS valor_pagado,
    NULLIF(valor_pendiente_de_pago, '')::numeric              AS valor_pendiente_pago,
    NULLIF(valor_pendiente_de_ejecucion, '')::numeric         AS valor_pendiente_ejecucion,
    origen_de_los_recursos,
    ciudad,
    departamento,
    urlproceso,
    NULLIF(left(ultima_actualizacion, 10), '')::date          AS ultima_actualizacion,
    es_obra_vial,
    palabras_encontradas
FROM stg_secop_contratos
WHERE coalesce(tipo_de_contrato, '') NOT ILIKE 'prestaci%n de servicios%'
ORDER BY id_contrato, ultima_actualizacion DESC NULLS LAST;

ALTER TABLE clean_secop ADD PRIMARY KEY (id_contrato);
CREATE INDEX ON clean_secop (contrato);
