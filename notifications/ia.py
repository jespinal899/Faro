"""Explicación y acción recomendada de una alerta, GENERADAS POR IA (Groq, plan gratuito).

Recibe solo los datos de la alerta (agregados de una empresa ficticia, sin datos personales)
y no puede consultar nada más: no hay herramientas. Si la IA no está disponible, la alerta se
registra y se envía igual, sin esta sección.
"""

from __future__ import annotations

import json
import logging
import os

log = logging.getLogger("faro.alertas")

MODELO = "openai/gpt-oss-120b"
INSTRUCCIONES = (
    "Eres analista de ventas de Wide World Importers (WWI), un mayorista ficticio. Recibes una "
    "alerta ya calculada por el sistema. En español y en una o dos oraciones: explica qué "
    "significa y qué podría causarla (como hipótesis), y propone UNA acción concreta. Usa solo "
    "los datos recibidos; no inventes cifras. Si la alerta es una predicción, dilo."
)
ESQUEMA = {
    "type": "object",
    "properties": {
        "explicacion": {"type": "string"},
        "accion_recomendada": {"type": "string"},
    },
    "required": ["explicacion", "accion_recomendada"],
    "additionalProperties": False,
}


def explicar(alerta: dict, cliente=None) -> tuple[str, str, str] | None:
    """(explicación, acción, modelo) o None si no hay IA disponible o falla."""
    if cliente is None:
        clave = os.getenv("GROQ_API_KEY")
        if not clave:
            return None
        import openai

        cliente = openai.OpenAI(
            base_url="https://api.groq.com/openai/v1", api_key=clave, timeout=45.0, max_retries=3
        )
    datos = {
        k: alerta[k]
        for k in (
            "regla",
            "severidad",
            "origen",
            "indicador",
            "entidad",
            "valor_observado",
            "umbral",
            "referencia",
            "periodo_desde",
            "periodo_hasta",
            "mensaje",
            "detalle",
            "incluye_simulados",
        )
        if k in alerta
    }
    try:
        r = cliente.chat.completions.create(
            model=MODELO,
            messages=[
                {"role": "system", "content": INSTRUCCIONES},
                {"role": "user", "content": json.dumps(datos, ensure_ascii=False, default=str)},
            ],
            max_completion_tokens=800,
            reasoning_effort="low",
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "explicacion", "strict": True, "schema": ESQUEMA},
            },
        )
        resultado = json.loads(r.choices[0].message.content or "{}")
        return resultado["explicacion"], resultado["accion_recomendada"], MODELO
    except Exception as e:  # la alerta no depende de la IA
        log.warning("No se generó la explicación con IA: %s", type(e).__name__)
        return None
