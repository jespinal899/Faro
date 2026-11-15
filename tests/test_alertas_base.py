"""Pruebas de integración de las alertas con bases temporales y el rol faro_alertas.

La guía pide probar: disparo y no disparo, sin duplicados, reintentos y fallas de envío,
registro de generación y entrega, y consulta del detalle y estado. Las reglas se reemplazan
por alertas fijas (los datos mínimos de prueba no tienen semanas completas); el correo y la
IA son simulados: nunca salen a la red.
"""

import smtplib
from datetime import date

import psycopg
import pytest
from conftest import RAIZ, Url, sql, uno
from psycopg.conninfo import make_conninfo

from etl.db import conectar
from etl.orchestration import pipeline
from notifications import correo, evaluar, reglas

pytestmark = pytest.mark.integracion

CFG = correo.ConfigCorreo(
    usuario="faro@ejemplo.com", clave="x" * 16, destino="analista@ejemplo.com"
)


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
    assert pipeline.ejecutar(fuente, analitica, modo="inicial", disparador="ci").estado == "exitoso"
    sql(analitica, (RAIZ / "database" / "security" / "roles_analitica.sql").read_text("utf-8"))
    return Url(analitica)


def _alerta(regla: str, clave: str) -> reglas.Alerta:
    return reglas.Alerta(
        regla=regla,
        clave_evento=clave,
        severidad="advertencia",
        origen="regla",
        indicador="Ventas netas semanales",
        entidad="Total WWI",
        valor_observado=800.0,
        umbral=850.0,
        referencia=1000.0,
        periodo_desde=date(2016, 5, 23),
        periodo_hasta=date(2016, 5, 28),
        mensaje="Caída de prueba.",
        detalle={"caida_pct": 20.0},
    )


@pytest.fixture
def reglas_fijas(monkeypatch):
    monkeypatch.setattr(
        reglas,
        "caida_ventas",
        lambda *a: [_alerta("caida_ventas", "caida_ventas|total|2016-05-23")],
    )
    monkeypatch.setattr(reglas, "pronostico_bajo", lambda *a: [])
    monkeypatch.setattr(
        reglas,
        "ventas_bajo_costo",
        lambda *a: [_alerta("ventas_bajo_costo", "ventas_bajo_costo|total|2016-05-23")],
    )


@pytest.fixture
def correos(monkeypatch):
    """Correo simulado: guarda los mensajes; falla mientras `fallar` sea True."""
    estado = {"enviados": [], "fallar": False}

    def enviar(mensaje, cfg):
        if estado["fallar"]:
            raise smtplib.SMTPServerDisconnected("servidor caído")
        estado["enviados"].append(mensaje)

    monkeypatch.setattr(correo, "enviar", enviar)
    return estado


def _evaluar(url, **kw):
    with conectar(_como(url, "faro_alertas")) as conn:
        return evaluar.evaluar(
            conn, config_correo=CFG, usar_ia=False, dormir=lambda s: None, disparador="ci", **kw
        )


def test_dispara_registra_y_envia_sin_duplicar(analitica, reglas_fijas, correos):
    r1 = _evaluar(analitica)
    assert len(r1.nuevas) == 2 and r1.correos_enviados == 2
    assert len(correos["enviados"]) == 2

    r2 = _evaluar(analitica)  # mismo evento: ni alerta ni correo nuevos
    assert (len(r2.nuevas), r2.ya_existentes, r2.correos_enviados) == (0, 2, 0)
    assert len(correos["enviados"]) == 2
    assert uno(analitica, "SELECT count(*) FROM alerta.alerta") == 2
    # Generación y entrega registradas
    assert sql(
        analitica,
        "SELECT estado, alertas_nuevas, correos_enviados FROM alerta.evaluacion ORDER BY 1, 2",
    ) == [("exitosa", 0, 0), ("exitosa", 2, 2)]
    assert uno(analitica, "SELECT count(*) FROM alerta.envio WHERE resultado = 'enviado'") == 2


def test_una_falla_de_envio_se_registra_y_se_reintenta_en_la_siguiente_evaluacion(
    analitica, correos, monkeypatch
):
    monkeypatch.setattr(
        reglas, "caida_ventas", lambda *a: [_alerta("caida_ventas", "caida|reintento")]
    )
    monkeypatch.setattr(reglas, "pronostico_bajo", lambda *a: [])
    monkeypatch.setattr(reglas, "ventas_bajo_costo", lambda *a: [])
    correos["fallar"] = True
    r = _evaluar(analitica)
    assert r.correos_fallidos == 1
    alerta_id = r.nuevas[0]
    assert sql(
        analitica,
        "SELECT intento, resultado FROM alerta.envio WHERE alerta_id = %s ORDER BY intento",
        (alerta_id,),
    ) == [(1, "fallido"), (2, "fallido"), (3, "fallido")]

    correos["fallar"] = False  # el servidor vuelve: la siguiente evaluación lo reintenta
    assert _evaluar(analitica).correos_enviados == 1
    assert (
        uno(
            analitica,
            "SELECT max(intento) FROM alerta.envio WHERE alerta_id = %s AND resultado = 'enviado'",
            (alerta_id,),
        )
        == 4
    )


def test_una_evaluacion_que_falla_queda_registrada(analitica, monkeypatch):
    def rompe(*a):
        raise ValueError("regla rota")

    monkeypatch.setattr(reglas, "caida_ventas", rompe)
    with pytest.raises(ValueError):
        _evaluar(analitica)
    assert sql(
        analitica,
        "SELECT estado, error FROM alerta.evaluacion ORDER BY evaluacion_id DESC LIMIT 1",
    ) == [("fallida", "ValueError: regla rota")]


def test_las_vistas_de_entrada_reconcilian_con_el_dw(analitica):
    total = uno(analitica, "SELECT sum(venta_neta) FROM alerta.ventas_semanales_total")
    assert total == uno(analitica, "SELECT sum(venta_neta) FROM dw.fact_ventas")


def test_permisos_de_faro_alertas_y_faro_api(analitica):
    alertas, api = _como(analitica, "faro_alertas"), _como(analitica, "faro_api")
    assert _denegado(alertas, "SELECT count(*) FROM dw.fact_ventas")
    assert _denegado(alertas, "DELETE FROM alerta.alerta")
    assert _denegado(alertas, "UPDATE alerta.alerta SET severidad = 'critica'")
    # La API lee el detalle por su vista y solo cambia el estado (y la nota)
    assert uno(api, "SELECT count(*) FROM api.alertas") >= 1
    alerta_id = uno(api, "SELECT min(alerta_id) FROM api.alertas")
    sql(
        api,
        "UPDATE alerta.alerta SET estado = 'atendida', estado_actualizado_en = now(), "
        "estado_actualizado_por = 'analista' WHERE alerta_id = %s",
        (alerta_id,),
    )
    assert (
        uno(api, "SELECT estado FROM api.alertas WHERE alerta_id = %s", (alerta_id,)) == "atendida"
    )
    assert _denegado(api, "UPDATE alerta.alerta SET valor_observado = 0")
    assert _denegado(api, "DELETE FROM alerta.alerta")
