"""Pruebas de la API de alertas y del monitoreo con bases temporales y el rol faro_api.

Las alertas se insertan como las dejaría el evaluador (con su explicación de IA y sus intentos
de correo); la API las lista, muestra el detalle y cambia SOLO su estado.
"""

import os

import pytest
from conftest import RAIZ, Url, sql, uno
from fastapi.testclient import TestClient
from psycopg.conninfo import make_conninfo

from backend.app import config as modulo_config
from backend.app.main import app
from backend.app.seguridad import hash_password
from etl.orchestration import pipeline

pytestmark = pytest.mark.integracion

PASSWORD = "Contraseña-de-prueba-123"

INSERTAR = """
INSERT INTO alerta.alerta (regla, clave_evento, creada_en, severidad, origen, indicador, entidad,
    valor_observado, umbral, referencia, periodo_desde, periodo_hasta, detalle, mensaje,
    explicacion_ia, accion_recomendada_ia, ia_modelo, incluye_simulados)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s)
RETURNING alerta_id
"""


@pytest.fixture(scope="module")
def entorno(bases):
    fuente, analitica = bases
    assert pipeline.ejecutar(fuente, analitica, modo="inicial", disparador="ci").estado == "exitoso"
    sql(analitica, (RAIZ / "database" / "security" / "roles_analitica.sql").read_text("utf-8"))
    sql(
        analitica,
        "INSERT INTO app.usuario (usuario, nombre, password_hash) VALUES (%s, %s, %s)",
        ("analista", "Usuario analista", hash_password(PASSWORD)),
    )
    caida = sql(
        analitica,
        INSERTAR,
        (
            "caida_ventas",
            "caida_ventas|total|2016-06-06",
            "2026-11-15 20:45+00",
            "critica",
            "regla",
            "Ventas netas semanales",
            "Total WWI",
            421418,
            15,
            1071676,
            "2016-06-06",
            "2016-06-11",
            '{"caida_pct": 60.7}',
            "Las ventas cayeron 60.7 %.",
            "La caída coincide con días simulados de bajo volumen.",
            "Revisar los pedidos.",
            "openai/gpt-oss-120b",
            True,
        ),
    )[0][0]
    costo = sql(
        analitica,
        INSERTAR,
        (
            "ventas_bajo_costo",
            "ventas_bajo_costo|total|2016-05-23",
            "2026-11-15 18:00+00",
            "advertencia",
            "regla",
            "Pérdida por ventas bajo costo",
            "Total WWI",
            2046,
            0,
            None,
            "2016-05-23",
            "2016-05-28",
            '{"lineas": 30}',
            "30 líneas bajo costo.",
            None,
            None,
            None,
            False,
        ),
    )[0][0]
    # La primera alerta se entregó al segundo intento; la segunda nunca se pudo enviar
    sql(
        analitica,
        "INSERT INTO alerta.envio (alerta_id, canal, intento, resultado, error) VALUES "
        "(%s, 'correo', 1, 'fallido', 'SMTPServerDisconnected'), "
        "(%s, 'correo', 2, 'enviado', NULL), "
        "(%s, 'correo', 1, 'fallido', 'timeout')",
        (caida, caida, costo),
    )
    sql(
        analitica,
        "INSERT INTO alerta.evaluacion (disparador, fin, estado, reglas_evaluadas, alertas_nuevas, "
        "correos_enviados) VALUES ('demo', now(), 'exitosa', 3, 2, 1)",
    )
    anteriores = {k: os.environ.get(k) for k in ("API_DATABASE_URL", "JWT_SECRET", "COOKIE_SEGURA")}
    os.environ.update(
        API_DATABASE_URL=make_conninfo(analitica, options="-c role=faro_api"),
        JWT_SECRET="a" * 48,
        COOKIE_SEGURA="false",
    )
    modulo_config.config.cache_clear()
    yield {"url": Url(analitica), "caida": caida, "costo": costo}
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


def test_sin_sesion_no_hay_alertas_ni_monitoreo(entorno):
    with TestClient(app) as anonimo:
        for ruta in ("/api/alertas", "/api/alertas/resumen", "/api/alertas/1", "/api/monitoreo"):
            assert anonimo.get(ruta).status_code == 401, ruta
        assert anonimo.patch("/api/alertas/1", json={"estado": "atendida"}).status_code == 401


def test_resumen_cuenta_las_nuevas_y_las_criticas(cliente):
    r = cliente.get("/api/alertas/resumen").json()
    assert r["nuevas"] == 2 and r["criticas_nuevas"] == 1
    assert r["ultima_creada_en"].startswith("2026-11-15T20:45")


def test_lista_de_la_mas_reciente_con_contenido_y_entrega(cliente, entorno):
    alertas = cliente.get("/api/alertas").json()
    assert [a["alerta_id"] for a in alertas] == [entorno["caida"], entorno["costo"]]
    caida, costo = alertas
    assert caida["regla_nombre"] == "Caída de ventas" and caida["unidad"] == "%"
    assert caida["valor_observado"] == 421418 and caida["referencia"] == 1071676
    assert caida["explicacion_ia"] and caida["ia_modelo"] == "openai/gpt-oss-120b"
    assert caida["incluye_simulados"] is True and caida["detalle"] == {"caida_pct": 60.7}
    assert caida["correo_enviado"] is True and caida["intentos_correo"] == 2
    assert costo["correo_enviado"] is False and costo["explicacion_ia"] is None
    assert costo["referencia"] is None


def test_detalle_con_cada_intento_de_entrega(cliente, entorno):
    d = cliente.get(f"/api/alertas/{entorno['caida']}").json()
    assert [(e["intento"], e["resultado"]) for e in d["envios"]] == [(1, "fallido"), (2, "enviado")]
    assert d["envios"][0]["error"] == "SMTPServerDisconnected"
    assert cliente.get("/api/alertas/999999").status_code == 404
    assert cliente.get("/api/alertas/0").status_code == 422


def test_cambiar_estado_registra_quien_cuando_y_la_nota(cliente, entorno):
    url, ida = entorno["url"], entorno["costo"]
    r = cliente.patch(f"/api/alertas/{ida}", json={"estado": "atendida", "nota": "  Revisado  "})
    assert r.status_code == 200
    d = r.json()
    assert d["estado"] == "atendida" and d["nota"] == "Revisado"
    assert d["estado_actualizado_por"] == "analista" and d["estado_actualizado_en"]
    assert d["mensaje"] == "30 líneas bajo costo."  # el contenido no cambia

    # Sin nota se conserva la anterior; una nota vacía la borra
    assert cliente.patch(f"/api/alertas/{ida}", json={"estado": "resuelta"}).json()["nota"] == (
        "Revisado"
    )
    assert (
        cliente.patch(f"/api/alertas/{ida}", json={"estado": "resuelta", "nota": ""}).json()["nota"]
        is None
    )
    assert uno(url, "SELECT estado FROM alerta.alerta WHERE alerta_id = %s", (ida,)) == "resuelta"

    # Filtro por estado y contador actualizados
    assert [a["alerta_id"] for a in cliente.get("/api/alertas?estado=resuelta").json()] == [ida]
    assert cliente.get("/api/alertas/resumen").json()["nuevas"] == 1

    # Reabrirla la devuelve a nueva
    assert (
        cliente.patch(f"/api/alertas/{ida}", json={"estado": "nueva"}).json()["estado"] == "nueva"
    )


def test_cambios_de_estado_invalidos(cliente, entorno):
    ida = entorno["caida"]
    assert cliente.patch(f"/api/alertas/{ida}", json={"estado": "borrada"}).status_code == 422
    assert cliente.patch(f"/api/alertas/{ida}", json={}).status_code == 422
    assert (
        cliente.patch(f"/api/alertas/{ida}", json={"estado": "atendida", "nota": "x" * 501})
    ).status_code == 422
    assert cliente.patch("/api/alertas/999999", json={"estado": "atendida"}).status_code == 404
    # No se puede cambiar el contenido por la API (campos fuera del modelo se ignoran)
    r = cliente.patch(f"/api/alertas/{ida}", json={"estado": "nueva", "mensaje": "otro"})
    assert r.json()["mensaje"] == "Las ventas cayeron 60.7 %."


def test_monitoreo_resume_etl_calidad_modelo_y_notificaciones(cliente, entorno):
    m = cliente.get("/api/monitoreo").json()
    ultima = m["etl"][0]
    assert ultima["estado"] == "exitoso" and ultima["modo"] == "inicial"
    assert ultima["leidas"] > 0 and ultima["reconciliado"] is True and ultima["error"] is None
    # La calidad es la de la última ejecución, agrupada por dimensión
    assert m["calidad_ejecucion_id"] == ultima["ejecucion_id"] and m["calidad"]
    assert sum(d["reglas"] for d in m["dimensiones"]) == len(m["calidad"])
    # Lo que incumple se separa entre lo que va a cuarentena y lo que solo se marca
    for d in m["dimensiones"]:
        assert d["a_cuarentena"] + d["marcadas"] == d["fallaron"]
    reglas_marca = [r for r in m["calidad"] if r["accion"] == "marcar"]
    assert sum(d["marcadas"] for d in m["dimensiones"]) == sum(r["fallaron"] for r in reglas_marca)
    assert all(
        d["cumplimiento_pct"] is None or 0 <= d["cumplimiento_pct"] <= 100 for d in m["dimensiones"]
    )
    assert m["modelo"] is None  # sin modelo entrenado en esta base
    n = m["notificaciones"]
    assert n["evaluaciones"][0]["disparador"] == "demo"
    assert sum(n["alertas_por_estado"].values()) == 2
    assert n["correos_enviados"] == 1 and n["intentos_fallidos"] == 2
    assert n["alertas_sin_entregar"] == 1


def test_un_error_del_etl_se_muestra_sin_detalle_interno(cliente, entorno):
    url = entorno["url"]
    sql(
        url,
        "INSERT INTO audit.etl_execution (pipeline_name, trigger, mode, end_time, status, "
        "error_detail) VALUES ('ventas', 'cron', 'incremental', now(), 'fallido', %s)",
        ("OperationalError: conexión rechazada\nTraceback interno con rutas" + "x" * 500,),
    )
    ultima = cliente.get("/api/monitoreo").json()["etl"][0]
    assert ultima["estado"] == "fallido"
    assert ultima["error"] == "OperationalError: conexión rechazada"
