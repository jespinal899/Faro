# Catálogo de reglas de calidad y transformación — Faro

> **Generado** por `database/scripts/documentar_reglas.py` desde
> [etl/config.py](../../etl/config.py): no se edita a mano. Una prueba verifica que esté al día.

Cada lote del ETL evalúa estas reglas en la zona `stg_raw → stg_clean` y guarda el resultado
de cada una en `audit.dq_result` (filas evaluadas y filas que fallaron por ejecución). Los
rechazados quedan en `stg_quarantine.registro_rechazado` con la regla, el detalle, el registro
original y la ejecución, y **se reintentan en cada ejecución**: si la fuente los corrige, entran.
El diseño y la justificación de cada regla están en
[diseno-staging-etl.md](../arquitectura/diseno-staging-etl.md) (secciones 3 y 4).

## Resumen

- **16 reglas** distintas, aplicadas como **35 controles** en 17 tablas.
- Por acción: 31 de cuarentena, 4 de marcar.

| Dimensión de calidad (guía, sección 10) | Controles |
|---|---:|
| Atípicos | 2 |
| Consistencia | 3 |
| Integridad | 8 |
| Oportunidad | 17 |
| Validez | 5 |
| Unicidad | Regla de supervivencia U03 (abajo) |
| Completitud | V02 (precio nulo) y política de nulos por columna (diseño, sección 3.1) |

## Reglas

| Código | Dimensión | Regla | Acción | Tablas |
|---|---|---|---|---|
| A01 | Atípicos | Cantidad atípica (> 225) | ⚠️ Marcar: pasa con su marca | `sales.invoice_lines` |
| A02 | Atípicos | Importe atípico (extended_price > 3643.2) | ⚠️ Marcar: pasa con su marca | `sales.invoice_lines` |
| I02 | Integridad | Factura de la línea inexistente o en cuarentena | ⛔ Cuarentena: no pasa a `stg_clean` | `sales.invoice_lines` |
| I08 | Integridad | Producto inexistente o en cuarentena | ⛔ Cuarentena: no pasa a `stg_clean` | `warehouse.stock_item_stock_groups`, `sales.invoice_lines` |
| I09 | Integridad | Grupo inexistente o en cuarentena | ⛔ Cuarentena: no pasa a `stg_clean` | `warehouse.stock_item_stock_groups` |
| I10 | Integridad | Ciudad de entrega inexistente o en cuarentena | ⛔ Cuarentena: no pasa a `stg_clean` | `sales.customers` |
| I11 | Integridad | Cliente del pedido inexistente o en cuarentena | ⛔ Cuarentena: no pasa a `stg_clean` | `sales.orders`, `sales.invoices` |
| I12 | Integridad | Pedido de la línea inexistente o en cuarentena | ⛔ Cuarentena: no pasa a `stg_clean` | `sales.order_lines` |
| K01 | Consistencia | extended_price distinto de quantity × unit_price + tax_amount | ⛔ Cuarentena: no pasa a `stg_clean` | `sales.invoice_lines` |
| K02 | Consistencia | tax_amount distinto de quantity × unit_price × tax_rate / 100 | ⛔ Cuarentena: no pasa a `stg_clean` | `sales.invoice_lines` |
| K03 | Consistencia | Factura con fecha anterior a la de su pedido | ⚠️ Marcar: pasa con su marca | `sales.invoices` |
| O02 | Oportunidad | last_edited_when en el futuro | ⛔ Cuarentena: no pasa a `stg_clean` | todas |
| V01 | Validez | Cantidad menor o igual a cero | ⛔ Cuarentena: no pasa a `stg_clean` | `sales.order_lines`, `sales.invoice_lines` |
| V02 | Validez | Precio unitario nulo, cero o negativo | ⛔ Cuarentena: no pasa a `stg_clean` | `sales.invoice_lines` |
| V03 | Validez | Tasa de impuesto fuera del rango 0–100 % | ⛔ Cuarentena: no pasa a `stg_clean` | `sales.invoice_lines` |
| V04 | Validez | Utilidad negativa (venta bajo costo: problema de negocio, no de datos) | ⚠️ Marcar: pasa con su marca | `sales.invoice_lines` |
| U03 | Unicidad | Varias versiones de la misma clave natural en un lote | 🔁 Supervivencia: gana la última versión extraída; las demás quedan en `stg_raw` como historia | todas |

Parámetros:
- tolerancia de reloj de O02: `5 minutes`;
- atípicos A01 y A02: cantidad > 225 e importe > 3643.2, calculados como Q3 + 3·IQR en el perfilado.

## Condición exacta de cada control (SQL sobre la fila `r` del lote)

| Tabla | Código | Condición (verdadera = incumple) |
|---|---|---|
| `application.people` | O02 | `r.last_edited_when > r._extracted_at + interval '5 minutes'` |
| `application.countries` | O02 | `r.last_edited_when > r._extracted_at + interval '5 minutes'` |
| `application.state_provinces` | O02 | `r.last_edited_when > r._extracted_at + interval '5 minutes'` |
| `application.cities` | O02 | `r.last_edited_when > r._extracted_at + interval '5 minutes'` |
| `application.delivery_methods` | O02 | `r.last_edited_when > r._extracted_at + interval '5 minutes'` |
| `warehouse.colors` | O02 | `r.last_edited_when > r._extracted_at + interval '5 minutes'` |
| `warehouse.package_types` | O02 | `r.last_edited_when > r._extracted_at + interval '5 minutes'` |
| `warehouse.stock_groups` | O02 | `r.last_edited_when > r._extracted_at + interval '5 minutes'` |
| `warehouse.stock_items` | O02 | `r.last_edited_when > r._extracted_at + interval '5 minutes'` |
| `warehouse.stock_item_stock_groups` | O02 | `r.last_edited_when > r._extracted_at + interval '5 minutes'` |
| `warehouse.stock_item_stock_groups` | I08 | `NOT EXISTS (SELECT 1 FROM stg_clean.warehouse_stock_items p WHERE p.stock_item_id = r.stock_item_id)` |
| `warehouse.stock_item_stock_groups` | I09 | `NOT EXISTS (SELECT 1 FROM stg_clean.warehouse_stock_groups p WHERE p.stock_group_id = r.stock_group_id)` |
| `sales.buying_groups` | O02 | `r.last_edited_when > r._extracted_at + interval '5 minutes'` |
| `sales.customer_categories` | O02 | `r.last_edited_when > r._extracted_at + interval '5 minutes'` |
| `sales.customers` | O02 | `r.last_edited_when > r._extracted_at + interval '5 minutes'` |
| `sales.customers` | I10 | `NOT EXISTS (SELECT 1 FROM stg_clean.application_cities p WHERE p.city_id = r.delivery_city_id)` |
| `sales.orders` | O02 | `r.last_edited_when > r._extracted_at + interval '5 minutes'` |
| `sales.orders` | I11 | `NOT EXISTS (SELECT 1 FROM stg_clean.sales_customers p WHERE p.customer_id = r.customer_id)` |
| `sales.order_lines` | O02 | `r.last_edited_when > r._extracted_at + interval '5 minutes'` |
| `sales.order_lines` | V01 | `r.quantity <= 0` |
| `sales.order_lines` | I12 | `NOT EXISTS (SELECT 1 FROM stg_clean.sales_orders p WHERE p.order_id = r.order_id)` |
| `sales.invoices` | O02 | `r.last_edited_when > r._extracted_at + interval '5 minutes'` |
| `sales.invoices` | I11 | `NOT EXISTS (SELECT 1 FROM stg_clean.sales_customers p WHERE p.customer_id = r.customer_id)` |
| `sales.invoices` | K03 | `EXISTS (SELECT 1 FROM stg_clean.sales_orders o WHERE o.order_id = r.order_id AND r.invoice_date < o.order_date)` |
| `sales.invoice_lines` | O02 | `r.last_edited_when > r._extracted_at + interval '5 minutes'` |
| `sales.invoice_lines` | V01 | `r.quantity <= 0` |
| `sales.invoice_lines` | V02 | `r.unit_price IS NULL OR r.unit_price <= 0` |
| `sales.invoice_lines` | V03 | `r.tax_rate NOT BETWEEN 0 AND 100` |
| `sales.invoice_lines` | K01 | `r.extended_price <> r.quantity * r.unit_price + r.tax_amount` |
| `sales.invoice_lines` | K02 | `r.tax_amount <> round(r.quantity * r.unit_price * r.tax_rate / 100, 2)` |
| `sales.invoice_lines` | I02 | `NOT EXISTS (SELECT 1 FROM stg_clean.sales_invoices p WHERE p.invoice_id = r.invoice_id)` |
| `sales.invoice_lines` | I08 | `NOT EXISTS (SELECT 1 FROM stg_clean.warehouse_stock_items p WHERE p.stock_item_id = r.stock_item_id)` |
| `sales.invoice_lines` | V04 | `r.line_profit < 0` |
| `sales.invoice_lines` | A01 | `r.quantity > 225` |
| `sales.invoice_lines` | A02 | `r.extended_price > 3643.2` |

## Transformaciones (en cada lote)

| Transformación | Dónde | Regla |
|---|---|---|
| Limpieza de textos | `stg_clean` ([limpiar.py](../../etl/transformation/limpiar.py)) | Sin caracteres de control, espacios múltiples colapsados y sin espacios en los extremos |
| Descarte de releídos | `stg_raw → stg_clean` | Las filas idénticas a la versión vigente (traídas por la ventana de solapamiento) no se vuelven a escribir |
| Nulos | `stg_ready` | Según su causa: no aplica, desconocido, pendiente o error (diseño, sección 3.1); una medida nunca se reemplaza por cero |
| Integración y enriquecimiento | `stg_ready` (vistas) | Grano de la línea de factura, grupo principal del producto, geografía, venta neta, costo y utilidad |
| Miembro desconocido | `dw` | Un hecho sin dimensión recibe la clave −1 |
| Historia | `dw` | SCD Tipo 2 en cliente y producto (solo si cambia el hash de la fila) |
