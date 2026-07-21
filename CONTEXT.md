# SRI IA Multimodal

Asistente RAG multimodal para consultas sobre normativa tributaria del SRI Ecuador. RAG vectorial, GraphRAG, STT y TTS son 100% locales; el LLM de generación es configurable (local o Ollama Cloud, ver ADR-0008) — ya no es una restricción dura de arquitectura.

## Language

**Corpus de tesis**:
El conjunto final de 22 documentos PDF curados sobre los que se miden los resultados de la tesis (ingesta, GraphRAG, evaluación). Reemplaza por completo al corpus de 176 documentos usado durante el desarrollo inicial — ese corpus queda obsoleto, no convive con el corpus de tesis.
_Avoid_: "los documentos", "la base de datos actual" (ambiguo entre el corpus de desarrollo y el de tesis)

**PlannerAgent**:
Agente que decide, vía tool-calling nativo de Ollama, si una consulta necesita GraphRAG además del RAG vectorial (que siempre corre). Corre como el tercer paso de un tramo de 3 agentes agénticos (Refiner→Validator→Planner), todos activados con `config.USE_AGENTIC_PLANNER` (default `False`) — el resto de agentes (STT, Visión, RAG, Respuesta, TTS) ejecutan una tarea determinística. Ver ADR-0005.

**QueryRefinerAgent**:
Agente que reescribe la pregunta (texto+STT+descripción visual/video ya combinados) para que sea más clara y específica al consultar la base normativa SRI. Corre en loop con `QueryValidatorAgent` hasta `config.REFINEMENT_MAX_ITERATIONS` (default `2`) — al llegar al tope, se fuerza el paso con la última versión sin bloquear al usuario. Usa `RefinementMemory` para inyectar ejemplos de correcciones pasadas similares como few-shot (aprendizaje in-context, no reentrenamiento de pesos). En la primera vuelta, también recibe el contexto conversacional (`previous_query`/`previous_answer`) para condensar preguntas de seguimiento ambiguas — ver "Contexto conversacional". Ver ADR-0006/ADR-0010.

**Contexto conversacional**:
El último intercambio (1 pregunta + 1 respuesta previas) de la conversación, extraído por `ui/interface.py::_extract_previous_exchange()` como texto plano y pasado a `CoordinatorAgent.process(previous_query=..., previous_answer=...)`. Resuelve follow-ups ambiguos (ej. "dime los pasos" tras "¿cómo obtengo el RUC?"). Con `USE_AGENTIC_PLANNER=True` se inyecta en `QueryRefinerAgent` (vía LLM, solo en la primera vuelta); sin el flag, un mecanismo liviano en `coordinator.py` concatena solo la pregunta anterior antes del RAG (sin LLM). Ver ADR-0010.
_Avoid_: confundir con `RefinementMemory`/`OffTopicMemory` — esas son memorias del sistema entre conversaciones distintas (aprendizaje de correcciones, preguntas fuera de dominio ya vistas), no el historial de la conversación en curso.

**QueryValidatorAgent**:
Agente que decide, vía tool-calling nativo de Ollama, si una pregunta refinada alcanza para responder correctamente — validando contra un retrieval de prueba real (`RAGAgent.retrieve`, vector_only), no solo la forma lingüística de la pregunta. Tiene DOS tools: `rechazar_pregunta` (pregunta SÍ tributaria pero mal formulada — vuelve al Refinador con el motivo) y `pregunta_fuera_de_dominio` (pregunta que no tiene nada que ver con el SRI — corta el pipeline entero con un mensaje fijo, ver "Guardrail de dominio"). Ver ADR-0006/ADR-0007.
_Avoid_: confundir esta validación con RAGAS (`faithfulness`/`answer_relevancy`) — el Validador juzga si la pregunta+contexto alcanzan *antes* de generar la respuesta, RAGAS evalúa la respuesta ya generada. No confundir "rechazar_pregunta" (pregunta corregible) con "pregunta_fuera_de_dominio" (pregunta que el Refinador NUNCA debe intentar arreglar).

**Guardrail de dominio**:
Mecanismo que evita que el `QueryRefinerAgent` reescriba una pregunta ajena al SRI (ej. "¿qué clima hace hoy?") hasta que suene tributaria. `run_refinement_loop` llama `QueryValidatorAgent.check_off_topic(query)` sobre la pregunta ORIGINAL **antes** de la primera vuelta (sin retrieval) — si es fuera de dominio, corta ahí, el Refinador nunca la toca. `validate()` conserva la misma tool dentro del loop como red de seguridad. `OffTopicMemory` hace match por texto normalizado (no embeddings — CLIP no discrimina preguntas cortas en español, ver ADR-0007). `check_off_topic()` también recibe el contexto conversacional (ver "Contexto conversacional") para no marcar como fuera de dominio un follow-up genérico sin palabras clave propias. Ver ADR-0007/ADR-0010.

**Memoria de refinamiento**:
Archivo `outputs/refinement_memory.json` — lista de `{rejected_query, motivo, approved_query, vector}` guardada por `RefinementMemory` cada vez que el loop Refinador⇄Validador tuvo al menos 1 rechazo antes de converger. El vector es el embedding OpenCLIP de la pregunta rechazada (mismo modelo que usa `RAGAgent`), usado para buscar por similitud coseno los ejemplos más parecidos a inyectar como few-shot. Ver ADR-0006.
_Avoid_: confundir con la base vectorial normativa (`CHROMA_DB_PATH`/ChromaDB) — son dos vector stores distintos con propósitos distintos (normativa tributaria vs. lecciones de refinamiento). Tampoco confundir con `outputs/off_topic_memory.json` (mismo mecanismo, `agents/off_topic_memory.py`, pero para preguntas fuera de dominio ya vistas — no hay "corrección" que guardar ahí, ver ADR-0007).

**Modelo cloud**:
Modelo de Ollama Cloud (ej. `gemma3:27b-cloud`) servido vía el mismo daemon local (`localhost:11434`, tras `ollama signin`) — no requiere cambios de red ni de código. Detectado con `config.is_cloud_model(model)` (heurística: sufijo `"-cloud"`). Solo aplica al LLM de texto (`LLM_MODEL`) — RAG/GraphRAG/STT/TTS siguen 100% locales siempre. Ver ADR-0008.
_Avoid_: asumir que el proyecto es "100% local" sin matiz — esa afirmación aplicaba a todo el sistema antes de ADR-0008; ahora es cierta para RAG/GraphRAG/STT/TTS, pero el LLM de generación es configurable.

**Modo de recuperación**:
Estrategia que usa `HybridRetriever.retrieve(mode=...)` para una consulta: `vector_only` (solo RAG vectorial), `graph_only` (solo GraphRAG), `hybrid` (ambos), `agentic` (decide el PlannerAgent), `auto` (default de producción — comportamiento fijo histórico, intenta grafo si está disponible). Los primeros cuatro son comparables entre sí en `scripts/run_benchmark.py`.
_Avoid_: "modo automático" a secas para referirse a "agentic" — son modos distintos; "auto" es la regla fija del desarrollador, "agentic" es la decisión del LLM.

**Benchmark de tesis**:
`scripts/run_benchmark.py` — corre las preguntas de `preguntas.docx` contra los modos de recuperación y modelos LLM configurados (locales o cloud, ver ADR-0008), mide tiempo (retrieval/generación/planning/refinamiento), tokens consumidos y calidad (RAGAS: faithfulness, answer relevancy, juez local vía Ollama). Resultado en `outputs/benchmarks/` (CSV + HTML + JSON de resumen), visible también en la tab "Benchmark RAGAS" de la UI, que incluye un selector de modelo y un ranking recomendado (`compute_model_ranking`, ver ADR-0009).

**Side-channel**:
Patrón usado para que la UI lea datos estructurados de los agentes sin re-parsear texto de display: `LogAgent.get_events()` (eventos por etapa, alimenta el diagrama de flujo) y `ResponseAgent.last_answer`/`last_sources` (respuesta limpia + fuentes estructuradas, alimentan el bubble del chat, el panel de fragmentos, el corte para TTS y el benchmark). Los agentes publican el estado tras cada llamada; los consumidores lo leen en el mismo hilo después de cada yield del pipeline.
_Avoid_: parsear con regex el texto del log o del bloque de fuentes — esos formatos son display puro y pueden cambiar sin aviso.

**Etapa (Stage)**:
Vocabulario único de etapas del pipeline (`INICIO`, `STT`, `VISION`, `PLANNER`, `RAG`, `GRAPH`, `NORMATIVA`, `GENERANDO`, `RESPUESTA`, `TTS`, `FIN`, …), definido en la clase `Stage` de `agents/log_agent.py` — la fuente única de verdad. Todos los productores loguean con `Stage.X` (no literales); los consumidores máquina (íconos, diagrama de flujo de agentes) se cuelgan de las mismas constantes. El diagrama consume `LogAgent.get_events()` (eventos estructurados), nunca re-parsea el texto del log.
_Avoid_: literales de etapa en llamadas a `log()` — un typo degrada en silencio; con `Stage.X` falla visible.
