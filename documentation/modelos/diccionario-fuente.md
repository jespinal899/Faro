# Diccionario de datos — base operacional `wwi_oltp`

> Generado automáticamente por `database/scripts/documentar_fuente.py` desde la base
> real (2026-11-14 23:39 UTC). No editar a mano: regenerar.

**Fuente original:** WideWorldImporters (SQL Server), módulo de ventas.
**Tablas:** 17 · **Filas:** 644,488

## Convenciones

- **Clave:** `PK` = clave primaria · `FK` = clave foránea · `UQ` = valor único.
- **Nulo:** ✔ = admite NULL.
- **Origen:** columna de SQL Server de la que proviene el dato (linaje).
- Todas las tablas tienen `last_edited_by` (quién modificó) y `last_edited_when`
  (cuándo, en UTC). `last_edited_when` es la marca de agua de la carga incremental
  y la actualiza un trigger en cada UPDATE.
- Por minimización de datos personales no se migraron contraseñas, fotos, correos,
  teléfonos, direcciones ni comentarios de texto libre.

## Tablas

| Tabla | Filas | Descripción |
|---|---:|---|
| [`application.people`](#applicationpeople) | 1,111 | Personas: empleados (incluidos vendedores) y contactos de clientes. Solo datos no sensibles. |
| [`application.countries`](#applicationcountries) | 190 | Países. |
| [`application.state_provinces`](#applicationstate_provinces) | 53 | Estados/provincias, con su territorio de ventas. |
| [`application.cities`](#applicationcities) | 37,940 | Ciudades. latitude/longitude provienen del tipo geography (Location) de SQL Server. |
| [`application.delivery_methods`](#applicationdelivery_methods) | 10 | Métodos de entrega. |
| [`warehouse.colors`](#warehousecolors) | 36 | Colores de producto. |
| [`warehouse.package_types`](#warehousepackage_types) | 14 | Tipos de empaque (unidad de venta). |
| [`warehouse.stock_groups`](#warehousestock_groups) | 10 | Grupos (categorías) de producto. |
| [`warehouse.stock_items`](#warehousestock_items) | 227 | Productos (artículos de inventario) que se venden. |
| [`warehouse.stock_item_stock_groups`](#warehousestock_item_stock_groups) | 442 | Relación MUCHOS a MUCHOS producto-grupo: un producto puede estar en varios grupos. |
| [`sales.buying_groups`](#salesbuying_groups) | 2 | Grupos de compra (cadenas que agrupan clientes). |
| [`sales.customer_categories`](#salescustomer_categories) | 8 | Categorías de cliente (tipo de negocio). |
| [`sales.customers`](#salescustomers) | 663 | Clientes. Sin teléfonos, sitio web ni direcciones (minimización de datos). |
| [`sales.orders`](#salesorders) | 73,595 | Pedidos de clientes (encabezado). backorder_order_id enlaza pedidos pendientes por falta de stock. |
| [`sales.order_lines`](#salesorder_lines) | 231,412 | Líneas de pedido: un producto por línea. |
| [`sales.invoices`](#salesinvoices) | 70,510 | Facturas (encabezado). confirmed_delivery_time proviene del JSON de entrega de SQL Server. |
| [`sales.invoice_lines`](#salesinvoice_lines) | 228,265 | Líneas de factura: la VENTA realizada. extended_price incluye impuestos (neto = extended_price - tax_amount). |

## application.people

Personas: empleados (incluidos vendedores) y contactos de clientes. Solo datos no sensibles.

Origen: `Application.People` · Filas: 1,111

| Columna | Tipo | Nulo | Clave | Origen (SQL Server) | Descripción |
|---|---|:---:|---|---|---|
| `person_id` | integer |  | PK | `Application.People.PersonID` |  |
| `full_name` | character varying(50) |  |  | `Application.People.FullName` |  |
| `preferred_name` | character varying(50) |  |  | `Application.People.PreferredName` | Nombre corto con el que se conoce a la persona. |
| `is_employee` | boolean |  |  | `Application.People.IsEmployee` |  |
| `is_salesperson` | boolean |  |  | `Application.People.IsSalesperson` | TRUE si la persona es vendedor (aparece como salesperson en pedidos/facturas). |
| `last_edited_by` | integer |  | FK → `application.people.person_id` | `Application.People.LastEditedBy` | Persona que hizo la última modificación (auditoría). |
| `last_edited_when` | timestamp with time zone |  |  | `Application.People.ValidFrom` | Fecha/hora (UTC) de la última modificación. Se usa como marca de agua (watermark) en la carga incremental. |

## application.countries

Países.

Origen: `Application.Countries` · Filas: 190

| Columna | Tipo | Nulo | Clave | Origen (SQL Server) | Descripción |
|---|---|:---:|---|---|---|
| `country_id` | integer |  | PK | `Application.Countries.CountryID` |  |
| `country_name` | character varying(60) |  |  | `Application.Countries.CountryName` |  |
| `formal_name` | character varying(60) |  |  | `Application.Countries.FormalName` |  |
| `iso_alpha3_code` | character varying(3) | ✔ |  | `Application.Countries.IsoAlpha3Code` |  |
| `iso_numeric_code` | integer | ✔ |  | `Application.Countries.IsoNumericCode` |  |
| `country_type` | character varying(20) | ✔ |  | `Application.Countries.CountryType` |  |
| `latest_recorded_population` | bigint | ✔ |  | `Application.Countries.LatestRecordedPopulation` |  |
| `continent` | character varying(30) |  |  | `Application.Countries.Continent` |  |
| `region` | character varying(30) |  |  | `Application.Countries.Region` |  |
| `subregion` | character varying(30) |  |  | `Application.Countries.Subregion` |  |
| `last_edited_by` | integer |  | FK → `application.people.person_id` | `Application.Countries.LastEditedBy` | Persona que hizo la última modificación (auditoría). |
| `last_edited_when` | timestamp with time zone |  |  | `Application.Countries.ValidFrom` | Fecha/hora (UTC) de la última modificación. Se usa como marca de agua (watermark) en la carga incremental. |

## application.state_provinces

Estados/provincias, con su territorio de ventas.

Origen: `Application.StateProvinces` · Filas: 53

| Columna | Tipo | Nulo | Clave | Origen (SQL Server) | Descripción |
|---|---|:---:|---|---|---|
| `state_province_id` | integer |  | PK | `Application.StateProvinces.StateProvinceID` |  |
| `state_province_code` | character varying(5) |  |  | `Application.StateProvinces.StateProvinceCode` |  |
| `state_province_name` | character varying(50) |  |  | `Application.StateProvinces.StateProvinceName` |  |
| `country_id` | integer |  | FK → `application.countries.country_id` | `Application.StateProvinces.CountryID` |  |
| `sales_territory` | character varying(50) |  |  | `Application.StateProvinces.SalesTerritory` | Territorio comercial al que pertenece el estado (agrupación de ventas). |
| `latest_recorded_population` | bigint | ✔ |  | `Application.StateProvinces.LatestRecordedPopulation` |  |
| `last_edited_by` | integer |  | FK → `application.people.person_id` | `Application.StateProvinces.LastEditedBy` | Persona que hizo la última modificación (auditoría). |
| `last_edited_when` | timestamp with time zone |  |  | `Application.StateProvinces.ValidFrom` | Fecha/hora (UTC) de la última modificación. Se usa como marca de agua (watermark) en la carga incremental. |

## application.cities

Ciudades. latitude/longitude provienen del tipo geography (Location) de SQL Server.

Origen: `Application.Cities` · Filas: 37,940

| Columna | Tipo | Nulo | Clave | Origen (SQL Server) | Descripción |
|---|---|:---:|---|---|---|
| `city_id` | integer |  | PK | `Application.Cities.CityID` |  |
| `city_name` | character varying(50) |  |  | `Application.Cities.CityName` |  |
| `state_province_id` | integer |  | FK → `application.state_provinces.state_province_id` | `Application.Cities.StateProvinceID` |  |
| `latitude` | double precision | ✔ |  | `Application.Cities.Location.Lat` |  |
| `longitude` | double precision | ✔ |  | `Application.Cities.Location.Long` |  |
| `latest_recorded_population` | bigint | ✔ |  | `Application.Cities.LatestRecordedPopulation` | Última población registrada de la ciudad. |
| `last_edited_by` | integer |  | FK → `application.people.person_id` | `Application.Cities.LastEditedBy` | Persona que hizo la última modificación (auditoría). |
| `last_edited_when` | timestamp with time zone |  |  | `Application.Cities.ValidFrom` | Fecha/hora (UTC) de la última modificación. Se usa como marca de agua (watermark) en la carga incremental. |

## application.delivery_methods

Métodos de entrega.

Origen: `Application.DeliveryMethods` · Filas: 10

| Columna | Tipo | Nulo | Clave | Origen (SQL Server) | Descripción |
|---|---|:---:|---|---|---|
| `delivery_method_id` | integer |  | PK | `Application.DeliveryMethods.DeliveryMethodID` |  |
| `delivery_method_name` | character varying(50) |  |  | `Application.DeliveryMethods.DeliveryMethodName` |  |
| `last_edited_by` | integer |  | FK → `application.people.person_id` | `Application.DeliveryMethods.LastEditedBy` | Persona que hizo la última modificación (auditoría). |
| `last_edited_when` | timestamp with time zone |  |  | `Application.DeliveryMethods.ValidFrom` | Fecha/hora (UTC) de la última modificación. Se usa como marca de agua (watermark) en la carga incremental. |

## warehouse.colors

Colores de producto.

Origen: `Warehouse.Colors` · Filas: 36

| Columna | Tipo | Nulo | Clave | Origen (SQL Server) | Descripción |
|---|---|:---:|---|---|---|
| `color_id` | integer |  | PK | `Warehouse.Colors.ColorID` |  |
| `color_name` | character varying(20) |  |  | `Warehouse.Colors.ColorName` |  |
| `last_edited_by` | integer |  | FK → `application.people.person_id` | `Warehouse.Colors.LastEditedBy` | Persona que hizo la última modificación (auditoría). |
| `last_edited_when` | timestamp with time zone |  |  | `Warehouse.Colors.ValidFrom` | Fecha/hora (UTC) de la última modificación. Se usa como marca de agua (watermark) en la carga incremental. |

## warehouse.package_types

Tipos de empaque (unidad de venta).

Origen: `Warehouse.PackageTypes` · Filas: 14

| Columna | Tipo | Nulo | Clave | Origen (SQL Server) | Descripción |
|---|---|:---:|---|---|---|
| `package_type_id` | integer |  | PK | `Warehouse.PackageTypes.PackageTypeID` |  |
| `package_type_name` | character varying(50) |  |  | `Warehouse.PackageTypes.PackageTypeName` |  |
| `last_edited_by` | integer |  | FK → `application.people.person_id` | `Warehouse.PackageTypes.LastEditedBy` | Persona que hizo la última modificación (auditoría). |
| `last_edited_when` | timestamp with time zone |  |  | `Warehouse.PackageTypes.ValidFrom` | Fecha/hora (UTC) de la última modificación. Se usa como marca de agua (watermark) en la carga incremental. |

## warehouse.stock_groups

Grupos (categorías) de producto.

Origen: `Warehouse.StockGroups` · Filas: 10

| Columna | Tipo | Nulo | Clave | Origen (SQL Server) | Descripción |
|---|---|:---:|---|---|---|
| `stock_group_id` | integer |  | PK | `Warehouse.StockGroups.StockGroupID` |  |
| `stock_group_name` | character varying(50) |  |  | `Warehouse.StockGroups.StockGroupName` |  |
| `last_edited_by` | integer |  | FK → `application.people.person_id` | `Warehouse.StockGroups.LastEditedBy` | Persona que hizo la última modificación (auditoría). |
| `last_edited_when` | timestamp with time zone |  |  | `Warehouse.StockGroups.ValidFrom` | Fecha/hora (UTC) de la última modificación. Se usa como marca de agua (watermark) en la carga incremental. |

## warehouse.stock_items

Productos (artículos de inventario) que se venden.

Origen: `Warehouse.StockItems` · Filas: 227

| Columna | Tipo | Nulo | Clave | Origen (SQL Server) | Descripción |
|---|---|:---:|---|---|---|
| `stock_item_id` | integer |  | PK | `Warehouse.StockItems.StockItemID` |  |
| `stock_item_name` | character varying(100) |  |  | `Warehouse.StockItems.StockItemName` |  |
| `color_id` | integer | ✔ | FK → `warehouse.colors.color_id` | `Warehouse.StockItems.ColorID` |  |
| `unit_package_id` | integer |  | FK → `warehouse.package_types.package_type_id` | `Warehouse.StockItems.UnitPackageID` | Empaque en el que se vende una unidad. |
| `outer_package_id` | integer |  | FK → `warehouse.package_types.package_type_id` | `Warehouse.StockItems.OuterPackageID` | Empaque exterior (caja) en el que se despacha. |
| `brand` | character varying(50) | ✔ |  | `Warehouse.StockItems.Brand` |  |
| `size` | character varying(20) | ✔ |  | `Warehouse.StockItems.Size` |  |
| `lead_time_days` | integer |  |  | `Warehouse.StockItems.LeadTimeDays` | Días de reposición del proveedor. |
| `quantity_per_outer` | integer |  |  | `Warehouse.StockItems.QuantityPerOuter` | Unidades que contiene un empaque exterior. |
| `is_chiller_stock` | boolean |  |  | `Warehouse.StockItems.IsChillerStock` | TRUE si requiere refrigeración. |
| `tax_rate` | numeric(18,3) |  |  | `Warehouse.StockItems.TaxRate` | Tasa de impuesto en porcentaje (15.000 = 15 %). |
| `unit_price` | numeric(18,2) |  |  | `Warehouse.StockItems.UnitPrice` | Precio de lista vigente por unidad, sin impuestos. |
| `recommended_retail_price` | numeric(18,2) | ✔ |  | `Warehouse.StockItems.RecommendedRetailPrice` | Precio de venta al público sugerido. |
| `typical_weight_per_unit` | numeric(18,3) |  |  | `Warehouse.StockItems.TypicalWeightPerUnit` | Peso típico por unidad (kg). |
| `last_edited_by` | integer |  | FK → `application.people.person_id` | `Warehouse.StockItems.LastEditedBy` | Persona que hizo la última modificación (auditoría). |
| `last_edited_when` | timestamp with time zone |  |  | `Warehouse.StockItems.ValidFrom` | Fecha/hora (UTC) de la última modificación. Se usa como marca de agua (watermark) en la carga incremental. |

## warehouse.stock_item_stock_groups

Relación MUCHOS a MUCHOS producto-grupo: un producto puede estar en varios grupos.

Origen: `Warehouse.StockItemStockGroups` · Filas: 442

| Columna | Tipo | Nulo | Clave | Origen (SQL Server) | Descripción |
|---|---|:---:|---|---|---|
| `stock_item_stock_group_id` | integer |  | PK | `Warehouse.StockItemStockGroups.StockItemStockGroupID` |  |
| `stock_item_id` | integer |  | UQ, FK → `warehouse.stock_items.stock_item_id` | `Warehouse.StockItemStockGroups.StockItemID` |  |
| `stock_group_id` | integer |  | UQ, FK → `warehouse.stock_groups.stock_group_id` | `Warehouse.StockItemStockGroups.StockGroupID` |  |
| `last_edited_by` | integer |  | FK → `application.people.person_id` | `Warehouse.StockItemStockGroups.LastEditedBy` | Persona que hizo la última modificación (auditoría). |
| `last_edited_when` | timestamp with time zone |  |  | `Warehouse.StockItemStockGroups.LastEditedWhen` | Fecha/hora (UTC) de la última modificación. Se usa como marca de agua (watermark) en la carga incremental. |

## sales.buying_groups

Grupos de compra (cadenas que agrupan clientes).

Origen: `Sales.BuyingGroups` · Filas: 2

| Columna | Tipo | Nulo | Clave | Origen (SQL Server) | Descripción |
|---|---|:---:|---|---|---|
| `buying_group_id` | integer |  | PK | `Sales.BuyingGroups.BuyingGroupID` |  |
| `buying_group_name` | character varying(50) |  |  | `Sales.BuyingGroups.BuyingGroupName` |  |
| `last_edited_by` | integer |  | FK → `application.people.person_id` | `Sales.BuyingGroups.LastEditedBy` | Persona que hizo la última modificación (auditoría). |
| `last_edited_when` | timestamp with time zone |  |  | `Sales.BuyingGroups.ValidFrom` | Fecha/hora (UTC) de la última modificación. Se usa como marca de agua (watermark) en la carga incremental. |

## sales.customer_categories

Categorías de cliente (tipo de negocio).

Origen: `Sales.CustomerCategories` · Filas: 8

| Columna | Tipo | Nulo | Clave | Origen (SQL Server) | Descripción |
|---|---|:---:|---|---|---|
| `customer_category_id` | integer |  | PK | `Sales.CustomerCategories.CustomerCategoryID` |  |
| `customer_category_name` | character varying(50) |  |  | `Sales.CustomerCategories.CustomerCategoryName` |  |
| `last_edited_by` | integer |  | FK → `application.people.person_id` | `Sales.CustomerCategories.LastEditedBy` | Persona que hizo la última modificación (auditoría). |
| `last_edited_when` | timestamp with time zone |  |  | `Sales.CustomerCategories.ValidFrom` | Fecha/hora (UTC) de la última modificación. Se usa como marca de agua (watermark) en la carga incremental. |

## sales.customers

Clientes. Sin teléfonos, sitio web ni direcciones (minimización de datos).

Origen: `Sales.Customers` · Filas: 663

| Columna | Tipo | Nulo | Clave | Origen (SQL Server) | Descripción |
|---|---|:---:|---|---|---|
| `customer_id` | integer |  | PK | `Sales.Customers.CustomerID` |  |
| `customer_name` | character varying(100) |  |  | `Sales.Customers.CustomerName` |  |
| `bill_to_customer_id` | integer |  | FK → `sales.customers.customer_id` | `Sales.Customers.BillToCustomerID` | Cliente al que se factura (p. ej. la casa matriz de una cadena). Puede ser el mismo cliente. |
| `customer_category_id` | integer |  | FK → `sales.customer_categories.customer_category_id` | `Sales.Customers.CustomerCategoryID` |  |
| `buying_group_id` | integer | ✔ | FK → `sales.buying_groups.buying_group_id` | `Sales.Customers.BuyingGroupID` | Grupo de compra (cadena). NULL = cliente independiente. |
| `primary_contact_person_id` | integer |  | FK → `application.people.person_id` | `Sales.Customers.PrimaryContactPersonID` |  |
| `alternate_contact_person_id` | integer | ✔ | FK → `application.people.person_id` | `Sales.Customers.AlternateContactPersonID` |  |
| `delivery_method_id` | integer |  | FK → `application.delivery_methods.delivery_method_id` | `Sales.Customers.DeliveryMethodID` |  |
| `delivery_city_id` | integer |  | FK → `application.cities.city_id` | `Sales.Customers.DeliveryCityID` |  |
| `postal_city_id` | integer |  | FK → `application.cities.city_id` | `Sales.Customers.PostalCityID` |  |
| `credit_limit` | numeric(18,2) | ✔ |  | `Sales.Customers.CreditLimit` | Límite de crédito. NULL = sin límite definido. |
| `account_opened_date` | date |  |  | `Sales.Customers.AccountOpenedDate` | Fecha de apertura de la cuenta del cliente. |
| `standard_discount_percentage` | numeric(18,3) |  |  | `Sales.Customers.StandardDiscountPercentage` | Descuento estándar del cliente, en porcentaje. |
| `is_statement_sent` | boolean |  |  | `Sales.Customers.IsStatementSent` |  |
| `is_on_credit_hold` | boolean |  |  | `Sales.Customers.IsOnCreditHold` | TRUE si el crédito del cliente está suspendido. |
| `payment_days` | integer |  |  | `Sales.Customers.PaymentDays` | Días de plazo para pagar una factura. |
| `delivery_postal_code` | character varying(10) |  |  | `Sales.Customers.DeliveryPostalCode` |  |
| `delivery_latitude` | double precision | ✔ |  | `Sales.Customers.DeliveryLocation.Lat` |  |
| `delivery_longitude` | double precision | ✔ |  | `Sales.Customers.DeliveryLocation.Long` |  |
| `last_edited_by` | integer |  | FK → `application.people.person_id` | `Sales.Customers.LastEditedBy` | Persona que hizo la última modificación (auditoría). |
| `last_edited_when` | timestamp with time zone |  |  | `Sales.Customers.ValidFrom` | Fecha/hora (UTC) de la última modificación. Se usa como marca de agua (watermark) en la carga incremental. |

## sales.orders

Pedidos de clientes (encabezado). backorder_order_id enlaza pedidos pendientes por falta de stock.

Origen: `Sales.Orders` · Filas: 73,595

| Columna | Tipo | Nulo | Clave | Origen (SQL Server) | Descripción |
|---|---|:---:|---|---|---|
| `order_id` | integer |  | PK | `Sales.Orders.OrderID` |  |
| `customer_id` | integer |  | FK → `sales.customers.customer_id` | `Sales.Orders.CustomerID` |  |
| `salesperson_person_id` | integer |  | FK → `application.people.person_id` | `Sales.Orders.SalespersonPersonID` |  |
| `picked_by_person_id` | integer | ✔ | FK → `application.people.person_id` | `Sales.Orders.PickedByPersonID` |  |
| `contact_person_id` | integer |  | FK → `application.people.person_id` | `Sales.Orders.ContactPersonID` |  |
| `backorder_order_id` | integer | ✔ | FK → `sales.orders.order_id` | `Sales.Orders.BackorderOrderID` | Pedido pendiente generado cuando no hubo stock suficiente para este pedido. |
| `order_date` | date |  |  | `Sales.Orders.OrderDate` |  |
| `expected_delivery_date` | date |  |  | `Sales.Orders.ExpectedDeliveryDate` | Fecha de entrega comprometida con el cliente. |
| `customer_purchase_order_number` | character varying(20) | ✔ |  | `Sales.Orders.CustomerPurchaseOrderNumber` |  |
| `is_undersupply_backordered` | boolean |  |  | `Sales.Orders.IsUndersupplyBackordered` | TRUE si los faltantes de stock se convierten en un pedido pendiente. |
| `picking_completed_when` | timestamp with time zone | ✔ |  | `Sales.Orders.PickingCompletedWhen` | Momento en que se terminó de preparar (picking) el pedido. NULL = no preparado. |
| `last_edited_by` | integer |  | FK → `application.people.person_id` | `Sales.Orders.LastEditedBy` | Persona que hizo la última modificación (auditoría). |
| `last_edited_when` | timestamp with time zone |  |  | `Sales.Orders.LastEditedWhen` | Fecha/hora (UTC) de la última modificación. Se usa como marca de agua (watermark) en la carga incremental. |

## sales.order_lines

Líneas de pedido: un producto por línea.

Origen: `Sales.OrderLines` · Filas: 231,412

| Columna | Tipo | Nulo | Clave | Origen (SQL Server) | Descripción |
|---|---|:---:|---|---|---|
| `order_line_id` | integer |  | PK | `Sales.OrderLines.OrderLineID` |  |
| `order_id` | integer |  | FK → `sales.orders.order_id` | `Sales.OrderLines.OrderID` |  |
| `stock_item_id` | integer |  | FK → `warehouse.stock_items.stock_item_id` | `Sales.OrderLines.StockItemID` |  |
| `description` | character varying(100) |  |  | `Sales.OrderLines.Description` |  |
| `package_type_id` | integer |  | FK → `warehouse.package_types.package_type_id` | `Sales.OrderLines.PackageTypeID` |  |
| `quantity` | integer |  |  | `Sales.OrderLines.Quantity` |  |
| `unit_price` | numeric(18,2) | ✔ |  | `Sales.OrderLines.UnitPrice` | Precio unitario acordado, sin impuestos. |
| `tax_rate` | numeric(18,3) |  |  | `Sales.OrderLines.TaxRate` |  |
| `picked_quantity` | integer |  |  | `Sales.OrderLines.PickedQuantity` | Unidades efectivamente preparadas; puede ser menor que quantity si faltó stock. |
| `picking_completed_when` | timestamp with time zone | ✔ |  | `Sales.OrderLines.PickingCompletedWhen` |  |
| `last_edited_by` | integer |  | FK → `application.people.person_id` | `Sales.OrderLines.LastEditedBy` | Persona que hizo la última modificación (auditoría). |
| `last_edited_when` | timestamp with time zone |  |  | `Sales.OrderLines.LastEditedWhen` | Fecha/hora (UTC) de la última modificación. Se usa como marca de agua (watermark) en la carga incremental. |

## sales.invoices

Facturas (encabezado). confirmed_delivery_time proviene del JSON de entrega de SQL Server.

Origen: `Sales.Invoices` · Filas: 70,510

| Columna | Tipo | Nulo | Clave | Origen (SQL Server) | Descripción |
|---|---|:---:|---|---|---|
| `invoice_id` | integer |  | PK | `Sales.Invoices.InvoiceID` |  |
| `customer_id` | integer |  | FK → `sales.customers.customer_id` | `Sales.Invoices.CustomerID` |  |
| `bill_to_customer_id` | integer |  | FK → `sales.customers.customer_id` | `Sales.Invoices.BillToCustomerID` | Cliente que paga la factura (puede diferir del cliente que recibe). |
| `order_id` | integer | ✔ | FK → `sales.orders.order_id` | `Sales.Invoices.OrderID` | Pedido que originó la factura. |
| `delivery_method_id` | integer |  | FK → `application.delivery_methods.delivery_method_id` | `Sales.Invoices.DeliveryMethodID` |  |
| `contact_person_id` | integer |  | FK → `application.people.person_id` | `Sales.Invoices.ContactPersonID` |  |
| `accounts_person_id` | integer |  | FK → `application.people.person_id` | `Sales.Invoices.AccountsPersonID` |  |
| `salesperson_person_id` | integer |  | FK → `application.people.person_id` | `Sales.Invoices.SalespersonPersonID` |  |
| `packed_by_person_id` | integer |  | FK → `application.people.person_id` | `Sales.Invoices.PackedByPersonID` |  |
| `invoice_date` | date |  |  | `Sales.Invoices.InvoiceDate` |  |
| `customer_purchase_order_number` | character varying(20) | ✔ |  | `Sales.Invoices.CustomerPurchaseOrderNumber` |  |
| `is_credit_note` | boolean |  |  | `Sales.Invoices.IsCreditNote` | TRUE si es nota de crédito (devolución o ajuste) en lugar de una venta. |
| `credit_note_reason` | text | ✔ |  | `Sales.Invoices.CreditNoteReason` |  |
| `total_dry_items` | integer |  |  | `Sales.Invoices.TotalDryItems` | Cantidad de bultos secos (sin refrigeración) despachados. |
| `total_chiller_items` | integer |  |  | `Sales.Invoices.TotalChillerItems` | Cantidad de bultos refrigerados despachados. |
| `confirmed_delivery_time` | timestamp with time zone | ✔ |  | `Sales.Invoices.ConfirmedDeliveryTime` | Momento confirmado de entrega al cliente. NULL = sin confirmar. |
| `last_edited_by` | integer |  | FK → `application.people.person_id` | `Sales.Invoices.LastEditedBy` | Persona que hizo la última modificación (auditoría). |
| `last_edited_when` | timestamp with time zone |  |  | `Sales.Invoices.LastEditedWhen` | Fecha/hora (UTC) de la última modificación. Se usa como marca de agua (watermark) en la carga incremental. |

## sales.invoice_lines

Líneas de factura: la VENTA realizada. extended_price incluye impuestos (neto = extended_price - tax_amount).

Origen: `Sales.InvoiceLines` · Filas: 228,265

| Columna | Tipo | Nulo | Clave | Origen (SQL Server) | Descripción |
|---|---|:---:|---|---|---|
| `invoice_line_id` | integer |  | PK | `Sales.InvoiceLines.InvoiceLineID` |  |
| `invoice_id` | integer |  | FK → `sales.invoices.invoice_id` | `Sales.InvoiceLines.InvoiceID` |  |
| `stock_item_id` | integer |  | FK → `warehouse.stock_items.stock_item_id` | `Sales.InvoiceLines.StockItemID` |  |
| `description` | character varying(100) |  |  | `Sales.InvoiceLines.Description` |  |
| `package_type_id` | integer |  | FK → `warehouse.package_types.package_type_id` | `Sales.InvoiceLines.PackageTypeID` |  |
| `quantity` | integer |  |  | `Sales.InvoiceLines.Quantity` | Unidades vendidas en la línea. |
| `unit_price` | numeric(18,2) | ✔ |  | `Sales.InvoiceLines.UnitPrice` | Precio unitario de venta, sin impuestos. |
| `tax_rate` | numeric(18,3) |  |  | `Sales.InvoiceLines.TaxRate` | Tasa de impuesto aplicada, en porcentaje. |
| `tax_amount` | numeric(18,2) |  |  | `Sales.InvoiceLines.TaxAmount` | Importe del impuesto de la línea. |
| `line_profit` | numeric(18,2) |  |  | `Sales.InvoiceLines.LineProfit` | Utilidad (margen) de la línea, sin impuestos. |
| `extended_price` | numeric(18,2) |  |  | `Sales.InvoiceLines.ExtendedPrice` | Importe total de la línea CON impuestos = quantity * unit_price + tax_amount. |
| `last_edited_by` | integer |  | FK → `application.people.person_id` | `Sales.InvoiceLines.LastEditedBy` | Persona que hizo la última modificación (auditoría). |
| `last_edited_when` | timestamp with time zone |  |  | `Sales.InvoiceLines.LastEditedWhen` | Fecha/hora (UTC) de la última modificación. Se usa como marca de agua (watermark) en la carga incremental. |
