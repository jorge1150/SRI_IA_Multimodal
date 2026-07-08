# SRI IA Multimodal

Asistente RAG multimodal 100% local para consultas sobre normativa tributaria del SRI Ecuador.

## Language

**Corpus de tesis**:
El conjunto final de 22 documentos PDF curados sobre los que se miden los resultados de la tesis (ingesta, GraphRAG, evaluación). Reemplaza por completo al corpus de 176 documentos usado durante el desarrollo inicial — ese corpus queda obsoleto, no convive con el corpus de tesis.
_Avoid_: "los documentos", "la base de datos actual" (ambiguo entre el corpus de desarrollo y el de tesis)

**PlannerAgent**:
Agente que decide, vía tool-calling nativo de Ollama, si una consulta necesita GraphRAG además del RAG vectorial (que siempre corre). Es el único punto del pipeline donde el LLM decide dinámicamente en vez de seguir una regla fija programada — el resto de agentes (STT, Visión, RAG, Respuesta, TTS) ejecutan una tarea determinística. Activado con `config.USE_AGENTIC_PLANNER` (default `False`). Ver ADR-0005.

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
