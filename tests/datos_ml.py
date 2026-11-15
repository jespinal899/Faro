"""Serie semanal sintética con el formato de ml.ventas_semanales (para probar el pronóstico)."""

from __future__ import annotations

import numpy as np
import pandas as pd

INICIO = pd.Timestamp("2013-01-07")  # lunes


def filas_sinteticas(
    semanas: int = 170,
    grupos: dict[str, float] | None = None,
    grupo_corto: str | None = "Nuevo",
    semanas_simuladas: int = 0,
    semilla: int = 7,
) -> pd.DataFrame:
    """Nivel + estacionalidad suave + ruido; un grupo corto opcional (debe quedar excluido).

    Las últimas `semanas_simuladas` semanas son ventas simuladas (no reales).
    """
    grupos = grupos or {"Grande": 500_000.0, "Mediano": 80_000.0, "Chico": 6_000.0}
    rng = np.random.default_rng(semilla)
    filas = []
    for k in range(semanas):
        semana = INICIO + pd.Timedelta(weeks=k)
        simulada = k >= semanas - semanas_simuladas
        estacion = 1 + 0.08 * np.sin(2 * np.pi * k / 52)
        activos = dict(grupos)
        if grupo_corto and k >= semanas - 20:
            activos[grupo_corto] = 40_000.0
        for grupo, nivel in activos.items():
            venta = float(nivel * estacion * rng.normal(1.0, 0.10))
            filas.append(
                {
                    "semana": semana,
                    "grupo": grupo,
                    "venta_neta": venta,
                    "venta_neta_real": 0.0 if simulada else venta,
                    "venta_neta_simulada": venta if simulada else 0.0,
                    "primera_fecha": semana,
                    "ultima_fecha": semana + pd.Timedelta(days=5),
                    "ultima_fecha_real": pd.NaT if simulada else semana + pd.Timedelta(days=5),
                }
            )
    return pd.DataFrame(filas)
