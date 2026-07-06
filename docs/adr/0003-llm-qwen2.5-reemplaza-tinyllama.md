# Qwen2.5:3b-instruct reemplaza a TinyLlama como LLM de generación

`docs/arquitectura_tecnica.md` justifica TinyLlama (1.1B) por restricción de hardware (Mac Intel sin GPU) y documenta trucos de prompt (seed `"Respuesta:"`, stop sequences agresivas) diseñados específicamente para compensar que TinyLlama repetía el prompt. En la práctica, TinyLlama alucinaba normativa y citaba mal la fuente — inaceptable para un asistente que debe basar toda respuesta en documentos recuperados. Se reemplaza por `qwen2.5:3b-instruct-q4_K_M`, ~3x más grande, a costa de generación más lenta en CPU.

Los trucos de prompt de TinyLlama se mantienen tal cual por ahora (no rompen nada con Qwen); se revisarán/simplificarán después de validar Qwen2.5 con el corpus de tesis real, no a priori.

## Reapertura — el LLM de producción se revalida empíricamente

Esta decisión deja de estar "cerrada": el proyecto ahora incluye un benchmark (`scripts/run_benchmark.py`) que compara múltiples LLMs disponibles en Ollama (tiempo de respuesta + métricas RAGAS) sobre el corpus de tesis. `qwen2.5:3b-instruct-q4_K_M` sigue siendo el default en `config.LLM_MODEL` y el modelo de producción, pero esa elección queda sujeta a lo que muestren los datos del benchmark, no a un criterio fijo. `HybridRetriever` y `ResponseAgent` aceptan el modelo/modo como parámetro explícito precisamente para permitir esta comparación sin reiniciar el proceso ni tocar `config.py` por cada corrida. El razonamiento histórico de por qué se abandonó TinyLlama (arriba) sigue siendo válido y no se re-litiga — lo que se reabre es únicamente si Qwen2.5 sigue siendo la mejor opción *entre las disponibles hoy*.
