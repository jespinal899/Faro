# Plan y resultados de pruebas — Faro

Consolida **qué se prueba, cómo y con qué resultado**, en el orden de la guía (sección 12). Los
reportes detallados de cada etapa están enlazados en la sección 4.

**Resultado al 2026-11-15 (rama `main` + Fase 8):**

| Nivel | Herramienta | Resultado |
|---|---|---|
| Pruebas de Python (unitarias e integración) | pytest + PostgreSQL 17 | **175 de 175** pasan (72.6 s) |
| Pruebas del dashboard | Vitest + Testing Library | **48 de 48** pasan |
| Navegador real, de punta a punta | Playwright | **1 flujo completo** pasa (11 capturas) |
| Calidad de código | ruff · ESLint · TypeScript | Sin errores |
| Contra producción (Neon) | Scripts de validación | DW 11 de 11 · asistente 14 de 14 · demo de alertas con correo entregado |

---

## 1. Estrategia

| Nivel | Qué cubre | Cómo se aísla |
|---|---|---|
| **Unitarias** | Reglas de alertas, motor del asistente, variables y métricas de ML, formato y filtros del dashboard | Sin base ni red: datos en memoria, IA y correo simulados |
| **Integración** | ETL, DW, roles, API, pronóstico, alertas | Cada archivo crea **dos bases temporales** (fuente y analítica) con los scripts reales y las borra al terminar. Se conecta **con el rol de producción** de cada proceso (`etl_lector`, `faro_etl`, `faro_api`, `faro_ml`, `faro_alertas`, `wwi_app`). |
| **Punta a punta (integral)** | Fuente → simulador → ETL → DW → alertas → API | `tests/test_e2e_integral.py`, con bases temporales; solo la IA y el correo son simulados |
| **Punta a punta (navegador)** | Sesión, KPI, filtros, drill-down, detalle, modo oscuro, móvil, pronóstico, asistente (IA real), alertas y operación | Playwright contra la API y el dashboard locales, con los datos completos |
| **Con servicios reales** | El modelo de IA real, el modelo de ML con datos completos, el DW de producción, el correo real | Scripts que generan reportes en `documentation/pruebas/` (sección 4) |
| **CI** | ruff, pytest con PostgreSQL 17, docker-compose, lint, Vitest y build del dashboard | GitHub Actions en cada PR; `main` protegida con los 4 checks obligatorios |

**Criterios de aceptación:**
- todas las pruebas automáticas en verde en el CI antes de integrar a `main`;
- los controles de validación del DW en 11 de 11;
- el asistente sin afirmaciones no verificadas;
- el modelo de ML evaluado contra la línea base en semanas que no vio.

## 2. Matriz de la guía (sección 12)

| Prueba de la guía | Qué se demuestra | Pruebas automáticas | Evidencia |
|---|---|---|---|
| **Carga inicial** | Se extrae y carga todo; se registran conteos | `test_etl_staging.py` | [pruebas del ETL](pruebas-etl-staging.md) · [validación en Neon](validacion-dw-neon.md) |
| **Carga incremental** | Solo los cambios, sin duplicar | `test_etl_staging.py`, `test_e2e_integral.py` | [pruebas del ETL](pruebas-etl-staging.md) |
| **Idempotencia** | Repetir el lote no altera el resultado | `test_etl_staging.py`, `test_dw.py` | [pruebas del DW](pruebas-dw.md) |
| **Nulos y duplicados** | Política de nulos por causa; repetir no duplica; regla de supervivencia | `test_zona_ready.py`, `test_etl_staging.py` | [catálogo de reglas](../modelos/catalogo-reglas-calidad.md) |
| **Integridad** | Huérfanos a cuarentena; miembro desconocido en el DW | `test_etl_staging.py`, `test_dw.py` | Control D08 de [validación](validacion-dw-neon.md) |
| **Recuperación** | Una falla controlada se revierte y se reintenta sin inconsistencias | `test_etl_staging.py` | [manual de operación](../manuales/manual-operacion.md) |
| **Reconciliación** | Conteos y sumas iguales entre capas | `test_dw.py`, `test_e2e_integral.py` (KPI = suma sobre la fuente) | [validación en Neon](validacion-dw-neon.md): 11 de 11 |
| **Dashboard** | KPI = consultas SQL independientes; filtros combinados; período sin datos; sin duplicar por joins; permisos | `test_api.py` (28), Vitest (48), Playwright | [tiempos en producción](tiempos-api-vercel.md) |
| **ML** | Línea base, evaluación en datos no usados, límites | `test_ml.py`, `test_ml_base.py`, `test_api_pronostico.py` | [evaluación en Neon](evaluacion-ml-neon.md) |
| **GenAI** | Respuestas contrastadas con SQL; rechaza lo que no tiene respaldo | `test_asistente.py`, `test_api_asistente.py` | [14 preguntas en Neon](pruebas-asistente-neon.md) |
| **Alertas** | Disparo, no disparo, sin duplicados, reintentos, registro y entrega | `test_alertas.py`, `test_alertas_base.py`, `test_api_alertas.py`, `test_e2e_integral.py` | [alertas §7](../arquitectura/alertas.md#7-pruebas) (incluye la demo en producción) |
| **End-to-end** | Flujo completo desde la fuente hasta el resultado visible | `test_e2e_integral.py` (4) y Playwright | Capturas [01 a 11](../capturas/) |

## 3. Inventario de pruebas automáticas

### Python (`tests/`, 175)

| Archivo | Pruebas | Qué cubre |
|---|---:|---|
| `test_conexion.py` | 7 | Variables faltantes, conexión a cada base, PostgreSQL 17 y que un error no exponga la contraseña |
| `test_esquema_fuente.py` | 23 | Mapeo desde SQL Server sin datos sensibles, auditoría en todas las tablas, orden de carga y trigger de `last_edited_when` |
| `test_simulador.py` | 6 | Días hábiles, sábados, importes válidos, marca de simulado hasta el ETL, registro inválido a cuarentena |
| `test_etl_staging.py` | 10 | Inicial, incremental, idempotencia, limpieza y marcas, cuarentena y salida al corregirse, fecha futura, falla con rollback y reintento, ejecuciones simultáneas, auditoría |
| `test_zona_ready.py` | 6 | Grano de la línea, medidas derivadas, grupo principal sin duplicar ventas, nulos por causa, geografía y empleados |
| `test_dw.py` | 10 | Carga inicial, SCD1 y SCD2 (la venta usa la versión vigente en su fecha), miembro desconocido y reasignación, idempotencia, validación completa |
| `test_catalogo_reglas.py` | 2 | El catálogo de reglas documentado coincide con el código del ETL |
| `test_roles.py` | 5 | El pipeline y el simulador funcionan con sus roles; cada rol no puede más de lo suyo |
| `test_api.py` | 28 | Sesión, bloqueo, KPI contra SQL independiente, filtros, paginación, inyección SQL, sin credenciales |
| `test_ml.py` / `test_ml_base.py` | 9 / 5 | Variables sin fuga de datos, validación temporal, líneas base, registro de versiones con `faro_ml` |
| `test_api_pronostico.py` | 6 | El pronóstico de la API es exactamente el registrado |
| `test_asistente.py` / `test_api_asistente.py` | 19 / 7 | Herramientas cerradas, citas verificadas, recordatorio sin consulta, límites, errores del proveedor |
| `test_alertas.py` / `test_alertas_base.py` | 15 / 5 | Cada regla dispara y no dispara, correo, reintentos, sin duplicados, permisos |
| `test_api_alertas.py` | 8 | Lista, detalle, estado y nota, 404 y 422, monitoreo, error sin detalle interno |
| `test_e2e_integral.py` | 4 | Fuente → ETL → DW → alerta → API, cada etapa con su rol |

### Dashboard (`frontend/src`, 48)

| Archivo | Pruebas | Qué cubre |
|---|---:|---|
| `App.test.tsx` | 3 | Inicio de sesión, error de credenciales, carga del panel |
| `TarjetasKpi.test.tsx` | 4 | 6 KPI, variación con flecha y texto, sin comparación, error |
| `graficos.test.ts` | 7 | Series, leyenda, «Otros» en gris, períodos incompletos con `*` |
| `filtros.test.ts` / `formato.test.ts` | 5 / 4 | Parámetros a la API, período por defecto, formatos y «sin dato» ≠ 0 |
| `PanelPronostico.test.tsx` | 6 | Identificado como predicción, versión, línea base, sin modelo |
| `PanelAsistente.test.tsx` | 6 | Hechos con cita, predicciones aparte, límite, sin clave |
| `PanelAlertas.test.tsx` | 6 | Filtro por estado, IA identificada, entregas, cambio de estado, error |
| `PanelOperacion.test.tsx` | 4 | Frescura, falla, cuarentena contra marcadas, sin modelo |
| `useIntervalo.test.ts` | 3 | Consulta periódica solo con la pestaña visible |

### Navegador (`frontend/e2e/dashboard.spec.ts`)

Un flujo de 12 pasos con datos completos y la IA real; genera las capturas 01 a 11 de
[documentation/capturas](../capturas/).

## 4. Pruebas con servicios y datos reales (reportes)

| Reporte | Qué prueba | Resultado |
|---|---|---|
| Reconciliación de la carga de la fuente ([local](reconciliacion-carga-fuente-local.md) · [Neon](reconciliacion-carga-fuente-neon.md)) | Migración de SQL Server a PostgreSQL | Conteos y sumas iguales en 17 tablas |
| [Perfil de la fuente](perfil-fuente.md) | Calidad de origen («antes») | 32 reglas perfiladas |
| [Pruebas del ETL](pruebas-etl-staging.md) | Staging, cuarentena, auditoría | Ver reporte |
| [Pruebas del DW](pruebas-dw.md) · Validación ([local](validacion-dw-local.md) · [Neon](validacion-dw-neon.md)) | Modelo y reconciliación («después») | 11 de 11 en Neon |
| Tiempos de la API ([local](tiempos-api-local.md) · [Vercel](tiempos-api-vercel.md)) | Rendimiento con datos completos | Todas las medianas < 1 s en producción |
| Evaluación del modelo ([local](evaluacion-ml-local.md) · [Neon](evaluacion-ml-neon.md)) | Modelo contra líneas base en semanas no vistas | WAPE 13.5 % contra 14.6 % (7 % menos error) |
| Asistente ([local](pruebas-asistente-local.md) · [Neon](pruebas-asistente-neon.md)) | 14 preguntas con valores esperados por SQL independiente | 14 de 14, 0 afirmaciones no verificadas, US$0 |
| Demo de alertas en producción ([alertas §7](../arquitectura/alertas.md#7-pruebas)) | Evento simulado → ETL → alerta → IA → correo | 2 alertas, 2 correos recibidos, sin duplicar al repetir |

## 5. Defectos que encontraron las pruebas

| Defecto | Cómo se detectó | Corrección |
|---|---|---|
| La cadena de conexión (con su contraseña) aparecía en un error de pytest | Revisión de la salida de una prueba fallida | Envoltorio `Url` que oculta la cadena en los reportes |
| El proveedor de IA rechazaba JSON junto con herramientas | Evaluación con el modelo real | La respuesta final llega por una herramienta `json`, con recuperación |
| Un caso del asistente (A08) se evaluaba de forma demasiado estrecha | Evaluación con el modelo real | Acepta las dos lecturas correctas |
| El límite de preguntas por hora bloqueaba la prueba del navegador | Playwright | Límite alto solo en la API de prueba; el real no cambia |
| La pestaña Operación marcaba en rojo filas que solo se marcan (atípicos) | Revisión de las capturas del E2E | Se separan las filas a cuarentena de las marcadas |
| Cifras redondeadas distinto en el mensaje y en el detalle de una alerta | Revisión de las capturas del E2E | El detalle muestra la cifra exacta con centavos |

## 6. Cómo ejecutar

```powershell
uv run ruff check . ; uv run pytest -q                 # Python (requiere Docker con PostgreSQL)
cd frontend ; npm run lint ; npm test ; npm run build   # dashboard
npm run e2e                                             # navegador real (datos completos en local)
uv run python database/scripts/validar_dw.py            # validación del DW
uv run python generative-ai/evaluar_asistente.py        # asistente con el modelo real
```

El detalle de cada comando está en el [manual de instalación](../manuales/manual-instalacion.md).

## 7. Límites de las pruebas

- **Horarios de GitHub:** los `cron` no se pueden probar de forma automática y en la práctica no
  son fiables ([pendiente documentado](../arquitectura/alertas.md#9-pendiente-un-disparador-programado-fiable)).
- **IA real:** no es determinista, por eso se evalúa con un script aparte y no en el CI (además
  costaría cuota). En el CI la IA está simulada.
- **Correo real:** la entrega se verificó en la bandeja de Gmail (local y producción). En el CI
  el servidor SMTP está simulado.
- **Bases temporales:** las pruebas de integración no corren contra Neon (crearían bases en
  producción). Producción se verifica con `validar_dw.py` en cada carga y con los reportes de la
  sección 4.
