"""Pruebas de integración del pipeline de staging (criterios de aceptación de la guía).

Crean dos bases TEMPORALES (fuente y analítica) con datos mínimos, así que nunca tocan
los datos reales. Las pruebas forman un escenario y se ejecutan en orden:

  carga inicial -> idempotencia -> incremental -> calidad y cuarentena ->
  corrección y reintento -> fecha futura -> recuperación ante falla -> candado
"""

import psycopg
import pytest
from conftest import sql, uno

from etl.config import TABLAS
from etl.orchestration import pipeline

pytestmark = pytest.mark.integracion


def _correr(bases, modo="incremental"):
    return pipeline.ejecutar(*bases, modo=modo, disparador="ci")


# ------------------------------------------------------------ carga inicial


def test_carga_inicial_copia_todo_y_reconcilia(bases):
    fuente, analitica = bases
    r = _correr(bases, "inicial")

    assert r.estado == "exitoso"
    assert r.reconciliado is True
    assert r.rechazadas == 0
    for t in TABLAS:
        en_fuente = uno(fuente, f"SELECT count(*) FROM {t.origen}")
        assert uno(analitica, f"SELECT count(*) FROM stg_raw.{t.staging}") == en_fuente
        assert uno(analitica, f"SELECT count(*) FROM stg_clean.{t.staging}") == en_fuente
    assert r.leidas == r.insertadas == 19


def test_auditoria_registra_ejecucion_pasos_y_watermarks(bases):
    _, analitica = bases
    estado, leidas, reconciliada = sql(
        analitica,
        "SELECT status, rows_read, reconciled FROM audit.etl_execution ORDER BY 1 DESC LIMIT 1",
    )[0]
    assert (estado, leidas, reconciliada) == ("exitoso", 19, True)
    pasos = dict(sql(analitica, "SELECT step, count(*) FROM audit.etl_step GROUP BY 1"))
    assert pasos == {"extract": 17, "clean": 17, "reconcile": 17}
    assert uno(analitica, "SELECT count(*) FROM audit.watermark") == 17
    assert uno(analitica, "SELECT count(*) FROM audit.dq_rule") >= 17


def test_limpieza_de_textos_y_marcas_de_calidad(bases):
    _, analitica = bases
    assert uno(analitica, "SELECT customer_name FROM stg_clean.sales_customers") == "Cliente Uno"
    # raw conserva el dato original, sin limpiar
    assert uno(analitica, "SELECT customer_name FROM stg_raw.sales_customers") == "  Cliente   Uno "
    flags = dict(
        sql(analitica, "SELECT invoice_line_id, _dq_flags FROM stg_clean.sales_invoice_lines")
    )
    assert flags == {1: [], 2: ["V04"]}  # la línea 2 se vendió bajo costo: entra, marcada


# ------------------------------------------------------------- idempotencia


def test_reejecutar_no_duplica_ni_altera(bases):
    _, analitica = bases
    antes = sql(analitica, "SELECT * FROM stg_clean.sales_invoice_lines ORDER BY 1")
    raw_antes = uno(analitica, "SELECT count(*) FROM stg_raw.sales_invoice_lines")

    r = _correr(bases)

    assert r.estado == "exitoso"
    assert (r.insertadas, r.actualizadas, r.rechazadas) == (0, 0, 0)
    assert sql(analitica, "SELECT * FROM stg_clean.sales_invoice_lines ORDER BY 1") == antes
    assert uno(analitica, "SELECT count(*) FROM stg_raw.sales_invoice_lines") == raw_antes


# -------------------------------------------------------------- incremental


def test_incremental_detecta_altas_y_cambios(bases):
    fuente, analitica = bases
    sql(fuente, "UPDATE sales.customers SET payment_days = 30 WHERE customer_id = 1")
    sql(
        fuente,
        "INSERT INTO sales.invoice_lines (invoice_line_id, invoice_id, stock_item_id, description,"
        " package_type_id, quantity, unit_price, tax_rate, tax_amount, line_profit, extended_price,"
        " last_edited_by) VALUES (3, 1, 1, 'Producto', 1, 4, 5.00, 15.000, 3.00, 8.00, 23.00, 1)",
    )

    r = _correr(bases)

    assert (r.estado, r.insertadas, r.actualizadas, r.rechazadas) == ("exitoso", 1, 1, 0)
    assert uno(analitica, "SELECT payment_days FROM stg_clean.sales_customers") == 30
    assert uno(analitica, "SELECT count(*) FROM stg_clean.sales_invoice_lines") == 3
    # raw conserva las dos versiones del cliente (historia)
    assert uno(analitica, "SELECT count(*) FROM stg_raw.sales_customers") == 2


# ---------------------------------------------------- calidad y cuarentena


def test_registro_invalido_va_a_cuarentena_y_no_a_clean(bases):
    fuente, analitica = bases
    # Cantidad 0 (V01) e importe inconsistente (K01)
    sql(
        fuente,
        "INSERT INTO sales.invoice_lines (invoice_line_id, invoice_id, stock_item_id, description,"
        " package_type_id, quantity, unit_price, tax_rate, tax_amount, line_profit, extended_price,"
        " last_edited_by) VALUES (4, 1, 1, 'Producto', 1, 0, 5.00, 15.000, 0.00, 0.00, 99.00, 1)",
    )

    r = _correr(bases)

    assert (r.estado, r.rechazadas, r.insertadas) == ("exitoso", 1, 0)
    assert r.reconciliado is True  # fuente = clean + cuarentena
    assert (
        uno(
            analitica,
            "SELECT count(*) FROM stg_clean.sales_invoice_lines WHERE invoice_line_id = 4",
        )
        == 0
    )
    rechazos = sql(
        analitica,
        "SELECT rule_code, payload->>'quantity' FROM stg_quarantine.registro_rechazado "
        "WHERE natural_key = 4 AND resolved_at IS NULL ORDER BY 1",
    )
    assert rechazos == [("K01", "0"), ("V01", "0")]
    fallas = uno(
        analitica,
        "SELECT rows_failed FROM audit.dq_result WHERE rule_code = 'V01' "
        "AND source_table = 'sales.invoice_lines' ORDER BY execution_id DESC LIMIT 1",
    )
    assert fallas == 1


def test_registro_corregido_en_la_fuente_sale_de_cuarentena(bases):
    fuente, analitica = bases
    sql(
        fuente,
        "UPDATE sales.invoice_lines SET quantity = 2, tax_amount = 1.50, extended_price = 11.50 "
        "WHERE invoice_line_id = 4",
    )

    r = _correr(bases)

    assert (r.estado, r.insertadas, r.rechazadas) == ("exitoso", 1, 0)
    assert (
        uno(
            analitica,
            "SELECT quantity FROM stg_clean.sales_invoice_lines WHERE invoice_line_id = 4",
        )
        == 2
    )
    pendientes = uno(
        analitica,
        "SELECT count(*) FROM stg_quarantine.registro_rechazado WHERE resolved_at IS NULL",
    )
    assert pendientes == 0


def test_fecha_futura_va_a_cuarentena_y_no_adelanta_el_watermark(bases):
    fuente, analitica = bases
    sql(
        fuente,
        "UPDATE sales.invoice_lines SET last_edited_when = now() + interval '30 days' "
        "WHERE invoice_line_id = 3",
    )

    r = _correr(bases)

    assert (r.estado, r.rechazadas) == ("exitoso", 1)
    assert uno(
        analitica,
        "SELECT last_value < now() + interval '1 hour' FROM audit.watermark "
        "WHERE source_table = 'sales.invoice_lines'",
    )
    # Se corrige en la fuente (el trigger pone la hora actual) y vuelve a entrar
    sql(fuente, "UPDATE sales.invoice_lines SET description = 'Producto' WHERE invoice_line_id = 3")
    sql(fuente, "UPDATE sales.invoice_lines SET last_edited_when = now() WHERE invoice_line_id = 3")
    assert _correr(bases).rechazadas == 0
    assert (
        uno(
            analitica,
            "SELECT count(*) FROM stg_quarantine.registro_rechazado WHERE resolved_at IS NULL",
        )
        == 0
    )


# ------------------------------------------------------------- recuperación


def test_falla_a_mitad_revierte_todo_y_el_reintento_se_recupera(bases, monkeypatch):
    fuente, analitica = bases
    sql(fuente, "UPDATE sales.customers SET payment_days = 45 WHERE customer_id = 1")
    sql(fuente, "UPDATE sales.invoices SET total_dry_items = 9 WHERE invoice_id = 1")
    watermarks = sql(analitica, "SELECT source_table, last_value FROM audit.watermark ORDER BY 1")
    raw_antes = uno(analitica, "SELECT count(*) FROM stg_raw.sales_customers")

    original = pipeline.limpiar_tabla

    def falla_en_facturas(dst, tabla, columnas, batch_id):
        if tabla.origen == "sales.invoices":  # clientes ya se procesó: debe revertirse
            raise RuntimeError("Falla simulada a mitad de la carga")
        return original(dst, tabla, columnas, batch_id)

    monkeypatch.setattr(pipeline, "limpiar_tabla", falla_en_facturas)
    r = _correr(bases)

    assert r.estado == "fallido"
    estado, error = sql(
        analitica,
        "SELECT status, error_detail FROM audit.etl_execution WHERE execution_id = %s",
        (r.execution_id,),
    )[0]
    assert estado == "fallido" and "Falla simulada" in error
    # Nada quedó a medias: ni datos, ni raw, ni watermarks
    assert uno(analitica, "SELECT payment_days FROM stg_clean.sales_customers") == 30
    assert uno(analitica, "SELECT count(*) FROM stg_raw.sales_customers") == raw_antes
    assert (
        sql(analitica, "SELECT source_table, last_value FROM audit.watermark ORDER BY 1")
        == watermarks
    )

    # Reintento sin la falla: procesa el mismo rango y queda consistente
    monkeypatch.undo()
    r = _correr(bases)

    assert (r.estado, r.actualizadas, r.reconciliado) == ("exitoso", 2, True)
    assert uno(analitica, "SELECT payment_days FROM stg_clean.sales_customers") == 45
    assert uno(analitica, "SELECT total_dry_items FROM stg_clean.sales_invoices") == 9


def test_no_permite_dos_ejecuciones_simultaneas(bases):
    _, analitica = bases
    with psycopg.connect(analitica, autocommit=True) as otra:
        otra.execute(f"SELECT pg_advisory_lock({pipeline.CANDADO})")
        with pytest.raises(pipeline.EjecucionEnCurso):
            _correr(bases)
