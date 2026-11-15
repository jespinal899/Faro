"""Pruebas unitarias del motor del asistente con un cliente de Claude SIMULADO (sin red, sin costo).

Verifican lo que exige la guía al componente generativo: solo consultas controladas, cada
hecho respaldado por una consulta real, predicciones separadas y solo del pronóstico, y
respuestas de "sin datos" o "fuera de alcance" cuando corresponde.
"""

import copy
import json
from dataclasses import dataclass, field
from datetime import date

import pytest

from backend.app.asistente import herramientas, motor
from backend.app.asistente.herramientas import Contexto, ErrorHerramienta
from backend.app.seguridad import Usuario

USUARIO = Usuario(usuario="demo", nombre="Demo", rol="analista")
CTX = Contexto(
    fecha_desde=date(2013, 1, 1),
    fecha_hasta=date(2016, 6, 2),
    ultima_fecha_real=date(2016, 5, 31),
    ultima_carga=None,
    lineas_simuladas=583,
    territorios=["Southeast", "Far West"],
    estados=["California"],
    categorias=["Novelty Shop"],
    grupos=["Mugs", "Toys"],
)


# ---------------------------------------------------------------- cliente simulado


@dataclass
class Bloque:
    type: str
    text: str = ""
    id: str = ""
    name: str = ""
    input: dict | None = None


@dataclass
class Uso:
    input_tokens: int = 1000
    output_tokens: int = 200
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0


@dataclass
class Mensaje:
    content: list
    stop_reason: str
    usage: Uso = field(default_factory=Uso)
    _request_id: str = "req_prueba"


class ClienteSimulado:
    """Imita client.messages.create: devuelve respuestas guionadas y guarda cada solicitud."""

    def __init__(self, *respuestas: Mensaje):
        self.respuestas = list(respuestas)
        self.solicitudes: list[dict] = []
        self.messages = self

    def create(self, **kwargs):
        self.solicitudes.append(copy.deepcopy({k: v for k, v in kwargs.items()}))
        return self.respuestas.pop(0)


def herramienta(nombre: str, entrada: dict, id_: str = "t1") -> Mensaje:
    return Mensaje([Bloque("tool_use", id=id_, name=nombre, input=entrada)], "tool_use")


def final(**datos) -> Mensaje:
    base = {
        "tipo": "respuesta",
        "resumen": "",
        "hechos": [],
        "predicciones": [],
        "interpretaciones": [],
        "sugerencias": [],
    }
    return Mensaje([Bloque("text", text=json.dumps({**base, **datos}))], "end_turn")


@pytest.fixture
def resultados_falsos(monkeypatch):
    """Las herramientas no van a la base: devuelven un resultado fijo o el error pedido."""

    def falso(nombre, entrada, ctx, usuario):
        if entrada.get("territorio") == "Marte":
            raise ErrorHerramienta("El territorio 'Marte' no existe.")
        return {"indicadores": {"ventas_netas": 53991490.45}}

    monkeypatch.setattr(motor, "ejecutar", falso)


def responder(cliente, pregunta="¿Cuánto vendimos en 2015?"):
    return motor.Asistente(cliente).responder(pregunta, [], CTX, USUARIO)


# ---------------------------------------------------------------- flujo


def test_flujo_normal_cita_la_consulta_y_calcula_el_costo(resultados_falsos):
    cliente = ClienteSimulado(
        herramienta("consultar_indicadores", {"desde": "2015-01-01", "hasta": "2015-12-31"}),
        final(
            resumen="En 2015 las ventas netas fueron USD 53,991,490.",
            hechos=[{"texto": "Ventas netas 2015: USD 53,991,490", "consultas": [1]}],
        ),
    )
    r = responder(cliente)

    assert r.tipo == "respuesta" and r.advertencias == []
    assert r.hechos[0].respaldada and r.hechos[0].consultas == [1]
    assert r.consultas[0].herramienta == "consultar_indicadores"
    assert "2015-01-01" in r.consultas[0].descripcion
    # El resultado de la herramienta volvió al modelo con su número de consulta
    resultado = cliente.solicitudes[1]["messages"][-1]["content"][0]
    assert resultado["type"] == "tool_result" and json.loads(resultado["content"])["consulta"] == 1
    # 2 llamadas x (1000 de entrada, 200 de salida) a USD 0.10 / 0.50 por millón
    assert (r.tokens_entrada, r.tokens_salida) == (2000, 400)
    assert r.costo_usd == pytest.approx((2000 * 0.10 + 400 * 0.50) / 1e6)


def test_la_solicitud_usa_haiku_esfuerzo_bajo_formato_y_ningun_parametro_de_muestreo(
    resultados_falsos,
):
    cliente = ClienteSimulado(final(tipo="fuera_de_alcance", resumen="Solo ventas de WWI."))
    responder(cliente, "¿Qué clima hará mañana?")
    s = cliente.solicitudes[0]
    assert s["model"] == "claude-haiku-5-5"
    assert s["output_config"]["effort"] == "low"
    assert s["output_config"]["format"]["type"] == "json_schema"
    assert {"temperature", "top_p", "top_k"}.isdisjoint(s)  # la API 2026-10-21 los rechaza
    assert [t["name"] for t in s["tools"]] == [d["name"] for d in herramientas.DEFINICIONES]
    # La pregunta va con el contexto de los datos
    assert "<contexto_de_datos>" in s["messages"][-1]["content"]


def test_hecho_que_cita_una_consulta_inexistente_queda_sin_respaldo(resultados_falsos):
    cliente = ClienteSimulado(
        herramienta("consultar_indicadores", {"desde": "2015-01-01", "hasta": "2015-12-31"}),
        final(hechos=[{"texto": "Algo", "consultas": [7]}]),
    )
    r = responder(cliente)
    assert not r.hechos[0].respaldada
    assert "sin una consulta válida" in r.advertencias[0]


def test_cifras_sin_consultar_se_le_pide_consultar_una_vez(resultados_falsos):
    cliente = ClienteSimulado(
        final(hechos=[{"texto": "Vendimos USD 1,000,000", "consultas": []}]),  # inventado
        herramienta("consultar_indicadores", {"desde": "2015-01-01", "hasta": "2015-12-31"}),
        final(hechos=[{"texto": "Ventas netas 2015: USD 53,991,490", "consultas": [1]}]),
    )
    r = responder(cliente)
    assert motor.RECORDATORIO in cliente.solicitudes[1]["messages"][-1]["content"]
    assert len(cliente.solicitudes) == 3 and r.hechos[0].respaldada


def test_parametros_invalidos_vuelven_como_error_y_el_modelo_puede_decir_sin_datos(
    resultados_falsos,
):
    cliente = ClienteSimulado(
        herramienta(
            "consultar_indicadores",
            {"desde": "2016-01-01", "hasta": "2016-05-31", "territorio": "Marte"},
        ),
        final(tipo="sin_datos", resumen="No existe el territorio Marte."),
    )
    r = responder(cliente)
    resultado = cliente.solicitudes[1]["messages"][-1]["content"][0]
    assert resultado["is_error"] is True and "Marte" in resultado["content"]
    assert r.tipo == "sin_datos" and r.consultas[0].error


def test_una_prediccion_solo_esta_respaldada_si_viene_del_pronostico(resultados_falsos):
    cliente = ClienteSimulado(
        herramienta("consultar_indicadores", {"desde": "2015-01-01", "hasta": "2015-12-31"}, "a"),
        herramienta("consultar_pronostico", {}, "b"),
        final(
            predicciones=[
                {"texto": "Junio crecerá (de los indicadores)", "consultas": [1]},
                {"texto": "Mugs venderá USD 19,733 la próxima semana", "consultas": [2]},
            ]
        ),
    )
    r = responder(cliente, "¿Cuánto venderemos?")
    assert [p.respaldada for p in r.predicciones] == [False, True]


def test_rechazo_del_modelo_responde_fuera_de_alcance(resultados_falsos):
    r = responder(ClienteSimulado(Mensaje([], "refusal")), "Algo indebido")
    assert r.tipo == "fuera_de_alcance"


def test_un_ciclo_sin_fin_de_herramientas_se_corta(resultados_falsos):
    pedido = herramienta("consultar_indicadores", {"desde": "2015-01-01", "hasta": "2015-12-31"})
    cliente = ClienteSimulado(*[copy.deepcopy(pedido) for _ in range(motor.MAX_LLAMADAS)])
    r = responder(cliente)
    assert r.tipo == "error" and len(cliente.solicitudes) == motor.MAX_LLAMADAS


def test_json_invalido_no_rompe(resultados_falsos):
    r = responder(ClienteSimulado(Mensaje([Bloque("text", text="no es json")], "end_turn")))
    assert r.tipo == "error"


def test_el_historial_va_antes_de_la_pregunta(resultados_falsos):
    cliente = ClienteSimulado(final(tipo="aclaracion", resumen="¿Qué período?"))
    motor.Asistente(cliente).responder(
        "¿Y el anterior?",
        [("user", "¿Ventas de 2015?"), ("assistant", "USD 53,991,490.")],
        CTX,
        USUARIO,
    )
    roles = [m["role"] for m in cliente.solicitudes[0]["messages"]]
    assert roles == ["user", "assistant", "user"]


# ---------------------------------------------------------------- herramientas (sin base)


def test_herramienta_inexistente_y_dimension_de_clientes_se_rechazan():
    with pytest.raises(ErrorHerramienta, match="no existe"):
        herramientas.ejecutar("borrar_todo", {}, CTX, USUARIO)
    with pytest.raises(ErrorHerramienta, match="dimension"):
        herramientas.ejecutar(
            "consultar_ranking",
            {"desde": "2016-01-01", "hasta": "2016-05-31", "dimension": "cliente"},
            CTX,
            USUARIO,
        )


def test_valores_de_filtro_inexistentes_y_periodos_sin_datos():
    with pytest.raises(ErrorHerramienta, match="Valores válidos: Southeast"):
        herramientas.ejecutar(
            "consultar_indicadores",
            {"desde": "2016-01-01", "hasta": "2016-05-31", "territorio": "Marte"},
            CTX,
            USUARIO,
        )
    # Período fuera del rango: responde "sin datos" sin ir a la base
    r = herramientas.ejecutar(
        "consultar_indicadores", {"desde": "2010-01-01", "hasta": "2010-12-31"}, CTX, USUARIO
    )
    assert "No hay ventas en ese período" in r["sin_datos"]


def test_las_definiciones_coinciden_con_la_validacion():
    """El esquema que ve el modelo y el que valida el servidor no pueden divergir."""
    for d in herramientas.DEFINICIONES:
        modelo, _ = herramientas._EJECUTORES[d["name"]]
        assert set(d["input_schema"]["properties"]) == set(modelo.model_fields), d["name"]
        assert d["input_schema"]["additionalProperties"] is False


# ---------------------------------------------------------------- dialecto compatible con OpenAI
# (Groq, Ollama): las herramientas y el JSON van en llamadas distintas.

from types import SimpleNamespace as N  # noqa: E402


def _oa(contenido="", llamadas=(), fin="stop", entrada=300, salida=40):
    tool_calls = [
        N(id=f"c{i}", function=N(name=nombre, arguments=args))
        for i, (nombre, args) in enumerate(llamadas)
    ] or None
    return N(
        choices=[N(message=N(content=contenido, tool_calls=tool_calls), finish_reason=fin)],
        usage=N(prompt_tokens=entrada, completion_tokens=salida),
        id="chatcmpl-prueba",
    )


class ClienteOpenAISimulado:
    def __init__(self, *respuestas):
        self.respuestas = list(respuestas)
        self.solicitudes: list[dict] = []
        self.chat = N(completions=self)

    def create(self, **kwargs):
        self.solicitudes.append(copy.deepcopy(kwargs))
        return self.respuestas.pop(0)


def responder_oa(cliente, pregunta="¿Cuánto vendimos en 2015?"):
    asistente = motor.Asistente(cliente, modelo="openai/gpt-oss-120b", proveedor="openai")
    return asistente.responder(pregunta, [], CTX, USUARIO)


FINAL_OA = json.dumps(
    {
        "tipo": "respuesta",
        "resumen": "En 2015 las ventas netas fueron USD 53,991,490.",
        "hechos": [{"texto": "Ventas netas 2015: USD 53,991,490", "consultas": [1]}],
        "predicciones": [],
        "interpretaciones": [],
        "sugerencias": [],
    }
)


def test_openai_herramientas_y_json_nunca_van_juntos_y_el_costo_es_cero(resultados_falsos):
    cliente = ClienteOpenAISimulado(
        _oa(
            llamadas=[("consultar_indicadores", '{"desde":"2015-01-01","hasta":"2015-12-31"}')],
            fin="tool_calls",
        ),
        _oa(contenido=f"```json\n{FINAL_OA}\n```"),  # el JSON llega dentro de un bloque de código
    )
    r = responder_oa(cliente)

    assert r.tipo == "respuesta" and r.hechos[0].respaldada and r.costo_usd == 0
    for s in cliente.solicitudes:
        assert not ("tools" in s and "response_format" in s)  # Groq los rechaza juntos (400)
        assert s["reasoning_effort"] == "low"
    # La respuesta final se pide con la herramienta "responder"; el resultado vuelve como "tool"
    assert motor.RESPONDER in cliente.solicitudes[0]["messages"][0]["content"]
    assert motor.RESPONDER in [t["function"]["name"] for t in cliente.solicitudes[0]["tools"]]
    herramienta_msg = cliente.solicitudes[1]["messages"][-1]
    assert (
        herramienta_msg["role"] == "tool"
        and json.loads(herramienta_msg["content"])["consulta"] == 1
    )


def test_openai_si_el_texto_no_es_json_pide_el_formato_sin_herramientas(resultados_falsos):
    cliente = ClienteOpenAISimulado(
        _oa(contenido="Las ventas fueron altas."),  # texto libre en vez de JSON
        _oa(contenido=json.dumps({**json.loads(FINAL_OA), "tipo": "sin_datos", "hechos": []})),
    )
    r = responder_oa(cliente)
    final = cliente.solicitudes[1]
    assert "tools" not in final and final["response_format"]["type"] == "json_schema"
    assert final["messages"][-1]["content"] == motor.PEDIDO_FORMATO
    assert r.tipo == "sin_datos"


def test_openai_argumentos_invalidos_vuelven_como_error(resultados_falsos):
    cliente = ClienteOpenAISimulado(
        _oa(llamadas=[("consultar_indicadores", "{no es json")], fin="tool_calls"),
        _oa(contenido=json.dumps({**json.loads(FINAL_OA), "tipo": "sin_datos", "hechos": []})),
    )
    r = responder_oa(cliente)
    assert r.consultas[0].error and "JSON" in r.consultas[0].error
    assert cliente.solicitudes[1]["messages"][-1]["content"].startswith("ERROR:")


def test_leer_json_tolera_texto_alrededor_y_rechaza_lo_que_no_es_respuesta():
    assert (
        motor.leer_json('Aquí va: {"tipo": "respuesta", "resumen": "x"} listo')["tipo"]
        == "respuesta"
    )
    assert motor.leer_json("sin json") is None
    assert motor.leer_json('{"otra": "cosa"}') is None


def test_openai_la_respuesta_final_llega_por_la_herramienta_responder(resultados_falsos):
    cliente = ClienteOpenAISimulado(
        _oa(
            llamadas=[("consultar_indicadores", '{"desde":"2015-01-01","hasta":"2015-12-31"}')],
            fin="tool_calls",
        ),
        _oa(llamadas=[(motor.RESPONDER, FINAL_OA)], fin="tool_calls"),
    )
    r = responder_oa(cliente)
    assert r.tipo == "respuesta" and r.hechos[0].respaldada
    assert len(cliente.solicitudes) == 2  # sin llamada extra de formato
    assert [c.herramienta for c in r.consultas] == [
        "consultar_indicadores"
    ]  # responder no es consulta


def test_openai_recupera_la_respuesta_si_el_modelo_llama_a_una_herramienta_inexistente(
    resultados_falsos,
):
    import httpx2
    import openai

    generado = json.dumps({"name": "json", "arguments": json.loads(FINAL_OA)})

    class ClienteConFallo(ClienteOpenAISimulado):
        def create(self, **kwargs):
            if len(self.solicitudes) == 1:  # la segunda llamada falla como en Groq
                self.solicitudes.append(kwargs)
                raise openai.BadRequestError(
                    "tool_use_failed",
                    response=httpx2.Response(
                        400, request=httpx2.Request("POST", "https://api.groq.com")
                    ),
                    body={"error": {"code": "tool_use_failed", "failed_generation": generado}},
                )
            return super().create(**kwargs)

    cliente = ClienteConFallo(
        _oa(
            llamadas=[("consultar_indicadores", '{"desde":"2015-01-01","hasta":"2015-12-31"}')],
            fin="tool_calls",
        )
    )
    r = responder_oa(cliente)
    assert r.tipo == "respuesta" and r.hechos[0].respaldada
