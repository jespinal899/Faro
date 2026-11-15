"""Carga del Data Warehouse: stg_ready -> dw (dimensiones, puente y hechos).

Orden (las claves de dimensión se resuelven ANTES de insertar los hechos):
  1. Dimensiones SCD Tipo 1 (empleado, geografía, grupo): se sobrescriben si cambiaron.
  2. Dimensiones SCD Tipo 2 (cliente, producto):
       - Clave nueva           -> versión 1, vigente desde 1900-01-01.
       - Cambio en atributo T1 -> se sobrescribe en todas sus versiones.
       - Cambio en atributo T2 -> se cierra la versión vigente y se abre una nueva.
         Los atributos T2 son IDENTIFICADORES (categoría, grupo, cliente de facturación):
         los nombres se refrescan en todas las versiones según su ID, así renombrar una
         categoría no crea versiones falsas.
     La nueva versión rige desde el día siguiente a la última venta cargada (el "reloj de
     negocio"): así las ventas anteriores conservan el contexto que tenían.
  3. Puente producto-grupo (factor de ponderación 1/n).
  4. Hechos: UPSERT por linea_factura_id. Cada clave se resuelve con la versión vigente en
     la fecha de la venta; si la dimensión no existe se usa el miembro desconocido (-1) y
     una ejecución posterior lo reasigna cuando la dimensión aparece.

Corre dentro de la transacción del pipeline: si algo falla, no queda nada a medias.
Los identificadores SQL vienen de constantes de este módulo, nunca de datos externos.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import psycopg


@dataclass(frozen=True)
class DimensionSCD1:
    tabla: str
    vista: str  # vista de stg_ready
    clave_natural: str
    atributos: tuple[str, ...]


@dataclass(frozen=True)
class DimensionSCD2:
    tabla: str
    vista: str
    clave_natural: str
    clave_sustituta: str
    tipo1: tuple[str, ...]  # se sobrescriben
    tipo2: tuple[str, ...]  # generan una versión nueva (identificadores, no nombres)
    # (columna con el nombre, columna con su ID, consulta "SELECT id, nombre"): el nombre se
    # refresca en TODAS las versiones según el ID que tiene cada una. Así renombrar una
    # categoría o un grupo no crea versiones nuevas (no es un cambio del cliente/producto).
    nombres: tuple[tuple[str, str, str], ...] = ()


DIMENSIONES_SCD1 = (
    DimensionSCD1(
        "dw.dim_empleado",
        "stg_ready.empleados",
        "persona_id",
        ("nombre_completo", "nombre_preferido", "es_vendedor"),
    ),
    DimensionSCD1(
        "dw.dim_geografia",
        "stg_ready.geografia",
        "ciudad_id",
        ("ciudad", "estado", "codigo_estado", "territorio_venta", "pais", "latitud", "longitud"),
    ),
    DimensionSCD1(
        "dw.dim_grupo_producto", "stg_ready.grupos_producto", "grupo_id", ("nombre", "prioridad")
    ),
)

DIMENSIONES_SCD2 = (
    DimensionSCD2(
        "dw.dim_cliente",
        "stg_ready.clientes",
        "cliente_id",
        "cliente_key",
        tipo1=(
            "nombre",
            "es_casa_matriz",
            "politica_credito",
            "limite_credito",
            "dias_pago",
            "en_suspension_credito",
            "descuento_estandar",
            "fecha_apertura",
        ),
        tipo2=("categoria_id", "grupo_compra_id", "cliente_facturacion_id"),
        nombres=(
            (
                "categoria",
                "categoria_id",
                "SELECT customer_category_id, customer_category_name "
                "FROM stg_clean.sales_customer_categories",
            ),
            (
                "grupo_compra",
                "grupo_compra_id",
                "SELECT buying_group_id, buying_group_name FROM stg_clean.sales_buying_groups",
            ),
        ),
    ),  # fmt: skip
    DimensionSCD2(
        "dw.dim_producto",
        "stg_ready.productos",
        "producto_id",
        "producto_key",
        tipo1=(
            "nombre",
            "marca",
            "color",
            "talla",
            "empaque_unidad",
            "empaque_exterior",
            "cantidad_por_empaque",
            "requiere_frio",
            "dias_reposicion",
            "peso_unitario",
            "cantidad_grupos",
        ),
        tipo2=("precio_lista", "precio_venta_sugerido", "tasa_impuesto", "grupo_principal_id"),
        nombres=(
            (
                "grupo_principal",
                "grupo_principal_id",
                "SELECT grupo_id, nombre FROM stg_ready.grupos_producto",
            ),
        ),
    ),  # fmt: skip
)

CLAVES_HECHO = (
    "fecha_factura_key", "fecha_pedido_key", "cliente_key", "cliente_facturacion_key",
    "producto_key", "vendedor_key", "geografia_key",
)  # fmt: skip

COLUMNAS_HECHO = (
    *CLAVES_HECHO,
    "linea_factura_id", "factura_id", "pedido_id", "fecha_factura", "cliente_id",
    "cliente_facturacion_id", "producto_id", "vendedor_id", "ciudad_id", "cantidad",
    "venta_bruta", "impuesto", "venta_neta", "costo", "utilidad", "precio_unitario",
    "tasa_impuesto", "es_venta_bajo_costo", "es_atipico", "es_simulado",
)  # fmt: skip


@dataclass
class ResultadoDW:
    dimensiones: dict[str, dict[str, int]] = field(default_factory=dict)
    hechos_nuevos: int = 0
    hechos_actualizados: int = 0
    hechos_con_desconocido: int = 0
    reconciliado: bool | None = None
    duracion_ms: int = 0


def vaciar_dw(dst: psycopg.Connection) -> None:
    """Modo inicial: borra hechos, puente y dimensiones (excepto los miembros desconocidos)."""
    dst.execute("DELETE FROM dw.fact_ventas")
    dst.execute("DELETE FROM dw.puente_producto_grupo")
    for d in DIMENSIONES_SCD2:
        dst.execute(f"DELETE FROM {d.tabla} WHERE {d.clave_sustituta} <> -1")
    for d in DIMENSIONES_SCD1:
        dst.execute(f"DELETE FROM {d.tabla} WHERE {d.clave_natural} <> -1")


def _cargar_scd1(dst: psycopg.Connection, d: DimensionSCD1, batch_id: int) -> dict[str, int]:
    cols = ", ".join(d.atributos)
    distinto = (
        f"ROW({', '.join(f't.{a}' for a in d.atributos)}) IS DISTINCT FROM "
        f"ROW({', '.join(f'EXCLUDED.{a}' for a in d.atributos)})"
    )
    nuevas, actualizadas = dst.execute(
        f"WITH c AS ("
        f"  INSERT INTO {d.tabla} AS t ({d.clave_natural}, {cols}, batch_id) "
        f"  SELECT {d.clave_natural}, {cols}, %(b)s FROM {d.vista} "
        f"  ON CONFLICT ({d.clave_natural}) DO UPDATE SET "
        f"  {', '.join(f'{a} = EXCLUDED.{a}' for a in d.atributos)}, batch_id = EXCLUDED.batch_id "
        f"  WHERE {distinto} RETURNING (xmax = 0) AS es_nueva) "
        f"SELECT count(*) FILTER (WHERE es_nueva), count(*) FILTER (WHERE NOT es_nueva) FROM c",
        {"b": batch_id},
    ).fetchone()
    return {"nuevas": nuevas, "actualizadas": actualizadas}


def _cargar_scd2(
    dst: psycopg.Connection, d: DimensionSCD2, batch_id: int, reloj: str
) -> dict[str, int]:
    nk = d.clave_natural
    todas = (*d.tipo1, *d.tipo2, *(nombre for nombre, _, _ in d.nombres))
    hash_t2 = f"md5(ROW({', '.join(f's.{a}' for a in d.tipo2)})::text)"
    p = {"b": batch_id, "vigencia": reloj}

    dst.execute(
        f"CREATE TEMP TABLE _src ON COMMIT DROP AS "
        f"SELECT s.{nk}, {', '.join(f's.{a}' for a in todas)}, {hash_t2} AS h2 FROM {d.vista} s"
    )

    # 1. Claves nuevas: versión 1, vigente "desde siempre"
    nuevas = dst.execute(
        f"INSERT INTO {d.tabla} ({nk}, {', '.join(todas)}, valido_desde, valido_hasta, "
        f"  es_actual, version, hash_tipo2, batch_id) "
        f"SELECT s.{nk}, {', '.join(f's.{a}' for a in todas)}, DATE '1900-01-01', "
        f"  DATE '9999-12-31', true, 1, s.h2, %(b)s FROM _src s "
        f"WHERE NOT EXISTS (SELECT 1 FROM {d.tabla} t WHERE t.{nk} = s.{nk})",
        p,
    ).rowcount

    # 2. Tipo 1: se sobrescribe en todas las versiones
    tipo1 = dst.execute(
        f"UPDATE {d.tabla} t SET {', '.join(f'{a} = s.{a}' for a in d.tipo1)}, batch_id = %(b)s "
        f"FROM _src s WHERE t.{nk} = s.{nk} AND t.{d.clave_sustituta} <> -1 "
        f"AND ROW({', '.join(f't.{a}' for a in d.tipo1)}) IS DISTINCT FROM "
        f"ROW({', '.join(f's.{a}' for a in d.tipo1)})",
        p,
    ).rowcount

    # 3. Tipo 2: cambios en la versión vigente
    dst.execute(
        f"CREATE TEMP TABLE _cambios ON COMMIT DROP AS "
        f"SELECT s.*, t.{d.clave_sustituta} AS clave_actual, t.version, "
        f"  (%(vigencia)s::date <= t.valido_desde) AS mismo_periodo "
        f"FROM _src s JOIN {d.tabla} t ON t.{nk} = s.{nk} AND t.es_actual "
        f"WHERE t.hash_tipo2 <> s.h2 AND t.{d.clave_sustituta} <> -1",
        p,
    )
    # 3a. Varios cambios antes de la siguiente venta: se corrige la versión vigente
    en_lugar = dst.execute(
        f"UPDATE {d.tabla} t SET {', '.join(f'{a} = c.{a}' for a in d.tipo2)}, "
        f"hash_tipo2 = c.h2, batch_id = %(b)s FROM _cambios c "
        f"WHERE t.{d.clave_sustituta} = c.clave_actual AND c.mismo_periodo",
        p,
    ).rowcount
    # 3b. Se cierra la versión vigente y se abre una nueva
    dst.execute(
        f"UPDATE {d.tabla} t SET valido_hasta = %(vigencia)s::date - 1, es_actual = false, "
        f"batch_id = %(b)s FROM _cambios c "
        f"WHERE t.{d.clave_sustituta} = c.clave_actual AND NOT c.mismo_periodo",
        p,
    )
    versiones = dst.execute(
        f"INSERT INTO {d.tabla} ({nk}, {', '.join(todas)}, valido_desde, valido_hasta, "
        f"  es_actual, version, hash_tipo2, batch_id) "
        f"SELECT c.{nk}, {', '.join(f'c.{a}' for a in todas)}, %(vigencia)s::date, "
        f"  DATE '9999-12-31', true, c.version + 1, c.h2, %(b)s "
        f"FROM _cambios c WHERE NOT c.mismo_periodo",
        p,
    ).rowcount

    # 4. Nombres de la segmentación: se refrescan según el ID de cada versión
    renombradas = 0
    for nombre, col_id, referencia in d.nombres:
        renombradas += dst.execute(
            f"UPDATE {d.tabla} t SET {nombre} = r.nombre, batch_id = %(b)s "
            f"FROM ({referencia}) AS r (id, nombre) "
            f"WHERE t.{col_id} = r.id AND t.{nombre} IS DISTINCT FROM r.nombre "
            f"AND t.{d.clave_sustituta} <> -1",
            p,
        ).rowcount

    dst.execute("DROP TABLE _src, _cambios")
    return {
        "nuevas": nuevas,
        "actualizadas": tipo1 + en_lugar + renombradas,
        "versiones_nuevas": versiones,
    }


def _cargar_puente(dst: psycopg.Connection) -> dict[str, int]:
    borradas = dst.execute(
        "DELETE FROM dw.puente_producto_grupo b WHERE NOT EXISTS ("
        "  SELECT 1 FROM stg_ready.producto_grupo s JOIN dw.dim_grupo_producto g "
        "  ON g.grupo_id = s.grupo_id WHERE s.producto_id = b.producto_id "
        "  AND g.grupo_key = b.grupo_key)"
    ).rowcount
    nuevas, actualizadas = dst.execute(
        "WITH c AS ("
        "  INSERT INTO dw.puente_producto_grupo AS t "
        "    (producto_id, grupo_key, factor_ponderacion, es_principal) "
        "  SELECT s.producto_id, g.grupo_key, s.factor_ponderacion, s.es_principal "
        "  FROM stg_ready.producto_grupo s "
        "  JOIN dw.dim_grupo_producto g ON g.grupo_id = s.grupo_id "
        "  ON CONFLICT (producto_id, grupo_key) DO UPDATE SET "
        "    factor_ponderacion = EXCLUDED.factor_ponderacion, "
        "    es_principal = EXCLUDED.es_principal "
        "  WHERE (t.factor_ponderacion, t.es_principal) IS DISTINCT FROM "
        "        (EXCLUDED.factor_ponderacion, EXCLUDED.es_principal) "
        "  RETURNING (xmax = 0) AS es_nueva) "
        "SELECT count(*) FILTER (WHERE es_nueva), count(*) FILTER (WHERE NOT es_nueva) FROM c"
    ).fetchone()
    return {"nuevas": nuevas, "actualizadas": actualizadas, "borradas": borradas}


def _cargar_hechos(dst: psycopg.Connection, batch_id: int, todo: bool) -> tuple[int, int]:
    """UPSERT de los hechos afectados por el lote (o de todos en la carga inicial)."""
    con_desconocido = " OR ".join(f"f.{c} = -1" for c in CLAVES_HECHO)
    cols = ", ".join(COLUMNAS_HECHO)
    negocio = [c for c in COLUMNAS_HECHO if c != "linea_factura_id"]
    distinto = (
        f"ROW({', '.join(f't.{c}' for c in negocio)}) IS DISTINCT FROM "
        f"ROW({', '.join(f'EXCLUDED.{c}' for c in negocio)})"
    )
    return dst.execute(
        f"WITH cand AS ("
        f"  SELECT v.* FROM stg_ready.ventas v WHERE %(todo)s "
        f"  OR v.batch_id = %(b)s "
        f"  OR v.factura_id IN (SELECT invoice_id FROM stg_clean.sales_invoices "
        f"                      WHERE _batch_id = %(b)s) "
        f"  OR v.pedido_id IN (SELECT order_id FROM stg_clean.sales_orders "
        f"                     WHERE _batch_id = %(b)s) "
        f"  OR v.linea_factura_id IN (SELECT f.linea_factura_id FROM dw.fact_ventas f "
        f"                            WHERE {con_desconocido})"
        f"), c AS ("
        f"  INSERT INTO dw.fact_ventas AS t ({cols}, batch_id) "
        f"  SELECT COALESCE(ff.fecha_key, -1), COALESCE(fp.fecha_key, -1), "
        f"    COALESCE(dc.cliente_key, -1), COALESCE(dcf.cliente_key, -1), "
        f"    COALESCE(dp.producto_key, -1), COALESCE(de.empleado_key, -1), "
        f"    COALESCE(dg.geografia_key, -1), "
        f"    v.linea_factura_id, v.factura_id, v.pedido_id, v.fecha_factura, v.cliente_id, "
        f"    v.cliente_facturacion_id, v.producto_id, v.vendedor_id, v.ciudad_id, v.cantidad, "
        f"    v.venta_bruta, v.impuesto, v.venta_neta, v.costo, v.utilidad, v.precio_unitario, "
        f"    v.tasa_impuesto, v.es_venta_bajo_costo, v.es_atipico, v.es_simulado, %(b)s "
        f"  FROM cand v "
        f"  LEFT JOIN dw.dim_fecha ff ON ff.fecha = v.fecha_factura "
        f"  LEFT JOIN dw.dim_fecha fp ON fp.fecha = v.fecha_pedido "
        f"  LEFT JOIN dw.dim_cliente dc ON dc.cliente_id = v.cliente_id "
        f"    AND v.fecha_factura BETWEEN dc.valido_desde AND dc.valido_hasta "
        f"  LEFT JOIN dw.dim_cliente dcf ON dcf.cliente_id = v.cliente_facturacion_id "
        f"    AND v.fecha_factura BETWEEN dcf.valido_desde AND dcf.valido_hasta "
        f"  LEFT JOIN dw.dim_producto dp ON dp.producto_id = v.producto_id "
        f"    AND v.fecha_factura BETWEEN dp.valido_desde AND dp.valido_hasta "
        f"  LEFT JOIN dw.dim_empleado de ON de.persona_id = v.vendedor_id "
        f"  LEFT JOIN dw.dim_geografia dg ON dg.ciudad_id = v.ciudad_id "
        f"  ON CONFLICT (linea_factura_id) DO UPDATE SET "
        f"  {', '.join(f'{c} = EXCLUDED.{c}' for c in negocio)}, "
        f"  batch_id = EXCLUDED.batch_id, cargado_en = now() "
        f"  WHERE {distinto} RETURNING (xmax = 0) AS es_nueva) "
        f"SELECT count(*) FILTER (WHERE es_nueva), count(*) FILTER (WHERE NOT es_nueva) FROM c",
        {"b": batch_id, "todo": todo},
    ).fetchone()


def reconciliar_dw(dst: psycopg.Connection) -> tuple[bool, dict[str, object]]:
    """El DW debe tener exactamente las líneas de stg_ready, con los mismos importes."""
    filas_ready, bruta_ready, filas_dw, bruta_dw = dst.execute(
        "SELECT (SELECT count(*) FROM stg_ready.ventas), "
        "(SELECT COALESCE(sum(venta_bruta), 0) FROM stg_ready.ventas), "
        "(SELECT count(*) FROM dw.fact_ventas), "
        "(SELECT COALESCE(sum(venta_bruta), 0) FROM dw.fact_ventas)"
    ).fetchone()
    detalle = {
        "filas_ready": filas_ready,
        "filas_dw": filas_dw,
        "venta_bruta_ready": bruta_ready,
        "venta_bruta_dw": bruta_dw,
    }
    return filas_ready == filas_dw and bruta_ready == bruta_dw, detalle


def cargar_dw(dst: psycopg.Connection, batch_id: int, inicial: bool) -> ResultadoDW:
    inicio = time.perf_counter()
    res = ResultadoDW()
    if inicial:
        vaciar_dw(dst)

    # Reloj de negocio: los cambios de tipo 2 rigen desde el día siguiente a la última venta
    reloj = dst.execute(
        "SELECT COALESCE(max(fecha_factura), current_date) + 1 FROM stg_ready.ventas"
    ).fetchone()[0]

    for d in DIMENSIONES_SCD1:
        res.dimensiones[d.tabla] = _cargar_scd1(dst, d, batch_id)
    for d in DIMENSIONES_SCD2:
        res.dimensiones[d.tabla] = _cargar_scd2(dst, d, batch_id, reloj.isoformat())
    res.dimensiones["dw.puente_producto_grupo"] = _cargar_puente(dst)

    res.hechos_nuevos, res.hechos_actualizados = _cargar_hechos(dst, batch_id, inicial)
    res.hechos_con_desconocido = dst.execute(
        "SELECT count(*) FROM dw.fact_ventas WHERE -1 IN (" + ", ".join(CLAVES_HECHO) + ")"
    ).fetchone()[0]
    res.reconciliado, _ = reconciliar_dw(dst)
    res.duracion_ms = int((time.perf_counter() - inicio) * 1000)
    return res
