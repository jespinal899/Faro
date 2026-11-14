# Perfil de datos — base operacional `wwi_oltp`

> Generado automáticamente por `database/scripts/perfilar_fuente.py`
> (2026-11-14 23:44 UTC). No editar a mano: regenerar.

## 1. Reglas de calidad

✅ cumple · ⚠️ la regla debería dar 0 casos y no los da · ℹ️ informativo (no es un error,
pero hay que considerarlo en el ETL o en el modelo).

**Reglas evaluadas:** 32 · **Con problemas:** 0

| Código | Dimensión | Regla | Casos | Total | % | Estado |
|---|---|---|---:|---:|---:|:---:|
| C01 | Completitud | Líneas de factura sin precio unitario | 0 | 228,265 | 0.00 % | ✅ |
| C02 | Completitud | Pedidos sin persona que los preparó (picked_by_person_id NULL) | 10,623 | 73,595 | 14.43 % | ℹ️ |
| C03 | Completitud | Facturas sin entrega confirmada | 84 | 70,510 | 0.12 % | ℹ️ |
| C04 | Completitud | Clientes sin límite de crédito definido | 402 | 663 | 60.63 % | ℹ️ |
| C05 | Completitud | Productos sin marca | 209 | 227 | 92.07 % | ℹ️ |
| U01 | Unicidad | Nombres de cliente repetidos | 0 | 663 | 0.00 % | ✅ |
| U02 | Unicidad | Nombres de producto repetidos | 0 | 227 | 0.00 % | ✅ |
| U03 | Unicidad | Mismo producto en más de una línea de la misma factura | 0 | 228,265 | 0.00 % | ✅ |
| V01 | Validez | Cantidad vendida menor o igual a cero | 0 | 228,265 | 0.00 % | ✅ |
| V02 | Validez | Precio unitario menor o igual a cero | 0 | 228,265 | 0.00 % | ✅ |
| V03 | Validez | Tasa de impuesto fuera del rango 0–100 % | 0 | 228,265 | 0.00 % | ✅ |
| V04 | Validez | Líneas con utilidad negativa (venta bajo costo: problema de negocio, no de datos) | 4,626 | 228,265 | 2.03 % | ℹ️ |
| V05 | Validez | Facturas que son notas de crédito | 0 | 70,510 | 0.00 % | ℹ️ |
| K01 | Consistencia | extended_price ≠ quantity × unit_price + tax_amount | 0 | 228,265 | 0.00 % | ✅ |
| K02 | Consistencia | tax_amount ≠ quantity × unit_price × tax_rate / 100 (redondeado a 2 decimales) | 0 | 228,265 | 0.00 % | ✅ |
| K03 | Consistencia | Factura con fecha anterior a la de su pedido | 0 | 70,510 | 0.00 % | ✅ |
| K04 | Consistencia | Entrega esperada anterior a la fecha del pedido | 0 | 73,595 | 0.00 % | ✅ |
| K05 | Consistencia | Entrega confirmada antes de la fecha de la factura | 0 | 70,426 | 0.00 % | ✅ |
| K06 | Consistencia | Cantidad preparada mayor que la pedida | 0 | 231,412 | 0.00 % | ✅ |
| K07 | Consistencia | Líneas de pedido preparadas parcialmente (faltó stock) | 3,147 | 231,412 | 1.36 % | ℹ️ |
| K08 | Consistencia | Factura con un 'cliente que paga' distinto al de la ficha del cliente | 0 | 70,510 | 0.00 % | ✅ |
| I01 | Integridad | Pedidos sin factura | 3,085 | 73,595 | 4.19 % | ℹ️ |
| I02 | Integridad | Facturas sin líneas | 0 | 70,510 | 0.00 % | ✅ |
| I03 | Integridad | Pedidos sin líneas | 0 | 73,595 | 0.00 % | ✅ |
| I04 | Integridad | Facturas sin pedido asociado (order_id NULL) | 0 | 70,510 | 0.00 % | ✅ |
| I05 | Integridad | Productos que pertenecen a MÁS de un grupo (riesgo de duplicar importes) | 133 | 227 | 58.59 % | ℹ️ |
| I06 | Integridad | Productos sin ningún grupo | 0 | 227 | 0.00 % | ✅ |
| I07 | Integridad | Productos que nunca se vendieron | 0 | 227 | 0.00 % | ℹ️ |
| O01 | Oportunidad | Días del período (lunes a sábado) sin ninguna factura | 0 | 1,069 | 0.00 % | ℹ️ |
| O02 | Oportunidad | Registros modificados con fecha futura (last_edited_when > ahora) | 0 | 228,265 | 0.00 % | ✅ |
| A01 | Atípicos | Líneas con cantidad atípica (> Q3 + 3·IQR) | 3,383 | 228,265 | 1.48 % | ℹ️ |
| A02 | Atípicos | Líneas con importe atípico (extended_price > Q3 + 3·IQR) | 8,039 | 228,265 | 3.52 % | ℹ️ |

## 2. Distribuciones

### Facturación por día de la semana

| n | dia | facturas |
|---|---|---|
| 1 | lunes | 13000 |
| 2 | martes | 13117 |
| 3 | miércoles | 12955 |
| 4 | jueves | 12853 |
| 5 | viernes | 12700 |
| 6 | sábado | 5885 |

### Percentiles de líneas de factura

| medida | p50 | p95 | p99 | maximo |
|---|---|---|---|---|
| quantity | 10.00 | 150.00 | 240.00 | 360.00 |
| extended_price | 264.50 | 2944.00 | 9660.00 | 21838.50 |

### Clientes y ventas por categoría de cliente

| categoria | clientes | ventas |
|---|---|---|
| Novelty Shop | 459 | 141,663,238 |
| Supermarket | 58 | 16,509,320 |
| Gift Store | 48 | 13,432,558 |
| Computer Store | 51 | 13,289,956 |
| Corporate | 47 | 13,148,367 |

### Continuidad mensual de la facturación

<details><summary>Ver tabla completa</summary>

| mes | facturas | dias_con_ventas | ventas |
|---|---|---|---|
| 2013-01 | 1639 | 27 | 4,335,973 |
| 2013-02 | 1120 | 24 | 3,193,305 |
| 2013-03 | 1624 | 26 | 4,451,082 |
| 2013-04 | 1636 | 26 | 4,668,548 |
| 2013-05 | 1727 | 27 | 5,080,661 |
| 2013-06 | 1624 | 25 | 4,679,392 |
| 2013-07 | 1824 | 27 | 5,039,033 |
| 2013-08 | 1486 | 27 | 4,020,390 |
| 2013-09 | 1539 | 25 | 4,345,898 |
| 2013-10 | 1546 | 27 | 4,315,500 |
| 2013-11 | 1494 | 26 | 4,252,082 |
| 2013-12 | 1508 | 26 | 4,181,409 |
| 2014-01 | 1719 | 27 | 4,677,669 |
| 2014-02 | 1476 | 24 | 3,990,741 |
| 2014-03 | 1538 | 26 | 4,441,219 |
| 2014-04 | 1670 | 26 | 4,709,520 |
| 2014-05 | 1811 | 27 | 5,279,236 |
| 2014-06 | 1800 | 25 | 4,906,641 |
| 2014-07 | 1925 | 27 | 5,504,247 |
| 2014-08 | 1572 | 26 | 4,698,314 |
| 2014-09 | 1580 | 26 | 4,465,415 |
| 2014-10 | 1831 | 27 | 5,104,487 |
| 2014-11 | 1549 | 25 | 4,621,813 |
| 2014-12 | 1832 | 27 | 5,019,616 |
| 2015-01 | 1749 | 27 | 5,061,955 |
| 2015-02 | 1661 | 24 | 4,824,618 |
| 2015-03 | 1821 | 26 | 5,207,352 |
| 2015-04 | 2020 | 26 | 5,834,255 |
| 2015-05 | 1857 | 26 | 5,152,841 |
| 2015-06 | 1878 | 26 | 5,193,217 |
| 2015-07 | 2166 | 27 | 5,929,023 |
| 2015-08 | 1642 | 26 | 4,528,888 |
| 2015-09 | 1970 | 26 | 5,361,991 |
| 2015-10 | 1880 | 27 | 5,165,857 |
| 2015-11 | 1743 | 25 | 4,702,590 |
| 2015-12 | 1863 | 27 | 5,127,634 |
| 2016-01 | 1844 | 26 | 5,103,948 |
| 2016-02 | 1655 | 25 | 4,596,535 |
| 2016-03 | 1887 | 27 | 5,330,251 |
| 2016-04 | 1856 | 26 | 5,236,063 |
| 2016-05 | 1948 | 26 | 5,704,233 |

</details>

## 3. Perfil por columna

Para texto, mínimo y máximo son longitudes; para booleanos, el máximo es la
cantidad de valores TRUE.

<details>
<summary><code>application.people</code></summary>

| Columna | Tipo | % nulos | Distintos | Mínimo | Máximo | Más frecuente |
|---|---|---|---|---|---|---|
| `person_id` | integer | 0.0 % | 1,111 | 1 | 3261 | (todos distintos) |
| `full_name` | character varying | 0.0 % | 1,111 | long. 5 | long. 29 | (todos distintos) |
| `preferred_name` | character varying | 0.0 % | 882 | long. 2 | long. 20 | `David` (5) |
| `is_employee` | boolean | 0.0 % | 2 |  | 19 TRUE | `false` (1,092) |
| `is_salesperson` | boolean | 0.0 % | 2 |  | 10 TRUE | `false` (1,101) |
| `last_edited_by` | integer | 0.0 % | 1 | 1 | 1 | `1` (1,111) |
| `last_edited_when` | timestamp with time zone | 0.0 % | 58 | 2013-01-01 00:00:00+00 | 2016-05-31 23:14:00+00 | `2013-01-01 00:00:00+00` (873) |

</details>

<details>
<summary><code>application.countries</code></summary>

| Columna | Tipo | % nulos | Distintos | Mínimo | Máximo | Más frecuente |
|---|---|---|---|---|---|---|
| `country_id` | integer | 0.0 % | 190 | 1 | 241 | (todos distintos) |
| `country_name` | character varying | 0.0 % | 190 | long. 4 | long. 21 | (todos distintos) |
| `formal_name` | character varying | 0.0 % | 190 | long. 5 | long. 52 | (todos distintos) |
| `iso_alpha3_code` | character varying | 0.0 % | 190 | long. 3 | long. 3 | (todos distintos) |
| `iso_numeric_code` | integer | 0.0 % | 190 | 4 | 894 | (todos distintos) |
| `country_type` | character varying | 0.0 % | 1 | long. 15 | long. 15 | `UN Member State` (190) |
| `latest_recorded_population` | bigint | 0.0 % | 190 | 14019 | 1392157488 | (todos distintos) |
| `continent` | character varying | 0.0 % | 7 | long. 4 | long. 23 | `Africa` (50) |
| `region` | character varying | 0.0 % | 5 | long. 4 | long. 8 | `Africa` (52) |
| `subregion` | character varying | 0.0 % | 22 | long. 9 | long. 25 | `Eastern Africa` (17) |
| `last_edited_by` | integer | 0.0 % | 4 | 1 | 20 | `1` (155) |
| `last_edited_when` | timestamp with time zone | 0.0 % | 5 | 2013-01-01 00:00:00+00 | 2022-10-07 22:01:58.622602+00 | `2013-01-01 00:00:00+00` (154) |

</details>

<details>
<summary><code>application.state_provinces</code></summary>

| Columna | Tipo | % nulos | Distintos | Mínimo | Máximo | Más frecuente |
|---|---|---|---|---|---|---|
| `state_province_id` | integer | 0.0 % | 53 | 1 | 53 | (todos distintos) |
| `state_province_code` | character varying | 0.0 % | 53 | long. 2 | long. 2 | (todos distintos) |
| `state_province_name` | character varying | 0.0 % | 53 | long. 4 | long. 29 | (todos distintos) |
| `country_id` | integer | 0.0 % | 1 | 230 | 230 | `230` (53) |
| `sales_territory` | character varying | 0.0 % | 9 | long. 6 | long. 14 | `Southeast` (12) |
| `latest_recorded_population` | bigint | 0.0 % | 53 | 104737 | 41460453 | (todos distintos) |
| `last_edited_by` | integer | 0.0 % | 4 | 1 | 20 | `1` (19) |
| `last_edited_when` | timestamp with time zone | 0.0 % | 9 | 2013-01-01 00:00:00+00 | 2015-07-01 16:00:00+00 | `2014-07-01 16:00:00+00` (15) |

</details>

<details>
<summary><code>application.cities</code></summary>

| Columna | Tipo | % nulos | Distintos | Mínimo | Máximo | Más frecuente |
|---|---|---|---|---|---|---|
| `city_id` | integer | 0.0 % | 37,940 | 1 | 38186 | (todos distintos) |
| `city_name` | character varying | 0.0 % | 23,279 | long. 3 | long. 35 | `Franklin` (32) |
| `state_province_id` | integer | 0.0 % | 53 | 1 | 53 | `45` (2,395) |
| `latitude` | double precision | 0.0 % | 37,895 | 17.7124746 | 71.2905556 | `18.2185674` (3) |
| `longitude` | double precision | 0.0 % | 37,920 | -176.6580556 | 178.8775 | `-120.2971776` (2) |
| `latest_recorded_population` | bigint | 29.1 % | 9,324 | 0 | 8175133 | `112` (37) |
| `last_edited_by` | integer | 0.0 % | 4 | 1 | 20 | `1` (37,912) |
| `last_edited_when` | timestamp with time zone | 0.0 % | 4 | 2013-01-01 00:00:00+00 | 2015-07-01 16:00:00+00 | `2013-01-01 00:00:00+00` (37,912) |

</details>

<details>
<summary><code>application.delivery_methods</code></summary>

| Columna | Tipo | % nulos | Distintos | Mínimo | Máximo | Más frecuente |
|---|---|---|---|---|---|---|
| `delivery_method_id` | integer | 0.0 % | 10 | 1 | 10 | (todos distintos) |
| `delivery_method_name` | character varying | 0.0 % | 10 | long. 4 | long. 27 | (todos distintos) |
| `last_edited_by` | integer | 0.0 % | 2 | 1 | 16 | `1` (9) |
| `last_edited_when` | timestamp with time zone | 0.0 % | 2 | 2013-01-01 00:00:00+00 | 2015-01-01 16:00:00+00 | `2013-01-01 00:00:00+00` (9) |

</details>

<details>
<summary><code>warehouse.colors</code></summary>

| Columna | Tipo | % nulos | Distintos | Mínimo | Máximo | Más frecuente |
|---|---|---|---|---|---|---|
| `color_id` | integer | 0.0 % | 36 | 1 | 36 | (todos distintos) |
| `color_name` | character varying | 0.0 % | 36 | long. 3 | long. 11 | (todos distintos) |
| `last_edited_by` | integer | 0.0 % | 2 | 1 | 9 | `1` (35) |
| `last_edited_when` | timestamp with time zone | 0.0 % | 2 | 2013-01-01 00:00:00+00 | 2016-01-01 16:00:00+00 | `2013-01-01 00:00:00+00` (35) |

</details>

<details>
<summary><code>warehouse.package_types</code></summary>

| Columna | Tipo | % nulos | Distintos | Mínimo | Máximo | Más frecuente |
|---|---|---|---|---|---|---|
| `package_type_id` | integer | 0.0 % | 14 | 1 | 14 | (todos distintos) |
| `package_type_name` | character varying | 0.0 % | 14 | long. 2 | long. 6 | (todos distintos) |
| `last_edited_by` | integer | 0.0 % | 1 | 1 | 1 | `1` (14) |
| `last_edited_when` | timestamp with time zone | 0.0 % | 1 | 2013-01-01 00:00:00+00 | 2013-01-01 00:00:00+00 | `2013-01-01 00:00:00+00` (14) |

</details>

<details>
<summary><code>warehouse.stock_groups</code></summary>

| Columna | Tipo | % nulos | Distintos | Mínimo | Máximo | Más frecuente |
|---|---|---|---|---|---|---|
| `stock_group_id` | integer | 0.0 % | 10 | 1 | 10 | (todos distintos) |
| `stock_group_name` | character varying | 0.0 % | 10 | long. 4 | long. 19 | (todos distintos) |
| `last_edited_by` | integer | 0.0 % | 2 | 1 | 9 | `1` (9) |
| `last_edited_when` | timestamp with time zone | 0.0 % | 2 | 2013-01-01 00:00:00+00 | 2016-01-01 16:00:00+00 | `2013-01-01 00:00:00+00` (9) |

</details>

<details>
<summary><code>warehouse.stock_items</code></summary>

| Columna | Tipo | % nulos | Distintos | Mínimo | Máximo | Más frecuente |
|---|---|---|---|---|---|---|
| `stock_item_id` | integer | 0.0 % | 227 | 1 | 227 | (todos distintos) |
| `stock_item_name` | character varying | 0.0 % | 227 | long. 20 | long. 85 | (todos distintos) |
| `color_id` | integer | 43.6 % | 7 | 3 | 36 | `3` (51) |
| `unit_package_id` | integer | 0.0 % | 4 | 1 | 10 | `7` (210) |
| `outer_package_id` | integer | 0.0 % | 3 | 6 | 9 | `7` (175) |
| `brand` | character varying | 92.1 % | 1 | long. 9 | long. 9 | `Northwind` (18) |
| `size` | character varying | 28.2 % | 43 | long. 1 | long. 13 | `XL` (12) |
| `lead_time_days` | integer | 0.0 % | 6 | 2 | 20 | `14` (96) |
| `quantity_per_outer` | integer | 0.0 % | 9 | 1 | 36 | `1` (119) |
| `is_chiller_stock` | boolean | 0.0 % | 2 |  | 8 TRUE | `false` (219) |
| `tax_rate` | numeric | 0.0 % | 2 | 10.000 | 15.000 | `15.000` (219) |
| `unit_price` | numeric | 0.0 % | 57 | 0.66 | 1899.00 | `13.00` (42) |
| `recommended_retail_price` | numeric | 0.0 % | 57 | 0.99 | 2839.01 | `19.44` (42) |
| `typical_weight_per_unit` | numeric | 0.0 % | 23 | 0.050 | 21.000 | `0.150` (42) |
| `last_edited_by` | integer | 0.0 % | 1 | 1 | 1 | `1` (227) |
| `last_edited_when` | timestamp with time zone | 0.0 % | 10 | 2016-05-31 23:00:00+00 | 2016-05-31 23:12:00+00 | `2016-05-31 23:12:00+00` (67) |

</details>

<details>
<summary><code>warehouse.stock_item_stock_groups</code></summary>

| Columna | Tipo | % nulos | Distintos | Mínimo | Máximo | Más frecuente |
|---|---|---|---|---|---|---|
| `stock_item_stock_group_id` | integer | 0.0 % | 442 | 1 | 442 | (todos distintos) |
| `stock_item_id` | integer | 0.0 % | 227 | 1 | 227 | `1` (3) |
| `stock_group_id` | integer | 0.0 % | 9 | 1 | 10 | `1` (91) |
| `last_edited_by` | integer | 0.0 % | 1 | 1 | 1 | `1` (442) |
| `last_edited_when` | timestamp with time zone | 0.0 % | 5 | 2013-01-01 00:00:00+00 | 2016-01-05 00:00:00+00 | `2013-01-01 00:00:00+00` (434) |

</details>

<details>
<summary><code>sales.buying_groups</code></summary>

| Columna | Tipo | % nulos | Distintos | Mínimo | Máximo | Más frecuente |
|---|---|---|---|---|---|---|
| `buying_group_id` | integer | 0.0 % | 2 | 1 | 2 | (todos distintos) |
| `buying_group_name` | character varying | 0.0 % | 2 | long. 12 | long. 13 | (todos distintos) |
| `last_edited_by` | integer | 0.0 % | 1 | 1 | 1 | `1` (2) |
| `last_edited_when` | timestamp with time zone | 0.0 % | 1 | 2013-01-01 00:00:00+00 | 2013-01-01 00:00:00+00 | `2013-01-01 00:00:00+00` (2) |

</details>

<details>
<summary><code>sales.customer_categories</code></summary>

| Columna | Tipo | % nulos | Distintos | Mínimo | Máximo | Más frecuente |
|---|---|---|---|---|---|---|
| `customer_category_id` | integer | 0.0 % | 8 | 1 | 8 | (todos distintos) |
| `customer_category_name` | character varying | 0.0 % | 8 | long. 5 | long. 16 | (todos distintos) |
| `last_edited_by` | integer | 0.0 % | 2 | 1 | 9 | `1` (7) |
| `last_edited_when` | timestamp with time zone | 0.0 % | 2 | 2013-01-01 00:00:00+00 | 2014-01-01 16:15:00+00 | `2013-01-01 00:00:00+00` (7) |

</details>

<details>
<summary><code>sales.customers</code></summary>

| Columna | Tipo | % nulos | Distintos | Mínimo | Máximo | Más frecuente |
|---|---|---|---|---|---|---|
| `customer_id` | integer | 0.0 % | 663 | 1 | 1061 | (todos distintos) |
| `customer_name` | character varying | 0.0 % | 663 | long. 6 | long. 38 | (todos distintos) |
| `bill_to_customer_id` | integer | 0.0 % | 263 | 1 | 1061 | `1` (201) |
| `customer_category_id` | integer | 0.0 % | 5 | 3 | 7 | `3` (459) |
| `buying_group_id` | integer | 39.4 % | 2 | 1 | 2 | `1` (201) |
| `primary_contact_person_id` | integer | 0.0 % | 663 | 1001 | 3261 | (todos distintos) |
| `alternate_contact_person_id` | integer | 39.4 % | 402 | 1002 | 2402 | (todos distintos) |
| `delivery_method_id` | integer | 0.0 % | 1 | 3 | 3 | `3` (663) |
| `delivery_city_id` | integer | 0.0 % | 655 | 15 | 38184 | `16702` (2) |
| `postal_city_id` | integer | 0.0 % | 655 | 15 | 38184 | `16702` (2) |
| `credit_limit` | numeric | 60.6 % | 56 | 1100.00 | 4630.50 | `3300.00` (17) |
| `account_opened_date` | date | 0.0 % | 62 | 2013-01-01 | 2016-05-07 | `2013-01-01` (602) |
| `standard_discount_percentage` | numeric | 0.0 % | 1 | 0.000 | 0.000 | `0.000` (663) |
| `is_statement_sent` | boolean | 0.0 % | 1 |  | 0 TRUE | `false` (663) |
| `is_on_credit_hold` | boolean | 0.0 % | 1 |  | 0 TRUE | `false` (663) |
| `payment_days` | integer | 0.0 % | 1 | 7 | 7 | `7` (663) |
| `delivery_postal_code` | character varying | 0.0 % | 453 | long. 5 | long. 5 | `90683` (5) |
| `delivery_latitude` | double precision | 0.0 % | 655 | 17.9941326 | 65.2097222 | `18.0819088` (2) |
| `delivery_longitude` | double precision | 0.0 % | 655 | -166.2080556 | -65.797939 | `-107.113103` (2) |
| `last_edited_by` | integer | 0.0 % | 4 | 1 | 20 | `1` (617) |
| `last_edited_when` | timestamp with time zone | 0.0 % | 58 | 2013-01-01 00:00:00+00 | 2016-05-07 00:00:00+00 | `2013-01-01 00:00:00+00` (563) |

</details>

<details>
<summary><code>sales.orders</code></summary>

| Columna | Tipo | % nulos | Distintos | Mínimo | Máximo | Más frecuente |
|---|---|---|---|---|---|---|
| `order_id` | integer | 0.0 % | 73,595 | 1 | 73595 | (todos distintos) |
| `customer_id` | integer | 0.0 % | 663 | 1 | 1061 | `90` (150) |
| `salesperson_person_id` | integer | 0.0 % | 10 | 2 | 20 | `16` (7,532) |
| `picked_by_person_id` | integer | 14.4 % | 19 | 2 | 20 | `7` (4,042) |
| `contact_person_id` | integer | 0.0 % | 663 | 1001 | 3261 | `1179` (150) |
| `backorder_order_id` | integer | 89.8 % | 7,538 | 45 | 73595 | (todos distintos) |
| `order_date` | date | 0.0 % | 1,069 | 2013-01-01 | 2016-05-31 | `2016-01-06` (133) |
| `expected_delivery_date` | date | 0.0 % | 891 | 2013-01-02 | 2016-06-01 | `2015-03-02` (173) |
| `customer_purchase_order_number` | character varying | 0.0 % | 9,984 | long. 5 | long. 5 | `10776` (22) |
| `is_undersupply_backordered` | boolean | 0.0 % | 1 |  | 73595 TRUE | `true` (73,595) |
| `picking_completed_when` | timestamp with time zone | 4.2 % | 2,124 | 2013-01-01 11:00:00+00 | 2016-05-31 12:00:00+00 | `2016-02-26 11:00:00+00` (107) |
| `last_edited_by` | integer | 0.0 % | 20 | 1 | 20 | `7` (4,633) |
| `last_edited_when` | timestamp with time zone | 0.0 % | 2,129 | 2013-01-01 11:00:00+00 | 2016-05-31 12:00:00+00 | `2016-02-26 11:00:00+00` (107) |

</details>

<details>
<summary><code>sales.order_lines</code></summary>

| Columna | Tipo | % nulos | Distintos | Mínimo | Máximo | Más frecuente |
|---|---|---|---|---|---|---|
| `order_line_id` | integer | 0.0 % | 231,412 | 1 | 231412 | (todos distintos) |
| `order_id` | integer | 0.0 % | 73,595 | 1 | 73595 | `10000` (5) |
| `stock_item_id` | integer | 0.0 % | 227 | 1 | 227 | `104` (1,123) |
| `description` | character varying | 0.0 % | 227 | long. 20 | long. 85 | `Alien officer hoodie (Black...` (1,123) |
| `package_type_id` | integer | 0.0 % | 4 | 1 | 10 | `7` (220,955) |
| `quantity` | integer | 0.0 % | 61 | 1 | 360 | `10` (15,799) |
| `unit_price` | numeric | 0.0 % | 62 | 0.66 | 1899.00 | `13.00` (44,577) |
| `tax_rate` | numeric | 0.0 % | 2 | 10.000 | 15.000 | `15.000` (230,376) |
| `picked_quantity` | integer | 0.0 % | 62 | 0 | 360 | `10` (15,799) |
| `picking_completed_when` | timestamp with time zone | 1.4 % | 1,069 | 2013-01-01 11:00:00+00 | 2016-05-31 11:00:00+00 | `2016-05-04 11:00:00+00` (395) |
| `last_edited_by` | integer | 0.0 % | 20 | 1 | 20 | `7` (14,952) |
| `last_edited_when` | timestamp with time zone | 0.0 % | 1,970 | 2013-01-01 11:00:00+00 | 2016-05-31 12:00:00+00 | `2016-05-04 11:00:00+00` (395) |

</details>

<details>
<summary><code>sales.invoices</code></summary>

| Columna | Tipo | % nulos | Distintos | Mínimo | Máximo | Más frecuente |
|---|---|---|---|---|---|---|
| `invoice_id` | integer | 0.0 % | 70,510 | 1 | 70510 | (todos distintos) |
| `customer_id` | integer | 0.0 % | 663 | 1 | 1061 | `831` (144) |
| `bill_to_customer_id` | integer | 0.0 % | 263 | 1 | 1061 | `1` (22,316) |
| `order_id` | integer | 0.0 % | 70,510 | 1 | 73586 | (todos distintos) |
| `delivery_method_id` | integer | 0.0 % | 1 | 3 | 3 | `3` (70,510) |
| `contact_person_id` | integer | 0.0 % | 663 | 1001 | 3261 | `3031` (144) |
| `accounts_person_id` | integer | 0.0 % | 263 | 1001 | 3261 | `1001` (22,316) |
| `salesperson_person_id` | integer | 0.0 % | 10 | 2 | 20 | `16` (7,184) |
| `packed_by_person_id` | integer | 0.0 % | 19 | 2 | 20 | `15` (4,817) |
| `invoice_date` | date | 0.0 % | 1,069 | 2013-01-01 | 2016-05-31 | `2016-01-06` (117) |
| `customer_purchase_order_number` | character varying | 0.0 % | 9,984 | long. 5 | long. 5 | `10776` (21) |
| `is_credit_note` | boolean | 0.0 % | 1 |  | 0 TRUE | `false` (70,510) |
| `credit_note_reason` | text | 100.0 % | 0 |  |  |  |
| `total_dry_items` | integer | 0.0 % | 6 | 0 | 5 | `3` (17,179) |
| `total_chiller_items` | integer | 0.0 % | 4 | 0 | 3 | `0` (69,519) |
| `confirmed_delivery_time` | timestamp with time zone | 0.1 % | 70,426 | 2013-01-02 07:05:00+00 | 2016-05-31 13:30:00+00 | (todos distintos) |
| `last_edited_by` | integer | 0.0 % | 19 | 2 | 20 | `2` (4,652) |
| `last_edited_when` | timestamp with time zone | 0.0 % | 1,069 | 2013-01-02 07:00:00+00 | 2016-05-31 12:00:00+00 | `2016-01-07 07:00:00+00` (117) |

</details>

<details>
<summary><code>sales.invoice_lines</code></summary>

| Columna | Tipo | % nulos | Distintos | Mínimo | Máximo | Más frecuente |
|---|---|---|---|---|---|---|
| `invoice_line_id` | integer | 0.0 % | 228,265 | 1 | 228265 | (todos distintos) |
| `invoice_id` | integer | 0.0 % | 70,510 | 1 | 70510 | `10005` (5) |
| `stock_item_id` | integer | 0.0 % | 227 | 1 | 227 | `104` (1,123) |
| `description` | character varying | 0.0 % | 227 | long. 20 | long. 85 | `Alien officer hoodie (Black...` (1,123) |
| `package_type_id` | integer | 0.0 % | 4 | 1 | 10 | `7` (217,808) |
| `quantity` | integer | 0.0 % | 61 | 1 | 360 | `10` (15,799) |
| `unit_price` | numeric | 0.0 % | 62 | 0.66 | 1899.00 | `13.00` (44,577) |
| `tax_rate` | numeric | 0.0 % | 2 | 10.000 | 15.000 | `15.000` (227,229) |
| `tax_amount` | numeric | 0.0 % | 493 | 0.38 | 2848.50 | `13.65` (4,613) |
| `line_profit` | numeric | 0.0 % | 570 | -645.00 | 9200.00 | `85.00` (5,056) |
| `extended_price` | numeric | 0.0 % | 497 | 2.88 | 21838.50 | `104.65` (4,613) |
| `last_edited_by` | integer | 0.0 % | 19 | 2 | 20 | `4` (14,674) |
| `last_edited_when` | timestamp with time zone | 0.0 % | 1,069 | 2013-01-01 12:00:00+00 | 2016-05-31 12:00:00+00 | `2016-05-04 12:00:00+00` (395) |

</details>
