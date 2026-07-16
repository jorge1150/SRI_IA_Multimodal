# Guía de Exposición Académica — SRI IA Multimodal

**Asistente Virtual Basado en RAG Multimodal para Normativa Tributaria del SRI Ecuador**  
Maestría en Inteligencia Artificial Aplicada · UIsrael

---

## Estructura de la Presentación (20-30 minutos)

### 1. Introducción y Motivación (3-5 min)

**Problema que resuelve:**
- La normativa tributaria ecuatoriana es extensa, cambia frecuentemente y es difícil de consultar para contribuyentes y asesores.
- El SRI tiene leyes, reglamentos, resoluciones, guías y formularios dispersos en múltiples fuentes.
- Consultar un abogado tributario tiene un costo elevado para pequeños contribuyentes.

**Solución propuesta:**
- Asistente IA local que responde consultas sobre normativa tributaria citando la fuente exacta.
- No depende de internet en tiempo de ejecución (privacidad y disponibilidad offline).
- Multimodal: acepta texto, voz, imagen (formularios, portal SRI) y video.

---

### 2. Arquitectura del Sistema (5-7 min)

**Mostrar diagrama del pipeline:**

```
Consulta del usuario
       ↓
[Multimodal: Texto + Voz + Imagen + Video]
       ↓
[Refinador ⇄ Validador] (opcional) → reescribe la pregunta y la valida
       contra un retrieval de prueba real; rechazo → vuelve a refinar
       (máx. 2 vueltas) — aprende de correcciones pasadas (memoria in-context)
       ↓
[PlannerAgent] (opcional) → decide vía tool-calling si necesita GraphRAG
       ↓
[HybridRetriever]
  ├─ RAG Vectorial: OpenCLIP → ChromaDB → fragmentos con metadatos
  └─ GraphRAG: EntityExtractor + NetworkX → relaciones estructurales
       ↓
[Qwen2.5 vía Ollama] → Respuesta con citas
       ↓
[Piper TTS] → Audio en español ecuatoriano
```

**Puntos clave a destacar:**
- Todo funciona localmente (sin APIs de pago, sin internet obligatorio)
- ChromaDB almacena embeddings vectoriales de la normativa
- El grafo de conocimiento (GraphRAG) complementa con relaciones estructurales
  entre entidades tributarias (ej. contribuyente → debe_presentar → declaración)
- Los 3 agentes agénticos (Refinador → Validador → Planner) son los únicos
  puntos del pipeline donde el LLM **decide/mejora** dinámicamente (vía
  reescritura y tool-calling) en vez de seguir una regla fija — es lo que
  hace que el sistema califique como "software agéntico" en el sentido
  moderno, no solo "arquitectura multiagente clásica"
- El Refinador aprende de sus propias correcciones pasadas: cuando el
  Validador rechaza una pregunta, la lección (pregunta rechazada + motivo +
  corrección) queda guardada y se reusa como ejemplo en consultas futuras
  parecidas — aprendizaje in-context (few-shot vía similitud CLIP), no
  reentrenamiento de pesos (ver ADR-0006)
- Los metadatos permiten citar la fuente exacta: ley, artículo y página
- El prompt obliga al LLM a no inventar información no respaldada

---

### 3. Demostración en Vivo (8-10 min)

**Demo 1: Consulta por texto simple**
- Escribe: "¿Cuál es la tarifa actual del IVA en Ecuador?"
- Muestra: respuesta con cita del documento normativo real (ver panel de
  fragmentos recuperados — nombre del documento, artículo y página)
- Señala en los logs: RAG recupera fragmento del corpus de tesis (22 documentos)

**Demo 2: Consulta por voz**
- Habla: "¿Cuáles son los plazos para declarar el IVA?"
- Muestra: transcripción Whisper → respuesta → audio Piper TTS
- Señala en los logs: flujo STT → RAG → GENERANDO → TTS

**Demo 3: Análisis de imagen (formulario)**
- Captura la pantalla o sube imagen del Formulario 104
- Escribe: "¿Qué significa esta casilla?"
- Muestra: Moondream describe la imagen → RAG busca instructivo → respuesta contextual

**Demo 4: Consulta sin normativa disponible**
- Pregunta sobre un tema no cargado en la BD
- Muestra: el sistema dice "No encontré normativa específica sobre este tema"
- Enfatiza: el sistema NO inventa información

**Demo 5: Decisión agéntica en vivo (el aporte central de la tesis)**
- Antes de la demo: lanzar la app con `USE_AGENTIC_PLANNER=true python app.py`
- Abrir el botón **"🕸️ Ver Flujo de Agentes"** en la tab Consulta Tributaria
- Pregunta simple ("¿Qué es el RUC?"): mostrar cómo el nodo Planner se activa,
  decide "no necesita grafo", y el flujo pasa directo a RAG vectorial
- Pregunta relacional ("¿Qué relación existe entre el contribuyente y la
  obligación de retener el IVA?"): mostrar cómo el Planner decide "sí,
  necesita grafo" — el nodo con borde punteado marcado como "decisión"
- Enfatiza: son los pasos del pipeline donde el LLM decide dinámicamente,
  vía reescritura/tool-calling nativo de Ollama — no una regla `if/else`
  fija (ADR-0005, ADR-0006)

**Demo 5b: Refinamiento de la pregunta y memoria de aprendizaje (ADR-0006)**
- Con `USE_AGENTIC_PLANNER=true`, escribe una pregunta deliberadamente vaga
  (ej. "iva cuanto es") — mostrar en el panel de logs cómo el nodo Refinador
  la reescribe ("Original: «...» → Refinada: «...»") y cómo el Validador la
  aprueba o la rechaza con un motivo, volviendo al Refinador si hace falta
- Repite una pregunta vaga parecida a una ya corregida antes: señalar en el
  log del Refinador "(usando N ejemplo(s) de memoria)" — evidencia visible
  de que el sistema reusa correcciones pasadas, sin reentrenar el modelo
- Enfatiza: es la evolución directa del `PlannerAgent` — antes solo decidía
  la estrategia de retrieval, ahora primero se asegura de que la pregunta
  en sí esté bien formulada

**Demo 6: Benchmark comparativo (evidencia cuantitativa)**
- Mostrar la tab **"📊 Benchmark RAGAS"** con el resultado de una corrida
  previa (`python scripts/run_benchmark.py`)
- Señalar la comparación RAG vectorial vs GraphRAG vs Híbrido vs Agéntico:
  tiempo (retrieval/planning/generación) y calidad (RAGAS: faithfulness,
  answer relevancy) lado a lado
- Enfatiza: la decisión de activar o no el planner en producción está
  respaldada por datos medidos, no por intuición

---

### 4. Innovaciones Técnicas (3-4 min)

**PlannerAgent — decisión agéntica real (aporte central de la tesis):**
- Único componente del pipeline donde el LLM decide dinámicamente vía
  tool-calling nativo de Ollama, en vez de una regla `if/else` fija.
- Decide si una consulta necesita GraphRAG además del RAG vectorial (que
  siempre corre) — decisión binaria, no elección exclusiva entre herramientas
  (ver limitación de modelos de 3B abajo).
- Visible en vivo en la UI: diagrama animado de flujo de agentes que marca
  el nodo del Planner como el único punto de decisión real, distinto de los
  demás pasos (fijos, sin negociación entre agentes).
- Validado empíricamente con benchmark propio (RAGAS + tiempos) antes de
  activarlo por defecto — decisión respaldada por datos, no por intuición.

**QueryRefinerAgent + QueryValidatorAgent — refinamiento agéntico con memoria in-context (evolución del Planner):**
- Antes de decidir la estrategia de retrieval, el sistema se asegura de que
  la pregunta en sí esté bien formulada: el Refinador la reescribe, el
  Validador la valida contra un retrieval de prueba real (no solo su forma
  lingüística) y decide vía tool-calling si alcanza o si hay que refinar de
  nuevo — con el motivo del rechazo pasando al Refinador para la siguiente
  vuelta.
- Tope de iteraciones (`REFINEMENT_MAX_ITERATIONS`, default 2) garantiza que
  nunca bloquea al usuario, aun si el modelo de 3B no converge.
- **Memoria de aprendizaje in-context**: cada corrección real (rechazo→
  aprobación) queda guardada con su embedding CLIP; consultas futuras
  parecidas reciben esos ejemplos como few-shot en el prompt del Refinador
  — el sistema mejora con el uso, sin reentrenar los pesos del modelo (no
  hay pipeline de fine-tuning en este proyecto 100% de inferencia local).
- Resuelve directamente el trabajo futuro anotado en la versión anterior de
  esta guía ("loop tipo ReAct" para reformular la consulta si el contexto
  no alcanza) — ver ADR-0006.

**GraphRAG — grafo de conocimiento tributario:**
- Complementa el RAG vectorial con relaciones **estructurales** entre
  entidades tributarias (ej. `contribuyente → debe_presentar → declaración
  de IVA`), extraídas automáticamente por reglas léxico-verbales, sin NLP
  entrenado externo.
- Persistido en NetworkX + JSON, 100% local — sin depender de un motor de
  grafos externo (Neo4j es opcional, no requerido).

**Metadatos ricos en el RAG:**
- A diferencia de sistemas genéricos, cada fragmento tiene: nombre del documento, tipo de normativa, año, artículo/sección y número de página.
- Esto permite citas precisas: "Según la Ley de Régimen Tributario Interno, Art. 65, Pág. 23..."

**Keyword Reranking tributario:**
- Después de la búsqueda vectorial, se aplica un re-ranking por palabras clave del dominio.
- Compensa las limitaciones de CLIP (modelo de visión) para texto legal especializado.

**Soporte multiformat:**
- El sistema procesa PDFs (con número de página), DOCX, TXT y MD.
- MinerU extrae layout, tablas y aplica OCR para una cita precisa; reconoce
  jerarquía de encabezados (ningún fragmento cruza dos artículos distintos) y
  preserva tablas de tarifas intactas; PyMuPDF queda como fallback automático
  si MinerU falla en un documento puntual.

**Evaluación con RAGAS (juez y embeddings 100% locales):**
- `scripts/run_benchmark.py` compara RAG vectorial, GraphRAG, Híbrido y
  Agéntico por tiempo y calidad (faithfulness, answer relevancy) usando el
  mismo Ollama del proyecto como juez — sin depender de OpenAI/GPT-4.
- Limitación documentada, no oculta: un juez de 3B falla con más frecuencia
  que GPT-4 en producir una evaluación parseable — el reporte lo hace
  explícito mostrando "(N/total)" evaluado, en vez de promediar en silencio.

**Prompt con restricciones legales:**
- El prompt del sistema prohíbe explícitamente inventar artículos, porcentajes o plazos.
- Obliga a decir cuándo no hay información suficiente.
- Incluye disclaimer de asesoría no vinculante.

---

### 5. Comparación con el Proyecto Base (2-3 min)

**S3 IA Multimodal (soporte técnico PC) → SRI IA Multimodal (normativa tributaria):**

| Aspecto | S3 IA (base) | SRI IA (nuevo) |
|---|---|---|
| Dominio | Fallas de computadora | Leyes y normativas tributarias |
| Documentos | TXT manuales simples | PDF/DOCX legales con paginación (MinerU) |
| Metadatos | source, id | + tipo, año, artículo, página |
| Recuperación | RAG vectorial | RAG vectorial + GraphRAG + decisión agéntica |
| Decisión agéntica | No | Sí — Refiner→Validator→Planner vía reescritura + tool-calling (ADR-0005, ADR-0006) |
| Aprendizaje del sistema | No | Memoria in-context de correcciones pasadas (few-shot vía similitud CLIP, sin fine-tuning) |
| Evaluación | Manual | RAGAS + benchmark comparable por modo/modelo |
| Citas de fuente | No | Sí (obligatorio por prompt) |
| Disclaimer | No | Sí (ético y legal) |
| Carpetas | 1 carpeta manuals/ | Categorías normativas dinámicas (subcarpetas de `data/`) |

---

### 6. Conclusiones y Trabajo Futuro (2-3 min)

**Logros:**
- Sistema RAG multimodal funcional y 100% local.
- Respuestas que citan la fuente exacta de la normativa.
- GraphRAG — grafo de conocimiento tributario complementando el RAG vectorial.
- **Decisión agéntica real** (`PlannerAgent`, ADR-0005) — el LLM decide
  dinámicamente la estrategia de retrieval vía tool-calling, no una regla fija.
- **Refinamiento agéntico de la consulta con memoria in-context**
  (`QueryRefinerAgent` + `QueryValidatorAgent`, ADR-0006) — antes de decidir
  la estrategia de retrieval, el sistema mejora la pregunta del usuario y
  valida que alcance contra un retrieval de prueba real, aprendiendo de
  correcciones pasadas sin reentrenar el modelo.
- Benchmark propio con RAGAS (juez y embeddings 100% locales) que compara
  RAG vectorial, GraphRAG, Híbrido y Agéntico por tiempo y calidad.
- Soporte para PDF (MinerU: layout, tablas, OCR), DOCX, TXT y MD del SRI.
- Interfaz profesional con logs de trazabilidad y diagrama animado del flujo
  de agentes en vivo (alimentado por eventos estructurados, no por parseo
  de texto); las tabs de estadísticas se refrescan al entrar, sin reiniciar.
- Calidad de ingeniería verificable: suite de 111 tests en verde, decisiones
  de arquitectura registradas en ADRs, y dos revisiones de arquitectura
  documentadas que eliminaron contratos frágiles (datos estructurados entre
  módulos en vez de texto re-parseado con regex).

**Limitaciones actuales:**
- Qwen2.5 (3B) tiene capacidad de razonamiento limitada frente a modelos más grandes (pueden cometerse errores en lógica compleja); reemplazó a TinyLlama tras detectarse alucinaciones (ver ADR-0003).
- El `PlannerAgent` tiene sesgo medido hacia "no usar grafo" incluso en preguntas donde ayudaría — limitación de modelos de 3B en decisiones de tool-calling, documentada empíricamente (ADR-0005), por eso queda detrás de un flag hasta validarse más.
- El loop Refinador⇄Validador puede no converger con un modelo de 3B en preguntas límite — el tope de iteraciones lo mitiga (fuerza el paso, nunca bloquea), pero no garantiza que la pregunta final sea perfecta (ADR-0006).
- La memoria de aprendizaje in-context solo ayuda si aparecen preguntas similares a las ya corregidas — no generaliza como lo haría un fine-tuning real; es una mejora incremental basada en el uso, no una solución completa a preguntas ambiguas nuevas.
- El juez local de RAGAS (mismo modelo de 3B) falla con más frecuencia que GPT-4 en producir una evaluación parseable — el benchmark lo reporta explícito en vez de ocultarlo.
- OpenCLIP es un modelo de visión, no optimizado para texto legal — el reranking compensa esto.
- La calidad de las respuestas depende de qué documentos se hayan cargado.

**Mejoras propuestas:**
- Usar un LLM más capaz (Llama 3, Mistral) cuando el hardware lo permita — comparable directo vía `scripts/run_benchmark.py --models`.
- ~~Extender el `PlannerAgent` a más decisiones (ej. reformular la consulta y reintentar si el contexto recuperado no alcanza — loop tipo ReAct)~~ — implementado (`QueryRefinerAgent`/`QueryValidatorAgent`, ADR-0006). Próximo paso natural: dar tope de tamaño o resumen a `refinement_memory.json` si crece mucho con el uso, y medir en el benchmark si la memoria mejora la tasa de aprobación en la 1ra vuelta a lo largo del tiempo.
- Implementar un embedder de texto especializado en español legal para el RAG vectorial (e.g., multilingual-e5) — hoy solo el benchmark usa un embedder de texto dedicado (`sentence-transformers`, para RAGAS), el RAG de producción sigue con OpenCLIP.
- Agregar actualización automática de normativa desde sri.gob.ec.
- Interfaz de administración para cargar nuevos documentos desde la UI.

---

## Preguntas Frecuentes del Jurado

**¿Por qué usar RAG en lugar de fine-tuning?**
La normativa tributaria cambia frecuentemente (nuevas resoluciones, cambios en tarifas). El RAG permite actualizar el conocimiento cargando nuevos documentos sin reentrenar el modelo. El fine-tuning requiere datos etiquetados y tiempo de entrenamiento para cada actualización.

**¿Cómo garantiza que no invente normativa?**
El prompt del sistema tiene restricciones explícitas: el LLM DEBE basarse solo en el contexto RAG recuperado. Si no hay normativa en el contexto, el sistema está programado para decirlo claramente y recomendar consultar sri.gob.ec.

**¿Por qué OpenCLIP y no un embedder de texto?**
El proyecto reutiliza la arquitectura del S3 IA Multimodal que usa OpenCLIP para compatibilidad multimodal (texto + imagen). El keyword reranking compensa sus limitaciones en texto especializado. El benchmark de tesis (`scripts/run_benchmark.py`) ya incorpora un embedder de texto dedicado (`sentence-transformers`) — pero solo para el juez RAGAS, no para el RAG de producción, precisamente porque CLIP no está optimizado para comparar dos textos entre sí (ver ADR-0004). Migrar el RAG de producción a un embedder de texto sigue siendo una mejora futura.

**¿Qué pasa si la normativa del SRI cambia?**
El sistema es agnóstico al contenido: simplemente se cargan los nuevos documentos en una subcarpeta de `data/` (categorías dinámicas, sin editar código) y se ejecuta `python rag/build_db.py --reset`. En minutos la base vectorial está actualizada con la nueva normativa.

**¿Funciona con documentos en otro idioma?**
El sistema está configurado para español (Whisper con idioma español). Los documentos en inglés o quechua no tendrían respuestas óptimas, pero el sistema no falla — simplemente tendrá menor precisión.

**¿En qué sentido es "software agéntico"?**
La arquitectura multiagente (Coordinador orquestando agentes especializados) por sí sola es una arquitectura multiagente **clásica** — módulos con responsabilidad única, sin autonomía. Lo que hace al sistema agéntico en el sentido moderno es el tramo Refinador→Validador→Planner (ADR-0005, ADR-0006): antes de generar la respuesta, el LLM mejora la pregunta, valida si alcanza contra un retrieval real, y decide vía tool-calling si la consulta necesita GraphRAG — en vez de que el desarrollador lo decida con reglas fijas. Es autonomía real, medible y visible (diagrama de flujo en vivo, con 2 nodos marcados como decisión), no solo terminología.

**¿Por qué el Refinador/Validador/Planner están desactivados por defecto (`USE_AGENTIC_PLANNER=False`)?**
Porque su confiabilidad se midió antes de recomendarlos, no se asumió. Pruebas con `scripts/run_benchmark.py` mostraron que un modelo de 3B tiene sesgo hacia "no usar grafo" en algunas preguntas donde ayudaría, y el mismo modelo puede no converger en preguntas límite dentro del loop de refinamiento. Activarlos por defecto sin ese dato habría sido reemplazar reglas fijas conocidas por decisiones de fiabilidad desconocida — el flag único permite decidir con evidencia, mismo criterio que otras decisiones del proyecto (`USE_MINERU_PDF`, `GRAPH_ENABLED`).

**¿La memoria de aprendizaje del Refinador es fine-tuning o RLHF?**
No. `RefinementMemory` guarda ejemplos de correcciones pasadas (pregunta rechazada + motivo + versión corregida) y los inyecta como few-shot en el prompt cuando aparece una pregunta similar (similitud coseno sobre embeddings CLIP) — el modelo "aprende" vía contexto acumulado entre consultas, no reentrenando sus pesos. Se descartó fine-tuning/RLHF real deliberadamente: el proyecto es 100% de inferencia local, sin GPU de entrenamiento ni pipeline de fine-tuning — agregar uno habría sido infraestructura nueva, fuera del alcance de la tesis (ver ADR-0006).

**¿Cómo se valida que el sistema responde bien, más allá de verlo funcionar?**
Con RAGAS: métricas de *faithfulness* (¿la respuesta está basada en el contexto recuperado, o el LLM inventó algo?) y *answer relevancy* (¿contesta la pregunta hecha?), calculadas por un juez LLM — en este caso el mismo Ollama local, sin depender de GPT-4/OpenAI, manteniendo el principio 100% local del proyecto. El benchmark compara estas métricas entre RAG vectorial, GraphRAG, Híbrido y Agéntico, con los mismos datos y el mismo juez para que la comparación sea justa.

---

## Comandos Clave para la Demo

```bash
# Iniciar Ollama (en terminal separada)
ollama serve

# Verificar que los modelos estén disponibles
ollama list

# Construir/actualizar base vectorial
python rag/build_db.py

# Lanzar el asistente (modo normal — planner desactivado)
source venv/bin/activate
python app.py
# → Abrir http://localhost:7865

# Lanzar con el PlannerAgent activo (para Demo 5 — decisión agéntica)
USE_AGENTIC_PLANNER=true python app.py

# Generar/actualizar el reporte de benchmark antes de la exposición (Demo 6)
python scripts/run_benchmark.py --limit 5        # prueba rápida
python scripts/run_benchmark.py                  # corrida completa (tarda horas en CPU)
```
