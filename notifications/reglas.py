"""Reglas de alerta como funciones PURAS (sin base de datos): reciben datos y devuelven alertas.

Así se prueban fácilmente la condición verdadera y la falsa, como pide la guía.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from statistics import mean

SEMANAS_REFERENCIA = 4  # caída de ventas: promedio de las 4 semanas anteriores
SEMANAS_PROMEDIO_GRUPO = 13  # pronóstico bajo: promedio del último trimestre del grupo


@dataclass
class Alerta:
    regla: str
    clave_evento: str  # identifica el evento: la misma clave nunca genera otra alerta
    severidad: str  # advertencia | critica
    origen: str  # regla | modelo
    indicador: str
    entidad: str
    valor_observado: float
    umbral: float
    referencia: float | None
    periodo_desde: date
    periodo_hasta: date
    mensaje: str
    detalle: dict = field(default_factory=dict)
    incluye_simulados: bool = False


def ultima_semana_completa(hasta: date) -> date:
    """Lunes de la última semana con datos de lunes a sábado (WWI no vende los domingos)."""
    lunes = hasta - timedelta(days=hasta.weekday())
    return lunes if lunes + timedelta(days=5) <= hasta else lunes - timedelta(weeks=1)


def _usd(valor: float) -> str:
    return f"USD {valor:,.0f}"


def caida_ventas(
    semanas: dict[date, tuple[float, bool]], desde: date, hasta: date, umbral_pct: float
) -> list[Alerta]:
    """P12. semanas: {lunes: (venta neta total, incluye simulados)}."""
    actual_sem = ultima_semana_completa(hasta)
    previas = [actual_sem - timedelta(weeks=k) for k in range(1, SEMANAS_REFERENCIA + 1)]
    # Todas deben existir y estar completas (la primera semana de la historia no lo está)
    if actual_sem not in semanas or any(s not in semanas or s < desde for s in previas):
        return []
    actual, simulada = semanas[actual_sem]
    referencia = mean(semanas[s][0] for s in previas)
    if referencia <= 0:
        return []
    caida = 100 * (1 - actual / referencia)
    if caida <= umbral_pct:
        return []
    minimo = referencia * (1 - umbral_pct / 100)
    return [
        Alerta(
            regla="caida_ventas",
            clave_evento=f"caida_ventas|total|{actual_sem}",
            severidad="critica" if caida >= 2 * umbral_pct else "advertencia",
            origen="regla",
            indicador="Ventas netas semanales",
            entidad="Total WWI",
            valor_observado=actual,
            umbral=minimo,
            referencia=referencia,
            periodo_desde=actual_sem,
            periodo_hasta=actual_sem + timedelta(days=5),
            mensaje=(
                f"Las ventas netas de la semana del {actual_sem:%d/%m/%Y} ({_usd(actual)}) cayeron "
                f"{caida:.1f} % frente al promedio de las {SEMANAS_REFERENCIA} semanas anteriores "
                f"({_usd(referencia)}). Umbral: caída de {umbral_pct:.0f} %."
            ),
            detalle={
                "caida_pct": round(caida, 2),
                "umbral_pct": umbral_pct,
                "semanas_referencia": [str(s) for s in previas],
            },
            incluye_simulados=simulada or any(semanas[s][1] for s in previas),
        )
    ]


def pronostico_bajo(
    pronostico: list[dict], historia: dict[str, list[float]], umbral_pct: float
) -> list[Alerta]:
    """P13 (Machine Learning). pronostico: filas de api.pronostico; historia: ventas semanales
    completas de cada grupo hasta el origen (la más reciente al final)."""
    alertas = []
    for grupo in sorted({p["grupo"] for p in pronostico}):
        semanas = historia.get(grupo, [])[-SEMANAS_PROMEDIO_GRUPO:]
        if len(semanas) < SEMANAS_PROMEDIO_GRUPO:
            continue  # sin historia suficiente para la referencia
        promedio = mean(semanas)
        minimo = promedio * umbral_pct / 100
        filas = sorted((p for p in pronostico if p["grupo"] == grupo), key=lambda p: p["semana"])
        bajas = [p for p in filas if p["venta_neta_pronosticada"] < minimo]
        if not bajas:
            continue
        peor = min(bajas, key=lambda p: p["venta_neta_pronosticada"])
        # Crítica si hasta el extremo optimista del rango del 80 % queda bajo el umbral
        critica = peor["superior"] < minimo
        alertas.append(
            Alerta(
                regla="pronostico_bajo",
                clave_evento=f"pronostico_bajo|{grupo}|{peor['origen']}",
                severidad="critica" if critica else "advertencia",
                origen="modelo",
                indicador="Venta neta semanal PRONOSTICADA",
                entidad=grupo,
                valor_observado=peor["venta_neta_pronosticada"],
                umbral=minimo,
                referencia=promedio,
                periodo_desde=peor["semana"],
                periodo_hasta=peor["semana"] + timedelta(days=5),
                mensaje=(
                    f"PREDICCIÓN: para la semana del {peor['semana']:%d/%m/%Y} "
                    f"({peor['horizonte']} semana(s) adelante) el modelo "
                    f"{peor['version']} pronostica "
                    f"{_usd(peor['venta_neta_pronosticada'])} para {grupo}, bajo el umbral de "
                    f"{_usd(minimo)} ({umbral_pct:.0f} % de su promedio de "
                    f"{SEMANAS_PROMEDIO_GRUPO} semanas, {_usd(promedio)})."
                ),
                detalle={
                    "horizonte": peor["horizonte"],
                    "version_modelo": peor["version"],
                    "origen_pronostico": str(peor["origen"]),
                    "rango_80": [peor["inferior"], peor["superior"]],
                    "semanas_bajo_umbral": [str(p["semana"]) for p in bajas],
                },
                incluye_simulados=bool(peor.get("usa_datos_simulados")),
            )
        )
    return alertas


def ventas_bajo_costo(semanas: dict[date, dict], hasta: date, umbral_usd: float) -> list[Alerta]:
    """P14. semanas: {lunes: {lineas, facturas, perdida, venta_neta, incluye_simulados}}."""
    semana = ultima_semana_completa(hasta)
    fila = semanas.get(semana)
    if not fila or fila["perdida"] <= umbral_usd:
        return []
    return [
        Alerta(
            regla="ventas_bajo_costo",
            clave_evento=f"ventas_bajo_costo|total|{semana}",
            severidad="advertencia",
            origen="regla",
            indicador="Pérdida por ventas bajo costo",
            entidad="Total WWI",
            valor_observado=fila["perdida"],
            umbral=umbral_usd,
            referencia=None,
            periodo_desde=semana,
            periodo_hasta=semana + timedelta(days=5),
            mensaje=(
                f"En la semana del {semana:%d/%m/%Y} se vendieron {fila['lineas']} líneas "
                f"({fila['facturas']} facturas) por debajo del costo: pérdida de "
                f"{_usd(fila['perdida'])} sobre {_usd(fila['venta_neta'])} vendidos."
            ),
            detalle={
                "lineas": fila["lineas"],
                "facturas": fila["facturas"],
                "venta_neta": fila["venta_neta"],
            },
            incluye_simulados=bool(fila.get("incluye_simulados")),
        )
    ]
