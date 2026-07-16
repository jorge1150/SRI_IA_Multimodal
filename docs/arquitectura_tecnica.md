# Arquitectura Técnica — SRI IA Multimodal
## Asistente de Normativa Tributaria Ecuador con RAG Híbrido

---

## 1. Descripción General

Sistema de asistencia tributaria local que responde preguntas sobre normativa del **Servicio de Rentas Internas (SRI) Ecuador** sin depender de servicios en la nube ni APIs externas. Toda la inferencia y recuperación de información ocurre en la máquina del usuario.

**Principio central:** toda respuesta se basa primero en documentos normativos recuperados por el sistema RAG; el LLM no inventa normativa.

---

## 2. Stack Tecnológico

| Capa | Tecnología | Versión / Detalle |
|------|-----------|-------------------|
| Interfaz de usuario | **Gradio** | v6.x — dark theme, CSS injection via `gr.HTML` |
| Modelo de lenguaje | **Qwen2.5** via **Ollama** | 3B params, `qwen2.5:3b-instruct-q4_K_M`, temperature 0.1 (ver ADR-0003) |
| Visión computacional | **Moondream** via **Ollama** | `moondream` — formularios y pantallas SRI |
| Embeddings | **OpenCLIP ViT-B-32** | `hf-hub:timm/vit_base_patch32_clip_224.openai`, dim=512 |
| Base vectorial | **ChromaDB** | Persistente en `vector_db/chroma_sri/`, colección `normativa_tributaria` |
| Grafo de conocimiento | **NetworkX DiGraph** | Persistido en JSON `graph_db/sri_graph.json` |
| STT (voz → texto) | **faster-whisper** | Modelo `base`, idioma `es`, beam_size=5 |
| TTS (texto → voz) | **Piper TTS** | Modelo `es_ES-sharvard-medium.onnx`, 22050 Hz |
| Extracción de texto PDF | **MinerU** (layout, tablas, OCR), fallback **PyMuPDF (fitz)** | MinerU por defecto (ver ADR-0001); PyMuPDF automático si MinerU falla o hace timeout |
| Extracción DOCX | **python-docx** | Párrafos concatenados |
| Cómputo | **PyTorch** | CPU (macOS Intel) — CLIP en float32 |
| Audio | **sounddevice + scipy** | Grabación a 48kHz, resample a 16kHz para Whisper |
| Decisión agéntica | **Ollama tool-calling** | `PlannerAgent` sí/no GraphRAG (ADR-0005) + `QueryRefinerAgent`/`QueryValidatorAgent` loop de refinamiento con memoria in-context (ADR-0006) |
| Evaluación (RAGAS) | **ragas 0.2.15** + **sentence-transformers 2.7.0** | Juez local vía Ollama, embeddings `paraphrase-multilingual-MiniLM-L12-v2` — versiones fijadas por compatibilidad con `torch==2.2.2` |

---

## 3. Estructura del Proyecto

```
SRI_IA_Multimodal/
├── app.py                      # Punto de entrada — instancia CoordinatorAgent + Gradio
├── config.py                   # Configuración central (todos los parámetros)
├── agents/
│   ├── coordinator.py          # Orquestador — pipeline completo + build_retrieval_pipeline()
│   │                            #   (wiring compartido con el benchmark: un solo lugar
│   │                            #   donde se construye RAG+Planner+Graph+Hybrid)
│   ├── planner_agent.py        # Decisión agéntica sí/no GraphRAG vía tool-calling (ADR-0005)
│   ├── query_refiner_agent.py  # Reescribe la pregunta con few-shot de RefinementMemory (ADR-0006)
│   ├── query_validator_agent.py # Valida la pregunta refinada contra retrieval de prueba (ADR-0006)
│   ├── refinement_memory.py    # Memoria in-context (JSON + similitud CLIP) de correcciones pasadas
│   ├── rag_agent.py            # Recuperación vectorial con OpenCLIP + ChromaDB
│   ├── response_agent.py       # Generación LLM + fuentes estructuradas (side-channel
│   │                            #   last_answer/last_sources; model= override)
│   ├── vision_agent.py         # Análisis de imágenes con Moondream ("" en error, sin sentinelas)
│   ├── video_agent.py          # Extracción de frames de video
│   ├── voice_agent.py          # STT con faster-whisper
│   ├── tts_agent.py            # TTS con Piper (3 backends en cascada)
│   └── log_agent.py            # Vocabulario de etapas (clase Stage, fuente única) +
│                                #   log de texto para humanos + eventos estructurados
│                                #   (get_events()) para el diagrama de flujo de agentes
├── graph/
│   ├── entity_extractor.py     # Taxonomía de 37 entidades tributarias
│   ├── relation_extractor.py   # Extracción de relaciones por patrones léxicos
│   ├── graph_builder.py        # Constructor del grafo desde chunks RAG (esquema plano)
│   ├── graph_store.py          # Almacenamiento NetworkX + persistencia JSON + build_seconds
│   └── graph_retriever.py      # Recuperación por sub-grafo para una consulta
├── rag/
│   ├── chunker.py              # Fragmentación PDF/DOCX/TXT/MD — MinerU-aware (kind, graph_text)
│   ├── ingesta.py              # Ingesta masiva a ChromaDB con embeddings CLIP + build_metadata.json
│   └── build_db.py             # Script de construcción/reconstrucción de la BD
├── services/
│   ├── hybrid_retriever.py     # Combina RAG vectorial + GraphRAG (mode=vector_only|graph_only|hybrid|auto)
│   └── benchmark_format.py     # Formateo compartido de métricas ("—", "(N/total)") —
│                                #   una sola convención para el HTML del script y la tab de la UI
├── scripts/
│   ├── build_graph.py          # Script de construcción del grafo de conocimiento
│   ├── run_benchmark.py        # Benchmark de tesis — modos × modelos × RAGAS
│   ├── ragas_local.py          # Juez RAGAS local (Ollama) + embeddings locales
│   └── benchmark_dataset.py    # Parser de preguntas.docx
├── data/
│   └── <categoría>/            # Subcarpetas dinámicas — el nombre es el tipo_normativa
├── preguntas.docx               # Dataset de evaluación (42 preguntas, 22 documentos)
├── vector_db/chroma_sri/       # Base vectorial persistida (ChromaDB)
├── vector_db/build_metadata.json # Tiempo acumulado de construcción del vector store
├── graph_db/sri_graph.json     # Grafo de conocimiento (NetworkX serializado)
├── outputs/benchmarks/         # Reportes de scripts/run_benchmark.py
├── ui/
│   ├── interface.py            # Componentes Gradio, lógica de la UI, diagrama de flujo de agentes
│   └── styles.py               # CSS del tema institucional
└── audio/piper_models/         # Modelo ONNX de Piper TTS
```

---

## 4. Pipeline de Consulta (flujo principal)

Cada consulta ejecuta este pipeline secuencial. El `CoordinatorAgent` emite actualizaciones parciales (`yield`) en tiempo real para mostrar el progreso en la UI:

```
[ENTRADA]
    │
    ├─ Texto escrito         ─┐
    ├─ Audio (micrófono)     ─┤→ [STT] faster-whisper → texto transcrito
    ├─ Imagen (formulario)   ─┤→ [VISION] Moondream → descripción breve
    └─ Video (pantalla)      ─┘→ [VIDEO] extracción de frames → Moondream
                                      │
                              Consulta combinada
                                      │
              [REFINADOR ⇄ VALIDADOR] (si USE_AGENTIC_PLANNER=True)
              QueryRefinerAgent reescribe la pregunta (+ few-shot de
              RefinementMemory) → QueryValidatorAgent la valida contra
              un retrieval de prueba real. Si rechaza, vuelve al
              Refinador con el motivo — hasta REFINEMENT_MAX_ITERATIONS
              (default 2), luego se fuerza el paso. (ADR-0006)
                                      │
                    [PLANNER] (si USE_AGENTIC_PLANNER=True)
                    PlannerAgent decide vía tool-calling de Ollama:
                    ¿esta consulta necesita GraphRAG? (ADR-0005)
                    Los 3 agentes (Refiner/Validator/Planner) son los
                    únicos pasos del pipeline con decisión real del LLM —
                    el resto son pasos fijos, no negociación entre agentes.
                                      │
                        [RAG HÍBRIDO — HybridRetriever]
                         /                           \
              [RAG Vectorial]                  [GraphRAG]
              OpenCLIP → ChromaDB           EntityExtractor
              similitud coseno             + RelationExtractor
              top-K=4 fragmentos          → sub-grafo NetworkX
              + keyword re-ranking        → triples en texto
                         \                           /
                          contexto normativo unificado
                                      │
                          [LLM — Qwen2.5 via Ollama]
                          system prompt mínimo
                          seed "Respuesta:" forzado
                          stop sequences configuradas
                          temperature=0.1, max_tokens=400
                                      │
                              respuesta en español
                                      │
                    [FUENTES] — construidas en Python (no LLM)
                    deduplicación por doc_name
                                      │
                        [TTS — Piper es_ES-sharvard]
                        solo el texto de la respuesta
                        (sin bloque de fuentes)
                                      │
                            [SALIDA] texto + audio + fragmentos
```

---

## 5. Construcción de la Base de Conocimiento

### 5a. Ingesta y Base Vectorial (ChromaDB)

**Script:** `python rag/build_db.py --reset`

**Proceso de ingesta por documento:**

1. **Extracción de texto:**
   - PDF → MinerU (layout, tablas HTML, OCR) por defecto (ADR-0001); si falla o hace timeout, fallback automático a PyMuPDF (`fitz`) página por página. Conserva el número de página en ambos casos.
   - DOCX → python-docx, concatenación de párrafos.
   - TXT / MD → lectura directa UTF-8.

2. **Fragmentación (`chunker.py`):**
   - Tamaño de chunk: **500 caracteres**, overlap de **60 caracteres**.
   - Corte preferente en punto final (`. `) si está en la segunda mitad del chunk.
   - Corte secundario en espacio (` `) garantizando avance real (> overlap).
   - Protección contra loop infinito: `start = new_start if new_start > start else end`.

3. **Metadatos por chunk (esquema unificado, un solo constructor `make_chunk` para los 5 formatos):**
   `id`, `text`, `kind` (`paragraph`/`table`/`equation`, MinerU-aware), `graph_text` (caption+footnote sin HTML/LaTeX, usado por el embedding CLIP y por el knowledge graph — ver ADR-0004), `doc_name`, `tipo_normativa`, `año`, `pagina`, `articulo_seccion`, `source`, `ruta_archivo`.
   Con MinerU, cada heading abre una nueva sección: ningún chunk de prosa cruza dos artículos distintos, y `articulo_seccion` se recalcula contra el texto del heading (no contra prosa aplanada). Un cambio de página corta igual, aunque la sección siga — `pagina` siempre es exacta.

4. **Vectorización:**
   - OpenCLIP ViT-B-32 (512 dimensiones).
   - Normalización L2: `vec /= vec.norm(dim=-1, keepdim=True)`.
   - Cómputo en CPU (float32), ~50–200 ms por chunk.
   - Para chunks `table`/`equation`: se embebe `graph_text` (caption+footnote), no el HTML/LaTeX crudo de `text` — evita que el vector solo capture las primeras etiquetas (ADR-0004).

5. **Almacenamiento:** ChromaDB con espacio coseno (`hnsw:space = cosine`).

**Estado actual (corpus de tesis, ADR-0002):** 10.944 fragmentos de 22 documentos curados.

**Tiempos de construcción (macOS Intel, sin GPU):**
| Operación | Tiempo aprox. |
|-----------|--------------|
| Extracción PDF con MinerU (por documento) | segundos a varios minutos — layout/OCR en CPU; cae a PyMuPDF si supera `MINERU_TIMEOUT` (600s) |
| Embedding CLIP (por chunk) | 50–200 ms |
| Ingesta completa 22 docs (MinerU) | del orden de horas — dominado por MinerU, no por CLIP |
| Reconexión a BD ya existente | < 1 s |

El tiempo real acumulado de la última construcción se ve en vivo en la tab
"Base de Conocimiento" de la UI (`vector_db/build_metadata.json`, acumula
desde el último `--reset` — incluye corridas interrumpidas y retomadas).

### 5b. Grafo de Conocimiento (GraphRAG)

**Script:** `python scripts/build_graph.py --reset`

**Proceso de construcción del grafo:**

1. **Fuente de datos:** Los mismos chunks ya fragmentados para ChromaDB.

2. **Extracción de entidades (`entity_extractor.py`):**
   - Taxonomía de **37 entidades** tributarias ecuatorianas (sin spaCy ni NLP externo).
   - Entidades: IVA, impuesto a la renta, ICE, RISE, retención, RUC, LORTI, Código Tributario, contribuyente, persona natural/jurídica, declaración, formulario 104/101/103, deducción, crédito tributario, multa, mora, entre otras.
   - Matching por regex sobre texto normalizado (sin tildes, minúsculas).
   - Desambiguación de solapamientos: conserva el match más largo.

3. **Extracción de relaciones (`relation_extractor.py`):**
   - Patrones léxico-verbales sobre oraciones (`_SENT_SPLIT`, solo aplica a chunks `kind="paragraph"` — chunks `table`/`equation` usan `graph_text`, nunca el HTML/LaTeX crudo, para no romper el splitter).
   - **8 tipos de relación observados en el corpus de tesis:** `relacionado_con`, `establece`, `aplica_tarifa`, `debe_presentar`, `esta_exento`, `puede_deducir`, `debe_retener`, `puede_acogerse`. (El extractor reconoce patrones para más tipos — `debe_inscribirse`, `declara_en`, `tiene_plazo`, etc. — pero no todos aparecen necesariamente en un corpus dado; depende de qué patrones verbales contiene el texto real.)
   - Cada relación emite un **triple** `(fuente, relación, destino)` con evidencia textual y nombre del documento (identificado correctamente desde el esquema plano de chunk — ver nota de esquema unificado abajo).

4. **Almacenamiento NetworkX:**
   - `nx.DiGraph` — nodos son entidades, aristas son relaciones.
   - Persistido en JSON (`graph_db/sri_graph.json`), incluye `metadata.build_seconds` (acumulado desde el último `--reset`).
   - Soporte opcional Neo4j (no requerido — sistema funciona 100% local).

**Estado actual (corpus de tesis, 22 documentos):** 37 entidades (nodos), 542 relaciones únicas (aristas), 996 triples nuevos, 10.743 chunks procesados.

**Tiempos de construcción:**
| Operación | Tiempo aprox. |
|-----------|--------------|
| Construcción grafo completo (corpus de tesis, MinerU) | del orden de horas — MinerU vuelve a parsear cada PDF (el grafo no comparte el chunking con la ingesta vectorial) |
| Carga del grafo JSON al iniciar app | < 0.5 s |

> **Nota de esquema (candidata de arquitectura resuelta):** `GraphBuilder.build_from_chunks`
> antes esperaba un dict anidado (`{"metadata": {...}}`) que ningún llamador real
> producía — `doc_name` caía siempre a `"chunk_N"` en el grafo. Se corrigió para
> leer el dict plano que sí produce `rag/chunker.py`; la trazabilidad
> documento→triple ahora es correcta.

---

## 6. Recuperación en Tiempo de Consulta

### 6a. RAG Vectorial

**Clase:** `RAGAgent.retrieve(query, top_k=4)`

1. **Vectorización de la consulta:**
   - OpenCLIP tokeniza la query (máx. 200 tokens).
   - Genera vector de 512 dimensiones, normalizado L2.

2. **Búsqueda en ChromaDB:**
   - Recupera **todos** los fragmentos de la colección (`n_results = collection.count()`).
   - ChromaDB calcula distancia coseno: `dist ∈ [0, 2]` donde 0 = idéntico.
   - Conversión a similitud: `similarity = 1.0 - dist` → rango `[0, 1]`.

3. **Filtrado por umbral:** solo fragmentos con `similarity ≥ 0.18` pasan al siguiente paso.

4. **Keyword re-ranking (`_keyword_rerank`):**
   - Extrae palabras clave de la consulta (longitud > 2, fuera de stopwords del dominio).
   - Cuenta coincidencias en: texto del chunk (`text_hits`), ID del documento (`source_hits`), metadatos (`meta_hits`).
   - Aplica boost multiplicativo:
     ```
     boost = 1.0 + 0.10 × text_hits + 0.25 × source_hits + 0.15 × meta_hits
     similarity_final = similarity_base × boost
     ```
   - El score final **puede superar 1.0** (es una puntuación de relevancia, no probabilidad). El umbral 0.18 se aplica a `similarity_base` **antes** del boost.

5. Retorna los **top-K=4** fragmentos ordenados por `similarity_final` con metadatos completos.

**Tiempo promedio por consulta:** 200–500 ms (CLIP en CPU cargado en memoria).

### 6b. GraphRAG

**Clase:** `GraphRetriever.retrieve(query)`

1. **Detección de entidades en la consulta:**
   - `EntityExtractor.extract(query)` — misma taxonomía de 37 entidades.
   - Si no hay entidades formales: búsqueda difusa por tokens del query contra nombres de nodos.

2. **Expansión del sub-grafo:**
   - Para cada entidad detectada: `GraphStore.get_neighbors(entity, hops=2)`.
   - Máximo 2 saltos de distancia en el grafo dirigido.
   - Deduplicación de aristas (por triple `source-relación-target`).

3. **Priorización:**
   - Triples con mayor peso de evidencia primero.
   - Boost: triples que conectan directamente entidades de la consulta.
   - Límite: top-10 triples.

4. **Formato para el LLM:**
   ```
   RELACIONES DEL GRAFO NORMATIVO SRI:
     • contribuyente → [debe presentar / declarar] → declaración de IVA  (Fuente: ...)
     • declaración de IVA → [se declara en] → formulario 104  (Fuente: ...)
   Evidencia textual:
     "Los contribuyentes que realicen actividades gravadas con IVA deberán declarar..."
   ```

**Tiempo promedio por consulta:** 10–50 ms (grafo en memoria, NetworkX).

### 6c. Recuperación Híbrida

**Clase:** `HybridRetriever.retrieve(query, mode="auto")`

`mode` controla qué se **calcula**, no solo qué se descarta — permite medir
tiempo de cada camino por separado (`scripts/run_benchmark.py`) y, con
`USE_AGENTIC_PLANNER=True`, permite que el `PlannerAgent` fuerce el modo real:

| `mode` | Comportamiento |
|---|---|
| `"auto"` (default de producción) | Intenta grafo si está disponible, cae a `vector_only` si no hay triples — comportamiento histórico sin cambios |
| `"vector_only"` | Nunca consulta el grafo, aunque esté disponible |
| `"graph_only"` | Nunca consulta ChromaDB, solo el grafo |
| `"hybrid"` | Fuerza intento de grafo igual que `"auto"` |

Si el grafo no está disponible o no retorna triples, opera en modo `vector_only` sin degradar el sistema.

```
hybrid_result = {
    "vector_chunks":  [...],        # lista de chunks con metadata
    "graph_context":  "texto...",   # relaciones formateadas para el LLM
    "graph_triples":  [...],        # triples estructurados
    "graph_entities": [...],        # entidades detectadas en la query
    "mode":           "hybrid" | "vector_only" | "graph_only"  # modo REAL resultante
}
```

### 6d. PlannerAgent — Decisión Agéntica (opcional, ADR-0005)

**Clase:** `PlannerAgent.should_use_graph(query, model=None) -> bool`

Único punto del pipeline donde el LLM decide dinámicamente en vez de seguir
una regla fija programada. Activo solo si `config.USE_AGENTIC_PLANNER=True`
(default `False`).

1. Llama a Ollama `/api/chat` con una sola herramienta definida
   (`buscar_relaciones_grafo`, descripción detallada de cuándo usarla).
2. La decisión es la **presencia o ausencia** del `tool_call` en la respuesta
   — no un parámetro booleano dentro de él. Más simple y más confiable de
   parsear con un modelo de 3B que pedirle un booleano explícito.
3. Si el LLM llama la herramienta → `mode="hybrid"`. Si no → `mode="vector_only"`.
4. Ante cualquier falla (Ollama caído, timeout `PLANNER_TIMEOUT=30s`,
   respuesta sin `tool_calls` parseable) → degrada a `False` (solo vectorial),
   mismo criterio de degradación segura que `_init_graph_retriever`.

**Por qué decisión binaria y no "elegir entre vector y grafo":** pruebas
reales (curl directo contra Ollama) mostraron sesgo fuerte del modelo de 3B
hacia elegir la herramienta vectorial cuando se ofrecen dos herramientas para
elegir entre sí, incluso con prompts diseñados para forzar el grafo.
Reformulada como decisión binaria ("¿esta pregunta *también* necesita
grafo?", vector siempre corre), la discriminación mejora notablemente.

**Validación empírica:** `scripts/run_benchmark.py --modes agentic` compara
el modo agéntico contra `vector_only`/`graph_only`/`hybrid` con las mismas
métricas (tiempo, RAGAS, `% Doc. correcto`), más una columna `planning_seconds`
propia y `planner_graph_usage_rate` (% de preguntas donde decidió usar grafo
— descriptivo, no una métrica de acierto, no hay ground truth de qué debería
haber decidido cada pregunta).

### 6e. Refinamiento agéntico de la consulta y memoria de aprendizaje in-context (opcional, ADR-0006)

**Clases:** `QueryRefinerAgent.refine(query, rejection_reason="")`,
`QueryValidatorAgent.validate(query) -> dict`, `RefinementMemory`.

Corre justo antes del `PlannerAgent`, sobre la misma `rag_query` combinada
(texto+STT+visual). Detrás del mismo flag `USE_AGENTIC_PLANNER`.

1. **Refinador**: reescribe la pregunta con Ollama (generación libre, sin
   tools). Si `RefinementMemory` tiene ejemplos parecidos guardados, los
   inyecta como few-shot en el prompt.
2. **Validador**: corre un retrieval de prueba real (`RAGAgent.retrieve`,
   vector_only) sobre la pregunta refinada y decide vía tool-calling
   (`rechazar_pregunta(motivo)`) si alcanza para responder — mismo patrón
   de "presencia/ausencia del tool_call decide" que `PlannerAgent`.
3. Si rechaza, el motivo vuelve al Refinador para la siguiente vuelta. Tope
   `REFINEMENT_MAX_ITERATIONS` (default 2, configurable) — al llegar al
   tope, se fuerza el paso con la última versión, nunca bloquea al usuario.
4. Los chunks del último retrieval del Validador se **reusan** en `[RAG]`
   final (`agents/coordinator.py`) — no se duplica la búsqueda vectorial.
   Si el Planner decide `"hybrid"`, se completa aparte solo el
   `graph_context` (`HybridRetriever.retrieve(mode="graph_only")`).

**Memoria de aprendizaje in-context (no fine-tuning):** cuando el loop tuvo
al menos 1 rechazo antes de converger, `RefinementMemory.record()` guarda
`{rejected_query, motivo, approved_query, vector}` en
`outputs/refinement_memory.json`. El vector es el embedding OpenCLIP de la
pregunta rechazada (mismo modelo que `RAGAgent`, sin dependencia nueva). En
cada `refine()` posterior, `RefinementMemory.similar()` busca por similitud
coseno los `REFINEMENT_MEMORY_TOP_K` ejemplos más parecidos (umbral
`REFINEMENT_MEMORY_MIN_SIMILARITY`) y se inyectan como few-shot — el
sistema "aprende" del uso acumulado vía contexto del prompt, no
reentrenando los pesos de qwen2.5:3b (ver "Arquitectura 100% local" más
abajo: no hay pipeline de fine-tuning en este proyecto).

**Fallback:** ante fallo de Ollama en Refiner o Validator, se degrada sin
bloquear — el Refinador devuelve la pregunta sin cambios, el Validador
aprueba por defecto (`approved=True`).

---

## 7. Generación de Respuesta

**Clase:** `ResponseAgent.generate(...)`

### Construcción del prompt

```python
# System prompt (mínimo para evitar que el modelo lo repita en el output —
# estrategia originalmente ajustada para TinyLlama, mantenida con Qwen2.5)
"Eres un asistente tributario del SRI Ecuador. Responde en español. Usa solo el contexto dado."

# Mensaje de usuario
"CONTEXTO NORMATIVO SRI:
[1] <texto del chunk 1 — máx 400 chars>
[2] <texto del chunk 2>
[3] <texto del chunk 3>

RELACIONES DEL GRAFO NORMATIVO SRI:
  • entidad → [relación] → entidad  (Fuente: ...)

PREGUNTA: <consulta del usuario>"

# Seed del assistant (fuerza al modelo a generar contenido, no repetir prompt)
{"role": "assistant", "content": "Respuesta:"}
```

### Parámetros de generación (Ollama API)

| Parámetro | Valor |
|-----------|-------|
| `temperature` | 0.1 |
| `num_predict` | 400 tokens |
| `stop` | `["Usuario:", "Consulta:", "NORMATIVA:", "REGLAS", "Responda", "Usa únicamente", "--- Documento", "[Fuente", "PREGUNTA:"]` |

### Deduplicación de contexto

Antes de enviar al LLM: máximo **1 chunk por documento único**, máximo **3 chunks en total** (`_dedup_by_doc`). Evita que el modelo repita información de la misma fuente.

### Post-procesamiento

- Limpieza de líneas que filtran patrones de instrucciones (`_LEAK_PATTERNS`) — modelos pequeños como TinyLlama a veces repiten fragmentos del system prompt; el filtro se mantiene con Qwen2.5 por seguridad.
- Strip del seed `"Respuesta:"` si el modelo lo incluye en el output.
- Si la respuesta queda vacía: mensaje genérico con referencia a `sri.gob.ec`.

### Construcción de fuentes (en Python, no LLM)

`_collect_sources()` produce la lista **estructurada** de fuentes (deduplicada
por `doc_name`, con tipo, año, artículo/sección, página y similitud) y
`generate()` la publica en el side-channel `last_sources` junto con
`last_answer` (la respuesta limpia). Los consumidores leen esa estructura
directo — el panel de fragmentos de la UI, el corte para TTS del coordinador
y el benchmark ya **no** parsean el texto del chat. El separador
`SOURCES_SEPARATOR` (`─` × 37, definido una sola vez en `response_agent.py`)
es formato de display puro para el bubble del chat.

---

## 8. Síntesis de Voz (TTS)

**Clase:** `TTSAgent.synthesize(text)`

**Backends en cascada (orden de prioridad):**

1. **Piper TTS Python package** — `piper-tts`, modelo `es_ES-sharvard-medium.onnx` (22050 Hz).
2. **Piper TTS binario** — ejecutable del sistema.
3. **macOS `say`** — fallback nativo con voz Monica, convierte AIFF → WAV con `afconvert`.

**Input al TTS:** solo el texto de la respuesta — el bloque de fuentes (separado por `─×37`) se elimina antes de sintetizar para evitar que el motor lea metadatos.

**Límite:** primeros 800 caracteres del texto limpio.

**Salida:** archivo WAV en `temp/sri_response_audio.wav`.

---

## 9. Procesamiento Multimodal de Entrada

### Voz (STT)

**Clase:** `VoiceAgent.transcribe(audio_input)`

- **Modelo:** faster-whisper `base`, idioma forzado a `es`.
- **Pipeline de audio:**
  1. Recibe `(sample_rate, numpy_array)` desde Gradio o archivo WAV.
  2. Convierte a float32 y normaliza amplitud (ceiling 0.9).
  3. Resamplea de 48kHz → 16kHz (Whisper requiere 16kHz).
  4. Transcribe con beam_size=5.
- `cpu_threads=1` para evitar conflictos en macOS Intel.

### Imagen (formularios SRI)

**Clase:** `VisionAgent.analyze(image_input)`

- Acepta PIL Image, numpy array, dict de Gradio, o ruta de archivo.
- Convierte a JPEG base64.
- Envía a Moondream via `POST /api/generate` con prompt especializado para formularios tributarios.
- Retorna descripción de máximo ~30 palabras en español.
- En error (Ollama caído, timeout) retorna `""` — el detalle queda en el log. Nunca retorna strings-sentinela tipo `"[Timeout...]"`: los consumidores no podrían distinguirlos de una descripción real, y filtrar por `[` daba falsos positivos con descripciones legítimas de formularios (checkboxes `[X]`, campos `[RUC]`).
- La descripción se concatena a la query RAG si no está vacía.

### Video

**Clase:** `VideoAgent` — extrae frames cada N fotogramas (default: cada 30 frames, máx. 2 frames), analiza cada frame con `VisionAgent`.

---

## 10. Parámetros de Configuración (`config.py`)

| Parámetro | Valor | Descripción |
|-----------|-------|-------------|
| `LLM_MODEL` | `qwen2.5:3b-instruct-q4_K_M` | Modelo Ollama para generación (ADR-0003) |
| `VISION_MODEL` | `moondream` | Modelo Ollama para visión |
| `USE_MINERU_PDF` | `True` | Backend de parseo PDF por defecto (ADR-0001); fallback automático a PyMuPDF |
| `CLIP_MODEL` | `hf-hub:timm/vit_base_patch32_clip_224.openai` | Modelo de embeddings |
| `CLIP_EMBEDDING_DIM` | 512 | Dimensión del vector semántico |
| `CLIP_MAX_TOKENS` | 200 | Tokens máximos por texto a vectorizar |
| `RAG_TOP_K` | 4 | Fragmentos recuperados por consulta |
| `RAG_MIN_SIMILARITY` | 0.18 | Umbral mínimo de similitud coseno (pre-boost) |
| `GRAPH_ENABLED` | `True` | Activa modo híbrido RAG + GraphRAG |
| `GRAPH_TOP_K_TRIPLES` | 10 | Máx. triples a incluir del grafo |
| `GRAPH_HOP_DEPTH` | 2 | Saltos de exploración en el grafo |
| `GRAPH_MIN_WEIGHT` | 0.4 | Peso mínimo de relación para incluir |
| `USE_AGENTIC_PLANNER` | `False` | Activa los 3 agentes agénticos (Refiner+Validator+Planner, ADR-0005/ADR-0006) en el chat de producción |
| `PLANNER_TIMEOUT` | 30 s | Timeout de la decisión del planner (corto — no es una generación completa) |
| `REFINEMENT_MAX_ITERATIONS` | 2 | Tope de vueltas Refinador⇄Validador antes de forzar el paso (configurable vía env) |
| `REFINER_TIMEOUT` / `VALIDATOR_TIMEOUT` | 30 s | Timeout de cada llamada del Refinador/Validador |
| `REFINEMENT_MEMORY_PATH` | `outputs/refinement_memory.json` | Persistencia de ejemplos aprendidos (ADR-0006) |
| `REFINEMENT_MEMORY_TOP_K` | 3 | Ejemplos más similares inyectados como few-shot en el Refinador |
| `REFINEMENT_MEMORY_MIN_SIMILARITY` | `RAG_MIN_SIMILARITY` (0.18) | Umbral mínimo de similitud coseno para considerar un ejemplo relevante |
| `WHISPER_MODEL_SIZE` | `base` | Tamaño del modelo STT |
| `LLM_TEMPERATURE` | 0.1 | Creatividad del LLM (baja = más determinista) |
| `OLLAMA_TIMEOUT` | 180 s | Timeout máximo de respuesta del LLM |
| `GRADIO_PORT` | 7865 | Puerto de la interfaz web |

---

## 11. Tiempos de Ejecución por Etapa

> Medidos en macOS Intel (sin GPU), con CLIP y grafo ya cargados en memoria.

| Etapa | Tiempo típico | Notas |
|-------|--------------|-------|
| STT (Whisper base) | 1–3 s | Depende de duración del audio |
| Visión (Moondream) | 5–15 s | Primera llamada incluye carga del modelo |
| Embedding CLIP (query) | 50–150 ms | Modelo ya cargado en memoria |
| Búsqueda ChromaDB | 100–400 ms | Escala con el tamaño de la colección |
| Keyword re-ranking | < 10 ms | Solo Python, sin GPU |
| GraphRAG (NetworkX) | 10–50 ms | Grafo en memoria RAM |
| Generación LLM (Qwen2.5, 3B) | por medir | Mayor que TinyLlama (1.1B) por ser CPU puro — ver benchmark de la tesis (`scripts/run_benchmark.py`) |
| TTS (Piper) | 1–4 s | Depende del largo de la respuesta |
| **Total por consulta (texto)** | por medir | Dominado por la generación LLM — cifra exacta en el reporte de benchmark |
| **Primera consulta** | **+15–30 s** | Carga de CLIP + ChromaDB + Whisper |

---

## 12. Decisiones de Diseño para la Tesis

### ¿Por qué OpenCLIP para embeddings de texto?

OpenCLIP ViT-B-32 fue diseñado para espacio semántico multimodal (texto + imagen). Permite que una imagen de un formulario SRI (`embed_image`) y su descripción textual queden en el mismo espacio vectorial, facilitando búsquedas cruzadas texto-imagen sin embeddings separados.

### ¿Por qué Qwen2.5 y no TinyLlama ni un modelo más grande?

Restricción de hardware: macOS Intel sin GPU. TinyLlama (1.1B) fue la elección inicial por ser el más liviano, pero en la práctica alucinaba normativa y citaba mal la fuente — inaceptable para un asistente que debe basarse en documentos recuperados (ver ADR-0003). Se reemplazó por Qwen2.5:3b-instruct-q4_K_M, ~3x más grande, a costa de generación más lenta en CPU. Modelos como Llama 3 (8B) tardarían varios minutos por respuesta en este hardware. La estrategia de prompt con seed `"Respuesta:"` + stop sequences, diseñada originalmente para compensar la tendencia de TinyLlama a repetir instrucciones, se mantiene con Qwen2.5 por seguridad. La elección de modelo queda sujeta a revalidación empírica vía el benchmark de la tesis (`scripts/run_benchmark.py`, compara Qwen2.5 vs otros modelos disponibles en Ollama).

### ¿Por qué grafos de conocimiento además de RAG vectorial?

El RAG vectorial recupera **fragmentos de texto** — excelente para respuestas con citación directa. El GraphRAG complementa con **relaciones estructurales** entre entidades: por ejemplo, sabe que `contribuyente → debe_presentar → declaración de IVA → declara_en → formulario 104` aunque ningún chunk lo diga explícitamente en esas palabras. Esto mejora preguntas del tipo "¿qué obligaciones tiene una persona natural?".

### ¿Por qué reglas y no NLP/NER entrenado?

El dominio tributario ecuatoriano tiene terminología fija y bien delimitada. Una taxonomía de 37 entidades con regex sobre texto normalizado (sin tildes) cubre el vocabulario controlado de la LORTI y resoluciones SRI con precisión predecible y sin dependencias externas (spaCy, transformers, etc.). La extracción de relaciones por patrones léxico-verbales es interpretable y auditable — relevante para un sistema que debe ser explicable ante el SRI.

### Arquitectura 100% local

Ningún componente requiere internet en tiempo de ejecución: Ollama corre los LLMs localmente, ChromaDB es una BD embebida, Piper TTS funciona con modelos ONNX en disco, faster-whisper descarga el modelo una vez. Esto garantiza privacidad de la consulta y funcionamiento sin conectividad. El benchmark/RAGAS respeta el mismo principio: juez local vía Ollama, embeddings `sentence-transformers` locales, nunca OpenAI (ver ADR-0005 y `scripts/ragas_local.py`).

### ¿Por qué agregar un PlannerAgent y no dejar la arquitectura multiagente clásica?

La arquitectura original (`CoordinatorAgent` orquestando agentes especializados en una secuencia fija de `if/else`) es una arquitectura multiagente **clásica** — módulos con responsabilidad única, sin autonomía real. No calificaba como "software agéntico" en el sentido moderno (LLM decidiendo dinámicamente, no una regla programada). El `PlannerAgent` (ADR-0005) agrega ese único punto de decisión real: decide vía tool-calling si la consulta necesita GraphRAG. Se prefirió una decisión **binaria** ("¿también necesita grafo?", vector siempre corre) en vez de "elegir entre dos herramientas", porque pruebas reales mostraron que un modelo de 3B discrimina mucho mejor una decisión binaria que una elección exclusiva entre dos tools con nombres similares — un hallazgo empírico documentado, no una suposición de diseño.

### Datos estructurados entre módulos, nunca texto de display re-parseado

Segunda revisión de arquitectura (2026-07): se eliminaron todos los contratos
"string-typed" — lugares donde un módulo serializaba datos a texto de display
y otro los re-parseaba con regex, con degradación silenciosa si el formato
cambiaba. Cuatro decisiones resultantes:

- **Vocabulario de etapas (`Stage`)**: las etiquetas del pipeline (`INICIO`,
  `PLANNER`, `RAG`, …) se definen una sola vez en `agents/log_agent.py`;
  todos los productores usan `Stage.X` (un typo falla con `AttributeError`
  visible, no en silencio). El diagrama de flujo de agentes consume
  `LogAgent.get_events()` (eventos estructurados), no regex sobre el log.
- **Side-channel de fuentes**: `ResponseAgent` publica `last_answer`
  (respuesta limpia) y `last_sources` (lista estructurada) tras cada
  generación; el panel de la UI, el corte para TTS y el benchmark leen esa
  estructura — el separador `─×37` del chat es display puro, definido una
  sola vez (`SOURCES_SEPARATOR`).
- **Sin strings-sentinela**: visión/video retornan `""` en error (detalle al
  log), nunca `"[Timeout...]"` — el filtro por `[` descartaba descripciones
  legítimas de formularios (`[X]`, `[RUC]`).
- **Tabs con datos frescos**: las tabs de estadísticas (Base de Conocimiento,
  Benchmark RAGAS, Estado del Sistema) recalculan sus datos al entrar
  (`Tab.select`) en vez de hornearlos al arranque de la app — correr un
  benchmark o reingestar documentos se refleja sin reiniciar.

### ¿Por qué un flag (`USE_AGENTIC_PLANNER`) en vez de activarlo directo?

El planner tiene una limitación conocida y medida: sesgo hacia "no usar grafo" incluso en preguntas donde ayudaría. Activar la decisión agéntica en el chat de producción sin antes medir su impacto real (tiempo, calidad de respuesta) sería reemplazar una regla fija conocida por una decisión de fiabilidad desconocida. El flag permite validar con `scripts/run_benchmark.py --modes agentic` antes de decidir si conviene por defecto — mismo patrón que `USE_MINERU_PDF`/`GRAPH_ENABLED`: agregar la capacidad, medirla, decidir con datos.

### ¿Por qué el Refinador/Validador comparten el mismo flag que el Planner, en vez de uno propio?

Los 3 agentes son el mismo tramo conceptual — "el LLM decide/mejora algo del pipeline en vez de seguir una regla fija programada" — y separar flags habría permitido combinaciones sin sentido (ej. Validator activo sin Planner). Un solo flag mantiene la garantía de que `USE_AGENTIC_PLANNER=False` reproduce exactamente el pipeline histórico, sin superficie nueva (ADR-0006).

### ¿Por qué few-shot con memoria in-context y no fine-tuning del modelo?

El proyecto es 100% de inferencia local (ver más abajo): no hay GPU de entrenamiento ni pipeline de fine-tuning, y agregar uno habría sido infraestructura completamente nueva, fuera del alcance de la tesis. `RefinementMemory` guarda las correcciones reales del Validador (`{rejected_query, motivo, approved_query}`) y las inyecta como ejemplos few-shot cuando aparece una pregunta similar — el sistema mejora con el uso sin reentrenar pesos. Es una forma honesta de "aprendizaje" acotada a lo que el hardware disponible permite (ADR-0006).

---

## 13. Flujo Resumido para la Presentación

```
Usuario hace pregunta (texto / voz / imagen)
          │
          ▼
  [Entrada multimodal]
  Voz → Whisper → texto
  Imagen → Moondream → descripción
          │
          ▼
  [Refinador ⇄ Validador] (opcional, USE_AGENTIC_PLANNER)
  Refinador reescribe la pregunta (+ memoria in-context) →
  Validador la valida contra un retrieval de prueba real
  Rechazo → vuelve al Refinador con el motivo (máx. 2 vueltas, ADR-0006)
          │
          ▼
  [PlannerAgent] (opcional, USE_AGENTIC_PLANNER)
  Tool-calling de Ollama: ¿necesita GraphRAG? sí/no
  Con Refinador/Validador, son los 3 pasos con decisión
  real del LLM (ADR-0005 / ADR-0006)
          │
          ▼
  [HybridRetriever]
  ┌─────────────────────┐    ┌──────────────────────┐
  │   RAG Vectorial     │    │      GraphRAG         │
  │  OpenCLIP + Chroma  │    │  37 entidades +       │
  │  similitud coseno   │    │  8 tipos relación     │
  │  + keyword boost    │    │  NetworkX 2-hop       │
  └────────┬────────────┘    └──────────┬───────────┘
           │                            │
           └──────────┬─────────────────┘
                      ▼
          Contexto normativo unificado
          (chunks + triples del grafo)
                      │
                      ▼
          [Qwen2.5 via Ollama]
          temp=0.1 · seed "Respuesta:"
          stop sequences · max 400 tokens
                      │
                      ▼
          Respuesta en español
          + fuentes citadas (Python)
          + audio Piper TTS
          + diagrama animado de flujo de agentes en la UI
```
