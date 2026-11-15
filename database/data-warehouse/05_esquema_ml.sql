-- =====================================================================
-- Faro · Machine Learning (base faro_analytics, esquema ml). IDEMPOTENTE.
-- Pronóstico semanal de ventas netas por grupo principal de producto (pregunta P10).
-- Diseño: documentation/modelos/modelo-ml.md · decisión D-24
--
-- El modelo NO lee el DW directamente: solo la vista ml.ventas_semanales (vista analítica
-- controlada, como pide la guía). Escribe su registro y sus predicciones en las tablas de
-- este esquema con el rol faro_ml.
-- =====================================================================

CREATE SCHEMA IF NOT EXISTS ml;
COMMENT ON SCHEMA ml IS
    'Machine Learning: serie de entrada, registro de modelos, evaluación y pronósticos.';

-- ------------------------------------------------------------- entrada
-- Una fila por semana (lunes) y grupo principal de producto, con la parte simulada aparte
-- para poder entrenar SOLO con datos reales. El grupo es el de la versión del producto
-- vigente en la fecha de la venta (SCD2), así cada venta se cuenta una sola vez (H04).
CREATE OR REPLACE VIEW ml.ventas_semanales AS
SELECT date_trunc('week', f.fecha_factura)::date                           AS semana,
       p.grupo_principal                                                    AS grupo,
       sum(f.venta_neta)                                                    AS venta_neta,
       coalesce(sum(f.venta_neta) FILTER (WHERE NOT f.es_simulado), 0)      AS venta_neta_real,
       coalesce(sum(f.venta_neta) FILTER (WHERE f.es_simulado), 0)          AS venta_neta_simulada,
       sum(f.cantidad)                                                      AS unidades,
       count(*)                                                             AS lineas,
       min(f.fecha_factura)                                                 AS primera_fecha,
       max(f.fecha_factura)                                                 AS ultima_fecha,
       max(f.fecha_factura) FILTER (WHERE NOT f.es_simulado)                AS ultima_fecha_real
FROM dw.fact_ventas f
JOIN dw.dim_producto p ON p.producto_key = f.producto_key
WHERE f.producto_key <> -1
GROUP BY 1, 2;
COMMENT ON VIEW ml.ventas_semanales IS
    'Serie de entrada del pronóstico: ventas netas por semana (lunes) y grupo principal.';

-- ------------------------------------------------------ registro de modelos
CREATE TABLE IF NOT EXISTS ml.modelo (
    modelo_id            integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre               text        NOT NULL,
    version              text        NOT NULL UNIQUE,         -- AAAAMMDD.HHMMSS (UTC)
    algoritmo            text        NOT NULL,
    parametros           jsonb       NOT NULL,
    variables            jsonb       NOT NULL,
    grupos               jsonb       NOT NULL,                -- incluidos y excluidos con motivo
    metricas             jsonb       NOT NULL,                -- validación y prueba, modelo y líneas base
    intervalo            jsonb       NOT NULL,                -- cuantiles del error por horizonte
    datos_desde          date        NOT NULL,                -- primera semana de la serie
    datos_hasta          date        NOT NULL,                -- última semana usada (solo datos reales)
    prueba_desde         date        NOT NULL,                -- primera semana del conjunto de prueba
    filas_entrenamiento  integer     NOT NULL,
    huella_datos         text        NOT NULL,                -- md5 de la serie usada (reproducibilidad)
    commit_codigo        text,                                -- commit de git que entrenó el modelo
    entrenado_en         timestamptz NOT NULL DEFAULT now(),
    es_vigente           boolean     NOT NULL DEFAULT false,
    artefacto            bytea       NOT NULL                 -- modelo serializado (joblib)
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_modelo_vigente ON ml.modelo (nombre) WHERE es_vigente;
COMMENT ON TABLE ml.modelo IS
    'Registro de modelos: versión, parámetros, métricas, datos usados y el modelo serializado. '
    'Solo uno vigente por nombre.';

-- ------------------------------------------- evaluación en el conjunto de prueba
CREATE TABLE IF NOT EXISTS ml.prediccion_prueba (
    modelo_id    integer       NOT NULL REFERENCES ml.modelo ON DELETE CASCADE,
    semana       date          NOT NULL,
    grupo        text          NOT NULL,
    horizonte    smallint      NOT NULL CHECK (horizonte BETWEEN 1 AND 4),
    origen       date          NOT NULL,                     -- última semana conocida al predecir
    real         numeric(18,2) NOT NULL,
    pronostico   numeric(18,2) NOT NULL,
    inferior     numeric(18,2) NOT NULL,
    superior     numeric(18,2) NOT NULL,
    linea_base   numeric(18,2) NOT NULL,                     -- la mejor línea base en validación
    PRIMARY KEY (modelo_id, semana, grupo, horizonte)
);
COMMENT ON TABLE ml.prediccion_prueba IS
    'Predicciones del modelo y de la línea base sobre semanas NO usadas para entrenar ni elegir el modelo.';

-- ------------------------------------------------------------- pronósticos
CREATE TABLE IF NOT EXISTS ml.pronostico (
    modelo_id                 integer       NOT NULL REFERENCES ml.modelo,
    origen                    date          NOT NULL,        -- última semana completa usada como dato
    semana                    date          NOT NULL,        -- semana pronosticada (lunes)
    grupo                     text          NOT NULL,
    horizonte                 smallint      NOT NULL CHECK (horizonte BETWEEN 1 AND 4),
    venta_neta_pronosticada   numeric(18,2) NOT NULL,
    inferior                  numeric(18,2) NOT NULL,        -- rango probable (80 %)
    superior                  numeric(18,2) NOT NULL,
    usa_datos_simulados       boolean       NOT NULL,        -- la historia usada incluye ventas simuladas
    generado_en               timestamptz   NOT NULL DEFAULT now(),
    PRIMARY KEY (modelo_id, origen, semana, grupo),
    CHECK (inferior <= venta_neta_pronosticada AND venta_neta_pronosticada <= superior)
);
COMMENT ON TABLE ml.pronostico IS
    'PREDICCIONES (no son datos históricos): ventas netas por semana y grupo, con versión del '
    'modelo, fecha de origen y horizonte.';
