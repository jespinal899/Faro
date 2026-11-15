"""Crea (o actualiza) un usuario del dashboard. En la base solo queda el hash Argon2.

La contraseña:
  - se toma de la variable de entorno FARO_NUEVA_PASSWORD si existe, o
  - se genera aleatoria y se guarda en .env como FARO_PASSWORD_<USUARIO> (no se imprime).

Uso:
    uv run python database/scripts/crear_usuario.py --usuario demo --nombre "Usuario Demo"
    uv run python database/scripts/crear_usuario.py --usuario admin --nombre "Admin" \
        --rol admin --neon
"""

from __future__ import annotations

import argparse
import os
import re
import secrets
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
from backend.app.seguridad import hash_password  # noqa: E402

ENV = RAIZ / ".env"


def _guardar(variable: str, valor: str) -> None:
    texto = ENV.read_text(encoding="utf-8") if ENV.exists() else ""
    linea = f"{variable}={valor}"
    if re.search(rf"^{variable}=", texto, flags=re.M):
        texto = re.sub(rf"^{variable}=.*$", lambda _m: linea, texto, flags=re.M)
    else:
        texto = texto.rstrip("\n") + "\n" + linea + "\n"
    ENV.write_text(texto, encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Crea o actualiza un usuario del dashboard")
    parser.add_argument("--usuario", required=True)
    parser.add_argument("--nombre", required=True)
    parser.add_argument("--rol", choices=["analista", "admin"], default="analista")
    parser.add_argument("--neon", action="store_true", help="crear en producción (Neon)")
    args = parser.parse_args()

    usuario = args.usuario.strip().lower()
    if not re.fullmatch(r"[a-z0-9._-]{3,40}", usuario):
        parser.error("usuario: 3 a 40 caracteres a-z, 0-9, punto, guion o guion bajo")

    load_dotenv(ENV)
    # Se crea con el dueño de la base (el rol de la API no puede escribir contraseñas)
    url = os.getenv("NEON_ANALYTICS_DATABASE_URL" if args.neon else "ANALYTICS_DATABASE_URL")
    if not url:
        print("Falta la conexión del dueño de la base analítica en .env")
        return 1

    password = os.getenv("FARO_NUEVA_PASSWORD")
    variable = f"FARO_PASSWORD_{usuario.upper().replace('.', '_').replace('-', '_')}"
    if args.neon:
        variable = "NEON_" + variable
    generada = not password
    if generada:
        password = secrets.token_urlsafe(12)

    with psycopg.connect(url, connect_timeout=20) as conn:
        conn.execute(
            "INSERT INTO app.usuario (usuario, nombre, password_hash, rol) "
            "VALUES (%s, %s, %s, %s) ON CONFLICT (usuario) DO UPDATE SET "
            "nombre = EXCLUDED.nombre, password_hash = EXCLUDED.password_hash, "
            "rol = EXCLUDED.rol, activo = true, intentos_fallidos = 0, bloqueado_hasta = NULL",
            (usuario, args.nombre, hash_password(password), args.rol),
        )
    if generada:
        _guardar(variable, password)
        print(f"[OK] Usuario '{usuario}' ({args.rol}). Contraseña guardada en .env: {variable}")
    else:
        print(f"[OK] Usuario '{usuario}' ({args.rol}) con la contraseña de FARO_NUEVA_PASSWORD")
    return 0


if __name__ == "__main__":
    sys.exit(main())
