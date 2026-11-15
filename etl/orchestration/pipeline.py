"""Pipeline de staging de ventas: fuente -> stg_raw -> stg_clean / cuarentena.

Uso (desde la raíz del repositorio):
    uv run python -m etl.orchestration.pipeline                  # incremental (por defecto)
    uv run python -m etl.orchestration.pipeline --modo inicial   # vacía staging y recarga todo

Garantías:
  - Todo o nada: los datos, los pasos de auditoría y los watermarks se confirman en UNA
    transacción. Si algo falla se revierte todo, el watermark no avanza y la ejecución
    queda registrada como 'fallido' con el detalle del error.
  - Idempotencia: repetir una ejecución no duplica ni altera los datos.
  - Una sola ejecución a la vez (candado en la base).
  - La fuente se lee en una transacción de solo lectura con una vista consistente
    (REPEATABLE READ): los hijos nunca llegan sin sus padres.

Variables de entorno: SOURCE_DATABASE_URL y ANALYTICS_DATABASE_URL.
"""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
from dataclasses import dataclass

import psycopg
from dotenv import load_dotenv
from psycopg import sql

from etl.config import PIPELINE, TABLAS, reglas_de
from etl.db import conectar
from etl.extraction.extraer import columnas_de, extraer_tabla
from etl.transformation.limpiar import limpiar_tabla

log = logging.getLogger("etl.pipeline")

CANDADO = "hashtext('faro.ventas_staging')"


@dataclass
class Resumen:
    execution_id: int
    estado: str
    leidas: int = 0
    insertadas: int = 0
    actualizadas: int = 0
    rechazadas: int = 0
    sin_cambios: int = 0
    reconciliado: bool | None = None
    error: str | None = None


class EjecucionEnCurso(RuntimeError):
    """Ya hay otra ejecución del pipeline corriendo."""


def _git_sha() -> str | None:
    if os.getenv("GITHUB_SHA"):
        return os.environ["GITHUB_SHA"][:7]
    try:
        salida = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=5
        )
        return salida.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def _abrir_ejecucion(aud: psycopg.Connection, modo: str, disparador: str) -> int:
    if not aud.execute(f"SELECT pg_try_advisory_lock({CANDADO})").fetchone()[0]:
        raise EjecucionEnCurso("Ya hay una ejecución del pipeline en curso")
    # Con el candado tomado, cualquier 'en_curso' anterior es de un proceso que murió
    aud.execute(
        "UPDATE audit.etl_execution SET status = 'fallido', end_time = clock_timestamp(), "
        "error_detail = 'Ejecución interrumpida (el proceso terminó sin cerrar)' "
        "WHERE status = 'en_curso' AND pipeline_name = %s",
        (PIPELINE,),
    )
    return aud.execute(
        "INSERT INTO audit.etl_execution (pipeline_name, trigger, mode, git_sha) "
        "VALUES (%s, %s, %s, %s) RETURNING execution_id",
        (PIPELINE, disparador, modo, _git_sha()),
    ).fetchone()[0]


def _vaciar_staging(dst: psycopg.Connection) -> None:
    """Modo inicial: reconstruir desde cero (staging vacío y watermarks reiniciados)."""
    tablas = [sql.Identifier(z, t.staging) for t in TABLAS for z in ("stg_raw", "stg_clean")]
    tablas.append(sql.Identifier("stg_quarantine", "registro_rechazado"))
    dst.execute(sql.SQL("TRUNCATE {}").format(sql.SQL(", ").join(tablas)))
    dst.execute("DELETE FROM audit.watermark")


def _sincronizar_catalogo_reglas(dst: psycopg.Connection) -> None:
    dst.execute("DELETE FROM audit.dq_rule")
    for t in TABLAS:
        for r in reglas_de(t):
            dst.execute(
                "INSERT INTO audit.dq_rule VALUES (%s, %s, %s, %s, %s)",
                (t.origen, r.codigo, r.dimension, r.descripcion, r.accion),
            )


def _registrar_paso(dst, batch_id, paso, origen, destino, **valores) -> None:
    columnas = ["execution_id", "step", "source_object", "target_object", *valores]
    dst.execute(
        sql.SQL("INSERT INTO audit.etl_step ({}) VALUES ({})").format(
            sql.SQL(", ").join(map(sql.Identifier, columnas)),
            sql.SQL(", ").join(sql.Placeholder() * len(columnas)),
        ),
        (batch_id, paso, origen, destino, *valores.values()),
    )


def _reconciliar(src, dst, batch_id: int) -> bool:
    """Por tabla: filas en la fuente = filas en clean + claves solo en cuarentena."""
    todo_ok = True
    for t in TABLAS:
        en_fuente = src.execute(
            sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(*t.origen.split(".")))
        ).fetchone()[0]
        en_clean, en_cuarentena = dst.execute(
            sql.SQL(
                "SELECT (SELECT count(*) FROM {clean}), "
                "(SELECT count(DISTINCT q.natural_key) FROM stg_quarantine.registro_rechazado q "
                " WHERE q.source_table = %s AND q.resolved_at IS NULL AND NOT EXISTS "
                " (SELECT 1 FROM {clean} c WHERE c.{pk} = q.natural_key))"
            ).format(clean=sql.Identifier("stg_clean", t.staging), pk=sql.Identifier(t.pk)),
            (t.origen,),
        ).fetchone()
        ok = en_fuente == en_clean + en_cuarentena
        todo_ok &= ok
        if not ok:
            log.warning(
                "Reconciliación %s: fuente=%d, clean=%d, cuarentena=%d",
                t.origen,
                en_fuente,
                en_clean,
                en_cuarentena,
            )
        _registrar_paso(
            dst,
            batch_id,
            "reconcile",
            t.origen,
            f"stg_clean.{t.staging}",
            rows_read=en_fuente,
            rows_inserted=en_clean,
            rows_rejected=en_cuarentena,
            status="ok" if ok else "diferencia",
        )
    return todo_ok


def _procesar(src, dst, batch_id: int, modo: str, resumen: Resumen) -> None:
    """Todo el trabajo de datos. Corre dentro de la transacción de `dst`."""
    if modo == "inicial":
        _vaciar_staging(dst)
    _sincronizar_catalogo_reglas(dst)
    extraido_en = src.execute("SELECT now()::text").fetchone()[0]

    extracciones = []
    for t in TABLAS:
        columnas = columnas_de(dst, t)
        ext = extraer_tabla(src, dst, t, [c for c, _ in columnas], batch_id, extraido_en)
        extracciones.append((ext, columnas))
        resumen.leidas += ext.filas_leidas
        _registrar_paso(
            dst,
            batch_id,
            "extract",
            t.origen,
            f"stg_raw.{t.staging}",
            rows_read=ext.filas_leidas,
            watermark_start=ext.watermark_inicio,
            watermark_end=ext.watermark_fin or ext.watermark_inicio,
            duration_ms=ext.duracion_ms,
        )

    for ext, columnas in extracciones:
        t = ext.tabla
        lim = limpiar_tabla(dst, t, columnas, batch_id)
        resumen.insertadas += lim.insertadas
        resumen.actualizadas += lim.actualizadas
        resumen.rechazadas += lim.rechazadas
        resumen.sin_cambios += lim.sin_cambios
        _registrar_paso(
            dst,
            batch_id,
            "clean",
            f"stg_raw.{t.staging}",
            f"stg_clean.{t.staging}",
            rows_read=lim.candidatos,
            rows_inserted=lim.insertadas,
            rows_updated=lim.actualizadas,
            rows_rejected=lim.rechazadas,
            rows_unchanged=lim.sin_cambios,
            duration_ms=lim.duracion_ms,
        )
        log.info(
            "  %-36s leídas=%-7d nuevas=%-7d actualizadas=%-5d rechazadas=%-4d sin cambios=%d",
            t.origen,
            ext.filas_leidas,
            lim.insertadas,
            lim.actualizadas,
            lim.rechazadas,
            lim.sin_cambios,
        )

    resumen.reconciliado = _reconciliar(src, dst, batch_id)

    # Los watermarks avanzan al final y en la misma transacción que los datos
    for ext, _ in extracciones:
        if ext.watermark_fin:
            dst.execute(
                "INSERT INTO audit.watermark (source_table, last_value, execution_id) "
                "VALUES (%s, %s::timestamptz, %s) ON CONFLICT (source_table) DO UPDATE SET "
                "last_value = GREATEST(audit.watermark.last_value, EXCLUDED.last_value), "
                "execution_id = EXCLUDED.execution_id, updated_at = now()",
                (ext.tabla.origen, ext.watermark_fin, batch_id),
            )

    dst.execute(
        "UPDATE audit.etl_execution SET status = 'exitoso', end_time = clock_timestamp(), "
        "rows_read = %s, "
        "rows_inserted = %s, rows_updated = %s, rows_rejected = %s, rows_unchanged = %s, "
        "reconciled = %s WHERE execution_id = %s",
        (
            resumen.leidas,
            resumen.insertadas,
            resumen.actualizadas,
            resumen.rechazadas,
            resumen.sin_cambios,
            resumen.reconciliado,
            batch_id,
        ),
    )


def ejecutar(
    url_fuente: str, url_analitica: str, modo: str = "incremental", disparador: str = "manual"
) -> Resumen:
    """Ejecuta el pipeline. Nunca lanza por errores de datos: devuelve el resumen con el estado."""
    with conectar(url_analitica, autocommit=True) as aud:
        batch_id = _abrir_ejecucion(aud, modo, disparador)
        resumen = Resumen(batch_id, "en_curso")
        log.info("Ejecución %d (%s, %s)", batch_id, modo, disparador)
        try:
            with conectar(url_fuente) as src, conectar(url_analitica) as dst:
                src.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ
                src.read_only = True
                _procesar(src, dst, batch_id, modo, resumen)
                dst.commit()
            resumen.estado = "exitoso"
        except Exception as error:  # noqa: BLE001 - toda falla debe quedar auditada
            # La transacción de datos ya se revirtió al salir del bloque `with`
            resumen.estado = "fallido"
            resumen.error = f"{type(error).__name__}: {error}"[:2000]
            aud.execute(
                "UPDATE audit.etl_execution SET status = 'fallido', end_time = clock_timestamp(), "
                "error_detail = %s WHERE execution_id = %s",
                (resumen.error, batch_id),
            )
            log.error("Ejecución %d fallida y revertida: %s", batch_id, resumen.error)
    return resumen


def main() -> int:
    parser = argparse.ArgumentParser(description="Pipeline de staging de ventas de Faro")
    parser.add_argument("--modo", choices=["incremental", "inicial"], default="incremental")
    parser.add_argument("--disparador", choices=["manual", "cron", "ci"], default="manual")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    load_dotenv()
    url_fuente = os.getenv("SOURCE_DATABASE_URL")
    url_analitica = os.getenv("ANALYTICS_DATABASE_URL")
    if not url_fuente or not url_analitica:
        log.error("Faltan SOURCE_DATABASE_URL o ANALYTICS_DATABASE_URL")
        return 1

    try:
        r = ejecutar(url_fuente, url_analitica, args.modo, args.disparador)
    except EjecucionEnCurso as error:
        log.error("%s", error)
        return 1
    if r.estado != "exitoso":
        return 1
    log.info(
        "OK ejecución %d: leídas=%d nuevas=%d actualizadas=%d rechazadas=%d sin cambios=%d "
        "reconciliado=%s",
        r.execution_id,
        r.leidas,
        r.insertadas,
        r.actualizadas,
        r.rechazadas,
        r.sin_cambios,
        r.reconciliado,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
