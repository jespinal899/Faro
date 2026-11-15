# Despliegue

La guía sugiere una carpeta `deployment/` para Docker y Compose. En Faro la configuración de cada
entorno vive junto a lo que despliega, y esta carpeta solo la indexa:

| Entorno | Archivo | Qué hace |
|---|---|---|
| Desarrollo | [docker-compose.yml](../docker-compose.yml) | PostgreSQL 17 local (puerto 5433) con las bases `wwi_oltp` y `faro_analytics` |
| Desarrollo (una vez) | [database/source/seed/docker-compose.seed.yml](../database/source/seed/docker-compose.seed.yml) | SQL Server temporal para restaurar el respaldo de WideWorldImporters |
| Producción: dashboard y API | [vercel.json](../vercel.json) | Dos servicios en Vercel (Vite + FastAPI), región `cle1` |
| Producción: bases | [.github/workflows/cd-neon.yml](../.github/workflows/cd-neon.yml) | Aplica esquemas y permisos en Neon desde `main` |
| Producción: procesos | [.github/workflows/](../.github/workflows/) | ETL, simulador, pronóstico y alertas (GitHub Actions) |
| Permisos | [database/security/](../database/security/) | Roles de mínimo privilegio |

Pasos completos: [manual de despliegue](../documentation/manuales/manual-despliegue.md).
