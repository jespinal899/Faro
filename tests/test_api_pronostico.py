"""Pruebas de la API del pronóstico: lo que muestra coincide con lo registrado por el modelo.

La API se conecta con el rol faro_api a bases temporales. El modelo se entrena con la serie
sintética (como en test_ml_base) y se registra en el esquema ml de la base temporal.
"""

import os

import pytest
from conftest import RAIZ, Url, sql, uno
from psycopg.conninfo import make_conninfo

pytest.importorskip("sklearn", reason="requiere el grupo ml: uv sync --group ml")

from datos_ml import filas_sinteticas  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import machine_learning.entrenar as modulo_entrenar  # noqa: E402
import machine_learning.predecir as modulo_predecir  # noqa: E402
from backend.app import config as modulo_config  # noqa: E402
from backend.app.main import app  # noqa: E402
from backend.app.rutas.pronostico import LINEAS_BASE as LINEAS_BASE_API  # noqa: E402
from backend.app.seguridad import hash_password  # noqa: E402
from etl.db import conectar  # noqa: E402
from etl.orchestration import pipeline  # noqa: E402
from machine_learning.variables import LINEAS_BASE as LINEAS_BASE_ML  # noqa: E402
from simulador import ventas  # noqa: E402

pytestmark = pytest.mark.integracion

PASSWORD = "Contraseña-de-prueba-123"


@pytest.fixture(scope="module")
def entorno(bases):
    fuente, analitica = bases
    assert pipeline.ejecutar(fuente, analitica, modo="inicial", disparador="ci").estado == "exitoso"
    # 14 días hábiles simulados: así el DW tiene al menos una semana completa (lunes a sábado)
    ventas.simular(fuente, dias=14, pedidos=2, semilla=5)
    assert pipeline.ejecutar(fuente, analitica, disparador="ci").estado == "exitoso"
    sql(analitica, (RAIZ / "database" / "security" / "roles_analitica.sql").read_text("utf-8"))
    sql(
        analitica,
        "INSERT INTO app.usuario (usuario, nombre, password_hash) VALUES (%s, %s, %s)",
        ("analista", "Usuario analista", hash_password(PASSWORD)),
    )
    anteriores = {k: os.environ.get(k) for k in ("API_DATABASE_URL", "JWT_SECRET", "COOKIE_SEGURA")}
    os.environ.update(
        API_DATABASE_URL=make_conninfo(analitica, options="-c role=faro_api"),
        JWT_SECRET="p" * 48,
        COOKIE_SEGURA="false",
    )
    modulo_config.config.cache_clear()
    yield Url(analitica)
    for k, v in anteriores.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    modulo_config.config.cache_clear()


@pytest.fixture(scope="module")
def cliente(entorno):
    with TestClient(app) as c:
        assert c.post(
            "/api/auth/login", json={"usuario": "analista", "password": PASSWORD}
        ).is_success
        yield c


def _entrenar_y_predecir(analitica: str, monkeypatch) -> str:
    filas = filas_sinteticas(semanas=175, semanas_simuladas=2)
    monkeypatch.setattr(modulo_entrenar, "leer", lambda conn: filas.copy())
    monkeypatch.setattr(modulo_predecir, "leer", lambda conn: filas.copy())
    url = make_conninfo(analitica, options="-c role=faro_ml")
    with conectar(url) as conn:
        version = modulo_entrenar.entrenar(conn).version
    with conectar(url) as conn:
        modulo_predecir.predecir(conn)
    return version


def test_sin_modelo_lo_dice_en_lugar_de_inventar(cliente):
    r = cliente.get("/api/pronostico")
    assert r.status_code == 200
    assert r.json()["disponible"] is False and r.json()["grupos"] == []


def test_el_pronostico_coincide_con_lo_registrado(cliente, entorno, monkeypatch):
    version = _entrenar_y_predecir(entorno, monkeypatch)
    d = cliente.get("/api/pronostico").json()

    assert d["disponible"] and d["modelo"]["version"] == version
    assert d["usa_datos_simulados"] is True
    assert [g["grupo"] for g in d["grupos"]] == ["Chico", "Grande", "Mediano"]
    assert d["excluidos"][0]["grupo"] == "Nuevo"
    for g in d["grupos"]:
        assert [p["horizonte"] for p in g["pronostico"]] == [1, 2, 3, 4]
        assert all(p["inferior"] <= p["venta_neta"] <= p["superior"] for p in g["pronostico"])
        assert g["wape_prueba"] is not None
    # Cada cifra de la API es la registrada en ml.pronostico (sin recalcular nada)
    total_api = sum(p["venta_neta"] for g in d["grupos"] for p in g["pronostico"])
    total_ml = uno(
        entorno,
        "SELECT sum(p.venta_neta_pronosticada) FROM ml.pronostico p "
        "JOIN ml.modelo m USING (modelo_id) WHERE m.version = %s",
        (version,),
    )
    assert total_api == pytest.approx(float(total_ml))
    # Calidad: la del registro del modelo
    calidad = d["modelo"]["calidad"]
    wape = uno(
        entorno,
        "SELECT (metricas->'prueba'->'modelo'->'total'->>'wape')::float FROM ml.modelo "
        "WHERE version = %s",
        (version,),
    )
    assert calidad["wape_prueba_modelo"] == pytest.approx(wape)
    assert [h["horizonte"] for h in calidad["por_horizonte"]] == [1, 2, 3, 4]
    assert calidad["linea_base_descripcion"] == LINEAS_BASE_ML[calidad["linea_base"]]


def test_evaluacion_en_semanas_de_prueba(cliente):
    puntos = cliente.get("/api/pronostico/evaluacion", params={"grupo": "Grande"}).json()
    assert len(puntos) == 16  # las 16 semanas de prueba, horizonte 1
    assert all(p["origen"] < p["semana"] for p in puntos)
    assert (
        cliente.get(
            "/api/pronostico/evaluacion", params={"grupo": "Grande", "horizonte": 5}
        ).status_code
        == 422
    )
    assert cliente.get("/api/pronostico/evaluacion", params={"grupo": "No existe"}).json() == []


def test_seguimiento_compara_con_lo_vendido(entorno):
    """Un pronóstico de una semana ya completa aparece junto a la venta real de esa semana."""
    semana, grupo, real = sql(
        entorno,
        "SELECT semana, grupo, venta_neta FROM api.ventas_semanales WHERE es_completa "
        "ORDER BY semana LIMIT 1",
    )[0]
    sql(
        entorno,
        "INSERT INTO ml.pronostico (modelo_id, origen, semana, grupo, horizonte, "
        "venta_neta_pronosticada, inferior, superior, usa_datos_simulados) "
        "SELECT modelo_id, %s::date - 7, %s, %s, 1, 100, 80, 120, false "
        "FROM ml.modelo WHERE es_vigente",
        (semana, semana, grupo),
    )
    api = make_conninfo(entorno, options="-c role=faro_api")
    fila = sql(
        api,
        "SELECT venta_neta_pronosticada, venta_neta_real FROM api.pronostico_vs_real "
        "WHERE semana = %s AND grupo = %s",
        (semana, grupo),
    )
    assert [(float(a), float(b)) for a, b in fila] == [(100.0, float(real))]


def test_requiere_sesion(entorno):
    assert TestClient(app).get("/api/pronostico").status_code == 401


def test_la_api_y_el_modelo_describen_igual_las_lineas_base():
    assert LINEAS_BASE_API == LINEAS_BASE_ML
