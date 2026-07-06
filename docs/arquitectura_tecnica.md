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

---

## 3. Estructura del Proyecto

```
SRI_IA_Multimodal/
├── app.py                      # Punto de entrada — instancia CoordinatorAgent + Gradio
├── config.py                   # Configuración central (todos los parámetros)
├── agents/
│   ├── coordinator.py          # Orquestador — pipeline completo
│   ├── rag_agent.py            # Recuperación vectorial con OpenCLIP + ChromaDB
│   ├── response_agent.py       # Generación LLM + construcción de fuentes
│   ├── vision_agent.py         # Análisis de imágenes con Moondream
│   ├── video_agent.py          # Extracción de frames de video
│   ├── voice_agent.py          # STT con faster-whisper
│   ├── tts_agent.py            # TTS con Piper (3 backends en cascada)
│   └── log_agent.py            # Log en tiempo real para la UI
├── graph/
│   ├── entity_extractor.py     # Taxonomía de 37 entidades tributarias
│   ├── relation_extractor.py   # Extracción de relaciones por patrones léxicos
│   ├── graph_builder.py        # Constructor del grafo desde chunks RAG
│   ├── graph_store.py          # Almacenamiento NetworkX + persistencia JSON
│   └── graph_retriever.py      # Recuperación por sub-grafo para una consulta
├── rag/
│   ├── chunker.py              # Fragmentación PDF/DOCX/TXT/MD con overlap
│   ├── ingesta.py              # Ingesta masiva a ChromaDB con embeddings CLIP
│   └── build_db.py             # Script de construcción/reconstrucción de la BD
├── services/
│   └── hybrid_retriever.py     # Combina RAG vectorial + GraphRAG
├── scripts/
│   └── build_graph.py          # Script de construcción del grafo de conocimiento
├── data/
│   ├── normativas_sri/         # Leyes, LORTI, Código Tributario
│   ├── resoluciones/           # Resoluciones NAC del SRI
│   ├── guias_tributarias/      # Guías de declaración, RUC, comprobantes
│   └── formularios/            # Instructivos formularios 104, 101, 103…
├── vector_db/chroma_sri/       # Base vectorial persistida (ChromaDB)
├── graph_db/sri_graph.json     # Grafo de conocimiento (NetworkX serializado)
├── ui/
│   ├── interface.py            # Componentes Gradio y lógica de la UI
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

3. **Metadatos por chunk:** `id`, `doc_name`, `tipo_normativa`, `año`, `pagina`, `articulo_seccion`, `source`, `ruta_archivo`.

4. **Vectorización:**
   - OpenCLIP ViT-B-32 (512 dimensiones).
   - Normalización L2: `vec /= vec.norm(dim=-1, keepdim=True)`.
   - Cómputo en CPU (float32), ~50–200 ms por chunk.

5. **Almacenamiento:** ChromaDB con espacio coseno (`hnsw:space = cosine`).

**Estado actual:** 9.448 fragmentos de 176 documentos.

**Tiempos de construcción (macOS Intel, CPU):**
| Operación | Tiempo aprox. |
|-----------|--------------|
| Extracción PDF (por documento) | 0.1–2 s |
| Embedding CLIP (por chunk) | 50–200 ms |
| Ingesta completa 176 docs | 15–40 min |
| Reconexión a BD ya existente | < 1 s |

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
   - Patrones léxico-verbales sobre oraciones.
   - **12 tipos de relación:** `debe_presentar`, `debe_retener`, `puede_deducir`, `esta_exento`, `aplica_tarifa`, `debe_inscribirse`, `establece`, `declara_en`, `genera_obligacion`, `tiene_plazo`, `puede_acogerse`, `relacionado_con`.
   - Cada relación emite un **triple** `(fuente, relación, destino)` con evidencia textual y nombre del documento.

4. **Almacenamiento NetworkX:**
   - `nx.DiGraph` — nodos son entidades, aristas son relaciones.
   - Persistido en JSON (`graph_db/sri_graph.json`).
   - Soporte opcional Neo4j (no requerido — sistema funciona 100% local).

**Estado actual:** 37 entidades (nodos), 568 relaciones (aristas), 933 triples.

**Tiempos de construcción:**
| Operación | Tiempo aprox. |
|-----------|--------------|
| Construcción grafo completo (9.448 chunks) | 2–5 min |
| Carga del grafo JSON al iniciar app | < 0.5 s |

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

**Clase:** `HybridRetriever.retrieve(query)`

Ejecuta ambos retrievers y combina sus salidas. Si el grafo no está disponible o no retorna triples, opera en modo `vector_only` sin degradar el sistema.

```
hybrid_result = {
    "vector_chunks":  [...],        # lista de chunks con metadata
    "graph_context":  "texto...",   # relaciones formateadas para el LLM
    "graph_triples":  [...],        # triples estructurados
    "graph_entities": [...],        # entidades detectadas en la query
    "mode":           "hybrid" | "vector_only"
}
```

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

La sección de fuentes se construye programáticamente en `_build_sources_section()`:
- Deduplica por `doc_name`.
- Lista cada fuente con tipo, año, artículo/sección, página y similitud.
- Separada de la respuesta por `─` × 37 (U+2500 × 37) — la UI divide en dos paneles en este carácter.

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
- La descripción se concatena a la query RAG si no contiene `[` (descarta mensajes de error).

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

Ningún componente requiere internet en tiempo de ejecución: Ollama corre los LLMs localmente, ChromaDB es una BD embebida, Piper TTS funciona con modelos ONNX en disco, faster-whisper descarga el modelo una vez. Esto garantiza privacidad de la consulta y funcionamiento sin conectividad.

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
  [HybridRetriever]
  ┌─────────────────────┐    ┌──────────────────────┐
  │   RAG Vectorial     │    │      GraphRAG         │
  │  OpenCLIP + Chroma  │    │  37 entidades +       │
  │  similitud coseno   │    │  12 tipos relación    │
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
```
