"""Acceso a la base desde la API.

- Una conexión por solicitud (la API corre en funciones serverless de Vercel).
- Compatible con el pooler de Neon (PgBouncer en modo transacción): sin sentencias
  preparadas (prepare_threshold=None) y los ajustes van con SET LOCAL dentro de la
  transacción, nunca a nivel de sesión.
- Las consultas de datos corren en una transacción de SOLO LECTURA y con un tiempo máximo,
  para que una consulta pesada no bloquee la función.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row

from .config import config

TIEMPO_MAXIMO_CONSULTA = "8s"


def _conectar() -> psycopg.Connection:
    return psycopg.connect(
        config().database_url,
        connect_timeout=15,
        prepare_threshold=None,
        row_factory=dict_row,
    )


@contextmanager
def lectura() -> Iterator[psycopg.Connection]:
    """Conexión en una transacción de solo lectura con tiempo máximo por consulta."""
    with _conectar() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        conn.execute(f"SET LOCAL statement_timeout = '{TIEMPO_MAXIMO_CONSULTA}'")
        conn.execute("SET LOCAL TIME ZONE 'UTC'")
        yield conn


@contextmanager
def escritura() -> Iterator[psycopg.Connection]:
    """Conexión para las pocas escrituras de la API (control de inicio de sesión)."""
    with _conectar() as conn:
        conn.execute(f"SET LOCAL statement_timeout = '{TIEMPO_MAXIMO_CONSULTA}'")
        yield conn
