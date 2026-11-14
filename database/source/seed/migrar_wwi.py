"""Migra el módulo de ventas de WideWorldImporters (SQL Server) a PostgreSQL (wwi_oltp).

Es la "carga semilla" de la base operacional. Se ejecuta una vez por entorno
(local y Neon), pero es IDEMPOTENTE: re-ejecutarla deja exactamente el mismo resultado.

Pasos:
  1. Aplica el esquema (database/source/01_esquema_fuente.sql).
  2. En UNA transacción: vacía las tablas y copia cada una con COPY (carga masiva).
     Si algo falla, no queda nada a medias (todo o nada).
  3. Ajusta las secuencias IDENTITY al ID máximo, para que el sistema genere IDs nuevos.
  4. Reconciliación: compara conteos y sumas de control entre SQL Server y PostgreSQL.
     Si algo no coincide, termina con código 1 y no se considera exitosa.

Uso (desde la raíz del repo, con el SQL Server temporal levantado):
    uv run --group seed python database/source/seed/migrar_wwi.py
"""

from __future__ import annotations

import logging
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import psycopg
import pymssql
from dotenv import load_dotenv
from mapeo_wwi import CONTROLES, TABLAS
from psycopg import sql

RAIZ = Path(__file__).resolve().parents[3]
ESQUEMA_SQL = RAIZ / "database" / "source" / "01_esquema_fuente.sql"
REPORTE = RAIZ / "documentation" / "pruebas" / "reconciliacion-carga-fuente.md"

log = logging.getLogger("migrar_wwi")


def _ident(nombre: str) -> sql.Identifier:
    """'esquema.tabla' -> identificador SQL escapado de forma segura."""
    return sql.Identifier(*nombre.split("."))


def _entorno(url: str) -> str:
    host = urlparse(url).hostname or ""
    return "Neon (producción)" if "neon.tech" in host else f"local ({host})"


def conectar_sqlserver() -> pymssql.Connection:
    return pymssql.connect(
        server=os.getenv("SEED_MSSQL_HOST", "localhost"),
        port=os.getenv("SEED_MSSQL_PORT", "14330"),
        user="sa",
        password=os.environ["MSSQL_SA_PASSWORD"],
        database="WideWorldImporters",
        tds_version="7.4",
        login_timeout=15,
    )


def aplicar_esquema(pg: psycopg.Connection) -> None:
    log.info("Aplicando esquema: %s", ESQUEMA_SQL.relative_to(RAIZ))
    pg.execute(ESQUEMA_SQL.read_text(encoding="utf-8"))
    pg.commit()


def cargar(pg: psycopg.Connection, ms: pymssql.Connection) -> dict[str, int]:
    """Vacía y recarga todas las tablas en UNA transacción. Devuelve filas copiadas por tabla."""
    copiadas: dict[str, int] = {}
    with pg.transaction():
        pg.execute(
            sql.SQL("TRUNCATE {} RESTART IDENTITY").format(
                sql.SQL(", ").join(_ident(t.destino) for t in TABLAS)
            )
        )
        for t in TABLAS:
            inicio = time.perf_counter()
            ms_cur = ms.cursor()
            ms_cur.execute(t.consulta_origen)
            copia = sql.SQL("COPY {} ({}) FROM STDIN").format(
                _ident(t.destino), sql.SQL(", ").join(map(sql.Identifier, t.columnas_destino))
            )
            n = 0
            with pg.cursor() as cur, cur.copy(copia) as copy:
                while filas := ms_cur.fetchmany(10_000):
                    for fila in filas:
                        copy.write_row(fila)
                    n += len(filas)
            copiadas[t.destino] = n
            log.info(
                "  %-36s %9s filas  (%.1f s)", t.destino, f"{n:,}", time.perf_counter() - inicio
            )

        # Las secuencias IDENTITY continúan después del ID más alto cargado
        for t in TABLAS:
            pk = t.columnas_destino[0]
            pg.execute(
                sql.SQL(
                    "SELECT setval(pg_get_serial_sequence({tabla}, {pk}), "
                    "COALESCE((SELECT MAX({col}) FROM {ident}), 1))"
                ).format(
                    tabla=sql.Literal(t.destino),
                    pk=sql.Literal(pk),
                    col=sql.Identifier(pk),
                    ident=_ident(t.destino),
                )
            )
    pg.execute("ANALYZE")  # estadísticas frescas para el planificador de consultas
    return copiadas


def reconciliar(pg: psycopg.Connection, ms: pymssql.Connection) -> tuple[list, list]:
    """Compara conteos por tabla y sumas de control. Devuelve (conteos, controles)."""
    ms_cur = ms.cursor()
    conteos = []
    for t in TABLAS:
        ms_cur.execute(f"SELECT COUNT_BIG(*) FROM {t.origen}")
        origen = ms_cur.fetchone()[0]
        destino = pg.execute(
            sql.SQL("SELECT COUNT(*) FROM {}").format(_ident(t.destino))
        ).fetchone()[0]
        conteos.append((t.origen, t.destino, origen, destino, origen == destino))
    controles = []
    for nombre, q_ms, q_pg in CONTROLES:
        ms_cur.execute(q_ms)
        origen = ms_cur.fetchone()[0]
        destino = pg.execute(q_pg).fetchone()[0]
        controles.append((nombre, origen, destino, origen == destino))
    return conteos, controles


def escribir_reporte(entorno: str, duracion: float, conteos: list, controles: list) -> None:
    ok = all(c[-1] for c in conteos) and all(c[-1] for c in controles)
    lineas = [
        "# Reconciliación de la carga de la fuente (WWI → wwi_oltp)",
        "",
        "Generado automáticamente por `database/source/seed/migrar_wwi.py`.",
        "",
        f"- **Fecha (UTC):** {datetime.now(UTC):%Y-%m-%d %H:%M:%S}",
        f"- **Entorno destino:** {entorno}",
        f"- **Duración:** {duracion:.1f} s",
        f"- **Resultado:** {'✅ RECONCILIADO' if ok else '❌ CON DIFERENCIAS'}",
        "",
        "## Conteo de filas por tabla",
        "",
        "| Origen (SQL Server) | Destino (PostgreSQL) | Filas origen | Filas destino "
        "| ¿Coincide? |",
        "|---|---|---:|---:|:---:|",
        *(
            f"| `{o}` | `{d}` | {a:,} | {b:,} | {'✅' if m else '❌'} |"
            for o, d, a, b, m in conteos
        ),
        "",
        "## Sumas de control",
        "",
        "| Control | Origen | Destino | ¿Coincide? |",
        "|---|---:|---:|:---:|",
        *(f"| {n} | {a:,} | {b:,} | {'✅' if m else '❌'} |" for n, a, b, m in controles),
        "",
    ]
    REPORTE.parent.mkdir(parents=True, exist_ok=True)
    REPORTE.write_text("\n".join(lineas), encoding="utf-8")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    load_dotenv(RAIZ / ".env")
    url = os.getenv("SOURCE_DATABASE_URL")
    if not url or not os.getenv("MSSQL_SA_PASSWORD"):
        log.error("Faltan SOURCE_DATABASE_URL o MSSQL_SA_PASSWORD en .env")
        return 1

    entorno = _entorno(url)
    log.info("Destino: base wwi_oltp en %s", entorno)
    inicio = time.perf_counter()
    try:
        with psycopg.connect(url, connect_timeout=15) as pg, conectar_sqlserver() as ms:
            pg.execute("SET TIME ZONE 'UTC'")
            aplicar_esquema(pg)
            log.info("Copiando tablas (una sola transacción)...")
            cargar(pg, ms)
            log.info("Reconciliando origen vs destino...")
            conteos, controles = reconciliar(pg, ms)
    except (psycopg.Error, pymssql.Error) as error:
        # Sin cadenas de conexión en el mensaje: no se exponen credenciales
        log.error("La migración falló y se revirtió por completo: %s", error)
        return 1

    duracion = time.perf_counter() - inicio
    escribir_reporte(entorno, duracion, conteos, controles)
    diferencias = [c for c in conteos if not c[-1]] + [c for c in controles if not c[-1]]
    total = sum(c[3] for c in conteos)
    if diferencias:
        log.error("Reconciliación con %d diferencia(s). Ver %s", len(diferencias), REPORTE.name)
        return 1
    log.info(
        "OK: %s filas migradas y reconciliadas en %.1f s. Reporte: %s",
        f"{total:,}",
        duracion,
        REPORTE.relative_to(RAIZ),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
