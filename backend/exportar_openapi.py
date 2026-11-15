"""Exporta el contrato de la API (OpenAPI) a documentation/api/openapi.json.

El contrato se genera desde el código (modelos de Pydantic), así que coincide con la API real.
Uso:
    uv run python -m backend.exportar_openapi
"""

from __future__ import annotations

import json
import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SALIDA = RAIZ / "documentation" / "api" / "openapi.json"


def main() -> None:
    # Generar el contrato no necesita base ni secretos reales
    os.environ.setdefault("API_DATABASE_URL", "postgresql://no-usada")
    os.environ.setdefault("JWT_SECRET", "x" * 32)
    from backend.app.main import app

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(
        json.dumps(app.openapi(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"Generado: {SALIDA.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
