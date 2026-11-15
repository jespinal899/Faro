"""Configuración del ETL: tablas de la fuente y reglas de calidad.

Es el CATÁLOGO DE REGLAS de calidad de Faro. Cada regla es una condición SQL sobre el
alias `r` (el registro candidato) que es verdadera cuando el registro INCUMPLE la regla.

Acciones:
  - cuarentena: el registro no entra a stg_clean; va a stg_quarantine con el motivo.
  - marcar    : el registro entra a stg_clean con el código de la regla en _dq_flags.

Diseño y justificación: documentation/arquitectura/diseno-staging-etl.md
"""

from __future__ import annotations

from dataclasses import dataclass

PIPELINE = "ventas_staging"

# Ventana hacia atrás del watermark: cubre transacciones confirmadas con retraso
SOLAPAMIENTO = "10 minutes"
# Tolerancia entre relojes antes de considerar "futura" una marca de tiempo
TOLERANCIA_RELOJ = "5 minutes"

# Umbrales de atípicos = Q3 + 3·IQR, calculados en el perfilado 2013–2016
# (quantity: Q1=5, Q3=60 · extended_price: Q1=110.40, Q3=993.60).
# Son fijos para que la regla sea reproducible; recalibrar con perfilar_fuente.py.
UMBRAL_CANTIDAD_ATIPICA = 225
UMBRAL_IMPORTE_ATIPICO = 3643.20


@dataclass(frozen=True)
class Regla:
    codigo: str
    dimension: str
    descripcion: str
    accion: str  # "cuarentena" | "marcar"
    condicion: str  # SQL sobre el alias r; TRUE = incumple


@dataclass(frozen=True)
class TablaFuente:
    origen: str  # esquema.tabla en wwi_oltp
    pk: str
    reglas: tuple[Regla, ...] = ()

    @property
    def staging(self) -> str:
        """Nombre de la tabla en stg_raw / stg_clean: sales.orders -> sales_orders."""
        return self.origen.replace(".", "_")


def _huerfano(codigo: str, padre: str, fk: str, pk_padre: str, que: str) -> Regla:
    """Integridad referencial: el registro apunta a un padre que no está en stg_clean."""
    return Regla(
        codigo,
        "Integridad",
        f"{que} inexistente o en cuarentena",
        "cuarentena",
        f"NOT EXISTS (SELECT 1 FROM stg_clean.{padre} p WHERE p.{pk_padre} = r.{fk})",
    )


# Se aplica a TODAS las tablas: una marca de tiempo futura rompería el watermark
REGLA_FECHA_FUTURA = Regla(
    "O02",
    "Oportunidad",
    "last_edited_when en el futuro",
    "cuarentena",
    f"r.last_edited_when > r._extracted_at + interval '{TOLERANCIA_RELOJ}'",
)

REGLAS_LINEA_FACTURA = (
    Regla("V01", "Validez", "Cantidad menor o igual a cero", "cuarentena", "r.quantity <= 0"),
    Regla(
        "V02",
        "Validez",
        "Precio unitario nulo, cero o negativo",
        "cuarentena",
        "r.unit_price IS NULL OR r.unit_price <= 0",
    ),
    Regla(
        "V03",
        "Validez",
        "Tasa de impuesto fuera del rango 0–100 %",
        "cuarentena",
        "r.tax_rate NOT BETWEEN 0 AND 100",
    ),
    Regla(
        "K01",
        "Consistencia",
        "extended_price distinto de quantity × unit_price + tax_amount",
        "cuarentena",
        "r.extended_price <> r.quantity * r.unit_price + r.tax_amount",
    ),
    Regla(
        "K02",
        "Consistencia",
        "tax_amount distinto de quantity × unit_price × tax_rate / 100",
        "cuarentena",
        "r.tax_amount <> round(r.quantity * r.unit_price * r.tax_rate / 100, 2)",
    ),
    _huerfano("I02", "sales_invoices", "invoice_id", "invoice_id", "Factura de la línea"),
    _huerfano("I08", "warehouse_stock_items", "stock_item_id", "stock_item_id", "Producto"),
    Regla(
        "V04",
        "Validez",
        "Utilidad negativa (venta bajo costo: problema de negocio, no de datos)",
        "marcar",
        "r.line_profit < 0",
    ),
    Regla(
        "A01",
        "Atípicos",
        f"Cantidad atípica (> {UMBRAL_CANTIDAD_ATIPICA})",
        "marcar",
        f"r.quantity > {UMBRAL_CANTIDAD_ATIPICA}",
    ),
    Regla(
        "A02",
        "Atípicos",
        f"Importe atípico (extended_price > {UMBRAL_IMPORTE_ATIPICO})",
        "marcar",
        f"r.extended_price > {UMBRAL_IMPORTE_ATIPICO}",
    ),
)

# El orden es el de carga: los padres se limpian antes que los hijos,
# para que las reglas de integridad encuentren al padre en stg_clean.
TABLAS: tuple[TablaFuente, ...] = (
    TablaFuente("application.people", "person_id"),
    TablaFuente("application.countries", "country_id"),
    TablaFuente("application.state_provinces", "state_province_id"),
    TablaFuente("application.cities", "city_id"),
    TablaFuente("application.delivery_methods", "delivery_method_id"),
    TablaFuente("warehouse.colors", "color_id"),
    TablaFuente("warehouse.package_types", "package_type_id"),
    TablaFuente("warehouse.stock_groups", "stock_group_id"),
    TablaFuente("warehouse.stock_items", "stock_item_id"),
    TablaFuente(
        "warehouse.stock_item_stock_groups",
        "stock_item_stock_group_id",
        (
            _huerfano("I08", "warehouse_stock_items", "stock_item_id", "stock_item_id", "Producto"),
            _huerfano("I09", "warehouse_stock_groups", "stock_group_id", "stock_group_id", "Grupo"),
        ),
    ),
    TablaFuente("sales.buying_groups", "buying_group_id"),
    TablaFuente("sales.customer_categories", "customer_category_id"),
    TablaFuente(
        "sales.customers",
        "customer_id",
        (
            _huerfano(
                "I10", "application_cities", "delivery_city_id", "city_id", "Ciudad de entrega"
            ),
        ),
    ),
    TablaFuente(
        "sales.orders",
        "order_id",
        (_huerfano("I11", "sales_customers", "customer_id", "customer_id", "Cliente del pedido"),),
    ),
    TablaFuente(
        "sales.order_lines",
        "order_line_id",
        (
            Regla(
                "V01", "Validez", "Cantidad menor o igual a cero", "cuarentena", "r.quantity <= 0"
            ),
            _huerfano("I12", "sales_orders", "order_id", "order_id", "Pedido de la línea"),
        ),
    ),
    TablaFuente(
        "sales.invoices",
        "invoice_id",
        (
            _huerfano("I11", "sales_customers", "customer_id", "customer_id", "Cliente"),
            Regla(
                "K03",
                "Consistencia",
                "Factura con fecha anterior a la de su pedido",
                "marcar",
                "EXISTS (SELECT 1 FROM stg_clean.sales_orders o "
                "WHERE o.order_id = r.order_id AND r.invoice_date < o.order_date)",
            ),
        ),
    ),
    TablaFuente("sales.invoice_lines", "invoice_line_id", REGLAS_LINEA_FACTURA),
)


def reglas_de(tabla: TablaFuente) -> tuple[Regla, ...]:
    """Reglas propias de la tabla más las comunes a todas."""
    return (REGLA_FECHA_FUTURA, *tabla.reglas)
