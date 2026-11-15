"""Prueba de punta a punta (guía, sección 12): de la fuente al resultado visible en la API.

Recorre la plataforma entera, cada etapa con su rol de mínimo privilegio, sobre bases TEMPORALES:

  1. Fuente: la operación normal de 5 semanas y luego una semana de baja venta (simulador).
  2. ETL (etl_lector y faro_etl): carga inicial e incremental, staging, DW y reconciliación.
  3. Alertas (faro_alertas): detecta la caída de ventas, la explica (IA simulada) y la envía
     (correo simulado). Una segunda evaluación no la duplica.
  4. API (faro_api), como la ve el dashboard: frescura, KPI iguales a una suma independiente
     sobre la FUENTE, la alerta con su detalle, el cambio de estado y el monitoreo.

La IA y el correo son simulados (nunca salen a la red); todo lo demás es el código real.
"""

import json
import os
from datetime import date
from types import SimpleNamespace

import pytest
from conftest import RAIZ, Url, sql, uno
from fastapi.testclient import TestClient
from psycopg.conninfo import make_conninfo

from backend.app import config as modulo_config
from backend.app.main import app
from backend.app.seguridad import hash_password
from etl.db import conectar
from etl.orchestration import pipeline
from notifications import correo, evaluar
from simulador import ventas

pytestmark = pytest.mark.integracion

PASSWORD = "Contraseña-de-prueba-123"
CFG = correo.ConfigCorreo(usuario="faro@ejemplo.com", clave="x" * 16, destino="a@ejemplo.com")


def _como(url: str, rol: str) -> str:
    return make_conninfo(url, options=f"-c role={rol}")


class IASimulada:
    """Imita al cliente de Groq: devuelve una explicación fija en el JSON esperado."""

    def __init__(self):
        self.pedidos = []
        respuesta = json.dumps(
            {"explicacion": "Caída en la semana simulada.", "accion_recomendada": "Revisar."}
        )

        def crear(**kw):
            self.pedidos.append(kw)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=respuesta))]
            )

        self.chat = SimpleNamespace(completions=SimpleNamespace(create=crear))


@pytest.fixture(scope="module")
def plataforma(bases):
    fuente, analitica = bases
    # Roles de mínimo privilegio, como en producción
    sql(fuente, (RAIZ / "database" / "security" / "roles_fuente.sql").read_text("utf-8"))
    sql(analitica, (RAIZ / "database" / "security" / "roles_analitica.sql").read_text("utf-8"))
    etl_fuente, etl_analitica = _como(fuente, "etl_lector"), _como(analitica, "faro_etl")

    # Carga inicial con los datos mínimos (una factura del lunes 04/01/2016)
    assert pipeline.ejecutar(etl_fuente, etl_analitica, modo="inicial", disparador="ci").estado == (
        "exitoso"
    )
    # Operación: hasta el sábado 06/02/2016 a ritmo normal (4 pedidos por día hábil), luego una
    # semana completa (08 al 13/02) al 25 %. Todo queda marcado como SIMULADO.
    ventas.simular(_como(fuente, "wwi_app"), dias=29, pedidos=4, semilla=11)
    ventas.simular(_como(fuente, "wwi_app"), dias=6, pedidos=4, semilla=12, factor_volumen=0.25)
    resumen = pipeline.ejecutar(etl_fuente, etl_analitica, disparador="ci")
    assert resumen.estado == "exitoso" and resumen.reconciliado

    sql(
        analitica,
        "INSERT INTO app.usuario (usuario, nombre, password_hash) VALUES (%s, %s, %s)",
        ("analista", "Usuario analista", hash_password(PASSWORD)),
    )
    anteriores = {k: os.environ.get(k) for k in ("API_DATABASE_URL", "JWT_SECRET", "COOKIE_SEGURA")}
    os.environ.update(
        API_DATABASE_URL=_como(analitica, "faro_api"), JWT_SECRET="e" * 48, COOKIE_SEGURA="false"
    )
    modulo_config.config.cache_clear()
    yield {"fuente": Url(fuente), "analitica": Url(analitica)}
    for k, v in anteriores.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    modulo_config.config.cache_clear()


@pytest.fixture(scope="module")
def correos():
    enviados = []
    original = correo.enviar
    correo.enviar = lambda mensaje, cfg: enviados.append(mensaje)
    yield enviados
    correo.enviar = original


@pytest.fixture(scope="module")
def evaluacion(plataforma, correos):
    ia = IASimulada()
    with conectar(_como(plataforma["analitica"], "faro_alertas")) as conn:
        primera = evaluar.evaluar(
            conn, config_correo=CFG, cliente_ia=ia, dormir=lambda s: None, disparador="ci"
        )
    with conectar(_como(plataforma["analitica"], "faro_alertas")) as conn:
        segunda = evaluar.evaluar(
            conn, config_correo=CFG, cliente_ia=ia, dormir=lambda s: None, disparador="ci"
        )
    return primera, segunda, ia


@pytest.fixture(scope="module")
def cliente(plataforma, evaluacion):
    with TestClient(app) as c:
        assert c.post(
            "/api/auth/login", json={"usuario": "analista", "password": PASSWORD}
        ).is_success
        yield c


def test_la_venta_nueva_de_la_fuente_llega_al_dashboard(cliente, plataforma):
    estado = cliente.get("/api/estado").json()
    assert estado["fecha_hasta"] == "2016-02-13"  # el último día simulado
    assert estado["estado_ultima_ejecucion"] == "exitoso" and estado["lineas_simuladas"] > 0

    # KPI del dashboard = suma independiente sobre la FUENTE (no sobre el DW)
    kpi = cliente.get("/api/kpis", params={"desde": "2016-01-01", "hasta": "2016-02-13"}).json()
    neta, facturas = sql(
        plataforma["fuente"],
        "SELECT sum(l.extended_price - l.tax_amount), count(DISTINCT i.invoice_id) "
        "FROM sales.invoice_lines l JOIN sales.invoices i USING (invoice_id)",
    )[0]
    assert kpi["actual"]["ventas_netas"] == pytest.approx(float(neta))
    assert kpi["actual"]["facturas"] == facturas


def test_la_semana_de_baja_venta_dispara_una_sola_alerta_y_un_solo_correo(
    plataforma, evaluacion, correos
):
    primera, segunda, ia = evaluacion
    caidas = sql(
        plataforma["analitica"],
        "SELECT severidad, periodo_desde FROM alerta.alerta "
        "WHERE alerta_id = ANY(%s) AND regla = 'caida_ventas'",
        (primera.nuevas,),
    )
    assert caidas == [("critica", date(2016, 2, 8))]
    assert primera.correos_enviados == len(primera.nuevas) == len(correos)
    assert ia.pedidos  # se pidió la explicación
    # Mismo evento: la segunda evaluación no crea alertas ni envía correos
    assert (len(segunda.nuevas), segunda.correos_enviados) == (0, 0)
    assert segunda.ya_existentes == len(primera.nuevas)


def test_la_alerta_se_ve_y_se_atiende_desde_el_dashboard(cliente, plataforma):
    assert cliente.get("/api/alertas/resumen").json()["criticas_nuevas"] == 1
    alerta = next(a for a in cliente.get("/api/alertas").json() if a["regla"] == "caida_ventas")
    assert alerta["incluye_simulados"] is True and alerta["correo_enviado"] is True
    assert alerta["explicacion_ia"] == "Caída en la semana simulada."
    assert alerta["detalle"]["caida_pct"] > 30

    d = cliente.get(f"/api/alertas/{alerta['alerta_id']}").json()
    assert [e["resultado"] for e in d["envios"]] == ["enviado"]

    r = cliente.patch(
        f"/api/alertas/{alerta['alerta_id']}", json={"estado": "resuelta", "nota": "Era la demo"}
    )
    assert r.json()["estado"] == "resuelta" and r.json()["estado_actualizado_por"] == "analista"
    assert (
        uno(
            plataforma["analitica"],
            "SELECT estado FROM alerta.alerta WHERE alerta_id = %s",
            (alerta["alerta_id"],),
        )
        == "resuelta"
    )


def test_el_monitoreo_muestra_todo_el_recorrido(cliente):
    m = cliente.get("/api/monitoreo").json()
    inicial, incremental = m["etl"][1], m["etl"][0]
    assert (inicial["modo"], incremental["modo"]) == ("inicial", "incremental")
    assert incremental["estado"] == "exitoso" and incremental["reconciliado"] is True
    assert incremental["nuevas"] > 0  # las ventas simuladas
    n = m["notificaciones"]
    assert [e["estado"] for e in n["evaluaciones"]] == ["exitosa", "exitosa"]
    assert n["correos_enviados"] >= 1 and n["alertas_sin_entregar"] == 0
