# Modelo de Machine Learning: pronóstico semanal de ventas por grupo de producto

> Pregunta analítica **P10** · decisión **D-24** · código en [machine_learning/](../../machine_learning/)
> · evaluación generada: [local](../pruebas/evaluacion-ml-local.md) · [Neon](../pruebas/evaluacion-ml-neon.md)

## 1. Problema, usuario y decisión

| | |
|---|---|
| **Qué se predice** | La venta neta (sin impuestos) de cada grupo principal de producto en cada una de las **4 semanas siguientes** a la última semana completa. |
| **Usuario** | Responsable de compras e inventario. |
| **Decisión que apoya** | Cuánto reponer de cada grupo para el próximo mes. El **rango probable del 80 %** sirve para dimensionar el stock de seguridad. |
| **Tipo de problema** | Regresión sobre series de tiempo, multi-horizonte (estrategia directa: el horizonte es una variable). |
| **Métrica principal** | **WAPE** = Σ\|error\| / Σ real: el error como % del volumen vendido. No se dispara con semanas pequeñas, como el MAPE. También se reportan MAE, RMSE, sMAPE y sesgo. |

## 2. Datos (pasos 2 y 3 de la guía)

- **Origen:** la vista `ml.ventas_semanales`, una vista analítica controlada sobre el DW. El modelo
  la lee con el rol `faro_ml`, que no tiene acceso al DW ni al staging.
- **Semana:** de lunes a sábado, porque WWI no vende los domingos (H02). Solo se usan semanas
  completas: la primera (que empieza un martes) y la última a medias quedan fuera.
- **Solo ventas reales** para entrenar y evaluar: 177 semanas, del 2013-01-07 al 2016-05-23. Las
  ventas **simuladas** no se usan para entrenar ni para evaluar. Sí sirven como historia al
  pronosticar, y entonces el pronóstico queda marcado con `usa_datos_simulados`.
- **Grupo:** el grupo principal del producto vigente en la fecha de la venta (SCD2). Así cada
  venta se cuenta una sola vez (H04). Ningún producto cambió de grupo principal en la historia.

**Hallazgos del análisis** (distribución, calidad, faltantes y sesgos):

| Hallazgo | Consecuencia |
|---|---|
| 9 grupos con ventas. **Novelty Items** son 8 chocolates lanzados en enero de 2016: solo 22 semanas de historia. | Se **excluye** con su motivo (mínimo 104 semanas). No se fabrica un pronóstico sin respaldo. |
| Sin semanas faltantes en los 8 grupos restantes (H03). | No hace falta imputar. Si apareciera una semana sin ventas dentro de la historia, vale 0, que es un dato y no un faltante. |
| Packaging Materials concentra el **59 %** del volumen. Computing Novelties, el 0.6 %. | El entrenamiento pondera por volumen para alinearse con el WAPE. |
| Variabilidad semanal (CV) de 14–25 %; Computing Novelties llega al 51 %. | Hay un piso de error que ningún modelo baja: el ruido semanal. |
| Crecimiento de ~8 % anual en 2013–2015, que **se frenó** en el último año (de −7 % a +4 % según el grupo). | Cambio de régimen: un modelo que aprendió el crecimiento tiende a sobrestimar. |
| Estacionalidad mensual suave: abril–julio más altos, agosto más bajo. | La validación debe cubrir un año completo para juzgar si esta información aporta. |

**Sesgos y límites de los datos:**
- WWI es una empresa ficticia con datos generados por reglas: no tiene crisis, promociones ni cambios de precio.
- 2016 está incompleto (H01).
- El modelo solo conoce los patrones de 2013–2016.

## 3. Variables (paso 4)

Cada **muestra** es un grupo, una semana de origen *t* y un horizonte *h* (1 a 4): con lo conocido
al cierre de la semana *t* se pronostica la semana *t+h*.

- **Escala relativa:** todo se expresa respecto del **nivel reciente** del grupo (la media de sus
  últimas 8 semanas), y el modelo predice venta/nivel. Así un solo modelo sirve para grupos de
  tamaños muy distintos, y el crecimiento no lo saca de su rango de entrenamiento.
- **Rezagos** (13): la venta de las semanas *t, t−1, …, t−12* relativa al nivel. El modelo
  aprende cuánto pesa cada semana; un promedio móvil es el caso de pesos iguales.
- **Contexto** (7):
  - tendencia: nivel de las últimas 8 semanas / nivel de las 8 anteriores;
  - crecimiento anual;
  - estacionalidad: la misma semana objetivo un año antes, puntual y suavizada;
  - volatilidad;
  - semana del año de la semana objetivo, como seno y coseno. Es calendario, así que se conoce de antemano.
- **Horizonte** y **grupo** (codificado *one-hot*).

**Control de fuga de información:** todas las variables usan semanas ≤ *t*. La prueba automática
`test_las_variables_no_usan_semanas_posteriores_al_origen` altera todo lo posterior al origen y
verifica que ninguna variable ni línea base cambie.

## 4. Separación, líneas base y candidatos (pasos 5 a 7)

Los conjuntos se separan por **semana pronosticada**, nunca al azar:

| Conjunto | Semanas pronosticadas | Uso |
|---|---|---|
| Validación cruzada temporal | 4 pliegues de 13 semanas: 2015-02-09 a 2016-02-01 (un año completo) | Cada pliegue se mide con un modelo entrenado **solo con semanas anteriores**. Sirve para elegir el modelo y calibrar el rango. |
| Prueba | 16 semanas: 2016-02-08 a 2016-05-23 | Medir el resultado final. No interviene en ninguna decisión. |

**Líneas base:**
- ingenuo: la última semana;
- media móvil de 4 semanas;
- **media móvil de 13 semanas**;
- estacional: la misma semana del año anterior.

La referencia es la mejor línea base **en validación**: la media móvil de 13 semanas.

**Candidatos:**
- Ridge con α = 10, 100 o 1000;
- *gradient boosting* (`HistGradientBoostingRegressor`) con pérdida absoluta, profundidad 2, tasa 0.03 y 200 iteraciones.

Cada uno se prueba con "rezagos" o con "rezagos + contexto": 8 candidatos en total. Todos se
entrenan con pesos proporcionales al volumen del grupo.

**Rango probable del 80 %:** los percentiles 10 y 90 del cociente real/pronóstico, medidos por
horizonte con las predicciones **fuera de pliegue** del candidato elegido (un año de semanas).

## 5. Resultados

| | Modelo elegido | Mejor línea base (media móvil 13) |
|---|---:|---:|
| WAPE en validación (un año, 4 pliegues) | 11.5 % | 11.5 % |
| WAPE en prueba (16 semanas) | **13.5 %** | 14.6 % |
| Sesgo en prueba | +1.7 % | −4.4 % |
| Cobertura del rango del 80 % en prueba | 76.4 % | — |

- **Modelo elegido:** `hgb[rezagos+contexto]`, *gradient boosting* con rezagos y contexto.
- **En un año completo empata** con la mejor línea base. Las variables de contexto ayudan en
  algunas estaciones (agosto–octubre: 9.6 % contra ~12 %) y perjudican en otras (fin de año).
- **En la prueba** (febrero–mayo) reduce el error un **7 %** y mejora en 7 de 8 grupos. Captó la
  subida de primavera que el promedio no ve: sesgo de +1.7 % contra −4.4 %.
- **El rango probable está bien calibrado:** contuvo el valor real el 76 % de las veces, contra
  el 80 % esperado.

Detalle por pliegue, horizonte y grupo: [evaluación local](../pruebas/evaluacion-ml-local.md).

## 6. Utilidad real y limitaciones

**Para qué sirve:**
- Da un pronóstico por grupo para las 4 semanas siguientes, con un error típico de ~13 % del
  volumen semanal. El total del mes tiene menos error relativo, porque las semanas se compensan.
- Su **rango probable calibrado** es lo que el promedio simple no ofrece, y es justo lo que
  necesita la decisión de stock de seguridad.
- Anticipa movimientos estacionales que un promedio de 13 semanas recoge tarde.

**Limitaciones (se documentan, no se esconden):**
- **La ventaja no es estable a lo largo del año:** en validación empata con un promedio de 13
  semanas. Gran parte de la variación semanal es ruido que ningún modelo puede predecir.
- **La prueba se calculó varias veces durante el desarrollo** (ver §7), porque el reporte la
  incluye siempre. Las decisiones se tomaron con validación, pero haber visto la prueba la vuelve
  una estimación algo optimista. La validación de un año es la referencia más conservadora.
- No hay variables externas: precios, promociones, feriados, inventario disponible.
- Computing Novelties (32 % de error) y USB Novelties (24 %) son poco predecibles: conviene
  usar el rango antes que el valor puntual.
- Novelty Items no tiene pronóstico hasta reunir 2 años de historia.

## 7. Experimentos (historial de diseño)

| # | Cambio | WAPE validación: modelo vs mejor línea base | Qué se aprendió |
|---|---|---|---|
| 1 | Diseño inicial: 4 rezagos + contexto, sin pesos, una sola ventana de validación (oct–feb). | 13.8 % vs 11.4 % (media móvil 4) | El modelo era **peor** que un promedio. Los grupos chicos y volátiles pesaban igual que los grandes, y el contexto agregaba ruido en esa ventana. |
| 2 | Pesos por volumen, 13 rezagos, media móvil 13 como línea base. | 11.4 % vs 11.1 % | Prácticamente un promedio aprendido. Promediar más semanas siempre ayudaba: la serie es "nivel + ruido". |
| 3 | Validación cruzada de **un año** (4 pliegues), porque una sola ventana otoño–invierno no permite juzgar la estacionalidad de primavera. | 11.5 % vs 11.5 % | Empate en el año. Gana el modelo con contexto, que en prueba mejora un 7 %. **Diseño final.** |

## 8. Registro, servicio, reentrenamiento y monitoreo (pasos 9 a 12)

- **Registro** (`ml.modelo`). Cada versión guarda:
  - la versión (`AAAAMMDD.HHMMSS` UTC), el algoritmo, los parámetros y la semilla;
  - las variables, los grupos incluidos y excluidos, y las métricas de validación y prueba;
  - los cuantiles del rango, la huella md5 de la serie usada y el commit de git;
  - el modelo serializado (joblib).

  Solo una versión es la **vigente**. La evaluación en prueba queda en `ml.prediccion_prueba`.
- **Pronóstico** (`ml.pronostico`):
  - cada fila lleva la versión del modelo, la semana de origen, la semana pronosticada, el
    horizonte, el rango y la marca de datos simulados;
  - repetir el mismo origen reemplaza el pronóstico y no lo duplica;
  - el historial completo se conserva.
- **Proceso programado:** el workflow *ML - Pronóstico* corre cada lunes a las 12:30 UTC y
  también a mano, con la opción de reentrenar. Usa el rol `faro_ml`.
- **Reentrenamiento:**
  - mensual, o antes si el monitoreo muestra que el error de las últimas semanas supera en más
    de 5 puntos al WAPE de prueba;
  - en esta demostración la historia real termina el 2016-05-31, así que reentrenar con los
    mismos datos da el mismo modelo (misma huella).
- **Monitoreo:**
  - la vista `api.pronostico_vs_real` compara cada pronóstico con lo vendido cuando la semana se
    completa, e indica si esa venta incluye ventas simuladas;
  - las alertas de la Fase 7 usarán el pronóstico (P13: grupo por debajo de un umbral).
- **Exposición:** vistas aprobadas `api.*` → API → dashboard, siempre identificado como
  **PREDICCIÓN** y no como dato histórico.

## 9. Cómo ejecutarlo

```powershell
uv sync --group ml                                          # una vez: pandas, numpy, scikit-learn
uv run --group ml python -m machine_learning entrenar       # base local: entrena, evalúa y registra
uv run --group ml python -m machine_learning predecir       # pronostica las 4 semanas siguientes
uv run --group ml python -m machine_learning entrenar --neon --sin-guardar   # producción, sin escribir
uv run --group ml pytest tests/test_ml.py tests/test_ml_base.py              # 14 pruebas
```
