"""Modelo de pronóstico: un estimador de scikit-learn sobre ventas relativas al nivel reciente,
más un rango probable calibrado con los errores de validación."""

from __future__ import annotations

import io
from dataclasses import dataclass, field

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .config import COBERTURA, HORIZONTES, SEMILLA
from .variables import CONJUNTOS, VARIABLES_CATEGORICAS


def describir(config: dict) -> str:
    """Nombre legible de una configuración, p. ej. 'ridge[rezagos](alpha=10.0)'."""
    params = ", ".join(f"{k}={v}" for k, v in config.items() if k not in ("algoritmo", "variables"))
    return f"{config['algoritmo']}[{config['variables']}]({params})"


def variables_de(config: dict) -> list[str]:
    return CONJUNTOS[config["variables"]] + VARIABLES_CATEGORICAS


def crear_estimador(config: dict) -> Pipeline:
    """Pipeline de scikit-learn para una configuración candidata."""
    numericas = CONJUNTOS[config["variables"]]
    grupo = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    if config["algoritmo"] == "ridge":
        columnas = ColumnTransformer(
            [("num", StandardScaler(), numericas), ("grupo", grupo, VARIABLES_CATEGORICAS)]
        )
        return Pipeline([("variables", columnas), ("modelo", Ridge(alpha=config["alpha"]))])
    if config["algoritmo"] == "hgb":
        columnas = ColumnTransformer(
            [("num", "passthrough", numericas), ("grupo", grupo, VARIABLES_CATEGORICAS)]
        )
        modelo = HistGradientBoostingRegressor(
            loss="absolute_error",  # el WAPE mide error absoluto
            max_depth=config["max_depth"],
            learning_rate=config["learning_rate"],
            max_iter=config["max_iter"],
            early_stopping=False,
            random_state=SEMILLA,
        )
        return Pipeline([("variables", columnas), ("modelo", modelo)])
    raise ValueError(f"Algoritmo desconocido: {config['algoritmo']}")


def pesos(muestras: pd.DataFrame) -> np.ndarray:
    """Peso de cada muestra proporcional al volumen del grupo (normalizado a media 1).

    El modelo aprende ventas RELATIVAS, donde un grupo chico y volátil pesaría lo mismo que uno
    grande; el WAPE, en cambio, pondera por volumen. Los pesos alinean ambos criterios.
    """
    nivel = muestras["nivel"].to_numpy(dtype=float)
    return nivel / nivel.mean()


@dataclass
class ModeloPronostico:
    """Estimador entrenado + cuantiles del error por horizonte (rango probable)."""

    config: dict
    estimador: Pipeline
    cuantiles: dict[int, tuple[float, float]] = field(default_factory=dict)
    grupos: list[str] = field(default_factory=list)

    @classmethod
    def entrenar(cls, config: dict, muestras: pd.DataFrame) -> ModeloPronostico:
        estimador = crear_estimador(config)
        estimador.fit(
            muestras[variables_de(config)],
            muestras["objetivo"],
            modelo__sample_weight=pesos(muestras),
        )
        return cls(config=config, estimador=estimador, grupos=sorted(muestras["grupo"].unique()))

    @property
    def variables(self) -> list[str]:
        return variables_de(self.config)

    def predecir(self, muestras: pd.DataFrame) -> np.ndarray:
        """Venta neta pronosticada (nunca negativa)."""
        relativa = np.clip(self.estimador.predict(muestras[self.variables]), 0.0, None)
        return relativa * muestras["nivel"].to_numpy()

    def calibrar(self, muestras: pd.DataFrame, pronostico: np.ndarray) -> None:
        """Cuantiles de real/pronóstico por horizonte.

        `pronostico` debe venir de modelos que NO vieron esas muestras (fuera de pliegue).
        """
        cociente = muestras["real"].to_numpy() / np.where(pronostico > 0, pronostico, np.nan)
        cola = (1 - COBERTURA) / 2
        for h in HORIZONTES:
            valores = cociente[(muestras["horizonte"] == h).to_numpy() & ~np.isnan(cociente)]
            self.cuantiles[h] = (
                float(np.quantile(valores, cola)),
                float(np.quantile(valores, 1 - cola)),
            )

    def rango(
        self, muestras: pd.DataFrame, pronostico: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        """Rango probable (80 %) alrededor del pronóstico."""
        inferior = np.array([self.cuantiles[h][0] for h in muestras["horizonte"]]) * pronostico
        superior = np.array([self.cuantiles[h][1] for h in muestras["horizonte"]]) * pronostico
        return np.minimum(inferior, pronostico), np.maximum(superior, pronostico)

    def a_bytes(self) -> bytes:
        buffer = io.BytesIO()
        joblib.dump(self, buffer, compress=3)
        return buffer.getvalue()

    @staticmethod
    def desde_bytes(datos: bytes) -> ModeloPronostico:
        # Solo se cargan artefactos escritos por el propio proceso (rol faro_ml o el dueño)
        return joblib.load(io.BytesIO(datos))
