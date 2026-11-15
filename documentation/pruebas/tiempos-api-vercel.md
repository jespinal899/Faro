# Tiempos de respuesta de la API — vercel

> Generado por `database/scripts/medir_api.py` (2026-11-15 06:21 UTC).
> Entorno: https://faro-fawn-kappa.vercel.app. 5 llamadas por consulta, con los datos completos.

| Consulta | Endpoint | Mediana (ms) | Máximo (ms) |
|---|---|---:|---:|
| KPI de todo el histórico | `/api/kpis` | 408 | 475 |
| KPI de un trimestre con comparación anual | `/api/kpis` | 277 | 484 |
| KPI con 3 filtros combinados | `/api/kpis` | 275 | 529 |
| Tendencia mensual (todo el histórico) | `/api/tendencia` | 584 | 836 |
| Tendencia diaria de un año | `/api/tendencia` | 315 | 456 |
| Desglose por grupo | `/api/desglose` | 496 | 505 |
| Desglose por pertenencia a grupo | `/api/desglose` | 925 | 977 |
| Top 10 productos | `/api/desglose` | 553 | 575 |
| Facturas, página 1 | `/api/facturas` | 608 | 1,225 |
| Facturas, página 100 | `/api/facturas` | 613 | 616 |
| Detalle de una factura | `/api/facturas/67114` | 143 | 144 |
| Opciones de filtros | `/api/opciones` | 920 | 940 |
| Estado de los datos | `/api/estado` | 276 | 447 |
