# ruff: noqa: E501  (genera Markdown: las filas de tabla no se pueden partir)
"""Genera el catálogo de reglas de calidad desde el código del ETL (etl/config.py).

El código es la fuente de verdad: lo que ejecuta el ETL es lo que dice el catálogo. Una prueba
(tests/test_catalogo_reglas.py) falla si el documento quedó desactualizado.

Uso:
    uv run python database/scripts/documentar_reglas.py
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))

from etl.config import (  # noqa: E402
    TABLAS,
    TOLERANCIA_RELOJ,
    UMBRAL_CANTIDAD_ATIPICA,
    UMBRAL_IMPORTE_ATIPICO,
    reglas_de,
)

SALIDA = RAIZ / "documentation" / "modelos" / "catalogo-reglas-calidad.md"

ACCIONES = {
    "cuarentena": "⛔ Cuarentena: no pasa a `stg_clean`",
    "marcar": "⚠️ Marcar: pasa con su marca",
}


def _celda(texto: str) -> str:
    return texto.replace("|", "\\|").replace("\n", " ")


def generar() -> str:
    filas = [(t, r) for t in TABLAS for r in reglas_de(t)]
    codigos: dict[str, tuple] = {}
    for t, r in filas:
        codigos.setdefault(r.codigo, (r, []))[1].append(t.origen)
    por_dimension = Counter(r.dimension for _, r in filas)
    por_accion = Counter(r.accion for _, r in filas)

    lineas = [
        "# Catálogo de reglas de calidad y transformación — Faro",
        "",
        "> **Generado** por `database/scripts/documentar_reglas.py` desde",
        "> [etl/config.py](../../etl/config.py): no se edita a mano. Una prueba verifica que esté al día.",
        "",
        "Cada lote del ETL evalúa estas reglas en la zona `stg_raw → stg_clean` y guarda el resultado",
        "de cada una en `audit.dq_result` (filas evaluadas y filas que fallaron por ejecución). Los",
        "rechazados quedan en `stg_quarantine.registro_rechazado` con la regla, el detalle, el registro",
        "original y la ejecución, y **se reintentan en cada ejecución**: si la fuente los corrige, entran.",
        "El diseño y la justificación de cada regla están en",
        "[diseno-staging-etl.md](../arquitectura/diseno-staging-etl.md) (secciones 3 y 4).",
        "",
        "## Resumen",
        "",
        f"- **{len(codigos)} reglas** distintas, aplicadas como **{len(filas)} controles** en"
        f" {len(TABLAS)} tablas.",
        "- Por acción: " + ", ".join(f"{n} de {a}" for a, n in sorted(por_accion.items())) + ".",
        "",
        "| Dimensión de calidad (guía, sección 10) | Controles |",
        "|---|---:|",
        *(f"| {d} | {n} |" for d, n in sorted(por_dimension.items())),
        "| Unicidad | Regla de supervivencia U03 (abajo) |",
        "| Completitud | V02 (precio nulo) y política de nulos por columna (diseño, sección 3.1) |",
        "",
        "## Reglas",
        "",
        "| Código | Dimensión | Regla | Acción | Tablas |",
        "|---|---|---|---|---|",
    ]
    for codigo in sorted(codigos):
        r, tablas = codigos[codigo]
        donde = "todas" if len(tablas) == len(TABLAS) else ", ".join(f"`{t}`" for t in tablas)
        lineas.append(
            f"| {codigo} | {r.dimension} | {_celda(r.descripcion)} | {ACCIONES[r.accion]} | {donde} |"
        )
    lineas += [
        "| U03 | Unicidad | Varias versiones de la misma clave natural en un lote | 🔁 Supervivencia:"
        " gana la última versión extraída; las demás quedan en `stg_raw` como historia | todas |",
        "",
        "Parámetros:",
        f"- tolerancia de reloj de O02: `{TOLERANCIA_RELOJ}`;",
        f"- atípicos A01 y A02: cantidad > {UMBRAL_CANTIDAD_ATIPICA} e importe >"
        f" {UMBRAL_IMPORTE_ATIPICO}, calculados como Q3 + 3·IQR en el perfilado.",
        "",
        "## Condición exacta de cada control (SQL sobre la fila `r` del lote)",
        "",
        "| Tabla | Código | Condición (verdadera = incumple) |",
        "|---|---|---|",
    ]
    for t, r in filas:
        lineas.append(f"| `{t.origen}` | {r.codigo} | `{_celda(r.condicion)}` |")
    lineas += [
        "",
        "## Transformaciones (en cada lote)",
        "",
        "| Transformación | Dónde | Regla |",
        "|---|---|---|",
        "| Limpieza de textos | `stg_clean` ([limpiar.py](../../etl/transformation/limpiar.py))"
        " | Sin caracteres de control, espacios múltiples colapsados y sin espacios en los extremos |",
        "| Descarte de releídos | `stg_raw → stg_clean` | Las filas idénticas a la versión vigente"
        " (traídas por la ventana de solapamiento) no se vuelven a escribir |",
        "| Nulos | `stg_ready` | Según su causa: no aplica, desconocido, pendiente o error"
        " (diseño, sección 3.1); una medida nunca se reemplaza por cero |",
        "| Integración y enriquecimiento | `stg_ready` (vistas) | Grano de la línea de factura,"
        " grupo principal del producto, geografía, venta neta, costo y utilidad |",
        "| Miembro desconocido | `dw` | Un hecho sin dimensión recibe la clave −1 |",
        "| Historia | `dw` | SCD Tipo 2 en cliente y producto (solo si cambia el hash de la fila) |",
        "",
    ]
    return "\n".join(lineas)


def main() -> None:
    SALIDA.write_text(generar(), encoding="utf-8", newline="\n")
    print(f"Generado: {SALIDA.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
