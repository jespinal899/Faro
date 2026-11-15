"""Catálogo cerrado de consultas que el asistente puede pedir (la guía: "consultas
parametrizadas, vistas aprobadas o herramientas analíticas limitadas").

- Cada herramienta valida sus parámetros (fechas, valores de filtros que existen, límites) y
  llama a las MISMAS funciones del dashboard: las cifras coinciden con lo que muestra.
- Solo devuelven datos agregados. No hay herramientas de clientes ni de facturas: ningún dato
  personal sale hacia el servicio externo de IA.
- Un error de validación vuelve al modelo como mensaje (para que corrija), nunca como SQL.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..filtros import Filtros
from ..rutas import datos, pronostico
from ..seguridad import Usuario

MAX_PUNTOS_TENDENCIA = 60
MAX_TOP = 15


class ErrorHerramienta(Exception):
    """Parámetros inválidos: el mensaje vuelve al modelo para que corrija la consulta."""


# ------------------------------------------------------------------ contexto


@dataclass
class Contexto:
    """Lo que el asistente necesita saber de los datos en esta solicitud."""

    fecha_desde: date
    fecha_hasta: date
    ultima_fecha_real: date | None
    ultima_carga: datetime | None
    lineas_simuladas: int
    territorios: list[str] = field(default_factory=list)
    estados: list[str] = field(default_factory=list)
    categorias: list[str] = field(default_factory=list)
    grupos: list[str] = field(default_factory=list)

    @classmethod
    def cargar(cls, usuario: Usuario) -> Contexto:
        e = datos.estado(usuario)
        o = datos.opciones(usuario)
        return cls(
            fecha_desde=e.fecha_desde,
            fecha_hasta=e.fecha_hasta,
            ultima_fecha_real=e.ultima_fecha_real,
            ultima_carga=e.ultima_carga_exitosa,
            lineas_simuladas=e.lineas_simuladas,
            territorios=o.territorios,
            estados=o.estados,
            categorias=o.categorias,
            grupos=o.grupos,
        )

    def texto(self) -> str:
        """Bloque de contexto que acompaña a cada pregunta (cambia con cada carga del ETL)."""
        simuladas = (
            f"Las ventas desde el {self.ultima_fecha_real + timedelta(days=1)} son SIMULADAS "
            "(operación de demostración); las anteriores son reales."
            if self.lineas_simuladas and self.ultima_fecha_real
            else "Todas las ventas son reales."
        )
        return (
            f"Datos disponibles: ventas del {self.fecha_desde} al {self.fecha_hasta} "
            f"(última fecha con datos: {self.fecha_hasta}). {simuladas}\n"
            f"Territorios: {', '.join(self.territorios)}.\n"
            f"Categorías de cliente: {', '.join(self.categorias)}.\n"
            f"Grupos de producto: {', '.join(self.grupos)}.\n"
            f"Estados: {len(self.estados)} estados de EE. UU. (nombre en inglés, p. ej. "
            "'California')."
        )


# ------------------------------------------------------------------ parámetros


class _Filtros(BaseModel):
    model_config = ConfigDict(extra="forbid")

    desde: date
    hasta: date
    territorio: str | None = Field(default=None, max_length=100)
    estado: str | None = Field(default=None, max_length=100)
    categoria_cliente: str | None = Field(default=None, max_length=100)
    grupo_producto: str | None = Field(default=None, max_length=100)
    incluir_simulados: bool = True


class _Indicadores(_Filtros):
    pass


class _Tendencia(_Filtros):
    granularidad: Literal["mes", "semana"] = "mes"


DIMENSIONES = {  # nombre para el modelo -> dimensión del dashboard (sin clientes: datos personales)
    "grupo_producto": "grupo",
    "categoria_cliente": "categoria",
    "grupo_compra": "grupo_compra",
    "territorio": "territorio",
    "estado": "estado",
    "vendedor": "vendedor",
    "producto": "producto",
}


class _Ranking(_Filtros):
    dimension: Literal[tuple(DIMENSIONES)]  # type: ignore[valid-type]
    orden: Literal["ventas", "crecimiento", "caida"] = "ventas"
    top: int = Field(default=10, ge=1, le=MAX_TOP)


class _Pronostico(BaseModel):
    model_config = ConfigDict(extra="forbid")

    grupo_producto: str | None = Field(default=None, max_length=100)


# ------------------------------------------------------------------ definiciones para el modelo

_PROPIEDADES_FILTROS = {
    "desde": {"type": "string", "format": "date", "description": "Fecha inicial (AAAA-MM-DD)."},
    "hasta": {"type": "string", "format": "date", "description": "Fecha final, incluida."},
    "territorio": {"type": "string", "description": "Filtra por territorio de venta."},
    "estado": {"type": "string", "description": "Filtra por estado de EE. UU. (en inglés)."},
    "categoria_cliente": {"type": "string", "description": "Filtra por categoría de cliente."},
    "grupo_producto": {"type": "string", "description": "Filtra por grupo principal de producto."},
    "incluir_simulados": {
        "type": "boolean",
        "description": "Incluir ventas simuladas (por defecto true, como el dashboard).",
    },
}


def _esquema(propiedades: dict, requeridas: list[str]) -> dict:
    return {
        "type": "object",
        "properties": propiedades,
        "required": requeridas,
        "additionalProperties": False,
    }


DEFINICIONES = [
    {
        "name": "consultar_indicadores",
        "description": (
            "Indicadores de ventas de un período (ventas netas sin impuestos, ventas brutas, "
            "utilidad, margen %, unidades, facturas, ticket promedio, clientes activos), "
            "comparados con el MISMO período del año anterior (variación %; el margen en puntos). "
            "Úsala para totales y para '¿cómo nos fue en...?'."
        ),
        "input_schema": _esquema(_PROPIEDADES_FILTROS, ["desde", "hasta"]),
    },
    {
        "name": "consultar_tendencia",
        "description": (
            "Serie de ventas netas, utilidad y facturas por mes o por semana, con la venta del "
            "período equivalente del año anterior. Máximo 60 puntos. Úsala para la evolución "
            "en el tiempo y para ubicar picos o caídas."
        ),
        "input_schema": _esquema(
            {
                **_PROPIEDADES_FILTROS,
                "granularidad": {"type": "string", "enum": ["mes", "semana"]},
            },
            ["desde", "hasta"],
        ),
    },
    {
        "name": "consultar_ranking",
        "description": (
            "Ventas netas por grupo de producto, categoría o grupo de compra del cliente, "
            "territorio, estado, vendedor o producto, con participación, margen y variación "
            "frente al mismo período del año anterior. orden='ventas' (mayores), 'crecimiento' "
            "(mayor alza %) o 'caida' (mayor baja %). Considera los 50 de mayor venta. No hay "
            "datos por cliente individual."
        ),
        "input_schema": _esquema(
            {
                **_PROPIEDADES_FILTROS,
                "dimension": {"type": "string", "enum": list(DIMENSIONES)},
                "orden": {"type": "string", "enum": ["ventas", "crecimiento", "caida"]},
                "top": {"type": "integer", "minimum": 1, "maximum": MAX_TOP},
            },
            ["desde", "hasta", "dimension"],
        ),
    },
    {
        "name": "consultar_pronostico",
        "description": (
            "PREDICCIÓN del modelo de Machine Learning: ventas netas de las 4 semanas siguientes "
            "a la última semana completa, por grupo de producto, con rango probable del 80 % y "
            "el error del modelo en semanas que no vio. Úsala solo para preguntas sobre el futuro."
        ),
        "input_schema": _esquema(
            {
                "grupo_producto": {
                    "type": "string",
                    "description": "Un grupo; si se omite, devuelve todos.",
                }
            },
            [],
        ),
    },
]


# ------------------------------------------------------------------ ejecución


def _redondear(valor):
    if isinstance(valor, float):
        return round(valor, 2)
    if isinstance(valor, dict):
        return {k: _redondear(v) for k, v in valor.items()}
    if isinstance(valor, list):
        return [_redondear(v) for v in valor]
    return valor


def _validar_valor(nombre: str, valor: str | None, permitidos: list[str]) -> None:
    if valor is not None and valor not in permitidos:
        raise ErrorHerramienta(
            f"{nombre} '{valor}' no existe. Valores válidos: {', '.join(permitidos)}."
        )


def _filtros(p: _Filtros, ctx: Contexto) -> tuple[Filtros, dict]:
    """Filtros del dashboard + aviso de cobertura. Lanza ErrorHerramienta si son inválidos."""
    if p.desde > p.hasta:
        raise ErrorHerramienta("'desde' no puede ser posterior a 'hasta'.")
    _validar_valor("El territorio", p.territorio, ctx.territorios)
    _validar_valor("El estado", p.estado, ctx.estados)
    _validar_valor("La categoría de cliente", p.categoria_cliente, ctx.categorias)
    _validar_valor("El grupo de producto", p.grupo_producto, ctx.grupos)
    cobertura: dict = {"periodo_pedido": [str(p.desde), str(p.hasta)]}
    if p.hasta < ctx.fecha_desde or p.desde > ctx.fecha_hasta:
        cobertura["sin_datos"] = (
            f"No hay ventas en ese período: los datos cubren del {ctx.fecha_desde} al "
            f"{ctx.fecha_hasta}."
        )
    elif p.desde < ctx.fecha_desde or p.hasta > ctx.fecha_hasta:
        cobertura["aviso"] = (
            f"El período pedido excede los datos disponibles ({ctx.fecha_desde} a "
            f"{ctx.fecha_hasta}): las cifras cubren solo las fechas con datos."
        )
    if p.incluir_simulados and ctx.lineas_simuladas and ctx.ultima_fecha_real:
        cobertura["incluye_ventas_simuladas"] = p.hasta > ctx.ultima_fecha_real
    f = Filtros(
        desde=p.desde,
        hasta=p.hasta,
        territorio=p.territorio,
        estado=p.estado,
        categoria=p.categoria_cliente,
        grupo=p.grupo_producto,
        incluir_simulados=p.incluir_simulados,
    )
    return f, cobertura


def _indicadores(p: _Indicadores, ctx: Contexto, usuario: Usuario) -> dict:
    f, cobertura = _filtros(p, ctx)
    if "sin_datos" in cobertura:
        return cobertura
    r = datos.kpis(usuario, f)
    resultado = {**cobertura, "indicadores": r.actual.model_dump()}
    if r.comparacion:
        resultado["anio_anterior"] = {
            "periodo": [str(r.comparacion.desde), str(r.comparacion.hasta)],
            "indicadores": r.comparacion.valores.model_dump(),
            "variacion_pct": r.comparacion.variacion_pct,
            "nota": "variacion_pct.margen_pct es la diferencia en puntos porcentuales",
        }
    return resultado


def _tendencia(p: _Tendencia, ctx: Contexto, usuario: Usuario) -> dict:
    f, cobertura = _filtros(p, ctx)
    if "sin_datos" in cobertura:
        return cobertura
    puntos = datos.tendencia(usuario, f, granularidad=p.granularidad)
    if len(puntos) > MAX_PUNTOS_TENDENCIA:
        raise ErrorHerramienta(
            f"Son {len(puntos)} puntos (máximo {MAX_PUNTOS_TENDENCIA}): usa granularidad 'mes' "
            "o un período más corto."
        )
    return {
        **cobertura,
        "granularidad": p.granularidad,
        "puntos": [
            {
                "periodo": str(x.periodo),
                "ventas_netas": x.ventas_netas,
                "ventas_netas_anio_anterior": x.ventas_netas_anterior,
                "utilidad": x.utilidad,
                "facturas": x.facturas,
            }
            for x in puntos
        ],
    }


def _ranking(p: _Ranking, ctx: Contexto, usuario: Usuario) -> dict:
    f, cobertura = _filtros(p, ctx)
    if "sin_datos" in cobertura:
        return cobertura
    dimension = DIMENSIONES[p.dimension]
    actual = datos.desglose(usuario, f, dimension=dimension, top=50, pertenencia=False)
    anterior_f = f.model_copy(
        update={
            "desde": datos._restar_un_anio(p.desde),
            "hasta": datos._restar_un_anio(p.hasta),
        }
    )
    anterior = datos.desglose(usuario, anterior_f, dimension=dimension, top=50, pertenencia=False)
    previas = {x.clave: x.ventas_netas for x in anterior.filas if x.clave is not None}

    filas = []
    for x in actual.filas:
        if x.clave is None:  # "Otros": no es un valor de la dimensión
            continue
        previa = previas.get(x.clave)
        filas.append(
            {
                "nombre": x.nombre,
                "ventas_netas": x.ventas_netas,
                "participacion_pct": x.participacion_pct,
                "margen_pct": x.margen_pct,
                "ventas_netas_anio_anterior": previa,
                "variacion_pct": (100 * (x.ventas_netas - previa) / previa) if previa else None,
            }
        )
    if p.orden == "ventas":
        filas.sort(key=lambda r: -r["ventas_netas"])
    else:
        con_variacion = [r for r in filas if r["variacion_pct"] is not None]
        con_variacion.sort(key=lambda r: r["variacion_pct"], reverse=p.orden == "crecimiento")
        filas = con_variacion
    return {
        **cobertura,
        "dimension": p.dimension,
        "orden": p.orden,
        "total_ventas_netas": actual.total_ventas_netas,
        "periodo_anio_anterior": [str(anterior_f.desde), str(anterior_f.hasta)],
        "filas": filas[: p.top],
    }


def _pronostico(p: _Pronostico, ctx: Contexto, usuario: Usuario) -> dict:
    r = pronostico.pronostico(usuario, semanas_historia=4)
    if not r.disponible or r.modelo is None:
        return {"sin_datos": "No hay un pronóstico registrado."}
    grupos = r.grupos
    if p.grupo_producto is not None:
        _validar_valor(
            "El grupo de producto",
            p.grupo_producto,
            [g.grupo for g in grupos] + [e.grupo for e in r.excluidos],
        )
        excluido = next((e for e in r.excluidos if e.grupo == p.grupo_producto), None)
        if excluido:
            return {"sin_datos": f"{excluido.grupo}: sin pronóstico ({excluido.motivo})."}
        grupos = [g for g in grupos if g.grupo == p.grupo_producto]
    c = r.modelo.calidad
    return {
        "es_prediccion": True,
        "modelo": r.modelo.version,
        "origen": str(r.origen),
        "nota": "Pronóstico desde la última semana completa; rango probable del 80 %.",
        "calidad": {
            "error_wape_prueba_pct": c.wape_prueba_modelo,
            "error_wape_linea_base_pct": c.wape_prueba_linea_base,
            "linea_base": c.linea_base_descripcion,
            "cobertura_rango_prueba_pct": c.cobertura_prueba_pct,
        },
        "grupos": [
            {
                "grupo": g.grupo,
                "semanas": [
                    {
                        "semana": str(x.semana),
                        "venta_neta": x.venta_neta,
                        "rango_80": [x.inferior, x.superior],
                    }
                    for x in g.pronostico
                ],
                "total_4_semanas": sum(x.venta_neta for x in g.pronostico),
            }
            for g in grupos
        ],
        "sin_pronostico": [{"grupo": e.grupo, "motivo": e.motivo} for e in r.excluidos],
    }


_EJECUTORES = {
    "consultar_indicadores": (_Indicadores, _indicadores),
    "consultar_tendencia": (_Tendencia, _tendencia),
    "consultar_ranking": (_Ranking, _ranking),
    "consultar_pronostico": (_Pronostico, _pronostico),
}


def ejecutar(nombre: str, entrada: dict, ctx: Contexto, usuario: Usuario) -> dict:
    """Valida y ejecuta una herramienta. Lanza ErrorHerramienta con un mensaje para el modelo."""
    if nombre not in _EJECUTORES:
        raise ErrorHerramienta(f"La herramienta '{nombre}' no existe.")
    modelo, funcion = _EJECUTORES[nombre]
    try:
        parametros = modelo.model_validate(entrada)
    except ValidationError as e:
        detalle = "; ".join(f"{'.'.join(map(str, x['loc']))}: {x['msg']}" for x in e.errors())
        raise ErrorHerramienta(f"Parámetros inválidos: {detalle}") from e
    return _redondear(funcion(parametros, ctx, usuario))


def describir(nombre: str, entrada: dict) -> str:
    """Descripción legible de una consulta (para mostrar como fuente)."""
    filtros = [
        f"{k.replace('_', ' ')}: {entrada[k]}"
        for k in ("territorio", "estado", "categoria_cliente", "grupo_producto")
        if entrada.get(k)
    ]
    if entrada.get("incluir_simulados") is False:
        filtros.append("solo ventas reales")
    sufijo = f" ({'; '.join(filtros)})" if filtros else ""
    periodo = f"del {entrada.get('desde')} al {entrada.get('hasta')}"
    if nombre == "consultar_indicadores":
        return f"Indicadores {periodo}{sufijo}, frente al mismo período del año anterior"
    if nombre == "consultar_tendencia":
        return f"Tendencia por {entrada.get('granularidad', 'mes')} {periodo}{sufijo}"
    if nombre == "consultar_ranking":
        return (
            f"Ventas por {str(entrada.get('dimension', '')).replace('_', ' ')} {periodo}"
            f"{sufijo}, orden: {entrada.get('orden', 'ventas')}"
        )
    if nombre == "consultar_pronostico":
        grupo = entrada.get("grupo_producto")
        return f"PREDICCIÓN de las 4 semanas siguientes{f' ({grupo})' if grupo else ''}"
    return nombre
