"""Pruebas del esquema de la base operacional (wwi_oltp) y del mapeo de la migración.

- Unitarias: validan el mapeo origen -> destino de migrar_wwi.py sin base de datos.
- Integración: aplican el esquema (dos veces, para probar idempotencia) y verifican
  tablas, columnas y el trigger de auditoría. No modifican datos existentes.
"""

import os
from pathlib import Path

import migrar_wwi as mig
import psycopg
import pytest
from dotenv import load_dotenv

load_dotenv()

ESQUEMA = Path(__file__).resolve().parents[1] / "database" / "source" / "01_esquema_fuente.sql"

# Columnas que NO deben existir en la fuente migrada (minimización de datos personales)
COLUMNAS_SENSIBLES = {
    "hashed_password",
    "logon_name",
    "email_address",
    "phone_number",
    "fax_number",
    "photo",
    "website_url",
    "delivery_address_line1",
    "postal_address_line1",
    "confirmed_received_by",
}


# ---------------------------------------------------------------- unitarias


def test_mapeo_sin_columnas_duplicadas():
    for tabla in mig.TABLAS:
        assert len(set(tabla.columnas_destino)) == len(tabla.columnas_destino), tabla.destino


def test_mapeo_no_migra_datos_sensibles():
    for tabla in mig.TABLAS:
        assert not COLUMNAS_SENSIBLES & set(tabla.columnas_destino), tabla.destino


def test_todas_las_tablas_tienen_auditoria():
    for tabla in mig.TABLAS:
        assert tabla.columnas_destino[-2:] == ["last_edited_by", "last_edited_when"], tabla.destino


def test_orden_de_carga_respeta_dependencias():
    orden = [t.destino for t in mig.TABLAS]
    assert orden[0] == "application.people"  # todas las tablas referencian a people
    assert orden.index("sales.customers") < orden.index("sales.orders")
    assert orden.index("sales.orders") < orden.index("sales.order_lines")
    assert orden.index("sales.orders") < orden.index("sales.invoices")
    assert orden.index("sales.invoices") < orden.index("sales.invoice_lines")
    assert orden.index("warehouse.stock_items") < orden.index("sales.invoice_lines")


# ------------------------------------------------------------- integración


@pytest.fixture(scope="module")
def conexion():
    url = os.getenv("SOURCE_DATABASE_URL")
    if not url:
        pytest.skip("SOURCE_DATABASE_URL no está definida (¿falta el archivo .env?)")
    with psycopg.connect(url, connect_timeout=10) as conn:
        script = ESQUEMA.read_text(encoding="utf-8")
        conn.execute(script)
        conn.execute(script)  # segunda vez: debe ser idempotente (sin errores)
        conn.commit()
        yield conn


@pytest.mark.integracion
def test_esquema_crea_exactamente_las_tablas_del_mapeo(conexion):
    filas = conexion.execute(
        "SELECT table_schema || '.' || table_name FROM information_schema.tables "
        "WHERE table_schema IN ('application', 'sales', 'warehouse') AND table_type = 'BASE TABLE'"
    ).fetchall()
    assert {f[0] for f in filas} == {t.destino for t in mig.TABLAS}


@pytest.mark.integracion
@pytest.mark.parametrize("tabla", mig.TABLAS, ids=lambda t: t.destino)
def test_columnas_del_mapeo_coinciden_con_el_esquema(conexion, tabla):
    esquema, nombre = tabla.destino.split(".")
    filas = conexion.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = %s AND table_name = %s ORDER BY ordinal_position",
        (esquema, nombre),
    ).fetchall()
    assert [f[0] for f in filas] == tabla.columnas_destino


@pytest.mark.integracion
def test_trigger_actualiza_last_edited_when(conexion):
    with conexion.transaction(force_rollback=True):  # no deja rastro en la base
        conexion.execute(
            "INSERT INTO application.people (person_id, full_name, preferred_name, is_employee, "
            "is_salesperson, last_edited_by, last_edited_when) "
            "VALUES (999999, 'Prueba', 'Prueba', false, false, 999999, '2000-01-01')"
        )
        conexion.execute(
            "UPDATE application.people SET preferred_name = 'Cambio' WHERE person_id = 999999"
        )
        valor = conexion.execute(
            "SELECT last_edited_when FROM application.people WHERE person_id = 999999"
        ).fetchone()[0]
    assert valor.year > 2000
