# Contexto conversacional — follow-ups pierden el turno anterior

Reportado en uso real: el usuario preguntó "¿Cómo obtengo el RUC como persona natural?", recibió una respuesta, y luego escribió un follow-up sin restatement ("Dime los pasos que debo seguir"). El sistema perdió el hilo por completo — `QueryRefinerAgent` reescribió el follow-up como "¿Cuál es el procedimiento... para cumplir con las obligaciones tributarias ante el SRI...?" (genérico, sin RUC ni persona natural), y el RAG recuperó normativa no relacionada.

Causa raíz: no existía ningún historial de conversación en el backend. `ui/interface.py` mantiene un `gr.Chatbot` con `history`, pero solo se usaba para pintar bubbles — nunca llegaba a `CoordinatorAgent.process()`, y ninguno de los 4 agentes del pipeline (Refiner, Validator, Planner, Response) veía nunca más que la pregunta del turno actual. `RefinementMemory`/`OffTopicMemory` (ADR-0006/ADR-0007) son memorias del sistema entre conversaciones distintas — no tienen nada que ver con el historial de una conversación puntual.

## Alcance: solo el Refinador

El contexto conversacional se inyecta **solo** en el paso de condensación de la pregunta (Refinador con LLM, o un mecanismo liviano equivalente sin LLM) — Validador, Planner, RAG y Generación siguen viendo una única pregunta autocontenida, sin tocar esos prompts. Se descartó inyectarlo también en `ResponseAgent.generate()` (para que la respuesta pudiera referenciar el turno anterior explícitamente): el patrón "condensar antes de recuperar" es el estándar en RAG conversacional, y mantiene la generación desacoplada del historial — menos riesgo de que un modelo de 3B mezcle contexto viejo con normativa nueva al redactar.

## Funciona con y sin `USE_AGENTIC_PLANNER`

- **Con el flag** (camino agéntico): `QueryRefinerAgent.refine()` recibe `previous_query`/`previous_answer` y los usa vía LLM para reescribir el follow-up en una pregunta autocontenida.
- **Sin el flag** (default de producción hoy): no existe Refinador. Mecanismo liviano en `agents/coordinator.py::CoordinatorAgent.process()` — sin LLM, concatena texto plano: `rag_query = f"{previous_query} {rag_query}"`, **solo la pregunta anterior, no la respuesta**. La respuesta puede traer normativa larga que diluiría la señal del embedding CLIP (ya frágil para texto largo/disperso, medido en ADR-0007) — con el Refinador (LLM, no búsqueda por embeddings) sí se pasa la respuesta anterior también, porque ahí el riesgo no aplica y hay casos reales donde el follow-up depende de lo que se respondió, no de lo que se preguntó.

## Profundidad: solo el último intercambio

Se lleva únicamente 1 pregunta + 1 respuesta previas, no todo el historial acumulado. Cubre el caso real reportado sin inflar el prompt del Refinador (modelo de 3B) ni arrastrar temas de turnos lejanos que podrían confundir la reescritura. Limitación aceptada: si el usuario cambia de tema y vuelve dos turnos después, el sistema no reconecta ese hilo — no es un chatbot con memoria de sesión completa, es resolución del caso de uso principal (follow-up inmediato).

## Plumbing: la UI extrae texto plano antes de llamar al backend

`ui/interface.py::_extract_previous_exchange(history)` (nivel de módulo, sin closure — testeable igual que `_render_agent_flow_html`) toma el último intercambio de `gr.Chatbot` y lo reduce a 2 strings simples, filtrando partes multimedia (imágenes/video adjuntos vía `_text_only`). Los agentes del backend nunca ven el formato de mensajes de Gradio — mantiene la separación UI/backend ya existente en el proyecto. `CoordinatorAgent.process()` gana `previous_query`/`previous_answer` opcionales (default `None`); `scripts/run_benchmark.py` nunca los pasa (preguntas sueltas de `preguntas.docx`, sin concepto de conversación), sin romper el benchmark existente.

`run_refinement_loop` propaga el contexto de dos formas distintas:
- A `check_off_topic()`: **siempre**, en la única llamada previa al loop.
- A `refine()`: **solo en la primera vuelta** (`i == 0`) — una vez que el Refinador ya condensó la pregunta en una autocontenida, las vueltas siguientes (impulsadas por `rejection_reason`, no por el historial) ya trabajan sobre texto que no necesita más contexto conversacional.

## Interacción con el guardrail de dominio (ADR-0007)

`check_off_topic()` corre ANTES del Refinador, sobre la pregunta cruda — un follow-up genérico como "dime los pasos" no tiene palabras clave tributarias por sí solo, y sin contexto podría marcarse fuera de dominio, reintroduciendo el problema que ya se corrigió (el guardrail bloqueando preguntas válidas). Por eso `check_off_topic()` también recibe `previous_query`/`previous_answer` y los incluye en su propio prompt — el LLM juzga la pregunta en el contexto real de la conversación, no aislada.

**Limitación aceptada**: el fast-path de `OffTopicMemory` (texto normalizado, sin contexto — ver ADR-0007) podría en teoría cachear una frase genérica como fuera de dominio en una conversación, y bloquearla en otra donde sí tiene sentido con contexto distinto. Caso raro dado que `check_off_topic` ya ve el contexto antes de decidir marcarla; no se rediseñó `OffTopicMemory` para ser contexto-consciente — fuera de alcance de esta corrección.
