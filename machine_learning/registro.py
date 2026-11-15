"""Registro del modelo, de su evaluación y de sus pronósticos en el esquema ml."""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
from psycopg.types.json import Jsonb

from .config import NOMBRE_MODELO
from .modelos import ModeloPronostico


def _fecha(valor) -> object:
    return pd.Timestamp(valor).date()


def _monto(valor) -> float:
    return round(float(valor), 2)


def guardar_modelo(conn, modelo: ModeloPronostico, info: dict) -> tuple[int, str]:
    """Registra el modelo como el vigente (el anterior deja de serlo). Devuelve (id, versión)."""
    version = datetime.now(UTC).strftime("%Y%m%d.%H%M%S")
    repetidas = conn.execute(
        "SELECT count(*) FROM ml.modelo WHERE version = %s OR version LIKE %s",
        (version, f"{version}-%"),
    ).fetchone()[0]
    if repetidas:  # dos entrenamientos en el mismo segundo
        version = f"{version}-{repetidas + 1}"
    conn.execute(
        "UPDATE ml.modelo SET es_vigente = false WHERE nombre = %s AND es_vigente",
        (NOMBRE_MODELO,),
    )
    modelo_id = conn.execute(
        """
        INSERT INTO ml.modelo (nombre, version, algoritmo, parametros, variables, grupos,
                               metricas, intervalo, datos_desde, datos_hasta, prueba_desde,
                               filas_entrenamiento, huella_datos, commit_codigo, es_vigente,
                               artefacto)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, true, %s)
        RETURNING modelo_id
        """,
        (
            NOMBRE_MODELO,
            version,
            info["algoritmo"],
            Jsonb(info["parametros"]),
            Jsonb(info["variables"]),
            Jsonb(info["grupos"]),
            Jsonb(info["metricas"]),
            Jsonb(info["intervalo"]),
            _fecha(info["datos_desde"]),
            _fecha(info["datos_hasta"]),
            _fecha(info["prueba_desde"]),
            info["filas_entrenamiento"],
            info["huella_datos"],
            info.get("commit_codigo"),
            modelo.a_bytes(),
        ),
    ).fetchone()[0]
    return modelo_id, version


def guardar_prueba(conn, modelo_id: int, predicciones: pd.DataFrame) -> None:
    """Guarda las predicciones del conjunto de prueba (modelo, rango y línea base)."""
    columnas = (
        "modelo_id, semana, grupo, horizonte, origen, real, pronostico, inferior, superior, "
        "linea_base"
    )
    with conn.cursor().copy(f"COPY ml.prediccion_prueba ({columnas}) FROM STDIN") as copia:
        for f in predicciones.itertuples(index=False):
            copia.write_row(
                (
                    modelo_id,
                    _fecha(f.semana),
                    f.grupo,
                    int(f.horizonte),
                    _fecha(f.origen),
                    _monto(f.real),
                    _monto(f.pronostico),
                    _monto(f.inferior),
                    _monto(f.superior),
                    _monto(f.linea_base),
                )
            )


def cargar_vigente(conn) -> tuple[int, str, ModeloPronostico] | None:
    """El modelo vigente: (id, versión, modelo), o None si nunca se entrenó."""
    fila = conn.execute(
        "SELECT modelo_id, version, artefacto FROM ml.modelo WHERE nombre = %s AND es_vigente",
        (NOMBRE_MODELO,),
    ).fetchone()
    if fila is None:
        return None
    return fila[0], fila[1], ModeloPronostico.desde_bytes(bytes(fila[2]))


def guardar_pronostico(
    conn, modelo_id: int, pronostico: pd.DataFrame, usa_datos_simulados: bool
) -> None:
    """Inserta el pronóstico; si ya existe el de ese origen (re-ejecución), lo reemplaza."""
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO ml.pronostico (modelo_id, origen, semana, grupo, horizonte,
                                       venta_neta_pronosticada, inferior, superior,
                                       usa_datos_simulados)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (modelo_id, origen, semana, grupo) DO UPDATE
            SET venta_neta_pronosticada = EXCLUDED.venta_neta_pronosticada,
                inferior = EXCLUDED.inferior,
                superior = EXCLUDED.superior,
                usa_datos_simulados = EXCLUDED.usa_datos_simulados,
                generado_en = now()
            """,
            [
                (
                    modelo_id,
                    _fecha(f.origen),
                    _fecha(f.semana),
                    f.grupo,
                    int(f.horizonte),
                    _monto(f.venta_neta_pronosticada),
                    _monto(f.inferior),
                    _monto(f.superior),
                    usa_datos_simulados,
                )
                for f in pronostico.itertuples(index=False)
            ],
        )
