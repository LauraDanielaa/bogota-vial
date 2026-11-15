-- =====================================================================
-- 06_ml.sql
-- Insumos y tablas de resultados de los modelos de machine learning (carpeta ml/).
-- Cada modelo tiene su propia sección.
--
-- Modelo: riesgo de prórroga (ml/riesgo_prorroga)
--   duracion_dias(...)             '24 Mes(es)' -> 720 días
--   v_ml_contratos                 1 fila por contrato de clean_secop (913) con las
--                                  variables conocidas al firmar, la etiqueta y si está vigente
--   ml_prorroga_metricas           métricas de cada modelo en cada versión (entrenamiento)
--   ml_prorroga_contrato           probabilidad de prórroga de cada contrato y sus 3 factores
--   ml_riesgo_obra                 nivel de riesgo de atraso de cada obra
--   clasificar_riesgo(...)         reglas del nivel de riesgo de una obra
--   v_prorroga_version_activa      versión del modelo que usa el backend
--
-- Las tablas ml_* se crean solo si no existen: el ETL NO las borra, así que las
-- predicciones se conservan al volver a correrlo. Tampoco tienen llaves foráneas
-- a tablas que el ETL borra y recrea (clean_secop, obras_integradas).
-- Las llena el entrenamiento:  docker compose run --rm ml riesgo_prorroga
-- =====================================================================


-- ---------------------------------------------------------------------
-- Duración pactada en días, sacada del texto de SECOP.
--   '24 Mes(es)' -> 720   '345 Dia(s)' -> 345   '2 Año(s)' -> 730
--   'Dia(s)' (sin número), 'No definido' -> NULL
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION duracion_dias(t text) RETURNS integer
LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE
        WHEN m IS NULL THEN NULL
        WHEN m[2] ILIKE 'mes%' THEN m[1]::integer * 30
        WHEN m[2] ILIKE 'a%o%' THEN m[1]::integer * 365
        WHEN m[2] ILIKE 'd%a%' THEN m[1]::integer
    END
    FROM (SELECT regexp_match(trim(coalesce(t, '')), '^(\d+)\s*([[:alpha:]ñÑ]+)') AS m) x
$$;


-- ---------------------------------------------------------------------
-- v_ml_contratos: insumo del modelo de prórroga
-- clean_secop no trae duración, si se puede prorrogar ni la categoría:
-- se toman de stg_secop_contratos por id_contrato.
--
-- Solo salen columnas conocidas al firmar el contrato, la etiqueta y es_vigente.
-- NO salen (filtran la respuesta): estado_contrato, fecha_fin, duraciones calculadas
-- con fecha_fin, fecha de notificación de prórroga, ultima_actualizacion.
--
-- es_vigente: contratos que aún podrían prorrogarse (sin días adicionados, que no están
-- terminados ni cerrados y cuya fecha de fin no ha pasado a la fecha de descarga).
-- No se usan para entrenar, solo reciben predicción. El estado y la fecha de fin se usan
-- aquí para separar filas, nunca como variables.
-- ---------------------------------------------------------------------
DROP VIEW IF EXISTS v_ml_contratos;

CREATE VIEW v_ml_contratos AS
WITH s AS (
    SELECT DISTINCT ON (id_contrato)
        id_contrato,
        duraci_n_del_contrato,
        el_contrato_puede_ser_prorrogado,
        codigo_de_categoria_principal,
        codigo_proveedor
    FROM stg_secop_contratos
    ORDER BY id_contrato, ultima_actualizacion DESC NULLS LAST
),
corte AS (
    SELECT max(NULLIF(left(fecha_descarga, 10), '')::date) AS fecha FROM stg_secop_contratos
)
SELECT
    c.id_contrato,
    c.contrato,
    c.tipo_de_contrato,
    c.modalidad_de_contratacion,
    c.origen_de_los_recursos,
    (upper(trim(s.el_contrato_puede_ser_prorrogado)) LIKE 'S%')   AS puede_prorrogarse,
    NULLIF(trim(s.codigo_de_categoria_principal), '')             AS categoria,
    c.valor_contrato,
    s.duraci_n_del_contrato                                       AS duracion_texto,
    duracion_dias(s.duraci_n_del_contrato)                        AS duracion_dias,
    c.fecha_firma,
    coalesce(NULLIF(trim(s.codigo_proveedor), ''), c.proveedor_adjudicado) AS codigo_proveedor,
    coalesce(c.dias_adicionados, 0)                               AS dias_adicionados,
    (coalesce(c.dias_adicionados, 0) > 0)::int                    AS prorrogado,
    (coalesce(c.dias_adicionados, 0) = 0
     AND lower(coalesce(c.estado_contrato, '')) NOT IN ('terminado', 'cerrado')
     AND (c.fecha_fin IS NULL OR c.fecha_fin >= (SELECT fecha FROM corte)))   AS es_vigente
FROM clean_secop c
JOIN s USING (id_contrato);


-- ---------------------------------------------------------------------
-- Tablas de resultados (las llena ml/riesgo_prorroga). Nunca se borran aquí.
-- ---------------------------------------------------------------------

-- Una fila por modelo comparado en cada versión (corrida) del entrenamiento
CREATE TABLE IF NOT EXISTS ml_prorroga_metricas (
    version            text        NOT NULL,   -- 'AAAAMMDD-HHMMSS'
    modelo             text        NOT NULL,   -- 'linea_base', 'regresion_logistica', ...
    seleccionado       boolean     NOT NULL DEFAULT false,
    entrenado_en       timestamptz NOT NULL DEFAULT now(),
    n_entrenamiento    integer,
    n_positivos        integer,
    n_vigentes         integer,
    cv_pr_auc          numeric,                -- validación cruzada estratificada, 5 pliegues
    cv_pr_auc_std      numeric,
    cv_roc_auc         numeric,
    cv_brier           numeric,
    temporal_pr_auc    numeric,                -- entrena hasta 2023, prueba 2024 en adelante
    temporal_roc_auc   numeric,
    temporal_n_prueba  integer,
    linea_base_pr_auc  numeric,                -- PR-AUC de la línea base (prevalencia)
    brier_calibrado    numeric,                -- Brier de las probabilidades calibradas fuera de pliegue
    supera_linea_base  boolean,
    variables          text[],
    nota               text,
    PRIMARY KEY (version, modelo)
);

-- Probabilidad de prórroga de cada contrato
CREATE TABLE IF NOT EXISTS ml_prorroga_contrato (
    version        text    NOT NULL,
    id_contrato    text    NOT NULL,
    probabilidad   numeric NOT NULL,
    origen         text    NOT NULL,   -- 'fuera_de_pliegue' (entrenamiento) | 'vigente'
    prorrogado     integer,            -- etiqueta real (solo entrenamiento)
    factores       jsonb,              -- [{"variable", "texto", "efecto": "aumenta"|"reduce"}]
    PRIMARY KEY (version, id_contrato)
);

-- Riesgo de atraso de cada obra
CREATE TABLE IF NOT EXISTS ml_riesgo_obra (
    version            text    NOT NULL,
    objectid           integer NOT NULL,
    id_contrato        text,
    nivel              text    NOT NULL,   -- No aplica | Sin dato | Prorrogada | Alto | Medio | Bajo
    probabilidad       numeric,
    dias_adicionados   integer,
    factores           jsonb,
    PRIMARY KEY (version, objectid)
);


-- ---------------------------------------------------------------------
-- Nivel de riesgo de atraso de UNA obra. Reglas, en orden:
--   * No aplica  : la obra está Finalizada o Caducada.
--   * Sin dato   : no tiene contrato en SECOP.
--   * Prorrogada : su contrato ya tiene días adicionados.
--   * Alto / Medio / Bajo según la probabilidad de prórroga
--     (umbrales de partida: 30 % y 60 %).
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION clasificar_riesgo(
    p_estado_seguimiento  text,
    p_id_contrato         text,
    p_dias_adicionados    integer,
    p_probabilidad        numeric,
    p_umbral_medio        numeric DEFAULT 0.30,
    p_umbral_alto         numeric DEFAULT 0.60
) RETURNS text
LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE
        WHEN p_estado_seguimiento IN ('Finalizada', 'Caducada') THEN 'No aplica'
        WHEN p_id_contrato IS NULL THEN 'Sin dato'
        WHEN coalesce(p_dias_adicionados, 0) > 0 THEN 'Prorrogada'
        WHEN p_probabilidad IS NULL THEN 'Sin dato'
        WHEN p_probabilidad >= p_umbral_alto THEN 'Alto'
        WHEN p_probabilidad >= p_umbral_medio THEN 'Medio'
        ELSE 'Bajo'
    END
$$;


-- ---------------------------------------------------------------------
-- Versión activa: la última corrida que dejó un modelo seleccionado.
-- Vacía mientras el modelo no se haya entrenado (el backend muestra "Sin calcular").
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_prorroga_version_activa AS
SELECT version
FROM ml_prorroga_metricas
WHERE seleccionado
ORDER BY entrenado_en DESC, version DESC
LIMIT 1;
