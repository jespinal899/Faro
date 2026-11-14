"""Pruebas del script de verificación de conexión.

- Pruebas unitarias: no necesitan base de datos.
- Pruebas de integración (marca `integracion`): se conectan a PostgreSQL.
  En local usan el contenedor de Docker (variables de .env); en GitHub Actions
  usan un PostgreSQL 17 temporal que crea el propio pipeline.
"""

import os

import psycopg
import pytest
import verificar_conexion as vc
from dotenv import load_dotenv

load_dotenv()

BASES_ESPERADAS = [
    ("SOURCE_DATABASE_URL", "wwi_oltp"),
    ("ANALYTICS_DATABASE_URL", "faro_analytics"),
]


# ---------------------------------------------------------------- unitarias


def test_variable_faltante_devuelve_false(monkeypatch, capsys):
    monkeypatch.delenv("VARIABLE_QUE_NO_EXISTE", raising=False)

    assert vc.verificar("Prueba", "VARIABLE_QUE_NO_EXISTE") is False
    assert "no está definida" in capsys.readouterr().out


def test_error_de_conexion_no_expone_la_contrasena(monkeypatch, capsys):
    """Si la conexión falla, el mensaje no debe mostrar la contraseña (seguridad)."""
    monkeypatch.setenv("URL_INVALIDA", "postgresql://usuario:ClaveSecreta123@127.0.0.1:1/nada")

    assert vc.verificar("Prueba", "URL_INVALIDA") is False
    assert "ClaveSecreta123" not in capsys.readouterr().out


# ------------------------------------------------------------- integración


def _url_o_saltar(variable: str) -> str:
    url = os.getenv(variable)
    if not url:
        pytest.skip(f"{variable} no está definida (¿falta el archivo .env?)")
    return url


@pytest.mark.integracion
@pytest.mark.parametrize(("variable", "base_esperada"), BASES_ESPERADAS)
def test_conecta_a_la_base_correcta(variable, base_esperada):
    with psycopg.connect(_url_o_saltar(variable), connect_timeout=10) as conn:
        base = conn.execute("SELECT current_database()").fetchone()[0]

    assert base == base_esperada


@pytest.mark.integracion
@pytest.mark.parametrize(("variable", "_base"), BASES_ESPERADAS)
def test_version_mayor_es_postgresql_17(variable, _base):
    """Misma versión mayor que en Neon (producción): evita diferencias entre entornos."""
    with psycopg.connect(_url_o_saltar(variable), connect_timeout=10) as conn:
        version = conn.info.server_version  # p. ej. 171100 = 17.11

    assert version // 10000 == 17


@pytest.mark.integracion
def test_script_completo_termina_sin_errores():
    for variable, _ in BASES_ESPERADAS:
        _url_o_saltar(variable)

    assert vc.main() == 0
