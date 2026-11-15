# Registro de decisiones técnicas

Cada decisión indica qué se eligió, qué alternativas se consideraron y por qué.
Estado: **Aceptada**, **Pendiente** o **Reemplazada**.

---

## D-01 · Motor de base de datos: PostgreSQL (Neon en producción)

- **Estado:** Aceptada (2026-11-14)
- **Decisión:** usar PostgreSQL para la fuente operacional, el staging y el Data Warehouse.
  En producción se aloja en **Neon** (PostgreSQL administrado y serverless).
- **Alternativa considerada:** SQL Server para staging y DW, como sugiere la guía.
- **Justificación:**
  - El docente aceptó PostgreSQL como tecnología equivalente.
  - PostgreSQL cubre todo lo que exige el modelo dimensional: esquemas, claves sustitutas
    (`GENERATED ... AS IDENTITY`), `MERGE` (desde la versión 15) para SCD, restricciones,
    índices, vistas y vistas materializadas.
  - Neon tiene un plan gratuito suficiente para el volumen del proyecto y no requiere
    administrar servidores.
- **Consecuencias:** los scripts SQL se escriben en dialecto PostgreSQL.

## D-02 · Fuente de datos: módulo de ventas de WideWorldImporters

- **Estado:** Aceptada (2026-11-14)
- **Decisión:** usar el módulo de ventas de WideWorldImporters (clientes, productos,
  vendedores, geografía, órdenes y facturas), migrado una sola vez a PostgreSQL.
- **Alternativa considerada:** Pagila (muestra nativa de PostgreSQL).
- **Justificación:** WideWorldImporters tiene unos 3.4 años de ventas diarias
  (~228k líneas de factura), lo que permite analizar tendencias, comparar períodos y
  entrenar un pronóstico. Pagila solo cubre pocos meses, insuficiente para un pronóstico
  confiable (la guía pide no prometerlo si faltan observaciones temporales).
- **Consecuencias:** se necesita un script de migración inicial (Fase 1), documentado
  y reproducible.

## D-03 · Separación de bases: operacional vs. analítica

- **Estado:** Aceptada (2026-11-14)
- **Decisión:**
  - `wwi_oltp`: base operacional (simula el sistema de la empresa).
  - `faro_analytics`: staging (`raw`, `clean`, `ready`, cuarentena, auditoría) y
    Data Warehouse, separados por **esquemas**.
  - En Neon, cada una es un **proyecto distinto** (`wwi-oltp` y `faro-analytics`),
    con cómputo, cuota y credenciales separados.
- **Justificación:** la fuente y la analítica son sistemas distintos en la vida real.
  Staging y DW comparten base para poder transformar con SQL dentro del motor
  (PostgreSQL no consulta entre bases sin extensiones).

## D-04 · Entornos: desarrollo en Docker, producción en Neon

- **Estado:** Aceptada (2026-11-14)
- **Decisión:** desarrollar contra PostgreSQL 17 en Docker y desplegar en Neon con la
  misma versión mayor.
- **Justificación:** las pruebas y cargas repetidas son rápidas, funcionan sin internet y
  no consumen las horas de cómputo del plan gratuito de Neon. Usar la misma versión evita
  diferencias entre entornos.

## D-05 · Python 3.12 gestionado con uv

- **Estado:** Aceptada (2026-11-14)
- **Decisión:** Python 3.12 instalado y gestionado por `uv`; dependencias fijadas en `uv.lock`.
- **Justificación:** instalación reproducible con un comando (`uv sync`) y aislada del
  Python del sistema.

## D-06 · Manejo de secretos

- **Estado:** Aceptada (2026-11-14)
- **Decisión:** credenciales solo en `.env` (excluido de Git). El repositorio incluye
  `.env.example` sin valores reales. Los scripts nunca imprimen cadenas de conexión.

## D-07 · Nombre del proyecto: Faro

- **Estado:** Aceptada (2026-11-14)
- **Decisión:** la plataforma se llama **Faro — Plataforma de Analítica Inteligente de Ventas**.
  Identificador técnico: `faro-analytics` (repositorio, paquete Python, proyecto Neon).
- **Convención:** el prefijo `wwi_` identifica lo que pertenece a la empresa (la fuente
  operacional) y `faro_` lo que pertenece a la plataforma analítica. Así queda claro qué
  es dato de origen y qué es producto del proceso.

## D-08 · Flujo de Git y CI/CD con GitHub Actions

- **Estado:** Aceptada (2026-11-14)
- **Decisión:**
  - Repositorio público en GitHub (`jespinal899/Faro`). `main` siempre estable; cada cambio
    entra por rama y Pull Request. Commits en formato *Conventional Commits*.
  - **CI** en GitHub Actions con tres jobs: calidad (`ruff`), pruebas (`pytest` con un
    PostgreSQL 17 temporal como servicio) y validación de `docker-compose`.
  - **CD** incremental: migraciones de base de datos hacia Neon (Fase 1) y despliegue de la
    aplicación (Fase 5). Las credenciales de producción irán en *GitHub Secrets*,
    nunca en el repositorio.
- **Alternativas consideradas:** GitLab CI o Jenkins. Se elige GitHub Actions porque el código
  ya está en GitHub y es gratuito en repositorios públicos.
- **Justificación:** cada cambio se verifica automáticamente antes de integrarse, y el historial
  de ejecuciones sirve como evidencia de pruebas (la guía lo pide en la sección 12).
- **Seguridad:** el repositorio es público, así que `.env` está excluido por `.gitignore`.
  El pipeline corre con permisos mínimos (`contents: read`) y las acciones usan versiones fijas.

## D-09 · Alcance: proceso de ventas

- **Estado:** Aceptada (2026-11-14)
- **Decisión:** Faro cubre el proceso de **ventas** (pedido → factura → entrega). Quedan fuera
  compras, movimientos de inventario y pagos de clientes.
- **Justificación:** la guía recomienda un proceso principal resuelto de punta a punta.
  Ventas tiene el mayor volumen (228k líneas de factura) y responde las preguntas de
  negocio más relevantes. Detalle en
  [alcance-y-preguntas.md](../arquitectura/alcance-y-preguntas.md).

## D-10 · Documentación generada desde la base (*docs as code*)

- **Estado:** Aceptada (2026-11-14)
- **Decisión:** el diccionario de datos, el diagrama entidad-relación y el perfil de calidad
  se **generan con scripts** a partir del catálogo de PostgreSQL. No se editan a mano.
- **Alternativa considerada:** escribirlos a mano (en Word o en una herramienta de diagramas).
- **Justificación:** la documentación nunca queda desactualizada respecto de la base real, se
  versiona en Git y cualquiera puede regenerarla con un comando. El diagrama en Mermaid es
  editable y GitHub lo muestra directamente.

## D-11 · Producción en Neon y despliegue continuo (CD)

- **Estado:** Aceptada (2026-11-15)
- **Decisión:**
  - Dos proyectos de Neon en la organización del autor, ambos con PostgreSQL 17 en
    `aws-us-east-2` y rama `production`: **wwi-oltp** (base `wwi_oltp`) y
    **faro-analytics** (base `faro_analytics`).
  - La carga inicial de la fuente usa el mismo script que en local (`migrar_wwi.py`),
    con conexión **directa** (sin *pooler*), como recomienda Neon para migraciones y
    cargas masivas.
  - **CD con GitHub Actions** (`cd-neon.yml`): al integrar a `main` un cambio del esquema,
    lo aplica en Neon en una sola transacción y verifica el resultado con las pruebas de
    integración contra producción.
  - Las credenciales son *secrets* del *environment* `production` de GitHub, que solo
    permite desplegar desde `main`.
- **Alternativa considerada:** `neon init` + `neon.ts` + `neon deploy` (flujo de Neon para
  apps JavaScript). Se descartó porque vincula la carpeta a un solo proyecto y Faro usa dos,
  y porque agregaría dependencias de npm a un proyecto Python sin aportar nada para un
  despliegue que solo usa Postgres.
- **Pendiente (Fase 3):** reemplazar el rol dueño (`*_owner`) por roles de mínimo privilegio
  para el ETL, la API y el asistente de IA.

## D-12 · Arquitectura por capas con lotes incrementales y DW estilo Kimball

- **Estado:** Aceptada (2026-11-15)
- **Decisión:** las 7 capas de la guía:
  - Extracción incremental por lotes (*micro-batch*).
  - Staging de tres zonas más cuarentena.
  - Data Warehouse dimensional en esquema estrella.
  - Una sola API para el dashboard, la IA y las alertas.
- **Alternativas descartadas:**
  - *Streaming* (Kafka, CDC o arquitecturas Lambda/Kappa): ningún caso de uso necesita
    latencia de segundos.
  - DW normalizado (Inmon) o Data Vault: la guía pide un modelo dimensional.
  - Lakehouse (Spark): un volumen de ~120 MB no lo justifica.
- Detalle en [arquitectura.md](../arquitectura/arquitectura.md).

## D-13 · Orquestación con GitHub Actions

- **Estado:** Aceptada (2026-11-15). **Reemplaza** la propuesta inicial de usar Prefect.
- **Decisión:** los pipelines se programan con `cron` en GitHub Actions y también se pueden
  lanzar a mano. La lógica ETL vive en módulos Python independientes del orquestador.
- **Justificación:**
  - El pipeline es lineal (extraer → validar → cargar), sin dependencias complejas, que es
    cuando la guía justifica Airflow.
  - Prefect o Airflow necesitan un servidor encendido todo el tiempo (costo de hosting).
    Con Neon (*scale-to-zero*), un ejecutor efímero que arranca, carga y se apaga es la
    combinación natural.
  - Ya tenemos ahí los *secrets*, los logs por ejecución y el CI/CD. Es gratis en repositorios
    públicos.
- **Limitaciones aceptadas:**
  - El `cron` de GitHub puede retrasarse unos minutos. Se tolera porque la latencia acordada
    es ≤ 1 hora.
  - GitHub desactiva los workflows programados tras 60 días sin actividad en el repositorio.
  - Los reintentos se implementan en el código, con espera creciente.

## D-14 · Staging en zonas, carga incremental por watermark e idempotencia

- **Estado:** Aceptada (2026-11-15)
- **Decisión:**
  - Zonas `stg_raw` (solo se agregan filas), `stg_clean`, `stg_quarantine`, `stg_ready` y `audit`.
  - Watermark por tabla sobre `last_edited_when`, con ventana de solapamiento de 10 minutos;
    el watermark solo avanza si la ejecución completa termina bien.
  - UPSERT por clave natural para que repetir una ejecución no duplique datos.
  - 12 reglas de calidad, cada una con su acción (cuarentena, marcar o aceptar).
- Detalle en [diseno-staging-etl.md](../arquitectura/diseno-staging-etl.md).

## D-15 · Grano de la línea de factura, esquema estrella y SCD

- **Estado:** Aceptada (2026-11-15)
- **Decisión:**
  - `fact_ventas` tiene una fila por línea de factura.
  - Seis dimensiones con clave sustituta y miembro desconocido (`-1`).
  - **SCD Tipo 2** en la segmentación de cliente (categoría, grupo de compra, cliente de
    facturación) y en el precio y grupo principal del producto; Tipo 1 en el resto.
  - `dim_fecha` con clave `AAAAMMDD` y rol doble (factura y pedido).
- **Justificación:** el grano de pedido contaría *backorders* no vendidos (H06); con el grano
  de factura se perdería el producto. Tipo 2 preserva el contexto de cada venta en el momento
  en que ocurrió.
- Detalle en [modelo-dimensional.md](../modelos/modelo-dimensional.md).

## D-16 · Productos en varios grupos: grupo principal + tabla puente

- **Estado:** Aceptada (2026-11-15)
- **Problema:** unir las ventas directamente con producto-grupo infla el total un **60 %**
  (198.0 M → 317.3 M).
- **Decisión:**
  - Cada producto tiene un `grupo_principal`: el **más específico**, según una prioridad fija
    y documentada. Las ventas por grupo principal suman exactamente el total (198 043 439).
  - La tabla `puente_producto_grupo`, con `factor_ponderacion = 1/n`, responde el análisis
    por pertenencia sin duplicar importes.
- **Alternativas descartadas:**
  - Elegir el primer grupo por ID: es arbitrario y deja *Novelty Items* como principal de casi
    todo.
  - Usar solo el puente: complica todas las consultas del dashboard.

## D-17 · Frecuencia y definición de "tiempo real"

- **Estado:** Aceptada (2026-11-15)
- **Decisión:**
  - En producción el ETL corre **una vez por hora**, y además se puede lanzar a mano en la
    demo. "Tiempo real" en Faro significa **latencia ≤ 1 hora** desde la venta hasta el DW y
    las alertas.
  - Un **simulador** genera operación continua a partir del 1-jun-2016 y marca sus datos como
    simulados, como exige la guía.
- **Justificación:** respeta la cuota gratuita de Neon (100 CU-horas por proyecto al mes) y
  evita confundir un batch frecuente con tiempo real.

## D-18 · Zona ready como vistas y regla de supervivencia

- **Estado:** Aceptada (2026-11-15)
- **Decisión:**
  - `stg_ready` son **vistas** sobre `stg_clean`: integran y derivan sin duplicar datos
    (cuida el almacenamiento gratuito de Neon) y nunca quedan desactualizadas.
  - La prioridad de los grupos de producto vive en una tabla de referencia versionada.
  - El factor de ponderación del puente no se redondea: redondear 1/3 a 6 decimales
    descuadraba el total en 41.82.
  - **Supervivencia:** ante varias versiones de un registro gana la **última extraída**
    (el estado actual de la fuente), no la de mayor fecha de modificación. Las pruebas
    mostraron que una versión vieja con fecha futura errónea le ganaba a la corregida.

## D-19 · Roles de mínimo privilegio

- **Estado:** Aceptada (2026-11-15). Cierra el pendiente de D-11.
- **Decisión:** `etl_lector` (solo lectura en la fuente), `wwi_app` (solo inserta pedidos y
  facturas) y `faro_etl` (solo datos de staging y auditoría, sin cambiar la estructura).
  Se crean con SQL y sin privilegios heredados. El dueño de las bases solo se usa en el CD.
- **Contraseñas:** aleatorias, rotables con un script, guardadas solo en `.env` y en los
  *secrets* del *environment* `production`.
- **Evidencia:** pruebas automáticas de lo que cada rol puede y **no** puede hacer.

## D-20 · Simulador de ventas y programación

- **Estado:** Aceptada (2026-11-15)
- **Decisión:**
  - El simulador inserta el siguiente día hábil del reloj de negocio (desde el 1-jun-2016)
    con los patrones del perfilado, y marca todo con la persona *Simulador de ventas*.
  - En producción corre una vez al día; el ETL corre cada hora (D-17). Ambos se pueden
    lanzar a mano para la demo, con opciones de volumen y de registro inválido.
- **Límite conocido:** los datos simulados son aleatorios alrededor del promedio histórico.
  Sirven para demostrar la carga incremental y las alertas, no para evaluar el pronóstico.

## D-21 · Carga del Data Warehouse

- **Estado:** Aceptada (2026-11-15)
- **Decisión:**
  - El DW se carga en la **misma transacción** que el staging: si falla, no queda nada a medias.
  - Orden: dimensiones SCD1 → dimensiones SCD2 → puente → hechos (las claves se resuelven
    antes de insertar los hechos, como pide la guía).
  - Hechos con **UPSERT** por `linea_factura_id`, solo para las líneas afectadas por el lote;
    con el DW vacío se cargan todos (primer despliegue).
  - Cada clave del hecho se resuelve con la versión **vigente en la fecha de la venta**.
  - **Miembro desconocido (-1)** si falta la dimensión: la venta no se pierde, queda contada en la
    auditoría y una ejecución posterior la **reasigna** cuando la dimensión aparece.
  - **SCD2 sobre identificadores**, no sobre nombres. Las pruebas mostraron que versionar por el
    nombre del cliente de facturación creaba una versión nueva al renombrar un cliente (casi
    todos se facturan a sí mismos). Los nombres se refrescan según el ID en todas las versiones.
  - Una versión nueva rige desde el **día siguiente a la última venta cargada** (reloj de negocio),
    válido tanto para la operación real como para la simulada.
- **Evidencia:** 11 controles de validación (`validar_dw.py`) que corren después de cada carga en
  producción, más 10 pruebas automáticas del DW.

## D-22 · API del dashboard y publicación en Vercel

- **Estado:** Aceptada (2026-11-15)
- **Decisión:**
  - **Vercel** (plan Hobby, gratuito) publica en un solo proyecto y un solo dominio el dashboard
    (React, estático) y la API (FastAPI como función de Python bajo `/api`). Al compartir el
    dominio no hay CORS y la sesión viaja en una cookie httpOnly.
  - La API lee **solo vistas aprobadas** (`api.*`) con el rol `faro_api`, por el **pooler** de
    Neon (muchas conexiones cortas). Usa transacciones de solo lectura y corta cada consulta a
    los 8 s.
  - **Autenticación propia:** usuarios en `app.usuario` con hash Argon2id, sesión JWT de
    8 horas y bloqueo tras 5 intentos fallidos (el estado vive en la base, porque las funciones
    no comparten memoria).
  - KPI con comparación contra el **mismo período del año anterior**. En semanas y días se
    corre 364 días para comparar el mismo día de la semana, porque los domingos no hay ventas.
- **Alternativas consideradas:** Render (gratis, pero el servicio se duerme a los 15 minutos y
  tarda ~1 minuto en despertar, malo para una demo); dos proyectos separados para frontend y
  API (obliga a CORS y a cookies entre dominios).
- **Consecuencias:** Vercel no admite WebSockets en funciones: las alertas de la Fase 7 se
  consultarán periódicamente (*polling*), lo que la guía permite. Las consultas deben
  responder en pocos segundos: medidas en < 1 s con los datos completos.
- **Implementación (2026-11-15):**
  - Se usó **Vercel Services**, la forma que hoy documenta Vercel para un backend en Python
    junto a un frontend, en lugar del antiguo `api/index.py`. `vercel.json` declara dos
    servicios: `dashboard` (`frontend/`) y `api` (`backend/`). La API recibe la ruta original
    (`/api/kpis`), así que el código no cambia entre local y producción.
  - Funciones en la región **`cle1`** (Cleveland), la misma zona de AWS que Neon (us-east-2).
    El chequeo de salud con consulta a la base responde en ~0.35 s desde la PC de desarrollo.
  - Las dependencias de la API salen de `uv.lock` (`backend/requirements.txt`, verificado en el
    CI) y Node queda fijo en 24, igual que en local y en el CI.
  - Los *preview* de cada PR quedan protegidos con el inicio de sesión de Vercel; solo el
    dominio de producción es público.

## D-23 · Dashboard web: tecnología y reglas de visualización

- **Estado:** Aceptada (2026-11-15)
- **Decisión:**
  - **React 19 + Vite + TypeScript** (estricto), componentes de **Ant Design 6** (tablas,
    filtros, modo oscuro, textos en español) y gráficos con **Apache ECharts 6** importando
    solo los módulos usados.
  - Reglas de visualización:
    - **un solo eje** por gráfico;
    - período actual contra el **año anterior** (línea discontinua) con leyenda;
    - paleta validada para daltonismo con su propia versión en **modo oscuro**;
    - la variación de los KPI se muestra con **flecha y texto**, no solo con color;
    - cada gráfico tiene una **vista de tabla**;
    - los períodos que el rango cubre solo en parte se marcan con `*`.
  - **Drill-down:**
    - clic en una barra o fila del desglose = filtro por ese valor;
    - clic en una factura = detalle por línea.
  - Los datos **simulados** se señalan en el encabezado y en cada factura, y se pueden excluir.
- **Alternativas consideradas:**
  - Angular: la guía lo admite, pero es más pesado para un solo desarrollador.
  - Recharts: menos opciones de zoom y de accesibilidad que ECharts.
  - Power BI o Superset: no se publican gratis con el inicio de sesión propio de la API.
- **Consecuencias:**
  - TypeScript se queda en la 6.0 porque `typescript-eslint` aún no admite la 7.
  - El sitio pesa unos 560 KB comprimidos, la mayor parte Ant Design y ECharts; van en archivos separados que el navegador guarda en caché.
- **Evidencia:**
  - 23 pruebas unitarias (Vitest) en el CI.
  - Una prueba E2E con Playwright que recorre el flujo completo y genera las
    [capturas](../capturas/).

## D-24 · Modelo de Machine Learning: pronóstico semanal por grupo de producto

- **Estado:** Aceptada (2026-11-15)
- **Decisión:**
  - **Problema:** pronosticar la venta neta semanal de cada grupo principal de producto para
    las 4 semanas siguientes (P10). Lo usa compras para decidir cuánto reponer.
  - **Datos:** la vista controlada `ml.ventas_semanales`, solo ventas reales y semanas completas.
    Un grupo necesita 2 años de historia: Novelty Items (lanzado en 2016) queda excluido con su motivo.
  - **Modelo:** uno solo para los 8 grupos (scikit-learn), sobre ventas relativas al nivel
    reciente, con 13 rezagos y variables de contexto. Se entrena con pesos por volumen.
  - **Evaluación:** validación cruzada temporal de un año (4 pliegues de 13 semanas) para elegir,
    y 16 semanas de prueba para medir. Se compara contra 4 líneas base, la referencia es la media
    móvil de 13 semanas y la métrica principal es el WAPE. El rango probable del 80 % se calibra
    fuera de pliegue.
  - **Servicio:** el registro de versiones vive en `ml.modelo`, las predicciones en `ml.pronostico`
    y el proceso programado es el workflow *ML - Pronóstico* (lunes y a mano). Todo corre con el
    rol `faro_ml`, que no ve el DW.
- **Alternativas consideradas:**
  - Clasificación de abandono de clientes: los 663 clientes compran todo el período, así que no
    hay abandono que aprender.
  - Segmentación: no responde una decisión con métrica verificable.
  - Un modelo estadístico por grupo (ARIMA o suavizado exponencial): 8 modelos con ~3 años cada
    uno es poca historia para estimar estacionalidad, y la guía prioriza scikit-learn.
  - MLflow: la guía lo da como extensión. El registro en PostgreSQL cumple lo exigido (versión,
    parámetros, métricas y fecha) sin otro servicio.
- **Consecuencias:**
  - En un año completo el modelo **empata** con el promedio de 13 semanas (11.5 % contra 11.5 %).
  - En prueba lo mejora un 7 % (13.5 % contra 14.6 %), con su rango calibrado (76 % de cobertura).
  - Se documenta como resultado, no se esconde: la serie es sobre todo "nivel + ruido". Ver
    [modelo-ml.md](../modelos/modelo-ml.md).

## D-25 · Asistente de IA generativa: Claude Haiku 5.5 con herramientas controladas

- **Estado:** Aceptada (2026-11-15)
- **Decisión:**
  - **Proveedor y modelo:** API de Anthropic con **Claude Haiku 5.5**, el modelo más
    económico (US$0.10 / US$0.50 por millón de tokens). El usuario lo eligió para no gastar.
    Corre dentro de la API en Vercel, así que funciona en producción. El modelo se cambia con
    `ASISTENTE_MODELO`.
  - **Acceso a datos:** el modelo no escribe SQL. Solo pide 4 herramientas de un catálogo
    cerrado (indicadores, tendencia, ranking y pronóstico), que validan sus parámetros y usan
    las mismas consultas del dashboard con el rol de solo lectura `faro_api`. Sin datos de
    clientes ni de facturas.
  - **Respuesta:** JSON con hechos (cada uno cita sus consultas, y el servidor verifica que
    existan), predicciones (solo del pronóstico), interpretaciones y sugerencias. Tipos
    `sin_datos`, `fuera_de_alcance` y `aclaracion` para cuando no hay respaldo.
  - **Controles:** sesión, 20 preguntas por hora y 100 por día por usuario, entrada de hasta 500
    caracteres, máximo 6 llamadas al modelo por pregunta, y registro en
    `app.consulta_asistente` sin la respuesta.
  - **Rol `faro_ia` descartado:** el catálogo cerrado se aplica en el código y la base solo
    expone vistas de lectura a `faro_api`. Un rol aparte no agregaría control: el modelo nunca
    toca la base.
- **Alternativas consideradas:**
  - **Ollama local**, que la guía permite: costo cero, pero solo funciona en la PC del usuario
    (no en producción), corre en CPU (20–60 s por respuesta) y es menos fiable con herramientas
    en español.
  - **Texto a SQL generado por la IA:** la guía lo desaconseja (acceso irrestricto).
  - **Claude Opus o Sonnet:** mejor calidad, pero de 20 a 40 veces más caros.
  - **LangChain / LlamaIndex:** innecesarios para 4 herramientas; el SDK oficial alcanza.
- **Consecuencias:**
  - El uso de la API se paga aparte del plan de Claude, con créditos prepagados en la consola.
  - El costo real es de centavos (menos de US$0.002 por pregunta) y cada respuesta muestra el suyo.
- **Evidencia:**
  - 13 pruebas del motor, 6 de la API y 5 del dashboard, todas sin red ni costo.
  - Una evaluación con el modelo real, de 14 preguntas, con valores esperados por SQL independiente.
  - Ver [asistente-ia.md](../arquitectura/asistente-ia.md).
- **Actualización (2026-11-15): proveedor por defecto Groq, gratuito.**
  - **Motivo:** la API de Anthropic exige una recarga mínima de US$5, y el usuario no puede
    pagarla. GitHub Models, otra opción gratuita, fue retirado en julio de 2026.
  - **Decisión:** el proveedor es intercambiable (`ASISTENTE_PROVEEDOR`). Por defecto se usa
    **Groq** con `openai/gpt-oss-120b`: plan gratuito sin tarjeta, funciona en producción
    (Vercel) y responde en 2 a 5 segundos. Ollama queda como respaldo local, y Claude sigue
    disponible si hubiera presupuesto.
  - **Consecuencias, medidas en la cuenta:**
    - 1,000 solicitudes por día y **8,000 tokens por minuto**: 1 o 2 preguntas por minuto.
    - Groq no permite JSON junto con herramientas, así que la respuesta final llega por la
      herramienta `json` (gpt-oss entrega su JSON con una herramienta de ese nombre).
    - Groq no retiene datos de inferencia por defecto.
    - La seguridad, las herramientas, la verificación de citas y las pruebas no cambian.

## D-26 · Alertas: reglas en la base, evaluación tras cada carga y correo por Gmail

- **Estado:** Aceptada (2026-11-15)
- **Decisión:**
  - **Reglas:** tres, P12 a P14: caída de ventas (regla de negocio), pronóstico bajo umbral
    (ML) y ventas bajo costo (regla de negocio). Sus umbrales viven en `alerta.regla`. La
    explicación y la acción recomendada las genera la IA (Groq) y se identifican como tales.
  - **Cuándo:** el evaluador corre al terminar cada carga del ETL y cada pronóstico, y también a
    mano. Siempre mira la última semana completa.
  - **Sin duplicados:** clave única por evento (regla | entidad | período).
  - **Correo:** Gmail por SMTP con contraseña de aplicación. Hasta 3 intentos por evaluación y 6
    en total; cada intento queda registrado.
  - **Dashboard:** una pestaña con polling (Vercel no admite WebSockets).
  - **Rol propio `faro_alertas`:** lee solo las vistas de entrada y el pronóstico, y escribe
    alertas y envíos.
- **Alternativas consideradas:**
  - Un proveedor de correo (Brevo, Resend): otra cuenta y otra clave, sin ventaja para la demo.
  - WebSockets: Vercel no los admite.
  - RabbitMQ o Redis: no hace falta mensajería para tres reglas en micro-lotes.
  - Disparadores en la base (triggers): mezclarían la lógica de negocio con la carga.
- **Consecuencias:**
  - La frecuencia real depende de que GitHub ejecute el ETL programado; hoy lo hace de forma muy
    irregular.
  - Para la demo hay un workflow de **evento simulado**, identificado como simulación, como
    permite la guía.
- **Evidencia:**
  - 15 pruebas unitarias y 5 de integración.
  - Evaluación local real: alerta de ventas bajo costo con explicación de IA y correo recibido,
    sin duplicarse en la segunda evaluación.
  - Ver [alertas.md](../arquitectura/alertas.md).

## D-27 · Monitoreo de la operación en el dashboard

- **Estado:** Aceptada (2026-11-15)
- **Decisión:**
  - Una pestaña **Operación** en el mismo dashboard: ETL, calidad por dimensión, cuarentena,
    modelo vigente y notificaciones.
  - Se lee de tres vistas aprobadas nuevas (`api.monitoreo_etl`, `api.monitoreo_calidad` y
    `api.monitoreo_cuarentena`). Muestran conteos y estados, y del error del ETL solo la primera
    línea, recortada.
  - La pestaña de alertas y la de operación se actualizan cada minuto por *polling*, solo con la
    pestaña del navegador visible.
  - En calidad se distinguen las filas **enviadas a cuarentena** (no entran al DW) de las
    **marcadas** (p. ej. atípicos, que sí entran con su marca), para no alarmar en rojo por avisos.
- **Alternativas consideradas:**
  - Grafana o Metabase: otro servicio que alojar y asegurar, con otro inicio de sesión.
  - Dar a `faro_api` lectura sobre `audit` y la cuarentena: expondría los registros rechazados
    completos.
  - Solo los resúmenes de GitHub Actions: no se ven desde el dashboard ni cubren el modelo y las
    notificaciones.
- **Consecuencias:**
  - El aviso de frescura se pone amarillo cuando GitHub no ejecuta el ETL programado. Hoy pasa
    seguido, y queda a la vista en lugar de ocultarse.
- **Evidencia:**
  - 8 pruebas de la API con el rol `faro_api`.
  - 13 pruebas de Vitest (paneles y consulta periódica).
  - E2E con las capturas 09 a 11.
  - Ver [alertas.md, sección 8](../arquitectura/alertas.md).

---

## Pendientes

| Tema | Fase |
|---|---|
| Disparador fiable para los procesos programados (GitHub retrasa o descarta los cron). Propuesta: cron-job.org + token de alcance mínimo, en [alertas.md, sección 9](../arquitectura/alertas.md) | 7 (documentado, no implementado) |
