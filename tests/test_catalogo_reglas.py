"""El catálogo de reglas de calidad (documentación) coincide con lo que ejecuta el ETL."""

import importlib.util

from conftest import RAIZ

from etl.config import TABLAS, reglas_de


def _generador():
    ruta = RAIZ / "database" / "scripts" / "documentar_reglas.py"
    spec = importlib.util.spec_from_file_location("documentar_reglas", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_el_catalogo_esta_al_dia():
    generador = _generador()
    actual = generador.SALIDA.read_text(encoding="utf-8")
    assert actual == generador.generar(), (
        "Catálogo desactualizado: uv run python database/scripts/documentar_reglas.py"
    )


def test_cada_control_del_etl_aparece_en_el_catalogo():
    texto = _generador().generar()
    for tabla in TABLAS:
        for regla in reglas_de(tabla):
            assert f"| `{tabla.origen}` | {regla.codigo} |" in texto
