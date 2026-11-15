# IA generativa: asistente analítico

El asistente corre dentro de la API (en Vercel), así que su código está en
[backend/app/asistente/](../backend/app/asistente/):

| Archivo | Contenido |
|---|---|
| `herramientas.py` | El catálogo cerrado de consultas que el modelo puede pedir, con su validación |
| `motor.py` | Las instrucciones (`SISTEMA`), el formato de respuesta, el ciclo de herramientas con Claude y la verificación de respaldo |
| `../rutas/asistente.py` | El endpoint: sesión, límite por usuario, registro de cada consulta y errores del servicio de IA |

Esta carpeta tiene las **pruebas con el modelo real**:

| Archivo | Contenido |
|---|---|
| [casos_prueba.py](casos_prueba.py) | 14 preguntas, con su resultado esperado calculado por SQL independiente sobre el DW |
| [evaluar_asistente.py](evaluar_asistente.py) | Hace cada pregunta y genera el reporte en `documentation/pruebas/` |

```powershell
# Requiere ANTHROPIC_API_KEY en .env y saldo en la cuenta de Anthropic (cuesta unos centavos)
uv run python generative-ai/evaluar_asistente.py          # API en proceso + base local
uv run python generative-ai/evaluar_asistente.py --neon   # API en proceso + Neon (producción)
```

## Configuración

| Variable | Dónde | Valor |
|---|---|---|
| `ANTHROPIC_API_KEY` | `.env` local y Vercel (*sensitive*) | Clave de la consola de Anthropic |
| `ASISTENTE_MODELO` | Opcional | Por defecto `claude-haiku-5-5` (el más económico) |
| `ASISTENTE_LIMITE_HORA` / `ASISTENTE_LIMITE_DIA` | Opcional | 20 / 100 preguntas por usuario |

Diseño completo, requisitos de seguridad de la guía y costos:
[documentation/arquitectura/asistente-ia.md](../documentation/arquitectura/asistente-ia.md).
