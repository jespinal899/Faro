"""Línea de comandos de las alertas.

    uv run python -m notifications evaluar [--neon] [--disparador manual] [--sin-correo] [--sin-ia]
    uv run python -m notifications prueba-correo

Conexión: --neon usa NEON_ALERTAS_ANALYTICS_URL (rol faro_alertas); si no, ALERTAS_DATABASE_URL
(la usa el workflow de GitHub) o, en desarrollo, ANALYTICS_DATABASE_URL.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import UTC, datetime
from email.message import EmailMessage
from pathlib import Path

from dotenv import load_dotenv

from etl.db import conectar

from .correo import ConfigCorreo, enviar
from .evaluar import evaluar

RAIZ = Path(__file__).resolve().parents[1]


def _resumen_github(texto: str) -> None:
    destino = os.getenv("GITHUB_STEP_SUMMARY")
    if destino:
        with open(destino, "a", encoding="utf-8") as f:
            f.write(texto + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m notifications", description=__doc__)
    acciones = parser.add_subparsers(dest="accion", required=True)
    p = acciones.add_parser("evaluar", help="evalúa las reglas, registra y envía las alertas")
    p.add_argument("--neon", action="store_true", help="usar NEON_ALERTAS_ANALYTICS_URL del .env")
    p.add_argument("--disparador", default="manual", help="cron | manual | demo | ci")
    p.add_argument("--sin-correo", action="store_true", help="registrar sin enviar correos")
    p.add_argument("--sin-ia", action="store_true", help="sin explicación generada por IA")
    acciones.add_parser("prueba-correo", help="envía un correo de prueba (no toca la base)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    for ruidoso in ("httpx2", "httpcore2", "openai"):
        logging.getLogger(ruidoso).setLevel(logging.WARNING)
    load_dotenv(RAIZ / ".env")

    if args.accion == "prueba-correo":
        cfg = ConfigCorreo.desde_entorno()
        if cfg is None:
            print("Faltan SMTP_USUARIO, SMTP_PASSWORD o ALERTAS_DESTINO")
            return 1
        m = EmailMessage()
        m["Subject"], m["From"], m["To"] = "[Faro] Correo de prueba", cfg.usuario, cfg.destino
        m.set_content(
            f"Prueba del canal de alertas de Faro ({datetime.now(UTC):%d/%m/%Y %H:%M} UTC)."
        )
        enviar(m, cfg)
        print("Correo de prueba enviado")
        return 0

    if args.neon:
        url = os.getenv("NEON_ALERTAS_ANALYTICS_URL")
    else:
        url = os.getenv("ALERTAS_DATABASE_URL") or os.getenv("ANALYTICS_DATABASE_URL")
    if not url:
        print(
            "Falta la conexión (NEON_ALERTAS_ANALYTICS_URL, ALERTAS_DATABASE_URL "
            "o ANALYTICS_DATABASE_URL)"
        )
        return 1
    with conectar(url) as conn:
        r = evaluar(
            conn,
            disparador=args.disparador,
            enviar_correos=not args.sin_correo,
            usar_ia=not args.sin_ia,
        )
        filas = conn.execute(
            "SELECT alerta_id, regla, severidad, entidad, mensaje FROM alerta.alerta "
            "WHERE evaluacion_id = %s ORDER BY alerta_id",
            (r.evaluacion_id,),
        ).fetchall()
    texto = [
        f"### Alertas · evaluación {r.evaluacion_id}",
        "",
        f"Reglas evaluadas: {r.reglas_evaluadas} · alertas nuevas: {len(r.nuevas)} · "
        f"ya registradas antes (sin duplicar): {r.ya_existentes} · explicadas por IA: "
        f"{r.explicadas_por_ia} · correos enviados: {r.correos_enviados} · fallidos: "
        f"{r.correos_fallidos}" + ("" if r.correo_configurado else " (correo no configurado)"),
        "",
    ]
    texto += [f"- #{i} [{s}] {regla} · {e}: {m}" for i, regla, s, e, m in filas] or [
        "Ninguna alerta nueva en esta evaluación."
    ]
    salida = "\n".join(texto)
    print(salida)
    _resumen_github(salida)
    return 0


if __name__ == "__main__":
    sys.exit(main())
