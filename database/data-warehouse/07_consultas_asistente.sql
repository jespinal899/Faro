-- =====================================================================
-- Faro · Registro de consultas al asistente de IA (esquema app). IDEMPOTENTE.
-- Decisión D-25 · documentation/arquitectura/asistente-ia.md
--
-- La guía pide "registrar consultas de forma compatible con privacidad y seguridad":
--   * se guarda quién preguntó, cuándo, la pregunta, qué consultas controladas se hicieron
--     (herramienta y parámetros), el tipo de respuesta, los tokens, el costo y la duración;
--   * NO se guarda la respuesta del modelo ni los datos devueltos (se pueden reconstruir con
--     las mismas consultas), ni ningún dato personal de clientes (el asistente no los consulta);
--   * sirve también para el límite de preguntas por usuario (las funciones de Vercel no
--     comparten memoria) y para medir el costo real.
-- =====================================================================

CREATE TABLE IF NOT EXISTS app.consulta_asistente (
    consulta_id     bigint        GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    usuario         text          NOT NULL REFERENCES app.usuario (usuario) ON DELETE CASCADE,
    creada_en       timestamptz   NOT NULL DEFAULT now(),
    pregunta        text          NOT NULL CHECK (length(pregunta) BETWEEN 1 AND 500),
    tipo_respuesta  text          NOT NULL CHECK (tipo_respuesta IN
                        ('respuesta', 'sin_datos', 'fuera_de_alcance', 'aclaracion', 'error')),
    herramientas    jsonb         NOT NULL DEFAULT '[]'::jsonb,  -- [{herramienta, parametros}]
    modelo          text,
    tokens_entrada  integer       NOT NULL DEFAULT 0,
    tokens_salida   integer       NOT NULL DEFAULT 0,
    costo_usd       numeric(10,6) NOT NULL DEFAULT 0,
    duracion_ms     integer,
    advertencias    jsonb         NOT NULL DEFAULT '[]'::jsonb,
    id_solicitud    text                                          -- request-id de Anthropic
);
CREATE INDEX IF NOT EXISTS ix_consulta_asistente_usuario
    ON app.consulta_asistente (usuario, creada_en DESC);
COMMENT ON TABLE app.consulta_asistente IS
    'Registro de preguntas al asistente de IA: consultas hechas, tokens y costo. '
    'No guarda la respuesta ni datos devueltos.';
