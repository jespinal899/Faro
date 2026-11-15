# Validación del Data Warehouse — local

> Generado por `database/scripts/validar_dw.py` (2026-11-15 04:59 UTC). No editar a mano.

**Resultado:** ✅ TODOS LOS CONTROLES PASAN (11/11)

| Código | Control | Estado | Detalle |
|---|---|:---:|---|
| D01 | Grano: linea_factura_id es único en fact_ventas | ✅ | 228,759 filas, 228,759 distintas |
| D02 | Reconciliación fuente → DW: líneas y venta bruta (fuente = DW + cuarentena) | ✅ | fuente 228,759 / 198,492,548.26 · DW 228,759 / 198,492,548.26 · cuarentena 0 / 0.00 |
| D03 | Reconciliación stg_ready → DW: líneas y venta bruta | ✅ | ready 228,759 / 198,492,548.26 |
| D04 | Medidas: venta_neta = bruta − impuesto y costo = neta − utilidad | ✅ | 0 filas incoherentes |
| D05 | Sin multiplicar importes: por grupo principal y por puente ponderado = total | ✅ | principal 198,492,548.26 · ponderado 198,492,548.26 · (sin ponderar daría 318,055,523.05) |
| D06 | SCD2 en dw.dim_cliente: una versión vigente por clave, sin solapes ni huecos | ✅ | claves sin una vigente: 0 · solapes: 0 · huecos: 0 · versiones históricas: 0 |
| D07 | SCD2 en dw.dim_producto: una versión vigente por clave, sin solapes ni huecos | ✅ | claves sin una vigente: 0 · solapes: 0 · huecos: 0 · versiones históricas: 0 |
| D08 | Miembro desconocido (-1) en cada dimensión; hechos que lo usan | ✅ | dimensiones sin miembro -1: 0 · hechos con -1: 0 |
| D09 | Dimensión fecha cubre todas las ventas; ninguna venta en domingo | ✅ | sin fecha: 0 · ventas en domingo: 0 |
| D10 | KPI venta neta por año: DW = consulta independiente a la fuente | ✅ | 2013: 45,707,188.00 · 2014: 49,929,487.20 · 2015: 53,991,490.45 · 2016: 23,024,611.65 |
| D11 | Integridad referencial: claves foráneas declaradas en fact_ventas | ✅ | 7 de 7 claves foráneas (las garantiza el motor) |

## Ventas por año desde el DW

| Año | Facturas | Líneas | Venta bruta | Venta neta | Utilidad | Margen % |
|---|---:|---:|---:|---:|---:|---:|
| 2013 | 18,767 | 60,968 | 52,563,272.64 | 45,707,188.00 | 22,768,352.25 | 49.81 |
| 2014 | 20,303 | 65,941 | 57,418,916.89 | 49,929,487.20 | 24,828,462.45 | 49.73 |
| 2015 | 22,250 | 71,898 | 62,090,220.81 | 53,991,490.45 | 26,957,600.65 | 49.93 |
| 2016 | 9,346 | 29,952 | 26,420,137.92 | 23,024,611.65 | 11,362,475.85 | 49.35 |

Margen % = Σ utilidad ÷ Σ venta neta (no aditivo: se recalcula por fila, no se suma).
