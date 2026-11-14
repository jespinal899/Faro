"""Mapeo de la migración WideWorldImporters (SQL Server) -> wwi_oltp (PostgreSQL).

Módulo de SOLO DATOS (sin conexiones): define qué tablas y columnas se migran y cómo se
llaman en cada motor. Es la fuente única del LINAJE de la base operacional y lo usan:
  - migrar_wwi.py               (ejecuta la migración)
  - documentar_fuente.py        (genera el diccionario de datos con el linaje)
  - tests/test_esquema_fuente.py (verifica que el mapeo coincide con el esquema)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Tabla:
    """Una tabla a migrar. `columnas` = pares (expresión en SQL Server, columna en PostgreSQL)."""

    origen: str
    destino: str
    columnas: tuple[tuple[str, str], ...]

    @property
    def consulta_origen(self) -> str:
        return f"SELECT {', '.join(o for o, _ in self.columnas)} FROM {self.origen}"

    @property
    def columnas_destino(self) -> list[str]:
        return [d for _, d in self.columnas]


def _cat(origen: str, destino: str, id_origen: str, id_destino: str, nombre: tuple[str, str]):
    """Atajo para catálogos simples: id, nombre, auditoría (tablas temporales)."""
    return Tabla(
        origen,
        destino,
        (
            (id_origen, id_destino),
            nombre,
            ("LastEditedBy", "last_edited_by"),
            ("ValidFrom", "last_edited_when"),
        ),
    )


# Orden = orden de carga (respeta las claves foráneas).
TABLAS: tuple[Tabla, ...] = (
    Tabla(
        "Application.People",
        "application.people",
        (
            ("PersonID", "person_id"),
            ("FullName", "full_name"),
            ("PreferredName", "preferred_name"),
            ("IsEmployee", "is_employee"),
            ("IsSalesperson", "is_salesperson"),
            ("LastEditedBy", "last_edited_by"),
            ("ValidFrom", "last_edited_when"),
        ),
    ),
    Tabla(
        "Application.Countries",
        "application.countries",
        (
            ("CountryID", "country_id"),
            ("CountryName", "country_name"),
            ("FormalName", "formal_name"),
            ("IsoAlpha3Code", "iso_alpha3_code"),
            ("IsoNumericCode", "iso_numeric_code"),
            ("CountryType", "country_type"),
            ("LatestRecordedPopulation", "latest_recorded_population"),
            ("Continent", "continent"),
            ("Region", "region"),
            ("Subregion", "subregion"),
            ("LastEditedBy", "last_edited_by"),
            ("ValidFrom", "last_edited_when"),
        ),
    ),
    Tabla(
        "Application.StateProvinces",
        "application.state_provinces",
        (
            ("StateProvinceID", "state_province_id"),
            ("StateProvinceCode", "state_province_code"),
            ("StateProvinceName", "state_province_name"),
            ("CountryID", "country_id"),
            ("SalesTerritory", "sales_territory"),
            ("LatestRecordedPopulation", "latest_recorded_population"),
            ("LastEditedBy", "last_edited_by"),
            ("ValidFrom", "last_edited_when"),
        ),
    ),
    Tabla(
        "Application.Cities",
        "application.cities",
        (
            ("CityID", "city_id"),
            ("CityName", "city_name"),
            ("StateProvinceID", "state_province_id"),
            ("Location.Lat", "latitude"),
            ("Location.Long", "longitude"),
            ("LatestRecordedPopulation", "latest_recorded_population"),
            ("LastEditedBy", "last_edited_by"),
            ("ValidFrom", "last_edited_when"),
        ),
    ),
    _cat(
        "Application.DeliveryMethods",
        "application.delivery_methods",
        "DeliveryMethodID",
        "delivery_method_id",
        ("DeliveryMethodName", "delivery_method_name"),
    ),
    _cat(
        "Warehouse.Colors",
        "warehouse.colors",
        "ColorID",
        "color_id",
        ("ColorName", "color_name"),
    ),
    _cat(
        "Warehouse.PackageTypes",
        "warehouse.package_types",
        "PackageTypeID",
        "package_type_id",
        ("PackageTypeName", "package_type_name"),
    ),
    _cat(
        "Warehouse.StockGroups",
        "warehouse.stock_groups",
        "StockGroupID",
        "stock_group_id",
        ("StockGroupName", "stock_group_name"),
    ),
    Tabla(
        "Warehouse.StockItems",
        "warehouse.stock_items",
        (
            ("StockItemID", "stock_item_id"),
            ("StockItemName", "stock_item_name"),
            ("ColorID", "color_id"),
            ("UnitPackageID", "unit_package_id"),
            ("OuterPackageID", "outer_package_id"),
            ("Brand", "brand"),
            ("Size", "size"),
            ("LeadTimeDays", "lead_time_days"),
            ("QuantityPerOuter", "quantity_per_outer"),
            ("IsChillerStock", "is_chiller_stock"),
            ("TaxRate", "tax_rate"),
            ("UnitPrice", "unit_price"),
            ("RecommendedRetailPrice", "recommended_retail_price"),
            ("TypicalWeightPerUnit", "typical_weight_per_unit"),
            ("LastEditedBy", "last_edited_by"),
            ("ValidFrom", "last_edited_when"),
        ),
    ),
    Tabla(
        "Warehouse.StockItemStockGroups",
        "warehouse.stock_item_stock_groups",
        (
            ("StockItemStockGroupID", "stock_item_stock_group_id"),
            ("StockItemID", "stock_item_id"),
            ("StockGroupID", "stock_group_id"),
            ("LastEditedBy", "last_edited_by"),
            ("LastEditedWhen", "last_edited_when"),
        ),
    ),
    _cat(
        "Sales.BuyingGroups",
        "sales.buying_groups",
        "BuyingGroupID",
        "buying_group_id",
        ("BuyingGroupName", "buying_group_name"),
    ),
    _cat(
        "Sales.CustomerCategories",
        "sales.customer_categories",
        "CustomerCategoryID",
        "customer_category_id",
        ("CustomerCategoryName", "customer_category_name"),
    ),
    Tabla(
        "Sales.Customers",
        "sales.customers",
        (
            ("CustomerID", "customer_id"),
            ("CustomerName", "customer_name"),
            ("BillToCustomerID", "bill_to_customer_id"),
            ("CustomerCategoryID", "customer_category_id"),
            ("BuyingGroupID", "buying_group_id"),
            ("PrimaryContactPersonID", "primary_contact_person_id"),
            ("AlternateContactPersonID", "alternate_contact_person_id"),
            ("DeliveryMethodID", "delivery_method_id"),
            ("DeliveryCityID", "delivery_city_id"),
            ("PostalCityID", "postal_city_id"),
            ("CreditLimit", "credit_limit"),
            ("AccountOpenedDate", "account_opened_date"),
            ("StandardDiscountPercentage", "standard_discount_percentage"),
            ("IsStatementSent", "is_statement_sent"),
            ("IsOnCreditHold", "is_on_credit_hold"),
            ("PaymentDays", "payment_days"),
            ("DeliveryPostalCode", "delivery_postal_code"),
            ("DeliveryLocation.Lat", "delivery_latitude"),
            ("DeliveryLocation.Long", "delivery_longitude"),
            ("LastEditedBy", "last_edited_by"),
            ("ValidFrom", "last_edited_when"),
        ),
    ),
    Tabla(
        "Sales.Orders",
        "sales.orders",
        (
            ("OrderID", "order_id"),
            ("CustomerID", "customer_id"),
            ("SalespersonPersonID", "salesperson_person_id"),
            ("PickedByPersonID", "picked_by_person_id"),
            ("ContactPersonID", "contact_person_id"),
            ("BackorderOrderID", "backorder_order_id"),
            ("OrderDate", "order_date"),
            ("ExpectedDeliveryDate", "expected_delivery_date"),
            ("CustomerPurchaseOrderNumber", "customer_purchase_order_number"),
            ("IsUndersupplyBackordered", "is_undersupply_backordered"),
            ("PickingCompletedWhen", "picking_completed_when"),
            ("LastEditedBy", "last_edited_by"),
            ("LastEditedWhen", "last_edited_when"),
        ),
    ),
    Tabla(
        "Sales.OrderLines",
        "sales.order_lines",
        (
            ("OrderLineID", "order_line_id"),
            ("OrderID", "order_id"),
            ("StockItemID", "stock_item_id"),
            ("Description", "description"),
            ("PackageTypeID", "package_type_id"),
            ("Quantity", "quantity"),
            ("UnitPrice", "unit_price"),
            ("TaxRate", "tax_rate"),
            ("PickedQuantity", "picked_quantity"),
            ("PickingCompletedWhen", "picking_completed_when"),
            ("LastEditedBy", "last_edited_by"),
            ("LastEditedWhen", "last_edited_when"),
        ),
    ),
    Tabla(
        "Sales.Invoices",
        "sales.invoices",
        (
            ("InvoiceID", "invoice_id"),
            ("CustomerID", "customer_id"),
            ("BillToCustomerID", "bill_to_customer_id"),
            ("OrderID", "order_id"),
            ("DeliveryMethodID", "delivery_method_id"),
            ("ContactPersonID", "contact_person_id"),
            ("AccountsPersonID", "accounts_person_id"),
            ("SalespersonPersonID", "salesperson_person_id"),
            ("PackedByPersonID", "packed_by_person_id"),
            ("InvoiceDate", "invoice_date"),
            ("CustomerPurchaseOrderNumber", "customer_purchase_order_number"),
            ("IsCreditNote", "is_credit_note"),
            ("CreditNoteReason", "credit_note_reason"),
            ("TotalDryItems", "total_dry_items"),
            ("TotalChillerItems", "total_chiller_items"),
            ("ConfirmedDeliveryTime", "confirmed_delivery_time"),
            ("LastEditedBy", "last_edited_by"),
            ("LastEditedWhen", "last_edited_when"),
        ),
    ),
    Tabla(
        "Sales.InvoiceLines",
        "sales.invoice_lines",
        (
            ("InvoiceLineID", "invoice_line_id"),
            ("InvoiceID", "invoice_id"),
            ("StockItemID", "stock_item_id"),
            ("Description", "description"),
            ("PackageTypeID", "package_type_id"),
            ("Quantity", "quantity"),
            ("UnitPrice", "unit_price"),
            ("TaxRate", "tax_rate"),
            ("TaxAmount", "tax_amount"),
            ("LineProfit", "line_profit"),
            ("ExtendedPrice", "extended_price"),
            ("LastEditedBy", "last_edited_by"),
            ("LastEditedWhen", "last_edited_when"),
        ),
    ),
)

# Sumas de control: (descripción, consulta en SQL Server, consulta en PostgreSQL)
CONTROLES: tuple[tuple[str, str, str], ...] = (
    (
        "Ventas: suma de extended_price",
        "SELECT SUM(ExtendedPrice) FROM Sales.InvoiceLines",
        "SELECT SUM(extended_price) FROM sales.invoice_lines",
    ),
    (
        "Ventas: suma de tax_amount",
        "SELECT SUM(TaxAmount) FROM Sales.InvoiceLines",
        "SELECT SUM(tax_amount) FROM sales.invoice_lines",
    ),
    (
        "Ventas: suma de line_profit",
        "SELECT SUM(LineProfit) FROM Sales.InvoiceLines",
        "SELECT SUM(line_profit) FROM sales.invoice_lines",
    ),
    (
        "Ventas: unidades vendidas",
        "SELECT SUM(CAST(Quantity AS bigint)) FROM Sales.InvoiceLines",
        "SELECT SUM(quantity) FROM sales.invoice_lines",
    ),
    (
        "Pedidos: unidades pedidas",
        "SELECT SUM(CAST(Quantity AS bigint)) FROM Sales.OrderLines",
        "SELECT SUM(quantity) FROM sales.order_lines",
    ),
    (
        "Clientes: suma de credit_limit",
        "SELECT SUM(CreditLimit) FROM Sales.Customers",
        "SELECT SUM(credit_limit) FROM sales.customers",
    ),
)
