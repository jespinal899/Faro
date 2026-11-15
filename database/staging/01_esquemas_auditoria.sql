-- =====================================================================
-- Faro · Staging (base faro_analytics) · Esquemas, auditoría y cuarentena
-- IDEMPOTENTE: se puede ejecutar varias veces sin error ni pérdida de datos.
-- Diseño: documentation/arquitectura/diseno-staging-etl.md
-- =====================================================================

CREATE SCHEMA IF NOT EXISTS audit;
CREATE SCHEMA IF NOT EXISTS stg_raw;
CREATE SCHEMA IF NOT EXISTS stg_clean;
CREATE SCHEMA IF NOT EXISTS stg_quarantine;
CREATE SCHEMA IF NOT EXISTS stg_ready;

COMMENT ON SCHEMA audit          IS 'Auditoría del ETL: ejecuciones, pasos, watermarks y resultados de calidad.';
COMMENT ON SCHEMA stg_raw        IS 'Landing/Raw: copia fiel de lo extraído de la fuente. Solo se agregan filas.';
COMMENT ON SCHEMA stg_clean      IS 'Clean/Validated: versión vigente de cada registro, limpia y validada.';
COMMENT ON SCHEMA stg_quarantine IS 'Registros rechazados por una regla de calidad.';
COMMENT ON SCHEMA stg_ready      IS 'Ready/Integration: entidades integradas listas para el Data Warehouse.';

-- ---------------------------------------------------------------------
-- Una fila por ejecución del pipeline (exitosa o fallida)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit.etl_execution (
    execution_id    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pipeline_name   text        NOT NULL,
    trigger         text        NOT NULL,           -- cron, manual, ci
    mode            text        NOT NULL,           -- inicial, incremental
    start_time      timestamptz NOT NULL DEFAULT now(),
    end_time        timestamptz,
    status          text        NOT NULL DEFAULT 'en_curso'
                    CHECK (status IN ('en_curso', 'exitoso', 'fallido')),
    rows_read       bigint      NOT NULL DEFAULT 0,
    rows_inserted   bigint      NOT NULL DEFAULT 0,
    rows_updated    bigint      NOT NULL DEFAULT 0,
    rows_rejected   bigint      NOT NULL DEFAULT 0,
    rows_unchanged  bigint      NOT NULL DEFAULT 0,
    reconciled      boolean,                        -- ¿fuente = clean + cuarentena?
    error_detail    text,
    git_sha         text
);
COMMENT ON TABLE audit.etl_execution IS 'Una fila por ejecución del pipeline, con conteos totales, estado y error.';

-- ---------------------------------------------------------------------
-- Una fila por tabla y etapa dentro de una ejecución
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit.etl_step (
    step_id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    execution_id     bigint      NOT NULL REFERENCES audit.etl_execution (execution_id),
    step             text        NOT NULL,          -- extract, clean, reconcile
    source_object    text        NOT NULL,
    target_object    text        NOT NULL,
    rows_read        bigint      NOT NULL DEFAULT 0,
    rows_inserted    bigint      NOT NULL DEFAULT 0,
    rows_updated     bigint      NOT NULL DEFAULT 0,
    rows_rejected    bigint      NOT NULL DEFAULT 0,
    rows_unchanged   bigint      NOT NULL DEFAULT 0,
    watermark_start  text,                          -- texto: admite '-infinity'
    watermark_end    text,
    duration_ms      integer,
    status           text        NOT NULL DEFAULT 'ok'
);
CREATE INDEX IF NOT EXISTS ix_etl_step_execution ON audit.etl_step (execution_id);
COMMENT ON TABLE audit.etl_step IS 'Detalle por tabla y etapa: conteos, rango de watermark procesado y duración.';

-- ---------------------------------------------------------------------
-- Marca de agua por tabla de la fuente (carga incremental)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit.watermark (
    source_table  text        PRIMARY KEY,
    last_value    timestamptz NOT NULL,
    execution_id  bigint      NOT NULL REFERENCES audit.etl_execution (execution_id),
    updated_at    timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE audit.watermark IS
    'Máximo last_edited_when ya procesado por tabla. Solo avanza si la ejecución termina bien.';

-- ---------------------------------------------------------------------
-- Catálogo de reglas de calidad (se sincroniza desde etl/config.py)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit.dq_rule (
    source_table  text NOT NULL,
    rule_code     text NOT NULL,
    dimension     text NOT NULL,
    description   text NOT NULL,
    action        text NOT NULL CHECK (action IN ('cuarentena', 'marcar')),
    PRIMARY KEY (source_table, rule_code)
);
COMMENT ON TABLE audit.dq_rule IS 'Catálogo de reglas de calidad vigentes y la acción que aplica cada una.';

-- ---------------------------------------------------------------------
-- Resultado de cada regla en cada ejecución (calidad "antes y después")
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit.dq_result (
    execution_id  bigint NOT NULL REFERENCES audit.etl_execution (execution_id),
    source_table  text   NOT NULL,
    rule_code     text   NOT NULL,
    action        text   NOT NULL,
    rows_checked  bigint NOT NULL,
    rows_failed   bigint NOT NULL,
    PRIMARY KEY (execution_id, source_table, rule_code)
);
COMMENT ON TABLE audit.dq_result IS 'Filas evaluadas y filas que fallaron por regla, tabla y ejecución.';

-- ---------------------------------------------------------------------
-- Cuarentena: registro original completo + regla que falló
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stg_quarantine.registro_rechazado (
    rechazo_id    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    execution_id  bigint      NOT NULL REFERENCES audit.etl_execution (execution_id),
    source_table  text        NOT NULL,
    natural_key   integer     NOT NULL,
    rule_code     text        NOT NULL,
    rule_detail   text        NOT NULL,
    payload       jsonb       NOT NULL,             -- el registro tal como llegó
    rejected_at   timestamptz NOT NULL DEFAULT now(),
    resolved_at   timestamptz,                      -- se llena cuando el registro corregido entra a clean
    CONSTRAINT uq_rechazo UNIQUE (source_table, natural_key, rule_code)
);
COMMENT ON TABLE stg_quarantine.registro_rechazado IS
    'Registros que no pasaron una regla de cuarentena. Se reintentan en cada ejecución.';
