"""Filtros del dashboard -> condiciones SQL PARAMETRIZADAS.

Los valores nunca se concatenan en el SQL: van como parámetros. Las columnas salen de una
lista fija. Así se evita la inyección SQL (la guía lo exige).
"""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import HTTPException, Query, status
from psycopg import sql
from pydantic import BaseModel, Field

TEXTO = Field(default=None, max_length=100)


class Filtros(BaseModel):
    """Filtros comunes a todos los indicadores. Todos son opcionales."""

    model_config = {"extra": "forbid"}

    desde: date | None = None
    hasta: date | None = None
    territorio: str | None = TEXTO
    estado: str | None = TEXTO
    categoria: str | None = TEXTO  # categoría del cliente
    grupo: str | None = TEXTO  # grupo principal del producto
    vendedor_id: int | None = Field(default=None, ge=0)
    cliente_id: int | None = Field(default=None, ge=0)
    producto_id: int | None = Field(default=None, ge=0)
    solo_bajo_costo: bool = False
    incluir_simulados: bool = True

    def validar(self) -> Filtros:
        if self.desde and self.hasta and self.desde > self.hasta:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, "'desde' no puede ser posterior a 'hasta'"
            )
        return self

    def condiciones(self, alias: str = "v", desplazamiento: str | None = None):
        """(SQL del WHERE, parámetros). `desplazamiento` corre el rango de fechas hacia atrás
        (p. ej. '1 year') para calcular el período de comparación."""
        c = sql.Identifier(alias)
        partes: list[sql.Composable] = []
        p: dict[str, object] = {}
        corrimiento = sql.SQL("")
        if desplazamiento:
            corrimiento = sql.SQL(" - %(desplazamiento)s::interval")
            p["desplazamiento"] = desplazamiento
        if self.desde:
            partes.append(sql.SQL("{}.fecha >= (%(desde)s::date{})::date").format(c, corrimiento))
            p["desde"] = self.desde
        if self.hasta:
            partes.append(sql.SQL("{}.fecha <= (%(hasta)s::date{})::date").format(c, corrimiento))
            p["hasta"] = self.hasta
        iguales = {
            "territorio": "territorio",
            "estado": "estado",
            "categoria": "categoria_cliente",
            "grupo": "grupo_principal",
            "vendedor_id": "vendedor_id",
            "cliente_id": "cliente_id",
            "producto_id": "producto_id",
        }
        for campo, columna in iguales.items():
            valor = getattr(self, campo)
            if valor is not None:
                partes.append(
                    sql.SQL("{}.{} = %({})s").format(c, sql.Identifier(columna), sql.SQL(campo))
                )
                p[campo] = valor
        if self.solo_bajo_costo:
            partes.append(sql.SQL("{}.es_venta_bajo_costo").format(c))
        if not self.incluir_simulados:
            partes.append(sql.SQL("NOT {}.es_simulado").format(c))
        where = sql.SQL(" AND ").join(partes) if partes else sql.SQL("TRUE")
        return where, p


FiltrosQuery = Annotated[Filtros, Query()]
