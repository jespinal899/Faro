"""Configuración de la API, leída de variables de entorno (nunca escrita en el código).

Variables:
  API_DATABASE_URL  Conexión del rol faro_api (en Neon: la del pooler). En desarrollo, si no
                    existe, se usa ANALYTICS_DATABASE_URL.
  JWT_SECRET        Secreto para firmar las sesiones (mínimo 32 caracteres).
  JWT_MINUTOS       Duración de la sesión (por defecto 480 = 8 horas).
  COOKIE_SEGURA     "false" solo en desarrollo local sin HTTPS.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    database_url: str
    jwt_secret: str
    jwt_minutos: int
    cookie_segura: bool


@lru_cache
def config() -> Config:
    load_dotenv()
    url = os.getenv("API_DATABASE_URL") or os.getenv("ANALYTICS_DATABASE_URL")
    secreto = os.getenv("JWT_SECRET", "")
    if not url:
        raise RuntimeError("Falta API_DATABASE_URL")
    if len(secreto) < 32:
        raise RuntimeError("JWT_SECRET debe tener al menos 32 caracteres")
    return Config(
        database_url=url,
        jwt_secret=secreto,
        jwt_minutos=int(os.getenv("JWT_MINUTOS", "480")),
        cookie_segura=os.getenv("COOKIE_SEGURA", "true").lower() != "false",
    )
