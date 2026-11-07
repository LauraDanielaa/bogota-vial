-- =====================================================================
-- 05_indicadores.sql
-- Funciones para los indicadores de la página principal (tarjetas del mapa).
--
--   clasificar_obra(...)       estado de seguimiento de UNA obra:
--                              'En ejecución' | 'Retrasada' | 'Suspendida'
--                              | 'Finalizada' | 'Caducada' | 'Sin dato'
--   v_obras_seguimiento        obras_integradas + su estado de seguimiento y brecha
--   fn_indicadores_obras(...)  1 fila con los totales (toda Bogotá o una localidad)
--
-- Reglas (umbral por defecto: 10 puntos porcentuales):
--   * Suspendida : estado del contrato = SUSPENDIDO.
--   * Retrasada  : contrato EN EJECUCION y
--                    - el avance ejecutado va 10 pp o más por debajo del programado, o
--                    - la fecha de fin ya pasó y la obra no llega al 100 %.
--   * En ejecución: contrato EN EJECUCION que no está retrasado.
--   * Finalizada : LIQUIDADO, TERMINADO... o EN TRAMITE ACTA TERMINACION.
--   * Caducada   : CADUCADO (el contrato se terminó sin completarse).
--   El umbral de 10 pp sale de los datos: en las obras en ejecución la brecha
--   salta de ~9 pp a ~13 pp, no hay casos intermedios.
--
-- Avance físico promedio = media simple de avance_ejecutado por obra
-- (las obras sin dato de avance no cuentan).
-- =====================================================================

-- ---------------------------------------------------------------------
-- Estado de seguimiento de una obra
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION clasificar_obra(
    p_estado      text,
    p_ejecutado   numeric,
    p_programado  numeric,
    p_fecha_fin   date,
    p_umbral      numeric DEFAULT 10
) RETURNS text
LANGUAGE sql STABLE AS $$
    SELECT CASE
        WHEN e = 'SUSPENDIDO' THEN 'Suspendida'
        WHEN e = 'EN EJECUCION' THEN
            CASE
                WHEN coalesce(p_programado - p_ejecutado, 0) >= p_umbral
                  OR (p_fecha_fin < current_date AND coalesce(p_ejecutado, 0) < 100)
                THEN 'Retrasada'
                ELSE 'En ejecución'
            END
        WHEN e = 'LIQUIDADO' OR e LIKE 'TERMINADO%' OR e LIKE 'EN TRAMITE ACTA TERMINACION%'
            THEN 'Finalizada'
        WHEN e = 'CADUCADO' THEN 'Caducada'
        ELSE 'Sin dato'
    END
    FROM (SELECT upper(trim(coalesce(p_estado, ''))) AS e) x
$$;


-- ---------------------------------------------------------------------
-- Obras con su estado de seguimiento (para el mapa, el listado o el ML)
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_obras_seguimiento AS
SELECT
    o.*,
    clasificar_obra(o.estado_contrato, o.avance_ejecutado, o.avance_programado, o.fecha_fin)
        AS estado_seguimiento,
    round(o.avance_programado - o.avance_ejecutado, 2) AS brecha_pp
FROM obras_integradas o;


-- ---------------------------------------------------------------------
-- Indicadores agregados. Sin argumentos = toda Bogotá.
--   SELECT * FROM fn_indicadores_obras();          -- toda la ciudad
--   SELECT * FROM fn_indicadores_obras('08');      -- solo Kennedy
-- ---------------------------------------------------------------------
DROP FUNCTION IF EXISTS fn_indicadores_obras(text, numeric);

CREATE FUNCTION fn_indicadores_obras(
    p_localidad_codigo text    DEFAULT NULL,
    p_umbral           numeric DEFAULT 10
) RETURNS TABLE (
    total_obras                 integer,
    n_localidades               integer,
    obras_con_avance            integer,
    avance_fisico_promedio      numeric,
    avance_programado_promedio  numeric,
    n_en_ejecucion              integer,   -- contrato EN EJECUCION (al día + retrasadas)
    n_al_dia                    integer,
    n_retrasadas                integer,
    n_suspendidas               integer,
    n_requieren_atencion        integer,   -- retrasadas + suspendidas
    n_finalizadas               integer,
    n_caducadas                 integer,
    n_sin_dato                  integer
)
LANGUAGE sql STABLE AS $$
    WITH o AS (
        SELECT
            localidad_codigo,
            avance_ejecutado,
            avance_programado,
            clasificar_obra(estado_contrato, avance_ejecutado, avance_programado, fecha_fin, p_umbral) AS est
        FROM obras_integradas
        WHERE p_localidad_codigo IS NULL OR localidad_codigo = p_localidad_codigo
    )
    SELECT
        count(*)::int,
        count(DISTINCT localidad_codigo)::int,
        count(avance_ejecutado)::int,
        round(avg(avance_ejecutado), 1),
        round(avg(avance_programado), 1),
        count(*) FILTER (WHERE est IN ('En ejecución', 'Retrasada'))::int,
        count(*) FILTER (WHERE est = 'En ejecución')::int,
        count(*) FILTER (WHERE est = 'Retrasada')::int,
        count(*) FILTER (WHERE est = 'Suspendida')::int,
        count(*) FILTER (WHERE est IN ('Retrasada', 'Suspendida'))::int,
        count(*) FILTER (WHERE est = 'Finalizada')::int,
        count(*) FILTER (WHERE est = 'Caducada')::int,
        count(*) FILTER (WHERE est = 'Sin dato')::int
    FROM o
$$;
