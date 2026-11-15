-- =====================================================================
-- Faro · Alertas y notificaciones (esquema alerta, base faro_analytics). IDEMPOTENTE.
-- Preguntas P12-P14 · decisión D-26 · documentation/arquitectura/alertas.md
--
-- El evaluador (rol faro_alertas, módulo notifications/) lee SOLO las vistas de entrada de
-- este esquema y el pronóstico aprobado (api.pronostico); escribe alertas, evaluaciones y
-- envíos. Cada evento tiene una clave única: repetir la evaluación no duplica alertas ni
-- correos. La API (faro_api) solo lee las vistas api.* y cambia el estado de una alerta.
-- =====================================================================

CREATE SCHEMA IF NOT EXISTS alerta;
COMMENT ON SCHEMA alerta IS 'Alertas: reglas, evaluaciones, alertas generadas y registro de envíos.';

-- --------------------------------------------------------- entradas controladas
CREATE OR REPLACE VIEW alerta.rango_datos AS
SELECT min(fecha_factura)                                AS desde,
       max(fecha_factura)                                AS hasta,
       max(fecha_factura) FILTER (WHERE NOT es_simulado) AS hasta_real
FROM dw.fact_ventas;
COMMENT ON VIEW alerta.rango_datos IS 'Rango de fechas del DW (para saber qué semanas están completas).';

CREATE OR REPLACE VIEW alerta.ventas_semanales_total AS
SELECT date_trunc('week', fecha_factura)::date AS semana,
       sum(venta_neta)                         AS venta_neta,
       bool_or(es_simulado)                    AS incluye_simulados
FROM dw.fact_ventas
GROUP BY 1;
COMMENT ON VIEW alerta.ventas_semanales_total IS 'Ventas netas de toda la empresa por semana (lunes).';

CREATE OR REPLACE VIEW alerta.bajo_costo_semanal AS
SELECT date_trunc('week', fecha_factura)::date AS semana,
       count(*)                                AS lineas,
       count(DISTINCT factura_id)              AS facturas,
       -sum(utilidad)                          AS perdida,
       sum(venta_neta)                         AS venta_neta,
       bool_or(es_simulado)                    AS incluye_simulados
FROM dw.fact_ventas
WHERE es_venta_bajo_costo
GROUP BY 1;
COMMENT ON VIEW alerta.bajo_costo_semanal IS 'Líneas vendidas bajo costo por semana y la pérdida que dejaron.';

-- ------------------------------------------------------------- reglas
CREATE TABLE IF NOT EXISTS alerta.regla (
    codigo       text    PRIMARY KEY,
    nombre       text    NOT NULL,
    origen       text    NOT NULL CHECK (origen IN ('regla', 'modelo')),
    descripcion  text    NOT NULL,
    umbral       numeric NOT NULL,
    unidad       text    NOT NULL,
    activa       boolean NOT NULL DEFAULT true
);
COMMENT ON TABLE alerta.regla IS
    'Catálogo de reglas de alerta. El umbral se ajusta aquí, sin volver a desplegar el código.';

-- Valores iniciales (si ya existen, se respetan los umbrales ajustados en la base)
INSERT INTO alerta.regla (codigo, nombre, origen, descripcion, umbral, unidad) VALUES
    ('caida_ventas', 'Caída de ventas', 'regla',
     'Las ventas netas de la última semana completa caen más que el umbral frente al promedio '
     'de las 4 semanas anteriores. Crítica si la caída duplica el umbral.', 15, '%'),
    ('pronostico_bajo', 'Pronóstico bajo umbral', 'modelo',
     'El pronóstico de un grupo de producto para alguna de las próximas 4 semanas queda por '
     'debajo del umbral (% de su promedio de las últimas 13 semanas).', 85, '% del promedio'),
    ('ventas_bajo_costo', 'Ventas bajo costo', 'regla',
     'En la última semana completa hubo líneas vendidas por debajo del costo y la pérdida '
     'supera el umbral.', 0, 'USD')
ON CONFLICT (codigo) DO NOTHING;

-- ------------------------------------------------------------- evaluaciones
CREATE TABLE IF NOT EXISTS alerta.evaluacion (
    evaluacion_id     bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    disparador        text        NOT NULL,          -- cron, manual, demo, ci
    inicio            timestamptz NOT NULL DEFAULT now(),
    fin               timestamptz,
    estado            text        NOT NULL DEFAULT 'en_curso'
                          CHECK (estado IN ('en_curso', 'exitosa', 'fallida')),
    reglas_evaluadas  integer     NOT NULL DEFAULT 0,
    alertas_nuevas    integer     NOT NULL DEFAULT 0,
    correos_enviados  integer     NOT NULL DEFAULT 0,
    error             text
);
COMMENT ON TABLE alerta.evaluacion IS 'Cada ejecución del evaluador de alertas (monitoreo).';

-- ------------------------------------------------------------- alertas
CREATE TABLE IF NOT EXISTS alerta.alerta (
    alerta_id               bigint        GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    evaluacion_id           bigint        REFERENCES alerta.evaluacion,
    regla                   text          NOT NULL REFERENCES alerta.regla (codigo),
    clave_evento            text          NOT NULL UNIQUE,   -- regla|entidad|período: sin duplicados
    creada_en               timestamptz   NOT NULL DEFAULT now(),
    severidad               text          NOT NULL CHECK (severidad IN ('advertencia', 'critica')),
    origen                  text          NOT NULL CHECK (origen IN ('regla', 'modelo')),
    indicador               text          NOT NULL,
    entidad                 text          NOT NULL,
    valor_observado         numeric(18,2) NOT NULL,          -- valor real o predicción
    umbral                  numeric(18,2) NOT NULL,
    referencia              numeric(18,2),                   -- valor de comparación
    periodo_desde           date          NOT NULL,
    periodo_hasta           date          NOT NULL,
    detalle                 jsonb         NOT NULL DEFAULT '{}'::jsonb,  -- horizonte, versión del modelo...
    mensaje                 text          NOT NULL,          -- descripción calculada (no IA)
    explicacion_ia          text,                            -- GENERADA POR IA (identificada)
    accion_recomendada_ia   text,                            -- GENERADA POR IA (identificada)
    ia_modelo               text,
    incluye_simulados       boolean       NOT NULL DEFAULT false,
    estado                  text          NOT NULL DEFAULT 'nueva'
                                CHECK (estado IN ('nueva', 'atendida', 'descartada', 'resuelta')),
    estado_actualizado_en   timestamptz,
    estado_actualizado_por  text,
    nota                    text CHECK (length(nota) <= 500)
);
CREATE INDEX IF NOT EXISTS ix_alerta_estado ON alerta.alerta (estado, creada_en DESC);
COMMENT ON TABLE alerta.alerta IS
    'Alertas generadas con su contenido mínimo (guía, sección 9) y su estado.';

-- ------------------------------------------------------------- envíos
CREATE TABLE IF NOT EXISTS alerta.envio (
    envio_id      bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    alerta_id     bigint      NOT NULL REFERENCES alerta.alerta ON DELETE CASCADE,
    canal         text        NOT NULL CHECK (canal IN ('correo')),
    intento       smallint    NOT NULL,
    intentado_en  timestamptz NOT NULL DEFAULT now(),
    resultado     text        NOT NULL CHECK (resultado IN ('enviado', 'fallido')),
    error         text
);
CREATE INDEX IF NOT EXISTS ix_envio_alerta ON alerta.envio (alerta_id);
COMMENT ON TABLE alerta.envio IS 'Cada intento de entrega de una alerta, con su resultado (reintentos).';

-- ------------------------------------------------------------- vistas para la API
CREATE OR REPLACE VIEW api.alertas AS
SELECT a.alerta_id, a.creada_en, a.regla, r.nombre AS regla_nombre, a.severidad, a.origen,
       a.indicador, a.entidad, a.valor_observado, a.umbral, a.referencia, r.unidad,
       a.periodo_desde, a.periodo_hasta, a.detalle, a.mensaje, a.explicacion_ia,
       a.accion_recomendada_ia, a.ia_modelo, a.incluye_simulados, a.estado,
       a.estado_actualizado_en, a.estado_actualizado_por, a.nota,
       coalesce(e.enviado, false)  AS correo_enviado,
       coalesce(e.intentos, 0)     AS intentos_correo,
       e.ultimo_intento
FROM alerta.alerta a
JOIN alerta.regla r ON r.codigo = a.regla
LEFT JOIN (
    SELECT alerta_id, bool_or(resultado = 'enviado') AS enviado, count(*) AS intentos,
           max(intentado_en) AS ultimo_intento
    FROM alerta.envio GROUP BY alerta_id
) e ON e.alerta_id = a.alerta_id;
COMMENT ON VIEW api.alertas IS 'Alertas con su regla, contenido, estado y entrega por correo.';

CREATE OR REPLACE VIEW api.alertas_envios AS
SELECT envio_id, alerta_id, canal, intento, intentado_en, resultado, error FROM alerta.envio;

CREATE OR REPLACE VIEW api.alertas_evaluaciones AS
SELECT evaluacion_id, disparador, inicio, fin, estado, reglas_evaluadas, alertas_nuevas,
       correos_enviados, error
FROM alerta.evaluacion;

CREATE OR REPLACE VIEW api.alertas_reglas AS
SELECT codigo, nombre, origen, descripcion, umbral, unidad, activa FROM alerta.regla;
