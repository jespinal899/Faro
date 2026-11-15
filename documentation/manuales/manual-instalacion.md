# Manual de instalación (entorno local) — Faro

Para quien quiera **levantar la solución completa en su computadora** desde cero: bases, ETL,
Data Warehouse, modelo, API, dashboard, asistente y alertas. Para publicarla en internet, ver el
[manual de despliegue](manual-despliegue.md).

Tiempo estimado: 30 a 45 minutos, la mayor parte en descargas.

---

## 1. Requisitos

| Herramienta | Versión | Para qué |
|---|---|---|
| [Git](https://git-scm.com/) | cualquiera reciente | Clonar el repositorio |
| [Docker Desktop](https://www.docker.com/products/docker-desktop/) | con Docker Compose v2 | PostgreSQL 17 local (y un SQL Server temporal para cargar la fuente) |
| [uv](https://docs.astral.sh/uv/) | reciente (probado con 0.12) | Instala Python 3.12 y las dependencias exactas (`uv.lock`) |
| [Node.js](https://nodejs.org/) | 24 (probado con 24.11) | Dashboard (React) |
| [go-sqlcmd](https://learn.microsoft.com/sql/tools/sqlcmd/go-sqlcmd-utility) | cualquiera | **Solo** para restaurar el respaldo de WideWorldImporters (paso 5) |

Equipo: 8 GB de RAM (el SQL Server temporal usa unos 2 GB) y unos 3 GB libres en disco.

> No hace falta instalar Python a mano: `uv` descarga Python 3.12 aunque haya otra versión en el
> `PATH`.

## 2. Obtener el código y configurar las variables

```powershell
git clone https://github.com/jespinal899/Faro.git
cd Faro
copy .env.example .env        # en macOS/Linux: cp .env.example .env
```

Editar `.env`:

| Variable | Qué poner |
|---|---|
| `POSTGRES_PASSWORD` | Una contraseña propia. Repetirla en `SOURCE_DATABASE_URL` y `ANALYTICS_DATABASE_URL` (donde dice `cambia_esta_clave`). |
| `MSSQL_SA_PASSWORD` | Mínimo 8 caracteres con mayúsculas, minúsculas y números (SQL Server temporal). |
| `JWT_SECRET` | Un secreto aleatorio: `uv run python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `COOKIE_SEGURA` | Dejar `false` en local (no hay HTTPS). |
| `GROQ_API_KEY` | Opcional: clave gratuita de https://console.groq.com para el asistente y las explicaciones de las alertas. |
| `SMTP_USUARIO`, `SMTP_PASSWORD`, `ALERTAS_DESTINO` | Opcional: Gmail con [contraseña de aplicación](https://myaccount.google.com/apppasswords) para el correo de alertas. |

El archivo `.env` **nunca** se sube al repositorio (está en `.gitignore`).

## 3. Levantar PostgreSQL

```powershell
docker compose up -d
docker compose ps                 # debe decir "healthy"
```

Crea un PostgreSQL 17 en el puerto **5433** con dos bases: `wwi_oltp` (la fuente) y
`faro_analytics` (staging, DW, modelo y alertas).

## 4. Instalar las dependencias de Python y verificar

```powershell
uv sync --group ml --group seed   # Python 3.12 + dependencias exactas (ETL, API, ML y carga)
uv run python database/scripts/verificar_conexion.py
```

Resultado esperado:

```
[OK]    Fuente (OLTP): base=wwi_oltp usuario=admin PostgreSQL 17.x
[OK]    Analítica (staging + DW): base=faro_analytics usuario=admin PostgreSQL 17.x
```

## 5. Cargar la fuente (WideWorldImporters)

Microsoft publica WideWorldImporters solo como respaldo de SQL Server. Se restaura en un SQL
Server **temporal** y se migra el módulo de ventas a PostgreSQL:

```powershell
# 5.1 SQL Server temporal (descarga el respaldo oficial, 121 MB)
docker compose --env-file .env -f database/source/seed/docker-compose.seed.yml up -d

# 5.2 Restaurar el respaldo (en PowerShell; en bash: export SQLCMDPASSWORD=...)
$env:SQLCMDPASSWORD = "<el valor de MSSQL_SA_PASSWORD>"
sqlcmd -S localhost,14330 -U sa -C -b -i database/source/seed/01_restaurar_wwi.sql

# 5.3 Migrar a PostgreSQL: esquema + datos + reconciliación (~45 s; se puede repetir)
uv run --group seed python database/source/seed/migrar_wwi.py

# 5.4 Borrar el SQL Server temporal (ya no se usa)
docker compose --env-file .env -f database/source/seed/docker-compose.seed.yml down -v
```

Resultado: 17 tablas y 644,488 filas, con conteos y sumas de control verificados. El reporte
queda en `documentation/pruebas/reconciliacion-carga-fuente-local.md`.

## 6. Crear staging, auditoría, Data Warehouse, modelo y alertas

Los scripts SQL son idempotentes y se aplican en orden (en producción lo hace el workflow
*CD - Neon*):

```powershell
Get-ChildItem database/staging/*.sql, database/data-warehouse/*.sql | ForEach-Object {
  Get-Content $_ -Raw | docker exec -i faro-postgres psql -U admin -d faro_analytics -v ON_ERROR_STOP=1 -q
}
Get-Content database/security/roles_analitica.sql -Raw | docker exec -i faro-postgres psql -U admin -d faro_analytics -v ON_ERROR_STOP=1 -q
```

En bash:

```bash
for f in database/staging/*.sql database/data-warehouse/*.sql database/security/roles_analitica.sql; do
  docker exec -i faro-postgres psql -U admin -d faro_analytics -v ON_ERROR_STOP=1 -q < "$f"
done
```

Opcional, para trabajar en local con los **mismos roles** que producción:
`uv run python database/scripts/configurar_roles.py --entorno local`. Escribe sus conexiones en
el `.env` y no las muestra.

## 7. Primera carga: ETL y Data Warehouse

```powershell
uv run python -m etl.orchestration.pipeline --modo inicial   # ~30 s: staging + DW
uv run python database/scripts/validar_dw.py                 # 11 controles: deben pasar todos
```

Desde ahí, cada `uv run python -m etl.orchestration.pipeline` (sin `--modo`) carga **solo lo
nuevo**. Para generar ventas nuevas (identificadas como **simuladas**):

```powershell
uv run python -m simulador.ventas --dias 5
uv run python -m etl.orchestration.pipeline
```

## 8. Modelo de pronóstico

```powershell
uv run --group ml python -m machine_learning entrenar   # entrena, evalúa y registra la versión
uv run --group ml python -m machine_learning predecir   # pronostica las 4 semanas siguientes
```

El reporte de evaluación queda en `documentation/pruebas/evaluacion-ml-local.md`.

## 9. Usuario del dashboard, API y dashboard

```powershell
# Una sola vez: usuario de demostración (la contraseña queda en .env como FARO_PASSWORD_DEMO)
uv run python database/scripts/crear_usuario.py --usuario demo --nombre "Usuario Demo"

# Terminal 1: API (documentación interactiva en http://localhost:8000/api/docs)
uv run uvicorn backend.app.main:app --reload --port 8000

# Terminal 2: dashboard
cd frontend
npm ci
npm run dev                       # http://localhost:5173
```

Abrir http://localhost:5173 e ingresar con `demo` y la contraseña `FARO_PASSWORD_DEMO` del `.env`.
El uso del dashboard está en el [manual de usuario](manual-usuario.md).

## 10. Asistente de IA y alertas (opcional)

- **Asistente:** con `GROQ_API_KEY` en el `.env`, la pestaña *Asistente (IA)* funciona al
  reiniciar la API. Sin clave, la pestaña lo explica y el resto del dashboard sigue igual.
- **Alertas:**

```powershell
uv run python -m notifications prueba-correo          # verifica la cuenta de Gmail
uv run python -m notifications evaluar --sin-correo   # evalúa las reglas sin enviar correos
uv run python -m notifications evaluar                # evalúa y envía las alertas nuevas
```

Las alertas aparecen en la pestaña *Alertas* del dashboard.

## 11. Verificar la instalación

```powershell
uv run ruff check .
uv run pytest -q                  # 175 pruebas (crean y borran sus propias bases temporales)
cd frontend
npm run lint; npm test; npm run build
npx playwright install chromium   # una sola vez
npm run e2e                       # recorre el dashboard en un navegador real
```

## 12. Puertos

| Servicio | Puerto |
|---|---|
| PostgreSQL | `5433` (el 5432 suele estar ocupado por otra instalación) |
| SQL Server temporal (solo en el paso 5) | `14330` |
| API | `8000` |
| Dashboard | `5173` |

## 13. Problemas frecuentes

| Síntoma | Causa y solución |
|---|---|
| `Define POSTGRES_PASSWORD en el archivo .env` | Falta el `.env` o la variable: repetir el paso 2. |
| `port is already allocated` al levantar Docker | El puerto 5433 está ocupado: cambiar `POSTGRES_PORT` y el puerto de las dos URL del `.env`. |
| `verificar_conexion.py` falla con *password authentication failed* | La contraseña de las URL no coincide con `POSTGRES_PASSWORD`. Si se cambió después de crear el volumen: `docker compose down -v` y volver a empezar desde el paso 3. |
| `sqlcmd` no se reconoce | Instalar go-sqlcmd (solo se usa en el paso 5). |
| La API responde 503 | La base no está levantada (`docker compose ps`) o, en Neon, se está despertando: reintentar. |
| «Cuenta bloqueada temporalmente» al ingresar | 5 intentos fallidos: esperar 15 minutos (o ver el [manual de operación](manual-operacion.md#r12-cuenta-del-dashboard-bloqueada-o-contraseña-perdida)). |
| El asistente dice que no está configurado | Falta `GROQ_API_KEY` en el `.env`; reiniciar la API después de agregarla. |

## 14. Reiniciar el entorno desde cero

```powershell
docker compose down -v            # borra el contenedor Y los datos
docker compose up -d              # bases vacías
# y repetir desde el paso 5
```

El orden completo de recuperación (con producción incluida) está en el
[manual de operación](manual-operacion.md#4-recuperación-reproducible-scripts-en-orden).
