# Pruebas del Data Warehouse

Evidencia de los criterios de aceptación de la guía (secciones 5 y 12) para el modelo
dimensional. Hay dos niveles:

1. **Pruebas automáticas** (`tests/test_dw.py`): escenarios sobre bases temporales con datos
   mínimos. Corren en cada Pull Request.
2. **Validación con datos reales** (`database/scripts/validar_dw.py`): 11 controles sobre el DW
   completo. Corren en local y **después de cada carga en producción**.

```powershell
uv run pytest tests/test_dw.py -v
uv run python database/scripts/validar_dw.py          # local
uv run python database/scripts/validar_dw.py --neon   # producción
```

## Pruebas automáticas

| Concepto de la guía | Qué se demuestra | Prueba |
|---|---|---|
| Carga inicial | Hechos cargados, todas las claves resueltas, nulos según su causa | `test_carga_inicial` |
| SCD Tipo 2 | Un cambio de categoría cierra la versión vigente y abre otra; las ventas anteriores **conservan** la categoría que tenía el cliente al comprar | `test_scd2_un_cambio_de_categoria_crea_una_version_nueva` |
| Búsqueda por vigencia | Las ventas nuevas usan la versión vigente en su fecha | `test_las_ventas_nuevas_usan_la_version_vigente` |
| SCD Tipo 1 | Renombrar un cliente sobrescribe todas sus versiones sin crear una nueva | `test_scd1_un_cambio_de_nombre_sobrescribe_todas_las_versiones` |
| SCD2 por identificador | Renombrar una categoría refresca el nombre y **no** versiona a sus clientes | `test_renombrar_una_categoria_no_crea_versiones_y_refresca_el_nombre` |
| Vigencias limpias | Dos cambios antes de la siguiente venta no dejan versiones vacías | `test_dos_cambios_antes_de_la_siguiente_venta_no_dejan_versiones_vacias` |
| Dimensión desconocida | Un vendedor sin dimensión recibe la clave -1 (la venta no se pierde) y se **reasigna** cuando la dimensión aparece | `test_miembro_desconocido_y_reasignacion` |
| Idempotencia | Repetir la carga no cambia hechos ni dimensiones | `test_reejecutar_no_cambia_el_dw` |
| Primer despliegue | Con el DW vacío, una ejecución incremental carga todos los hechos | `test_dw_vacio_se_carga_completo_aunque_la_ejecucion_sea_incremental` |
| Validación completa | Los 11 controles pasan | `test_validacion_completa_del_dw` |

## Controles de validación (datos reales)

| Código | Control |
|---|---|
| D01 | Grano: `linea_factura_id` único en `fact_ventas` |
| D02 | Reconciliación **fuente → DW** consultando la fuente: fuente = DW + cuarentena (líneas y venta bruta) |
| D03 | Reconciliación `stg_ready` → DW |
| D04 | Medidas derivadas coherentes en todas las filas |
| D05 | Ventas por grupo principal y por puente ponderado = total (sin multiplicar importes) |
| D06–D07 | SCD2: una versión vigente por clave, sin solapes ni huecos de vigencia |
| D08 | Miembro desconocido en cada dimensión y hechos que lo usan |
| D09 | La dimensión fecha cubre todas las ventas y ninguna cae en domingo |
| D10 | KPI venta neta por año del DW = consulta independiente a la fuente |
| D11 | Claves foráneas declaradas en el hecho |

Resultados: [local](validacion-dw-local.md) · [Neon](validacion-dw-neon.md).

## Defecto encontrado por las pruebas

`test_scd1_un_cambio_de_nombre_sobrescribe_todas_las_versiones` falló en la primera versión:
renombrar un cliente creaba una versión SCD2 nueva. El atributo con historia era el **nombre**
del cliente de facturación, y casi todos los clientes se facturan a sí mismos. Se corrigió
para que la historia siga a los **identificadores** (categoría, grupo de compra, cliente de
facturación, grupo principal) y los nombres se refresquen según el ID (decisión D-21).
