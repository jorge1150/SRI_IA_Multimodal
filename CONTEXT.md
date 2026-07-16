# SRI IA Multimodal

Asistente RAG multimodal 100% local para consultas sobre normativa tributaria del SRI Ecuador.

## Language

**Corpus de tesis**:
El conjunto final de 22 documentos PDF curados sobre los que se miden los resultados de la tesis (ingesta, GraphRAG, evaluación). Reemplaza por completo al corpus de 176 documentos usado durante el desarrollo inicial — ese corpus queda obsoleto, no convive con el corpus de tesis.
_Avoid_: "los documentos", "la base de datos actual" (ambiguo entre el corpus de desarrollo y el de tesis)

**PlannerAgent**:
Agente que decide, vía tool-calling nativo de Ollama, si una consulta necesita GraphRAG además del RAG vectorial (que siempre corre). Corre como el tercer paso de un tramo de 3 agentes agénticos (Refiner→Validator→Planner), todos activados con `config.USE_AGENTIC_PLANNER` (default `False`) — el resto de agentes (STT, Visión, RAG, Respuesta, TTS) ejecutan una tarea determinística. Ver ADR-0005.

**QueryRefinerAgent**:
Agente que reescribe la pregunta (texto+STT+descripción visual/video ya combinados) para que sea más clara y específica al consultar la base normativa SRI. Corre en loop con `QueryValidatorAgent` hasta `config.REFINEMENT_MAX_ITERATIONS` (default `2`) — al llegar al tope, se fuerza el paso con la última versión sin bloquear al usuario. Usa `RefinementMemory` para inyectar ejemplos de correcciones pasadas similares como few-shot (aprendizaje in-context, no reentrenamiento de pesos). Ver ADR-0006.

**QueryValidatorAgent**:
Agente que decide, vía tool-calling nativo de Ollama, si una pregunta refinada alcanza para responder correctamente — validando contra un retrieval de prueba real (`RAGAgent.retrieve`, vector_only), no solo la forma lingüística de la pregunta. Si rechaza, devuelve un motivo breve que el `QueryRefinerAgent` usa en la siguiente vuelta. Ver ADR-0006.
_Avoid_: confundir esta validación con RAGAS (`faithfulness`/`answer_relevancy`) — el Validador juzga si la pregunta+contexto alcanzan *antes* de generar la respuesta, RAGAS evalúa la respuesta ya generada.

**Memoria de refinamiento**:
Archivo `outputs/refinement_memory.json` — lista de `{rejected_query, motivo, approved_query, vector}` guardada por `RefinementMemory` cada vez que el loop Refinador⇄Validador tuvo al menos 1 rechazo antes de converger. El vector es el embedding OpenCLIP de la pregunta rechazada (mismo modelo que usa `RAGAgent`), usado para buscar por similitud coseno los ejemplos más parecidos a inyectar como few-shot. Ver ADR-0006.
_Avoid_: confundir con la base vectorial normativa (`CHROMA_DB_PATH`/ChromaDB) — son dos vector stores distintos con propósitos distintos (normativa tributaria vs. lecciones de refinamiento).

**Modo de recuperación**:
Estrategia que usa `HybridRetriever.retrieve(mode=...)` para una consulta: `vector_only` (solo RAG vectorial), `graph_only` (solo GraphRAG), `hybrid` (ambos), `agentic` (decide el PlannerAgent), `auto` (default de producción — comportamiento fijo histórico, intenta grafo si está disponible). Los primeros cuatro son comparables entre sí en `scripts/run_benchmark.py`.
_Avoid_: "modo automático" a secas para referirse a "agentic" — son modos distintos; "auto" es la regla fija del desarrollador, "agentic" es la decisión del LLM.

**Benchmark de tesis**:
`scripts/run_benchmark.py` — corre las preguntas de `preguntas.docx` contra los modos de recuperación y modelos LLM configurados, mide tiempo (retrieval/generación/planning) y calidad (RAGAS: faithfulness, answer relevancy, juez local vía Ollama). Resultado en `outputs/benchmarks/` (CSV + HTML + JSON de resumen), visible también en la tab "Benchmark RAGAS" de la UI.

**Side-channel**:
Patrón usado para que la UI lea datos estructurados de los agentes sin re-parsear texto de display: `LogAgent.get_events()` (eventos por etapa, alimenta el diagrama de flujo) y `ResponseAgent.last_answer`/`last_sources` (respuesta limpia + fuentes estructuradas, alimentan el bubble del chat, el panel de fragmentos, el corte para TTS y el benchmark). Los agentes publican el estado tras cada llamada; los consumidores lo leen en el mismo hilo después de cada yield del pipeline.
_Avoid_: parsear con regex el texto del log o del bloque de fuentes — esos formatos son display puro y pueden cambiar sin aviso.

**Etapa (Stage)**:
Vocabulario único de etapas del pipeline (`INICIO`, `STT`, `VISION`, `PLANNER`, `RAG`, `GRAPH`, `NORMATIVA`, `GENERANDO`, `RESPUESTA`, `TTS`, `FIN`, …), definido en la clase `Stage` de `agents/log_agent.py` — la fuente única de verdad. Todos los productores loguean con `Stage.X` (no literales); los consumidores máquina (íconos, diagrama de flujo de agentes) se cuelgan de las mismas constantes. El diagrama consume `LogAgent.get_events()` (eventos estructurados), nunca re-parsea el texto del log.
_Avoid_: literales de etapa en llamadas a `log()` — un typo degrada en silencio; con `Stage.X` falla visible.
