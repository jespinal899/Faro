"""Una evaluación de alertas de punta a punta, registrada en alerta.evaluacion.

1. Lee las reglas activas y sus umbrales (alerta.regla).
2. Evalúa cada regla sobre la última semana completa y el pronóstico vigente.
3. Registra las alertas NUEVAS (la clave del evento impide duplicados al repetir).
4. A cada alerta nueva le agrega una explicación y una acción GENERADAS POR IA (opcional).
5. Envía por correo las alertas pendientes, con reintentos; cada intento queda registrado y
   las que fallen se reintentan en la siguiente evaluación.
"""

from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass, field

from . import ia, registro, reglas
from .correo import ConfigCorreo, enviar_con_reintentos

log = logging.getLogger("faro.alertas")


@dataclass
class Resultado:
    evaluacion_id: int
    reglas_evaluadas: int = 0
    nuevas: list[int] = field(default_factory=list)
    ya_existentes: int = 0
    explicadas_por_ia: int = 0
    correos_enviados: int = 0
    correos_fallidos: int = 0
    correo_configurado: bool = False


def evaluar(
    conn,
    *,
    disparador: str = "manual",
    enviar_correos: bool = True,
    usar_ia: bool = True,
    config_correo: ConfigCorreo | None = None,
    cliente_ia=None,
    dormir=time.sleep,
) -> Resultado:
    r = Resultado(evaluacion_id=registro.iniciar_evaluacion(conn, disparador))
    try:
        umbrales = registro.reglas_activas(conn)
        desde, hasta, _ = registro.rango(conn)
        candidatas: list[reglas.Alerta] = []
        if "caida_ventas" in umbrales:
            candidatas += reglas.caida_ventas(
                registro.ventas_semanales(conn), desde, hasta, umbrales["caida_ventas"]
            )
        if "pronostico_bajo" in umbrales:
            pronostico, historia = registro.pronostico(conn)
            candidatas += reglas.pronostico_bajo(pronostico, historia, umbrales["pronostico_bajo"])
        if "ventas_bajo_costo" in umbrales:
            candidatas += reglas.ventas_bajo_costo(
                registro.bajo_costo(conn), hasta, umbrales["ventas_bajo_costo"]
            )
        r.reglas_evaluadas = len(umbrales)

        for alerta in candidatas:
            alerta_id = registro.insertar(conn, alerta, r.evaluacion_id)
            if alerta_id is None:
                r.ya_existentes += 1
                continue
            r.nuevas.append(alerta_id)
            if usar_ia:
                explicacion = ia.explicar(asdict(alerta), cliente=cliente_ia)
                if explicacion:
                    registro.guardar_explicacion(conn, alerta_id, *explicacion)
                    r.explicadas_por_ia += 1
        conn.commit()

        cfg = config_correo if config_correo is not None else ConfigCorreo.desde_entorno()
        r.correo_configurado = cfg is not None
        if enviar_correos and cfg is not None:
            for alerta in registro.pendientes_de_envio(conn):
                enviado = enviar_con_reintentos(
                    alerta,
                    cfg,
                    lambda intento, resultado, error, i=alerta["alerta_id"]: (
                        registro.registrar_envio(conn, i, intento, resultado, error)
                    ),
                    dormir=dormir,
                )
                if enviado:
                    r.correos_enviados += 1
                else:
                    r.correos_fallidos += 1

        registro.cerrar_evaluacion(
            conn,
            r.evaluacion_id,
            estado="exitosa",
            reglas=r.reglas_evaluadas,
            nuevas=len(r.nuevas),
            correos=r.correos_enviados,
        )
        return r
    except Exception as e:
        conn.rollback()
        registro.cerrar_evaluacion(
            conn, r.evaluacion_id, estado="fallida", error=f"{type(e).__name__}: {e}"[:500]
        )
        raise
