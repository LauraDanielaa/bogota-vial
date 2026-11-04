-- =====================================================================
-- 03_localidad.sql
-- Asigna la localidad a cada obra según sus coordenadas (PostGIS).
--
-- Entra:  stg_localidades (cargada desde el GeoJSON), obras_integradas
-- Crea:   clean_localidades            20 localidades de Bogotá
-- Agrega a obras_integradas:  geom, localidad_codigo, localidad_nombre
--
-- Requiere la extensión PostGIS (la imagen postgis/postgis ya la trae).
-- =====================================================================

CREATE EXTENSION IF NOT EXISTS postgis;

-- ---------------------------------------------------------------------
-- Localidades: de JSON con propiedades a columnas
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS clean_localidades CASCADE;

CREATE TABLE clean_localidades AS
SELECT
    propiedades->>'LocCodigo'             AS codigo,
    propiedades->>'LocNombre'             AS nombre,
    (propiedades->>'LocArea')::numeric    AS area_m2,
    geom
FROM stg_localidades;

ALTER TABLE clean_localidades ADD PRIMARY KEY (codigo);
CREATE INDEX ON clean_localidades USING GIST (geom);

-- ---------------------------------------------------------------------
-- Obras: punto + localidad
-- ---------------------------------------------------------------------
ALTER TABLE obras_integradas ADD COLUMN IF NOT EXISTS geom             geometry(Point, 4326);
ALTER TABLE obras_integradas ADD COLUMN IF NOT EXISTS localidad_codigo text;
ALTER TABLE obras_integradas ADD COLUMN IF NOT EXISTS localidad_nombre text;

-- Se limpia por si el archivo se corre dos veces
UPDATE obras_integradas SET geom = NULL, localidad_codigo = NULL, localidad_nombre = NULL;

-- Solo coordenadas que caen en la zona de Bogotá; lo demás queda sin punto
UPDATE obras_integradas
SET geom = ST_SetSRID(ST_MakePoint(lon, lat), 4326)
WHERE lon BETWEEN -75 AND -73
  AND lat BETWEEN 3.5 AND 5.5;

UPDATE obras_integradas o
SET localidad_codigo = l.codigo,
    localidad_nombre = l.nombre
FROM clean_localidades l
WHERE ST_Intersects(l.geom, o.geom);

CREATE INDEX IF NOT EXISTS obras_integradas_geom_idx ON obras_integradas USING GIST (geom);
