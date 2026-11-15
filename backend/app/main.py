"""API de Faro (FastAPI).

Desarrollo local:
    uv run uvicorn backend.app.main:app --reload --port 8000
    Documentación interactiva: http://localhost:8000/api/docs

En Vercel la misma aplicación se publica como función de Python bajo /api.
El navegador nunca se conecta a la base de datos: todo pasa por esta API.
"""

from __future__ import annotations

import logging

import psycopg
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .db import lectura
from .rutas import auth, datos

log = logging.getLogger("faro.api")

app = FastAPI(
    title="Faro API",
    version="1.0.0",
    description=(
        "API del dashboard de Faro. Todos los indicadores provienen del Data Warehouse "
        "(vistas aprobadas del esquema `api`). Requiere iniciar sesión."
    ),
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
)


@app.middleware("http")
async def cabeceras_de_seguridad(request: Request, llamar_siguiente):
    respuesta = await llamar_siguiente(request)
    respuesta.headers["X-Content-Type-Options"] = "nosniff"
    respuesta.headers["X-Frame-Options"] = "DENY"
    respuesta.headers["Referrer-Policy"] = "same-origin"
    if request.url.path.startswith("/api/") and not request.url.path.startswith("/api/docs"):
        respuesta.headers["Cache-Control"] = "no-store"
    return respuesta


@app.exception_handler(psycopg.errors.QueryCanceled)
async def consulta_demasiado_lenta(request: Request, error: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=504,
        content={"detail": "La consulta tardó demasiado. Reduce el rango de fechas o los filtros."},
    )


@app.exception_handler(psycopg.OperationalError)
async def base_no_disponible(request: Request, error: Exception) -> JSONResponse:
    # Sin detalles internos en la respuesta (podrían revelar la configuración)
    log.error("Base de datos no disponible: %s", type(error).__name__)
    return JSONResponse(
        status_code=503,
        content={"detail": "La base de datos no está disponible. Reintenta en unos segundos."},
    )


@app.get("/api/salud", tags=["Operación"], summary="Estado de la API y de la base de datos")
def salud() -> dict[str, str]:
    """Pública (sin sesión): sirve para monitorear que el servicio responde."""
    with lectura() as conn:
        conn.execute("SELECT 1")
    return {"api": "ok", "base_de_datos": "ok"}


app.include_router(auth.router, prefix="/api")
app.include_router(datos.router, prefix="/api")
