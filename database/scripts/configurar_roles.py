"""Activa los roles de mínimo privilegio en un entorno y guarda sus conexiones en .env.

Pasos (como DUEÑO de las bases):
  1. Aplica database/security/roles_fuente.sql y roles_analitica.sql (permisos).
  2. Asigna a cada rol una contraseña aleatoria nueva y le habilita el acceso.
  3. Escribe en .env las cadenas de conexión de cada rol.

Cada ejecución ROTA las contraseñas. Nunca se imprimen ni se guardan en el repositorio.

Uso:
    uv run python database/scripts/configurar_roles.py --entorno neon
    uv run python database/scripts/configurar_roles.py --entorno local

Después, en producción, subir las conexiones nuevas a GitHub (ver el README).
"""

from __future__ import annotations

import argparse
import os
import re
import secrets
import sys
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

import psycopg
from dotenv import load_dotenv
from psycopg import sql

RAIZ = Path(__file__).resolve().parents[2]
SEGURIDAD = RAIZ / "database" / "security"
ENV = RAIZ / ".env"

# entorno -> (variable con la conexión del dueño de la fuente, de la analítica, prefijo de salida)
ENTORNOS = {
    "neon": ("NEON_SOURCE_DATABASE_URL", "NEON_ANALYTICS_DATABASE_URL", "NEON_"),
    "local": ("SOURCE_DATABASE_URL", "ANALYTICS_DATABASE_URL", "LOCAL_"),
}
# rol -> (base: fuente/analitica, variable de salida sin prefijo)
ROLES = {
    "etl_lector": ("fuente", "ETL_SOURCE_URL"),
    "wwi_app": ("fuente", "APP_SOURCE_URL"),
    "faro_etl": ("analitica", "ETL_ANALYTICS_URL"),
}


def _url_del_rol(url_dueno: str, rol: str, clave: str) -> str:
    partes = urlsplit(url_dueno)
    host = partes.netloc.rsplit("@", 1)[-1]
    return urlunsplit(partes._replace(netloc=f"{rol}:{quote(clave, safe='')}@{host}"))


def _guardar_en_env(valores: dict[str, str]) -> None:
    texto = ENV.read_text(encoding="utf-8") if ENV.exists() else ""
    for variable, valor in valores.items():
        linea = f"{variable}={valor}"
        if re.search(rf"^{variable}=", texto, flags=re.M):
            texto = re.sub(rf"^{variable}=.*$", lambda _m, li=linea: li, texto, flags=re.M)
        else:
            texto = texto.rstrip("\n") + "\n" + linea + "\n"
    ENV.write_text(texto, encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Activa los roles de mínimo privilegio")
    parser.add_argument("--entorno", choices=ENTORNOS, required=True)
    args = parser.parse_args()

    load_dotenv(ENV)
    var_fuente, var_analitica, prefijo = ENTORNOS[args.entorno]
    duenos = {"fuente": os.getenv(var_fuente), "analitica": os.getenv(var_analitica)}
    if not all(duenos.values()):
        print(f"Faltan {var_fuente} o {var_analitica} en .env")
        return 1

    nuevas = {}
    for base, url in duenos.items():
        with psycopg.connect(url, connect_timeout=20) as conn:
            conn.execute((SEGURIDAD / f"roles_{base}.sql").read_text(encoding="utf-8"))
            for rol, (base_rol, variable) in ROLES.items():
                if base_rol != base:
                    continue
                clave = secrets.token_urlsafe(24)
                conn.execute(
                    sql.SQL("ALTER ROLE {} LOGIN PASSWORD {}").format(
                        sql.Identifier(rol), sql.Literal(clave)
                    )
                )
                nuevas[prefijo + variable] = _url_del_rol(url, rol, clave)
                print(f"[OK] {rol}: permisos aplicados y contraseña rotada -> {prefijo}{variable}")

    # Comprobar que cada rol realmente puede conectarse antes de guardar
    for variable, url in nuevas.items():
        with psycopg.connect(url, connect_timeout=20) as conn:
            usuario = conn.execute("SELECT current_user").fetchone()[0]
        print(f"[OK] conexión verificada como {usuario} ({variable})")

    _guardar_en_env(nuevas)
    print(f"Conexiones guardadas en .env ({len(nuevas)} variables). No se muestran por seguridad.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
