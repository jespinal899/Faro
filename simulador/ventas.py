"""Simulador de ventas: genera la operación de los siguientes días hábiles en wwi_oltp.

WideWorldImporters termina el 31-may-2016. Este programa hace de "sistema de ventas en
operación": por cada día hábil siguiente al último facturado inserta pedidos y facturas con
sus líneas, imitando los patrones medidos en el perfilado:
  - No se vende los domingos; el sábado vende ~42 % de un día hábil.
  - Cada factura tiene entre 1 y 5 productos distintos (3.2 en promedio).
  - Precio de lista, tasa de impuesto y costo unitario de cada producto; cantidades
    tomadas de las que ese producto ya vendió.
Los importes cumplen las reglas de consistencia de la fuente (K01 y K02).

TODO lo que crea lleva a la persona "Simulador de ventas" en last_edited_by, así los datos
simulados son identificables en el staging y en el Data Warehouse.

Uso (desde la raíz del repositorio):
    uv run python -m simulador.ventas                       # el siguiente día hábil
    uv run python -m simulador.ventas --dias 5              # los siguientes 5 días hábiles
    uv run python -m simulador.ventas --factor-volumen 0.5  # un día con la mitad de ventas
    uv run python -m simulador.ventas --registro-invalido   # agrega una línea inválida (demo
                                                            # de la cuarentena del ETL)

Conexión: variable SIMULADOR_DATABASE_URL o, si no existe, SOURCE_DATABASE_URL.
"""

from __future__ import annotations

import argparse
import logging
import os
import random
import sys
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal

import psycopg
from dotenv import load_dotenv

from etl.db import conectar

log = logging.getLogger("simulador")

NOMBRE_SIMULADOR = "Simulador de ventas"
PROPORCION_SABADO = 0.42  # facturas de un sábado / facturas de un día hábil (perfilado)
LINEAS_POR_FACTURA = ([1, 2, 3, 4, 5], [12, 18, 24, 24, 22])  # valores y pesos (media 3.26)
PEDIDOS_POR_DEFECTO = 75
CENTAVO = Decimal("0.01")


@dataclass
class ResumenDia:
    fecha: date
    pedidos: int
    lineas: int
    venta_bruta: Decimal


def siguiente_dia_habil(dia: date) -> date:
    """El día siguiente, saltando el domingo."""
    siguiente = dia + timedelta(days=1)
    return siguiente + timedelta(days=1) if siguiente.isoweekday() == 7 else siguiente


def _ids(conn: psycopg.Connection, tabla: str, pk: str, cantidad: int) -> list[int]:
    """Reserva `cantidad` identificadores consecutivos de la secuencia de la tabla."""
    filas = conn.execute(
        "SELECT nextval(pg_get_serial_sequence(%s, %s)) FROM generate_series(1, %s)",
        (tabla, pk, cantidad),
    ).fetchall()
    return [f[0] for f in filas]


def _copiar(conn: psycopg.Connection, tabla: str, columnas: str, filas: list[tuple]) -> None:
    with conn.cursor() as cur, cur.copy(f"COPY {tabla} ({columnas}) FROM STDIN") as copia:
        for fila in filas:
            copia.write_row(fila)


def _cargar_catalogos(conn: psycopg.Connection) -> dict:
    simulador = conn.execute(
        "SELECT person_id FROM application.people WHERE full_name = %s", (NOMBRE_SIMULADOR,)
    ).fetchone()
    if not simulador:
        raise RuntimeError(
            f"No existe la persona '{NOMBRE_SIMULADOR}': "
            "aplica database/source/02_persona_simulador.sql"
        )
    return {
        "simulador": simulador[0],
        "clientes": conn.execute(
            "SELECT customer_id, bill_to_customer_id, primary_contact_person_id, "
            "delivery_method_id FROM sales.customers ORDER BY 1"
        ).fetchall(),
        "vendedores": [
            f[0]
            for f in conn.execute(
                "SELECT person_id FROM application.people WHERE is_salesperson ORDER BY 1"
            )
        ],
        "empleados": [
            f[0]
            for f in conn.execute(
                "SELECT person_id FROM application.people WHERE is_employee ORDER BY 1"
            )
        ],
        # Solo productos con historia: de ahí salen sus cantidades típicas y su costo unitario
        "productos": conn.execute(
            "SELECT s.stock_item_id, s.stock_item_name, s.unit_package_id, s.unit_price, "
            "       s.tax_rate, s.is_chiller_stock, h.cantidades, h.costo "
            "FROM warehouse.stock_items s JOIN ("
            "  SELECT stock_item_id, array_agg(DISTINCT quantity) AS cantidades, "
            "         (array_agg(round((quantity * unit_price - line_profit) / quantity, 2) "
            "                    ORDER BY invoice_line_id DESC))[1] AS costo "
            "  FROM sales.invoice_lines WHERE quantity > 0 AND unit_price > 0 GROUP BY 1"
            ") h USING (stock_item_id) ORDER BY 1"
        ).fetchall(),
    }


def _pedidos_base(conn: psycopg.Connection, ultimo: date) -> float:
    """Promedio de facturas por día (lunes a viernes) de los últimos 90 días con datos."""
    promedio = conn.execute(
        "SELECT avg(n) FROM (SELECT count(*) AS n FROM sales.invoices "
        "WHERE invoice_date > %s AND extract(isodow FROM invoice_date) < 6 "
        "GROUP BY invoice_date) d",
        (ultimo - timedelta(days=90),),
    ).fetchone()[0]
    return float(promedio) if promedio else PEDIDOS_POR_DEFECTO


def _simular_dia(conn, cat: dict, dia: date, pedidos: int, rnd: random.Random, invalido: bool):
    sim = cat["simulador"]
    entrega = siguiente_dia_habil(dia)
    preparado = datetime.combine(dia, time(11, 0), tzinfo=UTC)
    entregado = datetime.combine(entrega, time(12, 0), tzinfo=UTC)

    pedidos_ids = _ids(conn, "sales.orders", "order_id", pedidos)
    facturas_ids = _ids(conn, "sales.invoices", "invoice_id", pedidos)
    f_pedidos, f_lineas_pedido, f_facturas, f_lineas_factura = [], [], [], []
    total = Decimal(0)

    for pedido_id, factura_id in zip(pedidos_ids, facturas_ids, strict=True):
        cliente, cliente_paga, contacto, metodo = rnd.choice(cat["clientes"])
        vendedor = rnd.choice(cat["vendedores"])
        preparador, empacador = rnd.choice(cat["empleados"]), rnd.choice(cat["empleados"])
        n_lineas = min(rnd.choices(*LINEAS_POR_FACTURA)[0], len(cat["productos"]))
        secos = frios = 0

        for prod, nombre, empaque, precio, tasa, es_frio, cantidades, costo in rnd.sample(
            cat["productos"], n_lineas
        ):
            cantidad = rnd.choice(cantidades)
            impuesto = (cantidad * precio * tasa / 100).quantize(CENTAVO, ROUND_HALF_UP)
            bruto = cantidad * precio + impuesto
            utilidad = cantidad * (precio - costo)
            total += bruto
            frios += es_frio
            secos += not es_frio
            f_lineas_pedido.append(
                (pedido_id, prod, nombre, empaque, cantidad, precio, tasa, cantidad, preparado, sim)
            )
            f_lineas_factura.append(
                (factura_id, prod, nombre, empaque, cantidad, precio, tasa, impuesto, utilidad,
                 bruto, sim)
            )  # fmt: skip

        f_pedidos.append(
            (pedido_id, cliente, vendedor, preparador, contacto, dia, entrega, True, preparado, sim)
        )
        f_facturas.append(
            (factura_id, cliente, cliente_paga, pedido_id, metodo, contacto, contacto, vendedor,
             empacador, dia, False, secos, frios, entregado, sim)
        )  # fmt: skip

    if invalido:
        # Línea con cantidad 0 e importe incoherente: el ETL debe mandarla a cuarentena
        prod, nombre, empaque, precio, tasa, *_ = cat["productos"][0]
        f_lineas_factura.append(
            (facturas_ids[-1], prod, nombre, empaque, 0, precio, tasa, Decimal(0), Decimal(0),
             Decimal("99.00"), sim)
        )  # fmt: skip

    _copiar(
        conn, "sales.orders",
        "order_id, customer_id, salesperson_person_id, picked_by_person_id, contact_person_id, "
        "order_date, expected_delivery_date, is_undersupply_backordered, picking_completed_when, "
        "last_edited_by",
        f_pedidos,
    )  # fmt: skip
    _copiar(
        conn, "sales.order_lines",
        "order_id, stock_item_id, description, package_type_id, quantity, unit_price, tax_rate, "
        "picked_quantity, picking_completed_when, last_edited_by",
        f_lineas_pedido,
    )  # fmt: skip
    _copiar(
        conn, "sales.invoices",
        "invoice_id, customer_id, bill_to_customer_id, order_id, delivery_method_id, "
        "contact_person_id, accounts_person_id, salesperson_person_id, packed_by_person_id, "
        "invoice_date, is_credit_note, total_dry_items, total_chiller_items, "
        "confirmed_delivery_time, last_edited_by",
        f_facturas,
    )  # fmt: skip
    _copiar(
        conn, "sales.invoice_lines",
        "invoice_id, stock_item_id, description, package_type_id, quantity, unit_price, tax_rate, "
        "tax_amount, line_profit, extended_price, last_edited_by",
        f_lineas_factura,
    )  # fmt: skip
    return ResumenDia(dia, pedidos, len(f_lineas_factura), total)


def simular(
    url: str,
    dias: int = 1,
    pedidos: int | None = None,
    semilla: int | None = None,
    factor_volumen: float = 1.0,
    registro_invalido: bool = False,
) -> list[ResumenDia]:
    """Inserta `dias` días hábiles de ventas, todos en una sola transacción."""
    rnd = random.Random(semilla)
    resumen = []
    with conectar(url) as conn:
        cat = _cargar_catalogos(conn)
        if not (cat["clientes"] and cat["vendedores"] and cat["productos"]):
            raise RuntimeError("La fuente no tiene clientes, vendedores o productos con historia")
        ultimo = conn.execute("SELECT max(invoice_date) FROM sales.invoices").fetchone()[0]
        base = pedidos if pedidos is not None else _pedidos_base(conn, ultimo)

        dia = ultimo
        for i in range(dias):
            dia = siguiente_dia_habil(dia)
            esperado = base * (PROPORCION_SABADO if dia.isoweekday() == 6 else 1.0) * factor_volumen
            cantidad = esperado if pedidos is not None else rnd.gauss(esperado, esperado * 0.1)
            r = _simular_dia(
                conn, cat, dia, max(1, round(cantidad)), rnd,
                invalido=registro_invalido and i == dias - 1,
            )  # fmt: skip
            resumen.append(r)
            log.info(
                "%s (%s): %d pedidos facturados, %d líneas, venta bruta %s",
                r.fecha, "sáb" if r.fecha.isoweekday() == 6 else "hábil", r.pedidos, r.lineas,
                f"{r.venta_bruta:,.2f}",
            )  # fmt: skip
    return resumen


def main() -> int:
    parser = argparse.ArgumentParser(description="Simulador de ventas de WideWorldImporters")
    parser.add_argument("--dias", type=int, default=1, help="días hábiles a simular")
    parser.add_argument(
        "--pedidos", type=int, help="pedidos por día hábil (por defecto, el histórico)"
    )
    parser.add_argument("--semilla", type=int, help="semilla para resultados repetibles")
    parser.add_argument("--factor-volumen", type=float, default=1.0, help="0.5 = mitad de ventas")
    parser.add_argument(
        "--registro-invalido", action="store_true", help="agrega una línea inválida"
    )
    args = parser.parse_args()
    if args.dias < 1 or args.dias > 60:
        parser.error("--dias debe estar entre 1 y 60")

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    load_dotenv()
    url = os.getenv("SIMULADOR_DATABASE_URL") or os.getenv("SOURCE_DATABASE_URL")
    if not url:
        log.error("Falta SIMULADOR_DATABASE_URL o SOURCE_DATABASE_URL")
        return 1
    try:
        dias = simular(
            url, args.dias, args.pedidos, args.semilla, args.factor_volumen, args.registro_invalido
        )
    except (psycopg.Error, RuntimeError) as error:
        log.error("La simulación falló y no se guardó nada: %s", error)
        return 1
    log.info(
        "SIMULACIÓN: %d día(s), %d pedidos facturados. Datos marcados como '%s'.",
        len(dias), sum(d.pedidos for d in dias), NOMBRE_SIMULADOR,
    )  # fmt: skip
    return 0


if __name__ == "__main__":
    sys.exit(main())
