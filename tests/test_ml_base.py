"""Pruebas de integración del pronóstico sobre bases temporales.

- La serie de entrada (ml.ventas_semanales) reconcilia con el DW.
- Entrenar, registrar y predecir funcionan con el rol faro_ml (mínimo privilegio), y la API
  ve el resultado por sus vistas aprobadas.
- Repetir el pronóstico no duplica filas; reentrenar deja un solo modelo vigente.
- faro_ml no ve el DW ni puede borrar pronósticos; faro_api no ve el modelo serializado.

El entrenamiento usa una serie sintética (175 semanas): los datos mínimos de prueba no tienen
los 2 años de historia que exige el modelo.
"""

import psycopg
import pytest
from conftest import RAIZ, sql, uno
from psycopg.conninfo import make_conninfo

pytest.importorskip("sklearn", reason="requiere el grupo ml: uv sync --group ml")

from datos_ml import filas_sinteticas  # noqa: E402

import machine_learning.entrenar as modulo_entrenar  # noqa: E402
import machine_learning.predecir as modulo_predecir  # noqa: E402
from etl.db import conectar  # noqa: E402
from etl.orchestration import pipeline  # noqa: E402

pytestmark = pytest.mark.integracion

PRONOSTICOS_POR_CORRIDA = 4 * 3  # 4 semanas x 3 grupos con historia


def _como(url: str, rol: str) -> str:
    return make_conninfo(url, options=f"-c role={rol}")


def _denegado(url: str, consulta: str) -> bool:
    try:
        sql(url, consulta)
    except psycopg.errors.InsufficientPrivilege:
        return True
    return False


@pytest.fixture(scope="module")
def analitica(bases):
    fuente, analitica = bases
    sql(analitica, (RAIZ / "database" / "security" / "roles_analitica.sql").read_text("utf-8"))
    r = pipeline.ejecutar(fuente, analitica, modo="inicial", disparador="ci")
    assert r.estado == "exitoso", r.error
    return analitica


@pytest.fixture
def serie_sintetica(monkeypatch):
    filas = filas_sinteticas(semanas=175, semanas_simuladas=2)
    monkeypatch.setattr(modulo_entrenar, "leer", lambda conn: filas.copy())
    monkeypatch.setattr(modulo_predecir, "leer", lambda conn: filas.copy())
    return filas


def test_la_serie_semanal_reconcilia_con_el_dw(analitica):
    serie = uno(analitica, "SELECT sum(venta_neta) FROM ml.ventas_semanales")
    dw = uno(analitica, "SELECT sum(venta_neta) FROM dw.fact_ventas WHERE producto_key <> -1")
    assert serie == dw and serie > 0
    # La parte real y la simulada suman el total
    assert uno(
        analitica,
        "SELECT bool_and(venta_neta = venta_neta_real + venta_neta_simulada) "
        "FROM ml.ventas_semanales",
    )


def test_entrenar_y_predecir_con_el_rol_faro_ml(analitica, serie_sintetica):
    url = _como(analitica, "faro_ml")
    with conectar(url) as conn:
        r = modulo_entrenar.entrenar(conn, commit_codigo="prueba")
    assert uno(analitica, "SELECT version FROM ml.modelo WHERE es_vigente") == r.version
    assert uno(
        analitica,
        "SELECT count(*) FROM ml.prediccion_prueba WHERE modelo_id = %s",
        (r.modelo_id,),
    ) == len(r.predicciones_prueba)

    with conectar(url) as conn:
        p = modulo_predecir.predecir(conn)
    assert len(p.tabla) == PRONOSTICOS_POR_CORRIDA
    assert p.usa_datos_simulados  # las 2 últimas semanas sintéticas son simuladas
    assert "Nuevo" in p.excluidos  # sin historia: no se inventa un pronóstico

    # La API lo ve por sus vistas aprobadas, con la versión del modelo
    api = _como(analitica, "faro_api")
    assert uno(api, "SELECT count(*) FROM api.pronostico") == PRONOSTICOS_POR_CORRIDA
    assert uno(api, "SELECT version FROM api.modelo_pronostico") == r.version
    assert uno(api, "SELECT bool_and(inferior <= venta_neta_pronosticada) FROM api.pronostico")


def test_repetir_no_duplica_y_reentrenar_deja_un_solo_vigente(analitica, serie_sintetica):
    url, api = _como(analitica, "faro_ml"), _como(analitica, "faro_api")
    with conectar(url) as conn:
        modulo_predecir.predecir(conn)  # mismo origen: reemplaza, no duplica
    assert uno(analitica, "SELECT count(*) FROM ml.pronostico") == PRONOSTICOS_POR_CORRIDA

    with conectar(url) as conn:
        r2 = modulo_entrenar.entrenar(conn)
    assert sql(analitica, "SELECT version FROM ml.modelo WHERE es_vigente") == [(r2.version,)]
    assert uno(analitica, "SELECT count(*) FROM ml.modelo") == 2
    # La vista solo muestra pronósticos del modelo vigente: vacía hasta predecir con él
    assert uno(api, "SELECT count(*) FROM api.pronostico") == 0
    with conectar(url) as conn:
        modulo_predecir.predecir(conn)
    assert uno(api, "SELECT count(*) FROM api.pronostico") == PRONOSTICOS_POR_CORRIDA
    # El historial de pronósticos se conserva (trazabilidad)
    assert uno(analitica, "SELECT count(*) FROM ml.pronostico") == 2 * PRONOSTICOS_POR_CORRIDA


def test_faro_ml_no_ve_el_dw_ni_borra_pronosticos(analitica):
    ml = _como(analitica, "faro_ml")
    assert _denegado(ml, "SELECT count(*) FROM dw.fact_ventas")
    assert _denegado(ml, "DELETE FROM ml.pronostico")
    assert _denegado(ml, "UPDATE ml.modelo SET metricas = '{}'::jsonb")  # solo es_vigente
    assert _denegado(ml, "DROP TABLE ml.pronostico")


def test_faro_api_no_ve_el_modelo_serializado(analitica):
    api = _como(analitica, "faro_api")
    assert _denegado(api, "SELECT artefacto FROM ml.modelo")
    assert _denegado(api, "SELECT count(*) FROM ml.ventas_semanales")
