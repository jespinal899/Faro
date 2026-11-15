"""Asistente analítico de IA: preguntas en lenguaje natural sobre las ventas (pregunta P11).

Arquitectura segura que pide la guía: usuario -> API (sesión y límite por usuario) ->
consultas controladas del catálogo (vistas aprobadas, solo lectura) -> modelo generativo ->
respuesta con secciones separadas y las consultas que la respaldan. Decisión D-25.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime
from functools import lru_cache
from typing import Literal

import anthropic
import openai
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from ..asistente.herramientas import Contexto
from ..asistente.motor import Asistente, Respuesta
from ..config import config
from ..db import escritura
from ..seguridad import UsuarioActual

log = logging.getLogger("faro.asistente")
router = APIRouter(prefix="/asistente", tags=["Asistente de IA"])

EJEMPLOS = [
    "¿Cuáles fueron las ventas del último trimestre completo?",
    "¿Qué categorías de cliente crecieron más en 2015?",
    "Resume los principales cambios de mayo de 2016 frente al año anterior.",
    "¿Qué territorios presentan una disminución relevante en 2016?",
    "¿Cuánto venderemos de Packaging Materials las próximas semanas?",
    "¿Qué análisis adicional convendría realizar?",
]


# ------------------------------------------------------------------ modelos


class Turno(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rol: Literal["usuario", "asistente"]
    texto: str = Field(min_length=1, max_length=2000)


class Pregunta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pregunta: str = Field(min_length=3, max_length=500)
    historial: list[Turno] = Field(default_factory=list, max_length=6)


class AfirmacionSalida(BaseModel):
    texto: str
    consultas: list[int]
    respaldada: bool


class ConsultaSalida(BaseModel):
    numero: int
    herramienta: str
    descripcion: str
    parametros: dict
    resultado: dict | None
    error: str | None


class RespuestaAsistente(BaseModel):
    tipo: Literal["respuesta", "sin_datos", "fuera_de_alcance", "aclaracion", "error"]
    resumen: str
    hechos: list[AfirmacionSalida]
    predicciones: list[AfirmacionSalida]
    interpretaciones: list[str]
    sugerencias: list[str]
    consultas: list[ConsultaSalida]
    datos_al: date
    ultima_carga: datetime | None
    incluye_simulados: bool
    """Alguna consulta incluyó ventas simuladas."""
    generado_por: str
    tokens_entrada: int
    tokens_salida: int
    costo_usd: float
    duracion_ms: int
    advertencias: list[str]


class InfoAsistente(BaseModel):
    disponible: bool
    proveedor: str
    modelo: str
    limite_hora: int
    limite_dia: int
    usadas_hoy: int
    ejemplos: list[str]


# ------------------------------------------------------------------ apoyo


# Proveedores (decisión D-25). "dialecto": cómo habla su API ("openai" = Chat Completions).
PROVEEDORES = {
    "groq": {
        "dialecto": "openai",
        "clave": "GROQ_API_KEY",
        "base_url": "https://api.groq.com/openai/v1",
        "modelo": "openai/gpt-oss-120b",
        "esfuerzo": "low",  # reasoning_effort de gpt-oss: menos tokens (límite por minuto)
    },
    "ollama": {
        "dialecto": "openai",
        "clave": None,  # local, sin clave
        "base_url": None,  # OLLAMA_BASE_URL o http://localhost:11434/v1
        "modelo": "qwen3:8b",
        "esfuerzo": None,
    },
    "anthropic": {
        "dialecto": "anthropic",
        "clave": "ANTHROPIC_API_KEY",
        "base_url": None,
        "modelo": "claude-haiku-5-5",
        "esfuerzo": "low",
    },
}


def _proveedor() -> tuple[str, dict, str]:
    """(nombre, configuración, modelo) del proveedor elegido en la configuración."""
    c = config()  # también carga el .env en desarrollo
    nombre = c.asistente_proveedor if c.asistente_proveedor in PROVEEDORES else "groq"
    p = PROVEEDORES[nombre]
    return nombre, p, c.asistente_modelo or p["modelo"]


@lru_cache
def cliente(nombre: str):
    """Cliente oficial del proveedor; las claves se toman del entorno (nunca del código)."""
    p = PROVEEDORES[nombre]
    if p["dialecto"] == "anthropic":
        return anthropic.Anthropic(timeout=45.0, max_retries=2)
    if nombre == "ollama":
        base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        return openai.OpenAI(base_url=base, api_key="ollama", timeout=180.0, max_retries=0)
    # Groq: si se llega al límite por minuto, el SDK reintenta respetando retry-after
    return openai.OpenAI(
        base_url=p["base_url"], api_key=os.getenv(p["clave"]), timeout=60.0, max_retries=3
    )


def _disponible() -> bool:
    _, p, _ = _proveedor()
    return p["clave"] is None or bool(os.getenv(p["clave"]))


def _usadas(usuario: str) -> tuple[int, int]:
    with escritura() as conn:
        fila = conn.execute(
            "SELECT count(*) FILTER (WHERE creada_en > now() - interval '1 hour') AS hora, "
            "       count(*) AS dia "
            "FROM app.consulta_asistente "
            "WHERE usuario = %s AND creada_en > now() - interval '1 day'",
            (usuario,),
        ).fetchone()
    return fila["hora"], fila["dia"]


def _registrar(usuario: str, pregunta: str, r: Respuesta) -> None:
    herramientas = [{"herramienta": c.herramienta, "parametros": c.parametros} for c in r.consultas]
    with escritura() as conn:
        conn.execute(
            "INSERT INTO app.consulta_asistente (usuario, pregunta, tipo_respuesta, herramientas, "
            " modelo, tokens_entrada, tokens_salida, costo_usd, duracion_ms, advertencias, "
            " id_solicitud) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                usuario,
                pregunta,
                r.tipo,
                json.dumps(herramientas, ensure_ascii=False, default=str),
                r.modelo,
                r.tokens_entrada,
                r.tokens_salida,
                round(r.costo_usd, 6),
                r.duracion_ms,
                json.dumps(r.advertencias, ensure_ascii=False),
                r.id_solicitud,
            ),
        )


ERRORES_IA = (anthropic.APIError, openai.APIError)


def _error_ia(e: Exception) -> HTTPException:
    """Traduce los errores del servicio de IA a mensajes para el usuario (sin detalles internos)."""
    if isinstance(e, anthropic.RateLimitError | openai.RateLimitError):
        return HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "El servicio de IA llegó a su límite por minuto (plan gratuito). "
            "Intenta en unos segundos.",
        )
    if isinstance(e, anthropic.BadRequestError) and "credit balance" in str(e).lower():
        return HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "El servicio de IA no tiene saldo disponible."
        )
    if isinstance(
        e,
        anthropic.AuthenticationError
        | anthropic.PermissionDeniedError
        | openai.AuthenticationError
        | openai.PermissionDeniedError
        | openai.NotFoundError,
    ):
        return HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "El asistente no está bien configurado."
        )
    return HTTPException(
        status.HTTP_502_BAD_GATEWAY, "El servicio de IA no respondió. Intenta de nuevo."
    )


# ------------------------------------------------------------------ rutas


@router.get("/info", response_model=InfoAsistente, summary="Estado y límites del asistente")
def info(usuario: UsuarioActual) -> InfoAsistente:
    c = config()
    _, dia = _usadas(usuario.usuario)
    nombre, _, modelo = _proveedor()
    return InfoAsistente(
        disponible=_disponible(),
        proveedor=nombre,
        modelo=modelo,
        limite_hora=c.asistente_limite_hora,
        limite_dia=c.asistente_limite_dia,
        usadas_hoy=dia,
        ejemplos=EJEMPLOS,
    )


@router.post("", response_model=RespuestaAsistente, summary="Preguntar al asistente")
def preguntar(usuario: UsuarioActual, cuerpo: Pregunta) -> RespuestaAsistente:
    """Responde una pregunta sobre las ventas consultando el DW con herramientas controladas.

    Cada hecho cita las consultas que lo respaldan (incluidas en la respuesta), las
    predicciones van aparte y las interpretaciones se identifican como generadas por IA.
    """
    c = config()
    if not _disponible():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "El asistente de IA no está configurado."
        )
    hora, dia = _usadas(usuario.usuario)
    if hora >= c.asistente_limite_hora or dia >= c.asistente_limite_dia:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Llegaste al límite de preguntas ({c.asistente_limite_hora} por hora, "
            f"{c.asistente_limite_dia} por día). Intenta más tarde.",
        )

    pregunta = " ".join(cuerpo.pregunta.split())  # sin saltos ni espacios repetidos
    historial = [("user" if t.rol == "usuario" else "assistant", t.texto) for t in cuerpo.historial]
    while historial and historial[0][0] != "user":  # la conversación empieza con el usuario
        historial.pop(0)
    ctx = Contexto.cargar(usuario)
    nombre, p, modelo = _proveedor()
    asistente = Asistente(cliente(nombre), modelo, proveedor=p["dialecto"], esfuerzo=p["esfuerzo"])
    try:
        r = asistente.responder(pregunta, historial, ctx, usuario)
    except ERRORES_IA as e:
        log.warning("Error del servicio de IA (%s): %s", nombre, type(e).__name__)
        _registrar(usuario.usuario, pregunta, Respuesta(tipo="error", resumen="", modelo=modelo))
        raise _error_ia(e) from e
    _registrar(usuario.usuario, pregunta, r)

    return RespuestaAsistente(
        tipo=r.tipo,
        resumen=r.resumen,
        hechos=[AfirmacionSalida(**vars(a)) for a in r.hechos],
        predicciones=[AfirmacionSalida(**vars(a)) for a in r.predicciones],
        interpretaciones=r.interpretaciones,
        sugerencias=r.sugerencias,
        consultas=[ConsultaSalida(**vars(x)) for x in r.consultas],
        datos_al=ctx.fecha_hasta,
        ultima_carga=ctx.ultima_carga,
        incluye_simulados=any(
            (x.resultado or {}).get("incluye_ventas_simuladas") for x in r.consultas
        ),
        generado_por=r.modelo,
        tokens_entrada=r.tokens_entrada,
        tokens_salida=r.tokens_salida,
        costo_usd=round(r.costo_usd, 6),
        duracion_ms=r.duracion_ms,
        advertencias=r.advertencias,
    )
