# Manual de operación y recuperación — Faro

Para el **operador de datos**: qué corre, cómo vigilarlo y qué hacer cuando algo falla. La guía
(sección 10) pide documentar:
- cómo reiniciar el pipeline;
- cómo reintentar una carga fallida;
- cómo restaurar la base de prueba;
- cómo reconstruir el entorno;
- los scripts en orden de ejecución (sección 4 de este manual).

Las consultas SQL se ejecutan con la conexión del dueño de la base analítica: en local,
`ANALYTICS_DATABASE_URL`; en producción, `NEON_ANALYTICS_DATABASE_URL`. Para abrir `psql`:
- local: `docker exec -it faro-postgres psql -U admin -d faro_analytics`;
- Neon: el *SQL Editor* de la consola.

---

## 1. Qué corre y cuándo

| Proceso | Programación | A mano | Qué hace | Si falla |
|---|---|---|---|---|
| **ETL - Ventas** | Cada hora, minuto 7 (UTC) | *Actions → ETL - Ventas → Run workflow* (modo `incremental` o `inicial`) | Fuente → staging → DW, validación del DW (11 controles) y evaluación de alertas | Se revierte; el watermark no avanza; la próxima ejecución reprocesa |
| **Simulador - Ventas** | Diario, 11:40 UTC | *Actions → Simulador - Ventas* | Inserta el siguiente día hábil de ventas **simuladas** | No inserta nada (una transacción) |
| **ML - Pronóstico** | Lunes, 12:30 UTC | *Actions → ML - Pronóstico* (opción *entrenar*) | Pronostica 4 semanas con el modelo vigente y evalúa las alertas | El pronóstico anterior sigue vigente |
| **Alertas - Evento simulado** | — | *Actions → Alertas - Evento simulado* | Demo: baja venta simulada → ETL → alerta y correo | Igual que el ETL |
| **CD - Neon** | Con cada merge que toque `database/` | *Actions → CD - Neon* | Aplica esquemas y permisos, en una transacción | No aplica nada |

> **GitHub no garantiza los horarios programados** (los retrasa o los omite). Para una
> demostración, lanzar los procesos a mano. Propuesta de solución:
> [alertas.md §9](../arquitectura/alertas.md#9-pendiente-un-disparador-programado-fiable).

Dos ejecuciones del ETL nunca corren a la vez: lo impiden el grupo de concurrencia del workflow
y un candado en la base. La segunda termina con «Ya hay una ejecución del pipeline en curso».

## 2. Vigilancia diaria

1. **Dashboard → pestaña Operación:**
   - **Frescura:** verde si hubo una carga en las últimas 2 horas, amarillo si no, rojo si la
     última falló.
   - Ejecuciones del ETL con leídas, nuevas y rechazadas.
   - Calidad por dimensión.
   - Cuarentena pendiente.
   - Modelo vigente.
   - Correos enviados o fallidos.
2. **GitHub → Actions:** cada ejecución deja un resumen (conteos, reglas con casos y la
   validación del DW). GitHub avisa por correo cuando un workflow falla.
3. **Dashboard → pestaña Alertas:** atender las nuevas (ver el [manual de usuario](manual-usuario.md#6-alertas)).

Consultas útiles:

```sql
-- Últimas ejecuciones del ETL
SELECT execution_id, trigger, mode, status, start_time, end_time - start_time AS duracion,
       rows_read, rows_inserted, rows_updated, rows_rejected, reconciled, error_detail
FROM audit.etl_execution ORDER BY execution_id DESC LIMIT 10;

-- Detalle por tabla y etapa de una ejecución (con el rango de watermark procesado)
SELECT step, source_object, target_object, rows_read, rows_inserted, rows_updated,
       rows_rejected, watermark_start, watermark_end, duration_ms, status
FROM audit.etl_step WHERE execution_id = <id> ORDER BY step_id;

-- Reglas de calidad con casos en la última ejecución
SELECT source_table, rule_code, action, rows_checked, rows_failed
FROM audit.dq_result WHERE execution_id = (SELECT max(execution_id) FROM audit.etl_execution)
  AND rows_failed > 0;

-- Evaluaciones de alertas y entregas
SELECT * FROM alerta.evaluacion ORDER BY evaluacion_id DESC LIMIT 5;
SELECT alerta_id, intento, intentado_en, resultado, error FROM alerta.envio ORDER BY envio_id DESC LIMIT 10;
```

## 3. Procedimientos ante fallas

### R1. El ETL falló

1. Ver el error: pestaña Operación (pasar el cursor por «Fallida») o
   `SELECT error_detail FROM audit.etl_execution WHERE status = 'fallido' ORDER BY execution_id DESC LIMIT 1;`.
2. Nada quedó a medias: la transacción se revirtió y el watermark no avanzó.
3. Corregir la causa (conexión, cuota, dato) y **volver a ejecutar**: *Actions → ETL - Ventas →
   Run workflow* (modo `incremental`) o `uv run python -m etl.orchestration.pipeline`. Reprocesa
   el mismo rango sin duplicar.
4. Si el proceso murió sin cerrar (runner cancelado), la ejecución quedó `en_curso`. La
   siguiente ejecución la marca como «Ejecución interrumpida» y continúa.

### R2. Hay registros en cuarentena

```sql
SELECT source_table, natural_key, rule_code, rule_detail, rejected_at
FROM stg_quarantine.registro_rechazado WHERE resolved_at IS NULL ORDER BY rejected_at DESC;
```

- **Qué es:** un registro que incumple una regla de cuarentena
  ([catálogo](../modelos/catalogo-reglas-calidad.md)). No entra al DW.
- **Qué hacer:** corregirlo **en la fuente**. Su `last_edited_when` cambia, el siguiente ETL lo
  vuelve a leer y, si ya cumple, entra y queda con `resolved_at`. **No** se edita el staging a
  mano.
- **Si no se corrige:** se reintenta en cada ejecución. Los reconciliadores cuentan la
  cuarentena: fuente = DW + cuarentena.

### R3. El ETL lleva horas sin correr (aviso amarillo)

Casi siempre son los horarios de GitHub. Lanzarlo a mano: *Actions → ETL - Ventas → Run
workflow*. Si *Actions* muestra ejecuciones fallidas, aplicar R1.

### R4. Neon: la base se suspendió o se agotó la cuota

| Síntoma | Causa | Acción |
|---|---|---|
| La API responde 503 («La base de datos no está disponible. Reintenta en unos segundos.»), o el ETL reintenta la conexión | Autosuspensión de Neon tras 5 minutos sin uso | Nada: el primer intento la despierta. El ETL reintenta 3 veces con espera creciente; en el dashboard, *Reintentar*. |
| Error `SQLSTATE 53000` («exceeded the quota») | Se agotaron las 100 CU-hora del mes del plan gratuito | La base vuelve el mes siguiente. Para recuperarla antes: en Neon, *Billing → Change plan* a Launch y volver a Free (reinicia la cuota sin costo). Después, revisar la frecuencia de los procesos. |

### R5. Una alerta no llegó por correo

1. En la pestaña Alertas, la columna *Correo* dice «Falló (n intentos)» o «Pendiente».
2. Verificar la cuenta: `uv run python -m notifications prueba-correo`.
   - Si falla con autenticación: generar una nueva
     [contraseña de aplicación](https://myaccount.google.com/apppasswords) y actualizar
     `SMTP_PASSWORD` en el `.env` y en el secret de GitHub.
3. La alerta se **reintenta sola** en la siguiente evaluación: 3 intentos por evaluación y 6 en
   total. Para forzarla: *Actions → ETL - Ventas* o `uv run python -m notifications evaluar --neon`.
4. Una alerta *descartada* no se envía.

### R6. Reconstruir el staging y el DW desde la fuente

Cuando el DW tiene datos incorrectos o se cambió una regla que afecta a la historia:
- en producción, *Actions → ETL - Ventas → Run workflow* con modo **`inicial`**;
- en local, `uv run python -m etl.orchestration.pipeline --modo inicial`.

Vacía staging y cuarentena, reinicia los watermarks y recarga todo, también el DW, en una
transacción. Toma alrededor de un minuto. Después: `uv run python database/scripts/validar_dw.py`
(o `--neon`), que debe dar 11 de 11.

### R7. Ajustar o apagar una regla de alerta

Los umbrales viven en la base, así que no hace falta desplegar nada:

```sql
UPDATE alerta.regla SET umbral = 20 WHERE codigo = 'caida_ventas';     -- caída > 20 %
UPDATE alerta.regla SET activa = false WHERE codigo = 'ventas_bajo_costo';
SELECT codigo, nombre, umbral, unidad, activa FROM alerta.regla;
```

### R8. El asistente de IA no responde

| Mensaje | Causa | Acción |
|---|---|---|
| «El asistente de IA no está configurado» | Falta `GROQ_API_KEY` en Vercel (o en el `.env`) | Agregarla y volver a desplegar (o reiniciar la API) |
| «Llegaste al límite de preguntas» | 20 por hora o 100 por día por usuario | Esperar; los límites se ajustan con `ASISTENTE_LIMITE_HORA` y `ASISTENTE_LIMITE_DIA` |
| «El servicio de IA no respondió» | Groq caído o el límite de tokens por minuto | Reintentar en un minuto. Alternativa: `ASISTENTE_PROVEEDOR=ollama` en local |

### R9. Reentrenar el modelo

*Actions → ML - Pronóstico → Run workflow* con **entrenar** marcado; en local,
`uv run --group ml python -m machine_learning entrenar`.
- Registra una versión nueva, la evalúa contra las líneas base y la deja vigente.
- Las anteriores quedan en `ml.modelo`.
- Se recomienda cada trimestre, o si el seguimiento de la pestaña Pronóstico muestra errores
  crecientes.

### R10. Restaurar la base de prueba local

```powershell
docker compose down -v ; docker compose up -d
# y los pasos 5 a 9 del manual de instalación (fuente, esquemas, ETL inicial, modelo, usuario)
```

### R11. Rotar credenciales

| Credencial | Cómo |
|---|---|
| Roles de la base (`etl_lector`, `faro_etl`, `faro_api`, `faro_ml`, `faro_alertas`, `wwi_app`) | `uv run python database/scripts/configurar_roles.py --entorno neon [--rol <rol>]`, y volver a subir los secrets (manual de despliegue, paso 5). Para `faro_api`, actualizar `API_DATABASE_URL` en Vercel. |
| `JWT_SECRET` | Generar uno nuevo en Vercel (manual de despliegue, paso 7). Cierra todas las sesiones abiertas. |
| `GROQ_API_KEY`, `SMTP_PASSWORD` | Revocar en el servicio, crear otra y actualizar el `.env`, los secrets de GitHub y, en el caso de Groq, Vercel. |

### R12. Cuenta del dashboard bloqueada o contraseña perdida

- **Bloqueada** (5 intentos fallidos): se desbloquea sola a los 15 minutos. Para desbloquearla
  ya:
  `UPDATE app.usuario SET intentos_fallidos = 0, bloqueado_hasta = NULL WHERE usuario = 'demo';`
- **Contraseña perdida:** `uv run python database/scripts/crear_usuario.py --usuario demo --nombre "Usuario Demo" [--neon]`
  genera una nueva y la guarda en el `.env`.

### R13. Un despliegue dejó de funcionar

Ver la sección *Revertir un despliegue* del [manual de despliegue](manual-despliegue.md#10-revertir-un-despliegue).

## 4. Recuperación reproducible: scripts en orden

Reconstruir **todo el entorno**, en este orden. Cada paso es idempotente: se puede repetir.

| # | Paso | Local | Producción |
|---|---|---|---|
| 1 | Bases vacías | `docker compose down -v ; docker compose up -d` | Neon: dos proyectos (manual de despliegue, §2) |
| 2 | Esquema de la fuente | Lo crea `migrar_wwi.py` | *CD - Neon* |
| 3 | Datos de la fuente | `database/source/seed/` (manual de instalación, §5) | El mismo script con `NEON_SOURCE_DATABASE_URL` |
| 4 | Staging, auditoría, DW, ML, alertas y vistas | `database/staging/*.sql`, luego `database/data-warehouse/01…09*.sql` | *CD - Neon* |
| 5 | Permisos y roles | `database/security/roles_*.sql` + `configurar_roles.py --entorno local` | *CD - Neon* + `configurar_roles.py --entorno neon` + secrets |
| 6 | Carga inicial | `python -m etl.orchestration.pipeline --modo inicial` | *ETL - Ventas*, modo `inicial` |
| 7 | Validación | `validar_dw.py` | Incluida en el workflow (`validar_dw.py --neon` a mano) |
| 8 | Modelo | `machine_learning entrenar` y `predecir` | *ML - Pronóstico* con *entrenar* |
| 9 | Usuario | `crear_usuario.py --usuario demo …` | Con `--neon` |
| 10 | Alertas | `notifications evaluar` | Corre al final del ETL |
| 11 | Aplicación | `uvicorn` + `npm run dev` | Vercel (push a `main`) |

## 5. Mantenimiento

| Tarea | Frecuencia | Cómo |
|---|---|---|
| Revisar la pestaña Operación y las alertas | Diaria | Sección 2 |
| Revisar la cuarentena pendiente | Semanal | R2 |
| Revisar el consumo de Neon (CU-hora) | Mensual | Consola de Neon → *Usage* |
| Reentrenar el modelo | Trimestral | R9 |
| Actualizar dependencias | Trimestral | `uv lock --upgrade` y `npm update`, con PR y CI |
| Rotar credenciales | Semestral o ante una exposición | R11 |
