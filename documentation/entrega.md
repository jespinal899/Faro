# Índice de la entrega — Faro

Mapa para **evaluar el proyecto**: cada entregable que pide la guía, con su enlace. El estado
general y los comandos están en el [README](../README.md).

- **Producción:** https://faro-fawn-kappa.vercel.app
- **Repositorio:** https://github.com/jespinal899/Faro

---

## 1. Checklist de entrega (guía, sección 14)

| Ítem de la guía | Estado | Evidencia |
|---|:---:|---|
| Alcance y preguntas analíticas documentados | ✅ | [Alcance y preguntas](arquitectura/alcance-y-preguntas.md) (con el estado final de P01 a P14) |
| Fuente identificada y ambiente reproducible | ✅ | [Manual de instalación](manuales/manual-instalacion.md) · [docker-compose.yml](../docker-compose.yml) · `uv.lock` |
| ERD y diccionario de datos completos | ✅ | [ERD](modelos/erd-fuente.md) · [Diccionario de la fuente](modelos/diccionario-fuente.md) · [Diccionario del DW](modelos/diccionario-dw.md) |
| Staging conserva trazabilidad y separa raw de datos preparados | ✅ | [Diseño del staging](arquitectura/diseno-staging-etl.md) · [Diagramas del ETL](arquitectura/diagramas-etl.md) |
| Reglas de calidad documentadas y probadas | ✅ | [Catálogo de reglas](modelos/catalogo-reglas-calidad.md) · [Pruebas del ETL](pruebas/pruebas-etl-staging.md) · [Perfil de la fuente](pruebas/perfil-fuente.md) |
| Carga inicial e incremental, auditoría e idempotencia | ✅ | `tests/test_etl_staging.py` · [Plan de pruebas §2](pruebas/plan-de-pruebas.md#2-matriz-de-la-guía-sección-12) |
| Data Warehouse con grano, hechos, dimensiones y claves | ✅ | [Modelo dimensional](modelos/modelo-dimensional.md) · `database/data-warehouse/` |
| Resultados reconciliados con la fuente | ✅ | [Validación del DW en Neon](pruebas/validacion-dw-neon.md): 11 de 11 |
| Dashboard consulta el DW y KPI validados | ✅ | [Catálogo de KPI](modelos/kpis.md) · `tests/test_api.py` (contra SQL independiente) · [API](api/README.md) |
| ML con línea base, métricas y prueba independiente | ✅ | [Modelo de ML](modelos/modelo-ml.md) · [Evaluación en Neon](pruebas/evaluacion-ml-neon.md) |
| GenAI consulta datos autorizados y reconoce límites | ✅ | [Asistente de IA](arquitectura/asistente-ia.md) · [14 preguntas en Neon](pruebas/pruebas-asistente-neon.md) |
| Alertas disparadas y registradas | ✅ | [Alertas](arquitectura/alertas.md) (demo en producción, §7) · capturas [09](capturas/09-alertas.png) y [10](capturas/10-alerta-detalle.png) |
| README permite ejecutar la solución | ✅ | [README](../README.md) · [Manual de instalación](manuales/manual-instalacion.md) |
| Repositorio libre de secretos | ✅ | `.env` ignorado; [.env.example](../.env.example) sin valores reales; secrets en GitHub y Vercel |
| Diagramas, manuales y resultados de pruebas entregados | ✅ | Secciones 2 y 3 de este índice |
| Video y demo funcional completos | ✅ | Video de 5 minutos grabado; el enlace va en el documento de entrega. Demo en vivo en la presentación. |

## 2. Documentación obligatoria (guía, sección 11)

| Documento | Dónde |
|---|---|
| Requerimientos funcionales y no funcionales | [requerimientos.md](arquitectura/requerimientos.md) |
| Arquitectura de solución y diagrama general | [arquitectura.md](arquitectura/arquitectura.md) |
| ERD de la fuente y diccionario de datos | [erd-fuente.md](modelos/erd-fuente.md) · [diccionario-fuente.md](modelos/diccionario-fuente.md) |
| Diagrama dimensional y diccionario del DW | [modelo-dimensional.md](modelos/modelo-dimensional.md) · [diccionario-dw.md](modelos/diccionario-dw.md) |
| Diagramas de extracción, transformación, carga y orquestación | [diagramas-etl.md](arquitectura/diagramas-etl.md) |
| Catálogo de reglas de calidad y transformación | [catalogo-reglas-calidad.md](modelos/catalogo-reglas-calidad.md) |
| Documentación de APIs y contratos de datos | [api/README.md](api/README.md) · [openapi.json](api/openapi.json) · [kpis.md](modelos/kpis.md) |
| Documento ML | [modelo-ml.md](modelos/modelo-ml.md) |
| Documento GenAI | [asistente-ia.md](arquitectura/asistente-ia.md) · [generative-ai/README.md](../generative-ai/README.md) |
| Documento de alertas y automatización | [alertas.md](arquitectura/alertas.md) |
| Plan y resultados de pruebas | [plan-de-pruebas.md](pruebas/plan-de-pruebas.md) |
| Manual de instalación | [manual-instalacion.md](manuales/manual-instalacion.md) |
| Manual de despliegue | [manual-despliegue.md](manuales/manual-despliegue.md) |
| Manual de operación (con recuperación) | [manual-operacion.md](manuales/manual-operacion.md) |
| Manual de usuario | [manual-usuario.md](manuales/manual-usuario.md) |
| Decisiones técnicas justificadas | [registro-decisiones.md](decisiones/registro-decisiones.md) (D-01 a D-27) |

## 3. Software y código fuente (guía, sección 11)

| Pide la guía | Dónde |
|---|---|
| Scripts de bases, esquemas, tablas, vistas y permisos | [database/](../database/) (`source/`, `staging/`, `data-warehouse/`, `security/`, `scripts/`) |
| Pipelines ETL y orquestación | [etl/](../etl/) (`extraction/`, `transformation/`, `loading/`, `orchestration/`) · [.github/workflows/](../.github/workflows/) |
| Frontend y backend | [frontend/](../frontend/) · [backend/](../backend/) |
| Entrenamiento e inferencia | [machine_learning/](../machine_learning/) |
| Configuración del componente generativo | [backend/app/asistente/](../backend/app/asistente/) · [generative-ai/](../generative-ai/) |
| Notificaciones y reglas | [notifications/](../notifications/) · `database/data-warehouse/08_alertas.sql` |
| Datos de prueba o cómo obtenerlos | [tests/datos/](../tests/datos/) (datos mínimos) · respaldo oficial de WideWorldImporters ([manual de instalación §5](manuales/manual-instalacion.md#5-cargar-la-fuente-wideworldimporters)) · [simulador/](../simulador/) |
| `.env.example` y README con pasos exactos | [.env.example](../.env.example) · [README](../README.md) |
| Pruebas automatizadas | [tests/](../tests/) (175) · `frontend/src/**/*.test.*` (48) · [frontend/e2e/](../frontend/e2e/) |

## 4. Rúbrica (guía, sección 12): dónde mirar

| Criterio | Peso | Evidencia principal |
|---|---:|---|
| Análisis y arquitectura | 10 % | [Alcance](arquitectura/alcance-y-preguntas.md), [arquitectura](arquitectura/arquitectura.md), [decisiones](decisiones/registro-decisiones.md) |
| ETL, staging y calidad | 20 % | [Diagramas](arquitectura/diagramas-etl.md), [catálogo de reglas](modelos/catalogo-reglas-calidad.md), [pruebas del ETL](pruebas/pruebas-etl-staging.md), pestaña Operación |
| Modelo dimensional | 15 % | [Modelo dimensional](modelos/modelo-dimensional.md), [validación 11 de 11](pruebas/validacion-dw-neon.md) |
| Dashboard y API | 15 % | Producción, [API](api/README.md), [tiempos](pruebas/tiempos-api-vercel.md), capturas 01 a 06 |
| Machine Learning | 10 % | [Modelo de ML](modelos/modelo-ml.md), [evaluación](pruebas/evaluacion-ml-neon.md), captura 07 |
| Generative AI | 10 % | [Asistente](arquitectura/asistente-ia.md), [14 de 14](pruebas/pruebas-asistente-neon.md), captura 08 |
| Automatización | 5 % | [Alertas](arquitectura/alertas.md), capturas 09 a 11 |
| Pruebas y documentación | 10 % | [Plan de pruebas](pruebas/plan-de-pruebas.md), [manuales](manuales/) |
| Demo y comunicación | 5 % | Video de 5 minutos (enlace en el documento de entrega) y demo en vivo |

## 5. Pendientes y límites conocidos (declarados)

| Tema | Detalle |
|---|---|
| Disparador programado | GitHub no garantiza los horarios de `cron`; los procesos se lanzan a mano. Propuesta: [alertas.md §9](arquitectura/alertas.md#9-pendiente-un-disparador-programado-fiable). |
| P08 (ciclo del pedido) | Parcial: consultable por SQL, sin vista en el dashboard |
| P09 (*backorders*) | No implementada: fuera del grano elegido (D-15) |
| Pronóstico | En un año de validación el modelo empata con la línea base; la mejora del 7 % es en las semanas de prueba ([modelo de ML](modelos/modelo-ml.md)) |
