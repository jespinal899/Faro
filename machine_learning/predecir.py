"""Inferencia: pronóstico de las 4 semanas siguientes a la última semana completa del DW."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .datos import leer, preparar
from .registro import cargar_vigente, guardar_pronostico
from .variables import muestras


@dataclass
class Pronostico:
    modelo_id: int
    version: str
    origen: pd.Timestamp
    usa_datos_simulados: bool
    tabla: pd.DataFrame
    excluidos: dict[str, str]


def predecir(conn, *, guardar: bool = True) -> Pronostico:
    vigente = cargar_vigente(conn)
    if vigente is None:
        raise RuntimeError("No hay un modelo vigente: ejecute primero 'entrenar'")
    modelo_id, version, modelo = vigente

    # Todo lo que hay en el DW (incluidas las ventas simuladas de la operación de demostración)
    serie = preparar(leer(conn), solo_reales=False)
    grupos = [g for g in modelo.grupos if g in serie.ventas.columns]
    excluidos = dict(serie.excluidos)
    for g in modelo.grupos:
        if g not in grupos:
            excluidos[g] = "sin historia suficiente en la serie actual"

    origen = serie.hasta
    m = muestras(serie.ventas[grupos], origenes=[origen], con_objetivo=False)
    valor = modelo.predecir(m)
    inferior, superior = modelo.rango(m, valor)
    tabla = m[["grupo", "origen", "semana", "horizonte"]].assign(
        venta_neta_pronosticada=valor, inferior=inferior, superior=superior
    )
    if guardar:
        guardar_pronostico(conn, modelo_id, tabla, serie.incluye_simulados)
        conn.commit()
    return Pronostico(
        modelo_id=modelo_id,
        version=version,
        origen=origen,
        usa_datos_simulados=serie.incluye_simulados,
        tabla=tabla,
        excluidos=excluidos,
    )
