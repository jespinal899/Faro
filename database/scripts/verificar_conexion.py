"""Verifica que Python puede conectarse a las dos bases del proyecto.

Uso:
    uv run python database/scripts/verificar_conexion.py

Lee las cadenas de conexión desde el archivo .env (nunca escritas en el código).
Sirve igual para el entorno local (Docker) y para producción (Neon):
solo cambian las variables SOURCE_DATABASE_URL y ANALYTICS_DATABASE_URL.
"""

import os
import sys

import psycopg
from dotenv import load_dotenv

BASES = {
    "Fuente (OLTP)": "SOURCE_DATABASE_URL",
    "Analítica (staging + DW)": "ANALYTICS_DATABASE_URL",
}


def verificar(nombre: str, variable: str) -> bool:
    url = os.getenv(variable)
    if not url:
        print(f"[FALTA] {nombre}: la variable {variable} no está definida en .env")
        return False
    try:
        with psycopg.connect(url, connect_timeout=10) as conn:
            fila = conn.execute(
                "SELECT current_database(), current_user, split_part(version(), ' ', 2)"
            ).fetchone()
        base, usuario, version = fila
        print(f"[OK]    {nombre}: base={base} usuario={usuario} PostgreSQL {version}")
        return True
    except psycopg.Error as error:
        # No imprimimos la URL para no exponer la contraseña
        print(f"[ERROR] {nombre} ({variable}): {error}")
        return False


def main() -> int:
    load_dotenv()
    resultados = [verificar(nombre, var) for nombre, var in BASES.items()]
    return 0 if all(resultados) else 1


if __name__ == "__main__":
    sys.exit(main())
