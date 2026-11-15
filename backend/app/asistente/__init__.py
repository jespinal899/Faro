"""Asistente analítico de IA (Fase 6, pregunta P11). Decisión D-25.

El modelo de lenguaje NUNCA ejecuta SQL: solo puede pedir las herramientas de
`herramientas.py`, que validan sus parámetros y llaman a las mismas consultas del dashboard
(vistas aprobadas, rol de solo lectura). La respuesta separa hechos consultados, predicciones
e interpretaciones, y cada hecho cita las consultas que lo respaldan.
"""
