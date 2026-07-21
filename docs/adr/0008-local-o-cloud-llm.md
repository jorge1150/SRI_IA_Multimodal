# Local o cloud: el LLM de generación deja de ser "100% local" por restricción dura

El proyecto se documentó desde el inicio como "100% local, sin conexión a internet en tiempo de ejecución" — un diferenciador de tesis frente a asistentes que dependen de APIs pagas. Probando el sistema real con `LLM_MODEL` apuntando a `gemma3:27b-cloud` (un modelo servido por Ollama Cloud), las respuestas fueron notablemente más coherentes que con `qwen2.5:3b-instruct-q4_K_M` local, con una latencia (~15s) todavía razonable para uso interactivo.

Mantener "100% local" como restricción dura habría significado descartar una opción que mejora la calidad de respuesta medible, solo por una afirmación de arquitectura que ya no refleja lo que el sistema realmente necesita permitir. Se decide dejar de exigirlo — el sistema pasa a soportar modelos locales y en la nube, documentado como una decisión configurable de privacidad/costo vs. calidad/velocidad, no oculta ni forzada.

## Alcance: solo el LLM de texto

Únicamente `LLM_MODEL` (usado por `ResponseAgent`, `PlannerAgent`, `QueryRefinerAgent`, `QueryValidatorAgent`) puede apuntar a un modelo local o cloud. **RAG vectorial (ChromaDB+OpenCLIP), GraphRAG (NetworkX), STT (Whisper) y TTS (Piper) siguen siendo 100% locales sin excepción** — no hay razón para mandarlos a la nube: son deterministas, rápidos, y no se benefician de un modelo más grande. El pivot de la tesis es específicamente sobre el paso de generación de texto (y las decisiones agénticas que también son generación de texto: Planner/Refiner/Validator).

## Por qué no hace falta tocar el código de red

Los modelos "-cloud" de Ollama Cloud se sirven a través del **mismo daemon local** (`ollama serve` en `localhost:11434`), tras autenticarse una vez con `ollama signin` — Ollama enruta la inferencia a su infraestructura cuando el modelo pedido es uno "-cloud", sin que el cliente HTTP note diferencia. Confirmado en pruebas reales: cambiar `config.LLM_MODEL` a `"gemma4:31b-cloud"` fue suficiente, sin tocar `OLLAMA_URL` ni ningún call site de `requests.post`. Los timeouts existentes (`OLLAMA_TIMEOUT=180s`, `PLANNER_TIMEOUT`/`REFINER_TIMEOUT`/`VALIDATOR_TIMEOUT=30s`) ya cubren la latencia extra de un roundtrip cloud.

## Detección: heurística de nombre, no lista mantenida a mano

`config.is_cloud_model(model) -> bool` retorna `model.endswith("-cloud")` — la convención de nombre que ya usa Ollama Cloud. Se prefirió esto sobre una lista explícita (`CLOUD_MODELS = {...}`) porque no requiere actualizarse cada vez que Ollama agregue un modelo cloud nuevo, y el proyecto ya no tiene forma de verificar esa lista contra la fuente real sin llamar a una API externa.

Usado para: el badge dinámico del header/footer de la UI (`ui/interface.py`, ya no dicen "100% Local" a secas — reflejan si `LLM_MODEL` activo es local o cloud), y el badge 🌐/💻 en la tab de Benchmark (ver ADR-0009).

## Sin selector de modelo en el chat de producción

El chat de producción (tab "Consulta Tributaria") sigue leyendo `config.LLM_MODEL`/variable de entorno, sin cambios — cambiar de modelo sigue siendo editar `config.py`. El selector interactivo de modelo (para comparar, no para uso diario) vive solo en la tab de Benchmark (ADR-0009) — agregar un selector en vivo habría requerido pasar `model=` a través de todo `CoordinatorAgent.process()`, superficie no pedida ni necesaria para el caso de uso real (elegir un modelo y quedarse con él, no cambiarlo pregunta a pregunta).
