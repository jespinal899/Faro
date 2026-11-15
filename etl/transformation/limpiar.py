"""Limpieza y validación: stg_raw -> stg_clean / stg_quarantine.

Por cada tabla, dentro de la base analítica:
  1. Descarta del lote las filas idénticas a la versión vigente (releídas por el solapamiento).
  2. Arma los candidatos: lo nuevo del lote más lo que sigue en cuarentena (reintento),
     dejando una sola versión por clave natural (regla de supervivencia: la más reciente).
  3. Evalúa las reglas: las de cuarentena apartan el registro; las de marcar lo etiquetan.
  4. Limpia los textos y hace UPSERT en stg_clean (solo si el registro cambió).
  5. Da por resueltos los rechazos anteriores de registros que ahora sí pasaron.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import psycopg

from etl.config import TablaFuente, reglas_de

TIPOS_TEXTO = ("character varying", "text")

# Los identificadores de este módulo vienen del catálogo de la base y de etl/config.py
# (nunca de datos externos), por eso el SQL se arma con f-strings.


@dataclass
class ResultadoLimpieza:
    tabla: TablaFuente
    candidatos: int = 0
    insertadas: int = 0
    actualizadas: int = 0
    rechazadas: int = 0
    sin_cambios: int = 0
    duplicadas: int = 0
    duracion_ms: int = 0
    fallas_por_regla: dict[str, int] = field(default_factory=dict)


def _expr_limpia(columna: str, tipo: str) -> str:
    """Textos: sin caracteres de control, espacios múltiples colapsados y sin espacios extremos."""
    if tipo not in TIPOS_TEXTO:
        return f"r.{columna}"
    sin_control = rf"regexp_replace(r.{columna}, '[\x01-\x08\x0B\x0C\x0E-\x1F]', '', 'g')"
    return rf"btrim(regexp_replace({sin_control}, '\s+', ' ', 'g'))"


def limpiar_tabla(
    dst: psycopg.Connection,
    tabla: TablaFuente,
    columnas: list[tuple[str, str]],
    batch_id: int,
) -> ResultadoLimpieza:
    inicio = time.perf_counter()
    res = ResultadoLimpieza(tabla)
    t, pk = tabla.staging, tabla.pk
    nombres = [c for c, _ in columnas]
    lista = ", ".join(nombres)
    huella = f"md5(ROW({', '.join(f'r.{c}' for c in nombres)})::text)"
    p = {"b": batch_id, "t": tabla.origen}

    # 1. Releídas sin cambios: no aportan historia nueva a raw
    res.sin_cambios = dst.execute(
        f"DELETE FROM stg_raw.{t} r USING stg_clean.{t} c "
        f"WHERE r._batch_id = %(b)s AND c.{pk} = r.{pk} AND c._row_hash = {huella}",
        p,
    ).rowcount

    # 2. Candidatos: una versión por clave (la más reciente)
    en_lote = dst.execute(
        f"SELECT count(*) FROM stg_raw.{t} WHERE _batch_id = %(b)s", p
    ).fetchone()[0]
    dst.execute(
        f"CREATE TEMP TABLE _cand ON COMMIT DROP AS "
        f"SELECT r.*, {huella} AS _h FROM ("
        f"  SELECT DISTINCT ON ({pk}) * FROM stg_raw.{t} "
        f"  WHERE _batch_id = %(b)s OR {pk} IN (SELECT natural_key FROM "
        f"    stg_quarantine.registro_rechazado WHERE source_table = %(t)s AND resolved_at IS NULL)"
        f"  ORDER BY {pk}, last_edited_when DESC, _raw_id DESC) r",
        p,
    )
    res.candidatos = dst.execute("SELECT count(*) FROM _cand").fetchone()[0]
    del_lote = dst.execute("SELECT count(*) FROM _cand WHERE _batch_id = %(b)s", p).fetchone()[0]
    res.duplicadas = en_lote - del_lote

    # 3. Reglas
    marcas = []
    for regla in reglas_de(tabla):
        if regla.accion == "cuarentena":
            fallas = dst.execute(
                f"INSERT INTO stg_quarantine.registro_rechazado "
                f"(execution_id, source_table, natural_key, rule_code, rule_detail, payload) "
                f"SELECT %(b)s, %(t)s, r.{pk}, %(codigo)s, %(detalle)s, to_jsonb(r) - '_h'::text "
                f"FROM _cand r WHERE ({regla.condicion}) IS TRUE "
                f"ON CONFLICT (source_table, natural_key, rule_code) DO UPDATE SET "
                f"execution_id = EXCLUDED.execution_id, payload = EXCLUDED.payload, "
                f"rule_detail = EXCLUDED.rule_detail, rejected_at = now(), resolved_at = NULL",
                {**p, "codigo": regla.codigo, "detalle": regla.descripcion},
            ).rowcount
        else:
            fallas = dst.execute(
                f"SELECT count(*) FROM _cand r WHERE ({regla.condicion}) IS TRUE"
            ).fetchone()[0]
            marcas.append(f"CASE WHEN ({regla.condicion}) IS TRUE THEN '{regla.codigo}' END")
        res.fallas_por_regla[regla.codigo] = fallas

    rechazado = (
        f"EXISTS (SELECT 1 FROM stg_quarantine.registro_rechazado q WHERE q.execution_id = %(b)s "
        f"AND q.source_table = %(t)s AND q.natural_key = r.{pk})"
    )
    res.rechazadas = dst.execute(f"SELECT count(*) FROM _cand r WHERE {rechazado}", p).fetchone()[0]

    # 4. UPSERT en clean: inserta lo nuevo y actualiza solo lo que cambió
    flags = f"array_remove(ARRAY[{', '.join(marcas)}], NULL)::text[]" if marcas else "'{}'::text[]"
    limpias = ", ".join(_expr_limpia(c, tipo) for c, tipo in columnas)
    asignaciones = ", ".join(f"{c} = EXCLUDED.{c}" for c in nombres if c != pk)
    res.insertadas, res.actualizadas = dst.execute(
        f"WITH cambios AS ("
        f"  INSERT INTO stg_clean.{t} AS c "
        f"    ({lista}, _batch_id, _extracted_at, _row_hash, _dq_flags) "
        f"  SELECT {limpias}, %(b)s, r._extracted_at, r._h, {flags} "
        f"  FROM _cand r WHERE NOT {rechazado} "
        f"  ON CONFLICT ({pk}) DO UPDATE SET {asignaciones}, _batch_id = EXCLUDED._batch_id, "
        f"    _extracted_at = EXCLUDED._extracted_at, _row_hash = EXCLUDED._row_hash, "
        f"    _dq_flags = EXCLUDED._dq_flags "
        f"  WHERE (c._row_hash <> EXCLUDED._row_hash OR c._dq_flags <> EXCLUDED._dq_flags) "
        f"    AND EXCLUDED.last_edited_when >= c.last_edited_when "
        f"  RETURNING (xmax = 0) AS es_nueva) "
        f"SELECT count(*) FILTER (WHERE es_nueva), count(*) FILTER (WHERE NOT es_nueva) "
        f"FROM cambios",
        p,
    ).fetchone()

    # 5. Rechazos anteriores de registros que en esta ejecución ya no fallaron esa regla
    dst.execute(
        f"UPDATE stg_quarantine.registro_rechazado q SET resolved_at = now() "
        f"WHERE q.source_table = %(t)s AND q.resolved_at IS NULL AND q.execution_id <> %(b)s "
        f"AND q.natural_key IN (SELECT {pk} FROM _cand)",
        p,
    )

    # Evidencia de calidad del lote
    for regla in reglas_de(tabla):
        dst.execute(
            "INSERT INTO audit.dq_result VALUES (%s, %s, %s, %s, %s, %s)",
            (
                batch_id,
                tabla.origen,
                regla.codigo,
                regla.accion,
                res.candidatos,
                res.fallas_por_regla[regla.codigo],
            ),
        )
    dst.execute("DROP TABLE _cand")
    res.duracion_ms = int((time.perf_counter() - inicio) * 1000)
    return res
