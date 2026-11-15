# Evaluación del pronóstico de ventas — local

> Generado por `python -m machine_learning entrenar` (2026-11-15 14:50 UTC). Versión **20261115.145023** · commit `fac7b24`.
> Diseño y justificación: [modelo-ml.md](../modelos/modelo-ml.md).

## Resultado en dos líneas

- **Prueba** (semanas que el modelo nunca vio): error de **13.5 %** del volumen vendido (WAPE), contra **14.6 %** de la mejor línea base (*el promedio de las últimas 13 semanas (un trimestre)*): **7.0 % menos error**.
- **Validación** (un año, 4 pliegues): modelo **11.5 %** contra **11.5 %** de la misma línea base — en un año completo **empatan**: la mejora en prueba no está garantizada en todas las estaciones.

## 1. Datos usados (solo ventas reales, semanas completas de lunes a sábado)

- Serie: semanas del **2013-01-07** al **2016-05-23** (177 semanas), 8 grupos.
- Huella de los datos (md5): `21591ef4a1f7104fc6398abbb782a81e`.
- Las ventas **simuladas** no se usan para entrenar ni para evaluar.

| Grupo | Semanas | Venta media semanal (USD) | Variabilidad (CV) | Crecimiento último año | Participación | Semanas sin venta |
|---|---:|---:|---:|---:|---:|---:|
| Clothing | 177 | 72,215 | 19.1 % | -0.4 % | 7.5 % | 0 |
| Computing Novelties | 177 | 5,836 | 51.0 % | +0.4 % | 0.6 % | 0 |
| Furry Footwear | 177 | 28,812 | 16.1 % | +3.6 % | 3.0 % | 0 |
| Mugs | 177 | 17,816 | 15.4 % | +4.4 % | 1.9 % | 0 |
| Packaging Materials | 177 | 565,995 | 16.3 % | -0.6 % | 58.8 % | 0 |
| T-Shirts | 177 | 160,015 | 13.9 % | +0.2 % | 16.6 % | 0 |
| Toys | 177 | 84,637 | 19.0 % | +1.9 % | 8.8 % | 0 |
| USB Novelties | 177 | 26,548 | 25.2 % | -6.9 % | 2.8 % | 0 |

**Grupos excluidos** (no se fabrica un pronóstico sin respaldo):

- Novelty Items: historia insuficiente: 22 semanas desde 2015-12-28 (mínimo 104).

## 2. Separación temporal (por semana pronosticada, nunca al azar)

| Conjunto | Semanas pronosticadas | Para qué se usa |
|---|---|---|
| Validación, pliegue 1 | 2015-02-09 – 2015-05-04 | Medir candidatos entrenados solo con semanas anteriores al 2015-02-09 |
| Validación, pliegue 2 | 2015-05-11 – 2015-08-03 | Medir candidatos entrenados solo con semanas anteriores al 2015-05-11 |
| Validación, pliegue 3 | 2015-08-10 – 2015-11-02 | Medir candidatos entrenados solo con semanas anteriores al 2015-08-10 |
| Validación, pliegue 4 | 2015-11-09 – 2016-02-01 | Medir candidatos entrenados solo con semanas anteriores al 2015-11-09 |
| Prueba | desde 2016-02-08 (512 muestras) | Medir **una sola vez** el resultado final |

Validación cruzada temporal: los 4 pliegues cubren un año completo (todas las estaciones) y cada modelo se entrena solo con el pasado de su pliegue. Una muestra = un grupo, una semana de origen y un horizonte (1 a 4 semanas); sus variables solo usan semanas hasta el origen.

## 3. Líneas base y selección del modelo (validación fuera de pliegue)

| Línea base | Qué predice | WAPE validación |
|---|---|---:|
| ingenuo | la venta de la última semana conocida | 15.0 % |
| media_movil_4 | el promedio de las últimas 4 semanas | 11.6 % |
| media_movil_13 | el promedio de las últimas 13 semanas (un trimestre) | 11.5 % ← mejor |
| estacional | la venta de la misma semana del año anterior | 17.4 % |

| Candidato | Pliegue 1 | Pliegue 2 | Pliegue 3 | Pliegue 4 | WAPE validación |
|---|---:|---:|---:|---:|---:|
| `ridge[rezagos](alpha=10.0)` | 11.7 % | 11.6 % | 12.6 % | 11.8 % | 11.9 % |
| `ridge[rezagos](alpha=100.0)` | 11.6 % | 11.6 % | 12.5 % | 11.8 % | 11.9 % |
| `ridge[rezagos](alpha=1000.0)` | 11.1 % | 11.8 % | 12.0 % | 11.7 % | 11.6 % |
| `ridge[rezagos+contexto](alpha=10.0)` | 13.7 % | 10.5 % | 11.4 % | 13.8 % | 12.3 % |
| `ridge[rezagos+contexto](alpha=100.0)` | 12.5 % | 10.7 % | 11.3 % | 13.8 % | 12.1 % |
| `ridge[rezagos+contexto](alpha=1000.0)` | 11.0 % | 11.3 % | 11.3 % | 12.9 % | 11.6 % |
| `hgb[rezagos](max_depth=2, learning_rate=0.03, max_iter=200)` | 11.9 % | 11.1 % | 12.2 % | 11.9 % | 11.7 % |
| `hgb[rezagos+contexto](max_depth=2, learning_rate=0.03, max_iter=200)` | 12.0 % | 12.0 % | 9.6 % | 12.2 % | 11.5 % ← elegido |

## 4. Resultado en prueba (semanas no usadas para entrenar ni elegir)

| Pronóstico | WAPE | MAE (USD) | RMSE (USD) | sMAPE | Sesgo |
|---|---:|---:|---:|---:|---:|
| **Modelo** | 13.5 % | 16,992 | 39,024 | 17.8 % | +1.7 % |
| Línea base: ingenuo | 18.1 % | 22,730 | 52,685 | 23.6 % | -2.7 % |
| Línea base: media_movil_4 | 14.7 % | 18,388 | 41,794 | 19.4 % | -3.6 % |
| Línea base: media_movil_13 | 14.6 % | 18,276 | 41,600 | 18.8 % | -4.4 % |
| Línea base: estacional | 19.5 % | 24,469 | 54,627 | 26.5 % | +8.5 % |

Por horizonte (contra la mejor línea base, *media_movil_13*):

| Semanas adelante | WAPE modelo | WAPE línea base | Cobertura del rango 80% |
|---:|---:|---:|---:|
| 1 | 13.1 % | 14.3 % | 78.9 % |
| 2 | 13.7 % | 14.7 % | 76.6 % |
| 3 | 13.5 % | 14.6 % | 76.6 % |
| 4 | 13.8 % | 14.7 % | 73.4 % |

Por grupo:

| Grupo | WAPE modelo | WAPE línea base |
|---|---:|---:|
| Clothing | 17.0 % | 16.2 % |
| Computing Novelties | 31.8 % | 35.5 % |
| Furry Footwear | 16.7 % | 17.4 % |
| Mugs | 11.2 % | 12.6 % |
| Packaging Materials | 13.4 % | 14.8 % |
| T-Shirts | 9.4 % | 10.1 % |
| Toys | 15.2 % | 15.9 % |
| USB Novelties | 24.0 % | 24.3 % |

## 5. Rango probable

El rango cubre el 80% central de los errores medidos en **validación**. En prueba contuvo al valor real el **76.4 %** de las veces (lo esperado es cerca del 80 %).

## 6. Modelo registrado

- Algoritmo: `hgb[rezagos+contexto](max_depth=2, learning_rate=0.03, max_iter=200)` · semilla 42.
- Modelo de producción: la misma configuración reentrenada con **toda** la historia real (3,696 muestras, hasta la semana del 2016-05-23). Las métricas de arriba son del modelo que no vio la prueba.
- Variables (22): `horizonte`, `rezago_0`, `rezago_1`, `rezago_2`, `rezago_3`, `rezago_4`, `rezago_5`, `rezago_6`, `rezago_7`, `rezago_8`, `rezago_9`, `rezago_10`, `rezago_11`, `rezago_12`, `tendencia`, `crecimiento_anual`, `estacional`, `estacional_suave`, `volatilidad`, `semana_sin`, `semana_cos`, `grupo`.
- Guardado en `ml.modelo` (versión, parámetros, métricas, huella y modelo serializado) y sus predicciones de prueba en `ml.prediccion_prueba`.
