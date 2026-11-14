"""Genera la documentación de la base operacional (wwi_oltp) a partir de la base REAL.

Produce:
  - documentation/modelos/diccionario-fuente.md : diccionario de datos con linaje.
  - documentation/modelos/erd-fuente.md         : diagrama entidad-relación (Mermaid).

Lee del catálogo de PostgreSQL (tipos, nulos, claves, descripciones, conteos) y agrega
el linaje (columna original en SQL Server) desde el mapeo de la migración.
Como se genera desde la base, nunca queda desactualizado respecto del esquema.

Uso:
    uv run python database/scripts/documentar_fuente.py
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
sys.path.insert(0, str(RAIZ / "database" / "source" / "seed"))
from mapeo_wwi import TABLAS  # noqa: E402

DICCIONARIO = RAIZ / "documentation" / "modelos" / "diccionario-fuente.md"
ERD = RAIZ / "documentation" / "modelos" / "erd-fuente.md"
ESQUEMAS = ("application", "warehouse", "sales")
AUDITORIA = ("last_edited_by", "last_edited_when")

# Tipos de PostgreSQL -> nombre corto para el diagrama
TIPOS_CORTOS = {
    "integer": "int",
    "bigint": "bigint",
    "boolean": "bool",
    "date": "date",
    "text": "text",
    "double precision": "float8",
    "timestamp with time zone": "timestamptz",
}

SQL_COLUMNAS = """
SELECT n.nspname || '.' || c.relname          AS tabla,
       a.attname                              AS columna,
       format_type(a.atttypid, a.atttypmod)   AS tipo,
       NOT a.attnotnull                       AS admite_nulo,
       col_description(c.oid, a.attnum)       AS descripcion
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped
WHERE c.relkind = 'r' AND n.nspname = ANY(%s)
ORDER BY tabla, a.attnum
"""

SQL_CLAVES = """
SELECT con.conrelid::regclass::text  AS tabla,
       con.contype                   AS tipo,
       a.attname                     AS columna,
       con.confrelid::regclass::text AS ref_tabla,
       af.attname                    AS ref_columna
FROM pg_constraint con
CROSS JOIN LATERAL unnest(con.conkey, con.confkey) AS k(attnum, fattnum)
JOIN pg_attribute a ON a.attrelid = con.conrelid AND a.attnum = k.attnum
LEFT JOIN pg_attribute af ON af.attrelid = con.confrelid AND af.attnum = k.fattnum
WHERE con.contype IN ('p', 'f', 'u')
  AND con.connamespace::regnamespace::text = ANY(%s)
"""

SQL_TABLAS = """
SELECT n.nspname || '.' || c.relname, obj_description(c.oid, 'pg_class')
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind = 'r' AND n.nspname = ANY(%s)
"""


def leer_catalogo(conn: psycopg.Connection) -> dict:
    esquemas = list(ESQUEMAS)
    columnas = defaultdict(list)
    for tabla, columna, tipo, nulo, desc in conn.execute(SQL_COLUMNAS, (esquemas,)):
        columnas[tabla].append({"columna": columna, "tipo": tipo, "nulo": nulo, "desc": desc})

    claves: dict[tuple[str, str], list[str]] = defaultdict(list)
    fks: list[tuple[str, str, str]] = []  # (tabla, columna, tabla_referenciada)
    for tabla, tipo, columna, ref_tabla, ref_columna in conn.execute(SQL_CLAVES, (esquemas,)):
        if tipo == "p":
            claves[(tabla, columna)].append("PK")
        elif tipo == "u":
            claves[(tabla, columna)].append("UQ")
        else:
            claves[(tabla, columna)].append(f"FK → `{ref_tabla}.{ref_columna}`")
            fks.append((tabla, columna, ref_tabla))

    descripciones = dict(conn.execute(SQL_TABLAS, (esquemas,)).fetchall())
    filas = {
        t.destino: conn.execute(f"SELECT count(*) FROM {t.destino}").fetchone()[0] for t in TABLAS
    }
    return {
        "columnas": columnas,
        "claves": claves,
        "fks": sorted(fks),
        "desc": descripciones,
        "filas": filas,
    }


def _linaje() -> dict[tuple[str, str], str]:
    """(tabla_destino, columna_destino) -> 'Esquema.Tabla.Columna' en SQL Server."""
    return {(t.destino, d): f"{t.origen}.{o}" for t in TABLAS for o, d in t.columnas}


def generar_diccionario(cat: dict) -> str:
    linaje = _linaje()
    total = sum(cat["filas"].values())
    out = [
        "# Diccionario de datos — base operacional `wwi_oltp`",
        "",
        "> Generado automáticamente por `database/scripts/documentar_fuente.py` desde la base",
        f"> real ({datetime.now(UTC):%Y-%m-%d %H:%M} UTC). No editar a mano: regenerar.",
        "",
        "**Fuente original:** WideWorldImporters (SQL Server), módulo de ventas.",
        f"**Tablas:** {len(TABLAS)} · **Filas:** {total:,}",
        "",
        "## Convenciones",
        "",
        "- **Clave:** `PK` = clave primaria · `FK` = clave foránea · `UQ` = valor único.",
        "- **Nulo:** ✔ = admite NULL.",
        "- **Origen:** columna de SQL Server de la que proviene el dato (linaje).",
        "- Todas las tablas tienen `last_edited_by` (quién modificó) y `last_edited_when`",
        "  (cuándo, en UTC). `last_edited_when` es la marca de agua de la carga incremental",
        "  y la actualiza un trigger en cada UPDATE.",
        "- Por minimización de datos personales no se migraron contraseñas, fotos, correos,",
        "  teléfonos, direcciones ni comentarios de texto libre.",
        "",
        "## Tablas",
        "",
        "| Tabla | Filas | Descripción |",
        "|---|---:|---|",
    ]
    for t in TABLAS:
        ancla = t.destino.replace(".", "")
        desc = cat["desc"].get(t.destino) or ""
        out.append(f"| [`{t.destino}`](#{ancla}) | {cat['filas'][t.destino]:,} | {desc} |")

    for t in TABLAS:
        out += [
            "",
            f"## {t.destino}",
            "",
            f"{cat['desc'].get(t.destino) or ''}",
            "",
            f"Origen: `{t.origen}` · Filas: {cat['filas'][t.destino]:,}",
            "",
            "| Columna | Tipo | Nulo | Clave | Origen (SQL Server) | Descripción |",
            "|---|---|:---:|---|---|---|",
        ]
        for col in cat["columnas"][t.destino]:
            nombre = col["columna"]
            clave = ", ".join(cat["claves"].get((t.destino, nombre), []))
            origen = linaje.get((t.destino, nombre), "—")
            out.append(
                f"| `{nombre}` | {col['tipo']} | {'✔' if col['nulo'] else ''} | {clave} "
                f"| `{origen}` | {col['desc'] or ''} |"
            )
    return "\n".join(out) + "\n"


def _entidad(tabla: str) -> str:
    """Mermaid no admite puntos en los nombres: sales.orders -> sales_orders."""
    return tabla.replace(".", "_")


def generar_erd(cat: dict) -> str:
    out = [
        "# Diagrama entidad-relación — base operacional `wwi_oltp`",
        "",
        "> Generado automáticamente por `database/scripts/documentar_fuente.py` desde la base",
        f"> real ({datetime.now(UTC):%Y-%m-%d %H:%M} UTC). No editar a mano: regenerar.",
        "",
        "**Cómo leerlo:** `||--o{` = uno a muchos (la FK es obligatoria);",
        "`|o--o{` = cero o uno a muchos (la FK admite NULL). La etiqueta es la columna FK.",
        "",
        "**Simplificación:** se omiten `last_edited_by` y `last_edited_when`, presentes en todas",
        "las tablas (cada `last_edited_by` es una FK a `application.people`).",
        "",
        "```mermaid",
        "erDiagram",
    ]
    nulos = {(t, c["columna"]): c["nulo"] for t, cols in cat["columnas"].items() for c in cols}
    for tabla, columna, ref_tabla in cat["fks"]:
        if columna in AUDITORIA:
            continue
        relacion = "|o--o{" if nulos[(tabla, columna)] else "||--o{"
        out.append(f'    {_entidad(ref_tabla)} {relacion} {_entidad(tabla)} : "{columna}"')
    for t in TABLAS:
        out.append(f"    {_entidad(t.destino)} {{")
        for col in cat["columnas"][t.destino]:
            if col["columna"] in AUDITORIA:
                continue
            marcas = [
                "FK" if k.startswith("FK") else ("UK" if k == "UQ" else k)
                for k in cat["claves"].get((t.destino, col["columna"]), [])
            ]
            tipo = TIPOS_CORTOS.get(col["tipo"], col["tipo"].split("(")[0].replace(" ", "_"))
            tipo = {"character_varying": "varchar"}.get(tipo, tipo)
            out.append(f"        {tipo} {col['columna']} {', '.join(marcas)}".rstrip())
        out.append("    }")
    out += [
        "```",
        "",
        "## Observaciones para el modelo dimensional",
        "",
        "- **Producto ↔ grupo es MUCHOS a MUCHOS** (`warehouse.stock_item_stock_groups`): un",
        "  producto puede pertenecer a varios grupos. Unir ventas con grupos sin control",
        "  **multiplicaría los importes**; hay que resolverlo en el diseño (Fase 2).",
        "- **Cliente que recibe ≠ cliente que paga:** `customers.bill_to_customer_id` y",
        "  `invoices.bill_to_customer_id` son autorreferencias a `sales.customers`.",
        "- **Pedidos pendientes:** `orders.backorder_order_id` es una autorreferencia a",
        "  `sales.orders`.",
        "- **Una persona, varios roles:** vendedor, contacto, preparador y empacador apuntan todos",
        "  a `application.people` (en el DW serán *role-playing dimensions*).",
        "- **Dos ciudades por cliente:** de entrega (`delivery_city_id`) y postal",
        "  (`postal_city_id`).",
        "",
    ]
    return "\n".join(out)


def _escribir(ruta: Path, contenido: str) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(contenido, encoding="utf-8", newline="\n")  # LF, igual que el repositorio
    print(f"Generado: {ruta.relative_to(RAIZ)}")


def main() -> int:
    load_dotenv(RAIZ / ".env")
    url = os.getenv("SOURCE_DATABASE_URL")
    if not url:
        print("Falta SOURCE_DATABASE_URL en .env")
        return 1
    with psycopg.connect(url, connect_timeout=10) as conn:
        cat = leer_catalogo(conn)
    _escribir(DICCIONARIO, generar_diccionario(cat))
    _escribir(ERD, generar_erd(cat))
    return 0


if __name__ == "__main__":
    sys.exit(main())
