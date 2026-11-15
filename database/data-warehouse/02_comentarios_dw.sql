-- =====================================================================
-- Faro · Data Warehouse · Descripción de columnas (base del diccionario de datos)
-- IDEMPOTENTE. Requiere 01_esquema_dw.sql.
-- El diccionario se genera con: uv run python database/scripts/documentar_dw.py
-- =====================================================================

-- ---------------------------- fact_ventas ----------------------------
COMMENT ON COLUMN dw.fact_ventas.venta_key IS 'Clave sustituta del hecho.';
COMMENT ON COLUMN dw.fact_ventas.fecha_factura_key IS 'Fecha de la factura (rol de dim_fecha). Fecha principal del análisis.';
COMMENT ON COLUMN dw.fact_ventas.fecha_pedido_key IS 'Fecha del pedido que originó la venta (segundo rol de dim_fecha).';
COMMENT ON COLUMN dw.fact_ventas.cliente_key IS 'Cliente que compra, en la versión vigente a la fecha de la factura (SCD2).';
COMMENT ON COLUMN dw.fact_ventas.cliente_facturacion_key IS 'Cliente que paga (rol de dim_cliente), en su versión vigente a la fecha de la factura.';
COMMENT ON COLUMN dw.fact_ventas.producto_key IS 'Producto en la versión vigente a la fecha de la factura (precio y grupo de ese momento).';
COMMENT ON COLUMN dw.fact_ventas.vendedor_key IS 'Vendedor (rol de dim_empleado). -1 = desconocido, se reasigna al llegar la dimensión.';
COMMENT ON COLUMN dw.fact_ventas.geografia_key IS 'Ciudad de entrega del cliente al momento de cargar la venta.';
COMMENT ON COLUMN dw.fact_ventas.linea_factura_id IS 'Clave natural de la línea de factura. Único: garantiza el grano del hecho.';
COMMENT ON COLUMN dw.fact_ventas.factura_id IS 'Dimensión degenerada: número de factura (para contar facturas y navegar al detalle).';
COMMENT ON COLUMN dw.fact_ventas.pedido_id IS 'Dimensión degenerada: número de pedido.';
COMMENT ON COLUMN dw.fact_ventas.fecha_factura IS 'Fecha de la factura (también como fecha, para buscar la versión SCD2 vigente).';
COMMENT ON COLUMN dw.fact_ventas.cantidad IS 'Unidades vendidas. Aditiva.';
COMMENT ON COLUMN dw.fact_ventas.venta_bruta IS 'Importe de la línea CON impuestos (extended_price). Aditiva.';
COMMENT ON COLUMN dw.fact_ventas.impuesto IS 'Impuesto de la línea. Aditiva.';
COMMENT ON COLUMN dw.fact_ventas.venta_neta IS 'venta_bruta - impuesto. Base de los KPI de venta. Aditiva.';
COMMENT ON COLUMN dw.fact_ventas.costo IS 'venta_neta - utilidad. Aditiva.';
COMMENT ON COLUMN dw.fact_ventas.utilidad IS 'Margen de la línea sin impuestos; negativa = venta bajo costo. Aditiva.';
COMMENT ON COLUMN dw.fact_ventas.precio_unitario IS 'Precio unitario sin impuestos. NO aditiva: promediar ponderando por cantidad.';
COMMENT ON COLUMN dw.fact_ventas.tasa_impuesto IS 'Tasa de impuesto en porcentaje. NO aditiva.';
COMMENT ON COLUMN dw.fact_ventas.es_venta_bajo_costo IS 'TRUE si utilidad < 0 (regla de calidad V04: problema de precios, no de datos).';
COMMENT ON COLUMN dw.fact_ventas.es_atipico IS 'TRUE si la cantidad o el importe superan Q3 + 3·IQR (reglas A01/A02).';
COMMENT ON COLUMN dw.fact_ventas.es_simulado IS 'TRUE si la venta la generó el simulador (datos de demostración, no históricos).';
COMMENT ON COLUMN dw.fact_ventas.batch_id IS 'Ejecución del ETL que cargó o actualizó la fila (linaje, ver audit.etl_execution).';
COMMENT ON COLUMN dw.fact_ventas.cargado_en IS 'Momento en que la fila se cargó o actualizó por última vez.';

-- ---------------------------- dim_cliente ----------------------------
COMMENT ON COLUMN dw.dim_cliente.cliente_key IS 'Clave sustituta: una por VERSIÓN del cliente. -1 = desconocido.';
COMMENT ON COLUMN dw.dim_cliente.cliente_id IS 'Clave natural (sales.customers.customer_id).';
COMMENT ON COLUMN dw.dim_cliente.categoria_id IS 'SCD2: un cambio de categoría crea una versión nueva.';
COMMENT ON COLUMN dw.dim_cliente.grupo_compra_id IS 'SCD2: grupo de compra (cadena). NULL = cliente independiente.';
COMMENT ON COLUMN dw.dim_cliente.cliente_facturacion_id IS 'SCD2: cliente al que se le factura (la casa matriz o el propio cliente).';
COMMENT ON COLUMN dw.dim_cliente.categoria IS 'Nombre de la categoría (se refresca según categoria_id; renombrar no versiona).';
COMMENT ON COLUMN dw.dim_cliente.grupo_compra IS 'Nombre del grupo de compra, o ''Independiente''.';
COMMENT ON COLUMN dw.dim_cliente.es_casa_matriz IS 'TRUE si otros clientes se facturan a este.';
COMMENT ON COLUMN dw.dim_cliente.politica_credito IS '''Límite propio'' o ''Gestionado por casa matriz'' (explica el NULL de limite_credito).';
COMMENT ON COLUMN dw.dim_cliente.limite_credito IS 'Límite de crédito. NULL = no aplica (lo gestiona la casa matriz); no es cero.';
COMMENT ON COLUMN dw.dim_cliente.valido_desde IS 'Inicio de vigencia de la versión (la primera versión rige desde 1900-01-01).';
COMMENT ON COLUMN dw.dim_cliente.valido_hasta IS 'Fin de vigencia de la versión (9999-12-31 = vigente).';
COMMENT ON COLUMN dw.dim_cliente.es_actual IS 'TRUE en la versión vigente (exactamente una por cliente).';
COMMENT ON COLUMN dw.dim_cliente.version IS 'Número de versión del cliente (1, 2, ...).';
COMMENT ON COLUMN dw.dim_cliente.hash_tipo2 IS 'Huella de los atributos SCD2: solo se versiona si cambia.';

-- ---------------------------- dim_producto ---------------------------
COMMENT ON COLUMN dw.dim_producto.producto_key IS 'Clave sustituta: una por VERSIÓN del producto. -1 = desconocido.';
COMMENT ON COLUMN dw.dim_producto.producto_id IS 'Clave natural (warehouse.stock_items.stock_item_id).';
COMMENT ON COLUMN dw.dim_producto.marca IS 'Marca, o ''Sin marca'' (el 92 % no tiene marca en la fuente).';
COMMENT ON COLUMN dw.dim_producto.color IS 'Color, o ''Sin color'' (no aplica).';
COMMENT ON COLUMN dw.dim_producto.precio_lista IS 'SCD2: precio de lista sin impuestos vigente en la versión.';
COMMENT ON COLUMN dw.dim_producto.tasa_impuesto IS 'SCD2: tasa de impuesto vigente en la versión.';
COMMENT ON COLUMN dw.dim_producto.grupo_principal_id IS 'SCD2: grupo más específico del producto (prioridad fija, decisión D-16).';
COMMENT ON COLUMN dw.dim_producto.grupo_principal IS 'Nombre del grupo principal. Analizar por este atributo NO duplica importes.';
COMMENT ON COLUMN dw.dim_producto.cantidad_grupos IS 'En cuántos grupos está el producto (para analizar por pertenencia, usar el puente).';
COMMENT ON COLUMN dw.dim_producto.valido_desde IS 'Inicio de vigencia de la versión.';
COMMENT ON COLUMN dw.dim_producto.valido_hasta IS 'Fin de vigencia de la versión (9999-12-31 = vigente).';
COMMENT ON COLUMN dw.dim_producto.es_actual IS 'TRUE en la versión vigente.';

-- ----------------------- otras dimensiones y puente -----------------------
COMMENT ON COLUMN dw.dim_fecha.fecha_key IS 'Clave AAAAMMDD (p. ej. 20160531). -1 = desconocida.';
COMMENT ON COLUMN dw.dim_fecha.es_dia_habil IS 'Lunes a sábado. En WWI no se vende los domingos.';
COMMENT ON COLUMN dw.dim_fecha.dia_semana IS '1 = lunes ... 7 = domingo (ISO).';
COMMENT ON COLUMN dw.dim_empleado.es_vendedor IS 'TRUE si la persona vende (rol vendedor en el hecho).';
COMMENT ON COLUMN dw.dim_geografia.territorio_venta IS 'Territorio comercial (9 en WWI): agrupa estados.';
COMMENT ON COLUMN dw.dim_geografia.latitud IS 'Latitud de la ciudad (para mapas).';
COMMENT ON COLUMN dw.dim_grupo_producto.prioridad IS '1 = grupo más específico. Define el grupo principal de cada producto.';
COMMENT ON COLUMN dw.puente_producto_grupo.factor_ponderacion IS '1 / grupos del producto. SUM(medida * factor) reparte la venta sin duplicarla.';
COMMENT ON COLUMN dw.puente_producto_grupo.es_principal IS 'TRUE en el grupo principal del producto.';
