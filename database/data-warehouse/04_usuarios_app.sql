-- =====================================================================
-- Faro · Usuarios del dashboard (esquema app). IDEMPOTENTE.
--
-- Contraseñas: solo su hash Argon2 (nunca en texto plano). Los usuarios se crean con
-- database/scripts/crear_usuario.py. Tras 5 intentos fallidos la cuenta se bloquea
-- 15 minutos (protección contra fuerza bruta; el estado vive en la base porque la API
-- corre en funciones sin memoria compartida).
-- =====================================================================

CREATE SCHEMA IF NOT EXISTS app;
COMMENT ON SCHEMA app IS 'Datos propios de la aplicación web (usuarios del dashboard).';

CREATE TABLE IF NOT EXISTS app.usuario (
    usuario            text        PRIMARY KEY CHECK (usuario ~ '^[a-z0-9._-]{3,40}$'),
    nombre             text        NOT NULL,
    password_hash      text        NOT NULL,
    rol                text        NOT NULL DEFAULT 'analista' CHECK (rol IN ('analista', 'admin')),
    activo             boolean     NOT NULL DEFAULT true,
    intentos_fallidos  integer     NOT NULL DEFAULT 0,
    bloqueado_hasta    timestamptz,
    ultimo_acceso      timestamptz,
    creado_en          timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE app.usuario IS 'Usuarios del dashboard. password_hash = Argon2id.';
