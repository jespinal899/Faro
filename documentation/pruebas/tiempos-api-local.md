# Tiempos de respuesta de la API — local

> Generado por `database/scripts/medir_api.py` (2026-11-15 05:28 UTC).
> Entorno: local (API en proceso, base en Docker). 5 llamadas por consulta, con los datos completos.

| Consulta | Endpoint | Mediana (ms) | Máximo (ms) |
|---|---|---:|---:|
| KPI de todo el histórico | `/api/kpis` | 326 | 355 |
| KPI de un trimestre con comparación anual | `/api/kpis` | 105 | 107 |
| KPI con 3 filtros combinados | `/api/kpis` | 100 | 167 |
| Tendencia mensual (todo el histórico) | `/api/tendencia` | 510 | 528 |
| Tendencia diaria de un año | `/api/tendencia` | 213 | 220 |
| Desglose por grupo | `/api/desglose` | 477 | 491 |
| Desglose por pertenencia a grupo | `/api/desglose` | 948 | 1,004 |
| Top 10 productos | `/api/desglose` | 668 | 707 |
| Facturas, página 1 | `/api/facturas` | 403 | 458 |
| Facturas, página 100 | `/api/facturas` | 385 | 408 |
| Detalle de una factura | `/api/facturas/67114` | 29 | 50 |
| Opciones de filtros | `/api/opciones` | 479 | 496 |
| Estado de los datos | `/api/estado` | 118 | 144 |
