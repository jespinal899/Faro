# Reconciliación de la carga de la fuente (WWI → wwi_oltp)

Generado automáticamente por `database/source/seed/migrar_wwi.py`.

- **Fecha (UTC):** 2026-11-14 23:38:38
- **Entorno destino:** local (localhost)
- **Duración:** 20.7 s
- **Resultado:** ✅ RECONCILIADO

## Conteo de filas por tabla

| Origen (SQL Server) | Destino (PostgreSQL) | Filas origen | Filas destino | ¿Coincide? |
|---|---|---:|---:|:---:|
| `Application.People` | `application.people` | 1,111 | 1,111 | ✅ |
| `Application.Countries` | `application.countries` | 190 | 190 | ✅ |
| `Application.StateProvinces` | `application.state_provinces` | 53 | 53 | ✅ |
| `Application.Cities` | `application.cities` | 37,940 | 37,940 | ✅ |
| `Application.DeliveryMethods` | `application.delivery_methods` | 10 | 10 | ✅ |
| `Warehouse.Colors` | `warehouse.colors` | 36 | 36 | ✅ |
| `Warehouse.PackageTypes` | `warehouse.package_types` | 14 | 14 | ✅ |
| `Warehouse.StockGroups` | `warehouse.stock_groups` | 10 | 10 | ✅ |
| `Warehouse.StockItems` | `warehouse.stock_items` | 227 | 227 | ✅ |
| `Warehouse.StockItemStockGroups` | `warehouse.stock_item_stock_groups` | 442 | 442 | ✅ |
| `Sales.BuyingGroups` | `sales.buying_groups` | 2 | 2 | ✅ |
| `Sales.CustomerCategories` | `sales.customer_categories` | 8 | 8 | ✅ |
| `Sales.Customers` | `sales.customers` | 663 | 663 | ✅ |
| `Sales.Orders` | `sales.orders` | 73,595 | 73,595 | ✅ |
| `Sales.OrderLines` | `sales.order_lines` | 231,412 | 231,412 | ✅ |
| `Sales.Invoices` | `sales.invoices` | 70,510 | 70,510 | ✅ |
| `Sales.InvoiceLines` | `sales.invoice_lines` | 228,265 | 228,265 | ✅ |

## Sumas de control

| Control | Origen | Destino | ¿Coincide? |
|---|---:|---:|:---:|
| Ventas: suma de extended_price | 198,043,439.45 | 198,043,439.45 | ✅ |
| Ventas: suma de tax_amount | 25,782,098.25 | 25,782,098.25 | ✅ |
| Ventas: suma de line_profit | 85,729,180.90 | 85,729,180.90 | ✅ |
| Ventas: unidades vendidas | 8,950,628 | 8,950,628 | ✅ |
| Pedidos: unidades pedidas | 9,310,904 | 9,310,904 | ✅ |
| Clientes: suma de credit_limit | 682,476.00 | 682,476.00 | ✅ |
