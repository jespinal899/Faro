-- =====================================================================
-- Faro · Vistas de monitoreo para el dashboard (pestaña Operación). IDEMPOTENTE.
-- Fase 7 · decisión D-27 · documentation/arquitectura/alertas.md (sección 8)
--
-- La API (faro_api) no ve el esquema audit ni la cuarentena: solo estas vistas aprobadas,
-- con conteos y estados (sin los registros rechazados). Del error de una ejecución del ETL se
-- muestra solo la primera línea, recortada.
-- El modelo vigente (api.modelo_pronostico) y las alertas (api.alertas*) ya tienen sus vistas.
-- =====================================================================

-- Ejecuciones del ETL: conteos, reconciliación, duración y error
CREATE OR REPLACE VIEW api.monitoreo_etl AS
SELECT execution_id                                         AS ejecucion_id,
       pipeline_name                                        AS proceso,
       trigger                                              AS disparador,
       mode                                                 AS modo,
       start_time                                           AS inicio,
       end_time                                             AS fin,
       round(extract(epoch FROM end_time - start_time)::numeric, 1) AS segundos,
       status                                               AS estado,
       rows_read                                            AS leidas,
       rows_inserted                                        AS nuevas,
       rows_updated                                         AS actualizadas,
       rows_rejected                                        AS rechazadas,
       rows_unchanged                                       AS sin_cambios,
       reconciled                                           AS reconciliado,
       left(split_part(error_detail, E'\n', 1), 300)        AS error
FROM audit.etl_execution;
COMMENT ON VIEW api.monitoreo_etl IS 'Ejecuciones del ETL para el monitoreo (sin el detalle interno del error).';

-- Reglas de calidad en la última ejecución que las evaluó, con su dimensión
CREATE OR REPLACE VIEW api.monitoreo_calidad AS
SELECT r.execution_id  AS ejecucion_id,
       r.source_table  AS tabla,
       r.rule_code     AS regla,
       d.dimension,
       d.description   AS descripcion,
       r.action        AS accion,
       r.rows_checked  AS evaluadas,
       r.rows_failed   AS fallaron
FROM audit.dq_result r
LEFT JOIN audit.dq_rule d USING (source_table, rule_code)
WHERE r.execution_id = (SELECT max(execution_id) FROM audit.dq_result);
COMMENT ON VIEW api.monitoreo_calidad IS 'Resultado de cada regla de calidad en la última ejecución evaluada.';

-- Cuarentena: cuántos registros rechazados siguen pendientes, por tabla y regla
CREATE OR REPLACE VIEW api.monitoreo_cuarentena AS
SELECT source_table                                    AS tabla,
       rule_code                                       AS regla,
       count(*) FILTER (WHERE resolved_at IS NULL)     AS pendientes,
       count(*) FILTER (WHERE resolved_at IS NOT NULL) AS resueltos,
       max(rejected_at)                                AS ultimo_rechazo
FROM stg_quarantine.registro_rechazado
GROUP BY source_table, rule_code;
COMMENT ON VIEW api.monitoreo_cuarentena IS 'Registros en cuarentena por tabla y regla (solo conteos).';
