"""Genera el DDL de las tablas de staging (stg_raw y stg_clean) desde el catálogo de la fuente.

Cada tabla de la fuente tiene su espejo en staging con las mismas columnas y tipos, así que
el DDL se genera en lugar de escribirse a mano (17 tablas x 2 zonas). El archivo generado
se versiona: database/staging/02_tablas_staging.sql

Uso (con la base wwi_oltp local levantada):
    uv run python database/scripts/generar_ddl_staging.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
from etl.config import TABLAS  # noqa: E402

SALIDA = RAIZ / "database" / "staging" / "02_tablas_staging.sql"

SQL_COLUMNAS = """
SELECT a.attname, format_type(a.atttypid, a.atttypmod)
FROM pg_attribute a
WHERE a.attrelid = %s::regclass AND a.attnum > 0 AND NOT a.attisdropped
ORDER BY a.attnum
"""


def generar(conn: psycopg.Connection) -> str:
    out = [
        "-- =====================================================================",
        "-- Faro · Staging · Tablas stg_raw y stg_clean (espejo de la fuente)",
        "-- GENERADO por database/scripts/generar_ddl_staging.py. No editar a mano.",
        "-- IDEMPOTENTE. Requiere 01_esquemas_auditoria.sql.",
        "--",
        "-- stg_raw  : copia fiel; solo se agregan filas. _raw_id ordena las versiones.",
        "-- stg_clean: una fila por clave natural (versión vigente), limpia y validada.",
        "--   _row_hash : huella del registro original, para detectar cambios reales.",
        "--   _dq_flags : reglas de calidad de tipo 'marcar' que el registro incumple.",
        "-- =====================================================================",
    ]
    for t in TABLAS:
        columnas = conn.execute(SQL_COLUMNAS, (t.origen,)).fetchall()
        defs = ",\n".join(f"    {nombre:<32} {tipo}" for nombre, tipo in columnas)
        defs_clean = ",\n".join(
            f"    {nombre:<32} {tipo}{' PRIMARY KEY' if nombre == t.pk else ''}"
            for nombre, tipo in columnas
        )
        s = t.staging
        out += [
            "",
            f"-- ---------- {t.origen} ----------",
            f"CREATE TABLE IF NOT EXISTS stg_raw.{s} (",
            f"    {'_raw_id':<32} bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,",
            defs + ",",
            f"    {'_batch_id':<32} bigint NOT NULL,",
            f"    {'_extracted_at':<32} timestamp with time zone NOT NULL",
            ");",
            f"CREATE INDEX IF NOT EXISTS ix_raw_{s}_batch ON stg_raw.{s} (_batch_id);",
            f"CREATE INDEX IF NOT EXISTS ix_raw_{s}_pk ON stg_raw.{s} ({t.pk});",
            "",
            f"CREATE TABLE IF NOT EXISTS stg_clean.{s} (",
            defs_clean + ",",
            f"    {'_batch_id':<32} bigint NOT NULL,",
            f"    {'_extracted_at':<32} timestamp with time zone NOT NULL,",
            f"    {'_row_hash':<32} text NOT NULL,",
            f"    {'_dq_flags':<32} text[] NOT NULL DEFAULT '{{}}'",
            ");",
        ]
    return "\n".join(out) + "\n"


def main() -> int:
    load_dotenv(RAIZ / ".env")
    url = os.getenv("SOURCE_DATABASE_URL")
    if not url:
        print("Falta SOURCE_DATABASE_URL en .env")
        return 1
    with psycopg.connect(url, connect_timeout=10) as conn:
        contenido = generar(conn)
    SALIDA.write_text(contenido, encoding="utf-8", newline="\n")
    print(f"Generado: {SALIDA.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
