-- =====================================================================
-- 02_cruce.sql
-- Une cada obra del visor con su contrato de SECOP (por número de contrato)
-- y completa los datos que le faltan al visor con los de SECOP.
--
-- Entra:  clean_obras, clean_secop
-- Crea:   obras_integradas   1 fila por obra (124), con el cruce y el completado
--
-- Reglas:
--   * El visor manda: si trae el dato, se usa el del visor.
--     (Es más reciente: refleja prórrogas y adiciones.)
--   * Si el visor no lo trae, se toma el de SECOP.
--   * Cada dato completado dice de dónde salió en una columna fuente_*.
--   * Si ninguna fuente lo tiene, queda NULL. No se inventan valores.
--   * El estado NO se completa con SECOP: sus valores son distintos
--     ('EN EJECUCION' vs 'En ejecución'). El de SECOP va aparte en secop_estado.
-- =====================================================================

DROP TABLE IF EXISTS obras_integradas CASCADE;

CREATE TABLE obras_integradas AS
WITH secop AS (
    -- Una sola fila de SECOP por número de contrato (la firmada más reciente),
    -- para que el cruce nunca duplique obras.
    SELECT DISTINCT ON (contrato) *
    FROM clean_secop
    WHERE contrato IS NOT NULL
    ORDER BY contrato, fecha_firma DESC NULLS LAST, ultima_actualizacion DESC NULLS LAST
)
SELECT
    o.objectid,
    o.nombre,
    o.etapa,
    o.contrato,
    o.codigo_sigidu,
    o.lon,
    o.lat,
    o.estado_contrato,
    o.fecha_actualizacion,
    o.avance_programado,
    o.avance_ejecutado,
    o.avance_etapa_programado,
    o.avance_etapa_ejecutado,
    o.contrato_tipo,

    -- ----- datos completados -----
    CASE WHEN o.contratista IS NOT NULL THEN o.contratista
         ELSE s.proveedor_adjudicado END                          AS contratista,
    CASE WHEN o.contratista IS NOT NULL THEN 'visor'
         WHEN s.proveedor_adjudicado IS NOT NULL THEN 'secop' END AS fuente_contratista,

    -- Un valor 0 en el visor se trata como "sin dato" si SECOP trae uno mayor que 0.
    CASE WHEN o.valor_contrato > 0 THEN o.valor_contrato
         WHEN s.valor_contrato > 0 THEN s.valor_contrato
         ELSE o.valor_contrato END                                AS valor_contrato,
    CASE WHEN o.valor_contrato > 0 THEN 'visor'
         WHEN s.valor_contrato > 0 THEN 'secop'
         WHEN o.valor_contrato IS NOT NULL THEN 'visor' END       AS fuente_valor,

    COALESCE(o.fecha_inicio, s.fecha_inicio)                      AS fecha_inicio,
    CASE WHEN o.fecha_inicio IS NOT NULL THEN 'visor'
         WHEN s.fecha_inicio IS NOT NULL THEN 'secop' END         AS fuente_fecha_inicio,
    COALESCE(o.fecha_fin, s.fecha_fin)                            AS fecha_fin,
    CASE WHEN o.fecha_fin IS NOT NULL THEN 'visor'
         WHEN s.fecha_fin IS NOT NULL THEN 'secop' END            AS fuente_fecha_fin,

    -- ----- resto del visor -----
    o.empleos,
    o.total_pagado,
    o.interventoria_contrato,
    o.interventoria_contratista,
    o.interventoria_valor,
    o.interventoria_fecha_inicio,
    o.interventoria_fecha_fin,
    o.interventoria_total_pagado,
    o.predios_requeridos,
    o.predios_entregados,
    o.predios_pendientes,
    o.predios_disponibles,
    o.predios_valor_estimado,
    o.predios_valor_ejecutado,
    o.predios_valor_girado,

    -- ----- lo que aporta SECOP -----
    (s.id_contrato IS NOT NULL)                                   AS en_secop,
    s.id_contrato                                                 AS secop_id_contrato,
    s.estado_contrato                                             AS secop_estado,
    s.tipo_de_contrato                                            AS secop_tipo,
    s.modalidad_de_contratacion                                   AS secop_modalidad,
    s.fecha_firma                                                 AS secop_fecha_firma,
    s.valor_facturado                                             AS secop_valor_facturado,
    s.valor_pagado                                                AS secop_valor_pagado,
    s.urlproceso                                                  AS secop_url
FROM clean_obras o
LEFT JOIN secop s ON s.contrato = o.contrato;

ALTER TABLE obras_integradas ADD PRIMARY KEY (objectid);
CREATE INDEX ON obras_integradas (contrato);
