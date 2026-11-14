# Alcance y preguntas analíticas — Faro

Documento de la **Fase 1 (Descubrimiento)**. Define qué proceso de negocio cubre Faro, qué
preguntas debe responder y qué implicaciones tienen los hallazgos del análisis de la fuente.

Evidencia de respaldo:
[diccionario de datos](../modelos/diccionario-fuente.md) ·
[diagrama entidad-relación](../modelos/erd-fuente.md) ·
[perfil de datos](../pruebas/perfil-fuente.md) ·
[reconciliación de la carga](../pruebas/reconciliacion-carga-fuente.md)

---

## 1. Proceso de negocio: **Ventas de WideWorldImporters**

WideWorldImporters (WWI) es un mayorista de artículos de novedad que vende a tiendas,
supermercados y cadenas. Faro analiza su **proceso de ventas**: desde el pedido del cliente
hasta la factura y la entrega.

| Dentro del alcance | Fuera del alcance (y por qué) |
|---|---|
| Pedidos, facturas y sus líneas | **Compras a proveedores:** es otro proceso de negocio |
| Clientes, categorías y grupos de compra | **Movimientos de inventario:** es otro proceso |
| Productos y grupos de producto | **Pagos de clientes / cuentas por cobrar:** otro proceso |
| Vendedores y geografía (ciudad → estado → país) | **Sensores de temperatura:** no aportan al análisis de ventas |

La guía recomienda **un proceso principal bien resuelto de punta a punta** antes que muchos
procesos a medias.

**Período de datos:** 1-ene-2013 → 31-may-2016 (3 años y 5 meses de ventas diarias).

## 2. Usuarios y decisiones que apoya

| Usuario | Decisión que toma con Faro |
|---|---|
| Gerencia comercial | Dónde crece o cae el negocio y qué priorizar (productos, clientes, territorios) |
| Jefes de venta | Desempeño de vendedores y de cartera de clientes |
| Compras / inventario | Cuánto se venderá en las próximas semanas (pronóstico) para reabastecer |
| Precios | Qué productos se venden bajo costo y deben revisarse |

## 3. Preguntas analíticas

### Descriptivas (Data Warehouse + dashboard)

| # | Pregunta |
|---|---|
| P01 | ¿Cuánto vendemos (bruto, neto de impuestos y utilidad) por día, semana, mes, trimestre y año? |
| P02 | ¿Cómo se comparan las ventas con el mismo período del año anterior? |
| P03 | ¿Qué grupos de producto y productos generan más ventas y más margen? |
| P04 | ¿Qué clientes, categorías y grupos de compra concentran las ventas? (análisis de Pareto) |
| P05 | ¿Cómo se distribuyen las ventas por territorio, estado y ciudad? (mapa) |
| P06 | ¿Qué vendedores venden más y con qué margen? |
| P07 | ¿Qué productos se venden bajo costo y cuánto margen se pierde? |
| P08 | ¿Cuánto tarda el ciclo pedido → factura → entrega confirmada? |
| P09 | ¿Qué porcentaje de pedidos genera faltantes (*backorders*) y en qué productos? |

### Predictiva (Machine Learning)

| # | Pregunta |
|---|---|
| P10 | ¿Cuánto venderemos en las próximas semanas por grupo de producto? |

### Generativa (asistente de IA)

| # | Pregunta |
|---|---|
| P11 | Responder en lenguaje natural las preguntas P01–P10 y explicar los cambios frente al período anterior, siempre citando las cifras consultadas |

### Alertas (automatización)

| # | Condición a vigilar |
|---|---|
| P12 | Ventas que caen más de un umbral frente a una referencia (regla de negocio) |
| P13 | Pronóstico de un grupo de producto por debajo de un umbral (Machine Learning) |
| P14 | Nuevas ventas bajo costo (regla de negocio, a partir del hallazgo H07) |

## 4. Indicadores preliminares

Definición inicial; la ficha completa de cada KPI (fórmula, unidad, filtros, fuente) se
formaliza en la Fase 5.

| KPI | Fórmula sobre la fuente | Tipo de medida |
|---|---|---|
| Ventas brutas | Σ `extended_price` (incluye impuestos) | Aditiva |
| Ventas netas | Σ (`extended_price` − `tax_amount`) | Aditiva |
| Utilidad | Σ `line_profit` | Aditiva |
| Margen % | Utilidad ÷ Ventas netas | **No aditiva** (se recalcula, no se suma) |
| Unidades vendidas | Σ `quantity` | Aditiva |
| Nº de facturas | Conteo de facturas distintas | No aditiva entre grupos de producto |
| Ticket promedio | Ventas netas ÷ Nº de facturas | **No aditiva** |
| Clientes activos | Clientes distintos con al menos una factura | **No aditiva** |

> En los datos no hay notas de crédito ni devoluciones (regla V05 = 0), así que
> ventas netas = ventas brutas − impuestos.

## 5. Hallazgos del análisis de la fuente y sus implicaciones

| # | Hallazgo | Evidencia | Implicación para el diseño |
|---|---|---|---|
| H01 | **2016 está incompleto** (solo enero–mayo) | Inventario y continuidad mensual | Comparar 2016 solo contra el mismo período de 2015; el pronóstico se entrena y evalúa respetando la fecha de corte. |
| H02 | **No hay ventas los domingos**; el sábado vende ~45 % de un día hábil | Distribución por día de la semana | La dimensión fecha marcará `es_dia_habil`; el día de la semana será una variable del modelo. |
| H03 | **La serie es continua**: todos los días de lunes a sábado tienen facturas | Regla O01 = 0 | La serie diaria/semanal no necesita imputar días faltantes para el pronóstico. |
| H04 | **58.6 % de los productos pertenece a más de un grupo** (133 de 227) | Regla I05 | Unir ventas con grupos sin control **duplica importes**. En la Fase 2 se definirá un *grupo principal* por producto o una tabla puente. |
| H05 | `extended_price` **incluye impuestos**, verificado en el 100 % de las líneas | Reglas K01 y K02 | El DW tendrá medidas separadas de venta bruta, impuesto y venta neta. |
| H06 | **3 085 pedidos sin factura**: 3 080 son *backorders* (pedidos automáticos por faltantes) | Regla I01 + investigación | El hecho de ventas tendrá como grano la **línea de factura**, no la de pedido, para no contar dos veces lo vendido. |
| H07 | **2 % de las líneas se vendió bajo costo**; el 89 % son 4 tallas de un mismo producto | Regla V04 + investigación | No es un error de datos: **no se corrige**. Se expone en el dashboard (P07) y genera alertas (P14). |
| H08 | **60 % de los clientes no tiene límite de crédito**: son exactamente los que facturan a su casa matriz | Regla C04 + investigación | NULL significa **"no aplica"**. No se imputa con cero; en la dimensión cliente será "gestionado por casa matriz". |
| H09 | **Atípicos plausibles**: 1.5 % de líneas con cantidad > Q3+3·IQR (máximo 360 unidades) | Reglas A01 y A02 | Pedidos mayoristas reales: **no se eliminan**; se marcan para análisis. |
| H10 | **Concentración**: la categoría *Novelty Shop* tiene el 69 % de los clientes y el 71.5 % de las ventas | Distribución por categoría | El análisis por categoría debe mostrar participación porcentual, no solo totales. |
| H11 | **Datos sintéticos**: WWI es una base de ejemplo generada por Microsoft | Origen del dataset | Los patrones pueden ser más regulares que en la realidad: el modelo se compara con una línea base y su utilidad se reporta con honestidad. |

## 6. Calidad general de la fuente

De las **32 reglas de calidad** evaluadas, **ninguna** reporta un problema de datos. Los casos
informativos (H06–H09) tienen explicación de negocio y quedan documentados. Aun así, el ETL
(Fase 3) **volverá a validar estas reglas en cada carga**, porque los datos nuevos que lleguen
a la fuente pueden no cumplirlas.
