"""Perfilado de datos de la base operacional (wwi_oltp).

Genera documentation/pruebas/perfil-fuente.md con:
  1. Reglas de calidad agrupadas por dimensión (completitud, unicidad, validez,
     consistencia, integridad, oportunidad, atípicos), con conteo de casos.
  2. Distribuciones clave (día de la semana, percentiles, continuidad mensual).
  3. Perfil por columna: % nulos, valores distintos, mínimo, máximo y valor más frecuente.

Solo LEE la base. Uso:
    uv run python database/scripts/perfilar_fuente.py
"""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg import sql

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "database" / "source" / "seed"))
from mapeo_wwi import TABLAS  # noqa: E402

REPORTE = RAIZ / "documentation" / "pruebas" / "perfil-fuente.md"


@dataclass(frozen=True)
class Regla:
    """`consulta` devuelve una fila (casos, total). Si `debe_ser_cero`, casos > 0 es un problema."""

    codigo: str
    dimension: str
    descripcion: str
    consulta: str
    debe_ser_cero: bool = True


REGLAS: tuple[Regla, ...] = (
    # ---------------------------------------------------------- completitud
    Regla(
        "C01",
        "Completitud",
        "Líneas de factura sin precio unitario",
        "SELECT count(*) FILTER (WHERE unit_price IS NULL), count(*) FROM sales.invoice_lines",
    ),
    Regla(
        "C02",
        "Completitud",
        "Pedidos sin persona que los preparó (picked_by_person_id NULL)",
        "SELECT count(*) FILTER (WHERE picked_by_person_id IS NULL), count(*) FROM sales.orders",
        debe_ser_cero=False,
    ),
    Regla(
        "C03",
        "Completitud",
        "Facturas sin entrega confirmada",
        "SELECT count(*) FILTER (WHERE confirmed_delivery_time IS NULL), count(*) "
        "FROM sales.invoices",
        debe_ser_cero=False,
    ),
    Regla(
        "C04",
        "Completitud",
        "Clientes sin límite de crédito definido",
        "SELECT count(*) FILTER (WHERE credit_limit IS NULL), count(*) FROM sales.customers",
        debe_ser_cero=False,
    ),
    Regla(
        "C05",
        "Completitud",
        "Productos sin marca",
        "SELECT count(*) FILTER (WHERE brand IS NULL), count(*) FROM warehouse.stock_items",
        debe_ser_cero=False,
    ),
    # ------------------------------------------------------------ unicidad
    Regla(
        "U01",
        "Unicidad",
        "Nombres de cliente repetidos",
        "SELECT count(*) - count(DISTINCT customer_name), count(*) FROM sales.customers",
    ),
    Regla(
        "U02",
        "Unicidad",
        "Nombres de producto repetidos",
        "SELECT count(*) - count(DISTINCT stock_item_name), count(*) FROM warehouse.stock_items",
    ),
    Regla(
        "U03",
        "Unicidad",
        "Mismo producto en más de una línea de la misma factura",
        "SELECT count(*) FILTER (WHERE c > 1), count(*) FROM "
        "(SELECT count(*) AS c FROM sales.invoice_lines GROUP BY invoice_id, stock_item_id) x",
    ),
    # -------------------------------------------------------------- validez
    Regla(
        "V01",
        "Validez",
        "Cantidad vendida menor o igual a cero",
        "SELECT count(*) FILTER (WHERE quantity <= 0), count(*) FROM sales.invoice_lines",
    ),
    Regla(
        "V02",
        "Validez",
        "Precio unitario menor o igual a cero",
        "SELECT count(*) FILTER (WHERE unit_price <= 0), count(*) FROM sales.invoice_lines",
    ),
    Regla(
        "V03",
        "Validez",
        "Tasa de impuesto fuera del rango 0–100 %",
        "SELECT count(*) FILTER (WHERE tax_rate NOT BETWEEN 0 AND 100), count(*) "
        "FROM sales.invoice_lines",
    ),
    Regla(
        "V04",
        "Validez",
        "Líneas con utilidad negativa (venta bajo costo: problema de negocio, no de datos)",
        "SELECT count(*) FILTER (WHERE line_profit < 0), count(*) FROM sales.invoice_lines",
        debe_ser_cero=False,
    ),
    Regla(
        "V05",
        "Validez",
        "Facturas que son notas de crédito",
        "SELECT count(*) FILTER (WHERE is_credit_note), count(*) FROM sales.invoices",
        debe_ser_cero=False,
    ),
    # --------------------------------------------------------- consistencia
    Regla(
        "K01",
        "Consistencia",
        "extended_price ≠ quantity × unit_price + tax_amount",
        "SELECT count(*) FILTER (WHERE extended_price <> quantity * unit_price + tax_amount), "
        "count(*) FROM sales.invoice_lines",
    ),
    Regla(
        "K02",
        "Consistencia",
        "tax_amount ≠ quantity × unit_price × tax_rate / 100 (redondeado a 2 decimales)",
        "SELECT count(*) FILTER (WHERE tax_amount <> "
        "round(quantity * unit_price * tax_rate / 100, 2)), count(*) FROM sales.invoice_lines",
    ),
    Regla(
        "K03",
        "Consistencia",
        "Factura con fecha anterior a la de su pedido",
        "SELECT count(*) FILTER (WHERE i.invoice_date < o.order_date), count(*) "
        "FROM sales.invoices i JOIN sales.orders o ON o.order_id = i.order_id",
    ),
    Regla(
        "K04",
        "Consistencia",
        "Entrega esperada anterior a la fecha del pedido",
        "SELECT count(*) FILTER (WHERE expected_delivery_date < order_date), count(*) "
        "FROM sales.orders",
    ),
    Regla(
        "K05",
        "Consistencia",
        "Entrega confirmada antes de la fecha de la factura",
        "SELECT count(*) FILTER (WHERE confirmed_delivery_time::date < invoice_date), count(*) "
        "FROM sales.invoices WHERE confirmed_delivery_time IS NOT NULL",
    ),
    Regla(
        "K06",
        "Consistencia",
        "Cantidad preparada mayor que la pedida",
        "SELECT count(*) FILTER (WHERE picked_quantity > quantity), count(*) "
        "FROM sales.order_lines",
    ),
    Regla(
        "K07",
        "Consistencia",
        "Líneas de pedido preparadas parcialmente (faltó stock)",
        "SELECT count(*) FILTER (WHERE picked_quantity < quantity), count(*) "
        "FROM sales.order_lines",
        debe_ser_cero=False,
    ),
    Regla(
        "K08",
        "Consistencia",
        "Factura con un 'cliente que paga' distinto al de la ficha del cliente",
        "SELECT count(*) FILTER (WHERE i.bill_to_customer_id <> c.bill_to_customer_id), count(*) "
        "FROM sales.invoices i JOIN sales.customers c ON c.customer_id = i.customer_id",
    ),
    # ----------------------------------------------------------- integridad
    Regla(
        "I01",
        "Integridad",
        "Pedidos sin factura",
        "SELECT count(*) FILTER (WHERE f.order_id IS NULL), count(*) FROM sales.orders o "
        "LEFT JOIN (SELECT DISTINCT order_id FROM sales.invoices) f ON f.order_id = o.order_id",
        debe_ser_cero=False,
    ),
    Regla(
        "I02",
        "Integridad",
        "Facturas sin líneas",
        "SELECT count(*) FILTER (WHERE l.invoice_id IS NULL), count(*) FROM sales.invoices i "
        "LEFT JOIN (SELECT DISTINCT invoice_id FROM sales.invoice_lines) l "
        "ON l.invoice_id = i.invoice_id",
    ),
    Regla(
        "I03",
        "Integridad",
        "Pedidos sin líneas",
        "SELECT count(*) FILTER (WHERE l.order_id IS NULL), count(*) FROM sales.orders o "
        "LEFT JOIN (SELECT DISTINCT order_id FROM sales.order_lines) l ON l.order_id = o.order_id",
    ),
    Regla(
        "I04",
        "Integridad",
        "Facturas sin pedido asociado (order_id NULL)",
        "SELECT count(*) FILTER (WHERE order_id IS NULL), count(*) FROM sales.invoices",
    ),
    Regla(
        "I05",
        "Integridad",
        "Productos que pertenecen a MÁS de un grupo (riesgo de duplicar importes)",
        "SELECT count(*) FILTER (WHERE coalesce(g.c, 0) > 1), count(*) "
        "FROM warehouse.stock_items s "
        "LEFT JOIN (SELECT stock_item_id, count(*) AS c FROM warehouse.stock_item_stock_groups "
        "GROUP BY 1) g ON g.stock_item_id = s.stock_item_id",
        debe_ser_cero=False,
    ),
    Regla(
        "I06",
        "Integridad",
        "Productos sin ningún grupo",
        "SELECT count(*) FILTER (WHERE g.stock_item_id IS NULL), count(*) "
        "FROM warehouse.stock_items s LEFT JOIN (SELECT DISTINCT stock_item_id "
        "FROM warehouse.stock_item_stock_groups) g ON g.stock_item_id = s.stock_item_id",
    ),
    Regla(
        "I07",
        "Integridad",
        "Productos que nunca se vendieron",
        "SELECT count(*) FILTER (WHERE v.stock_item_id IS NULL), count(*) "
        "FROM warehouse.stock_items s LEFT JOIN (SELECT DISTINCT stock_item_id "
        "FROM sales.invoice_lines) v ON v.stock_item_id = s.stock_item_id",
        debe_ser_cero=False,
    ),
    # ----------------------------------------------------------- oportunidad
    Regla(
        "O01",
        "Oportunidad",
        "Días del período (lunes a sábado) sin ninguna factura",
        "WITH d AS (SELECT generate_series(min(invoice_date), max(invoice_date), '1 day')::date "
        "AS dia FROM sales.invoices) "
        "SELECT count(*) FILTER (WHERE NOT EXISTS "
        "(SELECT 1 FROM sales.invoices i WHERE i.invoice_date = d.dia)), count(*) "
        "FROM d WHERE extract(isodow FROM dia) < 7",
        debe_ser_cero=False,
    ),
    Regla(
        "O02",
        "Oportunidad",
        "Registros modificados con fecha futura (last_edited_when > ahora)",
        "SELECT count(*) FILTER (WHERE last_edited_when > now()), count(*) "
        "FROM sales.invoice_lines",
    ),
    # -------------------------------------------------------------- atípicos
    Regla(
        "A01",
        "Atípicos",
        "Líneas con cantidad atípica (> Q3 + 3·IQR)",
        "WITH q AS (SELECT percentile_cont(0.25) WITHIN GROUP (ORDER BY quantity) AS q1, "
        "percentile_cont(0.75) WITHIN GROUP (ORDER BY quantity) AS q3 FROM sales.invoice_lines) "
        "SELECT count(*) FILTER (WHERE quantity > q3 + 3 * (q3 - q1)), count(*) "
        "FROM sales.invoice_lines, q",
        debe_ser_cero=False,
    ),
    Regla(
        "A02",
        "Atípicos",
        "Líneas con importe atípico (extended_price > Q3 + 3·IQR)",
        "WITH q AS (SELECT percentile_cont(0.25) WITHIN GROUP (ORDER BY extended_price) AS q1, "
        "percentile_cont(0.75) WITHIN GROUP (ORDER BY extended_price) AS q3 "
        "FROM sales.invoice_lines) "
        "SELECT count(*) FILTER (WHERE extended_price > q3 + 3 * (q3 - q1)), count(*) "
        "FROM sales.invoice_lines, q",
        debe_ser_cero=False,
    ),
)

DISTRIBUCIONES: tuple[tuple[str, str], ...] = (
    (
        "Facturación por día de la semana",
        "SELECT extract(isodow FROM invoice_date)::int AS n, "
        "(ARRAY['lunes','martes','miércoles','jueves','viernes','sábado','domingo'])"
        "[extract(isodow FROM invoice_date)::int] AS dia, count(*) AS facturas "
        "FROM sales.invoices GROUP BY 1, 2 ORDER BY 1",
    ),
    (
        "Percentiles de líneas de factura",
        "SELECT medida, round(p50::numeric, 2) AS p50, round(p95::numeric, 2) AS p95, "
        "round(p99::numeric, 2) AS p99, round(maximo::numeric, 2) AS maximo FROM ("
        "SELECT 'quantity' AS medida, "
        "percentile_cont(0.5) WITHIN GROUP (ORDER BY quantity) AS p50, "
        "percentile_cont(0.95) WITHIN GROUP (ORDER BY quantity) AS p95, "
        "percentile_cont(0.99) WITHIN GROUP (ORDER BY quantity) AS p99, "
        "max(quantity) AS maximo FROM sales.invoice_lines UNION ALL "
        "SELECT 'extended_price', "
        "percentile_cont(0.5) WITHIN GROUP (ORDER BY extended_price), "
        "percentile_cont(0.95) WITHIN GROUP (ORDER BY extended_price), "
        "percentile_cont(0.99) WITHIN GROUP (ORDER BY extended_price), "
        "max(extended_price) FROM sales.invoice_lines) p",
    ),
    (
        "Clientes y ventas por categoría de cliente",
        "SELECT cc.customer_category_name AS categoria, count(DISTINCT c.customer_id) AS clientes, "
        "to_char(sum(il.extended_price), 'FM999,999,999') AS ventas "
        "FROM sales.customer_categories cc "
        "JOIN sales.customers c ON c.customer_category_id = cc.customer_category_id "
        "LEFT JOIN sales.invoices i ON i.customer_id = c.customer_id "
        "LEFT JOIN sales.invoice_lines il ON il.invoice_id = i.invoice_id "
        "GROUP BY 1 ORDER BY sum(il.extended_price) DESC NULLS LAST",
    ),
    (
        "Continuidad mensual de la facturación",
        "SELECT to_char(date_trunc('month', i.invoice_date), 'YYYY-MM') AS mes, "
        "count(DISTINCT i.invoice_id) AS facturas, "
        "count(DISTINCT i.invoice_date) AS dias_con_ventas, "
        "to_char(sum(il.extended_price), 'FM999,999,999') AS ventas "
        "FROM sales.invoices i JOIN sales.invoice_lines il ON il.invoice_id = i.invoice_id "
        "GROUP BY 1 ORDER BY 1",
    ),
)


def evaluar_reglas(conn: psycopg.Connection) -> list[tuple[Regla, int, int]]:
    return [(r, *conn.execute(r.consulta).fetchone()) for r in REGLAS]


def _tabla_md(columnas: list[str], filas: list[tuple]) -> list[str]:
    out = ["| " + " | ".join(columnas) + " |", "|" + "---|" * len(columnas)]
    out += ["| " + " | ".join("" if v is None else str(v) for v in f) + " |" for f in filas]
    return out


def perfilar_tabla(conn: psycopg.Connection, tabla: str) -> list[tuple]:
    esquema, nombre = tabla.split(".")
    columnas = conn.execute(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_schema = %s AND table_name = %s ORDER BY ordinal_position",
        (esquema, nombre),
    ).fetchall()
    ident = sql.Identifier(esquema, nombre)
    total = conn.execute(sql.SQL("SELECT count(*) FROM {}").format(ident)).fetchone()[0]
    filas = []
    for col, tipo in columnas:
        c = sql.Identifier(col)
        es_texto = tipo in ("character varying", "text")
        if es_texto:
            extremos = sql.SQL("min(length({c}))::text, max(length({c}))::text").format(c=c)
        elif tipo == "boolean":
            extremos = sql.SQL("NULL, (count(*) FILTER (WHERE {c}))::text").format(c=c)
        else:
            extremos = sql.SQL("min({c})::text, max({c})::text").format(c=c)
        no_nulos, distintos, minimo, maximo = conn.execute(
            sql.SQL("SELECT count({c}), count(DISTINCT {c}), {e} FROM {t}").format(
                c=c, e=extremos, t=ident
            )
        ).fetchone()
        if distintos == no_nulos and no_nulos > 0:
            frecuente = "(todos distintos)"
        elif no_nulos == 0:
            frecuente = ""
        else:
            valor, frec = conn.execute(
                sql.SQL(
                    "SELECT {c}::text, count(*) FROM {t} WHERE {c} IS NOT NULL "
                    "GROUP BY 1 ORDER BY 2 DESC, 1 LIMIT 1"
                ).format(c=c, t=ident)
            ).fetchone()
            valor = valor if len(valor) <= 30 else valor[:27] + "..."
            frecuente = f"`{valor}` ({frec:,})"
        pct_nulos = 100 * (total - no_nulos) / total if total else 0
        if es_texto and minimo is not None:
            rango = (f"long. {minimo}", f"long. {maximo}")
        elif tipo == "boolean":
            rango = ("", f"{maximo} TRUE")
        else:
            rango = (minimo, maximo)
        filas.append((f"`{col}`", tipo, f"{pct_nulos:.1f} %", f"{distintos:,}", *rango, frecuente))
    return filas


def generar_reporte(conn: psycopg.Connection) -> tuple[str, int]:
    resultados = evaluar_reglas(conn)
    problemas = sum(1 for r, casos, _ in resultados if r.debe_ser_cero and casos > 0)
    out = [
        "# Perfil de datos — base operacional `wwi_oltp`",
        "",
        "> Generado automáticamente por `database/scripts/perfilar_fuente.py`",
        f"> ({datetime.now(UTC):%Y-%m-%d %H:%M} UTC). No editar a mano: regenerar.",
        "",
        "## 1. Reglas de calidad",
        "",
        "✅ cumple · ⚠️ la regla debería dar 0 casos y no los da · ℹ️ informativo (no es un error,",
        "pero hay que considerarlo en el ETL o en el modelo).",
        "",
        f"**Reglas evaluadas:** {len(resultados)} · **Con problemas:** {problemas}",
        "",
        "| Código | Dimensión | Regla | Casos | Total | % | Estado |",
        "|---|---|---|---:|---:|---:|:---:|",
    ]
    for r, casos, total in resultados:
        pct = 100 * casos / total if total else 0
        estado = ("⚠️" if casos else "✅") if r.debe_ser_cero else "ℹ️"
        out.append(
            f"| {r.codigo} | {r.dimension} | {r.descripcion} | {casos:,} | {total:,} "
            f"| {pct:.2f} % | {estado} |"
        )

    out += ["", "## 2. Distribuciones", ""]
    for titulo, consulta in DISTRIBUCIONES:
        cur = conn.execute(consulta)
        columnas = [d.name for d in cur.description]
        filas = cur.fetchall()
        out += [f"### {titulo}", ""]
        if len(filas) > 15:
            out += ["<details><summary>Ver tabla completa</summary>", ""]
            out += _tabla_md(columnas, filas) + ["", "</details>", ""]
        else:
            out += _tabla_md(columnas, filas) + [""]

    out += [
        "## 3. Perfil por columna",
        "",
        "Para texto, mínimo y máximo son longitudes; para booleanos, el máximo es la",
        "cantidad de valores TRUE.",
        "",
    ]
    encabezado = ["Columna", "Tipo", "% nulos", "Distintos", "Mínimo", "Máximo", "Más frecuente"]
    for t in TABLAS:
        out += [
            "<details>",
            f"<summary><code>{t.destino}</code></summary>",
            "",
            *_tabla_md(encabezado, perfilar_tabla(conn, t.destino)),
            "",
            "</details>",
            "",
        ]
    return "\n".join(out), problemas


def main() -> int:
    load_dotenv(RAIZ / ".env")
    url = os.getenv("SOURCE_DATABASE_URL")
    if not url:
        print("Falta SOURCE_DATABASE_URL en .env")
        return 1
    inicio = time.perf_counter()
    with psycopg.connect(url, connect_timeout=10) as conn:
        contenido, problemas = generar_reporte(conn)
    REPORTE.parent.mkdir(parents=True, exist_ok=True)
    REPORTE.write_text(contenido, encoding="utf-8", newline="\n")
    print(
        f"Perfil generado en {time.perf_counter() - inicio:.1f} s: {REPORTE.relative_to(RAIZ)} "
        f"({problemas} regla(s) con problemas)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
