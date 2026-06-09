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
│              LLM (TinyLlama via Ollama)                         │
│  Prompt: normativa RAG + relaciones de grafo → respuesta        │
└────────────────────────┬────────────────────────────────────────┘
                         ↓
              🔊 Piper TTS → Respuesta en voz
```

## Stack Tecnológico

| Componente | Tecnología |
|---|---|
| Interfaz | Gradio 6.x |
| LLM | TinyLlama via Ollama |
| Visión | Moondream via Ollama |
| STT | faster-whisper (base) |
| Embeddings | OpenCLIP ViT-B-32 |
| Vector DB | ChromaDB (cosine) |
| Grafo conocimiento | NetworkX DiGraph + JSON |
| Recuperación híbrida | HybridRetriever (RAG + GraphRAG) |
| TTS | Piper TTS es_ES-sharvard |
| PDF | PyMuPDF (fitz) |
| DOCX | python-docx |

## Estructura del Proyecto

```
SRI_IA_Multimodal/
├── app.py                      # Punto de entrada
├── config.py                   # Configuración central (incl. GRAPH_ENABLED)
├── requirements.txt
├── setup.sh
│
├── agents/                     # Sistema multiagente
│   ├── coordinator.py          # Orquestador del pipeline (usa HybridRetriever)
│   ├── rag_agent.py            # Recuperación semántica vectorial
│   ├── response_agent.py       # Generación con citas (acepta graph_context)
│   ├── voice_agent.py          # STT (Whisper)
│   ├── vision_agent.py         # Análisis visual (Moondream)
│   ├── video_agent.py          # Procesamiento de video
│   ├── tts_agent.py            # Síntesis de voz (Piper)
│   └── log_agent.py            # Trazabilidad
│
├── rag/                        # Motor RAG vectorial
│   ├── chunker.py              # Fragmentación PDF/DOCX/TXT/MD
│   ├── ingesta.py              # Carga a ChromaDB con metadatos
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
│   └── hybrid_retriever.py     # RAG vectorial + GraphRAG combinados
│
├── scripts/                    # Scripts CLI
│   └── build_graph.py          # Construir grafo: python scripts/build_graph.py
│
├── ui/                         # Interfaz Gradio
│   ├── interface.py            # Layout, panel RAG, eventos
│   └── styles.py               # CSS tema SRI (dark + Ecuador colors)
│
├── data/                       # Documentos normativos SRI
│   ├── normativas_sri/         # LORTI, Código Tributario, Reglamentos
│   ├── resoluciones/           # Resoluciones NAC del SRI
│   ├── guias_tributarias/      # Guías de declaración, RUC, comprobantes
│   └── formularios/            # Instructivos de formularios 104, 101, etc.
│
├── vector_db/chroma_sri/       # Base vectorial ChromaDB (generada)
├── graph_db/sri_graph.json     # Grafo de conocimiento (generado)
├── outputs/respuestas_audio/   # Audio generado
├── outputs/logs/               # Logs de sesión
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

# 3. Dependencias (incluye networkx para GraphRAG)
pip install -r requirements.txt

# 4. Modelos Ollama
ollama pull tinyllama
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

```bash
# Copiar documentos en las carpetas correspondientes:
data/normativas_sri/     → LORTI, Código Tributario, Reglamento Aplicación LORTI
data/resoluciones/       → Resoluciones NAC-DGERCGC del SRI
data/guias_tributarias/  → Guías oficiales del SRI
data/formularios/        → Instructivos de formularios

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
2. [STT]    Whisper transcribe audio → texto
3. [VISION] Moondream describe imagen → contexto visual
4. [HYBRID] HybridRetriever ejecuta en paralelo:
   4a. [RAG]    OpenCLIP vectoriza consulta → ChromaDB similitud coseno
   4b. [GRAPH]  EntityExtractor detecta entidades (IVA, RUC, RISE, ...)
               GraphRetriever explora relaciones en NetworkX (hop_depth=2)
               → Triples: "Contribuyente —debe_presentar→ Declaración IVA"
5. [LLM]   TinyLlama recibe: fragmentos RAG + relaciones de grafo
           → Respuesta con citas de fuente normativa
6. [TTS]   Piper sintetiza respuesta en español
7. [LOGS]  Trazabilidad completa: modo hybrid/vector_only, entidades, triples
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

## Notas Importantes

> Las respuestas son orientativas e informativas. No constituyen asesoría legal
> ni tributaria definitiva. Verificar siempre en [sri.gob.ec](https://sri.gob.ec)
> o consultar con un profesional tributario.

## Tests

```bash
# Todos los tests
python -m pytest tests/ -v

# Solo GraphRAG
python -m pytest tests/test_graph.py -v

# Solo agentes/RAG
python -m pytest tests/test_agents.py tests/test_rag.py -v
```

## Diferencias con S3 IA Multimodal (Proyecto Base)

| Aspecto | S3 IA Multimodal | SRI IA Multimodal |
|---|---|---|
| Dominio | Soporte técnico PC | Normativa tributaria SRI |
| Documentos | TXT manuales técnicos | PDF/DOCX/TXT normativos |
| Metadatos RAG | source, id | + tipo, año, artículo, página |
| Recuperación | RAG vectorial | RAG vectorial + GraphRAG híbrido |
| Grafo conocimiento | No | Sí (NetworkX + JSON, 100% local) |
| Prompt | Soporte técnico | Citas normativas, no inventa |
| Disclaimer | No | Sí (respuestas orientativas) |
| Carpetas datos | `manuals/` | `data/normativas_sri/`, etc. |
| Puerto Gradio | 7864 | 7865 |
| Colección ChromaDB | `manual_tecnico` | `normativa_tributaria` |
