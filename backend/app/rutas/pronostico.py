"""Pronóstico de ventas (Machine Learning): predicciones del modelo vigente, su calidad y su
seguimiento contra lo vendido.

La API no calcula nada: el modelo corre aparte (workflow "ML - Pronóstico") y aquí solo se
expone lo que registró, leído de vistas aprobadas. Son PREDICCIONES, no datos históricos.
Diseño: documentation/modelos/modelo-ml.md.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel

from ..db import lectura
from ..seguridad import UsuarioActual

router = APIRouter(prefix="/pronostico", tags=["Pronóstico (Machine Learning)"])

# Copia de machine_learning/variables.py::LINEAS_BASE (la API en Vercel no incluye ese paquete);
# una prueba verifica que ambas coincidan.
LINEAS_BASE = {
    "ingenuo": "la venta de la última semana conocida",
    "media_movil_4": "el promedio de las últimas 4 semanas",
    "media_movil_13": "el promedio de las últimas 13 semanas (un trimestre)",
    "estacional": "la venta de la misma semana del año anterior",
}


# ------------------------------------------------------------------ modelos


class PuntoHistoria(BaseModel):
    semana: date
    venta_neta: float
    incluye_simulados: bool


class PuntoPronostico(BaseModel):
    semana: date
    horizonte: int
    venta_neta: float
    inferior: float
    superior: float


class PuntoSeguimiento(BaseModel):
    """Un pronóstico ya vencido frente a lo que realmente se vendió esa semana."""

    origen: date
    semana: date
    horizonte: int
    pronostico: float
    inferior: float
    superior: float
    real: float
    real_incluye_simulados: bool


class SerieGrupo(BaseModel):
    grupo: str
    historia: list[PuntoHistoria]
    pronostico: list[PuntoPronostico]
    seguimiento: list[PuntoSeguimiento]
    wape_prueba: float | None
    wape_prueba_linea_base: float | None


class Excluido(BaseModel):
    grupo: str
    motivo: str


class CalidadHorizonte(BaseModel):
    horizonte: int
    wape_modelo: float
    wape_linea_base: float
    cobertura_pct: float


class Calidad(BaseModel):
    metrica: Literal["wape"] = "wape"
    linea_base: str
    linea_base_descripcion: str
    wape_validacion_modelo: float
    wape_validacion_linea_base: float
    wape_prueba_modelo: float
    wape_prueba_linea_base: float
    mejora_prueba_pct: float
    cobertura_objetivo_pct: float
    cobertura_prueba_pct: float
    por_horizonte: list[CalidadHorizonte]


class Modelo(BaseModel):
    version: str
    algoritmo: str
    entrenado_en: datetime
    datos_desde: date
    datos_hasta: date
    prueba_desde: date
    commit_codigo: str | None
    calidad: Calidad


class RespuestaPronostico(BaseModel):
    disponible: bool
    """False si todavía no hay un modelo vigente con pronóstico."""
    modelo: Modelo | None
    origen: date | None
    """Última semana completa que conocía el modelo al pronosticar."""
    generado_en: datetime | None
    usa_datos_simulados: bool
    grupos: list[SerieGrupo]
    excluidos: list[Excluido]


class PuntoPrueba(BaseModel):
    semana: date
    origen: date
    real: float
    pronostico: float
    inferior: float
    superior: float
    linea_base: float


# ------------------------------------------------------------------ armado


def _calidad(metricas: dict, intervalo: dict) -> Calidad:
    validacion, prueba = metricas["validacion"], metricas["prueba"]
    base = validacion["mejor_linea_base"]
    modelo_val = min(c["wape"] for c in validacion["candidatos"])
    return Calidad(
        linea_base=base,
        linea_base_descripcion=LINEAS_BASE.get(base, base),
        wape_validacion_modelo=modelo_val,
        wape_validacion_linea_base=validacion["lineas_base"][base],
        wape_prueba_modelo=prueba["modelo"]["total"]["wape"],
        wape_prueba_linea_base=prueba["lineas_base"][base]["total"]["wape"],
        mejora_prueba_pct=prueba["mejora_vs_linea_base_pct"],
        cobertura_objetivo_pct=intervalo["cobertura_objetivo_pct"],
        cobertura_prueba_pct=prueba["cobertura_rango_pct"]["total"],
        por_horizonte=[
            CalidadHorizonte(
                horizonte=int(h),
                wape_modelo=v["wape"],
                wape_linea_base=prueba["lineas_base"][base]["por_horizonte"][h]["wape"],
                cobertura_pct=prueba["cobertura_rango_pct"]["por_horizonte"][h],
            )
            for h, v in sorted(prueba["modelo"]["por_horizonte"].items(), key=lambda x: int(x[0]))
        ],
    )


@router.get("", response_model=RespuestaPronostico, summary="Pronóstico vigente por grupo")
def pronostico(
    usuario: UsuarioActual,
    semanas_historia: Annotated[int, Query(ge=4, le=156)] = 26,
) -> RespuestaPronostico:
    """Pronóstico de las 4 semanas siguientes por grupo de producto, con su rango probable del
    80 %, las últimas semanas reales como contexto, el seguimiento de pronósticos pasados y la
    calidad del modelo medida en semanas que no vio. Los filtros del análisis histórico no aplican.
    """
    with lectura() as conn:
        modelo = conn.execute("SELECT * FROM api.modelo_pronostico").fetchone()
        filas = conn.execute("SELECT * FROM api.pronostico ORDER BY grupo, semana").fetchall()
        if modelo is None or not filas:
            return RespuestaPronostico(
                disponible=False,
                modelo=None,
                origen=None,
                generado_en=None,
                usa_datos_simulados=False,
                grupos=[],
                excluidos=[],
            )
        origen = filas[0]["origen"]
        grupos = sorted({f["grupo"] for f in filas})
        desde = origen - timedelta(weeks=semanas_historia - 1)
        historia = conn.execute(
            "SELECT grupo, semana, venta_neta, venta_neta_simulada > 0 AS incluye_simulados "
            "FROM api.ventas_semanales "
            "WHERE es_completa AND semana >= %s AND grupo = ANY(%s) ORDER BY grupo, semana",
            (desde, grupos),
        ).fetchall()
        seguimiento = conn.execute(
            "SELECT * FROM api.pronostico_vs_real WHERE grupo = ANY(%s) AND semana >= %s "
            "ORDER BY grupo, semana, horizonte",
            (grupos, desde),
        ).fetchall()

    por_grupo = modelo["metricas"]["prueba"].get("por_grupo", {})
    series = [
        SerieGrupo(
            grupo=g,
            historia=[
                PuntoHistoria(**{k: h[k] for k in PuntoHistoria.model_fields})
                for h in historia
                if h["grupo"] == g
            ],
            pronostico=[
                PuntoPronostico(
                    semana=f["semana"],
                    horizonte=f["horizonte"],
                    venta_neta=f["venta_neta_pronosticada"],
                    inferior=f["inferior"],
                    superior=f["superior"],
                )
                for f in filas
                if f["grupo"] == g
            ],
            seguimiento=[
                PuntoSeguimiento(
                    origen=s["origen"],
                    semana=s["semana"],
                    horizonte=s["horizonte"],
                    pronostico=s["venta_neta_pronosticada"],
                    inferior=s["inferior"],
                    superior=s["superior"],
                    real=s["venta_neta_real"],
                    real_incluye_simulados=s["real_incluye_simulados"],
                )
                for s in seguimiento
                if s["grupo"] == g
            ],
            wape_prueba=por_grupo.get(g, {}).get("modelo_wape"),
            wape_prueba_linea_base=por_grupo.get(g, {}).get("linea_base_wape"),
        )
        for g in grupos
    ]
    return RespuestaPronostico(
        disponible=True,
        modelo=Modelo(
            **{k: modelo[k] for k in Modelo.model_fields if k != "calidad"},
            calidad=_calidad(modelo["metricas"], modelo["intervalo"]),
        ),
        origen=origen,
        generado_en=max(f["generado_en"] for f in filas),
        usa_datos_simulados=any(f["usa_datos_simulados"] for f in filas),
        grupos=series,
        excluidos=[
            Excluido(grupo=g, motivo=m) for g, m in modelo["grupos"].get("excluidos", {}).items()
        ],
    )


@router.get(
    "/evaluacion", response_model=list[PuntoPrueba], summary="Evaluación en semanas de prueba"
)
def evaluacion(
    usuario: UsuarioActual,
    grupo: Annotated[str, Query(min_length=1, max_length=80)],
    horizonte: Annotated[int, Query(ge=1, le=4)] = 1,
) -> list[PuntoPrueba]:
    """Lo que el modelo vigente y la línea base pronosticaron para las semanas de prueba
    (que el modelo no vio al entrenarse), frente a lo que realmente se vendió."""
    with lectura() as conn:
        filas = conn.execute(
            "SELECT semana, origen, real, pronostico, inferior, superior, linea_base "
            "FROM api.prediccion_prueba WHERE grupo = %s AND horizonte = %s ORDER BY semana",
            (grupo, horizonte),
        ).fetchall()
    return [PuntoPrueba(**f) for f in filas]
