"""Correo de alerta por SMTP (Gmail con contraseña de aplicación) con reintentos registrados.

Variables: SMTP_USUARIO, SMTP_PASSWORD, ALERTAS_DESTINO (y opcionales SMTP_HOST, SMTP_PUERTO,
FARO_URL). Nunca se imprimen ni se guardan en la base: el registro solo dice si se envió.
"""

from __future__ import annotations

import os
import smtplib
import ssl
import time
from dataclasses import dataclass
from email.message import EmailMessage

INTENTOS_POR_EVALUACION = 3
ESPERAS_S = (2, 4)  # entre el 1.º y el 2.º intento, y entre el 2.º y el 3.º
SEVERIDAD = {"advertencia": "Advertencia", "critica": "CRÍTICA"}


@dataclass(frozen=True)
class ConfigCorreo:
    usuario: str
    clave: str
    destino: str
    host: str = "smtp.gmail.com"
    puerto: int = 587
    url_dashboard: str = "https://faro-fawn-kappa.vercel.app"

    @classmethod
    def desde_entorno(cls) -> ConfigCorreo | None:
        usuario, clave, destino = (
            os.getenv("SMTP_USUARIO", "").strip(),
            os.getenv("SMTP_PASSWORD", "").replace(" ", ""),
            os.getenv("ALERTAS_DESTINO", "").strip(),
        )
        if not (usuario and clave and destino):
            return None
        return cls(
            usuario=usuario,
            clave=clave,
            destino=destino,
            host=os.getenv("SMTP_HOST", "smtp.gmail.com"),
            puerto=int(os.getenv("SMTP_PUERTO", "587")),
            url_dashboard=os.getenv("FARO_URL", "https://faro-fawn-kappa.vercel.app"),
        )


def _usd(v) -> str:
    return "—" if v is None else f"USD {float(v):,.2f}"


def componer(a: dict, cfg: ConfigCorreo) -> EmailMessage:
    """Correo con el contenido mínimo de la guía: id y fecha, tipo y severidad, indicador y
    entidad, valor, umbral, período, origen, explicación y acción (IA identificada) y estado."""
    m = EmailMessage()
    m["Subject"] = (
        f"[Faro] Alerta {SEVERIDAD.get(a['severidad'], a['severidad'])}: "
        f"{a['regla_nombre']} · {a['entidad']} (#{a['alerta_id']})"
    )
    m["From"] = f"Faro alertas <{cfg.usuario}>"
    m["To"] = cfg.destino
    detalle = a.get("detalle") or {}
    es_modelo = a["origen"] == "modelo"
    origen = "modelo de ML" if es_modelo else "regla de negocio"
    prediccion = " (PREDICCIÓN)" if es_modelo else ""
    lineas = [
        f"Alerta #{a['alerta_id']} · {a['creada_en']:%d/%m/%Y %H:%M} UTC",
        "",
        f"Tipo: {a['regla_nombre']} (origen: {origen})",
        f"Severidad: {SEVERIDAD.get(a['severidad'], a['severidad'])}",
        f"Indicador: {a['indicador']} · Entidad: {a['entidad']}",
        f"Valor observado{prediccion}: {_usd(a['valor_observado'])}",
        f"Umbral: {_usd(a['umbral'])}"
        + (f" · Referencia: {_usd(a['referencia'])}" if a.get("referencia") is not None else ""),
        f"Período: {a['periodo_desde']:%d/%m/%Y} al {a['periodo_hasta']:%d/%m/%Y}",
    ]
    if detalle.get("version_modelo"):
        lineas.append(
            f"Modelo: {detalle['version_modelo']} · horizonte: {detalle.get('horizonte')} semana(s)"
        )
    lineas += ["", a["mensaje"]]
    if a.get("explicacion_ia"):
        lineas += [
            "",
            f"Explicación (GENERADA POR IA, {a.get('ia_modelo')}): {a['explicacion_ia']}",
            f"Acción recomendada (GENERADA POR IA): {a.get('accion_recomendada_ia') or '—'}",
        ]
    if a.get("incluye_simulados"):
        lineas += ["", "Nota: los datos de esta alerta incluyen ventas SIMULADAS (demostración)."]
    lineas += [
        "",
        f"Estado: {a['estado']}. Gestiónala en {cfg.url_dashboard} (pestaña Alertas).",
    ]
    m.set_content("\n".join(lineas))
    return m


def enviar(mensaje: EmailMessage, cfg: ConfigCorreo) -> None:
    with smtplib.SMTP(cfg.host, cfg.puerto, timeout=30) as s:
        s.starttls(context=ssl.create_default_context())
        s.login(cfg.usuario, cfg.clave)
        s.send_message(mensaje)


def enviar_con_reintentos(alerta: dict, cfg: ConfigCorreo, registrar, dormir=time.sleep) -> bool:
    """Hasta 3 intentos en esta evaluación (con espera creciente); cada intento se registra.
    registrar(intento, resultado, error). Devuelve True si se envió."""
    previos = int(alerta.get("intentos", 0))
    for k in range(INTENTOS_POR_EVALUACION):
        intento = previos + k + 1
        try:
            enviar(componer(alerta, cfg), cfg)
        except (smtplib.SMTPException, OSError) as e:
            registrar(intento, "fallido", f"{type(e).__name__}: {e}")
            if k < INTENTOS_POR_EVALUACION - 1:
                dormir(ESPERAS_S[k])
            continue
        registrar(intento, "enviado", None)
        return True
    return False
