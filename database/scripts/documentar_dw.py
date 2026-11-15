"""Genera el diccionario de datos del Data Warehouse (esquema dw) desde la base REAL.

Lee del catálogo de PostgreSQL las tablas, columnas, tipos, nulos, claves, descripciones y
conteos, y escribe documentation/modelos/diccionario-dw.md. No se edita a mano.

Uso:
    uv run python database/scripts/documentar_dw.py
"""

from __future__ import annotations

import os
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import psycopg
from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parents[2]
SALIDA = RAIZ / "documentation" / "modelos" / "diccionario-dw.md"

# Orden de presentación: el hecho primero, luego dimensiones y el puente
ORDEN = (
    "fact_ventas", "dim_fecha", "dim_cliente", "dim_producto", "dim_empleado",
    "dim_geografia", "dim_grupo_producto", "puente_producto_grupo",
)  # fmt: skip

SQL_COLUMNAS = """
SELECT c.relname, a.attname, format_type(a.atttypid, a.atttypmod), NOT a.attnotnull,
       col_description(c.oid, a.attnum)
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped
WHERE c.relkind = 'r' AND n.nspname = 'dw'
ORDER BY c.relname, a.attnum
"""

SQL_CLAVES = """
SELECT con.conrelid::regclass::text, con.contype, a.attname, con.confrelid::regclass::text
FROM pg_constraint con
CROSS JOIN LATERAL unnest(con.conkey) AS k(attnum)
JOIN pg_attribute a ON a.attrelid = con.conrelid AND a.attnum = k.attnum
WHERE con.contype IN ('p', 'f', 'u') AND con.connamespace = 'dw'::regnamespace
"""


def generar(conn: psycopg.Connection) -> str:
    columnas = defaultdict(list)
    for tabla, col, tipo, nulo, desc in conn.execute(SQL_COLUMNAS):
        columnas[tabla].append((col, tipo, nulo, desc))
    claves = defaultdict(list)
    for tabla, tipo, col, ref in conn.execute(SQL_CLAVES):
        etiqueta = {"p": "PK", "u": "UQ"}.get(tipo) or f"FK → `{ref}`"
        claves[(tabla.removeprefix("dw."), col)].append(etiqueta)
    descripciones = dict(
        conn.execute(
            "SELECT c.relname, obj_description(c.oid, 'pg_class') FROM pg_class c "
            "WHERE c.relnamespace = 'dw'::regnamespace AND c.relkind = 'r'"
        ).fetchall()
    )
    filas = {
        t: conn.execute(f"SELECT count(*) FROM dw.{t}").fetchone()[0]
        for t in ORDEN
        if t in columnas
    }

    out = [
        "# Diccionario de datos — Data Warehouse (`faro_analytics.dw`)",
        "",
        "> Generado por `database/scripts/documentar_dw.py` desde la base real "
        f"({datetime.now(UTC):%Y-%m-%d %H:%M} UTC). No editar a mano.",
        "",
        "Modelo, grano y decisiones: [modelo-dimensional.md](modelo-dimensional.md).",
        "",
        "- **Clave:** `PK` primaria · `FK` foránea · `UQ` única. **Nulo:** ✔ admite NULL.",
        "- Todas las dimensiones tienen un **miembro desconocido** con clave `-1`.",
        "- Las filas incluyen ese miembro desconocido.",
        "",
        "## Tablas",
        "",
        "| Tabla | Filas | Descripción |",
        "|---|---:|---|",
        *(f"| [`dw.{t}`](#dw{t}) | {filas[t]:,} | {descripciones.get(t) or ''} |" for t in filas),
    ]
    for t in filas:
        out += [
            "",
            f"## dw.{t}",
            "",
            descripciones.get(t) or "",
            "",
            "| Columna | Tipo | Nulo | Clave | Descripción |",
            "|---|---|:---:|---|---|",
            *(
                f"| `{c}` | {tipo} | {'✔' if nulo else ''} | {', '.join(claves.get((t, c), []))} "
                f"| {desc or ''} |"
                for c, tipo, nulo, desc in columnas[t]
            ),
        ]
    return "\n".join(out) + "\n"


def main() -> int:
    load_dotenv(RAIZ / ".env")
    url = os.getenv("ANALYTICS_DATABASE_URL")
    if not url:
        print("Falta ANALYTICS_DATABASE_URL en .env")
        return 1
    with psycopg.connect(url, connect_timeout=15) as conn:
        contenido = generar(conn)
    SALIDA.write_text(contenido, encoding="utf-8", newline="\n")
    print(f"Generado: {SALIDA.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
