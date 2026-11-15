"""Pruebas del simulador de ventas y de su paso por el ETL."""

from datetime import date

import pytest
from conftest import sql, uno

from etl.orchestration import pipeline
from simulador import ventas

SIMULADAS = (
    "FROM sales.invoice_lines il JOIN sales.invoices i USING (invoice_id) "
    "WHERE il.last_edited_by = (SELECT person_id FROM application.people "
    f"WHERE full_name = '{ventas.NOMBRE_SIMULADOR}')"
)


def test_siguiente_dia_habil_salta_el_domingo():
    assert ventas.siguiente_dia_habil(date(2016, 6, 3)) == date(2016, 6, 4)  # viernes -> sábado
    assert ventas.siguiente_dia_habil(date(2016, 6, 4)) == date(2016, 6, 6)  # sábado -> lunes


@pytest.mark.integracion
def test_simula_los_dias_habiles_siguientes(bases):
    fuente, analitica = bases
    assert pipeline.ejecutar(fuente, analitica, modo="inicial", disparador="ci").estado == "exitoso"

    dias = ventas.simular(fuente, dias=3, pedidos=4, semilla=1)

    # La última factura de los datos de prueba es del lunes 4-ene-2016
    assert [d.fecha for d in dias] == [date(2016, 1, 5), date(2016, 1, 6), date(2016, 1, 7)]
    assert [d.pedidos for d in dias] == [4, 4, 4]
    assert uno(fuente, f"SELECT count(DISTINCT i.invoice_id) {SIMULADAS}") == 12
    assert uno(fuente, f"SELECT sum(il.extended_price) {SIMULADAS}") == sum(
        d.venta_bruta for d in dias
    )


@pytest.mark.integracion
def test_los_importes_simulados_cumplen_las_reglas_de_la_fuente(bases):
    fuente, _ = bases
    incoherentes = uno(
        fuente,
        f"SELECT count(*) {SIMULADAS} AND (il.quantity <= 0 "
        "OR il.extended_price <> il.quantity * il.unit_price + il.tax_amount "
        "OR il.tax_amount <> round(il.quantity * il.unit_price * il.tax_rate / 100, 2))",
    )
    assert incoherentes == 0


@pytest.mark.integracion
def test_no_vende_domingos_y_el_sabado_vende_menos(bases):
    fuente, _ = bases
    ventas.simular(fuente, dias=6, pedidos=10, semilla=2)  # vie 8, sáb 9, lun 11 ... jue 14

    por_dia = dict(
        sql(
            fuente,
            "SELECT invoice_date::text, count(*) FROM sales.invoices "
            "WHERE invoice_date >= '2016-01-08' GROUP BY 1",
        )
    )
    assert "2016-01-10" not in por_dia  # domingo
    assert por_dia["2016-01-08"] == 10
    assert por_dia["2016-01-09"] == 4  # sábado: 42 % de un día hábil


@pytest.mark.integracion
def test_el_etl_carga_lo_simulado_y_lo_identifica(bases):
    fuente, analitica = bases
    r = pipeline.ejecutar(fuente, analitica, disparador="ci")

    assert (r.estado, r.rechazadas, r.reconciliado) == ("exitoso", 0, True)
    simuladas = uno(fuente, f"SELECT count(*) {SIMULADAS}")
    assert uno(analitica, "SELECT count(*) FROM stg_ready.ventas WHERE es_simulado") == simuladas
    assert uno(analitica, "SELECT count(*) FROM stg_ready.ventas WHERE NOT es_simulado") == 2


@pytest.mark.integracion
def test_registro_invalido_simulado_termina_en_cuarentena(bases):
    fuente, analitica = bases
    ventas.simular(fuente, dias=1, pedidos=2, semilla=3, registro_invalido=True)

    r = pipeline.ejecutar(fuente, analitica, disparador="ci")

    assert (r.estado, r.rechazadas, r.reconciliado) == ("exitoso", 1, True)
    reglas = sql(
        analitica,
        "SELECT rule_code FROM stg_quarantine.registro_rechazado "
        "WHERE resolved_at IS NULL ORDER BY 1",
    )
    assert reglas == [("K01",), ("V01",)]
