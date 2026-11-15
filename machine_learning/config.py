"""Parámetros del pronóstico. Cada valor está justificado en documentation/modelos/modelo-ml.md."""

from __future__ import annotations

NOMBRE_MODELO = "pronostico_semanal_grupo"

# Se pronostican las 4 semanas siguientes a la última semana completa (un mes de compras).
HORIZONTES = (1, 2, 3, 4)

# Nivel reciente de un grupo = media de sus últimas 8 semanas. El modelo predice la venta
# RELATIVA a ese nivel: así un solo modelo sirve para grupos de tamaños muy distintos y la
# tendencia de crecimiento (~8 % anual) no lo saca de su rango de entrenamiento.
SEMANAS_NIVEL = 8
SEMANAS_ANIO = 52

# Semanas previas al origen que necesitan las variables: un año más el nivel de hace un año.
HISTORIA_REQUERIDA = SEMANAS_ANIO + SEMANAS_NIVEL

# Separación temporal por la semana pronosticada: las últimas 16 semanas son la PRUEBA.
# Antes de ellas, validación cruzada temporal: 4 pliegues de 13 semanas (un año completo, todas
# las estaciones); cada pliegue se valida con un modelo entrenado SOLO con semanas anteriores.
SEMANAS_PRUEBA = 16
PLIEGUES = 4
SEMANAS_PLIEGUE = 13
SEMANAS_VALIDACION = PLIEGUES * SEMANAS_PLIEGUE
# El primer pliegue debe tener al menos medio año de semanas para entrenar.
SEMANAS_MINIMAS_ENTRENAMIENTO = 26

# Un grupo entra al modelo si tiene al menos 2 años de historia continua. "Novelty Items"
# (chocolates lanzados en enero de 2016) no la tiene: se informa como excluido, sin inventar.
HISTORIA_MINIMA = 104

# Rango probable del pronóstico: del percentil 10 al 90 del error en validación (80 %).
COBERTURA = 0.80
SEMILLA = 42

# Configuraciones candidatas. Se elige la de menor WAPE en VALIDACIÓN (nunca en prueba).
# "rezagos" = solo las 13 semanas recientes; "rezagos+contexto" suma tendencia, estacionalidad
# y calendario, para que la validación muestre si esa información aporta.
CANDIDATOS: tuple[dict, ...] = tuple(
    [
        {"algoritmo": "ridge", "variables": v, "alpha": a}
        for v in ("rezagos", "rezagos+contexto")
        for a in (10.0, 100.0, 1000.0)
    ]
    + [
        {"algoritmo": "hgb", "variables": v, "max_depth": 2, "learning_rate": 0.03, "max_iter": 200}
        for v in ("rezagos", "rezagos+contexto")
    ]
)
