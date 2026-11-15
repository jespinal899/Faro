"""Pruebas unitarias de las alertas (guía, sección 9): condición verdadera y falsa de cada
regla, severidad, contenido mínimo del correo, reintentos y la IA como parte opcional."""

import json
import smtplib
from datetime import date, datetime, timedelta
from types import SimpleNamespace as N

import pytest

from notifications import correo, ia, reglas

LUNES = date(2016, 5, 23)  # semana completa: 23 al 28 de mayo
HASTA = date(2016, 5, 28)  # sábado


def _semanas(actual: float, previa: float = 1000.0, simulada=False) -> dict:
    s = {LUNES - timedelta(weeks=k): (previa, False) for k in range(1, 5)}
    s[LUNES] = (actual, simulada)
    return s


# ---------------------------------------------------------------- semana completa


@pytest.mark.parametrize(
    ("hasta", "esperado"),
    [
        (date(2016, 5, 28), date(2016, 5, 23)),  # sábado: la semana ya está completa
        (date(2016, 5, 29), date(2016, 5, 23)),  # domingo
        (date(2016, 6, 2), date(2016, 5, 23)),  # jueves: la semana en curso no cuenta
    ],
)
def test_ultima_semana_completa(hasta, esperado):
    assert reglas.ultima_semana_completa(hasta) == esperado


# ---------------------------------------------------------------- caída de ventas (P12)


def test_caida_de_ventas_condicion_verdadera_y_falsa():
    assert reglas.caida_ventas(_semanas(900), date(2013, 1, 1), HASTA, 15) == []  # cae 10 %
    a = reglas.caida_ventas(_semanas(800), date(2013, 1, 1), HASTA, 15)  # cae 20 %
    assert len(a) == 1 and a[0].severidad == "advertencia"
    assert (a[0].valor_observado, a[0].referencia, a[0].umbral) == (800, 1000, 850)
    assert a[0].clave_evento == "caida_ventas|total|2016-05-23"
    assert a[0].detalle["caida_pct"] == 20.0 and a[0].periodo_hasta == date(2016, 5, 28)


def test_caida_de_ventas_critica_y_marca_simulados():
    a = reglas.caida_ventas(_semanas(650, simulada=True), date(2013, 1, 1), HASTA, 15)  # 35 %
    assert a[0].severidad == "critica" and a[0].incluye_simulados


def test_caida_de_ventas_sin_semanas_de_referencia_completas_no_alerta():
    # La historia empieza después de las semanas de referencia
    assert reglas.caida_ventas(_semanas(100), date(2016, 5, 10), HASTA, 15) == []


# ---------------------------------------------------------------- pronóstico bajo (P13)


def _pronostico(venta: float, superior: float) -> list[dict]:
    return [
        {
            "grupo": "Mugs",
            "semana": date(2016, 5, 30) + timedelta(weeks=h - 1),
            "horizonte": h,
            "venta_neta_pronosticada": venta if h == 2 else 1000.0,
            "inferior": venta * 0.8,
            "superior": superior if h == 2 else 1200.0,
            "version": "20261115.145744",
            "origen": date(2016, 5, 23),
            "usa_datos_simulados": False,
        }
        for h in range(1, 5)
    ]


def test_pronostico_bajo_condicion_verdadera_falsa_y_critica():
    historia = {"Mugs": [1000.0] * 13}
    assert reglas.pronostico_bajo(_pronostico(900, 1100), historia, 85) == []  # 90 % >= 85 %
    a = reglas.pronostico_bajo(_pronostico(800, 1000), historia, 85)
    assert len(a) == 1 and a[0].severidad == "advertencia" and a[0].origen == "modelo"
    assert a[0].detalle["horizonte"] == 2 and a[0].detalle["version_modelo"] == "20261115.145744"
    assert a[0].clave_evento == "pronostico_bajo|Mugs|2016-05-23"
    assert "PREDICCIÓN" in a[0].mensaje
    # Crítica: ni el extremo optimista del rango del 80 % alcanza el umbral
    assert reglas.pronostico_bajo(_pronostico(700, 840), historia, 85)[0].severidad == "critica"


def test_pronostico_bajo_sin_historia_suficiente_no_alerta():
    assert reglas.pronostico_bajo(_pronostico(100, 120), {"Mugs": [1000.0] * 5}, 85) == []


# ---------------------------------------------------------------- ventas bajo costo (P14)


def test_ventas_bajo_costo_condicion_verdadera_y_falsa():
    fila = {"lineas": 30, "facturas": 30, "perdida": 2046.0, "venta_neta": 16354.0}
    assert reglas.ventas_bajo_costo({LUNES: fila}, HASTA, 5000) == []  # pérdida bajo el umbral
    assert reglas.ventas_bajo_costo({}, HASTA, 0) == []  # sin ventas bajo costo
    a = reglas.ventas_bajo_costo({LUNES: fila}, HASTA, 0)
    assert (
        a[0].valor_observado == 2046.0 and a[0].clave_evento == "ventas_bajo_costo|total|2016-05-23"
    )


# ---------------------------------------------------------------- correo


CFG = correo.ConfigCorreo(
    usuario="faro@ejemplo.com", clave="x" * 16, destino="analista@ejemplo.com"
)
ALERTA = {
    "alerta_id": 7,
    "creada_en": datetime(2026, 11, 15, 18, 0),
    "regla": "pronostico_bajo",
    "regla_nombre": "Pronóstico bajo umbral",
    "severidad": "critica",
    "origen": "modelo",
    "indicador": "Venta neta semanal PRONOSTICADA",
    "entidad": "Mugs",
    "valor_observado": 700.0,
    "umbral": 850.0,
    "referencia": 1000.0,
    "periodo_desde": date(2016, 6, 6),
    "periodo_hasta": date(2016, 6, 11),
    "detalle": {"horizonte": 2, "version_modelo": "20261115.145744"},
    "mensaje": "PREDICCIÓN: ...",
    "explicacion_ia": "Podría deberse a menor demanda.",
    "accion_recomendada_ia": "Revisar el inventario.",
    "ia_modelo": "openai/gpt-oss-120b",
    "incluye_simulados": True,
    "estado": "nueva",
    "intentos": 0,
}


def test_el_correo_tiene_el_contenido_minimo_de_la_guia():
    m = correo.componer(ALERTA, CFG)
    texto = m.get_content()
    assert "CRÍTICA" in m["Subject"] and "#7" in m["Subject"] and "Mugs" in m["Subject"]
    for esperado in (
        "Alerta #7 · 15/11/2026 18:00",  # identificador y fecha/hora
        "Pronóstico bajo umbral (origen: modelo de ML)",  # tipo y origen
        "Severidad: CRÍTICA",
        "Indicador: Venta neta semanal PRONOSTICADA · Entidad: Mugs",
        "Valor observado (PREDICCIÓN): USD 700.00",
        "Umbral: USD 850.00 · Referencia: USD 1,000.00",
        "Período: 06/06/2016 al 11/06/2016",
        "Modelo: 20261115.145744 · horizonte: 2",  # versión y horizonte de la predicción
        "(GENERADA POR IA, openai/gpt-oss-120b)",  # la IA se identifica
        "ventas SIMULADAS",
        "Estado: nueva",
    ):
        assert esperado in texto, esperado
    assert CFG.clave not in texto  # nunca la contraseña


def test_reintenta_y_registra_cada_intento(monkeypatch):
    fallas = [smtplib.SMTPServerDisconnected("caído"), OSError("sin red")]

    def enviar(mensaje, cfg):
        if fallas:
            raise fallas.pop(0)

    monkeypatch.setattr(correo, "enviar", enviar)
    registro, esperas = [], []
    ok = correo.enviar_con_reintentos(
        ALERTA, CFG, lambda i, r, e: registro.append((i, r)), dormir=esperas.append
    )
    assert ok and registro == [(1, "fallido"), (2, "fallido"), (3, "enviado")]
    assert esperas == [2, 4]  # espera creciente


def test_si_todos_los_intentos_fallan_queda_pendiente(monkeypatch):
    def falla(mensaje, cfg):
        raise smtplib.SMTPAuthenticationError(535, b"credenciales")

    monkeypatch.setattr(correo, "enviar", falla)
    registro = []
    alerta = {**ALERTA, "intentos": 3}  # ya hubo 3 intentos en una evaluación anterior
    ok = correo.enviar_con_reintentos(
        alerta, CFG, lambda i, r, e: registro.append((i, r)), dormir=lambda s: None
    )
    assert (
        not ok and [i for i, _ in registro] == [4, 5, 6] and {r for _, r in registro} == {"fallido"}
    )


def test_sin_configuracion_de_correo_no_hay_config(monkeypatch):
    for v in ("SMTP_USUARIO", "SMTP_PASSWORD", "ALERTAS_DESTINO"):
        monkeypatch.setenv(v, "")
    assert correo.ConfigCorreo.desde_entorno() is None


# ---------------------------------------------------------------- IA (opcional)


class _ClienteIA:
    def __init__(self, contenido=None, falla=False):
        self.contenido, self.falla, self.pedidos = contenido, falla, []
        self.chat = N(completions=self)

    def create(self, **kwargs):
        self.pedidos.append(kwargs)
        if self.falla:
            raise RuntimeError("servicio caído")
        return N(choices=[N(message=N(content=self.contenido))])


def test_la_ia_explica_sin_herramientas_y_con_esquema():
    cliente = _ClienteIA(
        json.dumps({"explicacion": "Hipótesis.", "accion_recomendada": "Revisar."})
    )
    assert ia.explicar(ALERTA, cliente=cliente) == ("Hipótesis.", "Revisar.", ia.MODELO)
    pedido = cliente.pedidos[0]
    assert "tools" not in pedido and pedido["response_format"]["json_schema"]["strict"] is True
    assert "inventes cifras" in pedido["messages"][0]["content"]


def test_si_la_ia_falla_la_alerta_sigue_sin_explicacion(monkeypatch):
    assert ia.explicar(ALERTA, cliente=_ClienteIA(falla=True)) is None
    monkeypatch.setenv("GROQ_API_KEY", "")
    assert ia.explicar(ALERTA) is None
