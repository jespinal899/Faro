-- Datos mínimos de la fuente para las pruebas del ETL (se cargan en una base temporal).
-- Un cliente, un producto, un pedido y una factura con dos líneas.
-- Línea 2: utilidad negativa (regla V04, se marca). El nombre del cliente trae espacios de más.

INSERT INTO application.people (person_id, full_name, preferred_name, is_employee, is_salesperson, last_edited_by, last_edited_when)
VALUES (1, 'Ana Vendedora', 'Ana', true, true, 1, '2016-01-01');

INSERT INTO application.countries (country_id, country_name, formal_name, continent, region, subregion, last_edited_by, last_edited_when)
VALUES (1, 'Pais', 'Republica de Pais', 'America', 'Americas', 'Norte', 1, '2016-01-01');
INSERT INTO application.state_provinces (state_province_id, state_province_code, state_province_name, country_id, sales_territory, last_edited_by, last_edited_when)
VALUES (1, 'ES', 'Estado', 1, 'Territorio', 1, '2016-01-01');
INSERT INTO application.cities (city_id, city_name, state_province_id, last_edited_by, last_edited_when)
VALUES (1, 'Ciudad', 1, 1, '2016-01-01');
INSERT INTO application.delivery_methods (delivery_method_id, delivery_method_name, last_edited_by, last_edited_when)
VALUES (1, 'Camion', 1, '2016-01-01');

INSERT INTO warehouse.colors (color_id, color_name, last_edited_by, last_edited_when) VALUES (1, 'Azul', 1, '2016-01-01');
INSERT INTO warehouse.package_types (package_type_id, package_type_name, last_edited_by, last_edited_when) VALUES (1, 'Unidad', 1, '2016-01-01');
INSERT INTO warehouse.stock_groups (stock_group_id, stock_group_name, last_edited_by, last_edited_when) VALUES (1, 'Grupo', 1, '2016-01-01');
INSERT INTO warehouse.stock_items (stock_item_id, stock_item_name, color_id, unit_package_id, outer_package_id, lead_time_days, quantity_per_outer, is_chiller_stock, tax_rate, unit_price, typical_weight_per_unit, last_edited_by, last_edited_when)
VALUES (1, 'Producto', 1, 1, 1, 7, 10, false, 15.000, 5.00, 0.500, 1, '2016-01-01');
INSERT INTO warehouse.stock_item_stock_groups (stock_item_stock_group_id, stock_item_id, stock_group_id, last_edited_by, last_edited_when)
VALUES (1, 1, 1, 1, '2016-01-01');

INSERT INTO sales.buying_groups (buying_group_id, buying_group_name, last_edited_by, last_edited_when) VALUES (1, 'Cadena', 1, '2016-01-01');
INSERT INTO sales.customer_categories (customer_category_id, customer_category_name, last_edited_by, last_edited_when) VALUES (1, 'Tienda', 1, '2016-01-01');
INSERT INTO sales.customers (customer_id, customer_name, bill_to_customer_id, customer_category_id, primary_contact_person_id, delivery_method_id, delivery_city_id, postal_city_id, account_opened_date, standard_discount_percentage, is_statement_sent, is_on_credit_hold, payment_days, delivery_postal_code, last_edited_by, last_edited_when)
VALUES (1, '  Cliente   Uno ', 1, 1, 1, 1, 1, 1, '2015-01-01', 0, false, false, 7, '00000', 1, '2016-01-01');

INSERT INTO sales.orders (order_id, customer_id, salesperson_person_id, contact_person_id, order_date, expected_delivery_date, is_undersupply_backordered, last_edited_by, last_edited_when)
VALUES (1, 1, 1, 1, '2016-01-04', '2016-01-05', true, 1, '2016-01-04');
INSERT INTO sales.order_lines (order_line_id, order_id, stock_item_id, description, package_type_id, quantity, unit_price, tax_rate, picked_quantity, last_edited_by, last_edited_when)
VALUES (1, 1, 1, 'Producto', 1, 10, 5.00, 15.000, 10, 1, '2016-01-04');

INSERT INTO sales.invoices (invoice_id, customer_id, bill_to_customer_id, order_id, delivery_method_id, contact_person_id, accounts_person_id, salesperson_person_id, packed_by_person_id, invoice_date, is_credit_note, total_dry_items, total_chiller_items, last_edited_by, last_edited_when)
VALUES (1, 1, 1, 1, 1, 1, 1, 1, 1, '2016-01-04', false, 1, 0, 1, '2016-01-04');
INSERT INTO sales.invoice_lines (invoice_line_id, invoice_id, stock_item_id, description, package_type_id, quantity, unit_price, tax_rate, tax_amount, line_profit, extended_price, last_edited_by, last_edited_when)
VALUES (1, 1, 1, 'Producto', 1, 10, 5.00, 15.000, 7.50, 20.00, 57.50, 1, '2016-01-04'),
       (2, 1, 1, 'Producto', 1, 2, 100.00, 15.000, 30.00, -5.00, 230.00, 1, '2016-01-04');
