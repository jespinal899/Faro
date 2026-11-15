"""Pruebas de mínimo privilegio: cada rol puede hacer su trabajo y nada más.

Se conecta como administrador y asume el rol con `SET ROLE` (opción de conexión), así no
hacen falta contraseñas: los permisos que se evalúan son los del rol asumido.
"""

import psycopg
import pytest
from conftest import RAIZ, sql, uno
from psycopg.conninfo import make_conninfo

from etl.orchestration import pipeline
from simulador import ventas

pytestmark = pytest.mark.integracion

SEGURIDAD = RAIZ / "database" / "security"


def _como(url: str, rol: str) -> str:
    return make_conninfo(url, options=f"-c role={rol}")


@pytest.fixture(scope="module")
def urls(bases):
    fuente, analitica = bases
    sql(fuente, (SEGURIDAD / "roles_fuente.sql").read_text(encoding="utf-8"))
    sql(analitica, (SEGURIDAD / "roles_analitica.sql").read_text(encoding="utf-8"))
    return {
        "etl_lector": _como(fuente, "etl_lector"),
        "wwi_app": _como(fuente, "wwi_app"),
        "faro_etl": _como(analitica, "faro_etl"),
    }


def _denegado(url: str, consulta: str) -> bool:
    try:
        sql(url, consulta)
    except psycopg.errors.InsufficientPrivilege:
        return True
    return False


def test_el_pipeline_funciona_con_los_roles_restringidos(urls):
    r = pipeline.ejecutar(urls["etl_lector"], urls["faro_etl"], modo="inicial", disparador="ci")
    assert (r.estado, r.reconciliado) == ("exitoso", True)
    assert uno(urls["faro_etl"], "SELECT current_user") == "faro_etl"
    assert uno(urls["faro_etl"], "SELECT count(*) FROM stg_ready.ventas") == 2


def test_el_simulador_funciona_con_el_rol_de_la_aplicacion(urls):
    dias = ventas.simular(urls["wwi_app"], dias=1, pedidos=2, semilla=1)
    assert dias[0].pedidos == 2


def test_etl_lector_no_puede_modificar_la_fuente(urls):
    u = urls["etl_lector"]
    assert _denegado(u, "UPDATE sales.customers SET payment_days = 0")
    assert _denegado(u, "DELETE FROM sales.invoice_lines")
    assert _denegado(u, "INSERT INTO warehouse.colors (color_name, last_edited_by) VALUES ('x', 1)")
    assert _denegado(u, "CREATE TABLE sales.intruso (id int)")


def test_wwi_app_solo_inserta_ventas(urls):
    u = urls["wwi_app"]
    assert _denegado(u, "UPDATE sales.invoices SET total_dry_items = 0")
    assert _denegado(u, "DELETE FROM sales.orders")
    assert _denegado(u, "UPDATE sales.customers SET credit_limit = 999999")
    assert _denegado(u, "TRUNCATE sales.invoice_lines")


def test_faro_etl_no_puede_cambiar_la_estructura(urls):
    u = urls["faro_etl"]
    assert _denegado(u, "CREATE TABLE stg_clean.intruso (id int)")
    assert _denegado(u, "DROP TABLE stg_clean.sales_customers")
    assert _denegado(u, "ALTER TABLE audit.etl_execution ADD COLUMN x int")
    assert _denegado(u, "INSERT INTO stg_ready.ref_prioridad_grupo VALUES (99, 1)")
