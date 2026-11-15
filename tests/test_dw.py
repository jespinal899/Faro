"""Pruebas del Data Warehouse (criterios de la guía: grano, SCD, integridad, idempotencia).

Escenario en orden sobre bases temporales:
  carga inicial -> SCD2 (cambio de categoría) -> ventas nuevas con la versión nueva ->
  SCD1 (cambio de nombre) -> dos cambios antes de la siguiente venta -> miembro
  desconocido y reasignación -> idempotencia -> validación completa
"""

from datetime import date

import pytest
import validar_dw
from conftest import sql, uno

from etl.orchestration import pipeline
from simulador import ventas

pytestmark = pytest.mark.integracion

VERSIONES = (
    "SELECT version, categoria, valido_desde::text, valido_hasta::text, es_actual "
    "FROM dw.dim_cliente WHERE cliente_id = 1 ORDER BY version"
)


def _correr(bases, modo="incremental"):
    r = pipeline.ejecutar(*bases, modo=modo, disparador="ci")
    assert r.estado == "exitoso", r.error
    return r


def test_carga_inicial(bases):
    fuente, dw = bases
    r = _correr(bases, "inicial")

    assert (r.dw_hechos_nuevos, r.dw_hechos_con_desconocido, r.reconciliado) == (2, 0, True)
    assert uno(dw, "SELECT count(*) FROM dw.fact_ventas") == 2
    assert sql(dw, VERSIONES) == [(1, "Tienda", "1900-01-01", "9999-12-31", True)]
    # Cada hecho apunta a dimensiones reales (ninguna clave -1)
    assert (
        uno(
            dw,
            "SELECT count(*) FROM dw.fact_ventas WHERE -1 IN (fecha_factura_key, fecha_pedido_key, "
            "cliente_key, cliente_facturacion_key, producto_key, vendedor_key, geografia_key)",
        )
        == 0
    )
    assert sql(
        dw, "SELECT grupo_principal, marca, color FROM dw.dim_producto WHERE producto_id = 1"
    ) == [("Grupo", "Sin marca", "Azul")]


def test_scd2_un_cambio_de_categoria_crea_una_version_nueva(bases):
    fuente, dw = bases
    clave_v1 = uno(dw, "SELECT cliente_key FROM dw.fact_ventas WHERE linea_factura_id = 1")
    sql(
        fuente,
        "INSERT INTO sales.customer_categories (customer_category_id, customer_category_name, "
        "last_edited_by) VALUES (2, 'Supermercado', 1);"
        "UPDATE sales.customers SET customer_category_id = 2 WHERE customer_id = 1",
    )

    r = _correr(bases)

    # La última venta es del 2016-01-04: la versión nueva rige desde el día siguiente
    assert r.dw_versiones_nuevas == 1
    assert sql(dw, VERSIONES) == [
        (1, "Tienda", "1900-01-01", "2016-01-04", False),
        (2, "Supermercado", "2016-01-05", "9999-12-31", True),
    ]
    # Las ventas anteriores conservan la categoría que tenía el cliente cuando compró
    assert uno(dw, "SELECT cliente_key FROM dw.fact_ventas WHERE linea_factura_id = 1") == clave_v1


def test_las_ventas_nuevas_usan_la_version_vigente(bases):
    fuente, dw = bases
    dias = ventas.simular(fuente, dias=1, pedidos=2, semilla=7)
    assert dias[0].fecha == date(2016, 1, 5)

    _correr(bases)

    categorias = dict(
        sql(
            dw,
            "SELECT f.fecha_factura::text, string_agg(DISTINCT c.categoria, ',') "
            "FROM dw.fact_ventas f JOIN dw.dim_cliente c ON c.cliente_key = f.cliente_key "
            "GROUP BY 1",
        )
    )
    assert categorias == {"2016-01-04": "Tienda", "2016-01-05": "Supermercado"}


def test_scd1_un_cambio_de_nombre_sobrescribe_todas_las_versiones(bases):
    fuente, dw = bases
    sql(
        fuente,
        "UPDATE sales.customers SET customer_name = 'Cliente Renombrado' WHERE customer_id = 1",
    )

    r = _correr(bases)

    assert r.dw_versiones_nuevas == 0
    assert sql(dw, "SELECT DISTINCT nombre FROM dw.dim_cliente WHERE cliente_id = 1") == [
        ("Cliente Renombrado",)
    ]


def test_renombrar_una_categoria_no_crea_versiones_y_refresca_el_nombre(bases):
    fuente, dw = bases
    sql(
        fuente,
        "UPDATE sales.customer_categories SET customer_category_name = 'Tienda Minorista' "
        "WHERE customer_category_id = 1",
    )

    r = _correr(bases)

    # Renombrar la categoría no es un cambio del cliente: no hay versión nueva
    assert r.dw_versiones_nuevas == 0
    assert [(v, c) for v, c, *_ in sql(dw, VERSIONES)] == [
        (1, "Tienda Minorista"),
        (2, "Supermercado"),
    ]


def test_dos_cambios_antes_de_la_siguiente_venta_no_dejan_versiones_vacias(bases):
    fuente, dw = bases
    sql(fuente, "UPDATE sales.customers SET customer_category_id = 1 WHERE customer_id = 1")
    assert _correr(bases).dw_versiones_nuevas == 1  # versión 3, desde el 2016-01-06

    sql(fuente, "UPDATE sales.customers SET customer_category_id = 2 WHERE customer_id = 1")
    assert _correr(bases).dw_versiones_nuevas == 0  # se corrige la versión 3 en su lugar

    assert sql(dw, VERSIONES)[-1] == (3, "Supermercado", "2016-01-06", "9999-12-31", True)
    assert uno(dw, "SELECT count(*) FROM dw.dim_cliente WHERE cliente_id = 1") == 3


def test_miembro_desconocido_y_reasignacion(bases):
    fuente, dw = bases
    # Un vendedor externo (no es empleado): no está en dim_empleado
    sql(
        fuente,
        "INSERT INTO application.people (person_id, full_name, preferred_name, is_employee, "
        "is_salesperson, last_edited_by) "
        "VALUES (900, 'Vendedor Externo', 'Externo', false, true, 1);"
        "INSERT INTO sales.orders (order_id, customer_id, salesperson_person_id, "
        "contact_person_id, "
        "order_date, expected_delivery_date, is_undersupply_backordered, last_edited_by) "
        "VALUES (900, 1, 900, 1, '2016-01-05', '2016-01-06', false, 1);"
        "INSERT INTO sales.invoices (invoice_id, customer_id, bill_to_customer_id, order_id, "
        "delivery_method_id, contact_person_id, accounts_person_id, salesperson_person_id, "
        "packed_by_person_id, invoice_date, is_credit_note, total_dry_items, total_chiller_items, "
        "last_edited_by) VALUES (900, 1, 1, 900, 1, 1, 1, 900, 1, '2016-01-05', false, 1, 0, 1);"
        "INSERT INTO sales.invoice_lines (invoice_line_id, invoice_id, stock_item_id, description, "
        "package_type_id, quantity, unit_price, tax_rate, tax_amount, line_profit, extended_price, "
        "last_edited_by) VALUES (900, 900, 1, 'Producto', 1, 1, 5.00, 15.000, 0.75, 2.00, 5.75, 1)",
    )

    r = _correr(bases)

    assert r.dw_hechos_con_desconocido == 1
    assert r.reconciliado is True  # el hecho se carga igual: no se pierde la venta
    assert uno(dw, "SELECT vendedor_key FROM dw.fact_ventas WHERE linea_factura_id = 900") == -1

    # La persona pasa a ser empleada: la siguiente ejecución reasigna la clave
    sql(fuente, "UPDATE application.people SET is_employee = true WHERE person_id = 900")
    r = _correr(bases)

    assert r.dw_hechos_con_desconocido == 0
    assert (
        uno(
            dw,
            "SELECT e.nombre_completo FROM dw.fact_ventas f "
            "JOIN dw.dim_empleado e ON e.empleado_key = f.vendedor_key "
            "WHERE f.linea_factura_id = 900",
        )
        == "Vendedor Externo"
    )


def test_reejecutar_no_cambia_el_dw(bases):
    _, dw = bases
    antes = sql(dw, "SELECT * FROM dw.fact_ventas ORDER BY linea_factura_id")
    dimensiones = sql(dw, "SELECT * FROM dw.dim_cliente ORDER BY cliente_key")

    r = _correr(bases)

    assert (r.dw_hechos_nuevos, r.dw_hechos_actualizados, r.dw_versiones_nuevas) == (0, 0, 0)
    assert sql(dw, "SELECT * FROM dw.fact_ventas ORDER BY linea_factura_id") == antes
    assert sql(dw, "SELECT * FROM dw.dim_cliente ORDER BY cliente_key") == dimensiones


def test_validacion_completa_del_dw(bases):
    import psycopg

    fuente, dw = bases
    with psycopg.connect(fuente) as f, psycopg.connect(dw) as d:
        resultados = validar_dw.controles(f, d)
    fallas = [(x.codigo, x.detalle) for x in resultados if not x.ok]
    assert fallas == []
    assert len(resultados) == 11
