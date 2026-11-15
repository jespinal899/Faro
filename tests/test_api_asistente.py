"""Pruebas de la API del asistente con el rol faro_api y un cliente de Claude SIMULADO.

Comprueban que las cifras que devuelve el asistente son las del DW (consulta independiente),
que cada pregunta queda registrada, y los controles: sesión, clave configurada, límite por
usuario, validación de la entrada y errores del servicio de IA.
"""

import json
import os

import anthropic
import httpx2
import pytest
from conftest import RAIZ, Url, sql, uno
from fastapi.testclient import TestClient
from psycopg.conninfo import make_conninfo
from test_asistente import ClienteSimulado, final, herramienta

from backend.app import config as modulo_config
from backend.app.main import app
from backend.app.rutas import asistente as rutas_asistente
from backend.app.seguridad import hash_password
from etl.orchestration import pipeline

pytestmark = pytest.mark.integracion

PASSWORD = "Contraseña-de-prueba-123"
VARIABLES = ("API_DATABASE_URL", "JWT_SECRET", "COOKIE_SEGURA", "ANTHROPIC_API_KEY")


@pytest.fixture(scope="module")
def entorno(bases):
    fuente, analitica = bases
    assert pipeline.ejecutar(fuente, analitica, modo="inicial", disparador="ci").estado == "exitoso"
    sql(analitica, (RAIZ / "database" / "security" / "roles_analitica.sql").read_text("utf-8"))
    for usuario in ("analista", "otro"):
        sql(
            analitica,
            "INSERT INTO app.usuario (usuario, nombre, password_hash) VALUES (%s, %s, %s)",
            (usuario, f"Usuario {usuario}", hash_password(PASSWORD)),
        )
    anteriores = {k: os.environ.get(k) for k in VARIABLES}
    os.environ.update(
        API_DATABASE_URL=make_conninfo(analitica, options="-c role=faro_api"),
        JWT_SECRET="a" * 48,
        COOKIE_SEGURA="false",
        ANTHROPIC_API_KEY="clave-de-prueba",  # el cliente es simulado: nunca sale a la red
    )
    modulo_config.config.cache_clear()
    yield Url(analitica)
    for k, v in anteriores.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    modulo_config.config.cache_clear()


def _cliente_http(usuario: str = "analista") -> TestClient:
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"usuario": usuario, "password": PASSWORD}).is_success
    return c


def _simular(monkeypatch, *respuestas) -> ClienteSimulado:
    simulado = ClienteSimulado(*respuestas)
    monkeypatch.setattr(rutas_asistente, "cliente", lambda: simulado)
    return simulado


def test_las_cifras_son_las_del_dw_y_la_pregunta_queda_registrada(entorno, monkeypatch):
    desde, hasta = sql(
        entorno, "SELECT fecha_desde::text, fecha_hasta::text FROM api.estado_datos"
    )[0]
    _simular(
        monkeypatch,
        herramienta("consultar_indicadores", {"desde": desde, "hasta": hasta}),
        final(resumen="Total del período.", hechos=[{"texto": "Ventas netas", "consultas": [1]}]),
    )
    with _cliente_http() as c:
        r = c.post("/api/asistente", json={"pregunta": "¿Cuánto vendimos en todo el período?"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["tipo"] == "respuesta" and d["hechos"][0]["respaldada"]
    assert d["generado_por"] == "claude-haiku-5-5" and d["costo_usd"] > 0
    # Consulta independiente sobre la tabla de hechos (sin pasar por la API ni sus vistas)
    independiente = uno(
        entorno,
        "SELECT sum(venta_neta) FROM dw.fact_ventas WHERE fecha_factura BETWEEN %s AND %s",
        (desde, hasta),
    )
    ventas = d["consultas"][0]["resultado"]["indicadores"]["ventas_netas"]
    assert ventas == pytest.approx(float(independiente), abs=0.01)
    # Registro: pregunta, consulta hecha, tokens y costo; nunca la respuesta
    fila = sql(
        entorno,
        "SELECT tipo_respuesta, herramientas, tokens_entrada, costo_usd "
        "FROM app.consulta_asistente "
        "WHERE usuario = 'analista' ORDER BY consulta_id DESC LIMIT 1",
    )[0]
    assert fila[0] == "respuesta" and fila[1][0]["herramienta"] == "consultar_indicadores"
    assert fila[2] > 0 and float(fila[3]) > 0
    columnas = {
        x[0]
        for x in sql(
            entorno,
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'consulta_asistente'",
        )
    }
    assert not columnas & {"respuesta", "resumen", "resultado"}


def test_sin_sesion_y_entradas_invalidas(entorno, monkeypatch):
    _simular(monkeypatch)
    assert TestClient(app).post("/api/asistente", json={"pregunta": "Hola hola"}).status_code == 401
    with _cliente_http() as c:
        assert c.post("/api/asistente", json={"pregunta": "x" * 501}).status_code == 422
        assert c.post("/api/asistente", json={"pregunta": "ok?", "sql": "DROP"}).status_code == 422
        historial = [{"rol": "usuario", "texto": "a"}] * 7
        assert (
            c.post("/api/asistente", json={"pregunta": "¿Y?", "historial": historial}).status_code
            == 422
        )


def test_sin_clave_responde_no_configurado(entorno, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    monkeypatch.setattr(rutas_asistente, "config", lambda: modulo_config.config())
    with _cliente_http() as c:
        assert c.get("/api/asistente/info").json()["disponible"] is False
        r = c.post("/api/asistente", json={"pregunta": "¿Cuánto vendimos?"})
    assert r.status_code == 503 and "no está configurado" in r.json()["detail"]


def test_limite_de_preguntas_por_usuario(entorno, monkeypatch):
    sql(
        entorno,
        "INSERT INTO app.consulta_asistente (usuario, pregunta, tipo_respuesta) "
        "SELECT 'otro', 'pregunta anterior', 'respuesta' FROM generate_series(1, 20)",
    )
    _simular(monkeypatch)
    with _cliente_http("otro") as c:
        info = c.get("/api/asistente/info").json()
        assert info["usadas_hoy"] == 20 and info["limite_hora"] == 20
        r = c.post("/api/asistente", json={"pregunta": "¿Cuánto vendimos?"})
    assert r.status_code == 429 and "límite" in r.json()["detail"]


def test_sin_saldo_en_el_servicio_de_ia_se_explica_y_se_registra(entorno, monkeypatch):
    class SinSaldo:
        messages = None

        def __init__(self):
            self.messages = self

        def create(self, **kwargs):
            respuesta = httpx2.Response(
                400, request=httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
            )
            raise anthropic.BadRequestError(
                "Your credit balance is too low to access the Anthropic API.",
                response=respuesta,
                body=None,
            )

    monkeypatch.setattr(rutas_asistente, "cliente", SinSaldo)
    antes = uno(
        entorno, "SELECT count(*) FROM app.consulta_asistente WHERE tipo_respuesta = 'error'"
    )
    with _cliente_http() as c:
        r = c.post("/api/asistente", json={"pregunta": "¿Cuánto vendimos?"})
    assert r.status_code == 503 and "saldo" in r.json()["detail"]
    despues = uno(
        entorno, "SELECT count(*) FROM app.consulta_asistente WHERE tipo_respuesta = 'error'"
    )
    assert despues == antes + 1


def test_respuesta_json_serializable_con_consultas(entorno, monkeypatch):
    """Las consultas incluidas en la respuesta son JSON puro (fechas como texto)."""
    _simular(
        monkeypatch,
        herramienta("consultar_indicadores", {"desde": "2010-01-01", "hasta": "2010-12-31"}),
        final(tipo="sin_datos", resumen="No hay ventas en 2010."),
    )
    with _cliente_http() as c:
        d = c.post("/api/asistente", json={"pregunta": "¿Cuánto vendimos en 2010?"}).json()
    assert d["tipo"] == "sin_datos"
    assert "No hay ventas" in d["consultas"][0]["resultado"]["sin_datos"]
    json.dumps(d)
