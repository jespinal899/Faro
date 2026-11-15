-- =====================================================================
-- Faro · Staging · Tablas stg_raw y stg_clean (espejo de la fuente)
-- GENERADO por database/scripts/generar_ddl_staging.py. No editar a mano.
-- IDEMPOTENTE. Requiere 01_esquemas_auditoria.sql.
--
-- stg_raw  : copia fiel; solo se agregan filas. _raw_id ordena las versiones.
-- stg_clean: una fila por clave natural (versión vigente), limpia y validada.
--   _row_hash : huella del registro original, para detectar cambios reales.
--   _dq_flags : reglas de calidad de tipo 'marcar' que el registro incumple.
-- =====================================================================

-- ---------- application.people ----------
CREATE TABLE IF NOT EXISTS stg_raw.application_people (
    _raw_id                          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    person_id                        integer,
    full_name                        character varying(50),
    preferred_name                   character varying(50),
    is_employee                      boolean,
    is_salesperson                   boolean,
    last_edited_by                   integer,
    last_edited_when                 timestamp with time zone,
    _batch_id                        bigint NOT NULL,
    _extracted_at                    timestamp with time zone NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_raw_application_people_batch ON stg_raw.application_people (_batch_id);
CREATE INDEX IF NOT EXISTS ix_raw_application_people_pk ON stg_raw.application_people (person_id);

CREATE TABLE IF NOT EXISTS stg_clean.application_people (
    person_id                        integer PRIMARY KEY,
    full_name                        character varying(50),
    preferred_name                   character varying(50),
    is_employee                      boolean,
    is_salesperson                   boolean,
    last_edited_by                   integer,
    last_edited_when                 timestamp with time zone,
    _batch_id                        bigint NOT NULL,
    _extracted_at                    timestamp with time zone NOT NULL,
    _row_hash                        text NOT NULL,
    _dq_flags                        text[] NOT NULL DEFAULT '{}'
);

-- ---------- application.countries ----------
CREATE TABLE IF NOT EXISTS stg_raw.application_countries (
    _raw_id                          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    country_id                       integer,
    country_name                     character varying(60),
    formal_name                      character varying(60),
    iso_alpha3_code                  character varying(3),
    iso_numeric_code                 integer,
    country_type                     character varying(20),
    latest_recorded_population       bigint,
    continent                        character varying(30),
    region                           character varying(30),
    subregion                        character varying(30),
    last_edited_by                   integer,
    last_edited_when                 timestamp with time zone,
    _batch_id                        bigint NOT NULL,
    _extracted_at                    timestamp with time zone NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_raw_application_countries_batch ON stg_raw.application_countries (_batch_id);
CREATE INDEX IF NOT EXISTS ix_raw_application_countries_pk ON stg_raw.application_countries (country_id);

CREATE TABLE IF NOT EXISTS stg_clean.application_countries (
    country_id                       integer PRIMARY KEY,
    country_name                     character varying(60),
    formal_name                      character varying(60),
    iso_alpha3_code                  character varying(3),
    iso_numeric_code                 integer,
    country_type                     character varying(20),
    latest_recorded_population       bigint,
    continent                        character varying(30),
    region                           character varying(30),
    subregion                        character varying(30),
    last_edited_by                   integer,
    last_edited_when                 timestamp with time zone,
    _batch_id                        bigint NOT NULL,
    _extracted_at                    timestamp with time zone NOT NULL,
    _row_hash                        text NOT NULL,
    _dq_flags                        text[] NOT NULL DEFAULT '{}'
);

-- ---------- application.state_provinces ----------
CREATE TABLE IF NOT EXISTS stg_raw.application_state_provinces (
    _raw_id                          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    state_province_id                integer,
    state_province_code              character varying(5),
    state_province_name              character varying(50),
    country_id                       integer,
    sales_territory                  character varying(50),
    latest_recorded_population       bigint,
    last_edited_by                   integer,
    last_edited_when                 timestamp with time zone,
    _batch_id                        bigint NOT NULL,
    _extracted_at                    timestamp with time zone NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_raw_application_state_provinces_batch ON stg_raw.application_state_provinces (_batch_id);
CREATE INDEX IF NOT EXISTS ix_raw_application_state_provinces_pk ON stg_raw.application_state_provinces (state_province_id);

CREATE TABLE IF NOT EXISTS stg_clean.application_state_provinces (
    state_province_id                integer PRIMARY KEY,
    state_province_code              character varying(5),
    state_province_name              character varying(50),
    country_id                       integer,
    sales_territory                  character varying(50),
    latest_recorded_population       bigint,
    last_edited_by                   integer,
    last_edited_when                 timestamp with time zone,
    _batch_id                        bigint NOT NULL,
    _extracted_at                    timestamp with time zone NOT NULL,
    _row_hash                        text NOT NULL,
    _dq_flags                        text[] NOT NULL DEFAULT '{}'
);

-- ---------- application.cities ----------
CREATE TABLE IF NOT EXISTS stg_raw.application_cities (
    _raw_id                          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    city_id                          integer,
    city_name                        character varying(50),
    state_province_id                integer,
    latitude                         double precision,
    longitude                        double precision,
    latest_recorded_population       bigint,
    last_edited_by                   integer,
    last_edited_when                 timestamp with time zone,
    _batch_id                        bigint NOT NULL,
    _extracted_at                    timestamp with time zone NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_raw_application_cities_batch ON stg_raw.application_cities (_batch_id);
CREATE INDEX IF NOT EXISTS ix_raw_application_cities_pk ON stg_raw.application_cities (city_id);

CREATE TABLE IF NOT EXISTS stg_clean.application_cities (
    city_id                          integer PRIMARY KEY,
    city_name                        character varying(50),
    state_province_id                integer,
    latitude                         double precision,
    longitude                        double precision,
    latest_recorded_population       bigint,
    last_edited_by                   integer,
    last_edited_when                 timestamp with time zone,
    _batch_id                        bigint NOT NULL,
    _extracted_at                    timestamp with time zone NOT NULL,
    _row_hash                        text NOT NULL,
    _dq_flags                        text[] NOT NULL DEFAULT '{}'
);

-- ---------- application.delivery_methods ----------
CREATE TABLE IF NOT EXISTS stg_raw.application_delivery_methods (
    _raw_id                          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    delivery_method_id               integer,
    delivery_method_name             character varying(50),
    last_edited_by                   integer,
    last_edited_when                 timestamp with time zone,
    _batch_id                        bigint NOT NULL,
    _extracted_at                    timestamp with time zone NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_raw_application_delivery_methods_batch ON stg_raw.application_delivery_methods (_batch_id);
CREATE INDEX IF NOT EXISTS ix_raw_application_delivery_methods_pk ON stg_raw.application_delivery_methods (delivery_method_id);

CREATE TABLE IF NOT EXISTS stg_clean.application_delivery_methods (
    delivery_method_id               integer PRIMARY KEY,
    delivery_method_name             character varying(50),
    last_edited_by                   integer,
    last_edited_when                 timestamp with time zone,
    _batch_id                        bigint NOT NULL,
    _extracted_at                    timestamp with time zone NOT NULL,
    _row_hash                        text NOT NULL,
    _dq_flags                        text[] NOT NULL DEFAULT '{}'
);

-- ---------- warehouse.colors ----------
CREATE TABLE IF NOT EXISTS stg_raw.warehouse_colors (
    _raw_id                          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    color_id                         integer,
    color_name                       character varying(20),
    last_edited_by                   integer,
    last_edited_when                 timestamp with time zone,
    _batch_id                        bigint NOT NULL,
    _extracted_at                    timestamp with time zone NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_raw_warehouse_colors_batch ON stg_raw.warehouse_colors (_batch_id);
CREATE INDEX IF NOT EXISTS ix_raw_warehouse_colors_pk ON stg_raw.warehouse_colors (color_id);

CREATE TABLE IF NOT EXISTS stg_clean.warehouse_colors (
    color_id                         integer PRIMARY KEY,
    color_name                       character varying(20),
    last_edited_by                   integer,
    last_edited_when                 timestamp with time zone,
    _batch_id                        bigint NOT NULL,
    _extracted_at                    timestamp with time zone NOT NULL,
    _row_hash                        text NOT NULL,
    _dq_flags                        text[] NOT NULL DEFAULT '{}'
);

-- ---------- warehouse.package_types ----------
CREATE TABLE IF NOT EXISTS stg_raw.warehouse_package_types (
    _raw_id                          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    package_type_id                  integer,
    package_type_name                character varying(50),
    last_edited_by                   integer,
    last_edited_when                 timestamp with time zone,
    _batch_id                        bigint NOT NULL,
    _extracted_at                    timestamp with time zone NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_raw_warehouse_package_types_batch ON stg_raw.warehouse_package_types (_batch_id);
CREATE INDEX IF NOT EXISTS ix_raw_warehouse_package_types_pk ON stg_raw.warehouse_package_types (package_type_id);

CREATE TABLE IF NOT EXISTS stg_clean.warehouse_package_types (
    package_type_id                  integer PRIMARY KEY,
    package_type_name                character varying(50),
    last_edited_by                   integer,
    last_edited_when                 timestamp with time zone,
    _batch_id                        bigint NOT NULL,
    _extracted_at                    timestamp with time zone NOT NULL,
    _row_hash                        text NOT NULL,
    _dq_flags                        text[] NOT NULL DEFAULT '{}'
);

-- ---------- warehouse.stock_groups ----------
CREATE TABLE IF NOT EXISTS stg_raw.warehouse_stock_groups (
    _raw_id                          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    stock_group_id                   integer,
    stock_group_name                 character varying(50),
    last_edited_by                   integer,
    last_edited_when                 timestamp with time zone,
    _batch_id                        bigint NOT NULL,
    _extracted_at                    timestamp with time zone NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_raw_warehouse_stock_groups_batch ON stg_raw.warehouse_stock_groups (_batch_id);
CREATE INDEX IF NOT EXISTS ix_raw_warehouse_stock_groups_pk ON stg_raw.warehouse_stock_groups (stock_group_id);

CREATE TABLE IF NOT EXISTS stg_clean.warehouse_stock_groups (
    stock_group_id                   integer PRIMARY KEY,
    stock_group_name                 character varying(50),
    last_edited_by                   integer,
    last_edited_when                 timestamp with time zone,
    _batch_id                        bigint NOT NULL,
    _extracted_at                    timestamp with time zone NOT NULL,
    _row_hash                        text NOT NULL,
    _dq_flags                        text[] NOT NULL DEFAULT '{}'
);

-- ---------- warehouse.stock_items ----------
CREATE TABLE IF NOT EXISTS stg_raw.warehouse_stock_items (
    _raw_id                          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    stock_item_id                    integer,
    stock_item_name                  character varying(100),
    color_id                         integer,
    unit_package_id                  integer,
    outer_package_id                 integer,
    brand                            character varying(50),
    size                             character varying(20),
    lead_time_days                   integer,
    quantity_per_outer               integer,
    is_chiller_stock                 boolean,
    tax_rate                         numeric(18,3),
    unit_price                       numeric(18,2),
    recommended_retail_price         numeric(18,2),
    typical_weight_per_unit          numeric(18,3),
    last_edited_by                   integer,
    last_edited_when                 timestamp with time zone,
    _batch_id                        bigint NOT NULL,
    _extracted_at                    timestamp with time zone NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_raw_warehouse_stock_items_batch ON stg_raw.warehouse_stock_items (_batch_id);
CREATE INDEX IF NOT EXISTS ix_raw_warehouse_stock_items_pk ON stg_raw.warehouse_stock_items (stock_item_id);

CREATE TABLE IF NOT EXISTS stg_clean.warehouse_stock_items (
    stock_item_id                    integer PRIMARY KEY,
    stock_item_name                  character varying(100),
    color_id                         integer,
    unit_package_id                  integer,
    outer_package_id                 integer,
    brand                            character varying(50),
    size                             character varying(20),
    lead_time_days                   integer,
    quantity_per_outer               integer,
    is_chiller_stock                 boolean,
    tax_rate                         numeric(18,3),
    unit_price                       numeric(18,2),
    recommended_retail_price         numeric(18,2),
    typical_weight_per_unit          numeric(18,3),
    last_edited_by                   integer,
    last_edited_when                 timestamp with time zone,
    _batch_id                        bigint NOT NULL,
    _extracted_at                    timestamp with time zone NOT NULL,
    _row_hash                        text NOT NULL,
    _dq_flags                        text[] NOT NULL DEFAULT '{}'
);

-- ---------- warehouse.stock_item_stock_groups ----------
CREATE TABLE IF NOT EXISTS stg_raw.warehouse_stock_item_stock_groups (
    _raw_id                          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    stock_item_stock_group_id        integer,
    stock_item_id                    integer,
    stock_group_id                   integer,
    last_edited_by                   integer,
    last_edited_when                 timestamp with time zone,
    _batch_id                        bigint NOT NULL,
    _extracted_at                    timestamp with time zone NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_raw_warehouse_stock_item_stock_groups_batch ON stg_raw.warehouse_stock_item_stock_groups (_batch_id);
CREATE INDEX IF NOT EXISTS ix_raw_warehouse_stock_item_stock_groups_pk ON stg_raw.warehouse_stock_item_stock_groups (stock_item_stock_group_id);

CREATE TABLE IF NOT EXISTS stg_clean.warehouse_stock_item_stock_groups (
    stock_item_stock_group_id        integer PRIMARY KEY,
    stock_item_id                    integer,
    stock_group_id                   integer,
    last_edited_by                   integer,
    last_edited_when                 timestamp with time zone,
    _batch_id                        bigint NOT NULL,
    _extracted_at                    timestamp with time zone NOT NULL,
    _row_hash                        text NOT NULL,
    _dq_flags                        text[] NOT NULL DEFAULT '{}'
);

-- ---------- sales.buying_groups ----------
CREATE TABLE IF NOT EXISTS stg_raw.sales_buying_groups (
    _raw_id                          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    buying_group_id                  integer,
    buying_group_name                character varying(50),
    last_edited_by                   integer,
    last_edited_when                 timestamp with time zone,
    _batch_id                        bigint NOT NULL,
    _extracted_at                    timestamp with time zone NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_raw_sales_buying_groups_batch ON stg_raw.sales_buying_groups (_batch_id);
CREATE INDEX IF NOT EXISTS ix_raw_sales_buying_groups_pk ON stg_raw.sales_buying_groups (buying_group_id);

CREATE TABLE IF NOT EXISTS stg_clean.sales_buying_groups (
    buying_group_id                  integer PRIMARY KEY,
    buying_group_name                character varying(50),
    last_edited_by                   integer,
    last_edited_when                 timestamp with time zone,
    _batch_id                        bigint NOT NULL,
    _extracted_at                    timestamp with time zone NOT NULL,
    _row_hash                        text NOT NULL,
    _dq_flags                        text[] NOT NULL DEFAULT '{}'
);

-- ---------- sales.customer_categories ----------
CREATE TABLE IF NOT EXISTS stg_raw.sales_customer_categories (
    _raw_id                          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    customer_category_id             integer,
    customer_category_name           character varying(50),
    last_edited_by                   integer,
    last_edited_when                 timestamp with time zone,
    _batch_id                        bigint NOT NULL,
    _extracted_at                    timestamp with time zone NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_raw_sales_customer_categories_batch ON stg_raw.sales_customer_categories (_batch_id);
CREATE INDEX IF NOT EXISTS ix_raw_sales_customer_categories_pk ON stg_raw.sales_customer_categories (customer_category_id);

CREATE TABLE IF NOT EXISTS stg_clean.sales_customer_categories (
    customer_category_id             integer PRIMARY KEY,
    customer_category_name           character varying(50),
    last_edited_by                   integer,
    last_edited_when                 timestamp with time zone,
    _batch_id                        bigint NOT NULL,
    _extracted_at                    timestamp with time zone NOT NULL,
    _row_hash                        text NOT NULL,
    _dq_flags                        text[] NOT NULL DEFAULT '{}'
);

-- ---------- sales.customers ----------
CREATE TABLE IF NOT EXISTS stg_raw.sales_customers (
    _raw_id                          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    customer_id                      integer,
    customer_name                    character varying(100),
    bill_to_customer_id              integer,
    customer_category_id             integer,
    buying_group_id                  integer,
    primary_contact_person_id        integer,
    alternate_contact_person_id      integer,
    delivery_method_id               integer,
    delivery_city_id                 integer,
    postal_city_id                   integer,
    credit_limit                     numeric(18,2),
    account_opened_date              date,
    standard_discount_percentage     numeric(18,3),
    is_statement_sent                boolean,
    is_on_credit_hold                boolean,
    payment_days                     integer,
    delivery_postal_code             character varying(10),
    delivery_latitude                double precision,
    delivery_longitude               double precision,
    last_edited_by                   integer,
    last_edited_when                 timestamp with time zone,
    _batch_id                        bigint NOT NULL,
    _extracted_at                    timestamp with time zone NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_raw_sales_customers_batch ON stg_raw.sales_customers (_batch_id);
CREATE INDEX IF NOT EXISTS ix_raw_sales_customers_pk ON stg_raw.sales_customers (customer_id);

CREATE TABLE IF NOT EXISTS stg_clean.sales_customers (
    customer_id                      integer PRIMARY KEY,
    customer_name                    character varying(100),
    bill_to_customer_id              integer,
    customer_category_id             integer,
    buying_group_id                  integer,
    primary_contact_person_id        integer,
    alternate_contact_person_id      integer,
    delivery_method_id               integer,
    delivery_city_id                 integer,
    postal_city_id                   integer,
    credit_limit                     numeric(18,2),
    account_opened_date              date,
    standard_discount_percentage     numeric(18,3),
    is_statement_sent                boolean,
    is_on_credit_hold                boolean,
    payment_days                     integer,
    delivery_postal_code             character varying(10),
    delivery_latitude                double precision,
    delivery_longitude               double precision,
    last_edited_by                   integer,
    last_edited_when                 timestamp with time zone,
    _batch_id                        bigint NOT NULL,
    _extracted_at                    timestamp with time zone NOT NULL,
    _row_hash                        text NOT NULL,
    _dq_flags                        text[] NOT NULL DEFAULT '{}'
);

-- ---------- sales.orders ----------
CREATE TABLE IF NOT EXISTS stg_raw.sales_orders (
    _raw_id                          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_id                         integer,
    customer_id                      integer,
    salesperson_person_id            integer,
    picked_by_person_id              integer,
    contact_person_id                integer,
    backorder_order_id               integer,
    order_date                       date,
    expected_delivery_date           date,
    customer_purchase_order_number   character varying(20),
    is_undersupply_backordered       boolean,
    picking_completed_when           timestamp with time zone,
    last_edited_by                   integer,
    last_edited_when                 timestamp with time zone,
    _batch_id                        bigint NOT NULL,
    _extracted_at                    timestamp with time zone NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_raw_sales_orders_batch ON stg_raw.sales_orders (_batch_id);
CREATE INDEX IF NOT EXISTS ix_raw_sales_orders_pk ON stg_raw.sales_orders (order_id);

CREATE TABLE IF NOT EXISTS stg_clean.sales_orders (
    order_id                         integer PRIMARY KEY,
    customer_id                      integer,
    salesperson_person_id            integer,
    picked_by_person_id              integer,
    contact_person_id                integer,
    backorder_order_id               integer,
    order_date                       date,
    expected_delivery_date           date,
    customer_purchase_order_number   character varying(20),
    is_undersupply_backordered       boolean,
    picking_completed_when           timestamp with time zone,
    last_edited_by                   integer,
    last_edited_when                 timestamp with time zone,
    _batch_id                        bigint NOT NULL,
    _extracted_at                    timestamp with time zone NOT NULL,
    _row_hash                        text NOT NULL,
    _dq_flags                        text[] NOT NULL DEFAULT '{}'
);

-- ---------- sales.order_lines ----------
CREATE TABLE IF NOT EXISTS stg_raw.sales_order_lines (
    _raw_id                          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_line_id                    integer,
    order_id                         integer,
    stock_item_id                    integer,
    description                      character varying(100),
    package_type_id                  integer,
    quantity                         integer,
    unit_price                       numeric(18,2),
    tax_rate                         numeric(18,3),
    picked_quantity                  integer,
    picking_completed_when           timestamp with time zone,
    last_edited_by                   integer,
    last_edited_when                 timestamp with time zone,
    _batch_id                        bigint NOT NULL,
    _extracted_at                    timestamp with time zone NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_raw_sales_order_lines_batch ON stg_raw.sales_order_lines (_batch_id);
CREATE INDEX IF NOT EXISTS ix_raw_sales_order_lines_pk ON stg_raw.sales_order_lines (order_line_id);

CREATE TABLE IF NOT EXISTS stg_clean.sales_order_lines (
    order_line_id                    integer PRIMARY KEY,
    order_id                         integer,
    stock_item_id                    integer,
    description                      character varying(100),
    package_type_id                  integer,
    quantity                         integer,
    unit_price                       numeric(18,2),
    tax_rate                         numeric(18,3),
    picked_quantity                  integer,
    picking_completed_when           timestamp with time zone,
    last_edited_by                   integer,
    last_edited_when                 timestamp with time zone,
    _batch_id                        bigint NOT NULL,
    _extracted_at                    timestamp with time zone NOT NULL,
    _row_hash                        text NOT NULL,
    _dq_flags                        text[] NOT NULL DEFAULT '{}'
);

-- ---------- sales.invoices ----------
CREATE TABLE IF NOT EXISTS stg_raw.sales_invoices (
    _raw_id                          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    invoice_id                       integer,
    customer_id                      integer,
    bill_to_customer_id              integer,
    order_id                         integer,
    delivery_method_id               integer,
    contact_person_id                integer,
    accounts_person_id               integer,
    salesperson_person_id            integer,
    packed_by_person_id              integer,
    invoice_date                     date,
    customer_purchase_order_number   character varying(20),
    is_credit_note                   boolean,
    credit_note_reason               text,
    total_dry_items                  integer,
    total_chiller_items              integer,
    confirmed_delivery_time          timestamp with time zone,
    last_edited_by                   integer,
    last_edited_when                 timestamp with time zone,
    _batch_id                        bigint NOT NULL,
    _extracted_at                    timestamp with time zone NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_raw_sales_invoices_batch ON stg_raw.sales_invoices (_batch_id);
CREATE INDEX IF NOT EXISTS ix_raw_sales_invoices_pk ON stg_raw.sales_invoices (invoice_id);

CREATE TABLE IF NOT EXISTS stg_clean.sales_invoices (
    invoice_id                       integer PRIMARY KEY,
    customer_id                      integer,
    bill_to_customer_id              integer,
    order_id                         integer,
    delivery_method_id               integer,
    contact_person_id                integer,
    accounts_person_id               integer,
    salesperson_person_id            integer,
    packed_by_person_id              integer,
    invoice_date                     date,
    customer_purchase_order_number   character varying(20),
    is_credit_note                   boolean,
    credit_note_reason               text,
    total_dry_items                  integer,
    total_chiller_items              integer,
    confirmed_delivery_time          timestamp with time zone,
    last_edited_by                   integer,
    last_edited_when                 timestamp with time zone,
    _batch_id                        bigint NOT NULL,
    _extracted_at                    timestamp with time zone NOT NULL,
    _row_hash                        text NOT NULL,
    _dq_flags                        text[] NOT NULL DEFAULT '{}'
);

-- ---------- sales.invoice_lines ----------
CREATE TABLE IF NOT EXISTS stg_raw.sales_invoice_lines (
    _raw_id                          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    invoice_line_id                  integer,
    invoice_id                       integer,
    stock_item_id                    integer,
    description                      character varying(100),
    package_type_id                  integer,
    quantity                         integer,
    unit_price                       numeric(18,2),
    tax_rate                         numeric(18,3),
    tax_amount                       numeric(18,2),
    line_profit                      numeric(18,2),
    extended_price                   numeric(18,2),
    last_edited_by                   integer,
    last_edited_when                 timestamp with time zone,
    _batch_id                        bigint NOT NULL,
    _extracted_at                    timestamp with time zone NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_raw_sales_invoice_lines_batch ON stg_raw.sales_invoice_lines (_batch_id);
CREATE INDEX IF NOT EXISTS ix_raw_sales_invoice_lines_pk ON stg_raw.sales_invoice_lines (invoice_line_id);

CREATE TABLE IF NOT EXISTS stg_clean.sales_invoice_lines (
    invoice_line_id                  integer PRIMARY KEY,
    invoice_id                       integer,
    stock_item_id                    integer,
    description                      character varying(100),
    package_type_id                  integer,
    quantity                         integer,
    unit_price                       numeric(18,2),
    tax_rate                         numeric(18,3),
    tax_amount                       numeric(18,2),
    line_profit                      numeric(18,2),
    extended_price                   numeric(18,2),
    last_edited_by                   integer,
    last_edited_when                 timestamp with time zone,
    _batch_id                        bigint NOT NULL,
    _extracted_at                    timestamp with time zone NOT NULL,
    _row_hash                        text NOT NULL,
    _dq_flags                        text[] NOT NULL DEFAULT '{}'
);
