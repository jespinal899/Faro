-- =====================================================================
-- Faro · Seguridad · Roles de mínimo privilegio en la FUENTE (wwi_oltp)
-- IDEMPOTENTE. Lo ejecuta el dueño de la base (despliegue), nunca la aplicación.
--
--   etl_lector : lo usa el ETL. SOLO puede leer. No puede modificar la fuente.
--   wwi_app    : representa al sistema de ventas (el simulador). Lee los catálogos y
--                SOLO puede insertar pedidos y facturas. No modifica ni borra nada.
--
-- Los roles se crean sin acceso (NOLOGIN) y sin contraseña: las contraseñas se asignan
-- aparte con database/scripts/configurar_roles.py y nunca se guardan en el repositorio.
-- =====================================================================

DO $$
DECLARE
    rol text;
BEGIN
    FOREACH rol IN ARRAY ARRAY['etl_lector', 'wwi_app'] LOOP
        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = rol) THEN
            EXECUTE format('CREATE ROLE %I NOLOGIN', rol);
        END IF;
        EXECUTE format('GRANT CONNECT ON DATABASE %I TO %I', current_database(), rol);
    END LOOP;
END;
$$;

GRANT USAGE ON SCHEMA application, warehouse, sales TO etl_lector, wwi_app;
GRANT SELECT ON ALL TABLES IN SCHEMA application, warehouse, sales TO etl_lector, wwi_app;
-- Las tablas que se creen después heredan el permiso de lectura
ALTER DEFAULT PRIVILEGES IN SCHEMA application, warehouse, sales
    GRANT SELECT ON TABLES TO etl_lector, wwi_app;

-- El sistema de ventas solo registra operaciones nuevas
GRANT INSERT ON sales.orders, sales.order_lines, sales.invoices, sales.invoice_lines TO wwi_app;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA sales TO wwi_app;
