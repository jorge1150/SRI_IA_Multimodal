# SRI IA Multimodal

**Asistente Virtual Basado en Generación Aumentada por Recuperación Multimodal para la Gestión Dinámica de la Normativa Tributaria del Servicio de Rentas Internas en Ecuador**

Maestría en Inteligencia Artificial Aplicada · UIsrael  

---

## Descripción

Sistema multimodal 100% local que responde consultas sobre normativa tributaria del SRI Ecuador. Combina RAG (Retrieval-Augmented Generation), modelos de lenguaje locales, reconocimiento de voz, análisis visual y síntesis de voz para ofrecer respuestas citando la fuente normativa específica.

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
│               RAG — RECUPERACIÓN NORMATIVA                      │
│  OpenCLIP → Vector  →  ChromaDB  →  Fragmentos Normativos      │
│  Metadatos: doc_name | tipo | año | artículo | página          │
└────────────────────────┬────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│              LLM (TinyLlama via Ollama)                         │
│  Prompt con normativa recuperada → Respuesta con citas         │
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
| TTS | Piper TTS es_ES-sharvard |
| PDF | PyMuPDF (fitz) |
| DOCX | python-docx |

## Estructura del Proyecto

```
SRI_IA_Multimodal/
├── app.py                      # Punto de entrada
├── config.py                   # Configuración central
├── requirements.txt
├── setup.sh
│
├── agents/                     # Sistema multiagente
│   ├── coordinator.py          # Orquestador del pipeline
│   ├── rag_agent.py            # Recuperación semántica
│   ├── response_agent.py       # Generación con citas
│   ├── voice_agent.py          # STT (Whisper)
│   ├── vision_agent.py         # Análisis visual (Moondream)
│   ├── video_agent.py          # Procesamiento de video
│   ├── tts_agent.py            # Síntesis de voz (Piper)
│   └── log_agent.py            # Trazabilidad
│
├── rag/                        # Motor RAG
│   ├── chunker.py              # Fragmentación PDF/DOCX/TXT/MD
│   ├── ingesta.py              # Carga a ChromaDB con metadatos
│   └── build_db.py             # Script de construcción
│
├── ui/                         # Interfaz Gradio
│   ├── interface.py            # Layout y eventos
│   └── styles.py               # CSS tema SRI
│
├── data/                       # Documentos normativos SRI
│   ├── normativas_sri/         # LORTI, Código Tributario, Reglamentos
│   ├── resoluciones/           # Resoluciones NAC del SRI
│   ├── guias_tributarias/      # Guías de declaración, RUC, comprobantes
│   └── formularios/            # Instructivos de formularios 104, 101, etc.
│
├── vector_db/chroma_sri/       # Base vectorial (generada)
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

# 3. Dependencias
pip install -r requirements.txt

# 4. Modelos Ollama
ollama pull tinyllama
ollama pull moondream

# 5. Voz Piper
python audio/download_piper.py

# 6. Base vectorial (documentos demo incluidos)
python rag/build_db.py

# 7. Iniciar
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

## Flujo RAG Detallado

```
1. Usuario hace consulta (texto/voz/imagen)
2. [STT] Whisper transcribe audio → texto
3. [VISION] Moondream describe imagen → contexto visual
4. [RAG] OpenCLIP vectoriza consulta + contexto visual
5. [ChromaDB] Búsqueda por similitud coseno en normativa
6. [Reranking] Boost por palabras clave tributarias
7. [LLM] TinyLlama genera respuesta con citas de fuente
8. [TTS] Piper sintetiza respuesta en español ecuatoriano
9. [LOGS] Trazabilidad completa del proceso
```

## Notas Importantes

> Las respuestas son orientativas e informativas. No constituyen asesoría legal
> ni tributaria definitiva. Verificar siempre en [sri.gob.ec](https://sri.gob.ec)
> o consultar con un profesional tributario.

## Diferencias con S3 IA Multimodal (Proyecto Base)

| Aspecto | S3 IA Multimodal | SRI IA Multimodal |
|---|---|---|
| Dominio | Soporte técnico PC | Normativa tributaria SRI |
| Documentos | TXT manuales técnicos | PDF/DOCX/TXT normativos |
| Metadatos RAG | source, id | + tipo, año, artículo, página |
| Prompt | Soporte técnico | Citas normativas, no inventa |
| Disclaimer | No | Sí (respuestas orientativas) |
| Carpetas datos | `manuals/` | `data/normativas_sri/`, etc. |
| Puerto Gradio | 7864 | 7865 |
| Colección ChromaDB | `manual_tecnico` | `normativa_tributaria` |
