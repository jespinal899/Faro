"""Alertas y notificaciones (Fase 7, preguntas P12-P14). Decisión D-26.

    uv run python -m notifications evaluar [--neon] [--sin-correo] [--sin-ia]
    uv run python -m notifications prueba-correo

Evalúa las reglas del catálogo (alerta.regla) sobre los datos del DW y el pronóstico, registra
las alertas nuevas (sin duplicados), agrega una explicación generada por IA (identificada como
tal) y las envía por correo con reintentos, registrando cada intento.
"""
