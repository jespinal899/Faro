# Pruebas del ETL de staging

Evidencia de los criterios de aceptación de la guía (sección 12) para la etapa de staging.
Las pruebas son automáticas (`tests/test_etl_staging.py`), se ejecutan en cada Pull Request
y usan **bases temporales con datos mínimos**: nunca tocan datos reales.

```powershell
uv run pytest tests/test_etl_staging.py -v
```

## Criterios de la guía → prueba automática

| Prueba de la guía | Qué se demuestra | Prueba |
|---|---|---|
| Carga inicial | Se copian todas las tablas; fuente = raw = clean; se registran conteos | `test_carga_inicial_copia_todo_y_reconcilia` |
| Auditoría | Ejecución, 17 pasos por etapa, watermarks y catálogo de reglas | `test_auditoria_registra_ejecucion_pasos_y_watermarks` |
| Carga incremental | Un alta y un cambio en la fuente se detectan sin duplicar; raw conserva la historia | `test_incremental_detecta_altas_y_cambios` |
| Idempotencia | Repetir la ejecución deja clean y raw idénticos | `test_reejecutar_no_duplica_ni_altera` |
| Limpieza y marcas | Los textos se limpian en clean (raw queda intacto); la venta bajo costo entra marcada | `test_limpieza_de_textos_y_marcas_de_calidad` |
| Reglas de calidad | Un registro inválido va a cuarentena con su regla y no entra a clean; la reconciliación cuadra | `test_registro_invalido_va_a_cuarentena_y_no_a_clean` |
| Corrección | Al corregirse en la fuente, el registro entra a clean y el rechazo queda resuelto | `test_registro_corregido_en_la_fuente_sale_de_cuarentena` |
| Registros con fecha inválida | Una fecha futura va a cuarentena y **no adelanta el watermark** | `test_fecha_futura_va_a_cuarentena_y_no_adelanta_el_watermark` |
| Recuperación | Una falla a mitad revierte todo (datos, raw y watermarks), queda auditada como fallida y el reintento se recupera | `test_falla_a_mitad_revierte_todo_y_el_reintento_se_recupera` |
| Concurrencia | No pueden correr dos ejecuciones a la vez | `test_no_permite_dos_ejecuciones_simultaneas` |

## Resultado con los datos completos (entorno local)

| Ejecución | Modo | Leídas | Nuevas | Actualizadas | Rechazadas | Sin cambios | Reconciliado |
|---|---|---:|---:|---:|---:|---:|:---:|
| 1 | inicial | 644 488 | 644 488 | 0 | 0 | 0 | ✅ |
| 2 | incremental | 790 | 0 | 0 | 0 | 790 | ✅ |

- Las 790 filas de la segunda ejecución son la **ventana de solapamiento** (10 minutos antes
  del watermark): se releen por seguridad y se descartan porque no cambiaron.
- Las marcas de calidad coinciden con el perfilado de la Fase 1: 4 626 líneas vendidas bajo
  costo (V04) y 3 383 con cantidad atípica (A01).

## Defecto encontrado por las pruebas

La prueba de la fecha futura detectó que la regla de supervivencia elegía "la versión con
mayor fecha de modificación": una versión vieja con fecha errónea le ganaba a la corregida,
y el registro no salía de cuarentena. Se corrigió para que gane **la última versión
extraída**, que es el estado actual de la fuente.

## Pruebas agregadas en la segunda parte de la fase

| Archivo | Qué se demuestra |
|---|---|
| `tests/test_zona_ready.py` | Una fila por línea de factura; medidas derivadas; grupo principal más específico; las ventas por grupo no se duplican (y se duplicarían sin el factor); nulos resueltos según su causa |
| `tests/test_simulador.py` | El simulador avanza por días hábiles sin domingos; sus importes cumplen las reglas; el ETL carga lo simulado y lo identifica; la línea inválida termina en cuarentena |
| `tests/test_roles.py` | El pipeline y el simulador funcionan con roles restringidos; cada rol tiene denegado lo que no le corresponde |

Total del proyecto: **57 pruebas automáticas**.

## Flujo completo con datos reales (entorno local)

Dos días simulados (1 y 2 de junio de 2016, 156 pedidos facturados) y una ejecución
incremental del ETL: **1 301 filas nuevas, 0 rechazadas, reconciliado**. Las 790 restantes
son la ventana de solapamiento, descartadas por no tener cambios.
