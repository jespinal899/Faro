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
# Requiere GROQ_API_KEY en .env (plan gratuito de Groq). --pausa espacia las preguntas para
# respetar el límite de tokens por minuto (por defecto 20 s).
uv run python generative-ai/evaluar_asistente.py          # API en proceso + base local
uv run python generative-ai/evaluar_asistente.py --neon   # API en proceso + Neon (producción)
```

## Configuración

| Variable | Dónde | Valor |
|---|---|---|
| `ASISTENTE_PROVEEDOR` | Opcional | `groq` (por defecto, gratis), `ollama` (local) o `anthropic` (Claude, de pago) |
| `GROQ_API_KEY` | `.env` local y Vercel (*sensitive*) | Clave gratuita de https://console.groq.com |
| `ANTHROPIC_API_KEY` / `OLLAMA_BASE_URL` | Opcional | Solo para esos proveedores |
| `ASISTENTE_MODELO` | Opcional | Por defecto el del proveedor (`openai/gpt-oss-120b` en Groq) |
| `ASISTENTE_LIMITE_HORA` / `ASISTENTE_LIMITE_DIA` | Opcional | 20 / 100 preguntas por usuario |

Diseño completo, requisitos de seguridad de la guía y costos:
[documentation/arquitectura/asistente-ia.md](../documentation/arquitectura/asistente-ia.md).
