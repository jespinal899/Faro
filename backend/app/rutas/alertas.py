"""Alertas (Fase 7, D-26): resumen para el contador, lista, detalle y cambio de estado.

Las alertas las genera el evaluador (módulo notifications/, rol faro_alertas) al terminar cada
carga. La API solo las muestra y cambia su estado: el rol faro_api puede actualizar únicamente
el estado, la nota, quién y cuándo (no el contenido de la alerta).
Diseño: documentation/arquitectura/alertas.md.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, HTTPException, Path, Query, status
from pydantic import BaseModel, Field, field_validator

from ..db import escritura, lectura
from ..seguridad import UsuarioActual

router = APIRouter(prefix="/alertas", tags=["Alertas"])

Estado = Literal["nueva", "atendida", "descartada", "resuelta"]
IdAlerta = Annotated[int, Path(ge=1, le=2**62)]
MAX_ALERTAS = 200


class ResumenAlertas(BaseModel):
    """Para el contador de la pestaña (se consulta periódicamente)."""

    nuevas: int
    criticas_nuevas: int
    ultima_creada_en: datetime | None


class Alerta(BaseModel):
    alerta_id: int
    creada_en: datetime
    regla: str
    regla_nombre: str
    severidad: Literal["advertencia", "critica"]
    origen: Literal["regla", "modelo"]
    indicador: str
    entidad: str
    valor_observado: float
    """Valor real o, en las alertas del modelo, la predicción."""
    umbral: float
    referencia: float | None
    unidad: str
    periodo_desde: date
    periodo_hasta: date
    detalle: dict[str, Any]
    mensaje: str
    """Descripción calculada por la regla (no la escribe la IA)."""
    explicacion_ia: str | None
    """GENERADA POR IA: se muestra identificada como tal."""
    accion_recomendada_ia: str | None
    """GENERADA POR IA: se muestra identificada como tal."""
    ia_modelo: str | None
    incluye_simulados: bool
    estado: Estado
    estado_actualizado_en: datetime | None
    estado_actualizado_por: str | None
    nota: str | None
    correo_enviado: bool
    intentos_correo: int
    ultimo_intento: datetime | None


class Envio(BaseModel):
    canal: str
    intento: int
    intentado_en: datetime
    resultado: Literal["enviado", "fallido"]
    error: str | None


class DetalleAlerta(Alerta):
    envios: list[Envio]


class CambioEstado(BaseModel):
    estado: Estado
    nota: str | None = Field(default=None, max_length=500)
    """Si no se envía, la nota anterior se conserva; una cadena vacía la borra."""

    @field_validator("nota")
    @classmethod
    def _limpiar(cls, v: str | None) -> str | None:
        return None if v is None else v.strip()


def _detalle(conn, alerta_id: int) -> DetalleAlerta:
    fila = conn.execute("SELECT * FROM api.alertas WHERE alerta_id = %s", (alerta_id,)).fetchone()
    if fila is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "La alerta no existe.")
    envios = conn.execute(
        "SELECT canal, intento, intentado_en, resultado, error FROM api.alertas_envios "
        "WHERE alerta_id = %s ORDER BY intentado_en, intento",
        (alerta_id,),
    ).fetchall()
    return DetalleAlerta(**fila, envios=[Envio(**e) for e in envios])


@router.get("/resumen", response_model=ResumenAlertas, summary="Cuántas alertas nuevas hay")
def resumen(usuario: UsuarioActual) -> ResumenAlertas:
    with lectura() as conn:
        fila = conn.execute(
            "SELECT count(*) FILTER (WHERE estado = 'nueva') AS nuevas, "
            "count(*) FILTER (WHERE estado = 'nueva' AND severidad = 'critica') "
            "AS criticas_nuevas, "
            "max(creada_en) AS ultima_creada_en FROM api.alertas"
        ).fetchone()
    return ResumenAlertas(**fila)


@router.get("", response_model=list[Alerta], summary="Alertas, de la más reciente a la más antigua")
def lista(
    usuario: UsuarioActual,
    estado: Annotated[list[Estado] | None, Query()] = None,
    limite: Annotated[int, Query(ge=1, le=MAX_ALERTAS)] = 100,
) -> list[Alerta]:
    with lectura() as conn:
        filas = conn.execute(
            "SELECT * FROM api.alertas "
            "WHERE %(estados)s::text[] IS NULL OR estado = ANY(%(estados)s) "
            "ORDER BY creada_en DESC, alerta_id DESC LIMIT %(limite)s",
            {"estados": estado, "limite": limite},
        ).fetchall()
    return [Alerta(**f) for f in filas]


@router.get("/{alerta_id}", response_model=DetalleAlerta, summary="Detalle de una alerta")
def detalle(usuario: UsuarioActual, alerta_id: IdAlerta) -> DetalleAlerta:
    """Contenido completo de la alerta, con cada intento de entrega del correo."""
    with lectura() as conn:
        return _detalle(conn, alerta_id)


@router.patch("/{alerta_id}", response_model=DetalleAlerta, summary="Cambiar el estado")
def cambiar_estado(
    usuario: UsuarioActual, alerta_id: IdAlerta, cambio: CambioEstado
) -> DetalleAlerta:
    """Marca la alerta como atendida, descartada o resuelta (o la reabre como nueva). Queda
    registrado quién y cuándo, con una nota opcional."""
    columnas = ["estado = %s", "estado_actualizado_en = now()", "estado_actualizado_por = %s"]
    valores: list[Any] = [cambio.estado, usuario.usuario]
    if cambio.nota is not None:
        columnas.append("nota = %s")
        valores.append(cambio.nota or None)
    with escritura() as conn:
        # Las columnas son fijas (de este código); los valores van siempre como parámetros
        actualizada = conn.execute(
            f"UPDATE alerta.alerta SET {', '.join(columnas)} WHERE alerta_id = %s "
            "RETURNING alerta_id",
            (*valores, alerta_id),
        ).fetchone()
        if actualizada is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "La alerta no existe.")
        return _detalle(conn, alerta_id)
