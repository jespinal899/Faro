"""Validación del Data Warehouse: reconciliación y pruebas del modelo dimensional.

Ejecuta los controles del modelo (documentation/modelos/modelo-dimensional.md, sección 10)
contra un entorno y escribe el reporte documentation/pruebas/validacion-dw-<entorno>.md.
Termina con código 1 si algún control falla. Solo LEE las bases.

Uso:
    uv run python database/scripts/validar_dw.py           # usa SOURCE_/ANALYTICS_DATABASE_URL
    uv run python database/scripts/validar_dw.py --neon    # usa las conexiones de Neon del .env
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse

import psycopg
from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parents[2]
PRUEBAS = RAIZ / "documentation" / "pruebas"


@dataclass
class Resultado:
    codigo: str
    control: str
    ok: bool
    detalle: str


def _fmt(valor) -> str:
    if isinstance(valor, Decimal):
        return f"{valor:,.2f}"
    if isinstance(valor, int):
        return f"{valor:,}"
    return str(valor)


def _uno(conn: psycopg.Connection, consulta: str):
    return conn.execute(consulta).fetchone()


def controles(fuente: psycopg.Connection, dw: psycopg.Connection) -> list[Resultado]:
    r: list[Resultado] = []

    # D01 · Grano: una fila por línea de factura
    filas, distintas = _uno(
        dw, "SELECT count(*), count(DISTINCT linea_factura_id) FROM dw.fact_ventas"
    )
    r.append(Resultado("D01", "Grano: linea_factura_id es único en fact_ventas",
                       filas == distintas,
                       f"{_fmt(filas)} filas, {_fmt(distintas)} distintas"))  # fmt: skip

    # D02 · Reconciliación fuente -> DW (independiente del ETL: se consulta la fuente)
    lineas_src, bruta_src = _uno(
        fuente, "SELECT count(*), COALESCE(sum(extended_price), 0) FROM sales.invoice_lines"
    )
    lineas_q, bruta_q = _uno(
        dw,
        "SELECT count(*), COALESCE(sum((payload->>'extended_price')::numeric), 0) FROM ("
        "  SELECT DISTINCT ON (natural_key) natural_key, payload "
        "  FROM stg_quarantine.registro_rechazado q "
        "  WHERE source_table = 'sales.invoice_lines' AND resolved_at IS NULL "
        "  AND NOT EXISTS (SELECT 1 FROM dw.fact_ventas f WHERE f.linea_factura_id = q.natural_key)"
        "  ORDER BY natural_key, rechazo_id DESC) x",
    )
    lineas_dw, bruta_dw = _uno(
        dw, "SELECT count(*), COALESCE(sum(venta_bruta), 0) FROM dw.fact_ventas"
    )
    r.append(Resultado(
        "D02", "Reconciliación fuente → DW: líneas y venta bruta (fuente = DW + cuarentena)",
        lineas_src == lineas_dw + lineas_q and bruta_src == bruta_dw + bruta_q,
        f"fuente {_fmt(lineas_src)} / {_fmt(bruta_src)} · DW {_fmt(lineas_dw)} / {_fmt(bruta_dw)}"
        f" · cuarentena {_fmt(lineas_q)} / {_fmt(bruta_q)}",
    ))  # fmt: skip

    # D03 · Reconciliación staging (ready) -> DW
    ready = _uno(dw, "SELECT count(*), COALESCE(sum(venta_bruta), 0) FROM stg_ready.ventas")
    r.append(Resultado("D03", "Reconciliación stg_ready → DW: líneas y venta bruta",
                       ready == (lineas_dw, bruta_dw),
                       f"ready {_fmt(ready[0])} / {_fmt(ready[1])}"))  # fmt: skip

    # D04 · Medidas derivadas coherentes en todas las filas
    malas = _uno(
        dw,
        "SELECT count(*) FROM dw.fact_ventas WHERE venta_neta <> venta_bruta - impuesto "
        "OR costo <> venta_neta - utilidad OR es_venta_bajo_costo <> (utilidad < 0)",
    )[0]
    r.append(Resultado("D04", "Medidas: venta_neta = bruta − impuesto y costo = neta − utilidad",
                       malas == 0, f"{_fmt(malas)} filas incoherentes"))  # fmt: skip

    # D05 · Sin multiplicación por grupo de producto
    principal, ponderado, sin_ponderar = _uno(
        dw,
        "SELECT (SELECT sum(f.venta_bruta) FROM dw.fact_ventas f "
        "        JOIN dw.dim_producto p ON p.producto_key = f.producto_key), "
        "(SELECT round(sum(f.venta_bruta * b.factor_ponderacion), 2) FROM dw.fact_ventas f "
        "        JOIN dw.puente_producto_grupo b ON b.producto_id = f.producto_id), "
        "(SELECT sum(f.venta_bruta) FROM dw.fact_ventas f "
        "        JOIN dw.puente_producto_grupo b ON b.producto_id = f.producto_id)",
    )
    r.append(Resultado(
        "D05", "Sin multiplicar importes: por grupo principal y por puente ponderado = total",
        principal == bruta_dw and ponderado == bruta_dw,
        f"principal {_fmt(principal)} · ponderado {_fmt(ponderado)} · "
        f"(sin ponderar daría {_fmt(sin_ponderar)})",
    ))  # fmt: skip

    # D06-D07 · SCD2: una versión vigente por clave y vigencias sin solapamiento ni huecos
    for codigo, tabla, nk, sk in (
        ("D06", "dw.dim_cliente", "cliente_id", "cliente_key"),
        ("D07", "dw.dim_producto", "producto_id", "producto_key"),
    ):
        sin_una_vigente, solapes, huecos, versiones = _uno(
            dw,
            f"SELECT (SELECT count(*) FROM (SELECT {nk} FROM {tabla} GROUP BY 1 "
            f"         HAVING count(*) FILTER (WHERE es_actual) <> 1) x), "
            f"(SELECT count(*) FROM {tabla} a JOIN {tabla} b ON a.{nk} = b.{nk} "
            f"   AND a.{sk} < b.{sk} AND a.valido_desde <= b.valido_hasta "
            f"   AND b.valido_desde <= a.valido_hasta), "
            f"(SELECT count(*) FROM (SELECT valido_desde, lag(valido_hasta) OVER "
            f"   (PARTITION BY {nk} ORDER BY version) AS fin_anterior FROM {tabla}) x "
            f"   WHERE fin_anterior IS NOT NULL AND valido_desde <> fin_anterior + 1), "
            f"(SELECT count(*) FROM {tabla} WHERE version > 1)",
        )
        r.append(Resultado(
            codigo, f"SCD2 en {tabla}: una versión vigente por clave, sin solapes ni huecos",
            sin_una_vigente == solapes == huecos == 0,
            f"claves sin una vigente: {sin_una_vigente} · solapes: {solapes} · huecos: {huecos}"
            f" · versiones históricas: {versiones}",
        ))  # fmt: skip

    # D08 · Miembro desconocido presente y uso justificado
    faltan = _uno(
        dw,
        "SELECT 7 - ((SELECT count(*) FROM dw.dim_cliente WHERE cliente_key = -1) "
        "+ (SELECT count(*) FROM dw.dim_producto WHERE producto_key = -1) "
        "+ (SELECT count(*) FROM dw.dim_empleado WHERE empleado_key = -1) "
        "+ (SELECT count(*) FROM dw.dim_geografia WHERE geografia_key = -1) "
        "+ (SELECT count(*) FROM dw.dim_grupo_producto WHERE grupo_key = -1) "
        "+ (SELECT count(*) FROM dw.dim_fecha WHERE fecha_key = -1) * 2)",
    )[0]
    desconocidos = _uno(
        dw,
        "SELECT count(*) FROM dw.fact_ventas WHERE -1 IN (fecha_factura_key, fecha_pedido_key, "
        "cliente_key, cliente_facturacion_key, producto_key, vendedor_key, geografia_key)",
    )[0]
    r.append(Resultado("D08", "Miembro desconocido (-1) en cada dimensión; hechos que lo usan",
                       faltan == 0,
                       f"dimensiones sin miembro -1: {faltan} · "
                       f"hechos con -1: {_fmt(desconocidos)}"))  # fmt: skip

    # D09 · Dimensión fecha: cubre todas las ventas y ninguna cae en domingo
    sin_fecha, domingos = _uno(
        dw,
        "SELECT count(*) FILTER (WHERE f.fecha_factura_key = -1), "
        "count(*) FILTER (WHERE d.dia_semana = 7) FROM dw.fact_ventas f "
        "JOIN dw.dim_fecha d ON d.fecha_key = f.fecha_factura_key",
    )
    r.append(Resultado("D09", "Dimensión fecha cubre todas las ventas; ninguna venta en domingo",
                       sin_fecha == 0 and domingos == 0,
                       f"sin fecha: {sin_fecha} · ventas en domingo: {domingos}"))  # fmt: skip

    # D10 · KPI contra una consulta independiente a la fuente (venta neta por año)
    dw_anual = dict(
        dw.execute(
            "SELECT d.anio, sum(f.venta_neta) FROM dw.fact_ventas f "
            "JOIN dw.dim_fecha d ON d.fecha_key = f.fecha_factura_key GROUP BY 1"
        ).fetchall()
    )
    src_anual = dict(
        fuente.execute(
            "SELECT extract(year FROM i.invoice_date)::int, sum(l.extended_price - l.tax_amount) "
            "FROM sales.invoice_lines l JOIN sales.invoices i USING (invoice_id) "
            "WHERE l.quantity > 0 GROUP BY 1"
        ).fetchall()
    )
    difieren = sorted(a for a in src_anual if src_anual[a] != dw_anual.get(a))
    r.append(Resultado(
        "D10", "KPI venta neta por año: DW = consulta independiente a la fuente",
        not difieren,
        " · ".join(f"{a}: {_fmt(dw_anual.get(a, 0))}" for a in sorted(dw_anual))
        + (f" · DIFIEREN: {difieren}" if difieren else ""),
    ))  # fmt: skip

    # D11 · Integridad: cada clave del hecho existe en su dimensión (FK declaradas)
    fks = _uno(
        dw,
        "SELECT count(*) FROM pg_constraint WHERE contype = 'f' "
        "AND conrelid = 'dw.fact_ventas'::regclass",
    )[0]
    r.append(Resultado("D11", "Integridad referencial: claves foráneas declaradas en fact_ventas",
                       fks == 7,
                       f"{fks} de 7 claves foráneas (las garantiza el motor)"))  # fmt: skip
    return r


def reporte(entorno: str, resultados: list[Resultado], ventas_anuales: list[tuple]) -> str:
    ok = all(x.ok for x in resultados)
    lineas = [
        f"# Validación del Data Warehouse — {entorno}",
        "",
        "> Generado por `database/scripts/validar_dw.py` "
        f"({datetime.now(UTC):%Y-%m-%d %H:%M} UTC). No editar a mano.",
        "",
        f"**Resultado:** {'✅ TODOS LOS CONTROLES PASAN' if ok else '❌ HAY CONTROLES QUE FALLAN'}"
        f" ({sum(x.ok for x in resultados)}/{len(resultados)})",
        "",
        "| Código | Control | Estado | Detalle |",
        "|---|---|:---:|---|",
        *(
            f"| {x.codigo} | {x.control} | {'✅' if x.ok else '❌'} | {x.detalle} |"
            for x in resultados
        ),  # fmt: skip
        "",
        "## Ventas por año desde el DW",
        "",
        "| Año | Facturas | Líneas | Venta bruta | Venta neta | Utilidad | Margen % |",
        "|---|---:|---:|---:|---:|---:|---:|",
        *(
            f"| {a} | {_fmt(fa)} | {_fmt(li)} | {_fmt(vb)} | {_fmt(vn)} | {_fmt(ut)} | {mg} |"
            for a, fa, li, vb, vn, ut, mg in ventas_anuales
        ),  # fmt: skip
        "",
        "Margen % = Σ utilidad ÷ Σ venta neta (no aditivo: se recalcula por fila, no se suma).",
        "",
    ]
    return "\n".join(lineas)


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida el Data Warehouse de Faro")
    parser.add_argument("--neon", action="store_true", help="usar las conexiones de Neon del .env")
    args = parser.parse_args()
    load_dotenv(RAIZ / ".env")
    if args.neon:
        url_fuente, url_dw = os.getenv("NEON_ETL_SOURCE_URL"), os.getenv("NEON_ETL_ANALYTICS_URL")
    else:
        url_fuente, url_dw = os.getenv("SOURCE_DATABASE_URL"), os.getenv("ANALYTICS_DATABASE_URL")
    if not url_fuente or not url_dw:
        print("Faltan las cadenas de conexión de la fuente o del DW")
        return 1

    es_neon = "neon.tech" in (urlparse(url_dw).hostname or "")
    with (
        psycopg.connect(url_fuente, connect_timeout=20) as fuente,
        psycopg.connect(url_dw, connect_timeout=20) as dw,
    ):
        resultados = controles(fuente, dw)
        anuales = dw.execute(
            "SELECT d.anio, count(DISTINCT f.factura_id), count(*), sum(f.venta_bruta), "
            "sum(f.venta_neta), sum(f.utilidad), "
            "round(100 * sum(f.utilidad) / NULLIF(sum(f.venta_neta), 0), 2) "
            "FROM dw.fact_ventas f JOIN dw.dim_fecha d ON d.fecha_key = f.fecha_factura_key "
            "GROUP BY 1 ORDER BY 1"
        ).fetchall()

    entorno = "Neon (producción)" if es_neon else "local"
    destino = PRUEBAS / f"validacion-dw-{'neon' if es_neon else 'local'}.md"
    destino.write_text(reporte(entorno, resultados, anuales), encoding="utf-8", newline="\n")
    for x in resultados:
        print(f"[{'OK' if x.ok else 'FALLA'}] {x.codigo} {x.control}: {x.detalle}")
    print(f"Reporte: {destino.relative_to(RAIZ)}")
    return 0 if all(x.ok for x in resultados) else 1


if __name__ == "__main__":
    sys.exit(main())
