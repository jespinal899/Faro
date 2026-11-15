"""Pruebas de la zona READY: integración sin multiplicar filas ni importes."""

from decimal import Decimal

import pytest
from conftest import sql, uno

from etl.orchestration import pipeline

pytestmark = pytest.mark.integracion


@pytest.fixture(scope="module")
def analitica(bases):
    fuente, url = bases
    # Un segundo grupo para el producto: debe repartirse, no duplicarse
    sql(
        fuente,
        "INSERT INTO warehouse.stock_groups (stock_group_id, stock_group_name, last_edited_by) "
        "VALUES (7, 'USB Novelties', 1);"
        "INSERT INTO warehouse.stock_item_stock_groups "
        "(stock_item_stock_group_id, stock_item_id, stock_group_id, last_edited_by) "
        "VALUES (2, 1, 7, 1)",
    )
    assert pipeline.ejecutar(fuente, url, modo="inicial", disparador="ci").estado == "exitoso"
    return url


def test_ventas_tiene_una_fila_por_linea_de_factura(analitica):
    lineas = uno(analitica, "SELECT count(*) FROM stg_clean.sales_invoice_lines")
    assert uno(analitica, "SELECT count(*) FROM stg_ready.ventas") == lineas
    assert uno(analitica, "SELECT count(DISTINCT linea_factura_id) FROM stg_ready.ventas") == lineas


def test_medidas_derivadas(analitica):
    fila = sql(
        analitica,
        "SELECT venta_bruta, impuesto, venta_neta, utilidad, costo, es_venta_bajo_costo, "
        "fecha_pedido::text, ciudad_id, es_simulado "
        "FROM stg_ready.ventas WHERE linea_factura_id = 2",
    )[0]
    assert fila == (
        Decimal("230.00"), Decimal("30.00"), Decimal("200.00"), Decimal("-5.00"),
        Decimal("205.00"), True, "2016-01-04", 1, False,
    )  # fmt: skip


def test_grupo_principal_es_el_mas_especifico(analitica):
    # El producto está en 'Grupo' (sin prioridad -> 999) y en 'USB Novelties' (prioridad 1)
    assert sql(analitica, "SELECT grupo_principal, cantidad_grupos FROM stg_ready.productos") == [
        ("USB Novelties", 2)
    ]


def test_ventas_por_grupo_no_se_duplican(analitica):
    total = uno(analitica, "SELECT sum(venta_bruta) FROM stg_ready.ventas")
    por_principal = uno(
        analitica,
        "SELECT sum(v.venta_bruta) FROM stg_ready.ventas v "
        "JOIN stg_ready.productos p USING (producto_id)",
    )
    ponderado = uno(
        analitica,
        "SELECT round(sum(v.venta_bruta * b.factor_ponderacion), 2) FROM stg_ready.ventas v "
        "JOIN stg_ready.producto_grupo b USING (producto_id)",
    )
    sin_ponderar = uno(
        analitica,
        "SELECT sum(v.venta_bruta) FROM stg_ready.ventas v "
        "JOIN stg_ready.producto_grupo b USING (producto_id)",
    )
    assert por_principal == total
    assert ponderado == total
    assert sin_ponderar == 2 * total  # lo que pasaría sin el factor: el error que se evita


def test_nulos_resueltos_segun_su_causa(analitica):
    assert sql(
        analitica,
        "SELECT nombre, categoria, grupo_compra, politica_credito, limite_credito, es_casa_matriz "
        "FROM stg_ready.clientes",
    ) == [("Cliente Uno", "Tienda", "Independiente", "Gestionado por casa matriz", None, False)]
    assert uno(analitica, "SELECT marca FROM stg_ready.productos") == "Sin marca"


def test_geografia_y_empleados(analitica):
    assert sql(
        analitica, "SELECT ciudad, estado, territorio_venta, pais FROM stg_ready.geografia"
    ) == [("Ciudad", "Estado", "Territorio", "Pais")]
    assert sql(analitica, "SELECT nombre_completo, es_vendedor FROM stg_ready.empleados") == [
        ("Ana Vendedora", True)
    ]
