# Requerimientos funcionales y no funcionales — Faro

La guía (sección 11) pide documentar los requerimientos. Cada requerimiento indica dónde está
implementado y qué **evidencia** lo comprueba. Las preguntas analíticas (P01 a P14) están en
[alcance-y-preguntas.md](alcance-y-preguntas.md).

**Estado:** ✅ cumplido · 🟡 parcial · ⬜ no implementado (con la razón).

## 1. Usuarios

| Usuario | Qué necesita | Cómo accede |
|---|---|---|
| **Analista comercial** | Analizar ventas, comparar períodos, ver pronósticos, preguntar en lenguaje natural y atender alertas | Dashboard web con usuario y contraseña (rol `analista`) |
| **Operador de datos** | Ejecutar y vigilar las cargas, recuperar fallas, reentrenar el modelo | GitHub Actions, línea de comandos y la pestaña **Operación** |
| **Evaluador** | Reproducir la solución y verificar resultados | README, manuales, pruebas automatizadas y la demo |

## 2. Requerimientos funcionales

### Fuente y ambiente

| ID | Requerimiento | Implementación | Evidencia | Estado |
|---|---|---|---|:---:|
| RF-01 | Tener una fuente relacional con el proceso de ventas | WideWorldImporters migrada de SQL Server a PostgreSQL 17 (`wwi_oltp`): 17 tablas y 644,488 filas | [Reconciliación de la carga](../pruebas/reconciliacion-carga-fuente-neon.md) | ✅ |
| RF-02 | Documentar la fuente: ERD, diccionario y perfil | Generados desde la base | [ERD](../modelos/erd-fuente.md) · [diccionario](../modelos/diccionario-fuente.md) · [perfil](../pruebas/perfil-fuente.md) | ✅ |
| RF-03 | Simular la operación continua, con los datos simulados identificados | [simulador/](../../simulador/), marca `es_simulado` hasta el dashboard | `tests/test_simulador.py` | ✅ |

### ETL, staging y calidad

| ID | Requerimiento | Implementación | Evidencia | Estado |
|---|---|---|---|:---:|
| RF-04 | Carga inicial y carga incremental | Watermark por tabla con 10 minutos de solapamiento | `tests/test_etl_staging.py` · [pruebas del ETL](../pruebas/pruebas-etl-staging.md) | ✅ |
| RF-05 | Staging con zonas raw, clean y ready, y cuarentena | `stg_raw`, `stg_clean`, `stg_quarantine`, `stg_ready` | [diagramas](diagramas-etl.md) · `tests/test_zona_ready.py` | ✅ |
| RF-06 | Reglas de calidad reproducibles, con rechazados en cuarentena | 16 reglas, aplicadas como 35 controles en las tablas; los rechazados se reintentan | [catálogo de reglas](../modelos/catalogo-reglas-calidad.md) · `tests/test_catalogo_reglas.py` | ✅ |
| RF-07 | Auditoría de cada ejecución (campos mínimos de la guía) | `audit.etl_execution`, `etl_step`, `watermark`, `dq_result` | `tests/test_etl_staging.py` | ✅ |
| RF-08 | Idempotencia: repetir una carga no duplica | UPSERT por clave natural y SCD2 por hash | `tests/test_etl_staging.py` · `tests/test_dw.py` | ✅ |
| RF-09 | Recuperación: una falla se revierte y se puede reintentar | Una transacción por ejecución; el watermark no avanza | `tests/test_etl_staging.py` · [manual de operación](../manuales/manual-operacion.md) | ✅ |

### Data Warehouse

| ID | Requerimiento | Implementación | Evidencia | Estado |
|---|---|---|---|:---:|
| RF-10 | Modelo dimensional con grano declarado | Estrella: una fila por línea de factura; 6 dimensiones y un puente | [modelo dimensional](../modelos/modelo-dimensional.md) · [diccionario del DW](../modelos/diccionario-dw.md) | ✅ |
| RF-11 | Historia de clientes y productos | SCD Tipo 2 con vigencias; Tipo 1 en el resto | Control D06/D07 de [validación](../pruebas/validacion-dw-neon.md) | ✅ |
| RF-12 | Política para hechos sin dimensión | Miembro desconocido (−1) que se reasigna cuando llega la dimensión | Control D08 · `tests/test_dw.py` | ✅ |
| RF-13 | Reconciliar fuente, staging y DW | 11 controles en cada carga de producción | [validación en Neon](../pruebas/validacion-dw-neon.md): 11 de 11 | ✅ |

### Business Intelligence (API y dashboard)

| ID | Requerimiento | Implementación | Evidencia | Estado |
|---|---|---|---|:---:|
| RF-14 | Iniciar sesión para usar el dashboard | Argon2, JWT en cookie httpOnly y bloqueo tras 5 intentos | `tests/test_api.py` | ✅ |
| RF-15 | 4 a 6 KPI con comparación entre períodos | 6 KPI en el panel (8 en la API) contra el mismo período del año anterior | [catálogo de KPI](../modelos/kpis.md) · `tests/test_api.py` (contra SQL independiente) | ✅ |
| RF-16 | Filtros por fecha y al menos dos dimensiones | Fechas, territorio, categoría, grupo, vendedor, simulados y bajo costo | `tests/test_api.py` · E2E | ✅ |
| RF-17 | Tendencias, desgloses y drill-down al detalle | Tendencia por mes, semana o día; desglose en 8 dimensiones; facturas y su detalle | E2E (capturas [02](../capturas/02-dashboard.png) a [04](../capturas/04-detalle-factura.png)) | ✅ |
| RF-18 | Fecha de la última actualización y estados de carga, error y sin datos | Encabezado y componentes de estado | Vitest · E2E | ✅ |
| RF-19 | Responder P01 a P07 | KPI, tendencia y desgloses (P07: filtro «solo bajo costo») | E2E · `tests/test_api.py` | ✅ |
| RF-20 | P08: ciclo pedido → factura → entrega | El hecho guarda la fecha de pedido y la de factura (rol doble de la dimensión fecha), consultables por SQL. No hay vista en el dashboard ni se modeló la entrega confirmada. | [modelo dimensional](../modelos/modelo-dimensional.md) | 🟡 |
| RF-21 | P09: pedidos con faltantes (*backorders*) | Fuera del grano elegido (líneas **facturadas**, hallazgo H06): los pedidos sin factura no están en el DW | [D-15](../decisiones/registro-decisiones.md) | ⬜ |

### Machine Learning

| ID | Requerimiento | Implementación | Evidencia | Estado |
|---|---|---|---|:---:|
| RF-22 | Pronosticar las ventas de las próximas semanas (P10) | Venta neta semanal por grupo, 4 semanas, con rango del 80 % | [modelo de ML](../modelos/modelo-ml.md) · `tests/test_ml.py` | ✅ |
| RF-23 | Comparar con una línea base y evaluar en datos no vistos | 4 líneas base, validación cruzada temporal y 16 semanas de prueba | [evaluación en Neon](../pruebas/evaluacion-ml-neon.md): WAPE 13.5 % contra 14.6 % | ✅ |
| RF-24 | Registrar versión, parámetros, métricas, fecha y horizonte | `ml.modelo` y `ml.pronostico` | `tests/test_ml_base.py` | ✅ |
| RF-25 | Mostrar la predicción identificada como tal | Pestaña Pronóstico | Captura [07](../capturas/07-pronostico.png) · Vitest | ✅ |

### IA generativa

| ID | Requerimiento | Implementación | Evidencia | Estado |
|---|---|---|---|:---:|
| RF-26 | Responder en lenguaje natural con datos del DW (P11) | 4 herramientas controladas; el modelo no escribe SQL | [asistente de IA](asistente-ia.md) · `tests/test_asistente.py` | ✅ |
| RF-27 | Separar hechos, predicciones e interpretaciones, y citar el respaldo | Cada hecho cita su consulta y el servidor lo verifica | [pruebas en Neon](../pruebas/pruebas-asistente-neon.md): 14 de 14, 0 no verificadas | ✅ |
| RF-28 | Reconocer cuando no hay datos o la pregunta está fuera de alcance | Tipos `sin_datos`, `fuera_de_alcance` y `aclaracion` | Casos S01 a S03 (sin datos), B01 (ambigua) y F01 a F02 (fuera de alcance y seguridad) de las pruebas | ✅ |

### Alertas y monitoreo

| ID | Requerimiento | Implementación | Evidencia | Estado |
|---|---|---|---|:---:|
| RF-29 | Alerta por regla de negocio (P12, P14) | Caída de ventas > 15 % y ventas bajo costo | `tests/test_alertas.py` · demo en producción | ✅ |
| RF-30 | Alerta por modelo de ML (P13) | Pronóstico bajo el 85 % del promedio, con horizonte y versión | `tests/test_alertas.py` | ✅ |
| RF-31 | Explicación y acción generadas por IA, identificadas | Groq, salida JSON estricta | Captura [10](../capturas/10-alerta-detalle.png) | ✅ |
| RF-32 | Notificar por correo y en el dashboard, sin duplicados y con reintentos | Gmail SMTP con hasta 3 intentos; clave de evento única; pestaña Alertas | `tests/test_alertas_base.py` · [alertas](alertas.md) | ✅ |
| RF-33 | Consultar el detalle y cambiar el estado de una alerta | Nueva, atendida, descartada o resuelta, con nota | `tests/test_api_alertas.py` · E2E | ✅ |
| RF-34 | Vista operativa: ejecuciones, fallas, rechazados, modelo y notificaciones | Pestaña Operación | Captura [11](../capturas/11-operacion.png) · `tests/test_api_alertas.py` | ✅ |
| RF-35 | Ejecutar los procesos de forma programada | `cron` de GitHub Actions; en la práctica GitHub los retrasa o los descarta | [pendiente documentado](alertas.md#9-pendiente-un-disparador-programado-fiable) | 🟡 |

## 3. Requerimientos no funcionales

| ID | Categoría | Requerimiento | Criterio | Resultado | Evidencia |
|---|---|---|---|---|---|
| RNF-01 | Rendimiento | Respuesta rápida de las consultas del dashboard | Mediana < 1 s en producción | ✅ Todas < 1 s; la más lenta, 925 ms (desglose por pertenencia a grupo) | [tiempos en Vercel](../pruebas/tiempos-api-vercel.md) |
| RNF-02 | Rendimiento | Carga completa en un tiempo razonable | < 1 minuto la carga inicial | ✅ 24 a 32 s con 645,789 filas (local) | Pestaña Operación |
| RNF-03 | Frescura | Latencia entre venta y análisis | ≤ 1 hora (D-17) | 🟡 Se cumple al ejecutar a mano; los horarios de GitHub no son fiables | [alertas §9](alertas.md#9-pendiente-un-disparador-programado-fiable) |
| RNF-04 | Seguridad | Sin secretos en el repositorio | 0 contraseñas versionadas | ✅ `.env` ignorado, secrets de GitHub y Vercel | [arquitectura §7](arquitectura.md#7-seguridad) |
| RNF-05 | Seguridad | Mínimo privilegio | Un rol por proceso | ✅ 6 roles; pruebas de permisos negados | `tests/test_roles.py` · `tests/test_alertas_base.py` |
| RNF-06 | Seguridad | Sin inyección SQL ni SQL generado por la IA | Consultas parametrizadas | ✅ | `tests/test_api.py` · `tests/test_asistente.py` |
| RNF-07 | Seguridad | La API no expone credenciales ni detalles internos | Errores sin trazas ni cadenas de conexión | ✅ | `tests/test_api.py` · `tests/test_api_alertas.py` |
| RNF-08 | Privacidad | Minimizar datos personales y documentar lo que se envía a la IA | Sin contacto de clientes; a la IA solo van agregados | ✅ | [asistente §seguridad](asistente-ia.md) · [arquitectura §7](arquitectura.md#7-seguridad) |
| RNF-09 | Confiabilidad | Todo o nada en cada carga | Rollback y reintento sin inconsistencias | ✅ | `tests/test_etl_staging.py` |
| RNF-10 | Confiabilidad | Control de uso del asistente | 20 preguntas por hora y 100 por día por usuario | ✅ | `tests/test_api_asistente.py` |
| RNF-11 | Reproducibilidad | Cualquiera puede levantar el proyecto con el README | Dependencias exactas (`uv.lock`, `package-lock.json`) y Docker | ✅ | [manual de instalación](../manuales/manual-instalacion.md) · CI |
| RNF-12 | Mantenibilidad | Pruebas automáticas y CI obligatorio | Rama `main` protegida con 4 checks | ✅ 171 pruebas Python y 48 Vitest | [plan de pruebas](../pruebas/plan-de-pruebas.md) |
| RNF-13 | Usabilidad | Uso en escritorio y móvil, accesible | Diseño adaptable, modo oscuro, tablas en lugar de gráficos y color nunca como único código | ✅ | Capturas [05](../capturas/05-modo-oscuro.png) y [06](../capturas/06-movil.png) |
| RNF-14 | Trazabilidad | Linaje de cada dato | Lote, tabla y momento de extracción en staging; lote en el DW | ✅ | [diseño del staging](diseno-staging-etl.md) |
| RNF-15 | Costo | Operar sin costo | US$0 al mes | ✅ Planes gratuitos | [arquitectura §9](arquitectura.md#9-costos) |
| RNF-16 | Portabilidad | Mismo motor en todos los entornos | PostgreSQL 17 en desarrollo, CI y producción | ✅ | [arquitectura §3](arquitectura.md#3-entornos) |
