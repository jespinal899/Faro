"""Mide el tiempo de respuesta de los endpoints principales de la API.

Llama cada endpoint varias veces (con sesión iniciada) y registra la mediana y el máximo.
La guía pide documentar el tiempo de respuesta de las consultas principales.

Uso:
    uv run python database/scripts/medir_api.py                     # API local en proceso
    uv run python database/scripts/medir_api.py --url https://...   # API publicada
Usuario y contraseña: FARO_MEDIR_USUARIO (por defecto demo) y FARO_PASSWORD_DEMO del .env.
"""

from __future__ import annotations

import argparse
import os
import statistics
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

CONSULTAS = (
    ("KPI de todo el histórico", "/api/kpis", {}),
    ("KPI de un trimestre con comparación anual", "/api/kpis",
     {"desde": "2016-01-01", "hasta": "2016-03-31"}),
    ("KPI con 3 filtros combinados", "/api/kpis",
     {"desde": "2015-01-01", "hasta": "2015-12-31", "territorio": "Southeast",
      "grupo": "T-Shirts"}),
    ("Tendencia mensual (todo el histórico)", "/api/tendencia", {"granularidad": "mes"}),
    ("Tendencia diaria de un año", "/api/tendencia",
     {"granularidad": "dia", "desde": "2015-01-01", "hasta": "2015-12-31"}),
    ("Desglose por grupo", "/api/desglose", {"dimension": "grupo"}),
    ("Desglose por pertenencia a grupo", "/api/desglose",
     {"dimension": "grupo", "pertenencia": "true"}),
    ("Top 10 productos", "/api/desglose", {"dimension": "producto", "top": 10}),
    ("Facturas, página 1", "/api/facturas", {"tamano": 25}),
    ("Facturas, página 100", "/api/facturas", {"tamano": 25, "pagina": 100}),
    ("Detalle de una factura", "/api/facturas/67114", {}),
    ("Opciones de filtros", "/api/opciones", {}),
    ("Estado de los datos", "/api/estado", {}),
)  # fmt: skip
REPETICIONES = 5


def main() -> int:
    parser = argparse.ArgumentParser(description="Mide tiempos de respuesta de la API")
    parser.add_argument("--url", help="URL base de una API publicada (si no, se usa en proceso)")
    args = parser.parse_args()
    load_dotenv(RAIZ / ".env")
    usuario = os.getenv("FARO_MEDIR_USUARIO", "demo")
    variable = f"{'NEON_' if args.url else ''}FARO_PASSWORD_{usuario.upper()}"
    password = os.getenv(variable)
    if not password:
        print(f"Falta {variable} en .env")
        return 1

    if args.url:
        import httpx2 as httpx

        cliente = httpx.Client(base_url=args.url, timeout=60)
        entorno = args.url
    else:
        from fastapi.testclient import TestClient

        from backend.app.main import app

        cliente = TestClient(app)
        entorno = "local (API en proceso, base en Docker)"

    with cliente:
        r = cliente.post("/api/auth/login", json={"usuario": usuario, "password": password})
        r.raise_for_status()
        filas = []
        for nombre, ruta, params in CONSULTAS:
            tiempos = []
            for _ in range(REPETICIONES):
                inicio = time.perf_counter()
                respuesta = cliente.get(ruta, params=params)
                tiempos.append((time.perf_counter() - inicio) * 1000)
                respuesta.raise_for_status()
            filas.append((nombre, ruta, statistics.median(tiempos), max(tiempos)))
            print(f"{nombre:45} mediana {statistics.median(tiempos):7.0f} ms")

    sufijo = "vercel" if args.url else "local"
    salida = RAIZ / "documentation" / "pruebas" / f"tiempos-api-{sufijo}.md"
    lineas = [
        f"# Tiempos de respuesta de la API — {sufijo}",
        "",
        f"> Generado por `database/scripts/medir_api.py` ({datetime.now(UTC):%Y-%m-%d %H:%M} UTC).",
        f"> Entorno: {entorno}. {REPETICIONES} llamadas por consulta, con los datos completos.",
        "",
        "| Consulta | Endpoint | Mediana (ms) | Máximo (ms) |",
        "|---|---|---:|---:|",
        *(f"| {n} | `{r}` | {m:,.0f} | {x:,.0f} |" for n, r, m, x in filas),
        "",
    ]
    salida.write_text("\n".join(lineas), encoding="utf-8", newline="\n")
    print(f"Reporte: {salida.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
