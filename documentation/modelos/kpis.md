# Catálogo de KPI — Faro

Ficha de cada indicador del dashboard, como pide la guía (sección 6): nombre, propósito,
fórmula, unidad, granularidad, filtros, fuente y responsable.

**Reglas comunes**
- **Fuente:** Data Warehouse, vista aprobada `api.ventas` (hechos de `dw.fact_ventas` con sus
  dimensiones), a través de la API `GET /api/kpis`.
- **Grano de origen:** línea de factura. Todos los KPI se calculan agregando ese grano.
- **Filtros disponibles** en todos los KPI:
  - período (`desde`, `hasta`);
  - territorio, estado, categoría de cliente y grupo principal de producto;
  - vendedor, cliente y producto;
  - solo ventas bajo costo;
  - incluir o excluir ventas simuladas.
- **Comparación:** si se indica un período, cada KPI se compara con el **mismo período del año
  anterior** (variación %). El margen se compara en **puntos porcentuales**.
- **Responsable del dato:** Gerencia comercial (definición del indicador) · equipo de datos
  (cálculo y calidad).
- **Validación:** cada KPI se compara con una consulta SQL independiente sobre las tablas del DW
  en `tests/test_api.py`, sin filtros, con filtros combinados y sin datos simulados.

---

| # | KPI | Propósito | Fórmula (sobre `api.ventas`) | Unidad | Aditividad |
|---|---|---|---|---|---|
| K1 | **Ventas netas** | Cuánto se vendió, sin impuestos. Es el KPI principal | Σ `venta_neta` (= Σ `extended_price` − Σ `tax_amount`) | USD | Aditiva |
| K2 | **Ventas brutas** | Cuánto se facturó, con impuestos | Σ `venta_bruta` | USD | Aditiva |
| K3 | **Utilidad** | Cuánto se ganó | Σ `utilidad` | USD | Aditiva |
| K4 | **Margen %** | Rentabilidad de lo vendido | Σ `utilidad` ÷ Σ `venta_neta` × 100 | % | **No aditiva**: se recalcula, nunca se suma ni se promedia |
| K5 | **Unidades vendidas** | Volumen físico | Σ `cantidad` | unidades | Aditiva |
| K6 | **Facturas** | Número de transacciones | COUNT(DISTINCT `factura_id`) | facturas | **No aditiva** entre grupos de producto (una factura puede tener productos de varios grupos) |
| K7 | **Ticket promedio** | Valor medio de cada compra | Σ `venta_neta` ÷ COUNT(DISTINCT `factura_id`) | USD por factura | **No aditiva** |
| K8 | **Clientes activos** | Amplitud de la cartera que compra | COUNT(DISTINCT `cliente_id`) | clientes | **No aditiva** entre períodos |

## Detalle de cada ficha

### K1 · Ventas netas
- **Pregunta que responde:** P01 y P02 (cuánto vendemos y cómo se compara con el año anterior).
- **Granularidad:** día, semana, mes, trimestre y año; también por cualquier dimensión.
- **Notas:** no hay notas de crédito en los datos (regla V05 = 0), así que no se restan
  devoluciones. Si aparecieran, se restarían aquí.

### K2 · Ventas brutas
- **Notas:** `extended_price` **incluye impuestos** (hallazgo H05, verificado en el 100 % de las
  líneas). Por eso el KPI principal es la venta neta.

### K3 · Utilidad
- **Notas:** puede ser negativa en ventas bajo costo (H07). El filtro "solo ventas bajo costo"
  muestra cuánto margen se pierde (P07).

### K4 · Margen %
- **Notas:** para un grupo o período se calcula como Σ utilidad ÷ Σ venta neta del conjunto, no
  como el promedio de los márgenes de cada línea. Si no hay ventas, vale *sin dato* (no 0 %).

### K5 · Unidades vendidas
- **Notas:** la unidad depende del empaque del producto (unidad, paquete, bolsa o caja).

### K6 · Facturas
- **Notas:** en el desglose por grupo, las facturas de la fila "Otros" no se informan, porque
  sumarlas contaría dos veces las facturas con productos de varios grupos.

### K7 · Ticket promedio
- **Notas:** si no hay facturas en el período, vale *sin dato*.

### K8 · Clientes activos
- **Notas:** el total anual **no** es la suma de los clientes activos de cada mes: un cliente que
  compra todos los meses cuenta una sola vez en el año.

## Reglas de presentación
- Los indicadores descriptivos provienen del DW. Si se muestra una predicción (Fase 6), se rotula
  claramente como **predicción**, no como dato histórico.
- Las ventas simuladas (a partir del 1-jun-2016) se pueden excluir con un filtro y se identifican
  en el detalle.
- El dashboard muestra la **fecha y hora de la última carga exitosa** (`GET /api/estado`).
