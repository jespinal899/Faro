-- =====================================================================
-- Faro · Seguridad · Roles de mínimo privilegio en la base ANALÍTICA (faro_analytics)
-- IDEMPOTENTE. Lo ejecuta el dueño de la base (despliegue), nunca la aplicación.
--
--   faro_etl : lo usa el pipeline. Lee y escribe DATOS en staging y auditoría, pero no
--              puede crear, alterar ni borrar tablas (la estructura solo cambia por el CD).
--
-- Los roles de la API (faro_api) y del asistente de IA (faro_ia) se agregan con sus fases.
-- Contraseñas: database/scripts/configurar_roles.py (nunca en el repositorio).
-- =====================================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'faro_etl') THEN
        CREATE ROLE faro_etl NOLOGIN;
    END IF;
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO faro_etl', current_database());
END;
$$;

GRANT USAGE ON SCHEMA audit, stg_raw, stg_clean, stg_quarantine, stg_ready TO faro_etl;

GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE
    ON ALL TABLES IN SCHEMA audit, stg_raw, stg_clean, stg_quarantine TO faro_etl;
ALTER DEFAULT PRIVILEGES IN SCHEMA audit, stg_raw, stg_clean, stg_quarantine
    GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE ON TABLES TO faro_etl;

-- La zona ready es de solo lectura para el pipeline
GRANT SELECT ON ALL TABLES IN SCHEMA stg_ready TO faro_etl;
ALTER DEFAULT PRIVILEGES IN SCHEMA stg_ready GRANT SELECT ON TABLES TO faro_etl;
