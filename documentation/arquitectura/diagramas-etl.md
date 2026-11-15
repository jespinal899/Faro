# Diagramas de extracción, transformación, carga y orquestación — Faro

La guía (sección 11) pide diagramas del ETL y de la orquestación. Están en Mermaid, así que son
**editables** y GitHub los dibuja. Cada diagrama describe el código actual:
- [pipeline.py](../../etl/orchestration/pipeline.py)
- [extraer.py](../../etl/extraction/extraer.py)
- [limpiar.py](../../etl/transformation/limpiar.py)
- [cargar_dw.py](../../etl/loading/cargar_dw.py)
- [.github/workflows](../../.github/workflows/)

Diseño y justificación: [diseno-staging-etl.md](diseno-staging-etl.md) ·
reglas: [catálogo de reglas](../modelos/catalogo-reglas-calidad.md) ·
modelo: [modelo dimensional](../modelos/modelo-dimensional.md).

---

## 1. Vista de una ejecución completa

Una ejecución del pipeline es **una sola transacción** en la base analítica: o se aplica todo
(staging, DW y watermarks), o no se aplica nada.

```mermaid
flowchart TB
    INI([Inicio]) --> LOCK{"¿Candado libre?<br/>pg_try_advisory_lock"}
    LOCK -- no --> FIN0([Termina: ya hay otra ejecución])
    LOCK -- sí --> AUD0["audit.etl_execution<br/>estado = en_curso"]
    AUD0 --> MODO{"¿Modo inicial?"}
    MODO -- sí --> VAC["Vaciar staging y cuarentena<br/>borrar watermarks (= −infinity)<br/>el DW se vacía al cargarlo"]
    MODO -- no --> CAT
    VAC --> CAT["Sincronizar catálogo de reglas<br/>(audit.dq_rule)"]
    CAT --> EXT["1 · EXTRAER las 17 tablas<br/>(sección 2)"]
    EXT --> LIM["2 · LIMPIAR y VALIDAR<br/>(sección 3)"]
    LIM --> REC1["Reconciliar fuente ↔ staging"]
    REC1 --> DW["3 · CARGAR el DW<br/>(sección 4)"]
    DW --> REC2["Reconciliar staging ↔ DW"]
    REC2 --> WM["Avanzar watermarks<br/>(solo ahora)"]
    WM --> OK["estado = exitoso<br/>conteos y reconciliación"]
    OK --> COMMIT([COMMIT])

    EXT & LIM & DW -. error .-> ERR["ROLLBACK de los datos<br/>estado = fallido + error_detail<br/>watermark sin avanzar"]
    ERR --> FIN1([La próxima ejecución reprocesa el mismo rango])
```

## 2. Extracción (fuente → `stg_raw`)

```mermaid
flowchart LR
    subgraph SRC["wwi_oltp (rol etl_lector, solo lectura,<br/>REPEATABLE READ: una foto consistente)"]
        T[("17 tablas<br/>application, warehouse, sales")]
    end
    subgraph A["faro_analytics (rol faro_etl)"]
        W[("audit.watermark<br/>último last_edited_when por tabla")]
        R[("stg_raw.&lt;tabla&gt;<br/>+ _batch_id, _source_table,<br/>_extracted_at")]
        S[("audit.etl_step<br/>extract: leídas, rango, ms")]
    end
    W -- "desde = watermark − 10 min<br/>(solapamiento: registros tardíos)" --> Q["COPY (SELECT … WHERE<br/>last_edited_when > desde)<br/>de la fuente directo a stg_raw"]
    T --> Q --> R
    R --> NW["Nuevo watermark = máximo recibido<br/>(sin marcas futuras > ahora + 5 min,<br/>que van a cuarentena por O02)"]
    Q -. registra .-> S
```

- **Inicial:** el watermark es `-infinity`, así que se lee todo. **Incremental:** solo lo
  modificado desde el último watermark, con 10 minutos de solapamiento.
- `stg_raw` **solo agrega filas**: nunca sobrescribe lo recibido, que es la historia de cada
  registro.
- Un trigger en la fuente actualiza `last_edited_when` en cada UPDATE, así ningún cambio
  escapa al watermark.
- Conexión con **3 reintentos** y espera creciente si Neon está despertando.

## 3. Transformación y calidad (`stg_raw` → `stg_clean` / `stg_quarantine` → `stg_ready`)

```mermaid
flowchart LR
    R[("stg_raw<br/>lote nuevo")] --> D{"¿Idéntica a la<br/>versión vigente?"}
    D -- sí --> X["Se descarta<br/>(releída por el solapamiento)"]
    D -- no --> C["Candidatos =<br/>lote nuevo + cuarentena pendiente<br/>(reintento)"]
    C --> U["U03 supervivencia:<br/>una versión por clave<br/>(la última extraída)"]
    U --> RG{"Reglas de calidad<br/>(16 reglas · 35 controles)"}
    RG -- "falla regla de cuarentena" --> Q[("stg_quarantine.registro_rechazado<br/>regla, detalle, registro original,<br/>ejecución")]
    RG -- "falla regla de marca" --> M["Pasa marcada<br/>(atípico, bajo costo, fecha)"]
    RG -- cumple --> L
    M --> L["Limpieza de textos<br/>(control, espacios)"]
    L --> CL[("stg_clean<br/>UPSERT solo si cambió")]
    CL --> RS["Rechazos anteriores que ahora<br/>pasan → resolved_at"]
    CL --> RD[["stg_ready (vistas)<br/>ventas por línea, clientes, productos<br/>con grupo principal, geografía, empleados"]]
    RG -. por regla .-> DQ[("audit.dq_result<br/>evaluadas / fallaron")]
```

- Las tablas se limpian **de padres a hijos**: las reglas de integridad (I02, I08 a I12) buscan
  al padre en `stg_clean`, y si el padre está en cuarentena, el hijo también espera.
- `stg_ready` son **vistas**: integran las entidades al grano del DW, resuelven los nulos según
  su causa y calculan venta neta, costo y utilidad (D-18).

## 4. Carga del Data Warehouse (`stg_ready` → `dw`)

```mermaid
flowchart TB
    RE[["stg_ready"]] --> D1["Dimensiones SCD Tipo 1<br/>empleado, geografía, grupo de producto<br/>(UPSERT: corrige en el lugar)"]
    D1 --> D2["Dimensiones SCD Tipo 2<br/>cliente y producto<br/>(nueva versión si cambia el hash;<br/>vigencia desde el reloj de negocio)"]
    D2 --> PU["Puente producto ↔ grupo<br/>(factor de ponderación)"]
    PU --> H["Hechos dw.fact_ventas<br/>UPSERT por invoice_line_id<br/>claves resueltas por fecha de la venta"]
    H --> UNK{"¿Falta la dimensión?"}
    UNK -- sí --> M1["Miembro desconocido (−1)<br/>se reasigna cuando llega"]
    UNK -- no --> OK
    M1 --> OK["Reconciliar: filas y Σ importes<br/>ready = DW"]
    DF[("dw.dim_fecha<br/>calendario precargado")] -. "fecha de factura<br/>y de pedido (rol doble)" .-> H
```

- **Dimensiones antes que hechos**, para que cada hecho encuentre su clave sustituta.
- La versión de una dimensión SCD2 que corresponde a una venta es la **vigente en la fecha de
  la venta**, no la actual.
- Repetir la carga **no duplica**: los hechos se insertan o actualizan por la clave natural de
  la línea de factura.
- Validación posterior: [validar_dw.py](../../database/scripts/validar_dw.py), con 11 controles.

## 5. Orquestación (GitHub Actions)

```mermaid
flowchart TB
    subgraph PROG["Procesos programados (environment production, solo desde main)"]
        SIM["Simulador - Ventas<br/>diario 11:40 UTC + manual<br/>rol wwi_app"]
        ETLW["ETL - Ventas<br/>cada hora, minuto 7 + manual<br/>roles etl_lector y faro_etl"]
        MLW["ML - Pronóstico<br/>lunes 12:30 UTC + manual<br/>rol faro_ml"]
        DEMO["Alertas - Evento simulado<br/>solo manual (demo)"]
    end

    SIM -. "inserta ventas en la fuente;<br/>el ETL siguiente las carga" .-> ETLW
    ETLW --> E1["pipeline (staging + DW)"] --> E2["validar_dw.py"] --> E3["notifications evaluar<br/>rol faro_alertas"] --> E4["Resumen en GitHub"]
    MLW --> M0["(opcional) entrenar y evaluar"] --> M1["predecir 4 semanas"] --> M2["notifications evaluar"]
    DEMO --> D1["simulador: 8 días al 40 %"] --> D2["pipeline + validar_dw.py"] --> D3["notifications evaluar"]

    subgraph CICD["Integración y despliegue continuos"]
        PR["Pull Request"] --> CI["CI: ruff · pytest + PostgreSQL 17 ·<br/>docker-compose · dashboard (lint, Vitest, build)"]
        CI --> MERGE["Rebase a main<br/>(rama protegida)"]
        MERGE --> CD["CD - Neon<br/>esquemas SQL + permisos"]
        MERGE --> VER["Vercel<br/>dashboard + API"]
    end
```

| Workflow | Disparador | Pasos | Concurrencia |
|---|---|---|---|
| [ETL - Ventas](../../.github/workflows/etl-ventas.yml) | `cron` cada hora y manual (modo `incremental` o `inicial`) | pipeline → validar DW → evaluar alertas → resumen | grupo `etl-ventas-production`, más un candado en la base |
| [Simulador - Ventas](../../.github/workflows/simulador-ventas.yml) | `cron` diario y manual | simula el siguiente día hábil (marcado como simulado) | — |
| [ML - Pronóstico](../../.github/workflows/ml-pronostico.yml) | `cron` los lunes y manual (opción de reentrenar) | entrenar (opcional) → predecir → evaluar alertas | grupo `ml-pronostico-production` |
| [Alertas - Evento simulado](../../.github/workflows/alertas-demo.yml) | Solo manual | simular baja venta → ETL → validar → evaluar alertas | comparte el grupo del ETL |
| [CI](../../.github/workflows/ci.yml) | Cada PR y cada push a `main` | ruff, pytest con PostgreSQL 17, docker-compose, dashboard | — |
| [CD - Neon](../../.github/workflows/cd-neon.yml) | Push a `main` con cambios en `database/` y manual | esquemas de la fuente y de la analítica + permisos, en una transacción | — |

**El orquestador solo dispara y encadena:** toda la lógica vive en módulos de Python que se
ejecutan igual en una PC (`uv run ...`) que en GitHub Actions (D-13).

**Limitación conocida:** GitHub no garantiza los horarios de `cron`. Mientras no haya un
disparador externo, los procesos se lanzan a mano
([pendiente documentado](alertas.md#9-pendiente-un-disparador-programado-fiable)).
