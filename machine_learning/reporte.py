"""Reportes en Markdown del entrenamiento y del pronóstico (evidencia para la documentación)."""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from .config import COBERTURA, HORIZONTES
from .entrenar import Resultado
from .predecir import Pronostico
from .variables import LINEAS_BASE


def _usd(valor: float) -> str:
    return f"{valor:,.0f}"


def _pct(valor: float | None, signo: bool = False) -> str:
    if valor is None:
        return "—"
    return f"{valor:+.1f} %" if signo else f"{valor:.1f} %"


def reporte_entrenamiento(r: Resultado, entorno: str) -> str:
    info, m = r.info, r.info["metricas"]
    prueba = m["prueba"]
    base = r.mejor_linea_base
    wape_modelo = prueba["modelo"]["total"]["wape"]
    wape_base = prueba["lineas_base"][base]["total"]["wape"]
    mejora = prueba["mejora_vs_linea_base_pct"]
    val_modelo = min(x["wape_validacion"] for x in r.candidatos)
    ahora = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    semanas = len(r.serie.ventas)
    L = [
        f"# Evaluación del pronóstico de ventas — {entorno}",
        "",
        f"> Generado por `python -m machine_learning entrenar` ({ahora}). "
        f"Versión **{r.version or 'sin guardar'}**"
        + (f" · commit `{info['commit_codigo']}`" if info.get("commit_codigo") else "")
        + ".",
        "> Diseño y justificación: [modelo-ml.md](../modelos/modelo-ml.md).",
        "",
        "## Resultado en dos líneas",
        "",
        (
            f"- **Prueba** (semanas que el modelo nunca vio): error de **{_pct(wape_modelo)}** del "
            f"volumen vendido (WAPE), contra **{_pct(wape_base)}** de la mejor línea base "
            f"(*{LINEAS_BASE[base]}*): "
            + (
                f"**{_pct(mejora)} menos error**."
                if mejora > 0
                else f"**no la supera** ({_pct(mejora)}): conviene usar la línea base."
            )
        ),
        (
            f"- **Validación** (un año, 4 pliegues): modelo **{_pct(val_modelo)}** contra "
            f"**{_pct(r.lineas_base_validacion[base])}** de la misma línea base"
            + (
                " — en un año completo **empatan**: la mejora en prueba no está garantizada "
                "en todas las estaciones."
                if abs(val_modelo - r.lineas_base_validacion[base]) < 0.5
                else "."
            )
        ),
        "",
        "## 1. Datos usados (solo ventas reales, semanas completas de lunes a sábado)",
        "",
        f"- Serie: semanas del **{r.serie.desde.date()}** al **{r.serie.hasta.date()}** "
        f"({semanas} semanas), {len(r.serie.ventas.columns)} grupos.",
        f"- Huella de los datos (md5): `{info['huella_datos']}`.",
        "- Las ventas **simuladas** no se usan para entrenar ni para evaluar.",
        "",
        "| Grupo | Semanas | Venta media semanal (USD) | Variabilidad (CV) "
        "| Crecimiento último año | Participación | Semanas sin venta |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for d in m["datos"]:
        L.append(
            f"| {d['grupo']} | {d['semanas']} | {_usd(d['media_semanal'])} | "
            f"{_pct(d['coef_variacion_pct'])} | {_pct(d['crecimiento_anual_pct'], True)} | "
            f"{_pct(d['participacion_pct'])} | {d['semanas_sin_venta']} |"
        )
    if r.serie.excluidos:
        L += ["", "**Grupos excluidos** (no se fabrica un pronóstico sin respaldo):", ""]
        L += [f"- {g}: {motivo}." for g, motivo in r.serie.excluidos.items()]

    c = r.cortes
    L += [
        "",
        "## 2. Separación temporal (por semana pronosticada, nunca al azar)",
        "",
        "| Conjunto | Semanas pronosticadas | Para qué se usa |",
        "|---|---|---|",
    ]
    for k, (inicio, fin) in enumerate(c.pliegues, 1):
        ultima = (fin - pd.Timedelta(weeks=1)).date()
        L.append(
            f"| Validación, pliegue {k} | {inicio.date()} – {ultima} "
            f"| Medir candidatos entrenados solo con semanas anteriores al {inicio.date()} |"
        )
    L += [
        f"| Prueba | desde {c.prueba.date()} ({r.conteos['prueba']:,} muestras) "
        "| Medir **una sola vez** el resultado final |",
        "",
        "Validación cruzada temporal: los 4 pliegues cubren un año completo (todas las "
        "estaciones) y cada modelo se entrena solo con el pasado de su pliegue. Una muestra = "
        "un grupo, una semana de origen y un horizonte (1 a 4 semanas); sus variables solo usan "
        "semanas hasta el origen.",
        "",
        "## 3. Líneas base y selección del modelo (validación fuera de pliegue)",
        "",
        "| Línea base | Qué predice | WAPE validación |",
        "|---|---|---:|",
    ]
    for nombre, descripcion in LINEAS_BASE.items():
        marca = " ← mejor" if nombre == base else ""
        L.append(f"| {nombre} | {descripcion} | {_pct(r.lineas_base_validacion[nombre])}{marca} |")
    encabezado = " | ".join(f"Pliegue {k}" for k in range(1, len(c.pliegues) + 1))
    L += [
        "",
        f"| Candidato | {encabezado} | WAPE validación |",
        "|---|" + "---:|" * (len(c.pliegues) + 1),
    ]
    elegido = min(r.candidatos, key=lambda x: x["wape_validacion"])["nombre"]
    for cand in r.candidatos:
        marca = " ← elegido" if cand["nombre"] == elegido else ""
        pliegues = " | ".join(_pct(w) for w in cand["wape_por_pliegue"])
        L.append(f"| `{cand['nombre']}` | {pliegues} | {_pct(cand['wape_validacion'])}{marca} |")

    L += [
        "",
        "## 4. Resultado en prueba (semanas no usadas para entrenar ni elegir)",
        "",
        "| Pronóstico | WAPE | MAE (USD) | RMSE (USD) | sMAPE | Sesgo |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    filas = [("**Modelo**", prueba["modelo"]["total"])] + [
        (f"Línea base: {n}", prueba["lineas_base"][n]["total"]) for n in LINEAS_BASE
    ]
    for nombre, t in filas:
        L.append(
            f"| {nombre} | {_pct(t['wape'])} | {_usd(t['mae'])} | {_usd(t['rmse'])} | "
            f"{_pct(t['smape'])} | {_pct(t['sesgo'], True)} |"
        )
    L += [
        "",
        f"Por horizonte (contra la mejor línea base, *{base}*):",
        "",
        "| Semanas adelante | WAPE modelo | WAPE línea base "
        f"| Cobertura del rango {COBERTURA:.0%} |",
        "|---:|---:|---:|---:|",
    ]
    for h in HORIZONTES:
        k = str(h)
        L.append(
            f"| {h} | {_pct(prueba['modelo']['por_horizonte'][k]['wape'])} | "
            f"{_pct(prueba['lineas_base'][base]['por_horizonte'][k]['wape'])} | "
            f"{_pct(prueba['cobertura_rango_pct']['por_horizonte'][k])} |"
        )
    L += ["", "Por grupo:", "", "| Grupo | WAPE modelo | WAPE línea base |", "|---|---:|---:|"]
    for grupo, v in prueba["por_grupo"].items():
        L.append(f"| {grupo} | {_pct(v['modelo_wape'])} | {_pct(v['linea_base_wape'])} |")

    L += [
        "",
        "## 5. Rango probable",
        "",
        f"El rango cubre el {COBERTURA:.0%} central de los errores medidos en **validación**. "
        f"En prueba contuvo al valor real el **{_pct(prueba['cobertura_rango_pct']['total'])}** "
        "de las veces (lo esperado es cerca del 80 %).",
        "",
        "## 6. Modelo registrado",
        "",
        f"- Algoritmo: `{info['algoritmo']}` · semilla {info['parametros']['semilla']}.",
        f"- Modelo de producción: la misma configuración reentrenada con **toda** la historia "
        f"real ({info['filas_entrenamiento']:,} muestras, hasta la semana del "
        f"{r.serie.hasta.date()}). Las métricas de arriba son del modelo que no vio la prueba.",
        f"- Variables ({len(info['variables'])}): "
        + ", ".join(f"`{v}`" for v in info["variables"])
        + ".",
        "- Guardado en `ml.modelo` (versión, parámetros, métricas, huella y modelo serializado) "
        "y sus predicciones de prueba en `ml.prediccion_prueba`.",
        "",
    ]
    return "\n".join(L)


def reporte_pronostico(p: Pronostico) -> str:
    L = [
        f"### Pronóstico (PREDICCIÓN) · modelo {p.version}",
        "",
        f"Origen: semana del **{p.origen.date()}** (última semana completa)."
        + (" La historia usada **incluye ventas simuladas**." if p.usa_datos_simulados else ""),
        "",
        "| Grupo | Semana | Semanas adelante | Venta neta pronosticada (USD) "
        "| Rango probable 80 % |",
        "|---|---|---:|---:|---|",
    ]
    for f in p.tabla.sort_values(["grupo", "horizonte"]).itertuples(index=False):
        L.append(
            f"| {f.grupo} | {f.semana.date()} | {f.horizonte} "
            f"| {_usd(f.venta_neta_pronosticada)} | {_usd(f.inferior)} – {_usd(f.superior)} |"
        )
    if p.excluidos:
        L += ["", "Sin pronóstico:", ""] + [f"- {g}: {m}." for g, m in p.excluidos.items()]
    return "\n".join(L) + "\n"
