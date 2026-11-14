# Diagrama entidad-relación — base operacional `wwi_oltp`

> Generado automáticamente por `database/scripts/documentar_fuente.py` desde la base
> real (2026-11-14 23:40 UTC). No editar a mano: regenerar.

**Cómo leerlo:** `||--o{` = uno a muchos (la FK es obligatoria);
`|o--o{` = cero o uno a muchos (la FK admite NULL). La etiqueta es la columna FK.

**Simplificación:** se omiten `last_edited_by` y `last_edited_when`, presentes en todas
las tablas (cada `last_edited_by` es una FK a `application.people`).

```mermaid
erDiagram
    application_state_provinces ||--o{ application_cities : "state_province_id"
    application_countries ||--o{ application_state_provinces : "country_id"
    application_people |o--o{ sales_customers : "alternate_contact_person_id"
    sales_customers ||--o{ sales_customers : "bill_to_customer_id"
    sales_buying_groups |o--o{ sales_customers : "buying_group_id"
    sales_customer_categories ||--o{ sales_customers : "customer_category_id"
    application_cities ||--o{ sales_customers : "delivery_city_id"
    application_delivery_methods ||--o{ sales_customers : "delivery_method_id"
    application_cities ||--o{ sales_customers : "postal_city_id"
    application_people ||--o{ sales_customers : "primary_contact_person_id"
    sales_invoices ||--o{ sales_invoice_lines : "invoice_id"
    warehouse_package_types ||--o{ sales_invoice_lines : "package_type_id"
    warehouse_stock_items ||--o{ sales_invoice_lines : "stock_item_id"
    application_people ||--o{ sales_invoices : "accounts_person_id"
    sales_customers ||--o{ sales_invoices : "bill_to_customer_id"
    application_people ||--o{ sales_invoices : "contact_person_id"
    sales_customers ||--o{ sales_invoices : "customer_id"
    application_delivery_methods ||--o{ sales_invoices : "delivery_method_id"
    sales_orders |o--o{ sales_invoices : "order_id"
    application_people ||--o{ sales_invoices : "packed_by_person_id"
    application_people ||--o{ sales_invoices : "salesperson_person_id"
    sales_orders ||--o{ sales_order_lines : "order_id"
    warehouse_package_types ||--o{ sales_order_lines : "package_type_id"
    warehouse_stock_items ||--o{ sales_order_lines : "stock_item_id"
    sales_orders |o--o{ sales_orders : "backorder_order_id"
    application_people ||--o{ sales_orders : "contact_person_id"
    sales_customers ||--o{ sales_orders : "customer_id"
    application_people |o--o{ sales_orders : "picked_by_person_id"
    application_people ||--o{ sales_orders : "salesperson_person_id"
    warehouse_stock_groups ||--o{ warehouse_stock_item_stock_groups : "stock_group_id"
    warehouse_stock_items ||--o{ warehouse_stock_item_stock_groups : "stock_item_id"
    warehouse_colors |o--o{ warehouse_stock_items : "color_id"
    warehouse_package_types ||--o{ warehouse_stock_items : "outer_package_id"
    warehouse_package_types ||--o{ warehouse_stock_items : "unit_package_id"
    application_people {
        int person_id PK
        varchar full_name
        varchar preferred_name
        bool is_employee
        bool is_salesperson
    }
    application_countries {
        int country_id PK
        varchar country_name
        varchar formal_name
        varchar iso_alpha3_code
        int iso_numeric_code
        varchar country_type
        bigint latest_recorded_population
        varchar continent
        varchar region
        varchar subregion
    }
    application_state_provinces {
        int state_province_id PK
        varchar state_province_code
        varchar state_province_name
        int country_id FK
        varchar sales_territory
        bigint latest_recorded_population
    }
    application_cities {
        int city_id PK
        varchar city_name
        int state_province_id FK
        float8 latitude
        float8 longitude
        bigint latest_recorded_population
    }
    application_delivery_methods {
        int delivery_method_id PK
        varchar delivery_method_name
    }
    warehouse_colors {
        int color_id PK
        varchar color_name
    }
    warehouse_package_types {
        int package_type_id PK
        varchar package_type_name
    }
    warehouse_stock_groups {
        int stock_group_id PK
        varchar stock_group_name
    }
    warehouse_stock_items {
        int stock_item_id PK
        varchar stock_item_name
        int color_id FK
        int unit_package_id FK
        int outer_package_id FK
        varchar brand
        varchar size
        int lead_time_days
        int quantity_per_outer
        bool is_chiller_stock
        numeric tax_rate
        numeric unit_price
        numeric recommended_retail_price
        numeric typical_weight_per_unit
    }
    warehouse_stock_item_stock_groups {
        int stock_item_stock_group_id PK
        int stock_item_id UK, FK
        int stock_group_id UK, FK
    }
    sales_buying_groups {
        int buying_group_id PK
        varchar buying_group_name
    }
    sales_customer_categories {
        int customer_category_id PK
        varchar customer_category_name
    }
    sales_customers {
        int customer_id PK
        varchar customer_name
        int bill_to_customer_id FK
        int customer_category_id FK
        int buying_group_id FK
        int primary_contact_person_id FK
        int alternate_contact_person_id FK
        int delivery_method_id FK
        int delivery_city_id FK
        int postal_city_id FK
        numeric credit_limit
        date account_opened_date
        numeric standard_discount_percentage
        bool is_statement_sent
        bool is_on_credit_hold
        int payment_days
        varchar delivery_postal_code
        float8 delivery_latitude
        float8 delivery_longitude
    }
    sales_orders {
        int order_id PK
        int customer_id FK
        int salesperson_person_id FK
        int picked_by_person_id FK
        int contact_person_id FK
        int backorder_order_id FK
        date order_date
        date expected_delivery_date
        varchar customer_purchase_order_number
        bool is_undersupply_backordered
        timestamptz picking_completed_when
    }
    sales_order_lines {
        int order_line_id PK
        int order_id FK
        int stock_item_id FK
        varchar description
        int package_type_id FK
        int quantity
        numeric unit_price
        numeric tax_rate
        int picked_quantity
        timestamptz picking_completed_when
    }
    sales_invoices {
        int invoice_id PK
        int customer_id FK
        int bill_to_customer_id FK
        int order_id FK
        int delivery_method_id FK
        int contact_person_id FK
        int accounts_person_id FK
        int salesperson_person_id FK
        int packed_by_person_id FK
        date invoice_date
        varchar customer_purchase_order_number
        bool is_credit_note
        text credit_note_reason
        int total_dry_items
        int total_chiller_items
        timestamptz confirmed_delivery_time
    }
    sales_invoice_lines {
        int invoice_line_id PK
        int invoice_id FK
        int stock_item_id FK
        varchar description
        int package_type_id FK
        int quantity
        numeric unit_price
        numeric tax_rate
        numeric tax_amount
        numeric line_profit
        numeric extended_price
    }
```

## Observaciones para el modelo dimensional

- **Producto ↔ grupo es MUCHOS a MUCHOS** (`warehouse.stock_item_stock_groups`): un
  producto puede pertenecer a varios grupos. Unir ventas con grupos sin control
  **multiplicaría los importes**; hay que resolverlo en el diseño (Fase 2).
- **Cliente que recibe ≠ cliente que paga:** `customers.bill_to_customer_id` y
  `invoices.bill_to_customer_id` son autorreferencias a `sales.customers`.
- **Pedidos pendientes:** `orders.backorder_order_id` es una autorreferencia a
  `sales.orders`.
- **Una persona, varios roles:** vendedor, contacto, preparador y empacador apuntan todos
  a `application.people` (en el DW serán *role-playing dimensions*).
- **Dos ciudades por cliente:** de entrega (`delivery_city_id`) y postal
  (`postal_city_id`).
