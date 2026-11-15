"""Lectura de las entradas del evaluador y registro de alertas, evaluaciones y envíos.

Todo con el rol faro_alertas: lee las vistas de entrada del esquema alerta y el pronóstico
aprobado; escribe solo en alerta.alerta, alerta.envio y alerta.evaluacion.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date

from .reglas import Alerta

MAX_INTENTOS_TOTALES = 6  # por alerta, sumando todas las evaluaciones


# ------------------------------------------------------------------ entradas


def rango(conn) -> tuple[date, date, date | None]:
    return conn.execute("SELECT desde, hasta, hasta_real FROM alerta.rango_datos").fetchone()


def reglas_activas(conn) -> dict[str, float]:
    filas = conn.execute("SELECT codigo, umbral FROM alerta.regla WHERE activa").fetchall()
    return {codigo: float(umbral) for codigo, umbral in filas}


def ventas_semanales(conn) -> dict[date, tuple[float, bool]]:
    filas = conn.execute(
        "SELECT semana, venta_neta, incluye_simulados FROM alerta.ventas_semanales_total"
    ).fetchall()
    return {s: (float(v), bool(sim)) for s, v, sim in filas}


def bajo_costo(conn) -> dict[date, dict]:
    filas = conn.execute(
        "SELECT semana, lineas, facturas, perdida, venta_neta, incluye_simulados "
        "FROM alerta.bajo_costo_semanal"
    ).fetchall()
    return {
        s: {
            "lineas": int(lineas),
            "facturas": int(facturas),
            "perdida": float(perdida),
            "venta_neta": float(venta),
            "incluye_simulados": bool(sim),
        }
        for s, lineas, facturas, perdida, venta, sim in filas
    }


def pronostico(conn) -> tuple[list[dict], dict[str, list[float]]]:
    """Pronóstico vigente y, por grupo, sus ventas semanales completas hasta el origen."""
    columnas = (
        "grupo, semana, horizonte, venta_neta_pronosticada, inferior, superior, version, "
        "origen, usa_datos_simulados"
    )
    cur = conn.execute(f"SELECT {columnas} FROM api.pronostico ORDER BY grupo, semana")
    nombres = [c.name for c in cur.description]
    filas = [
        {
            k: (float(v) if k in ("venta_neta_pronosticada", "inferior", "superior") else v)
            for k, v in zip(nombres, f, strict=True)
        }
        for f in cur.fetchall()
    ]
    if not filas:
        return [], {}
    origen = filas[0]["origen"]
    historia: dict[str, list[float]] = {}
    for grupo, venta in conn.execute(
        "SELECT grupo, venta_neta FROM api.ventas_semanales "
        "WHERE es_completa AND semana <= %s ORDER BY grupo, semana",
        (origen,),
    ):
        historia.setdefault(grupo, []).append(float(venta))
    return filas, historia


# ------------------------------------------------------------------ escritura


def iniciar_evaluacion(conn, disparador: str) -> int:
    evaluacion_id = conn.execute(
        "INSERT INTO alerta.evaluacion (disparador) VALUES (%s) RETURNING evaluacion_id",
        (disparador,),
    ).fetchone()[0]
    conn.commit()
    return evaluacion_id


def cerrar_evaluacion(
    conn,
    evaluacion_id: int,
    *,
    estado: str,
    reglas: int = 0,
    nuevas: int = 0,
    correos: int = 0,
    error: str | None = None,
) -> None:
    conn.execute(
        "UPDATE alerta.evaluacion SET fin = now(), estado = %s, reglas_evaluadas = %s, "
        "alertas_nuevas = %s, correos_enviados = %s, error = %s WHERE evaluacion_id = %s",
        (estado, reglas, nuevas, correos, error, evaluacion_id),
    )
    conn.commit()


def insertar(conn, alerta: Alerta, evaluacion_id: int) -> int | None:
    """Inserta la alerta si su evento es nuevo. Devuelve su id, o None si ya existía."""
    d = asdict(alerta)
    fila = conn.execute(
        """
        INSERT INTO alerta.alerta (evaluacion_id, regla, clave_evento, severidad, origen,
                                   indicador, entidad, valor_observado, umbral, referencia,
                                   periodo_desde, periodo_hasta, detalle, mensaje,
                                   incluye_simulados)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (clave_evento) DO NOTHING
        RETURNING alerta_id
        """,
        (
            evaluacion_id,
            d["regla"],
            d["clave_evento"],
            d["severidad"],
            d["origen"],
            d["indicador"],
            d["entidad"],
            round(d["valor_observado"], 2),
            round(d["umbral"], 2),
            None if d["referencia"] is None else round(d["referencia"], 2),
            d["periodo_desde"],
            d["periodo_hasta"],
            json.dumps(d["detalle"], ensure_ascii=False, default=str),
            d["mensaje"],
            d["incluye_simulados"],
        ),
    ).fetchone()
    return fila[0] if fila else None


def guardar_explicacion(conn, alerta_id: int, explicacion: str, accion: str, modelo: str) -> None:
    conn.execute(
        "UPDATE alerta.alerta SET explicacion_ia = %s, accion_recomendada_ia = %s, ia_modelo = %s "
        "WHERE alerta_id = %s",
        (explicacion, accion, modelo, alerta_id),
    )


def pendientes_de_envio(conn) -> list[dict]:
    """Alertas sin un correo enviado y con intentos disponibles (las descartadas no se envían)."""
    cur = conn.execute(
        """
        SELECT a.alerta_id, a.creada_en, a.regla, r.nombre AS regla_nombre, a.severidad,
               a.origen, a.indicador, a.entidad, a.valor_observado, a.umbral, a.referencia,
               a.periodo_desde, a.periodo_hasta, a.detalle, a.mensaje, a.explicacion_ia,
               a.accion_recomendada_ia, a.ia_modelo, a.incluye_simulados, a.estado,
               coalesce(e.intentos, 0) AS intentos
        FROM alerta.alerta a
        JOIN alerta.regla r ON r.codigo = a.regla
        LEFT JOIN (
            SELECT alerta_id, count(*) AS intentos, bool_or(resultado = 'enviado') AS enviado
            FROM alerta.envio WHERE canal = 'correo' GROUP BY alerta_id
        ) e ON e.alerta_id = a.alerta_id
        WHERE a.estado <> 'descartada'
          AND NOT coalesce(e.enviado, false)
          AND coalesce(e.intentos, 0) < %s
        ORDER BY a.alerta_id
        """,
        (MAX_INTENTOS_TOTALES,),
    )
    nombres = [c.name for c in cur.description]
    return [dict(zip(nombres, f, strict=True)) for f in cur.fetchall()]


def registrar_envio(conn, alerta_id: int, intento: int, resultado: str, error: str | None) -> None:
    conn.execute(
        "INSERT INTO alerta.envio (alerta_id, canal, intento, resultado, error) "
        "VALUES (%s, 'correo', %s, %s, %s)",
        (alerta_id, intento, resultado, (error or "")[:500] or None),
    )
    conn.commit()
