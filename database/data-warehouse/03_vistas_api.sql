-- =====================================================================
-- Faro · Vistas APROBADAS para la API (esquema api). IDEMPOTENTE.
--
-- La API y el dashboard solo leen estas vistas, nunca las tablas del DW: así el rol
-- faro_api no necesita permisos sobre dw, staging ni auditoría, y lo que se expone
-- está definido y versionado aquí (la guía pide "vistas aprobadas").
-- Las vistas se ejecutan con los permisos de su dueño.
-- =====================================================================

CREATE SCHEMA IF NOT EXISTS api;
COMMENT ON SCHEMA api IS 'Vistas aprobadas que consume la API del dashboard (solo lectura).';

-- Ventas al grano de la línea de factura, con los atributos de sus dimensiones
CREATE OR REPLACE VIEW api.ventas AS
SELECT f.linea_factura_id,
       f.factura_id,
       f.pedido_id,
       f.fecha_factura          AS fecha,
       d.anio,
       d.trimestre,
       d.mes,
       d.nombre_mes,
       d.anio_mes,
       d.semana_iso,
       d.dia_semana,
       d.es_dia_habil,
       f.cliente_id,
       c.nombre                 AS cliente,
       c.categoria              AS categoria_cliente,
       c.grupo_compra,
       f.cliente_facturacion_id,
       f.producto_id,
       p.nombre                 AS producto,
       p.grupo_principal,
       p.marca,
       f.vendedor_id,
       e.nombre_completo        AS vendedor,
       g.ciudad,
       g.estado,
       g.territorio_venta       AS territorio,
       g.latitud,
       g.longitud,
       f.cantidad,
       f.venta_bruta,
       f.impuesto,
       f.venta_neta,
       f.costo,
       f.utilidad,
       f.precio_unitario,
       f.es_venta_bajo_costo,
       f.es_atipico,
       f.es_simulado
FROM dw.fact_ventas f
JOIN dw.dim_fecha d     ON d.fecha_key = f.fecha_factura_key
JOIN dw.dim_cliente c   ON c.cliente_key = f.cliente_key
JOIN dw.dim_producto p  ON p.producto_key = f.producto_key
JOIN dw.dim_empleado e  ON e.empleado_key = f.vendedor_key
JOIN dw.dim_geografia g ON g.geografia_key = f.geografia_key;
COMMENT ON VIEW api.ventas IS
    'Una fila por línea de factura con sus dimensiones. Margen y ticket se calculan al agregar.';

-- Pertenencia producto-grupo con su factor de ponderación (para no duplicar importes)
CREATE OR REPLACE VIEW api.producto_grupo AS
SELECT b.producto_id, g.nombre AS grupo, b.factor_ponderacion, b.es_principal
FROM dw.puente_producto_grupo b
JOIN dw.dim_grupo_producto g ON g.grupo_key = b.grupo_key;

-- Estado de los datos: fecha y hora de la última actualización (la guía lo exige en el dashboard)
CREATE OR REPLACE VIEW api.estado_datos AS
SELECT (SELECT max(end_time) FROM audit.etl_execution WHERE status = 'exitoso')
           AS ultima_carga_exitosa,
       (SELECT status FROM audit.etl_execution ORDER BY execution_id DESC LIMIT 1)
           AS estado_ultima_ejecucion,
       (SELECT min(fecha_factura) FROM dw.fact_ventas)                     AS fecha_desde,
       (SELECT max(fecha_factura) FROM dw.fact_ventas)                     AS fecha_hasta,
       (SELECT max(fecha_factura) FROM dw.fact_ventas WHERE NOT es_simulado) AS ultima_fecha_real,
       (SELECT count(*) FROM dw.fact_ventas)                               AS lineas,
       (SELECT count(*) FROM dw.fact_ventas WHERE es_simulado)             AS lineas_simuladas;
COMMENT ON VIEW api.estado_datos IS 'Frescura de los datos para mostrar en el dashboard.';
