-- =====================================================================
-- Faro · Vistas APROBADAS del pronóstico para la API (esquema api). IDEMPOTENTE.
-- La API solo lee estas vistas: nunca el modelo serializado ni las tablas de ml.
-- =====================================================================

-- Serie semanal real por grupo (contexto del gráfico). Una semana está completa cuando el
-- DW cubre de su lunes a su sábado (WWI no vende los domingos): la primera semana de la
-- historia empieza un martes y la última puede estar a medias.
CREATE OR REPLACE VIEW api.ventas_semanales AS
SELECT s.semana,
       s.grupo,
       s.venta_neta,
       s.venta_neta_simulada,
       s.semana >= (SELECT min(fecha_factura) FROM dw.fact_ventas)
           AND s.semana + 5 <= (SELECT max(fecha_factura) FROM dw.fact_ventas) AS es_completa
FROM ml.ventas_semanales s;
COMMENT ON VIEW api.ventas_semanales IS 'Ventas netas por semana y grupo principal (datos históricos).';

-- Modelo vigente, sin el artefacto
CREATE OR REPLACE VIEW api.modelo_pronostico AS
SELECT modelo_id, nombre, version, algoritmo, parametros, variables, grupos, metricas,
       intervalo, datos_desde, datos_hasta, prueba_desde, filas_entrenamiento, commit_codigo,
       entrenado_en
FROM ml.modelo
WHERE es_vigente;
COMMENT ON VIEW api.modelo_pronostico IS 'Modelo de pronóstico vigente: versión, datos usados y métricas.';

-- Último pronóstico del modelo vigente (el de la fecha de origen más reciente)
CREATE OR REPLACE VIEW api.pronostico AS
SELECT p.modelo_id, m.version, p.origen, p.semana, p.grupo, p.horizonte,
       p.venta_neta_pronosticada, p.inferior, p.superior, p.usa_datos_simulados, p.generado_en
FROM ml.pronostico p
JOIN ml.modelo m ON m.modelo_id = p.modelo_id AND m.es_vigente
WHERE p.origen = (SELECT max(q.origen) FROM ml.pronostico q WHERE q.modelo_id = p.modelo_id);
COMMENT ON VIEW api.pronostico IS 'PREDICCIÓN vigente de ventas netas por semana y grupo (no es dato histórico).';

-- Monitoreo: pronósticos ya vencidos del modelo vigente frente a lo que realmente se vendió
CREATE OR REPLACE VIEW api.pronostico_vs_real AS
SELECT p.modelo_id, m.version, p.origen, p.semana, p.grupo, p.horizonte,
       p.venta_neta_pronosticada, p.inferior, p.superior,
       s.venta_neta                  AS venta_neta_real,
       s.venta_neta_simulada > 0     AS real_incluye_simulados
FROM ml.pronostico p
JOIN ml.modelo m           ON m.modelo_id = p.modelo_id AND m.es_vigente
JOIN api.ventas_semanales s ON s.semana = p.semana AND s.grupo = p.grupo AND s.es_completa;
COMMENT ON VIEW api.pronostico_vs_real IS 'Pronósticos pasados contra las ventas reales de esas semanas.';

-- Evaluación del modelo vigente en el conjunto de prueba
CREATE OR REPLACE VIEW api.prediccion_prueba AS
SELECT pp.semana, pp.grupo, pp.horizonte, pp.origen, pp.real, pp.pronostico, pp.inferior,
       pp.superior, pp.linea_base
FROM ml.prediccion_prueba pp
JOIN ml.modelo m ON m.modelo_id = pp.modelo_id AND m.es_vigente;
COMMENT ON VIEW api.prediccion_prueba IS
    'Predicciones del modelo vigente sobre semanas que no se usaron para entrenarlo.';
