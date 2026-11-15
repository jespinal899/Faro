"""Construcción de variables (feature engineering) sin fuga de información futura.

Cada muestra es (grupo, semana de origen t, horizonte h): con lo conocido hasta el cierre de
la semana t se pronostica la venta de la semana t+h. TODAS las variables usan semanas <= t;
la única que mira el calendario futuro es la semana del año de t+h, que se conoce de antemano.

Escala: las ventas se expresan relativas al nivel reciente del grupo (media de las últimas
8 semanas hasta t). El objetivo es y[t+h] / nivel; el pronóstico se reconstruye multiplicando.
"""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd

from .config import HISTORIA_REQUERIDA, HORIZONTES, SEMANAS_ANIO, SEMANAS_NIVEL

REZAGOS = 13  # un trimestre de semanas recientes

# Rezagos: venta de las semanas t, t-1, ..., t-12 relativa al nivel. El modelo aprende cuánto
# pesa cada semana reciente (un promedio móvil es el caso particular de pesos iguales).
VARIABLES_REZAGOS = ["horizonte"] + [f"rezago_{k}" for k in range(REZAGOS)]
# Contexto: tendencia, estacionalidad y calendario. La validación decide si aportan.
VARIABLES_CONTEXTO = [
    "tendencia",  # nivel de las últimas 8 semanas / nivel de las 8 anteriores
    "crecimiento_anual",  # nivel actual / nivel de hace un año
    "estacional",  # venta de la misma semana objetivo hace un año / nivel de hace un año
    "estacional_suave",  # ídem, promedio de 3 semanas alrededor (menos ruido)
    "volatilidad",  # desviación de las últimas 8 semanas / nivel
    "semana_sin",  # semana del año de la semana objetivo (calendario, se conoce antes)
    "semana_cos",
]
CONJUNTOS = {
    "rezagos": VARIABLES_REZAGOS,
    "rezagos+contexto": VARIABLES_REZAGOS + VARIABLES_CONTEXTO,
}
VARIABLES_NUMERICAS = VARIABLES_REZAGOS + VARIABLES_CONTEXTO
VARIABLES_CATEGORICAS = ["grupo"]
VARIABLES = VARIABLES_NUMERICAS + VARIABLES_CATEGORICAS

# Líneas base: predicciones simples que el modelo debe superar para ser útil
LINEAS_BASE = {
    "ingenuo": "la venta de la última semana conocida",
    "media_movil_4": "el promedio de las últimas 4 semanas",
    "media_movil_13": "el promedio de las últimas 13 semanas (un trimestre)",
    "estacional": "la venta de la misma semana del año anterior",
}


def muestras(
    ventas: pd.DataFrame,
    *,
    origenes: Iterable[pd.Timestamp] | None = None,
    horizontes: Iterable[int] = HORIZONTES,
    con_objetivo: bool = True,
) -> pd.DataFrame:
    """Una fila por (grupo, origen, horizonte) con variables, líneas base y, si se pide, el real.

    - ventas: serie semanal (índice = lunes de cada semana, columnas = grupos).
    - origenes: semanas de origen a usar (por defecto, todas las que tengan historia suficiente).
    - con_objetivo: False para pronosticar el futuro (la semana t+h aún no existe).
    """
    semanas = ventas.index
    n = len(semanas)
    posiciones = (
        range(HISTORIA_REQUERIDA - 1, n)
        if origenes is None
        else [semanas.get_loc(pd.Timestamp(o)) for o in origenes]
    )
    horizontes = tuple(horizontes)
    filas = []
    for grupo in ventas.columns:
        y = ventas[grupo].to_numpy(dtype=float)
        for i in posiciones:
            if i < HISTORIA_REQUERIDA - 1:
                continue
            historia = y[i - HISTORIA_REQUERIDA + 1 : i + 1]
            if np.isnan(historia).any():
                continue  # el grupo aún no existía en parte de la ventana
            nivel = historia[-SEMANAS_NIVEL:].mean()
            nivel_previo = y[i - 2 * SEMANAS_NIVEL + 1 : i - SEMANAS_NIVEL + 1].mean()
            # Nivel de hace un año: las 8 semanas que terminan en t-52
            nivel_anio = y[i - SEMANAS_ANIO - SEMANAS_NIVEL + 1 : i - SEMANAS_ANIO + 1].mean()
            if nivel <= 0 or nivel_previo <= 0 or nivel_anio <= 0:
                continue
            for h in horizontes:
                if con_objetivo and i + h >= n:
                    continue
                objetivo_semana = semanas[i] + pd.Timedelta(weeks=h)
                j = i + h - SEMANAS_ANIO  # misma semana objetivo, un año antes (j <= i - 48)
                semana_anio = objetivo_semana.isocalendar().week
                fila = {
                    "grupo": grupo,
                    "origen": semanas[i],
                    "semana": objetivo_semana,
                    "horizonte": h,
                    "nivel": nivel,
                    **{f"rezago_{k}": y[i - k] / nivel for k in range(REZAGOS)},
                    "tendencia": nivel / nivel_previo,
                    "crecimiento_anual": nivel / nivel_anio,
                    "estacional": y[j] / nivel_anio,
                    "estacional_suave": y[j - 1 : j + 2].mean() / nivel_anio,
                    "volatilidad": historia[-SEMANAS_NIVEL:].std() / nivel,
                    "semana_sin": np.sin(2 * np.pi * semana_anio / 52.18),
                    "semana_cos": np.cos(2 * np.pi * semana_anio / 52.18),
                    "base_ingenuo": y[i],
                    "base_media_movil_4": y[i - 3 : i + 1].mean(),
                    "base_media_movil_13": y[i - REZAGOS + 1 : i + 1].mean(),
                    "base_estacional": y[j],
                }
                if con_objetivo:
                    fila["real"] = y[i + h]
                    fila["objetivo"] = y[i + h] / nivel
                filas.append(fila)
    return pd.DataFrame(filas)
