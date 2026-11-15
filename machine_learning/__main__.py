"""Línea de comandos del pronóstico.

    uv run --group ml python -m machine_learning entrenar [--neon] [--sin-guardar]
    uv run --group ml python -m machine_learning predecir [--neon] [--sin-guardar]

Conexión: --neon usa NEON_ML_ANALYTICS_URL (rol faro_ml) del .env; si no, ML_DATABASE_URL
(la usa el workflow de GitHub) o, en desarrollo, ANALYTICS_DATABASE_URL.
"""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

from etl.db import conectar

from .entrenar import entrenar
from .predecir import predecir
from .reporte import reporte_entrenamiento, reporte_pronostico

RAIZ = Path(__file__).resolve().parents[1]
PRUEBAS = RAIZ / "documentation" / "pruebas"


def _commit() -> str | None:
    if os.getenv("GITHUB_SHA"):
        return os.environ["GITHUB_SHA"][:7]
    try:
        salida = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=RAIZ
        )
        return salida.stdout.strip() or None
    except OSError:
        return None


def _resumen_github(texto: str) -> None:
    """En GitHub Actions, publica el reporte en el resumen de la ejecución."""
    destino = os.getenv("GITHUB_STEP_SUMMARY")
    if destino:
        with open(destino, "a", encoding="utf-8") as f:
            f.write(texto + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m machine_learning", description=__doc__)
    acciones = parser.add_subparsers(dest="accion", required=True)
    for nombre, ayuda in (
        ("entrenar", "entrena, evalúa contra las líneas base y registra el modelo"),
        ("predecir", "pronostica las 4 semanas siguientes con el modelo vigente"),
    ):
        p = acciones.add_parser(nombre, help=ayuda)
        p.add_argument("--neon", action="store_true", help="usar NEON_ML_ANALYTICS_URL del .env")
        p.add_argument(
            "--sin-guardar", action="store_true", help="calcular sin escribir en la base"
        )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    load_dotenv(RAIZ / ".env")
    if args.neon:
        url = os.getenv("NEON_ML_ANALYTICS_URL")
    else:
        url = os.getenv("ML_DATABASE_URL") or os.getenv("ANALYTICS_DATABASE_URL")
    if not url:
        print("Falta la conexión (NEON_ML_ANALYTICS_URL, ML_DATABASE_URL o ANALYTICS_DATABASE_URL)")
        return 1
    entorno = "neon" if "neon.tech" in (urlparse(url).hostname or "") else "local"
    guardar = not args.sin_guardar

    with conectar(url) as conn:
        if args.accion == "entrenar":
            r = entrenar(conn, guardar=guardar, commit_codigo=_commit())
            texto = reporte_entrenamiento(r, "Neon (producción)" if entorno == "neon" else "local")
            destino = PRUEBAS / f"evaluacion-ml-{entorno}.md"
            destino.write_text(texto, encoding="utf-8", newline="\n")
            _resumen_github(texto)
            prueba = r.info["metricas"]["prueba"]
            print(f"Modelo {r.version or '(sin guardar)'}: {r.info['algoritmo']}")
            print(
                f"WAPE en prueba: modelo {prueba['modelo']['total']['wape']:.1f} % · "
                f"línea base '{r.mejor_linea_base}' "
                f"{prueba['lineas_base'][r.mejor_linea_base]['total']['wape']:.1f} % · "
                f"mejora {prueba['mejora_vs_linea_base_pct']:+.1f} %"
            )
            print(f"Reporte: {destino.relative_to(RAIZ)}")
        else:
            p = predecir(conn, guardar=guardar)
            texto = reporte_pronostico(p)
            _resumen_github(texto)
            print(texto)
            print("Guardado en ml.pronostico" if guardar else "(sin guardar)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
