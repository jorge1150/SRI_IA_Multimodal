# Qwen2.5:3b-instruct reemplaza a TinyLlama como LLM de generación

`docs/arquitectura_tecnica.md` justifica TinyLlama (1.1B) por restricción de hardware (Mac Intel sin GPU) y documenta trucos de prompt (seed `"Respuesta:"`, stop sequences agresivas) diseñados específicamente para compensar que TinyLlama repetía el prompt. En la práctica, TinyLlama alucinaba normativa y citaba mal la fuente — inaceptable para un asistente que debe basar toda respuesta en documentos recuperados. Se reemplaza por `qwen2.5:3b-instruct-q4_K_M`, ~3x más grande, a costa de generación más lenta en CPU.

Los trucos de prompt de TinyLlama se mantienen tal cual por ahora (no rompen nada con Qwen); se revisarán/simplificarán después de validar Qwen2.5 con el corpus de tesis real, no a priori.
