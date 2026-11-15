"""Métricas de error y separación temporal de las muestras."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import PLIEGUES, SEMANAS_PLIEGUE, SEMANAS_PRUEBA


def metricas(real, pronostico) -> dict[str, float]:
    """MAE, RMSE, WAPE, sMAPE y sesgo (los tres últimos en %).

    WAPE = Σ|error| / Σ real: el error en % del volumen vendido (la métrica principal, porque
    no se dispara con semanas pequeñas como el MAPE). Sesgo > 0 = el pronóstico se pasa.
    """
    real = np.asarray(real, dtype=float)
    pronostico = np.asarray(pronostico, dtype=float)
    error = pronostico - real
    denominador = np.abs(real) + np.abs(pronostico)
    return {
        "mae": float(np.mean(np.abs(error))),
        "rmse": float(np.sqrt(np.mean(error**2))),
        "wape": float(100 * np.sum(np.abs(error)) / np.sum(np.abs(real))),
        "smape": float(
            100 * np.mean(np.where(denominador > 0, 2 * np.abs(error) / denominador, 0))
        ),
        "sesgo": float(100 * np.sum(error) / np.sum(real)),
    }


@dataclass(frozen=True)
class Cortes:
    """Fechas (semana pronosticada) que separan los conjuntos.

    - pliegues: (inicio, fin exclusivo) de cada pliegue de validación, en orden cronológico.
    - prueba: primera semana de la prueba (nada desde aquí se usa para entrenar ni elegir).
    """

    pliegues: tuple[tuple[pd.Timestamp, pd.Timestamp], ...]
    prueba: pd.Timestamp

    @property
    def validacion(self) -> pd.Timestamp:
        return self.pliegues[0][0]


def cortes(muestras: pd.DataFrame) -> Cortes:
    ultima = muestras["semana"].max()
    prueba = ultima - pd.Timedelta(weeks=SEMANAS_PRUEBA - 1)
    pliegues = []
    for k in range(PLIEGUES, 0, -1):
        inicio = prueba - pd.Timedelta(weeks=k * SEMANAS_PLIEGUE)
        pliegues.append((inicio, inicio + pd.Timedelta(weeks=SEMANAS_PLIEGUE)))
    return Cortes(pliegues=tuple(pliegues), prueba=prueba)


def separar(muestras: pd.DataFrame, c: Cortes) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Desarrollo (todo lo anterior a la prueba) y prueba, según la semana PRONOSTICADA."""
    return muestras[muestras["semana"] < c.prueba], muestras[muestras["semana"] >= c.prueba]


def pliegue(
    desarrollo: pd.DataFrame, inicio: pd.Timestamp, fin: pd.Timestamp
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Entrenamiento (semanas pronosticadas antes del pliegue) y validación (las del pliegue).

    Las variables de una muestra son anteriores a su semana pronosticada: el modelo de cada
    pliegue nunca ve el período en que se lo evalúa (nunca se separa al azar).
    """
    entrenamiento = desarrollo[desarrollo["semana"] < inicio]
    validacion = desarrollo[(desarrollo["semana"] >= inicio) & (desarrollo["semana"] < fin)]
    return entrenamiento, validacion
