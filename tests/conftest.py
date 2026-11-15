"""Utilidades compartidas por las pruebas de integración.

`bases` crea dos bases TEMPORALES (fuente y analítica) por cada archivo de pruebas, con los
esquemas del proyecto y datos mínimos. Así las pruebas nunca tocan los datos reales.
"""

import os
import uuid
from pathlib import Path

import psycopg
import pytest
from dotenv import load_dotenv
from psycopg.conninfo import make_conninfo

load_dotenv()

RAIZ = Path(__file__).resolve().parents[1]
ESQUEMAS_FUENTE = sorted((RAIZ / "database" / "source").glob("*.sql"))
ESQUEMAS_STAGING = sorted((RAIZ / "database" / "staging").glob("*.sql"))
DATOS = RAIZ / "tests" / "datos" / "fuente_minima.sql"


class Bases(tuple):
    """(url_fuente, url_analitica). Oculta las cadenas de conexión en los reportes de pytest."""

    def __repr__(self) -> str:
        return "Bases(<oculto>)"


@pytest.fixture(scope="module")
def bases():
    url = os.getenv("ANALYTICS_DATABASE_URL")
    if not url:
        pytest.skip("ANALYTICS_DATABASE_URL no está definida")
    if "neon.tech" in url:
        pytest.skip("Estas pruebas crean bases temporales: solo corren en local o en CI")

    sufijo = uuid.uuid4().hex[:8]
    nombres = {"fuente": f"faro_test_src_{sufijo}", "analitica": f"faro_test_ana_{sufijo}"}
    with psycopg.connect(url, autocommit=True) as admin:
        for nombre in nombres.values():
            admin.execute(f'CREATE DATABASE "{nombre}"')
    urls = {k: make_conninfo(url, dbname=v) for k, v in nombres.items()}

    with psycopg.connect(urls["fuente"]) as c:
        for archivo in ESQUEMAS_FUENTE:
            c.execute(archivo.read_text(encoding="utf-8"))
        c.execute(DATOS.read_text(encoding="utf-8"))
    with psycopg.connect(urls["analitica"]) as c:
        for archivo in ESQUEMAS_STAGING:
            c.execute(archivo.read_text(encoding="utf-8"))

    yield Bases((urls["fuente"], urls["analitica"]))

    with psycopg.connect(url, autocommit=True) as admin:
        for nombre in nombres.values():
            admin.execute(f'DROP DATABASE IF EXISTS "{nombre}" WITH (FORCE)')


def sql(url: str, consulta: str, parametros=None):
    """Ejecuta una consulta y devuelve sus filas (o None si no devuelve nada)."""
    with psycopg.connect(url) as c:
        cur = c.execute(consulta, parametros)
        return cur.fetchall() if cur.description else None


def uno(url: str, consulta: str, parametros=None):
    """Primer valor de la primera fila."""
    return sql(url, consulta, parametros)[0][0]
