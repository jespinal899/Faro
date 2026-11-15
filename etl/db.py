"""Conexiones a PostgreSQL con reintentos.

Neon suspende el cómputo tras 5 minutos sin uso: la primera conexión puede tardar o
fallar mientras "despierta". Por eso se reintenta con espera creciente.
"""

from __future__ import annotations

import logging
import time

import psycopg

log = logging.getLogger("etl.db")

INTENTOS = 3
ESPERA_INICIAL_S = 2.0


def conectar(url: str, *, autocommit: bool = False, espera_s: float = ESPERA_INICIAL_S):
    """Abre una conexión en UTC. Reintenta fallas de conexión (no errores de SQL)."""
    ultimo: Exception | None = None
    for intento in range(1, INTENTOS + 1):
        try:
            conn = psycopg.connect(url, connect_timeout=20, autocommit=autocommit)
            conn.execute("SET TIME ZONE 'UTC'")
            if not autocommit:
                conn.commit()
            return conn
        except psycopg.OperationalError as error:
            ultimo = error
            if intento < INTENTOS:
                espera = espera_s * 2 ** (intento - 1)
                log.warning(
                    "Conexión fallida (intento %d/%d); reintento en %.0f s",
                    intento,
                    INTENTOS,
                    espera,
                )
                time.sleep(espera)
    raise ultimo
