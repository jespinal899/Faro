"""Lectura de la serie de entrada (vista ml.ventas_semanales) y armado de la serie semanal."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

import pandas as pd

from .config import HISTORIA_MINIMA

SQL_SERIE = """
SELECT semana, grupo, venta_neta, venta_neta_real, venta_neta_simulada,
       primera_fecha, ultima_fecha, ultima_fecha_real
FROM ml.ventas_semanales
ORDER BY semana, grupo
"""

COLUMNAS = [
    "semana",
    "grupo",
    "venta_neta",
    "venta_neta_real",
    "venta_neta_simulada",
    "primera_fecha",
    "ultima_fecha",
    "ultima_fecha_real",
]


@dataclass(frozen=True)
class Serie:
    """Ventas netas por semana (filas, lunes) y grupo (columnas), solo semanas completas."""

    ventas: pd.DataFrame
    solo_reales: bool
    incluye_simulados: bool
    excluidos: dict[str, str] = field(default_factory=dict)

    @property
    def desde(self) -> pd.Timestamp:
        return self.ventas.index.min()

    @property
    def hasta(self) -> pd.Timestamp:
        return self.ventas.index.max()


def leer(conn) -> pd.DataFrame:
    """Lee la vista ml.ventas_semanales (una fila por semana y grupo)."""
    filas = conn.execute(SQL_SERIE).fetchall()
    df = pd.DataFrame(filas, columns=COLUMNAS)
    for columna in ("semana", "primera_fecha", "ultima_fecha", "ultima_fecha_real"):
        df[columna] = pd.to_datetime(df[columna])
    for columna in ("venta_neta", "venta_neta_real", "venta_neta_simulada"):
        df[columna] = df[columna].astype(float)
    return df


def preparar(filas: pd.DataFrame, *, solo_reales: bool) -> Serie:
    """Arma la serie semanal continua, solo con semanas completas (lunes a sábado).

    - Entrenamiento: solo_reales=True usa únicamente ventas reales (hasta la última fecha real).
    - Pronóstico: solo_reales=False usa todo lo que hay en el DW, incluidas las simuladas.
    Una semana dentro de la historia de un grupo sin ventas vale 0 (es un dato, no un faltante).
    """
    if filas.empty:
        raise ValueError("La vista ml.ventas_semanales no tiene datos")
    inicio = filas["primera_fecha"].min()
    fin = filas["ultima_fecha_real"].max() if solo_reales else filas["ultima_fecha"].max()
    valor = "venta_neta_real" if solo_reales else "venta_neta"

    completas = filas[(filas["semana"] >= inicio) & (filas["semana"] + pd.Timedelta(days=5) <= fin)]
    if completas.empty:
        raise ValueError("No hay semanas completas en la serie")
    ancho = completas.pivot_table(index="semana", columns="grupo", values=valor, aggfunc="sum")
    semanas = pd.date_range(ancho.index.min(), ancho.index.max(), freq="W-MON", name="semana")
    ancho = ancho.reindex(semanas)

    incluidos, excluidos = [], {}
    for grupo in ancho.columns:
        primera = ancho[grupo].first_valid_index()
        historia = len(ancho.loc[primera:]) if primera is not None else 0
        if historia >= HISTORIA_MINIMA:
            incluidos.append(grupo)
        else:
            desde = primera.date().isoformat() if primera is not None else "—"
            excluidos[grupo] = (
                f"historia insuficiente: {historia} semanas desde {desde} "
                f"(mínimo {HISTORIA_MINIMA})"
            )
    ventas = ancho[sorted(incluidos)]
    # Dentro de la historia de cada grupo, una semana sin filas = semana sin ventas
    for grupo in ventas.columns:
        primera = ventas[grupo].first_valid_index()
        ventas.loc[primera:, grupo] = ventas.loc[primera:, grupo].fillna(0.0)

    simuladas = completas[completas["semana"].isin(semanas)]["venta_neta_simulada"].sum()
    return Serie(
        ventas=ventas,
        solo_reales=solo_reales,
        incluye_simulados=(not solo_reales) and simuladas > 0,
        excluidos=excluidos,
    )


def huella(ventas: pd.DataFrame) -> str:
    """md5 de la serie (redondeada al centavo): identifica exactamente qué datos se usaron."""
    texto = ventas.round(2).to_csv(lineterminator="\n")
    return hashlib.md5(texto.encode("utf-8")).hexdigest()
