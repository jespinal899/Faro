"""Entrenamiento y evaluación del pronóstico (flujo obligatorio de la guía, sección 7).

1. Serie SOLO con ventas reales y semanas completas (ml.ventas_semanales).
2. Muestras (grupo, origen, horizonte) con variables que solo usan el pasado.
3. Separación temporal por semana pronosticada: desarrollo / prueba (las últimas 16 semanas).
4. Validación cruzada temporal en desarrollo: 4 pliegues de 13 semanas (un año), cada uno
   validado con un modelo entrenado solo con semanas anteriores.
5. Líneas base (ingenuo, medias móviles, estacional): la mejor en validación es la referencia.
6. Candidatos comparados por su error fuera de pliegue (la prueba no decide nada).
7. Rango probable calibrado con los errores fuera de pliegue del candidato elegido.
8. Evaluación final, una sola vez, en PRUEBA: modelo contra líneas base, por horizonte y grupo.
9. Modelo de producción: la configuración elegida reentrenada con toda la historia real.
10. Registro en ml.modelo (versión, parámetros, métricas, datos) y ml.prediccion_prueba.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import (
    CANDIDATOS,
    COBERTURA,
    HISTORIA_MINIMA,
    HORIZONTES,
    PLIEGUES,
    SEMANAS_MINIMAS_ENTRENAMIENTO,
    SEMANAS_NIVEL,
    SEMANAS_PLIEGUE,
    SEMANAS_PRUEBA,
    SEMILLA,
)
from .datos import Serie, huella, leer, preparar
from .evaluacion import Cortes, cortes, metricas, pliegue, separar
from .modelos import ModeloPronostico, describir
from .registro import guardar_modelo, guardar_prueba
from .variables import LINEAS_BASE, muestras


@dataclass
class Resultado:
    serie: Serie
    cortes: Cortes
    conteos: dict[str, int]
    candidatos: list[dict]
    lineas_base_validacion: dict[str, float]
    mejor_linea_base: str
    elegido: dict
    modelo: ModeloPronostico
    predicciones_prueba: pd.DataFrame
    info: dict
    modelo_id: int | None = None
    version: str | None = None


def _resumen_datos(serie: Serie) -> list[dict]:
    """Distribución por grupo: tamaño, variabilidad y crecimiento del último año."""
    v = serie.ventas
    total = v.sum().sum()
    filas = []
    for grupo in v.columns:
        y = v[grupo].dropna()
        ultimo, previo = y.iloc[-52:].sum(), y.iloc[-104:-52].sum()
        filas.append(
            {
                "grupo": grupo,
                "semanas": int(len(y)),
                "media_semanal": float(y.mean()),
                "coef_variacion_pct": float(100 * y.std() / y.mean()),
                "crecimiento_anual_pct": float(100 * (ultimo / previo - 1)) if previo else None,
                "participacion_pct": float(100 * y.sum() / total),
                "semanas_sin_venta": int((y == 0).sum()),
            }
        )
    return filas


def _evaluar(real: pd.Series, pronostico: np.ndarray, horizonte: pd.Series) -> dict:
    por_horizonte = {
        str(h): metricas(real[horizonte == h], pronostico[(horizonte == h).to_numpy()])
        for h in HORIZONTES
    }
    return {"total": metricas(real, pronostico), "por_horizonte": por_horizonte}


def entrenar(conn, *, guardar: bool = True, commit_codigo: str | None = None) -> Resultado:
    serie = preparar(leer(conn), solo_reales=True)
    todas = muestras(serie.ventas)
    c = cortes(todas)
    desarrollo, prueba = separar(todas, c)
    particiones = [pliegue(desarrollo, inicio, fin) for inicio, fin in c.pliegues]
    semanas_primer_pliegue = particiones[0][0]["semana"].nunique()
    if semanas_primer_pliegue < SEMANAS_MINIMAS_ENTRENAMIENTO:
        raise ValueError(
            f"Historia insuficiente: el primer pliegue tendría {semanas_primer_pliegue} semanas "
            f"para entrenar (mínimo {SEMANAS_MINIMAS_ENTRENAMIENTO}). La serie tiene "
            f"{len(serie.ventas)} semanas reales completas."
        )
    validacion = pd.concat([val for _, val in particiones])

    # Líneas base en validación: la mejor es la referencia a superar
    bases_val = {
        nombre: metricas(validacion["real"], validacion[f"base_{nombre}"])["wape"]
        for nombre in LINEAS_BASE
    }
    mejor_base = min(bases_val, key=bases_val.get)

    # Candidatos: en cada pliegue se entrenan con lo anterior y se miden en el pliegue
    candidatos = []
    for config in CANDIDATOS:
        fuera_de_pliegue, por_pliegue = [], []
        for entrenamiento, val in particiones:
            p = ModeloPronostico.entrenar(config, entrenamiento).predecir(val)
            fuera_de_pliegue.append(p)
            por_pliegue.append(metricas(val["real"], p)["wape"])
        prediccion = np.concatenate(fuera_de_pliegue)
        candidatos.append(
            {
                "nombre": describir(config),
                "config": config,
                "wape_validacion": metricas(validacion["real"], prediccion)["wape"],
                "wape_por_pliegue": por_pliegue,
                "prediccion": prediccion,
            }
        )
    ganador = min(candidatos, key=lambda x: x["wape_validacion"])
    elegido = ganador["config"]

    # Rango probable: errores fuera de pliegue del elegido (un año completo de semanas)
    calibrador = ModeloPronostico(config=elegido, estimador=None)
    calibrador.calibrar(validacion, ganador["prediccion"])

    # Evaluación final en prueba (una sola vez), con el modelo que vio todo el desarrollo
    evaluado = ModeloPronostico.entrenar(elegido, desarrollo)
    evaluado.cuantiles = calibrador.cuantiles
    pronostico = evaluado.predecir(prueba)
    inferior, superior = evaluado.rango(prueba, pronostico)
    base = prueba[f"base_{mejor_base}"].to_numpy()
    dentro = (prueba["real"].to_numpy() >= inferior) & (prueba["real"].to_numpy() <= superior)

    resultado_prueba = {
        "modelo": _evaluar(prueba["real"], pronostico, prueba["horizonte"]),
        "lineas_base": {
            nombre: _evaluar(
                prueba["real"], prueba[f"base_{nombre}"].to_numpy(), prueba["horizonte"]
            )
            for nombre in LINEAS_BASE
        },
        "cobertura_rango_pct": {
            "total": float(100 * dentro.mean()),
            "por_horizonte": {
                str(h): float(100 * dentro[(prueba["horizonte"] == h).to_numpy()].mean())
                for h in HORIZONTES
            },
        },
        "por_grupo": {
            grupo: {
                "modelo_wape": metricas(prueba["real"][m], pronostico[m.to_numpy()])["wape"],
                "linea_base_wape": metricas(prueba["real"][m], base[m.to_numpy()])["wape"],
            }
            for grupo in sorted(prueba["grupo"].unique())
            for m in [prueba["grupo"] == grupo]
        },
    }
    wape_modelo = resultado_prueba["modelo"]["total"]["wape"]
    wape_base = resultado_prueba["lineas_base"][mejor_base]["total"]["wape"]
    resultado_prueba["mejora_vs_linea_base_pct"] = float(100 * (1 - wape_modelo / wape_base))

    predicciones_prueba = prueba[["semana", "grupo", "horizonte", "origen", "real"]].assign(
        pronostico=pronostico, inferior=inferior, superior=superior, linea_base=base
    )

    # Modelo de producción: misma configuración, toda la historia real
    final = ModeloPronostico.entrenar(elegido, todas)
    final.cuantiles = calibrador.cuantiles

    conteos = {
        "entrenamiento_primer_pliegue": len(particiones[0][0]),
        "validacion": len(validacion),
        "desarrollo": len(desarrollo),
        "prueba": len(prueba),
        "produccion": len(todas),
    }
    for x in candidatos:
        x.pop("prediccion")  # ya se usó para calibrar; no va al registro
    info = {
        "algoritmo": describir(elegido),
        "parametros": {
            **elegido,
            "semilla": SEMILLA,
            "horizontes": list(HORIZONTES),
            "semanas_nivel": SEMANAS_NIVEL,
            "pliegues": PLIEGUES,
            "semanas_pliegue": SEMANAS_PLIEGUE,
            "semanas_prueba": SEMANAS_PRUEBA,
            "historia_minima": HISTORIA_MINIMA,
        },
        "variables": final.variables,
        "grupos": {"incluidos": list(serie.ventas.columns), "excluidos": serie.excluidos},
        "metricas": {
            "principal": "wape",
            "muestras": conteos,
            "cortes": {
                "pliegues": [[str(a.date()), str(b.date())] for a, b in c.pliegues],
                "prueba": str(c.prueba.date()),
            },
            "datos": _resumen_datos(serie),
            "validacion": {
                "candidatos": [
                    {
                        "nombre": x["nombre"],
                        "wape": x["wape_validacion"],
                        "por_pliegue": x["wape_por_pliegue"],
                    }
                    for x in candidatos
                ],
                "lineas_base": bases_val,
                "mejor_linea_base": mejor_base,
            },
            "prueba": resultado_prueba,
        },
        "intervalo": {
            "cobertura_objetivo_pct": 100 * COBERTURA,
            "cuantiles_por_horizonte": {str(h): q for h, q in calibrador.cuantiles.items()},
        },
        "datos_desde": serie.desde,
        "datos_hasta": serie.hasta,
        "prueba_desde": c.prueba,
        "filas_entrenamiento": len(todas),
        "huella_datos": huella(serie.ventas),
        "commit_codigo": commit_codigo,
    }
    resultado = Resultado(
        serie=serie,
        cortes=c,
        conteos=conteos,
        candidatos=candidatos,
        lineas_base_validacion=bases_val,
        mejor_linea_base=mejor_base,
        elegido=elegido,
        modelo=final,
        predicciones_prueba=predicciones_prueba,
        info=info,
    )
    if guardar:
        resultado.modelo_id, resultado.version = guardar_modelo(conn, final, info)
        guardar_prueba(conn, resultado.modelo_id, predicciones_prueba)
        conn.commit()
    return resultado
