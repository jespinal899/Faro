-- =====================================================================
-- Faro · Seguridad · Roles de mínimo privilegio en la base ANALÍTICA (faro_analytics)
-- IDEMPOTENTE. Lo ejecuta el dueño de la base (despliegue), nunca la aplicación.
--
--   faro_etl : lo usa el pipeline. Lee y escribe DATOS en staging, auditoría y DW, pero no
--              puede crear, alterar ni borrar tablas (la estructura solo cambia por el CD).
--
--   faro_api : la API del dashboard (solo vistas aprobadas del esquema api).
--   faro_ml  : el pronóstico (lee la serie de ml y escribe modelos y predicciones).
--   faro_alertas : el evaluador de alertas (lee vistas de entrada, registra alertas y envíos).
--
-- El rol del asistente de IA (faro_ia) se agrega con su fase.
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

-- El pipeline carga el Data Warehouse: datos sí, estructura no
GRANT USAGE ON SCHEMA dw TO faro_etl;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA dw TO faro_etl;
ALTER DEFAULT PRIVILEGES IN SCHEMA dw GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO faro_etl;

-- ---------------------------------------------------------------------
-- faro_api : lo usa la API del dashboard. SOLO lee las vistas aprobadas del esquema api
--            (no ve dw, staging ni auditoría) y maneja el inicio de sesión de app.usuario.
-- ---------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'faro_api') THEN
        CREATE ROLE faro_api NOLOGIN;
    END IF;
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO faro_api', current_database());
END;
$$;

GRANT USAGE ON SCHEMA api, app TO faro_api;
GRANT SELECT ON ALL TABLES IN SCHEMA api TO faro_api;
ALTER DEFAULT PRIVILEGES IN SCHEMA api GRANT SELECT ON TABLES TO faro_api;
GRANT SELECT ON app.usuario TO faro_api;
-- Solo puede actualizar el control de intentos y el último acceso (no contraseñas ni roles)
GRANT UPDATE (intentos_fallidos, bloqueado_hasta, ultimo_acceso) ON app.usuario TO faro_api;
-- Asistente de IA: registra cada pregunta y cuenta las recientes (límite por usuario). No
-- puede modificar ni borrar el registro. El asistente consulta los datos con las mismas
-- vistas aprobadas y de solo lectura: el modelo nunca ejecuta SQL (decisión D-25).
GRANT SELECT, INSERT ON app.consulta_asistente TO faro_api;

-- ---------------------------------------------------------------------
-- faro_ml : entrena el modelo y genera los pronósticos (workflow "ML - Pronóstico").
--           Lee SOLO la serie de entrada (vista ml.ventas_semanales, no el DW) y escribe el
--           registro de modelos, la evaluación y las predicciones. No puede borrar pronósticos.
-- ---------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'faro_ml') THEN
        CREATE ROLE faro_ml NOLOGIN;
    END IF;
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO faro_ml', current_database());
END;
$$;

GRANT USAGE ON SCHEMA ml TO faro_ml;
GRANT SELECT ON ml.ventas_semanales TO faro_ml;
GRANT SELECT, INSERT ON ml.modelo, ml.prediccion_prueba, ml.pronostico TO faro_ml;
-- Marcar cuál versión es la vigente, y regenerar el pronóstico de un mismo origen
GRANT UPDATE (es_vigente) ON ml.modelo TO faro_ml;
GRANT UPDATE (venta_neta_pronosticada, inferior, superior, usa_datos_simulados, generado_en)
    ON ml.pronostico TO faro_ml;

-- ---------------------------------------------------------------------
-- faro_alertas : evaluador de alertas (módulo notifications/, workflow del ETL). Lee SOLO
--                las vistas de entrada del esquema alerta y el pronóstico aprobado; registra
--                alertas, evaluaciones y envíos. No ve el DW ni puede borrar alertas.
-- ---------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'faro_alertas') THEN
        CREATE ROLE faro_alertas NOLOGIN;
    END IF;
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO faro_alertas', current_database());
END;
$$;

GRANT USAGE ON SCHEMA alerta, api TO faro_alertas;
GRANT SELECT ON alerta.rango_datos, alerta.ventas_semanales_total, alerta.bajo_costo_semanal,
                alerta.regla, api.pronostico, api.modelo_pronostico, api.ventas_semanales
    TO faro_alertas;
GRANT SELECT, INSERT ON alerta.alerta, alerta.envio, alerta.evaluacion TO faro_alertas;
GRANT UPDATE (fin, estado, reglas_evaluadas, alertas_nuevas, correos_enviados, error)
    ON alerta.evaluacion TO faro_alertas;
GRANT UPDATE (explicacion_ia, accion_recomendada_ia, ia_modelo) ON alerta.alerta TO faro_alertas;

-- La API solo cambia el estado de una alerta (atendida, descartada, resuelta) y su nota
GRANT USAGE ON SCHEMA alerta TO faro_api;
GRANT SELECT (alerta_id, estado) ON alerta.alerta TO faro_api;
GRANT UPDATE (estado, estado_actualizado_en, estado_actualizado_por, nota)
    ON alerta.alerta TO faro_api;
