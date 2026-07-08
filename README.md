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
│  🧠 PLANNER AGENT (opcional, USE_AGENTIC_PLANNER)               │
│  Decide vía tool-calling de Ollama: ¿esta consulta necesita     │
│  GraphRAG además del RAG vectorial? Único punto del pipeline    │
│  donde el LLM decide dinámicamente, no una regla fija (ADR-0005)│
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
> pulsando y el Planner marcado como el único punto de decisión real.

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
4. [PLANNER] (si USE_AGENTIC_PLANNER=True) el LLM decide vía tool-calling
             si esta consulta necesita GraphRAG además del RAG vectorial
5. [HYBRID]  HybridRetriever ejecuta según el modo (auto o el decidido por el planner):
   5a. [RAG]    OpenCLIP vectoriza consulta → ChromaDB similitud coseno
   5b. [GRAPH]  EntityExtractor detecta entidades (IVA, RUC, RISE, ...)
               GraphRetriever explora relaciones en NetworkX (hop_depth=2)
               → Triples: "Contribuyente —debe_presentar→ Declaración IVA"
6. [LLM]    Qwen2.5 recibe: fragmentos RAG + relaciones de grafo
           → Respuesta con citas de fuente normativa
7. [TTS]    Piper sintetiza respuesta en español
8. [LOGS]   Trazabilidad completa: modo hybrid/vector_only, entidades, triples,
            decisión del planner — visible también como diagrama animado
            (botón "Ver Flujo de Agentes")
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

## PlannerAgent — Decisión Agéntica (ADR-0005)

El resto de agentes del sistema ejecutan una tarea fija — el `PlannerAgent` es
el único punto donde el LLM **decide** dinámicamente, en vez de seguir una
regla programada. Vía tool-calling nativo de Ollama, decide si una consulta
necesita GraphRAG además del RAG vectorial (que siempre corre):

```python
# config.py
USE_AGENTIC_PLANNER: bool = False   # default: chat de producción usa modo "auto" fijo
PLANNER_TIMEOUT: int = 30            # decisión corta, no una generación completa
```

```bash
# Activar para probarlo:
USE_AGENTIC_PLANNER=true python app.py
```

Con el planner activo, la tab "Consulta Tributaria" muestra un botón
**"🕸️ Ver Flujo de Agentes"** — diagrama animado en vivo que va marcando qué
agente está trabajando en cada momento del pipeline, con el nodo del Planner
distinguido visualmente como el único punto de decisión real (borde punteado).

Ante cualquier falla (Ollama caído, timeout, respuesta sin parsear) el planner
degrada a `False` — solo RAG vectorial, mismo criterio de degradación segura
que ya usa el sistema cuando el grafo no está disponible.

**Limitación conocida** (documentada, no oculta): un modelo de 3B tiene sesgo
hacia elegir "no usar grafo" incluso en preguntas donde ayudaría — por eso la
decisión se validó empíricamente con `scripts/run_benchmark.py` antes de
considerar activarlo por defecto (ver sección Benchmark abajo).

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

**Nota de compatibilidad:** RAGAS/`sentence-transformers` requieren versiones
específicas fijadas en `requirements.txt` — las últimas versiones de esas
librerías arrastran dependencias incompatibles entre sí y con `torch==2.2.2`
(pinneado por MinerU/OpenCLIP). Ver comentario en `requirements.txt`.

## Notas Importantes

> Las respuestas son orientativas e informativas. No constituyen asesoría legal
> ni tributaria definitiva. Verificar siempre en [sri.gob.ec](https://sri.gob.ec)
> o consultar con un profesional tributario.

## Tests

Suite completa en verde (99 tests): chunker MinerU-aware, GraphRAG,
PlannerAgent (con fallbacks mockeados), HybridRetriever (todos los modos),
fuentes estructuradas, diagrama de flujo de agentes, rutas de error de
visión y helpers del benchmark.

```bash
# Todos los tests
python -m pytest tests/ -v

# Solo GraphRAG
python -m pytest tests/test_graph.py -v

# Solo agentes/RAG (incluye PlannerAgent, visión, fuentes, diagrama de flujo)
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
| Decisión agéntica | No | Sí — PlannerAgent vía tool-calling (ADR-0005) |
| Evaluación | Manual | RAGAS + benchmark comparable por modo/modelo |
| Prompt | Soporte técnico | Citas normativas, no inventa |
| Disclaimer | No | Sí (respuestas orientativas) |
| Carpetas datos | `manuals/` (fija) | Subcarpetas dinámicas de `data/` |
| Puerto Gradio | 7864 | 7865 |
| Colección ChromaDB | `manual_tecnico` | `normativa_tributaria` |
