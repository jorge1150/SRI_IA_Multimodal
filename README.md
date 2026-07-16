# SRI IA Multimodal

**Asistente Virtual Basado en Generación Aumentada por Recuperación Multimodal para la Gestión Dinámica de la Normativa Tributaria del Servicio de Rentas Internas en Ecuador**

Maestría en Inteligencia Artificial Aplicada · UIsrael  

---

## Descripción

Sistema multimodal 100% local que responde consultas sobre normativa tributaria del SRI Ecuador. Combina RAG vectorial (ChromaDB + OpenCLIP), GraphRAG (grafo de conocimiento tributario), modelos de lenguaje locales, reconocimiento de voz, análisis visual y síntesis de voz para ofrecer respuestas citando la fuente normativa específica.

## Arquitectura del Sistema

```
┌─────────────────────────────────────────────────────────────────┐
│                    ENTRADAS MULTIMODALES                        │
│  🎤 Voz → Whisper STT  │  📷 Imagen → Moondream  │  💬 Texto   │
└────────────────────────┬────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│                    COORDINADOR (Orquestador)                    │
└────────────────────────┬────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│  ✏️ REFINADOR ⇄ ✅ VALIDADOR (opcional, USE_AGENTIC_PLANNER)     │
│  Refinador reescribe la pregunta (+ memoria in-context de       │
│  correcciones pasadas) → Validador la valida contra un          │
│  retrieval de prueba real. Rechazo → vuelve al Refinador con    │
│  el motivo, hasta REFINEMENT_MAX_ITERATIONS (default 2) (ADR-0006)│
└────────────────────────┬────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│  🧠 PLANNER AGENT (opcional, USE_AGENTIC_PLANNER)               │
│  Decide vía tool-calling de Ollama: ¿esta consulta necesita     │
│  GraphRAG además del RAG vectorial? Con Refinador/Validador,    │
│  son los 3 puntos del pipeline donde el LLM decide/mejora       │
│  dinámicamente, no una regla fija (ADR-0005, ADR-0006)          │
└────────────────────────┬────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│              HYBRID RETRIEVER (recuperación híbrida)            │
│                                                                 │
│  ┌─────────────────────────┐  ┌──────────────────────────────┐ │
│  │  RAG VECTORIAL          │  │  GRAPHRAG                    │ │
│  │  OpenCLIP → ChromaDB    │  │  Entidades → NetworkX DiGraph│ │
│  │  Fragmentos normativos  │  │  Relaciones tributarias      │ │
│  │  + similitud coseno     │  │  (debe_presentar, aplica_    │ │
│  │                         │  │   tarifa, esta_exento, ...)  │ │
│  └───────────┬─────────────┘  └──────────────┬───────────────┘ │
│              └──────────────┬─────────────────┘                 │
└───────────────────────────  ↓  ──────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│              LLM (Qwen2.5 via Ollama)                           │
│  Prompt: normativa RAG + relaciones de grafo → respuesta        │
└────────────────────────┬────────────────────────────────────────┘
                         ↓
              🔊 Piper TTS → Respuesta en voz
```

> La UI incluye un diagrama animado en vivo de este flujo (botón "🕸️ Ver
> Flujo de Agentes" en la tab Consulta Tributaria) — se ve el nodo activo
> pulsando y el Validador/Planner marcados como los puntos de decisión real.

## Stack Tecnológico

| Componente | Tecnología |
|---|---|
| Interfaz | Gradio 6.x |
| LLM | Qwen2.5:3b-instruct via Ollama |
| Visión | Moondream via Ollama |
| STT | faster-whisper (base) |
| Embeddings | OpenCLIP ViT-B-32 |
| Vector DB | ChromaDB (cosine) |
| Grafo conocimiento | NetworkX DiGraph + JSON |
| Recuperación híbrida | HybridRetriever (RAG + GraphRAG) |
| TTS | Piper TTS es_ES-sharvard |
| PDF | MinerU (layout/tablas/OCR), fallback a PyMuPDF (fitz) |
| DOCX | python-docx |
| Decisión agéntica | PlannerAgent — tool-calling nativo de Ollama (ADR-0005) |
| Refinamiento agéntico + memoria | QueryRefinerAgent/QueryValidatorAgent — reescritura + tool-calling + memoria in-context vía similitud CLIP (ADR-0006) |
| Evaluación / benchmark | RAGAS (juez local Ollama) + sentence-transformers (embeddings) |

## Estructura del Proyecto

```
SRI_IA_Multimodal/
├── app.py                      # Punto de entrada
├── config.py                   # Configuración central (incl. GRAPH_ENABLED)
├── requirements.txt
├── setup.sh
│
├── agents/                     # Sistema multiagente
│   ├── coordinator.py          # Orquestador del pipeline + build_retrieval_pipeline()
│   ├── planner_agent.py        # Decisión agéntica sí/no GraphRAG (tool-calling, ADR-0005)
│   ├── query_refiner_agent.py  # Reescribe la pregunta + few-shot de memoria (ADR-0006)
│   ├── query_validator_agent.py # Valida la pregunta contra retrieval de prueba (ADR-0006)
│   ├── refinement_memory.py    # Memoria in-context (JSON + similitud CLIP)
│   ├── rag_agent.py            # Recuperación semántica vectorial
│   ├── response_agent.py       # Generación con citas + fuentes estructuradas (last_sources)
│   ├── voice_agent.py          # STT (Whisper)
│   ├── vision_agent.py         # Análisis visual (Moondream)
│   ├── video_agent.py          # Procesamiento de video
│   ├── tts_agent.py            # Síntesis de voz (Piper)
│   └── log_agent.py            # Trazabilidad — vocabulario Stage + eventos estructurados
│
├── rag/                        # Motor RAG vectorial
│   ├── chunker.py              # Fragmentación PDF/DOCX/TXT/MD (MinerU-aware: kind, graph_text)
│   ├── ingesta.py              # Carga a ChromaDB con metadatos + tiempo de build
│   └── build_db.py             # Script de construcción vectorial
│
├── graph/                      # Módulo GraphRAG (grafo de conocimiento)
│   ├── __init__.py
│   ├── entity_extractor.py     # Extracción de entidades tributarias (regex/taxonomía)
│   ├── relation_extractor.py   # Extracción de relaciones (patrones verbales)
│   ├── graph_store.py          # Persistencia NetworkX DiGraph + JSON
│   ├── graph_builder.py        # Construcción del grafo desde documentos
│   └── graph_retriever.py      # Consulta del grafo por entidades
│
├── services/                   # Servicios transversales
│   ├── __init__.py
│   ├── hybrid_retriever.py     # RAG vectorial + GraphRAG combinados (mode=)
│   └── benchmark_format.py     # Formato compartido de métricas (script CLI + tab de la UI)
│
├── scripts/                    # Scripts CLI
│   ├── build_graph.py          # Construir grafo: python scripts/build_graph.py
│   ├── run_benchmark.py        # Benchmark de tesis: RAG vs GraphRAG vs Híbrido vs Agéntico + RAGAS
│   ├── ragas_local.py          # Juez RAGAS local (Ollama) + embeddings (sentence-transformers)
│   └── benchmark_dataset.py    # Parser de preguntas.docx
│
├── ui/                         # Interfaz Gradio
│   ├── interface.py            # Layout, panel RAG, eventos, diagrama de flujo de agentes
│   └── styles.py               # CSS tema SRI (dark + Ecuador colors)
│
├── data/                       # Documentos normativos SRI — categorías DINÁMICAS
│   └── <categoría>/            # Cada subcarpeta de data/ es una categoría; el nombre
│                                # de la carpeta se usa como tipo_normativa (sin tabla
│                                # de mapeo fija). Ej.: data/IVA (Impuesto al Valor Agregado)/
│
├── preguntas.docx               # Dataset de preguntas para scripts/run_benchmark.py
├── vector_db/chroma_sri/       # Base vectorial ChromaDB (generada)
├── vector_db/build_metadata.json # Tiempo acumulado de construcción del vector store
├── graph_db/sri_graph.json     # Grafo de conocimiento (generado, incl. build_seconds)
├── outputs/respuestas_audio/   # Audio generado
├── outputs/logs/               # Logs de sesión
├── outputs/benchmarks/         # Reportes de scripts/run_benchmark.py (CSV/HTML/JSON)
├── outputs/refinement_memory.json # Memoria de aprendizaje in-context del Refinador (ADR-0006)
└── audio/piper_models/         # Modelos TTS (descargados)
```

## Instalación

### Requisitos previos
- Python 3.12
- Ollama instalado
- Homebrew (macOS)

### Instalación automática

```bash
bash setup.sh
```

### Instalación manual

```bash
# 1. Entorno virtual Python 3.12
/usr/local/bin/python3.12 -m venv venv
source venv/bin/activate

# 2. PortAudio
brew install portaudio

# 3. Dependencias (incluye networkx para GraphRAG, ragas + sentence-transformers
#    para el benchmark de tesis — versiones fijadas, ver comentario en
#    requirements.txt sobre compatibilidad con torch==2.2.2)
pip install -r requirements.txt

# 4. Modelos Ollama
ollama pull qwen2.5:3b-instruct-q4_K_M
ollama pull moondream

# 5. Voz Piper
python audio/download_piper.py

# 6. Base vectorial (documentos demo incluidos)
python rag/build_db.py

# 7. Grafo de conocimiento GraphRAG
python scripts/build_graph.py

# 8. Iniciar
ollama serve &
python app.py
```

## Cargar Documentos Oficiales del SRI

Las categorías son **dinámicas**: cada subcarpeta directa de `data/` (excepto
`data/output/`, reservado para salidas de MinerU) es una categoría normativa —
el nombre de la carpeta se usa tal cual como `tipo_normativa`, sin tabla de
mapeo. Renombrar o agregar una carpeta cambia la categoría sin tocar código.

```bash
# Crear una carpeta con el nombre de la categoría y copiar los documentos:
mkdir -p "data/IVA (Impuesto al Valor Agregado)"
cp mis_pdfs/*.pdf "data/IVA (Impuesto al Valor Agregado)/"

# Formatos soportados: .pdf, .txt, .docx, .md

# Reconstruir la base vectorial:
python rag/build_db.py --reset

# Reconstruir el grafo GraphRAG (siempre tras agregar documentos):
python scripts/build_graph.py --reset
```

## Ejemplos de Consultas

```
¿Cuál es la tarifa actual del IVA en Ecuador?
¿Cuáles son los plazos para declarar el IVA si mi RUC termina en 5?
¿Cómo obtengo el RUC como persona natural?
¿Qué gastos son deducibles del impuesto a la renta?
¿Qué es el RISE y quién puede acogerse?
¿Qué comprobantes electrónicos existen en Ecuador?
¿Cuál es la tarifa del impuesto a la renta para sociedades?
¿Qué pasa si no presento la declaración del IVA a tiempo?
```

## Metadatos RAG

Cada fragmento normativo almacenado incluye:

| Metadato | Descripción |
|---|---|
| `doc_name` | Nombre del documento |
| `tipo_normativa` | Ley / Resolución / Guía / Formulario |
| `año` | Año del documento (extraído del nombre) |
| `pagina` | Número de página (PDFs) |
| `articulo_seccion` | Artículo o sección detectada |
| `ruta_archivo` | Ruta del archivo fuente |

## Flujo RAG + GraphRAG Detallado

```
1. Usuario hace consulta (texto/voz/imagen)
2. [STT]     Whisper transcribe audio → texto
3. [VISION]  Moondream describe imagen → contexto visual
4. [REFINADOR⇄VALIDADOR] (si USE_AGENTIC_PLANNER=True) el Refinador reescribe
             la pregunta (+ few-shot de memoria), el Validador la valida
             contra un retrieval de prueba real; rechazo → vuelve al
             Refinador con el motivo, hasta REFINEMENT_MAX_ITERATIONS
5. [PLANNER] (si USE_AGENTIC_PLANNER=True) el LLM decide vía tool-calling
             si esta consulta necesita GraphRAG además del RAG vectorial
6. [HYBRID]  HybridRetriever ejecuta según el modo (auto o el decidido por el planner);
             si el Validador ya trajo chunks, se reusan sin repetir la búsqueda
   6a. [RAG]    OpenCLIP vectoriza consulta → ChromaDB similitud coseno
   6b. [GRAPH]  EntityExtractor detecta entidades (IVA, RUC, RISE, ...)
               GraphRetriever explora relaciones en NetworkX (hop_depth=2)
               → Triples: "Contribuyente —debe_presentar→ Declaración IVA"
7. [LLM]    Qwen2.5 recibe: fragmentos RAG + relaciones de grafo
           → Respuesta con citas de fuente normativa
8. [TTS]    Piper sintetiza respuesta en español
9. [LOGS]   Trazabilidad completa: refinamiento, modo hybrid/vector_only,
            entidades, triples, decisión del planner — visible también como
            diagrama animado (botón "Ver Flujo de Agentes")
```

## GraphRAG — Grafo de Conocimiento Tributario

El módulo GraphRAG extrae automáticamente entidades y relaciones de los documentos normativos para construir un grafo de conocimiento local.

### Entidades reconocidas (taxonomía SRI Ecuador)

`IVA` · `Impuesto a la Renta` · `RISE` · `RUC` · `Retención` · `Declaración` · `Contribuyente` · `Agente de Retención` · `Formulario 104` · `Formulario 101` · `LORTI` · `SRI` · y más de 30 entidades tributarias.

### Tipos de relaciones extraídas

| Relación | Significado |
|---|---|
| `debe_presentar` | Sujeto obligado a presentar declaración/formulario |
| `debe_retener` | Agente obligado a retener impuesto |
| `puede_deducir` | Gasto/valor deducible permitido |
| `esta_exento` | Bien/servicio exento de impuesto |
| `aplica_tarifa` | Impuesto aplica una tarifa específica |
| `debe_inscribirse` | Sujeto obligado a inscribirse en registro |
| `establece` | Ley/normativa que establece obligación |
| `declara_en` | Declaración se realiza en formulario/periodo |
| `tiene_plazo` | Obligación con plazo definido |
| `puede_acogerse` | Régimen al que puede acogerse el contribuyente |

### Construir / reconstruir el grafo

```bash
# Primera vez (o tras agregar documentos):
python scripts/build_graph.py

# Reconstruir desde cero:
python scripts/build_graph.py --reset

# Ver estadísticas sin reconstruir:
python scripts/build_graph.py --stats-only

# Exportar a GraphML (para visualizar en Gephi):
python scripts/build_graph.py --export-graphml
```

### Activar / desactivar GraphRAG

En `config.py`:
```python
GRAPH_ENABLED: bool = True   # False = solo RAG vectorial
```

Si `GRAPH_ENABLED=True` pero el grafo no existe aún, el sistema cae back a RAG vectorial automáticamente sin errores.

## Refinador → Validador → PlannerAgent — Tramo Agéntico (ADR-0005, ADR-0006)

El resto de agentes del sistema ejecutan una tarea fija — este tramo de 3
agentes es donde el LLM **decide/mejora** dinámicamente, en vez de seguir
una regla programada, todos detrás del mismo flag:

```python
# config.py
USE_AGENTIC_PLANNER: bool = False       # default: chat de producción usa el pipeline fijo histórico
PLANNER_TIMEOUT: int = 30                # decisión corta, no una generación completa
REFINEMENT_MAX_ITERATIONS: int = 2       # tope Refinador⇄Validador antes de forzar el paso
REFINER_TIMEOUT: int = 30
VALIDATOR_TIMEOUT: int = 30
REFINEMENT_MEMORY_PATH: str = "outputs/refinement_memory.json"
```

```bash
# Activar para probarlo (activa Refinador + Validador + Planner):
USE_AGENTIC_PLANNER=true python app.py
```

**`QueryRefinerAgent`** reescribe la pregunta (texto+STT+visual combinados)
para que sea más clara y específica, inyectando como few-shot ejemplos de
correcciones pasadas similares guardadas en `RefinementMemory`.

**`QueryValidatorAgent`** corre un retrieval de prueba real sobre la
pregunta refinada y decide vía tool-calling (`rechazar_pregunta(motivo)`) si
alcanza para responder. Si rechaza, el motivo vuelve al Refinador para la
siguiente vuelta — hasta `REFINEMENT_MAX_ITERATIONS`, luego se fuerza el
paso con la última versión (nunca bloquea al usuario). Los chunks de ese
retrieval de prueba se reusan en `[RAG]` final, sin duplicar la búsqueda.

**`PlannerAgent`** decide si la pregunta ya refinada/aprobada necesita
GraphRAG además del RAG vectorial (que siempre corre).

**Memoria de aprendizaje in-context**: cuando el loop tuvo al menos 1
rechazo antes de converger, se guarda `{rejected_query, motivo,
approved_query, vector}` en `outputs/refinement_memory.json` (vector =
embedding OpenCLIP, mismo modelo que `RAGAgent`). El Refinador la reusa como
few-shot en preguntas futuras similares — el sistema mejora con el uso sin
reentrenar pesos (no hay fine-tuning en este proyecto 100% de inferencia
local).

Con el tramo activo, la tab "Consulta Tributaria" muestra un botón
**"🕸️ Ver Flujo de Agentes"** — diagrama animado en vivo que va marcando qué
agente está trabajando en cada momento del pipeline, con los nodos Validador
y Planner distinguidos visualmente como puntos de decisión real (borde
punteado).

Ante cualquier falla (Ollama caído, timeout, respuesta sin parsear) cada
agente degrada sin bloquear el pipeline: el Refinador devuelve la pregunta
sin cambios, el Validador aprueba por defecto, el Planner cae a `False` —
mismo criterio de degradación segura que ya usa el sistema cuando el grafo
no está disponible.

**Limitaciones conocidas** (documentadas, no ocultas): un modelo de 3B tiene
sesgo hacia elegir "no usar grafo" incluso en preguntas donde ayudaría, y
puede no converger en preguntas límite dentro del loop de refinamiento — por
eso ambas decisiones se validan empíricamente con `scripts/run_benchmark.py`
antes de considerar activarlas por defecto (ver sección Benchmark abajo).

## Benchmark de Tesis — RAG vs GraphRAG vs Híbrido vs Agéntico + RAGAS

```bash
# Prueba rápida (solo tiempos, sin juez RAGAS):
python scripts/run_benchmark.py --limit 5 --no-ragas

# Corrida completa (puede tardar horas en CPU — 42 preguntas × modos × modelos):
python scripts/run_benchmark.py

# Elegir modos/modelos específicos:
python scripts/run_benchmark.py --modes vector_only,agentic --models qwen2.5:3b-instruct-q4_K_M,tinyllama:latest
```

Compara, por cada combinación pregunta × modo × modelo:

| Métrica | Qué mide |
|---|---|
| `retrieval_seconds` | Tiempo en buscar contexto (vectorial y/o grafo) |
| `refinement_seconds` / `refinement_iterations` | Solo en modo `agentic` — tiempo y vueltas del loop Refinador⇄Validador |
| `planning_seconds` | Solo en modo `agentic` — tiempo de la decisión sí/no grafo |
| `generation_seconds` | Tiempo en que el LLM redacta la respuesta |
| `faithfulness` / `answer_relevancy` | RAGAS — juez local vía Ollama, embeddings `sentence-transformers` (nunca OpenAI, sistema 100% local) |
| `source_matched` | Si el retrieval trajo el documento fuente esperado (según `preguntas.docx`) |

Resultado en `outputs/benchmarks/` (CSV con datos crudos, HTML con reporte
visual, JSON de resumen) — visible también en la tab **"📊 Benchmark RAGAS"**
de la UI, que lee el reporte más reciente **cada vez que entrás a la tab**
(al igual que "Base de Conocimiento" y "Estado del Sistema", los datos se
refrescan al entrar — no hace falta reiniciar la app tras correr un benchmark
o reingestar documentos). La tab es solo lectura: correr el benchmark sigue
siendo por terminal.

**Nota:** correr el benchmark en modo `agentic` también alimenta
`outputs/refinement_memory.json` con lecciones reales del loop de
refinamiento (ver ADR-0006) — no es solo medición, deja rastro persistente.

**Nota de compatibilidad:** RAGAS/`sentence-transformers` requieren versiones
específicas fijadas en `requirements.txt` — las últimas versiones de esas
librerías arrastran dependencias incompatibles entre sí y con `torch==2.2.2`
(pinneado por MinerU/OpenCLIP). Ver comentario en `requirements.txt`.

## Notas Importantes

> Las respuestas son orientativas e informativas. No constituyen asesoría legal
> ni tributaria definitiva. Verificar siempre en [sri.gob.ec](https://sri.gob.ec)
> o consultar con un profesional tributario.

## Tests

Suite completa en verde (111 tests): chunker MinerU-aware, GraphRAG,
PlannerAgent + QueryRefinerAgent + QueryValidatorAgent + RefinementMemory
(con fallbacks mockeados), loop de refinamiento (`run_refinement_loop`),
HybridRetriever (todos los modos), fuentes estructuradas, diagrama de flujo
de agentes, rutas de error de visión y helpers del benchmark.

```bash
# Todos los tests
python -m pytest tests/ -v

# Solo GraphRAG
python -m pytest tests/test_graph.py -v

# Solo agentes/RAG (incluye Planner/Refiner/Validator, visión, fuentes, diagrama de flujo)
python -m pytest tests/test_agents.py tests/test_rag.py -v

# Solo benchmark/RAGAS (incluye formateadores compartidos)
python -m pytest tests/test_benchmark.py tests/test_benchmark_dataset.py -v
```

## Diferencias con S3 IA Multimodal (Proyecto Base)

| Aspecto | S3 IA Multimodal | SRI IA Multimodal |
|---|---|---|
| Dominio | Soporte técnico PC | Normativa tributaria SRI |
| Documentos | TXT manuales técnicos | PDF/DOCX/TXT normativos (MinerU) |
| Metadatos RAG | source, id | + tipo, año, artículo, página, kind |
| Recuperación | RAG vectorial | RAG vectorial + GraphRAG + decisión agéntica |
| Grafo conocimiento | No | Sí (NetworkX + JSON, 100% local) |
| Decisión agéntica | No | Sí — Refiner→Validator→Planner vía reescritura + tool-calling (ADR-0005, ADR-0006) |
| Aprendizaje del sistema | No | Memoria in-context de correcciones pasadas (few-shot, sin fine-tuning) |
| Evaluación | Manual | RAGAS + benchmark comparable por modo/modelo |
| Prompt | Soporte técnico | Citas normativas, no inventa |
| Disclaimer | No | Sí (respuestas orientativas) |
| Carpetas datos | `manuals/` (fija) | Subcarpetas dinámicas de `data/` |
| Puerto Gradio | 7864 | 7865 |
| Colección ChromaDB | `manual_tecnico` | `normativa_tributaria` |
