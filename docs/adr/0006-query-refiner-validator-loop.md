# QueryRefinerAgent + QueryValidatorAgent — loop de refinamiento agéntico con memoria in-context

`PlannerAgent` (ADR-0005) agrega un punto de decisión real antes del retrieval, pero la pregunta que recibe es la combinación literal de texto+STT+descripción visual/video, sin ningún control de calidad — si el usuario formula algo ambiguo, el Planner y el RAG heredan ese ruido. Esto ya estaba anotado como trabajo futuro en `docs/guia_exposicion.md` ("reformular la consulta y reintentar si el contexto recuperado no alcanza — loop tipo ReAct").

Se agregan dos agentes nuevos, insertados justo antes del `PlannerAgent`:

- **`QueryRefinerAgent`**: reescribe la pregunta (texto+STT+visual ya combinados) para que sea más clara y específica.
- **`QueryValidatorAgent`**: valida la pregunta refinada contra un retrieval de prueba real (`RAGAgent.retrieve`, vector_only) — no solo su forma lingüística — y decide vía tool-calling si alcanza para responder o si hay que refinar de nuevo.

Pipeline resultante:
```
[INICIO] → [STT] → [VISION] → [VIDEO] → [REFINADOR⇄VALIDADOR] → [PLANNER] → [RAG/NORMATIVA] → [GENERANDO] → [TTS] → [FIN]
```

## Por qué tool-calling con motivo, y no una decisión booleana simple

Mismo hallazgo empírico que ADR-0005 (modelo de 3B más confiable con presencia/ausencia de un `tool_call` que con un booleano dentro de la respuesta), extendido con un argumento `motivo: str` en la función `rechazar_pregunta(motivo)`: el motivo es lo que le permite al `QueryRefinerAgent` corregir el problema específico en la siguiente vuelta, en vez de generar variaciones ciegas de la misma pregunta.

## Por qué un tope de iteraciones, y no reintentar indefinidamente

Un modelo de 3B puede no converger nunca en una pregunta límite. `config.REFINEMENT_MAX_ITERATIONS` (default `2`, configurable vía variable de entorno) corta el loop y sigue con la última versión refinada — mismo criterio de "nunca bloquear al usuario" que ya usa `PlannerAgent` y `_init_graph_retriever` ante fallos de Ollama/grafo. No hay ninguna condición bajo la cual el pipeline se detiene esperando: al llegar al tope, se fuerza el paso.

## Por qué comparte flag con `USE_AGENTIC_PLANNER` en vez de uno propio

Los 3 agentes (Refiner, Validator, Planner) son el mismo tramo conceptual: "el LLM decide/mejora algo del pipeline en vez de seguir una regla fija". Separar flags habría permitido combinaciones sin sentido (ej. Validator activo sin Planner). Un solo flag mantiene la garantía existente: `USE_AGENTIC_PLANNER=False` reproduce exactamente el pipeline histórico, sin ninguna superficie nueva.

## Reuso del retrieval de prueba

El `QueryValidatorAgent` ya corre un retrieval vectorial real para juzgar la pregunta. Esos mismos chunks se reusan en `[RAG]` final (`agents/coordinator.py`) en vez de repetir la búsqueda — evita una llamada a ChromaDB/OpenCLIP redundante en el caso común. Si el `PlannerAgent` decide `"hybrid"`, se pide aparte solo el contexto de grafo (`HybridRetriever.retrieve(mode="graph_only")`, ya existente) y se combina con los chunks reusados.

## Memoria de aprendizaje in-context (few-shot), no fine-tuning

Cuando el loop tuvo al menos 1 rechazo antes de converger, se guarda una lección en `outputs/refinement_memory.json`: `{rejected_query, motivo, approved_query, vector}`. El vector se calcula con el mismo OpenCLIP que ya carga `RAGAgent` (sin nuevo modelo en memoria). En cada `refine()` posterior, se buscan los `REFINEMENT_MEMORY_TOP_K` ejemplos más parecidos por similitud coseno (umbral `REFINEMENT_MEMORY_MIN_SIMILARITY`, reusa el mismo criterio calibrado que `RAG_MIN_SIMILARITY`) y se inyectan como few-shot en el prompt del Refinador.

Se descartó fine-tuning/RLHF real de qwen2.5:3b: este proyecto es 100% de inferencia local (ver "Arquitectura 100% local" en `docs/arquitectura_tecnica.md`), sin GPU ni pipeline de entrenamiento — reentrenar pesos habría sido una pieza de infraestructura completamente nueva y fuera de alcance de la tesis. El few-shot vía memoria da una forma honesta de "el sistema mejora con el uso" sin esa infraestructura: es aprendizaje en el prompt, no en los pesos del modelo.

Solo se graban lecciones que tuvieron un rechazo real — si el Validador aprueba a la primera no hay corrección que enseñar, y grabar esos casos diluiría la señal útil del few-shot.

## Fallback

Ante cualquier falla de Ollama (`ConnectionError`, `Timeout`, excepción) en Refiner o Validator: se loguea `⚠` y se degrada sin bloquear el loop —
- `QueryRefinerAgent.refine()` degrada devolviendo la pregunta de entrada sin cambios.
- `QueryValidatorAgent.validate()` degrada a `approved=True` (aprobar por defecto es la opción segura: no reintenta indefinidamente y dan paso al resto del pipeline con lo que ya se tiene).

## Activación

`config.USE_AGENTIC_PLANNER` (default `False`, mismo flag que ADR-0005). `scripts/run_benchmark.py` en modo `"agentic"` corre el loop completo (Refiner→Validator→Planner) antes del retrieval, con columnas nuevas `refinement_seconds`/`refinement_iterations` en el CSV/HTML — y por lo tanto también alimenta `outputs/refinement_memory.json` con lecciones reales de esas corridas.
