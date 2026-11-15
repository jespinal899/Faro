-- =====================================================================
-- Faro · Staging · Zona READY (integración para el Data Warehouse)
-- IDEMPOTENTE. Requiere 01 y 02.
--
-- Son VISTAS sobre stg_clean: integran las entidades, resuelven los nulos según su
-- causa y calculan los atributos derivados, sin duplicar datos. Conservan las claves
-- de negocio y el lote (linaje). Todos los joins son muchos-a-uno: no multiplican filas.
-- Diseño: documentation/modelos/modelo-dimensional.md
-- =====================================================================

-- ---------------------------------------------------------------------
-- Prioridad FIJA de los grupos de producto (1 = más específico).
-- Decide el grupo principal de cada producto (decisión D-16). Es una tabla de
-- referencia versionada: no cambia sola al agregar productos. Un grupo nuevo que
-- no esté aquí queda al final (prioridad 999) hasta que se le asigne una.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stg_ready.ref_prioridad_grupo (
    stock_group_id  integer PRIMARY KEY,
    prioridad       integer NOT NULL
);
INSERT INTO stg_ready.ref_prioridad_grupo (stock_group_id, prioridad) VALUES
    (7, 1),   -- USB Novelties
    (9, 2),   -- Toys
    (8, 3),   -- Furry Footwear
    (4, 4),   -- T-Shirts
    (3, 5),   -- Mugs
    (10, 6),  -- Packaging Materials
    (2, 7),   -- Clothing
    (6, 8),   -- Computing Novelties
    (1, 9),   -- Novelty Items
    (5, 10)   -- Airline Novelties
ON CONFLICT (stock_group_id) DO NOTHING;

-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW stg_ready.grupos_producto AS
SELECT g.stock_group_id            AS grupo_id,
       g.stock_group_name          AS nombre,
       COALESCE(p.prioridad, 999)  AS prioridad
FROM stg_clean.warehouse_stock_groups g
LEFT JOIN stg_ready.ref_prioridad_grupo p USING (stock_group_id);

-- Puente producto-grupo: factor de ponderación 1/n y marca del grupo principal
CREATE OR REPLACE VIEW stg_ready.producto_grupo AS
SELECT sg.stock_item_id   AS producto_id,
       sg.stock_group_id  AS grupo_id,
       1.0 / count(*) OVER (PARTITION BY sg.stock_item_id) AS factor_ponderacion,  -- sin redondear
       row_number() OVER (PARTITION BY sg.stock_item_id
                          ORDER BY g.prioridad, sg.stock_group_id) = 1 AS es_principal
FROM stg_clean.warehouse_stock_item_stock_groups sg
JOIN stg_ready.grupos_producto g ON g.grupo_id = sg.stock_group_id;

-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW stg_ready.productos AS
SELECT s.stock_item_id                      AS producto_id,
       s.stock_item_name                    AS nombre,
       COALESCE(s.brand, 'Sin marca')       AS marca,           -- nulo = desconocido
       COALESCE(c.color_name, 'Sin color')  AS color,           -- nulo = no aplica
       s.size                               AS talla,
       pu.package_type_name                 AS empaque_unidad,
       pe.package_type_name                 AS empaque_exterior,
       s.quantity_per_outer                 AS cantidad_por_empaque,
       s.is_chiller_stock                   AS requiere_frio,
       s.lead_time_days                     AS dias_reposicion,
       s.typical_weight_per_unit            AS peso_unitario,
       s.unit_price                         AS precio_lista,
       s.recommended_retail_price           AS precio_venta_sugerido,
       s.tax_rate                           AS tasa_impuesto,
       COALESCE(gp.nombre, 'Sin grupo')     AS grupo_principal,
       COALESCE(n.cantidad_grupos, 0)       AS cantidad_grupos,
       s.last_edited_when                   AS modificado_en,
       s._batch_id                          AS batch_id,
       -- Identificador del grupo principal: la historia (SCD2) sigue al ID, no al nombre.
       -- (Las columnas nuevas van al final: CREATE OR REPLACE VIEW no permite intercalarlas.)
       pg.grupo_id                          AS grupo_principal_id
FROM stg_clean.warehouse_stock_items s
LEFT JOIN stg_clean.warehouse_colors c ON c.color_id = s.color_id
LEFT JOIN stg_clean.warehouse_package_types pu ON pu.package_type_id = s.unit_package_id
LEFT JOIN stg_clean.warehouse_package_types pe ON pe.package_type_id = s.outer_package_id
LEFT JOIN stg_ready.producto_grupo pg ON pg.producto_id = s.stock_item_id AND pg.es_principal
LEFT JOIN stg_ready.grupos_producto gp ON gp.grupo_id = pg.grupo_id
LEFT JOIN (SELECT stock_item_id, count(*) AS cantidad_grupos
           FROM stg_clean.warehouse_stock_item_stock_groups GROUP BY 1) n
       ON n.stock_item_id = s.stock_item_id;

-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW stg_ready.clientes AS
SELECT c.customer_id                                   AS cliente_id,
       c.customer_name                                 AS nombre,
       cat.customer_category_name                      AS categoria,
       COALESCE(bg.buying_group_name, 'Independiente') AS grupo_compra,   -- nulo = no aplica
       c.bill_to_customer_id                           AS cliente_facturacion_id,
       fact.customer_name                              AS cliente_facturacion,
       EXISTS (SELECT 1 FROM stg_clean.sales_customers h
               WHERE h.bill_to_customer_id = c.customer_id
                 AND h.customer_id <> c.customer_id)   AS es_casa_matriz,
       CASE WHEN c.credit_limit IS NULL THEN 'Gestionado por casa matriz'
            ELSE 'Límite propio' END                   AS politica_credito,
       c.credit_limit                                  AS limite_credito, -- nulo = no aplica
       c.payment_days                                  AS dias_pago,
       c.is_on_credit_hold                             AS en_suspension_credito,
       c.standard_discount_percentage                  AS descuento_estandar,
       c.account_opened_date                           AS fecha_apertura,
       c.delivery_city_id                              AS ciudad_id,
       c.last_edited_when                              AS modificado_en,
       c._batch_id                                     AS batch_id,
       -- Identificadores de la segmentación: la historia (SCD2) sigue a los IDs, no a los
       -- nombres (renombrar una categoría no es un cambio del cliente).
       c.customer_category_id                          AS categoria_id,
       c.buying_group_id                               AS grupo_compra_id   -- nulo = independiente
FROM stg_clean.sales_customers c
LEFT JOIN stg_clean.sales_customer_categories cat USING (customer_category_id)
LEFT JOIN stg_clean.sales_buying_groups bg ON bg.buying_group_id = c.buying_group_id
LEFT JOIN stg_clean.sales_customers fact ON fact.customer_id = c.bill_to_customer_id;

-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW stg_ready.geografia AS
SELECT ci.city_id               AS ciudad_id,
       ci.city_name             AS ciudad,
       sp.state_province_name   AS estado,
       sp.state_province_code   AS codigo_estado,
       sp.sales_territory       AS territorio_venta,
       co.country_name          AS pais,
       ci.latitude              AS latitud,
       ci.longitude             AS longitud,
       ci._batch_id             AS batch_id
FROM stg_clean.application_cities ci
LEFT JOIN stg_clean.application_state_provinces sp USING (state_province_id)
LEFT JOIN stg_clean.application_countries co ON co.country_id = sp.country_id;

-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW stg_ready.empleados AS
SELECT p.person_id        AS persona_id,
       p.full_name        AS nombre_completo,
       p.preferred_name   AS nombre_preferido,
       p.is_salesperson   AS es_vendedor,
       p._batch_id        AS batch_id
FROM stg_clean.application_people p
WHERE p.is_employee;

-- ---------------------------------------------------------------------
-- Ventas al grano de la LÍNEA DE FACTURA, con sus medidas derivadas
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW stg_ready.ventas AS
SELECT il.invoice_line_id                              AS linea_factura_id,
       i.invoice_id                                    AS factura_id,
       i.order_id                                      AS pedido_id,
       i.invoice_date                                  AS fecha_factura,
       o.order_date                                    AS fecha_pedido,
       i.customer_id                                   AS cliente_id,
       i.bill_to_customer_id                           AS cliente_facturacion_id,
       il.stock_item_id                                AS producto_id,
       i.salesperson_person_id                         AS vendedor_id,
       c.delivery_city_id                              AS ciudad_id,
       il.quantity                                     AS cantidad,
       il.unit_price                                   AS precio_unitario,
       il.tax_rate                                     AS tasa_impuesto,
       il.extended_price                               AS venta_bruta,     -- incluye impuestos
       il.tax_amount                                   AS impuesto,
       il.extended_price - il.tax_amount               AS venta_neta,
       il.extended_price - il.tax_amount - il.line_profit AS costo,
       il.line_profit                                  AS utilidad,
       'V04' = ANY (il._dq_flags)                      AS es_venta_bajo_costo,
       il._dq_flags && ARRAY['A01', 'A02']             AS es_atipico,
       COALESCE(il.last_edited_by = sim.person_id, false) AS es_simulado,
       GREATEST(il.last_edited_when, i.last_edited_when) AS modificado_en,
       il._batch_id                                    AS batch_id
FROM stg_clean.sales_invoice_lines il
JOIN stg_clean.sales_invoices i ON i.invoice_id = il.invoice_id
LEFT JOIN stg_clean.sales_orders o ON o.order_id = i.order_id
LEFT JOIN stg_clean.sales_customers c ON c.customer_id = i.customer_id
LEFT JOIN (SELECT min(person_id) AS person_id FROM stg_clean.application_people
           WHERE full_name = 'Simulador de ventas') sim ON true;

COMMENT ON VIEW stg_ready.ventas IS
    'Una fila por línea de factura, lista para fact_ventas. venta_neta = venta_bruta - impuesto.';
COMMENT ON VIEW stg_ready.producto_grupo IS
    'Puente producto-grupo. Sumar venta x factor_ponderacion reparte la venta sin duplicarla.';
