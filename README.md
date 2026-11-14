# Faro — Plataforma de Analítica Inteligente de Ventas

[![CI](https://github.com/jespinal899/Faro/actions/workflows/ci.yml/badge.svg)](https://github.com/jespinal899/Faro/actions/workflows/ci.yml)

> Así como un faro ilumina el camino, Faro convierte los datos operacionales
> en información confiable para tomar decisiones.

Faro es una solución de extremo a extremo que toma los datos operacionales de ventas de
**WideWorldImporters** (la empresa), los procesa por un staging con controles de calidad,
los organiza en un **Data Warehouse dimensional** y habilita dashboard,
Machine Learning, un asistente de IA generativa y alertas automáticas.

**Convención de nombres:** `wwi_*` = sistema operacional de la empresa (la fuente) ·
`faro_*` = nuestra plataforma analítica.

| Componente | Tecnología |
|---|---|
| Bases de datos | PostgreSQL 17 — Docker (desarrollo) / Neon (producción) |
| ETL y ML | Python 3.12 (gestionado con `uv`) |
| Contenedores | Docker + Docker Compose |

Las decisiones técnicas y su justificación están en
[documentation/decisiones/registro-decisiones.md](documentation/decisiones/registro-decisiones.md).

---

## Estado por fases

| Fase | Contenido | Estado |
|---|---|---|
| 0. Entorno | Python, Docker, PostgreSQL local, repositorio, CI | ✅ Completa |
| 1. Descubrimiento | Cargar la fuente, ERD, diccionario, perfilado, preguntas analíticas | ⏳ Siguiente |
| 2. Diseño | Arquitectura, staging, grano, dimensiones | — |
| 3. ETL y calidad | Extracción, limpieza, auditoría, cuarentena | — |
| 4. Data Warehouse | Modelo dimensional, cargas, SCD, reconciliación | — |
| 5. BI | API y dashboard | — |
| 6. ML y GenAI | Modelo predictivo y asistente | — |
| 7. Automatización | Alertas y monitoreo | — |
| 8. Integración | Pruebas end-to-end, despliegue, video | — |

---

## Requisitos

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- [uv](https://docs.astral.sh/uv/) (instala y gestiona Python 3.12 automáticamente)
- Git

## Puesta en marcha (desarrollo local)

```powershell
# 1. Variables de entorno: copiar la plantilla y poner una contraseña propia
copy .env.example .env
#    (editar .env y reemplazar "cambia_esta_clave" en las 3 líneas donde aparece)

# 2. Levantar PostgreSQL (crea las bases wwi_oltp y faro_analytics)
docker compose up -d
docker compose ps          # debe mostrar "healthy"

# 3. Instalar Python 3.12 y las dependencias exactas (uv.lock)
uv sync

# 4. Verificar que Python se conecta a ambas bases
uv run python database/scripts/verificar_conexion.py
```

Resultado esperado:

```
[OK]    Fuente (OLTP): base=wwi_oltp usuario=admin PostgreSQL 17.x
[OK]    Analítica (staging + DW): base=faro_analytics usuario=admin PostgreSQL 17.x
```

## Calidad y pruebas (lo mismo que ejecuta el CI)

```powershell
uv run ruff check .            # errores y malas prácticas
uv run ruff format .           # aplica el formato estándar
uv run pytest -v               # pruebas (las de integración requieren la base levantada)
```

## Flujo de trabajo con Git y CI/CD

1. `main` siempre debe funcionar. Cada cambio se hace en una rama
   (`fase-1/carga-fuente`, `ci/...`, `docs/...`).
2. Commits en formato *Conventional Commits*: `feat:`, `fix:`, `docs:`, `test:`, `ci:`, `chore:`.
3. Se abre un **Pull Request** hacia `main`. GitHub Actions ejecuta automáticamente:

   | Job | Qué valida |
   |---|---|
   | Calidad de código | `ruff` sin errores y con formato correcto |
   | Pruebas | `pytest` contra un PostgreSQL 17 temporal (misma versión que Neon) |
   | Validar docker-compose | que el archivo de Docker sea válido |

4. Solo se integra a `main` si todos los jobs pasan.
5. **CD (despliegue continuo):** se agrega por etapas, cuando exista algo que desplegar.
   Primero los esquemas de base de datos hacia Neon (Fase 1) y después la aplicación (Fase 5).

## Reiniciar el entorno desde cero

```powershell
docker compose down -v     # borra el contenedor Y los datos
docker compose up -d       # vuelve a crear las bases vacías
```

## Puertos

| Servicio | Puerto en tu máquina |
|---|---|
| PostgreSQL | `5433` (el 5432 lo usa otro proyecto) |

## Estructura del repositorio

```
├── documentation/      decisiones, arquitectura, modelos, manuales, pruebas
├── database/           scripts SQL de fuente, staging y data warehouse
├── etl/                extracción, transformación, carga y orquestación
├── backend/            API
├── frontend/           dashboard web
├── machine-learning/   notebooks, entrenamiento, evaluación, modelos
├── generative-ai/      asistente analítico
├── notifications/      alertas
├── tests/              pruebas automatizadas (pytest)
├── .github/workflows/  pipelines de CI/CD (GitHub Actions)
├── deployment/         configuración de producción
├── docker-compose.yml  entorno de desarrollo
├── pyproject.toml      dependencias de Python (uv)
└── .env.example        plantilla de variables (sin secretos)
```
