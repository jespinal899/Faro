"""Datos del dashboard: KPI, tendencia, desglose, detalle, factura, opciones y estado.

Todos los indicadores provienen del Data Warehouse (vistas aprobadas del esquema api).
Las definiciones de cada KPI están en documentation/modelos/kpis.md.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Path, Query, status
from psycopg import sql
from pydantic import BaseModel

from ..db import lectura
from ..filtros import Filtros, FiltrosQuery
from ..seguridad import UsuarioActual

router = APIRouter(tags=["Datos del dashboard"])


# ------------------------------------------------------------------ modelos


class Indicadores(BaseModel):
    ventas_netas: float
    ventas_brutas: float
    utilidad: float
    margen_pct: float | None
    unidades: int
    facturas: int
    ticket_promedio: float | None
    clientes_activos: int


class Comparacion(BaseModel):
    tipo: Literal["anio_anterior"]
    desde: date
    hasta: date
    valores: Indicadores
    variacion_pct: dict[str, float | None]
    """Variación porcentual de cada KPI; para el margen, diferencia en puntos porcentuales."""


class RespuestaKpis(BaseModel):
    filtros: Filtros
    actual: Indicadores
    comparacion: Comparacion | None


class PuntoTendencia(BaseModel):
    periodo: date
    ventas_netas: float
    utilidad: float
    facturas: int
    ventas_netas_anterior: float | None


class FilaDesglose(BaseModel):
    clave: str | None
    nombre: str
    ventas_netas: float
    utilidad: float
    margen_pct: float | None
    unidades: float
    facturas: int | None
    participacion_pct: float | None


class RespuestaDesglose(BaseModel):
    dimension: str
    pertenencia: bool
    total_ventas_netas: float
    filas: list[FilaDesglose]


class FilaFactura(BaseModel):
    factura_id: int
    fecha: date
    cliente: str
    vendedor: str
    territorio: str
    lineas: int
    unidades: int
    ventas_netas: float
    utilidad: float
    es_simulado: bool
    tiene_venta_bajo_costo: bool


class PaginaFacturas(BaseModel):
    pagina: int
    tamano: int
    total: int
    filas: list[FilaFactura]


class LineaFactura(BaseModel):
    linea_factura_id: int
    producto_id: int
    producto: str
    grupo_principal: str
    cantidad: int
    precio_unitario: float | None
    venta_bruta: float
    impuesto: float
    venta_neta: float
    utilidad: float
    es_venta_bajo_costo: bool


class Factura(BaseModel):
    factura_id: int
    pedido_id: int | None
    fecha: date
    cliente_id: int
    cliente: str
    categoria_cliente: str
    grupo_compra: str
    vendedor: str
    ciudad: str
    estado: str
    territorio: str
    es_simulado: bool
    ventas_netas: float
    utilidad: float
    lineas: list[LineaFactura]


class Opcion(BaseModel):
    id: int
    nombre: str


class Opciones(BaseModel):
    territorios: list[str]
    estados: list[str]
    categorias: list[str]
    grupos: list[str]
    vendedores: list[Opcion]
    fecha_desde: date | None
    fecha_hasta: date | None


class EstadoDatos(BaseModel):
    ultima_carga_exitosa: datetime | None
    estado_ultima_ejecucion: str | None
    fecha_desde: date | None
    fecha_hasta: date | None
    ultima_fecha_real: date | None
    lineas: int
    lineas_simuladas: int


# ---------------------------------------------------------------- consultas

SQL_KPI = """
SELECT COALESCE(sum(v.venta_neta), 0)   AS ventas_netas,
       COALESCE(sum(v.venta_bruta), 0)  AS ventas_brutas,
       COALESCE(sum(v.utilidad), 0)     AS utilidad,
       round(100 * sum(v.utilidad) / NULLIF(sum(v.venta_neta), 0), 2) AS margen_pct,
       COALESCE(sum(v.cantidad), 0)     AS unidades,
       count(DISTINCT v.factura_id)     AS facturas,
       round(sum(v.venta_neta) / NULLIF(count(DISTINCT v.factura_id), 0), 2) AS ticket_promedio,
       count(DISTINCT v.cliente_id)     AS clientes_activos
FROM api.ventas v WHERE {where}
"""

# dimensión -> (columna clave, columna nombre)
DIMENSIONES = {
    "grupo": ("grupo_principal", "grupo_principal"),
    "categoria": ("categoria_cliente", "categoria_cliente"),
    "grupo_compra": ("grupo_compra", "grupo_compra"),
    "territorio": ("territorio", "territorio"),
    "estado": ("estado", "estado"),
    "vendedor": ("vendedor_id", "vendedor"),
    "producto": ("producto_id", "producto"),
    "cliente": ("cliente_id", "cliente"),
}

GRANULARIDADES = {
    # granularidad -> (date_trunc, desplazamiento para comparar con el año anterior)
    # Semana y día se corren 364 días (52 semanas) para comparar el mismo día de la semana.
    "mes": ("month", "1 year"),
    "semana": ("week", "364 days"),
    "dia": ("day", "364 days"),
}

# Campos de Factura que se calculan sumando las líneas (no se copian de la cabecera)
TOTALES_FACTURA = {"ventas_netas", "utilidad", "lineas"}

ORDENES = {
    "fecha_desc": "fecha DESC, factura_id DESC",
    "fecha_asc": "fecha, factura_id",
    "venta_desc": "ventas_netas DESC, factura_id DESC",
    "venta_asc": "ventas_netas, factura_id",
}


def _variacion(actual: Indicadores, anterior: Indicadores) -> dict[str, float | None]:
    resultado: dict[str, float | None] = {}
    for campo in Indicadores.model_fields:
        a, b = getattr(actual, campo), getattr(anterior, campo)
        if a is None or b is None:
            resultado[campo] = None
        elif campo == "margen_pct":
            resultado[campo] = round(a - b, 2)  # puntos porcentuales
        else:
            resultado[campo] = round(100 * (a - b) / b, 2) if b else None
    return resultado


def _restar_un_anio(d: date) -> date:
    try:
        return d.replace(year=d.year - 1)
    except ValueError:  # 29 de febrero
        return d.replace(year=d.year - 1, day=28)


# ------------------------------------------------------------------- rutas


@router.get("/kpis", response_model=RespuestaKpis, summary="Indicadores principales")
def kpis(usuario: UsuarioActual, filtros: FiltrosQuery) -> RespuestaKpis:
    """KPI del período filtrado. Si se indica `desde` y `hasta`, se comparan con el mismo
    período del año anterior."""
    f = filtros.validar()
    with lectura() as conn:
        where, p = f.condiciones()
        actual = Indicadores(**conn.execute(sql.SQL(SQL_KPI).format(where=where), p).fetchone())
        comparacion = None
        if f.desde and f.hasta:
            where_a, p_a = f.condiciones(desplazamiento="1 year")
            anterior = Indicadores(
                **conn.execute(sql.SQL(SQL_KPI).format(where=where_a), p_a).fetchone()
            )
            comparacion = Comparacion(
                tipo="anio_anterior",
                desde=_restar_un_anio(f.desde),
                hasta=_restar_un_anio(f.hasta),
                valores=anterior,
                variacion_pct=_variacion(actual, anterior),
            )
    return RespuestaKpis(filtros=f, actual=actual, comparacion=comparacion)


@router.get("/tendencia", response_model=list[PuntoTendencia], summary="Tendencia histórica")
def tendencia(
    usuario: UsuarioActual,
    filtros: FiltrosQuery,
    granularidad: Annotated[Literal["mes", "semana", "dia"], Query()] = "mes",
) -> list[PuntoTendencia]:
    """Ventas netas, utilidad y facturas por período, con las ventas del período equivalente
    del año anterior para comparar."""
    f = filtros.validar()
    trunc, desplazamiento = GRANULARIDADES[granularidad]
    where_actual, p_actual = f.condiciones()
    where_anterior, p_anterior = f.condiciones(desplazamiento=desplazamiento)
    consulta = sql.SQL(
        "WITH actual AS ("
        "  SELECT date_trunc(%(trunc)s, v.fecha)::date AS periodo,"
        "         sum(v.venta_neta) AS ventas_netas, sum(v.utilidad) AS utilidad,"
        "         count(DISTINCT v.factura_id) AS facturas"
        "  FROM api.ventas v WHERE {wa} GROUP BY 1),"
        " anterior AS ("
        "  SELECT date_trunc(%(trunc)s, v.fecha + %(desplazamiento)s::interval)::date AS periodo,"
        "         sum(v.venta_neta) AS ventas_netas"
        "  FROM api.ventas v WHERE {wp} GROUP BY 1)"
        " SELECT a.periodo, a.ventas_netas, a.utilidad, a.facturas,"
        "        p.ventas_netas AS ventas_netas_anterior"
        " FROM actual a LEFT JOIN anterior p USING (periodo) ORDER BY a.periodo"
    ).format(wa=where_actual, wp=where_anterior)
    with lectura() as conn:
        filas = conn.execute(consulta, {**p_actual, **p_anterior, "trunc": trunc}).fetchall()
    return [PuntoTendencia(**fila) for fila in filas]


@router.get("/desglose", response_model=RespuestaDesglose, summary="Ventas por dimensión")
def desglose(
    usuario: UsuarioActual,
    filtros: FiltrosQuery,
    dimension: Annotated[Literal[tuple(DIMENSIONES)], Query()] = "grupo",  # type: ignore[valid-type]
    top: Annotated[int, Query(ge=1, le=50)] = 10,
    pertenencia: Annotated[bool, Query()] = False,
) -> RespuestaDesglose:
    """Ventas por grupo, categoría, territorio, vendedor, producto o cliente.

    Con `pertenencia=true` (solo para grupos) cada venta se reparte entre todos los grupos
    del producto con su factor de ponderación: la suma sigue siendo el total (no se duplica).
    Las filas que no entran en el top se agrupan en "Otros".
    """
    f = filtros.validar()
    if pertenencia and dimension != "grupo":
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "'pertenencia' solo aplica a la dimensión grupo"
        )
    where, p = f.condiciones()
    if pertenencia:
        clave = nombre = sql.SQL("b.grupo")
        factor = sql.SQL(" * b.factor_ponderacion")
        union = sql.SQL("JOIN api.producto_grupo b ON b.producto_id = v.producto_id")
    else:
        col_clave, col_nombre = DIMENSIONES[dimension]
        clave = sql.SQL("v.{}").format(sql.Identifier(col_clave))
        nombre = sql.SQL("v.{}").format(sql.Identifier(col_nombre))
        factor = sql.SQL("")
        union = sql.SQL("")
    consulta = sql.SQL(
        "SELECT {clave}::text AS clave, {nombre}::text AS nombre,"
        " sum(v.venta_neta{f}) AS ventas_netas, sum(v.utilidad{f}) AS utilidad,"
        " sum(v.cantidad{f}) AS unidades, count(DISTINCT v.factura_id) AS facturas"
        " FROM api.ventas v {union} WHERE {where} GROUP BY 1, 2"
        " ORDER BY ventas_netas DESC NULLS LAST, nombre"
    ).format(clave=clave, nombre=nombre, f=factor, union=union, where=where)
    with lectura() as conn:
        filas = conn.execute(consulta, p).fetchall()

    total = float(sum(x["ventas_netas"] for x in filas))

    def fila(clave, nombre, netas, utilidad, unidades, facturas) -> FilaDesglose:
        return FilaDesglose(
            clave=clave,
            nombre=nombre,
            ventas_netas=netas,
            utilidad=utilidad,
            margen_pct=round(100 * float(utilidad) / float(netas), 2) if netas else None,
            unidades=unidades,
            facturas=facturas,
            participacion_pct=round(100 * float(netas) / total, 2) if total else None,
        )

    resultado = [
        fila(
            x["clave"], x["nombre"], x["ventas_netas"], x["utilidad"], x["unidades"], x["facturas"]
        )
        for x in filas[:top]
    ]
    resto = filas[top:]
    if resto:
        # Las facturas no se suman entre grupos (una factura puede estar en varios): None
        resultado.append(
            fila(
                None,
                f"Otros ({len(resto)})",
                sum(x["ventas_netas"] for x in resto),
                sum(x["utilidad"] for x in resto),
                sum(x["unidades"] for x in resto),
                None,
            )
        )
    return RespuestaDesglose(
        dimension=dimension, pertenencia=pertenencia, total_ventas_netas=total, filas=resultado
    )


@router.get("/facturas", response_model=PaginaFacturas, summary="Detalle de facturas (paginado)")
def facturas(
    usuario: UsuarioActual,
    filtros: FiltrosQuery,
    pagina: Annotated[int, Query(ge=1, le=10_000)] = 1,
    tamano: Annotated[int, Query(ge=1, le=100)] = 25,
    orden: Annotated[Literal[tuple(ORDENES)], Query()] = "fecha_desc",  # type: ignore[valid-type]
    buscar: Annotated[str | None, Query(max_length=60)] = None,
) -> PaginaFacturas:
    """Facturas del período filtrado, de a `tamano` por página (máximo 100).
    `buscar` filtra por nombre de cliente."""
    f = filtros.validar()
    where, p = f.condiciones()
    if buscar:
        escapado = buscar.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        where = sql.SQL("{} AND v.cliente ILIKE %(buscar)s").format(where)
        p["buscar"] = f"%{escapado}%"
    consulta = sql.SQL(
        "SELECT v.factura_id, min(v.fecha) AS fecha, min(v.cliente) AS cliente,"
        " min(v.vendedor) AS vendedor, min(v.territorio) AS territorio, count(*) AS lineas,"
        " sum(v.cantidad) AS unidades, sum(v.venta_neta) AS ventas_netas,"
        " sum(v.utilidad) AS utilidad, bool_or(v.es_simulado) AS es_simulado,"
        " bool_or(v.es_venta_bajo_costo) AS tiene_venta_bajo_costo, count(*) OVER () AS total"
        " FROM api.ventas v WHERE {where} GROUP BY v.factura_id"
        " ORDER BY {orden} LIMIT %(limite)s OFFSET %(desde_fila)s"
    ).format(where=where, orden=sql.SQL(ORDENES[orden]))
    with lectura() as conn:
        filas = conn.execute(
            consulta, {**p, "limite": tamano, "desde_fila": (pagina - 1) * tamano}
        ).fetchall()
    total = filas[0]["total"] if filas else 0
    return PaginaFacturas(
        pagina=pagina, tamano=tamano, total=total, filas=[FilaFactura(**x) for x in filas]
    )


@router.get("/facturas/{factura_id}", response_model=Factura, summary="Detalle de una factura")
def factura(usuario: UsuarioActual, factura_id: Annotated[int, Path(ge=1)]) -> Factura:
    """Navegación de resumen a detalle (drill-down): la factura con sus líneas."""
    with lectura() as conn:
        lineas = conn.execute(
            "SELECT * FROM api.ventas WHERE factura_id = %s ORDER BY linea_factura_id",
            (factura_id,),
        ).fetchall()
    if not lineas:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Factura no encontrada")
    cab = lineas[0]  # los datos de cabecera se repiten en cada línea
    return Factura(
        **{k: cab[k] for k in Factura.model_fields if k in cab and k not in TOTALES_FACTURA},
        ventas_netas=sum(x["venta_neta"] for x in lineas),
        utilidad=sum(x["utilidad"] for x in lineas),
        lineas=[LineaFactura(**x) for x in lineas],
    )


@router.get("/opciones", response_model=Opciones, summary="Valores para los filtros")
def opciones(usuario: UsuarioActual) -> Opciones:
    with lectura() as conn:

        def lista(columna: str) -> list[str]:
            return [
                x["v"]
                for x in conn.execute(
                    sql.SQL("SELECT DISTINCT {c} AS v FROM api.ventas ORDER BY 1").format(
                        c=sql.Identifier(columna)
                    )
                )
            ]

        vendedores = conn.execute(
            "SELECT DISTINCT vendedor_id AS id, vendedor AS nombre FROM api.ventas ORDER BY 2"
        ).fetchall()
        rango = conn.execute("SELECT fecha_desde, fecha_hasta FROM api.estado_datos").fetchone()
        return Opciones(
            territorios=lista("territorio"),
            estados=lista("estado"),
            categorias=lista("categoria_cliente"),
            grupos=lista("grupo_principal"),
            vendedores=[Opcion(**x) for x in vendedores],
            **rango,
        )


@router.get("/estado", response_model=EstadoDatos, summary="Frescura de los datos")
def estado(usuario: UsuarioActual) -> EstadoDatos:
    """Fecha y hora de la última carga exitosa y rango de datos disponibles."""
    with lectura() as conn:
        return EstadoDatos(**conn.execute("SELECT * FROM api.estado_datos").fetchone())
