"""Monitoreo de la operación (Fase 7, D-27): ETL, calidad, cuarentena, modelo y notificaciones.

Todo se lee de vistas aprobadas del esquema api (database/data-warehouse/09 y anteriores): la
API no ve la auditoría ni los registros rechazados, solo conteos y estados.
"""

from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter
from pydantic import BaseModel

from ..db import lectura
from ..seguridad import UsuarioActual

router = APIRouter(prefix="/monitoreo", tags=["Operación"])

EJECUCIONES = 15
EVALUACIONES = 10


class EjecucionEtl(BaseModel):
    ejecucion_id: int
    proceso: str
    disparador: str
    modo: str
    inicio: datetime
    fin: datetime | None
    segundos: float | None
    estado: str
    leidas: int
    nuevas: int
    actualizadas: int
    rechazadas: int
    sin_cambios: int
    reconciliado: bool | None
    error: str | None


class ReglaCalidad(BaseModel):
    tabla: str
    regla: str
    dimension: str | None
    descripcion: str | None
    accion: str
    evaluadas: int
    fallaron: int


class DimensionCalidad(BaseModel):
    dimension: str
    reglas: int
    evaluadas: int
    fallaron: int
    cumplimiento_pct: float | None
    """Porcentaje de filas evaluadas que cumplen; None si no se evaluó ninguna."""


class Cuarentena(BaseModel):
    tabla: str
    regla: str
    pendientes: int
    resueltos: int
    ultimo_rechazo: datetime | None


class ModeloVigente(BaseModel):
    version: str
    algoritmo: str
    entrenado_en: datetime
    datos_hasta: date
    commit_codigo: str | None
    wape_prueba: float | None
    wape_prueba_linea_base: float | None
    pronostico_origen: date | None
    pronostico_generado_en: datetime | None


class EvaluacionAlertas(BaseModel):
    evaluacion_id: int
    disparador: str
    inicio: datetime
    fin: datetime | None
    estado: str
    reglas_evaluadas: int
    alertas_nuevas: int
    correos_enviados: int
    error: str | None


class Notificaciones(BaseModel):
    evaluaciones: list[EvaluacionAlertas]
    alertas_por_estado: dict[str, int]
    correos_enviados: int
    intentos_fallidos: int
    alertas_sin_entregar: int
    """Alertas no descartadas cuyo correo todavía no se pudo enviar."""


class RespuestaMonitoreo(BaseModel):
    etl: list[EjecucionEtl]
    calidad_ejecucion_id: int | None
    calidad: list[ReglaCalidad]
    dimensiones: list[DimensionCalidad]
    cuarentena: list[Cuarentena]
    modelo: ModeloVigente | None
    notificaciones: Notificaciones


def _dimensiones(reglas: list[ReglaCalidad]) -> list[DimensionCalidad]:
    grupos: dict[str, list[ReglaCalidad]] = {}
    for r in reglas:
        grupos.setdefault(r.dimension or "Sin dimensión", []).append(r)
    resultado = []
    for nombre, rs in sorted(grupos.items()):
        evaluadas = sum(r.evaluadas for r in rs)
        fallaron = sum(r.fallaron for r in rs)
        resultado.append(
            DimensionCalidad(
                dimension=nombre,
                reglas=len(rs),
                evaluadas=evaluadas,
                fallaron=fallaron,
                cumplimiento_pct=100 * (1 - fallaron / evaluadas) if evaluadas else None,
            )
        )
    return resultado


def _modelo(conn) -> ModeloVigente | None:
    m = conn.execute(
        "SELECT version, algoritmo, entrenado_en, datos_hasta, commit_codigo, metricas "
        "FROM api.modelo_pronostico"
    ).fetchone()
    if m is None:
        return None
    p = conn.execute(
        "SELECT max(origen) AS origen, max(generado_en) AS generado_en FROM api.pronostico"
    ).fetchone()
    prueba = (m["metricas"] or {}).get("prueba", {})
    base = (m["metricas"] or {}).get("validacion", {}).get("mejor_linea_base")
    return ModeloVigente(
        version=m["version"],
        algoritmo=m["algoritmo"],
        entrenado_en=m["entrenado_en"],
        datos_hasta=m["datos_hasta"],
        commit_codigo=m["commit_codigo"],
        wape_prueba=prueba.get("modelo", {}).get("total", {}).get("wape"),
        wape_prueba_linea_base=prueba.get("lineas_base", {})
        .get(base, {})
        .get("total", {})
        .get("wape"),
        pronostico_origen=p["origen"],
        pronostico_generado_en=p["generado_en"],
    )


@router.get("", response_model=RespuestaMonitoreo, summary="Estado de la operación")
def monitoreo(usuario: UsuarioActual) -> RespuestaMonitoreo:
    """Últimas ejecuciones del ETL, calidad de la última ejecución evaluada por dimensión,
    cuarentena pendiente, modelo vigente y estado de las notificaciones."""
    with lectura() as conn:
        etl = conn.execute(
            "SELECT * FROM api.monitoreo_etl ORDER BY ejecucion_id DESC LIMIT %s", (EJECUCIONES,)
        ).fetchall()
        calidad = conn.execute(
            "SELECT * FROM api.monitoreo_calidad ORDER BY fallaron DESC, tabla, regla"
        ).fetchall()
        cuarentena = conn.execute(
            "SELECT * FROM api.monitoreo_cuarentena ORDER BY pendientes DESC, tabla, regla"
        ).fetchall()
        modelo = _modelo(conn)
        evaluaciones = conn.execute(
            "SELECT * FROM api.alertas_evaluaciones ORDER BY evaluacion_id DESC LIMIT %s",
            (EVALUACIONES,),
        ).fetchall()
        por_estado = conn.execute(
            "SELECT estado, count(*) AS n FROM api.alertas GROUP BY estado"
        ).fetchall()
        envios = conn.execute(
            "SELECT count(*) FILTER (WHERE resultado = 'enviado') AS enviados, "
            "count(*) FILTER (WHERE resultado = 'fallido') AS fallidos FROM api.alertas_envios"
        ).fetchone()
        sin_entregar = conn.execute(
            "SELECT count(*) AS n FROM api.alertas "
            "WHERE NOT correo_enviado AND estado <> 'descartada'"
        ).fetchone()

    reglas = [ReglaCalidad(**{k: f[k] for k in ReglaCalidad.model_fields}) for f in calidad]
    return RespuestaMonitoreo(
        etl=[EjecucionEtl(**f) for f in etl],
        calidad_ejecucion_id=calidad[0]["ejecucion_id"] if calidad else None,
        calidad=reglas,
        dimensiones=_dimensiones(reglas),
        cuarentena=[Cuarentena(**f) for f in cuarentena],
        modelo=modelo,
        notificaciones=Notificaciones(
            evaluaciones=[EvaluacionAlertas(**e) for e in evaluaciones],
            alertas_por_estado={f["estado"]: f["n"] for f in por_estado},
            correos_enviados=envios["enviados"],
            intentos_fallidos=envios["fallidos"],
            alertas_sin_entregar=sin_entregar["n"],
        ),
    )
