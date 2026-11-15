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

---

## Pendientes

| Tema | Fase |
|---|---|
| Orquestador de pipelines | 3 |
| Estrategia SCD por dimensión | 4 |
| Backend, frontend y hosting de la aplicación | 5 |
| Modelo de ML y proveedor de IA generativa | 6 |
| Canales de notificación | 7 |
