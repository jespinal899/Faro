# API de Faro — documentación y contratos de datos

La API (FastAPI) es la única puerta entre el navegador y los datos: **el navegador nunca se
conecta a la base**. Todos los indicadores salen del Data Warehouse, a través de las vistas
aprobadas del esquema `api`.

- **Documentación interactiva:** `/api/docs` (en local: http://localhost:8000/api/docs).
- **Contrato completo (OpenAPI 3):** [openapi.json](openapi.json). Se genera desde el código con
  `uv run python -m backend.exportar_openapi`, así que siempre coincide con la API real.
- **Definición de cada KPI:** [kpis.md](../modelos/kpis.md).

## Autenticación

1. `POST /api/auth/login` con `{"usuario": "...", "password": "..."}`.
2. La respuesta deja una cookie de sesión `faro_sesion`: JWT, **httpOnly**, `SameSite=Lax`,
   `Secure` en producción. Dura 8 horas.
3. Las demás rutas exigen la sesión (`401` si falta, expiró o fue alterada).
4. Tras **5 intentos fallidos** la cuenta se bloquea 15 minutos (`423`).
5. El mensaje es el mismo exista o no el usuario.

## Endpoints

| Método | Ruta | Para qué | Sesión |
|---|---|---|:---:|
| GET | `/api/salud` | La API y la base responden | — |
| POST | `/api/auth/login` · `/api/auth/logout` | Abrir o cerrar sesión | — |
| GET | `/api/auth/me` | Usuario de la sesión | ✔ |
| GET | `/api/kpis` | 8 KPI del período, comparados con el mismo período del año anterior | ✔ |
| GET | `/api/tendencia?granularidad=mes\|semana\|dia` | Serie histórica con la del año anterior | ✔ |
| GET | `/api/desglose?dimension=…&top=N&pertenencia=` | Ventas por grupo, categoría, grupo de compra, territorio, estado, vendedor, producto o cliente | ✔ |
| GET | `/api/facturas?pagina&tamano&orden&buscar` | Detalle paginado (máximo 100 por página) | ✔ |
| GET | `/api/facturas/{id}` | Navegación a una factura y sus líneas | ✔ |
| GET | `/api/opciones` | Valores para los filtros | ✔ |
| GET | `/api/estado` | Fecha de la última carga exitosa y rango de datos | ✔ |
| GET | `/api/pronostico?semanas_historia=26` | **PREDICCIÓN** de las 4 semanas siguientes por grupo, con rango del 80 %, contexto real, seguimiento de pronósticos pasados y calidad del modelo | ✔ |
| GET | `/api/pronostico/evaluacion?grupo=…&horizonte=1..4` | Lo que pronosticaron el modelo y la línea base en las semanas de prueba, frente a lo vendido | ✔ |
| GET | `/api/asistente/info` | Si el asistente de IA está disponible, su modelo, límites y preguntas de ejemplo | ✔ |
| POST | `/api/asistente` | Pregunta en lenguaje natural; respuesta con hechos citados, predicciones e interpretaciones aparte ([asistente-ia.md](../arquitectura/asistente-ia.md)) | ✔ |
| GET | `/api/alertas/resumen` | Cuántas alertas nuevas (y críticas) hay: el dashboard lo consulta cada minuto | ✔ |
| GET | `/api/alertas?estado=…&limite=100` | Alertas de la más reciente a la más antigua, con contenido, explicación de IA y entrega del correo | ✔ |
| GET | `/api/alertas/{id}` | Detalle de una alerta con cada intento de envío | ✔ |
| PATCH | `/api/alertas/{id}` | Cambiar el estado (`nueva`, `atendida`, `descartada`, `resuelta`) con una nota opcional; registra quién y cuándo | ✔ |
| GET | `/api/monitoreo` | Operación: ejecuciones del ETL, calidad por dimensión, cuarentena, modelo vigente y notificaciones | ✔ |

**Filtros comunes** (parámetros de consulta, todos opcionales):
- `desde`, `hasta`;
- `territorio`, `estado`, `categoria`, `grupo`;
- `vendedor_id`, `cliente_id`, `producto_id`;
- `solo_bajo_costo`, `incluir_simulados`.

Los filtros **no aplican al pronóstico**: el modelo pronostica cada grupo completo. La API del
pronóstico no calcula nada: expone lo que registró el proceso del modelo (versión, origen,
horizonte y métricas), leído de las vistas aprobadas `api.modelo_pronostico`, `api.pronostico`,
`api.pronostico_vs_real`, `api.prediccion_prueba` y `api.ventas_semanales`. Si no hay un
modelo vigente responde `disponible: false`, en lugar de inventar un pronóstico.

Las **alertas** las genera el evaluador al terminar cada carga ([alertas.md](../arquitectura/alertas.md));
la API solo las muestra y cambia su estado. El **monitoreo** lee vistas aprobadas
(`api.monitoreo_etl`, `api.monitoreo_calidad`, `api.monitoreo_cuarentena`) con conteos y estados:
nunca los registros rechazados ni el detalle interno de un error.

## Errores

| Código | Cuándo |
|---|---|
| 401 | Falta la sesión, expiró o es inválida; o credenciales incorrectas |
| 404 | La factura o la alerta no existe |
| 422 | Parámetro inválido (fecha, rango, dimensión, página > 100) |
| 423 | Cuenta bloqueada por intentos fallidos |
| 429 | Se alcanzó el límite de preguntas al asistente (por hora o por día) |
| 502 | El servicio de IA no respondió |
| 503 | La base no está disponible (p. ej. Neon despertando), o el asistente no está configurado: reintentar |
| 504 | La consulta superó el tiempo máximo (8 s) |

Los errores nunca incluyen detalles internos (consultas, cadenas de conexión o trazas).

## Seguridad aplicada
- Consultas **parametrizadas**; columnas de listas fijas; sin SQL dinámico con datos del usuario.
- El rol de base `faro_api` solo lee las vistas `api.*`: no ve el DW, el staging ni la auditoría,
  y no puede cambiar contraseñas ni roles. De una alerta solo puede actualizar el estado y la nota.
- Transacciones de **solo lectura** con un tiempo máximo por consulta.
- Cabeceras `X-Content-Type-Options`, `X-Frame-Options` y `Referrer-Policy`, y `Cache-Control: no-store` en los datos.

## Tiempos de respuesta
Medidos con los datos completos: [tiempos-api-local.md](../pruebas/tiempos-api-local.md).
