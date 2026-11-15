"""Extracción incremental: fuente (wwi_oltp) -> stg_raw.

Por cada tabla lee solo las filas con last_edited_when posterior al watermark (menos una
ventana de solapamiento) y las copia tal cual a stg_raw con su lote. Usa COPY de extremo
a extremo: los datos pasan de una base a la otra sin transformarse en Python.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import psycopg
from psycopg import sql

from etl.config import SOLAPAMIENTO, TOLERANCIA_RELOJ, TablaFuente


@dataclass
class ResultadoExtraccion:
    tabla: TablaFuente
    filas_leidas: int
    watermark_inicio: str
    watermark_fin: str | None  # None = no llegaron filas válidas; el watermark no cambia
    duracion_ms: int


def columnas_de(dst: psycopg.Connection, tabla: TablaFuente) -> list[tuple[str, str]]:
    """Columnas de negocio (nombre, tipo) según stg_raw: es el contrato con la fuente."""
    return dst.execute(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_schema = 'stg_raw' AND table_name = %s AND left(column_name, 1) <> '_' "
        "ORDER BY ordinal_position",
        (tabla.staging,),
    ).fetchall()


def leer_watermark(dst: psycopg.Connection, tabla: TablaFuente) -> str:
    fila = dst.execute(
        "SELECT last_value::text FROM audit.watermark WHERE source_table = %s", (tabla.origen,)
    ).fetchone()
    return fila[0] if fila else "-infinity"


def extraer_tabla(
    src: psycopg.Connection,
    dst: psycopg.Connection,
    tabla: TablaFuente,
    columnas: list[str],
    batch_id: int,
    extraido_en: str,
) -> ResultadoExtraccion:
    inicio = time.perf_counter()
    watermark = leer_watermark(dst, tabla)
    cols = sql.SQL(", ").join(map(sql.Identifier, columnas))
    destino = sql.Identifier("stg_raw", tabla.staging)

    salida = sql.SQL(
        "COPY (SELECT {cols}, {batch}::bigint, {extraido}::timestamptz FROM {origen} "
        "WHERE last_edited_when > {wm}::timestamptz - {solape}::interval) TO STDOUT"
    ).format(
        cols=cols,
        batch=sql.Literal(batch_id),
        extraido=sql.Literal(extraido_en),
        origen=sql.Identifier(*tabla.origen.split(".")),
        wm=sql.Literal(watermark),
        solape=sql.Literal(SOLAPAMIENTO),
    )
    entrada = sql.SQL("COPY {} ({}, _batch_id, _extracted_at) FROM STDIN").format(destino, cols)

    with src.cursor() as c_src, dst.cursor() as c_dst:
        with c_src.copy(salida) as lectura, c_dst.copy(entrada) as escritura:
            for bloque in lectura:
                escritura.write(bloque)

    # El nuevo watermark es el máximo last_edited_when recibido. Se ignoran las marcas
    # "futuras" (irán a cuarentena) para que no adelanten el watermark indebidamente.
    filas, maximo = dst.execute(
        sql.SQL(
            "SELECT count(*), max(last_edited_when) FILTER "
            "(WHERE last_edited_when <= _extracted_at + {tol}::interval)::text "
            "FROM {} WHERE _batch_id = %s"
        ).format(destino, tol=sql.Literal(TOLERANCIA_RELOJ)),
        (batch_id,),
    ).fetchone()
    return ResultadoExtraccion(
        tabla, filas, watermark, maximo, int((time.perf_counter() - inicio) * 1000)
    )
