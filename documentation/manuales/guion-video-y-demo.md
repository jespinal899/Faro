# Guion del video (5 minutos) y checklist de la demo en vivo — Faro

Material de apoyo para la **demostración final** (guía, sección 13). Los tiempos siguen la tabla
de la guía. Todo lo que se muestra es **ejecución real** contra producción.

---

## 1. Preparación (antes de grabar)

| # | Tarea | Cómo |
|---|---|---|
| 1 | Despertar la base y verificar el sitio | Abrir https://faro-fawn-kappa.vercel.app/api/salud: `{"api":"ok","base_de_datos":"ok"}` |
| 2 | Datos al día | *Actions → ETL - Ventas → Run workflow* (incremental). En la pestaña Operación, el aviso debe estar **verde**. |
| 3 | Pronóstico vigente | Pestaña Pronóstico con la versión del modelo. Si no: *Actions → ML - Pronóstico*. |
| 4 | Pestañas abiertas en el navegador | Dashboard (sesión iniciada), GitHub Actions, [modelo dimensional](../modelos/modelo-dimensional.md) en GitHub, Gmail y el *SQL Editor* de Neon (proyecto `faro-analytics`) |
| 5 | Ocultar secretos | Cerrar el `.env` y cualquier terminal con variables; usar el modo de presentación del navegador. En GitHub, los secrets aparecen como `***`. |
| 6 | Alerta lista | Para no esperar en cámara, lanzar *Alertas - Evento simulado* ~3 minutos antes del bloque 7 (tarda 1 a 2 minutos). |
| 7 | Resolución y audio | Ventana a 1440×900 o mayor, zoom del navegador al 110 %, micrófono probado |

## 2. Guion

| Tiempo | Bloque | Qué mostrar | Qué decir (idea central) |
|---|---|---|---|
| **0:00–0:40** | Caso, arquitectura y tecnologías | El README y el diagrama de [arquitectura.md](../arquitectura/arquitectura.md) | «Faro convierte las ventas de WideWorldImporters en información confiable: una fuente PostgreSQL, un ETL en Python con staging de tres zonas, un Data Warehouse en estrella, un dashboard React con API FastAPI, un pronóstico con scikit-learn, un asistente de IA con consultas controladas y alertas por correo. Producción: Neon, Vercel y GitHub Actions, sin costo.» |
| **0:40–1:30** | ETL: extracción, staging, transformación y controles | *Actions → ETL - Ventas*: la última ejecución y su resumen (leídas, nuevas, rechazadas, reglas con casos). Después, la pestaña **Operación**: ejecuciones, calidad por dimensión, cuarentena. | «Extracción incremental por watermark con 10 minutos de solapamiento. Staging raw, clean, cuarentena y ready. 16 reglas de calidad: lo inválido va a cuarentena con la regla que falló; lo atípico se marca. Cada ejecución es todo o nada: si falla, se revierte y el watermark no avanza.» |
| **1:30–2:15** | Modelo dimensional, carga y validación | El diagrama del [modelo dimensional](../modelos/modelo-dimensional.md). En Neon, la consulta de abajo. En *Actions*, «Validación del DW: 11 de 11». | «Grano: una línea de factura. SCD tipo 2 en cliente y producto, miembro desconocido, puente producto-grupo para no duplicar importes. Esta consulta independiente coincide con el dashboard.» |
| **2:15–3:00** | Dashboard: KPI, filtros y análisis histórico | Pestaña *Análisis histórico*: KPI contra el año anterior → filtro de período o territorio → clic en una barra del desglose (*drill-down*) → clic en una factura (detalle) | «Seis KPI comparados con el año anterior; filtros que afectan todo el panel; del resumen al detalle de una factura. Arriba, la fecha de la última carga y el aviso de datos simulados.» |
| **3:00–3:45** | Modelo predictivo y una métrica | Pestaña *Pronóstico*: el aviso «PREDICCIÓN», la versión, un grupo con su rango y la tarjeta *Calidad del modelo* | «Pronóstico semanal por grupo para 4 semanas, con rango del 80 %. Se entrena solo con ventas reales y se evalúa en semanas que no vio: WAPE de 13.5 % frente a 14.6 % de la línea base, un 7 % menos error. En un año de validación empatan, y lo decimos.» |
| **3:45–4:25** | Asistente de IA con respuesta respaldada | Pestaña *Asistente (IA)*: una pregunta de ejemplo («¿Qué territorios presentan una disminución relevante?») → abrir *Datos consultados* | «El modelo no escribe SQL: pide consultas de un catálogo cerrado que el servidor valida. Cada cifra cita su consulta; las predicciones y las interpretaciones van aparte. Si no hay datos, lo dice.» |
| **4:25–5:00** | Disparo y visualización de una alerta | *Actions → Alertas - Evento simulado* (la ejecución preparada) → pestaña **Alertas** (contador, detalle con «GENERADO POR IA», intento de correo) → el correo en Gmail → marcar como *Atendida* | «Evento **simulado** de baja venta: el ETL lo carga, la regla detecta la caída, la IA redacta la explicación, el correo llega y queda registrado. Sin duplicados al repetir.» **Cierre:** «Todo lo que vieron funciona en producción, con 175 pruebas automáticas, 48 del dashboard y una prueba de punta a punta. Pendiente documentado: un disparador programado más fiable que el cron de GitHub.» |

Consulta para el bloque 1:30 (en el *SQL Editor* de Neon, base `faro_analytics`):

```sql
-- Ventas netas y margen por año (el margen se recalcula, no se suma)
SELECT d.anio, sum(f.venta_neta) AS venta_neta,
       round(100 * sum(f.utilidad) / sum(f.venta_neta), 2) AS margen_pct,
       count(*) FILTER (WHERE f.es_simulado) AS lineas_simuladas
FROM dw.fact_ventas f JOIN dw.dim_fecha d ON d.fecha_key = f.fecha_factura_key
GROUP BY d.anio ORDER BY d.anio;
```

Para comparar con el dashboard: en *Análisis histórico*, período 1-ene a 31-dic de 2015, con
**Incluir simulados**; las ventas netas deben coincidir con la fila 2015.

## 3. Condiciones del video (guía)

- [ ] Duración ≤ 5:00 (respetar el límite del docente).
- [ ] Audio claro; texto legible (zoom del navegador).
- [ ] **Ejecución real**, no solo diapositivas.
- [ ] Sin contraseñas, tokens ni el `.env` en pantalla. Al iniciar sesión, la contraseña se ve
      como puntos.
- [ ] Decir en voz alta que el evento de la alerta y las ventas desde junio de 2016 son
      **simulados**.
- [ ] Conclusión breve: qué funciona y qué queda pendiente.

## 4. Checklist de la demo en vivo (guía, sección 13)

| # | La guía pide | Cómo hacerlo en Faro | Plan B si falla la red o un servicio |
|---|---|---|---|
| 1 | Ambiente preparado y procedimiento de inicio conocido | Producción despierta (sección 1); conocer el [manual de instalación](manual-instalacion.md) | Entorno local: `docker compose up -d`, `uvicorn` y `npm run dev` |
| 2 | Ejecutar al menos un pipeline o lote de prueba | *Actions → Simulador - Ventas* y luego *ETL - Ventas*, o en local: `uv run python -m simulador.ventas` y `uv run python -m etl.orchestration.pipeline` (muestra conteos por tabla) | Local |
| 3 | Dashboard y una consulta analítica | Análisis histórico + la consulta SQL de la sección 2 | Capturas en `documentation/capturas/` |
| 4 | Una predicción con versión identificable | Pestaña Pronóstico (versión `aaaammdd.hhmmss`) | `uv run --group ml python -m machine_learning predecir` en local |
| 5 | Una pregunta al componente generativo | Pestaña Asistente (IA) | Si Groq no responde: mostrar el [reporte de 14 preguntas](../pruebas/pruebas-asistente-neon.md) |
| 6 | Disparar una alerta de prueba y mostrar el registro o la recepción | *Alertas - Evento simulado* → pestaña Alertas → Gmail | `uv run python -m notifications evaluar` en local; el registro en `alerta.envio` |
| 7 | Explicar cómo se recuperaría una ejecución fallida | Pestaña Operación + [manual de operación, R1](manual-operacion.md#r1-el-etl-falló): la transacción se revierte, el watermark no avanza y se vuelve a ejecutar sin duplicar. Prueba automática: `tests/test_etl_staging.py::test_falla_a_mitad_revierte_todo_y_el_reintento_se_recupera`. | — |

## 5. Preguntas probables del evaluador

| Pregunta | Respuesta corta | Dónde está |
|---|---|---|
| ¿Por qué PostgreSQL y no SQL Server? | Mismo motor en local, CI y producción gratuita (Neon); la guía permite tecnologías equivalentes justificadas | D-01 |
| ¿Es tiempo real? | No: micro-lotes de 1 hora como máximo. Los eventos de la demo son simulados. | D-17 |
| ¿Cómo evitan duplicar importes con productos en varios grupos? | Grupo principal y puente con factor de ponderación; validado por el control D05 | D-16 |
| ¿Cómo evitan la fuga de datos en el modelo? | Variables solo del pasado del origen, separación temporal y prueba con semanas no vistas | [modelo de ML](../modelos/modelo-ml.md) |
| ¿La IA puede ejecutar SQL? | No. Cuatro herramientas cerradas con parámetros validados y un rol de solo lectura | D-25 |
| ¿Qué pasa si el correo falla? | 3 intentos por evaluación y 6 en total, cada uno registrado; se reintenta en la siguiente evaluación | D-26 |
| ¿Qué no funciona del todo? | Los horarios de GitHub no son fiables; P08 es parcial y P09 no se implementó | [requerimientos](../arquitectura/requerimientos.md) |
