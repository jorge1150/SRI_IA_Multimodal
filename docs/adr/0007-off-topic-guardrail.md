# Guardrail de dominio — pregunta_fuera_de_dominio + OffTopicMemory

Con el loop Refinador⇄Validador (ADR-0006) en producción, se detectó un problema en pruebas reales: una pregunta totalmente ajena al SRI (ej. "¿Qué clima hace hoy?") era reescrita por el `QueryRefinerAgent` — ayudado por los ejemplos de `RefinementMemory` — hasta que sonaba tributaria y el `QueryValidatorAgent` terminaba aprobándola. El sistema respondía como si la pregunta fuera legítima, en vez de reconocer que estaba completamente fuera de tema.

La causa: `rechazar_pregunta` (la única tool del Validador hasta ahora) solo comunica "no alcanza para responder", y esa señal es indistinguible entre "es tributaria pero está mal formulada" (el Refinador SÍ debe corregirla) y "no tiene nada que ver con tributación" (el Refinador NUNCA debe "arreglarla" para que suene tributaria).

## Segunda tool: `pregunta_fuera_de_dominio`

Se agrega una tool nueva al `QueryValidatorAgent`, junto a `rechazar_pregunta`:

- **`rechazar_pregunta(motivo)`**: la pregunta ES sobre normativa tributaria pero está mal formulada o no trajo contexto suficiente — el Refinador la reformula con el motivo como guía (comportamiento sin cambios, ADR-0006).
- **`pregunta_fuera_de_dominio()`**: la pregunta no tiene absolutamente nada que ver con el SRI — el `run_refinement_loop` corta el loop de inmediato (sin volver a llamar al Refinador) y `CoordinatorAgent.process()` salta Planner/RAG/Generación por completo, respondiendo con un mensaje fijo: *"Esta pregunta no tiene relación con la normativa tributaria del SRI Ecuador..."*

Mismo patrón de "presencia/ausencia de tool_call decide" que ya usan `PlannerAgent` y `rechazar_pregunta` — confiable con un modelo de 3B (ADR-0005).

## OffTopicMemory — fast-path para preguntas repetidas

Cada pregunta marcada `pregunta_fuera_de_dominio` se guarda en `outputs/off_topic_memory.json`. Antes de gastar una llamada a Ollama, se compara la consulta nueva contra las ya vistas — si hay un match, se corta directo con el mensaje fijo. Esto evita pagar el costo de una llamada LLM en preguntas repetidas obviamente fuera de tema.

## Por qué no se graba en RefinementMemory

`RefinementMemory` guarda pares (pregunta rechazada → corrección exitosa) para enseñarle al Refinador cómo corregir errores reales. Una pregunta fuera de dominio no tiene una "corrección" — no existe una versión tributaria de "¿qué clima hace hoy?". Mezclar estos casos en la misma memoria diluiría la señal útil del few-shot. Por eso `OffTopicMemory` es un almacén separado, con su propio propósito: reconocer repetidos, no enseñar correcciones.

## Corrección post-producción: el diseño original rompía el sistema entero

**Incidente real** (dos problemas encontrados corriendo el sistema con el guardrail activo):

1. **Match por similitud CLIP era inutilizable para este propósito.** La versión original de `OffTopicMemory` reusaba `SimilarityMemory` (embedding CLIP + coseno, igual que `RefinementMemory`) con `OFF_TOPIC_MEMORY_MIN_SIMILARITY = RAG_MIN_SIMILARITY` (0.18). Medido en producción: la similitud coseno de OpenCLIP entre preguntas cortas en español cae siempre en un rango angosto (~0.83–0.90), **sin importar si el tema es el mismo o no** — "¿qué clima hace hoy?" vs. "¿cuál es la tarifa del IVA?" dio 0.855; "¿qué clima hace hoy?" vs. "¿cómo está el clima?" (mismo tema, reformulado) dio 0.899. Con un umbral de 0.18, **una sola entrada en la memoria bastaba para marcar cualquier pregunta tributaria real como fuera de dominio** — el sistema dejó de responder cualquier consulta después de la primera detección. Fix: `OffTopicMemory` dejó de usar `SimilarityMemory`/embeddings por completo — ahora compara **texto normalizado** (sin tildes, minúsculas, sin puntuación) con `difflib.SequenceMatcher` y un umbral alto (`0.92`), pensado para detectar la MISMA pregunta repetida con variaciones triviales, no parafraseos. `RefinementMemory` no se toca — ahí un few-shot "no tan preciso" es inofensivo (en el peor caso, un ejemplo poco relevante), muy distinto a bloquear una pregunta entera.

2. **El chequeo corría DESPUÉS del Refinador, no antes.** El diseño original metía la tool `pregunta_fuera_de_dominio` solo dentro de `validate()`, que el loop llama recién después de que `QueryRefinerAgent.refine()` ya reescribió la pregunta — exactamente el orden que este ADR dice que hay que evitar ("el Refinador nunca debe arreglar una pregunta fuera de dominio"), porque para cuando el Validador la ve, ya pasó por el Refinador. Fix: `QueryValidatorAgent.check_off_topic(query)` — chequeo liviano (sin retrieval, solo la tool `pregunta_fuera_de_dominio`) que `run_refinement_loop` llama **antes** de la primera vuelta, sobre la pregunta ORIGINAL. Si es fuera de dominio, corta ahí — `refiner_agent.refine()` nunca se invoca. `validate()` conserva ambas tools dentro del loop como red de seguridad (por si una vuelta de refinamiento desviara el tema), pero el camino principal de detección es el chequeo previo.
