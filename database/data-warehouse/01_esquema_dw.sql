-- =====================================================================
-- Faro · Data Warehouse (base faro_analytics, esquema dw)
-- Esquema estrella del proceso de VENTAS. IDEMPOTENTE.
-- Diseño: documentation/modelos/modelo-dimensional.md
--
-- GRANO de fact_ventas: una fila por LÍNEA DE FACTURA.
--
-- Convenciones:
--  * Claves sustitutas *_key (IDENTITY), sin significado. dim_fecha usa AAAAMMDD.
--  * Cada dimensión conserva la clave natural de la fuente (trazabilidad).
--  * Miembro desconocido: clave -1 en todas las dimensiones.
--  * SCD Tipo 2 (dim_cliente, dim_producto): valido_desde / valido_hasta / es_actual.
--    La primera versión rige desde 1900-01-01; la vigente, hasta 9999-12-31.
-- =====================================================================

CREATE SCHEMA IF NOT EXISTS dw;
COMMENT ON SCHEMA dw IS 'Data Warehouse dimensional (esquema estrella) del proceso de ventas.';

-- ============================ dim_fecha =============================
CREATE TABLE IF NOT EXISTS dw.dim_fecha (
    fecha_key         integer PRIMARY KEY,          -- AAAAMMDD
    fecha             date UNIQUE,                  -- NULL solo en el miembro desconocido
    anio              integer  NOT NULL,
    trimestre         integer  NOT NULL,
    mes               integer  NOT NULL,
    nombre_mes        text     NOT NULL,
    anio_mes          text     NOT NULL,            -- AAAA-MM
    semana_iso        integer  NOT NULL,
    dia_mes           integer  NOT NULL,
    dia_semana        integer  NOT NULL,            -- 1 = lunes ... 7 = domingo
    nombre_dia        text     NOT NULL,
    es_fin_de_semana  boolean  NOT NULL,
    es_dia_habil      boolean  NOT NULL             -- lunes a sábado: WWI no vende los domingos
);
COMMENT ON TABLE dw.dim_fecha IS
    'Calendario (un día por fila). Cumple dos roles en el hecho: fecha de factura y fecha de pedido.';

INSERT INTO dw.dim_fecha
SELECT to_char(d, 'YYYYMMDD')::integer,
       d::date,
       extract(year FROM d)::integer,
       extract(quarter FROM d)::integer,
       extract(month FROM d)::integer,
       (ARRAY['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto',
              'septiembre', 'octubre', 'noviembre', 'diciembre'])[extract(month FROM d)::integer],
       to_char(d, 'YYYY-MM'),
       extract(week FROM d)::integer,
       extract(day FROM d)::integer,
       extract(isodow FROM d)::integer,
       (ARRAY['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo'])
           [extract(isodow FROM d)::integer],
       extract(isodow FROM d) >= 6,
       extract(isodow FROM d) <= 6
FROM generate_series('2013-01-01'::date, '2027-12-31'::date, '1 day') AS d
ON CONFLICT (fecha_key) DO NOTHING;

INSERT INTO dw.dim_fecha
VALUES (-1, NULL, 0, 0, 0, 'Desconocido', 'Desconocido', 0, 0, 0, 'Desconocido', false, false)
ON CONFLICT (fecha_key) DO NOTHING;

-- =========================== dim_cliente ============================
CREATE TABLE IF NOT EXISTS dw.dim_cliente (
    cliente_key            integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    cliente_id             integer NOT NULL,        -- clave natural (sales.customers)
    nombre                 text    NOT NULL,
    -- SCD2: la historia sigue a los IDENTIFICADORES de la segmentación. Los nombres se
    -- refrescan según su ID en todas las versiones (renombrar una categoría no versiona).
    categoria_id           integer,                 -- SCD2
    grupo_compra_id        integer,                 -- SCD2 (NULL = independiente)
    cliente_facturacion_id integer NOT NULL,        -- SCD2 (a quién se le factura)
    categoria              text    NOT NULL,        -- nombre de categoria_id
    grupo_compra           text    NOT NULL,        -- nombre de grupo_compra_id ('Independiente')
    es_casa_matriz         boolean NOT NULL,
    politica_credito       text    NOT NULL,
    limite_credito         numeric(18,2),           -- NULL = no aplica (lo gestiona la casa matriz)
    dias_pago              integer,
    en_suspension_credito  boolean,
    descuento_estandar     numeric(18,3),
    fecha_apertura         date,
    valido_desde           date    NOT NULL,
    valido_hasta           date    NOT NULL,
    es_actual              boolean NOT NULL,
    version                integer NOT NULL,
    hash_tipo2             text    NOT NULL,        -- huella de los atributos SCD2
    batch_id               bigint  NOT NULL,
    CONSTRAINT ck_cliente_vigencia CHECK (valido_desde <= valido_hasta),
    CONSTRAINT uq_cliente_version UNIQUE (cliente_id, version)
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_dim_cliente_actual ON dw.dim_cliente (cliente_id) WHERE es_actual;
COMMENT ON TABLE dw.dim_cliente IS
    'Clientes con historia (SCD2) en su segmentación: categoría, grupo de compra y cliente de facturación.';

INSERT INTO dw.dim_cliente (cliente_key, cliente_id, nombre, cliente_facturacion_id, categoria,
    grupo_compra, es_casa_matriz, politica_credito, valido_desde, valido_hasta,
    es_actual, version, hash_tipo2, batch_id)
OVERRIDING SYSTEM VALUE
VALUES (-1, -1, 'Desconocido', -1, 'Desconocido', 'Desconocido', false, 'Desconocido',
        '1900-01-01', '9999-12-31', true, 1, '-', 0)
ON CONFLICT (cliente_key) DO NOTHING;

-- =========================== dim_producto ===========================
CREATE TABLE IF NOT EXISTS dw.dim_producto (
    producto_key           integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    producto_id            integer NOT NULL,        -- clave natural (warehouse.stock_items)
    nombre                 text    NOT NULL,
    marca                  text    NOT NULL,
    color                  text    NOT NULL,
    talla                  text,
    empaque_unidad         text,
    empaque_exterior       text,
    cantidad_por_empaque   integer,
    requiere_frio          boolean,
    dias_reposicion        integer,
    peso_unitario          numeric(18,3),
    precio_lista           numeric(18,2),           -- SCD2
    precio_venta_sugerido  numeric(18,2),           -- SCD2
    tasa_impuesto          numeric(18,3),           -- SCD2
    grupo_principal_id     integer,                 -- SCD2 (el grupo más específico)
    grupo_principal        text    NOT NULL,        -- nombre de grupo_principal_id (se refresca)
    cantidad_grupos        integer NOT NULL,
    valido_desde           date    NOT NULL,
    valido_hasta           date    NOT NULL,
    es_actual              boolean NOT NULL,
    version                integer NOT NULL,
    hash_tipo2             text    NOT NULL,
    batch_id               bigint  NOT NULL,
    CONSTRAINT ck_producto_vigencia CHECK (valido_desde <= valido_hasta),
    CONSTRAINT uq_producto_version UNIQUE (producto_id, version)
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_dim_producto_actual ON dw.dim_producto (producto_id) WHERE es_actual;
COMMENT ON TABLE dw.dim_producto IS
    'Productos con historia (SCD2) en precio, impuesto y grupo principal.';

INSERT INTO dw.dim_producto (producto_key, producto_id, nombre, marca, color, grupo_principal,
    cantidad_grupos, valido_desde, valido_hasta, es_actual, version, hash_tipo2, batch_id)
OVERRIDING SYSTEM VALUE
VALUES (-1, -1, 'Desconocido', 'Desconocido', 'Desconocido', 'Desconocido', 0,
        '1900-01-01', '9999-12-31', true, 1, '-', 0)
ON CONFLICT (producto_key) DO NOTHING;

-- =========================== dim_empleado ===========================
CREATE TABLE IF NOT EXISTS dw.dim_empleado (
    empleado_key      integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    persona_id        integer NOT NULL UNIQUE,      -- clave natural (application.people)
    nombre_completo   text    NOT NULL,
    nombre_preferido  text    NOT NULL,
    es_vendedor       boolean NOT NULL,
    batch_id          bigint  NOT NULL
);
COMMENT ON TABLE dw.dim_empleado IS 'Empleados (SCD1). En el hecho cumple el rol de vendedor.';

INSERT INTO dw.dim_empleado (empleado_key, persona_id, nombre_completo, nombre_preferido,
    es_vendedor, batch_id)
OVERRIDING SYSTEM VALUE VALUES (-1, -1, 'Desconocido', 'Desconocido', false, 0)
ON CONFLICT (empleado_key) DO NOTHING;

-- ========================== dim_geografia ===========================
CREATE TABLE IF NOT EXISTS dw.dim_geografia (
    geografia_key     integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ciudad_id         integer NOT NULL UNIQUE,      -- clave natural (application.cities)
    ciudad            text    NOT NULL,
    estado            text    NOT NULL,
    codigo_estado     text,
    territorio_venta  text    NOT NULL,
    pais              text    NOT NULL,
    latitud           double precision,
    longitud          double precision,
    batch_id          bigint  NOT NULL
);
COMMENT ON TABLE dw.dim_geografia IS
    'Ciudad de entrega (SCD1). Jerarquía: ciudad -> estado -> territorio de venta -> país.';

INSERT INTO dw.dim_geografia (geografia_key, ciudad_id, ciudad, estado, territorio_venta, pais,
    batch_id)
OVERRIDING SYSTEM VALUE
VALUES (-1, -1, 'Desconocido', 'Desconocido', 'Desconocido', 'Desconocido', 0)
ON CONFLICT (geografia_key) DO NOTHING;

-- ======================= dim_grupo_producto =========================
CREATE TABLE IF NOT EXISTS dw.dim_grupo_producto (
    grupo_key  integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    grupo_id   integer NOT NULL UNIQUE,             -- clave natural (warehouse.stock_groups)
    nombre     text    NOT NULL,
    prioridad  integer NOT NULL,                    -- 1 = más específico
    batch_id   bigint  NOT NULL
);
COMMENT ON TABLE dw.dim_grupo_producto IS 'Grupos de producto (SCD1) con su prioridad de especificidad.';

INSERT INTO dw.dim_grupo_producto (grupo_key, grupo_id, nombre, prioridad, batch_id)
OVERRIDING SYSTEM VALUE VALUES (-1, -1, 'Desconocido', 999, 0)
ON CONFLICT (grupo_key) DO NOTHING;

-- ====================== puente_producto_grupo =======================
-- Un producto puede estar en varios grupos (H04). Para analizar por PERTENENCIA sin
-- duplicar importes: SUM(medida * factor_ponderacion).
CREATE TABLE IF NOT EXISTS dw.puente_producto_grupo (
    producto_id         integer NOT NULL,           -- clave natural del producto
    grupo_key           integer NOT NULL REFERENCES dw.dim_grupo_producto (grupo_key),
    factor_ponderacion  numeric NOT NULL,           -- 1 / cantidad de grupos del producto
    es_principal        boolean NOT NULL,
    PRIMARY KEY (producto_id, grupo_key)
);
COMMENT ON TABLE dw.puente_producto_grupo IS
    'Puente producto-grupo. Sin el factor de ponderación las ventas se contarían una vez por grupo.';

-- ============================ fact_ventas ===========================
CREATE TABLE IF NOT EXISTS dw.fact_ventas (
    venta_key                bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    -- dimensiones
    fecha_factura_key        integer NOT NULL REFERENCES dw.dim_fecha (fecha_key),
    fecha_pedido_key         integer NOT NULL REFERENCES dw.dim_fecha (fecha_key),
    cliente_key              integer NOT NULL REFERENCES dw.dim_cliente (cliente_key),
    cliente_facturacion_key  integer NOT NULL REFERENCES dw.dim_cliente (cliente_key),
    producto_key             integer NOT NULL REFERENCES dw.dim_producto (producto_key),
    vendedor_key             integer NOT NULL REFERENCES dw.dim_empleado (empleado_key),
    geografia_key            integer NOT NULL REFERENCES dw.dim_geografia (geografia_key),
    -- grano y dimensiones degeneradas
    linea_factura_id         integer NOT NULL UNIQUE,   -- clave natural: garantiza el grano
    factura_id               integer NOT NULL,
    pedido_id                integer,
    -- claves naturales (trazabilidad y reasignación del miembro desconocido)
    fecha_factura            date    NOT NULL,
    cliente_id               integer NOT NULL,
    cliente_facturacion_id   integer NOT NULL,
    producto_id              integer NOT NULL,
    vendedor_id              integer NOT NULL,
    ciudad_id                integer,
    -- medidas aditivas
    cantidad                 integer       NOT NULL,
    venta_bruta              numeric(18,2) NOT NULL,    -- incluye impuestos
    impuesto                 numeric(18,2) NOT NULL,
    venta_neta               numeric(18,2) NOT NULL,    -- venta_bruta - impuesto
    costo                    numeric(18,2) NOT NULL,
    utilidad                 numeric(18,2) NOT NULL,
    -- medidas no aditivas (referencia; no se suman)
    precio_unitario          numeric(18,2),
    tasa_impuesto            numeric(18,3),
    -- atributos de control
    es_venta_bajo_costo      boolean NOT NULL,
    es_atipico               boolean NOT NULL,
    es_simulado              boolean NOT NULL,
    batch_id                 bigint  NOT NULL,          -- ejecución que la cargó o actualizó
    cargado_en               timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_fact_ventas_fecha    ON dw.fact_ventas (fecha_factura_key);
CREATE INDEX IF NOT EXISTS ix_fact_ventas_cliente  ON dw.fact_ventas (cliente_key);
CREATE INDEX IF NOT EXISTS ix_fact_ventas_producto ON dw.fact_ventas (producto_key);
CREATE INDEX IF NOT EXISTS ix_fact_ventas_factura  ON dw.fact_ventas (factura_id);
COMMENT ON TABLE dw.fact_ventas IS
    'Ventas facturadas. GRANO: una fila por línea de factura. Margen % y ticket promedio se calculan, no se suman.';
