# Diccionario de datos — Data Warehouse (`faro_analytics.dw`)

> Generado por `database/scripts/documentar_dw.py` desde la base real (2026-11-15 05:06 UTC). No editar a mano.

Modelo, grano y decisiones: [modelo-dimensional.md](modelo-dimensional.md).

- **Clave:** `PK` primaria · `FK` foránea · `UQ` única. **Nulo:** ✔ admite NULL.
- Todas las dimensiones tienen un **miembro desconocido** con clave `-1`.
- Las filas incluyen ese miembro desconocido.

## Tablas

| Tabla | Filas | Descripción |
|---|---:|---|
| [`dw.fact_ventas`](#dwfact_ventas) | 228,759 | Ventas facturadas. GRANO: una fila por línea de factura. Margen % y ticket promedio se calculan, no se suman. |
| [`dw.dim_fecha`](#dwdim_fecha) | 5,479 | Calendario (un día por fila). Cumple dos roles en el hecho: fecha de factura y fecha de pedido. |
| [`dw.dim_cliente`](#dwdim_cliente) | 664 | Clientes con historia (SCD2) en su segmentación: categoría, grupo de compra y cliente de facturación. |
| [`dw.dim_producto`](#dwdim_producto) | 228 | Productos con historia (SCD2) en precio, impuesto y grupo principal. |
| [`dw.dim_empleado`](#dwdim_empleado) | 20 | Empleados (SCD1). En el hecho cumple el rol de vendedor. |
| [`dw.dim_geografia`](#dwdim_geografia) | 37,941 | Ciudad de entrega (SCD1). Jerarquía: ciudad -> estado -> territorio de venta -> país. |
| [`dw.dim_grupo_producto`](#dwdim_grupo_producto) | 11 | Grupos de producto (SCD1) con su prioridad de especificidad. |
| [`dw.puente_producto_grupo`](#dwpuente_producto_grupo) | 442 | Puente producto-grupo. Sin el factor de ponderación las ventas se contarían una vez por grupo. |

## dw.fact_ventas

Ventas facturadas. GRANO: una fila por línea de factura. Margen % y ticket promedio se calculan, no se suman.

| Columna | Tipo | Nulo | Clave | Descripción |
|---|---|:---:|---|---|
| `venta_key` | bigint |  | PK | Clave sustituta del hecho. |
| `fecha_factura_key` | integer |  | FK → `dw.dim_fecha` | Fecha de la factura (rol de dim_fecha). Fecha principal del análisis. |
| `fecha_pedido_key` | integer |  | FK → `dw.dim_fecha` | Fecha del pedido que originó la venta (segundo rol de dim_fecha). |
| `cliente_key` | integer |  | FK → `dw.dim_cliente` | Cliente que compra, en la versión vigente a la fecha de la factura (SCD2). |
| `cliente_facturacion_key` | integer |  | FK → `dw.dim_cliente` | Cliente que paga (rol de dim_cliente), en su versión vigente a la fecha de la factura. |
| `producto_key` | integer |  | FK → `dw.dim_producto` | Producto en la versión vigente a la fecha de la factura (precio y grupo de ese momento). |
| `vendedor_key` | integer |  | FK → `dw.dim_empleado` | Vendedor (rol de dim_empleado). -1 = desconocido, se reasigna al llegar la dimensión. |
| `geografia_key` | integer |  | FK → `dw.dim_geografia` | Ciudad de entrega del cliente al momento de cargar la venta. |
| `linea_factura_id` | integer |  | UQ | Clave natural de la línea de factura. Único: garantiza el grano del hecho. |
| `factura_id` | integer |  |  | Dimensión degenerada: número de factura (para contar facturas y navegar al detalle). |
| `pedido_id` | integer | ✔ |  | Dimensión degenerada: número de pedido. |
| `fecha_factura` | date |  |  | Fecha de la factura (también como fecha, para buscar la versión SCD2 vigente). |
| `cliente_id` | integer |  |  |  |
| `cliente_facturacion_id` | integer |  |  |  |
| `producto_id` | integer |  |  |  |
| `vendedor_id` | integer |  |  |  |
| `ciudad_id` | integer | ✔ |  |  |
| `cantidad` | integer |  |  | Unidades vendidas. Aditiva. |
| `venta_bruta` | numeric(18,2) |  |  | Importe de la línea CON impuestos (extended_price). Aditiva. |
| `impuesto` | numeric(18,2) |  |  | Impuesto de la línea. Aditiva. |
| `venta_neta` | numeric(18,2) |  |  | venta_bruta - impuesto. Base de los KPI de venta. Aditiva. |
| `costo` | numeric(18,2) |  |  | venta_neta - utilidad. Aditiva. |
| `utilidad` | numeric(18,2) |  |  | Margen de la línea sin impuestos; negativa = venta bajo costo. Aditiva. |
| `precio_unitario` | numeric(18,2) | ✔ |  | Precio unitario sin impuestos. NO aditiva: promediar ponderando por cantidad. |
| `tasa_impuesto` | numeric(18,3) | ✔ |  | Tasa de impuesto en porcentaje. NO aditiva. |
| `es_venta_bajo_costo` | boolean |  |  | TRUE si utilidad < 0 (regla de calidad V04: problema de precios, no de datos). |
| `es_atipico` | boolean |  |  | TRUE si la cantidad o el importe superan Q3 + 3·IQR (reglas A01/A02). |
| `es_simulado` | boolean |  |  | TRUE si la venta la generó el simulador (datos de demostración, no históricos). |
| `batch_id` | bigint |  |  | Ejecución del ETL que cargó o actualizó la fila (linaje, ver audit.etl_execution). |
| `cargado_en` | timestamp with time zone |  |  | Momento en que la fila se cargó o actualizó por última vez. |

## dw.dim_fecha

Calendario (un día por fila). Cumple dos roles en el hecho: fecha de factura y fecha de pedido.

| Columna | Tipo | Nulo | Clave | Descripción |
|---|---|:---:|---|---|
| `fecha_key` | integer |  | PK | Clave AAAAMMDD (p. ej. 20160531). -1 = desconocida. |
| `fecha` | date | ✔ | UQ |  |
| `anio` | integer |  |  |  |
| `trimestre` | integer |  |  |  |
| `mes` | integer |  |  |  |
| `nombre_mes` | text |  |  |  |
| `anio_mes` | text |  |  |  |
| `semana_iso` | integer |  |  |  |
| `dia_mes` | integer |  |  |  |
| `dia_semana` | integer |  |  | 1 = lunes ... 7 = domingo (ISO). |
| `nombre_dia` | text |  |  |  |
| `es_fin_de_semana` | boolean |  |  |  |
| `es_dia_habil` | boolean |  |  | Lunes a sábado. En WWI no se vende los domingos. |

## dw.dim_cliente

Clientes con historia (SCD2) en su segmentación: categoría, grupo de compra y cliente de facturación.

| Columna | Tipo | Nulo | Clave | Descripción |
|---|---|:---:|---|---|
| `cliente_key` | integer |  | PK | Clave sustituta: una por VERSIÓN del cliente. -1 = desconocido. |
| `cliente_id` | integer |  | UQ | Clave natural (sales.customers.customer_id). |
| `nombre` | text |  |  |  |
| `categoria_id` | integer | ✔ |  | SCD2: un cambio de categoría crea una versión nueva. |
| `grupo_compra_id` | integer | ✔ |  | SCD2: grupo de compra (cadena). NULL = cliente independiente. |
| `cliente_facturacion_id` | integer |  |  | SCD2: cliente al que se le factura (la casa matriz o el propio cliente). |
| `categoria` | text |  |  | Nombre de la categoría (se refresca según categoria_id; renombrar no versiona). |
| `grupo_compra` | text |  |  | Nombre del grupo de compra, o 'Independiente'. |
| `es_casa_matriz` | boolean |  |  | TRUE si otros clientes se facturan a este. |
| `politica_credito` | text |  |  | 'Límite propio' o 'Gestionado por casa matriz' (explica el NULL de limite_credito). |
| `limite_credito` | numeric(18,2) | ✔ |  | Límite de crédito. NULL = no aplica (lo gestiona la casa matriz); no es cero. |
| `dias_pago` | integer | ✔ |  |  |
| `en_suspension_credito` | boolean | ✔ |  |  |
| `descuento_estandar` | numeric(18,3) | ✔ |  |  |
| `fecha_apertura` | date | ✔ |  |  |
| `valido_desde` | date |  |  | Inicio de vigencia de la versión (la primera versión rige desde 1900-01-01). |
| `valido_hasta` | date |  |  | Fin de vigencia de la versión (9999-12-31 = vigente). |
| `es_actual` | boolean |  |  | TRUE en la versión vigente (exactamente una por cliente). |
| `version` | integer |  | UQ | Número de versión del cliente (1, 2, ...). |
| `hash_tipo2` | text |  |  | Huella de los atributos SCD2: solo se versiona si cambia. |
| `batch_id` | bigint |  |  |  |

## dw.dim_producto

Productos con historia (SCD2) en precio, impuesto y grupo principal.

| Columna | Tipo | Nulo | Clave | Descripción |
|---|---|:---:|---|---|
| `producto_key` | integer |  | PK | Clave sustituta: una por VERSIÓN del producto. -1 = desconocido. |
| `producto_id` | integer |  | UQ | Clave natural (warehouse.stock_items.stock_item_id). |
| `nombre` | text |  |  |  |
| `marca` | text |  |  | Marca, o 'Sin marca' (el 92 % no tiene marca en la fuente). |
| `color` | text |  |  | Color, o 'Sin color' (no aplica). |
| `talla` | text | ✔ |  |  |
| `empaque_unidad` | text | ✔ |  |  |
| `empaque_exterior` | text | ✔ |  |  |
| `cantidad_por_empaque` | integer | ✔ |  |  |
| `requiere_frio` | boolean | ✔ |  |  |
| `dias_reposicion` | integer | ✔ |  |  |
| `peso_unitario` | numeric(18,3) | ✔ |  |  |
| `precio_lista` | numeric(18,2) | ✔ |  | SCD2: precio de lista sin impuestos vigente en la versión. |
| `precio_venta_sugerido` | numeric(18,2) | ✔ |  |  |
| `tasa_impuesto` | numeric(18,3) | ✔ |  | SCD2: tasa de impuesto vigente en la versión. |
| `grupo_principal_id` | integer | ✔ |  | SCD2: grupo más específico del producto (prioridad fija, decisión D-16). |
| `grupo_principal` | text |  |  | Nombre del grupo principal. Analizar por este atributo NO duplica importes. |
| `cantidad_grupos` | integer |  |  | En cuántos grupos está el producto (para analizar por pertenencia, usar el puente). |
| `valido_desde` | date |  |  | Inicio de vigencia de la versión. |
| `valido_hasta` | date |  |  | Fin de vigencia de la versión (9999-12-31 = vigente). |
| `es_actual` | boolean |  |  | TRUE en la versión vigente. |
| `version` | integer |  | UQ |  |
| `hash_tipo2` | text |  |  |  |
| `batch_id` | bigint |  |  |  |

## dw.dim_empleado

Empleados (SCD1). En el hecho cumple el rol de vendedor.

| Columna | Tipo | Nulo | Clave | Descripción |
|---|---|:---:|---|---|
| `empleado_key` | integer |  | PK |  |
| `persona_id` | integer |  | UQ |  |
| `nombre_completo` | text |  |  |  |
| `nombre_preferido` | text |  |  |  |
| `es_vendedor` | boolean |  |  | TRUE si la persona vende (rol vendedor en el hecho). |
| `batch_id` | bigint |  |  |  |

## dw.dim_geografia

Ciudad de entrega (SCD1). Jerarquía: ciudad -> estado -> territorio de venta -> país.

| Columna | Tipo | Nulo | Clave | Descripción |
|---|---|:---:|---|---|
| `geografia_key` | integer |  | PK |  |
| `ciudad_id` | integer |  | UQ |  |
| `ciudad` | text |  |  |  |
| `estado` | text |  |  |  |
| `codigo_estado` | text | ✔ |  |  |
| `territorio_venta` | text |  |  | Territorio comercial (9 en WWI): agrupa estados. |
| `pais` | text |  |  |  |
| `latitud` | double precision | ✔ |  | Latitud de la ciudad (para mapas). |
| `longitud` | double precision | ✔ |  |  |
| `batch_id` | bigint |  |  |  |

## dw.dim_grupo_producto

Grupos de producto (SCD1) con su prioridad de especificidad.

| Columna | Tipo | Nulo | Clave | Descripción |
|---|---|:---:|---|---|
| `grupo_key` | integer |  | PK |  |
| `grupo_id` | integer |  | UQ |  |
| `nombre` | text |  |  |  |
| `prioridad` | integer |  |  | 1 = grupo más específico. Define el grupo principal de cada producto. |
| `batch_id` | bigint |  |  |  |

## dw.puente_producto_grupo

Puente producto-grupo. Sin el factor de ponderación las ventas se contarían una vez por grupo.

| Columna | Tipo | Nulo | Clave | Descripción |
|---|---|:---:|---|---|
| `producto_id` | integer |  | PK |  |
| `grupo_key` | integer |  | PK, FK → `dw.dim_grupo_producto` |  |
| `factor_ponderacion` | numeric |  |  | 1 / grupos del producto. SUM(medida * factor) reparte la venta sin duplicarla. |
| `es_principal` | boolean |  |  | TRUE en el grupo principal del producto. |
