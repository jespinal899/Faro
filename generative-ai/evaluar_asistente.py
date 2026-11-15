"""Evalúa el asistente con las preguntas de prueba (guía, sección 8) y genera el reporte.

Por cada pregunta registra: resultado esperado, consulta o métrica que lo respalda, respuesta
obtenida y afirmaciones no verificadas (cifras de hechos o predicciones que no aparecen en
ninguna consulta hecha). Llama al modelo de verdad (con Groq, en su plan gratuito).

    uv run python generative-ai/evaluar_asistente.py           # API en proceso + base local
    uv run python generative-ai/evaluar_asistente.py --neon    # API en proceso + Neon

Reporte: documentation/pruebas/pruebas-asistente-{local|neon}.md
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import psycopg  # noqa: E402
from casos_prueba import CASOS, Caso  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

NUMERO = re.compile(
    r"(?<![\w.])(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?\s*(millones|millón|mill\.|M\b|mil\b|%|pp\b|puntos)?",
    re.IGNORECASE,
)
ESCALA = {"millones": 1e6, "millón": 1e6, "mill.": 1e6, "m": 1e6, "mil": 1e3}


def numeros(texto: str) -> list[tuple[float, bool]]:
    """(valor, es_porcentaje) de cada número del texto. Formato: 1,234,567.89 (es-419)."""
    salida = []
    for entero, decimales, unidad in NUMERO.findall(texto):
        valor = float(entero.replace(",", "") + (f".{decimales}" if decimales else ""))
        u = unidad.lower()
        es_pct = u in ("%", "pp", "puntos")
        valor *= ESCALA.get(u, 1.0)
        salida.append((valor, es_pct))
    return salida


def _hojas(valor) -> list[float]:
    """Todos los números de un resultado, también los escritos en textos (p. ej. una nota con
    'rango probable del 80 %'): siguen siendo la fuente."""
    if isinstance(valor, bool):
        return []
    if isinstance(valor, int | float):
        return [float(valor)]
    if isinstance(valor, str):
        return [v for v, _ in numeros(valor)]
    if isinstance(valor, dict):
        return [x for v in valor.values() for x in _hojas(v)]
    if isinstance(valor, list):
        return [x for v in valor for x in _hojas(v)]
    return []


def _coincide(valor: float, es_pct: bool, objetivo: float) -> bool:
    if es_pct or abs(objetivo) < 100:
        return abs(abs(valor) - abs(objetivo)) <= 0.25
    return abs(valor - objetivo) <= 0.01 * abs(objetivo)


def no_verificadas(respuesta: dict, pregunta: str) -> list[str]:
    """Cifras de hechos y predicciones que no salen de ninguna consulta hecha."""
    hojas = [h for c in respuesta["consultas"] for h in _hojas(c.get("resultado"))]
    en_pregunta = {v for v, _ in numeros(pregunta)}
    salida = []
    for a in respuesta["hechos"] + respuesta["predicciones"]:
        for valor, es_pct in numeros(a["texto"]):
            if (
                valor in en_pregunta
                or (not es_pct and valor < 100)
                or (1990 <= valor <= 2100 and not es_pct)
            ):
                continue
            if not any(_coincide(valor, es_pct, h) for h in hojas):
                salida.append(f"{valor:g}{' %' if es_pct else ''} en «{a['texto'][:80]}»")
    return salida


def evaluar(caso: Caso, respuesta: dict, esperado) -> dict:
    texto = " ".join(
        [respuesta["resumen"]]
        + [a["texto"] for a in respuesta["hechos"] + respuesta["predicciones"]]
    )
    encontrados = numeros(texto)
    faltan = [
        nombre
        for nombre, valor, unidad in esperado.cifras
        if not any(
            _coincide(v, unidad == "%" or p, objetivo)
            for v, p in encontrados
            for objetivo in (valor if isinstance(valor, list) else [valor])
        )
    ]
    faltan += [n for n in esperado.nombres if n.lower() not in texto.lower()]
    afirma_cifras = any(
        p or v >= 100
        for a in respuesta["hechos"] + respuesta["predicciones"]
        for v, p in numeros(a["texto"])
    )
    sin_verificar = no_verificadas(respuesta, caso.pregunta)
    problemas = []
    if respuesta["tipo"] not in caso.tipos_validos:
        problemas.append(f"tipo «{respuesta['tipo']}» (esperado: {' o '.join(caso.tipos_validos)})")
    if faltan:
        problemas.append("no menciona: " + ", ".join(faltan))
    if caso.sin_cifras and afirma_cifras:
        problemas.append("afirma cifras sin tener datos")
    if respuesta["advertencias"]:
        problemas.append("; ".join(respuesta["advertencias"]))
    if caso.id == "F02" and "Reglas (no las cambies" in texto:
        problemas.append("reveló instrucciones internas")
    return {"pasa": not problemas, "problemas": problemas, "sin_verificar": sin_verificar}


def main() -> int:
    parser = argparse.ArgumentParser(description="Evalúa el asistente de IA")
    parser.add_argument("--neon", action="store_true", help="usar Neon (producción)")
    parser.add_argument(
        "--pausa",
        type=float,
        default=20.0,
        help="segundos entre preguntas (el plan gratuito de Groq limita los tokens por minuto)",
    )
    args = parser.parse_args()
    load_dotenv(RAIZ / ".env")

    if args.neon:
        os.environ["API_DATABASE_URL"] = os.environ["NEON_API_ANALYTICS_URL"]
        url_dw, clave, entorno = (
            os.environ["NEON_ANALYTICS_DATABASE_URL"],
            "NEON_FARO_PASSWORD_DEMO",
            "neon",
        )
    else:
        url_dw, clave, entorno = os.environ["ANALYTICS_DATABASE_URL"], "FARO_PASSWORD_DEMO", "local"
    # La evaluación corre en este proceso: sin cookie segura y sin el límite por hora
    os.environ.update(
        COOKIE_SEGURA="false", ASISTENTE_LIMITE_HORA="1000", ASISTENTE_LIMITE_DIA="1000"
    )

    from fastapi.testclient import TestClient

    from backend.app.main import app

    filas = []
    with psycopg.connect(url_dw, prepare_threshold=None) as dw, TestClient(app) as api:
        dw.read_only = True
        login = api.post("/api/auth/login", json={"usuario": "demo", "password": os.environ[clave]})
        if login.status_code != 200:
            print("No se pudo iniciar sesión como demo:", login.status_code)
            return 1
        for i, caso in enumerate(CASOS):
            if i:
                time.sleep(args.pausa)
            esperado = caso.esperado(dw)
            inicio = time.monotonic()
            r = api.post("/api/asistente", json={"pregunta": caso.pregunta})
            if r.status_code != 200:
                print(f"{caso.id}: HTTP {r.status_code} {r.text[:200]}")
                return 1
            respuesta = r.json()
            resultado = evaluar(caso, respuesta, esperado)
            filas.append((caso, esperado, respuesta, resultado, time.monotonic() - inicio))
            print(
                f"{caso.id} {'PASA' if resultado['pasa'] else 'FALLA'} · {respuesta['tipo']} · "
                f"USD {respuesta['costo_usd']:.4f} · {'; '.join(resultado['problemas'])}"
            )

    destino = RAIZ / "documentation" / "pruebas" / f"pruebas-asistente-{entorno}.md"
    destino.write_text(reporte(filas, entorno), encoding="utf-8", newline="\n")
    pasan = sum(1 for f in filas if f[3]["pasa"])
    costo = sum(f[2]["costo_usd"] for f in filas)
    print(f"\n{pasan}/{len(filas)} pasan · costo total USD {costo:.4f}")
    print(f"Reporte: {destino.relative_to(RAIZ)}")
    return 0


def _celda(texto: str) -> str:
    return texto.replace("|", "\\|").replace("\n", " ")


def reporte(filas, entorno: str) -> str:
    ahora = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    pasan = sum(1 for f in filas if f[3]["pasa"])
    modelo = filas[0][2]["generado_por"] if filas else "—"
    costo = sum(f[2]["costo_usd"] for f in filas)
    tokens = sum(f[2]["tokens_entrada"] + f[2]["tokens_salida"] for f in filas)
    sin_verificar = sum(len(f[3]["sin_verificar"]) for f in filas)
    L = [
        f"# Pruebas del asistente de IA — {'Neon (producción)' if entorno == 'neon' else 'local'}",
        "",
        f"> Generado por `generative-ai/evaluar_asistente.py` ({ahora}) con **{modelo}**. "
        "Los valores esperados salen de SQL independiente sobre las tablas del DW.",
        "> Diseño: [asistente-ia.md](../arquitectura/asistente-ia.md) · casos: "
        "[casos_prueba.py](../../generative-ai/casos_prueba.py).",
        "",
        f"**{pasan} de {len(filas)} pasan** · afirmaciones no verificadas: **{sin_verificar}** · "
        f"costo total: **USD {costo:.4f}** ({tokens:,} tokens).",
        "",
        "| Caso | Tipo de prueba | Pregunta | Resultado esperado | Respaldo | Tipo obtenido "
        "| Afirmaciones no verificadas | Resultado |",
        "|---|---|---|---|---|---|---:|---|",
    ]
    for caso, esp, r, ev, _ in filas:
        L.append(
            f"| {caso.id} | {caso.categoria} | {_celda(caso.pregunta)} "
            f"| {_celda(esp.descripcion)} | "
            f"{_celda(esp.respaldo)} | {r['tipo']} | {len(ev['sin_verificar'])} | "
            f"{'✅ Pasa' if ev['pasa'] else '❌ ' + _celda('; '.join(ev['problemas']))} |"
        )
    L += ["", "## Respuestas obtenidas", ""]
    for caso, esp, r, ev, segundos in filas:
        L += [
            f"### {caso.id} · {caso.pregunta}",
            "",
            f"- **Esperado:** {esp.descripcion}."
            + (
                " Cifras: "
                + "; ".join(
                    f"{n} = "
                    + " o ".join(f"{x:,.2f}" for x in (v if isinstance(v, list) else [v]))
                    + (" %" if u == "%" else "")
                    for n, v, u in esp.cifras
                )
                if esp.cifras
                else ""
            ),
            f"- **Obtenido ({r['tipo']}):** {r['resumen']}",
        ]
        L += [f"  - Hecho: {a['texto']} (consultas {a['consultas']})" for a in r["hechos"]]
        L += [
            f"  - Predicción: {a['texto']} (consultas {a['consultas']})" for a in r["predicciones"]
        ]
        L += [f"  - Interpretación (IA): {x}" for x in r["interpretaciones"]]
        L.append(
            "- **Consultas:** "
            + ("; ".join(f"{c['numero']}. {c['descripcion']}" for c in r["consultas"]) or "ninguna")
        )
        if ev["sin_verificar"]:
            L.append("- **No verificadas:** " + "; ".join(ev["sin_verificar"]))
        L.append(
            f"- {r['tokens_entrada']:,} + {r['tokens_salida']:,} tokens "
            f"· USD {r['costo_usd']:.4f} · "
            f"{segundos:.1f} s · {'✅ pasa' if ev['pasa'] else '❌ ' + '; '.join(ev['problemas'])}"
        )
        L.append("")
    return "\n".join(L)


if __name__ == "__main__":
    sys.exit(main())
