# Diseño del staging y del ETL — Faro

Documento de la **Fase 2 (Diseño)**. Define cómo viajan los datos desde `wwi_oltp` hasta el
Data Warehouse: zonas de staging, extracción incremental, reglas de calidad y qué hacer con
cada caso, auditoría, idempotencia y recuperación ante fallas. Se implementa en la Fase 3.

Base: [arquitectura](arquitectura.md) · [perfil de datos](../pruebas/perfil-fuente.md) ·
[hallazgos H01–H11](alcance-y-preguntas.md#5-hallazgos-del-análisis-de-la-fuente-y-sus-implicaciones)

---

## 1. Zonas de staging (base `faro_analytics`)

| Esquema | Zona | Propósito | Regla |
|---|---|---|---|
| `stg_raw` | Landing / Raw | Conservar **exactamente** lo recibido de la fuente | Solo se agregan filas; nunca se sobrescriben. Cada fila lleva su lote (`_batch_id`). |
| `stg_clean` | Clean / Validated | Datos con tipos, formatos y reglas de calidad aplicados | Una fila por clave natural (la versión vigente). Se registra qué regla se aplicó. |
| `stg_quarantine` | Cuarentena | Registros rechazados por una regla | Se guarda el registro original completo, la regla que falló y su detalle. |
| `stg_ready` | Ready / Integration | Entidades integradas y listas para el DW | Conserva claves de negocio y linaje. Controla los joins uno-a-muchos. |
| `audit` | Auditoría | Ejecuciones, pasos, watermarks y resultados de calidad | Se escribe en cada ejecución, exitosa o fallida. |

**Columnas de linaje** en cada fila de staging:

| Columna | Significado |
|---|---|
| `_batch_id` | Ejecución que trajo la fila (FK a `audit.etl_execution`) |
| `_extracted_at` | Momento de la extracción (UTC) |
| `_source_table` | Tabla de origen (`sales.invoice_lines`, etc.) |
| `_row_hash` | Hash de las columnas de negocio, para detectar cambios reales (solo en `stg_clean`) |

## 2. Extracción

### Carga inicial e incremental

| Aspecto | Diseño |
|---|---|
| **Carga inicial** | Extrae todas las filas de las 17 tablas (watermark inicial = `-infinity`). |
| **Carga incremental** | `WHERE last_edited_when > watermark − 10 minutos` por tabla. |
| **Watermark** | Se guarda por tabla en `audit.watermark`. Vale el **máximo `last_edited_when` extraído**, no la hora del reloj, para no depender de diferencias de hora entre servidores. |
| **Avance del watermark** | **Solo** cuando toda la ejecución termina bien, en la misma transacción que la carga. |
| **Ventana de solapamiento** | 10 minutos hacia atrás. Cubre transacciones que se confirmaron (*commit*) después de que se leyó la fuente. Las filas repetidas se absorben porque la carga es idempotente. |
| **Detección de cambios** | La fuente garantiza que todo UPDATE actualiza `last_edited_when` (trigger, ver [esquema de la fuente](../../database/source/01_esquema_fuente.sql)). |
| **Eliminaciones** | En el proceso de ventas de WWI no se borran filas: una venta se corrige con notas de crédito. Igual, la reconciliación compara conteos fuente ↔ staging y **alerta** si el staging tiene más filas que la fuente (señal de una eliminación). |
| **Conexión** | Directa (sin *pooler*) y de solo lectura sobre la fuente (rol `etl_lector`, Fase 3). |

## 3. Transformaciones obligatorias (sección 4 de la guía)

| Actividad | Cómo se aplica en Faro |
|---|---|
| **Perfilado** | `perfilar_fuente.py` (Fase 1) y re-validación de reglas en cada lote (sección 4). |
| **Limpieza** | `trim` y espacios múltiples colapsados en los textos; se eliminan caracteres de control. |
| **Nulos** | Según su causa, con la tabla de la sección 3.1. **Nunca** se reemplaza una medida numérica por cero. |
| **Duplicados** | Clave de duplicidad = clave natural (p. ej. `invoice_line_id`). **Regla de supervivencia:** gana la **última versión extraída** (el estado actual de la fuente); las demás quedan en `stg_raw` como historia. |
| **Estandarización** | Fechas y horas en UTC; una sola moneda (USD); nombres de día y mes en español en la dimensión fecha. |
| **Tipos de datos** | Conversión explícita conservando la precisión (`numeric(18,2)` para importes, `numeric(18,3)` para tasas). Un valor que no se puede convertir va a cuarentena, no se trunca. |
| **Integridad referencial** | Una transacción que apunta a algo inexistente (factura sin encabezado, producto desconocido) va a **cuarentena**. En el DW, un hecho sin dimensión recibe el **miembro desconocido** (clave −1). |
| **Atípicos** | Se **marcan** (`es_atipico`) con la regla Q3 + 3·IQR, sin eliminarlos (H09). |
| **Reglas de negocio** | Consistencia de importes, fechas y cantidades (sección 4). |
| **Enriquecimiento** | `venta_neta`, `costo`, `margen`, `es_casa_matriz`, `grupo_principal` del producto, `es_dia_habil`. |
| **Integración** | Factura + líneas al grano de la línea. Producto ↔ grupo **solo** mediante grupo principal o tabla puente con factor de ponderación (H04). |
| **Históricos** | SCD Tipo 2 en las dimensiones (ver modelo dimensional). |
| **Errores / cuarentena** | `stg_quarantine.registro_rechazado` (sección 5). |
| **Linaje** | Columnas `_batch_id`, `_source_table` y `_extracted_at`, más el [mapeo de la fuente](../modelos/diccionario-fuente.md). |

### 3.1 Manejo de nulos (decisión por columna)

| Columna | % nulos | Causa (guía de decisión) | Tratamiento |
|---|---:|---|---|
| `customers.credit_limit` | 60.6 % | **No aplica:** el crédito lo gestiona la casa matriz (H08) | Se conserva NULL y se agrega el atributo `politica_credito = 'Gestionado por casa matriz'`. No se imputa cero. |
| `customers.buying_group_id` | 39.4 % | **No aplica:** cliente independiente | Atributo `grupo_compra = 'Independiente'` |
| `stock_items.brand` | 92.1 % | **Desconocido** | `marca = 'Sin marca'` (categoría controlada) |
| `stock_items.color_id` | 43.6 % | **No aplica** (el producto no tiene color) | `color = 'Sin color'` |
| `orders.picked_by_person_id` | 14.4 % | **Pendiente / no registrado** | Se conserva NULL; no afecta al hecho de ventas |
| `invoices.confirmed_delivery_time` | 0.1 % | **Pendiente:** entrega aún no confirmada | Se conserva NULL y se actualiza cuando llega (UPSERT) |
| `invoice_lines.unit_price` | 0 % | **Error de captura** si apareciera | Cuarentena (regla V02) |

## 4. Reglas de calidad en cada lote

Las reglas del perfilado se convierten en controles del ETL. Cada resultado se guarda en
`audit.dq_result`, que es la evidencia de "calidad antes y después" que pide la guía.

| Código | Regla | Acción si falla | Motivo |
|---|---|---|---|
| V01 | Cantidad ≤ 0 | ⛔ Cuarentena | Una venta sin unidades no es válida |
| V02 / C01 | Precio unitario nulo o ≤ 0 | ⛔ Cuarentena | Importe imposible de calcular |
| V03 | Tasa de impuesto fuera de 0–100 % | ⛔ Cuarentena | Valor fuera de dominio |
| K01 | `extended_price ≠ quantity × unit_price + tax_amount` | ⛔ Cuarentena | Inconsistencia financiera |
| K02 | `tax_amount ≠ quantity × unit_price × tax_rate / 100` | ⛔ Cuarentena | Inconsistencia financiera |
| O02 | `last_edited_when` en el futuro | ⛔ Cuarentena | Marca de tiempo inválida: rompería el watermark |
| I02 | Línea sin factura o con producto inexistente | ⛔ Cuarentena | Integridad referencial |
| U03 | Varias versiones de la misma clave | 🔁 Supervivencia | Gana la última versión extraída |
| K03 | Factura con fecha anterior a la de su pedido | ⚠️ Marcar | Posible error de captura, pero la venta existe |
| V04 | Utilidad negativa (venta bajo costo) | ⚠️ Marcar + alerta de negocio | Problema de precios, no de datos (H07) |
| A01 / A02 | Cantidad o importe atípico | ⚠️ Marcar (`es_atipico`) | Pedido mayorista plausible (H09) |
| C03 | Entrega sin confirmar | ✅ Aceptar | Estado pendiente legítimo |

⛔ = no pasa a `stg_clean` · ⚠️ = pasa, marcado · ✅ = pasa sin marcas

## 5. Auditoría y cuarentena (campos mínimos de la guía)

**`audit.etl_execution`**: una fila por ejecución.

| Campo | Descripción |
|---|---|
| `execution_id` (PK), `pipeline_name` | Identificador y nombre del proceso (p. ej. `ventas_incremental`) |
| `trigger` | `cron`, `manual` o `ci` |
| `start_time`, `end_time` | Inicio y fin (UTC) |
| `status` | `en_curso`, `exitoso`, `fallido` |
| `rows_read`, `rows_inserted`, `rows_updated`, `rows_rejected` | Conteos totales |
| `error_detail` | Mensaje y paso del error (sin credenciales) |
| `git_sha` | Versión del código que se ejecutó |

**`audit.etl_step`**: una fila por tabla y etapa, con `execution_id`, `step` (`extract`, `clean`,
`load_dim`, `load_fact`…), `source_object`, `target_object`, los conteos,
`watermark_start`, `watermark_end`, la duración y el estado.

**`audit.watermark`**: `source_table` (PK), `last_value` y `updated_at`.

**`audit.dq_result`**: `execution_id`, `rule_code`, `table`, `rows_checked`, `rows_failed` y la acción aplicada.

**`stg_quarantine.registro_rechazado`**: `execution_id`, `source_table`, `natural_key`,
`rule_code`, `rule_detail`, `payload` (el registro original en `jsonb`) y `rejected_at`.
Opcionalmente, `resolved_at`.

## 6. Idempotencia, fallas y recuperación

| Escenario | Comportamiento |
|---|---|
| Se re-ejecuta el mismo lote | Mismo resultado: UPSERT por clave natural en clean, ready y hechos, y SCD2 que solo versiona si cambió el `_row_hash` |
| Falla a mitad de la carga | Se revierte la transacción, el watermark **no** avanza y `etl_execution.status = 'fallido'` con el detalle. La siguiente ejecución reprocesa el mismo rango. |
| Falla de red o Neon suspendido (arranque en frío) | Reintentos con espera creciente (3 intentos) antes de declarar la falla |
| Cuota de Neon agotada (SQLSTATE 53000) | Falla controlada y registrada. Solución documentada en el manual de operación. |
| Registro que llega tarde | Lo captura la ventana de solapamiento o la siguiente ejecución |
| Registro en cuarentena que luego se corrige en la fuente | Su `last_edited_when` cambia, el próximo lote lo vuelve a traer y, si ya cumple, entra a clean |
| Reconstruir todo desde cero | Se vacía staging/DW y se reinician los watermarks a `-infinity`: equivale a una carga inicial |

## 7. Reconciliación entre capas

En cada ejecución se comparan y se guardan en `audit`:

| Control | Debe cumplirse |
|---|---|
| Fuente → raw | Filas leídas = filas insertadas en `stg_raw` |
| Raw → clean | Filas raw = clean (nuevas + actualizadas) + cuarentena + duplicados descartados |
| Ready → DW | Líneas en `stg_ready` = filas en el hecho de ventas, y Σ importes iguales |
| Fuente → DW (total) | Conteo de líneas y Σ `extended_price` de la fuente = DW + cuarentena |

## 8. Orquestación

| Pipeline | Disparador | Pasos |
|---|---|---|
| `ventas_incremental` | Cada hora (`cron`) y manual | Extracción → validación → staging → dimensiones → hechos → reconciliación |
| `simulador_ventas` | Programado y manual (demo) | Inserta las operaciones del siguiente día de negocio simulado |
| `ml_prediccion` y `alertas` | Después de `ventas_incremental` | Fases 6 y 7 |

La lógica vive en módulos Python (`etl/extraction`, `etl/transformation`, `etl/loading`) y se
ejecuta igual en local (`uv run ...`) que en GitHub Actions. El orquestador **solo dispara y
encadena**: no contiene lógica ETL, como recomienda la guía.
