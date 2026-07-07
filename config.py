"""
config.py — Configuración central del proyecto SRI IA Multimodal
Toda constante del sistema vive aquí.
"""

import os
import torch


# ─────────────────────────────────────────────
# DISPOSITIVO DE CÓMPUTO
# ─────────────────────────────────────────────
def _detect_device() -> str:
    import platform
    if torch.cuda.is_available():
        return "cuda"
    if (platform.machine() == "arm64"
            and hasattr(torch.backends, "mps")
            and torch.backends.mps.is_available()):
        return "mps"
    return "cpu"


DEVICE: str = _detect_device()
WHISPER_COMPUTE_TYPE: str = "float16" if DEVICE == "cuda" else "int8"

# ─────────────────────────────────────────────
# OLLAMA
# ─────────────────────────────────────────────
OLLAMA_HOST: str = "localhost"
OLLAMA_PORT: int = 11434
OLLAMA_URL: str = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}"
OLLAMA_TIMEOUT: int = 180

LLM_MODEL: str = "qwen2.5:3b-instruct-q4_K_M"
VISION_MODEL: str = "moondream"
LLM_TEMPERATURE: float = 0.1

# ─────────────────────────────────────────────
# WHISPER STT (faster-whisper)
# ─────────────────────────────────────────────
WHISPER_MODEL_SIZE: str = "base"
WHISPER_BEAM_SIZE: int = 5
WHISPER_LANGUAGE: str = "es"

# ─────────────────────────────────────────────
# AUDIO
# ─────────────────────────────────────────────
SAMPLE_RATE_RECORD: int = 48000
SAMPLE_RATE_WHISPER: int = 16000
RECORD_DURATION: int = 5
AUDIO_SAFETY_CEILING: float = 0.9
MIC_DEVICE_INDEX = None
OUTPUT_DEVICE_INDEX = None

# ─────────────────────────────────────────────
# OPENCLIP — Embeddings para RAG
# ─────────────────────────────────────────────
CLIP_MODEL: str = "hf-hub:timm/vit_base_patch32_clip_224.openai"
CLIP_PRETRAINED: str = ""
CLIP_EMBEDDING_DIM: int = 512
CLIP_MAX_TOKENS: int = 200

# ─────────────────────────────────────────────
# CHROMADB — Base vectorial SRI
# ─────────────────────────────────────────────
BASE_DIR: str = os.path.dirname(os.path.abspath(__file__))
CHROMA_DB_PATH: str = os.path.join(BASE_DIR, "vector_db", "chroma_sri")
CHROMA_COLLECTION: str = "normativa_tributaria"
# Tiempo acumulado de construcción del vector store (ver rag/ingesta.py),
# mismo patrón que build_seconds en graph_db/sri_graph.json.
VECTOR_BUILD_METADATA_PATH: str = os.path.join(BASE_DIR, "vector_db", "build_metadata.json")
RAG_TOP_K: int = 4
RAG_MIN_SIMILARITY: float = 0.18

# ─────────────────────────────────────────────
# PIPER TTS
# ─────────────────────────────────────────────
PIPER_MODELS_DIR: str = os.path.join(BASE_DIR, "audio", "piper_models")
PIPER_MODEL_NAME: str = "es_ES-sharvard-medium"
PIPER_MODEL_PATH: str = os.path.join(PIPER_MODELS_DIR, "es_ES-sharvard-medium.onnx")
PIPER_CONFIG_PATH: str = os.path.join(PIPER_MODELS_DIR, "es_ES-sharvard-medium.onnx.json")
TTS_SAMPLE_RATE: int = 22050

# ─────────────────────────────────────────────
# VISIÓN — Prompt para formularios y portal SRI
# ─────────────────────────────────────────────
VISION_TIMEOUT: int = 180
# Cualquier instrucción de longitud en el texto del prompt ("Be concise",
# "in one sentence", "maximum N words") hace que Moondream corte a 1 token
# (respuesta vacía, eval_count=1, 100% reproducible con Ollama) — se limita
# la longitud con num_predict (parámetro de la API) en vez de en el prompt.
MOONDREAM_PROMPT: str = (
    "Describe what is shown in this image. "
    "It may be a tax form, web portal screenshot, electronic invoice, "
    "tax declaration, or government system screen."
)
MOONDREAM_NUM_PREDICT: int = 100

# ─────────────────────────────────────────────
# VIDEO
# ─────────────────────────────────────────────
VIDEO_FRAME_INTERVAL: int = 30
VIDEO_MAX_FRAMES: int = 2

# ─────────────────────────────────────────────
# RUTAS DEL SISTEMA — Documentos SRI
# ─────────────────────────────────────────────
DATA_DIR: str = os.path.join(BASE_DIR, "data")

OUTPUTS_DIR: str = os.path.join(BASE_DIR, "outputs")
AUDIO_OUTPUT_DIR: str = os.path.join(OUTPUTS_DIR, "respuestas_audio")
LOGS_DIR: str = os.path.join(OUTPUTS_DIR, "logs")
TEMP_DIR: str = os.path.join(BASE_DIR, "temp")

# Nombres de subcarpeta de data/ que no son categorías de normativa.
_DATA_DIR_EXCLUDE = {"output"}


def get_data_dirs() -> list:
    """
    Descubre las categorías de normativa como subcarpetas directas de data/
    (sin recursividad, sin ocultas, sin "output"). El nombre de cada carpeta
    es directamente el tipo_normativa del chunk — no hay tabla de mapeo:
    renombrar/agregar una carpeta cambia la categoría sin tocar código.
    """
    if not os.path.isdir(DATA_DIR):
        return []
    dirs = []
    for name in sorted(os.listdir(DATA_DIR)):
        if name.startswith(".") or name in _DATA_DIR_EXCLUDE:
            continue
        full = os.path.join(DATA_DIR, name)
        if os.path.isdir(full):
            dirs.append(full)
    return dirs

# ─────────────────────────────────────────────
# MinerU — parseo avanzado de PDF (tablas, OCR, layout)
# ─────────────────────────────────────────────
# MinerU[pipeline] fuerza numpy>=2 / opencv>=2, incompatible con
# torch==2.2.2 (requiere numpy<2) que usa el resto del proyecto.
# Por eso vive en su propio venv (venv_mineru/), no en venv/, y con
# opencv-python==4.11.0.86 (última compatible con numpy<2, ver setup abajo).
# Setup:
#   python3.12 -m venv venv_mineru
#   venv_mineru/bin/pip install "mineru[pipeline]"
#   venv_mineru/bin/pip install "numpy<2" "opencv-python==4.11.0.86" \
#       "opencv-python-headless==4.11.0.86" "scipy<1.14"
# Default true (ADR-0001): MinerU es el backend por defecto sobre el corpus
# de tesis. Desactivar con: export USE_MINERU_PDF=false
USE_MINERU_PDF: bool = os.getenv("USE_MINERU_PDF", "true").lower() == "true"
MINERU_BIN: str = os.path.join(BASE_DIR, "venv_mineru", "bin", "mineru")
MINERU_BACKEND: str = "pipeline"
# Este Mac es Intel x86_64: MPS (Metal) se detecta pero torchvision::nms y
# bfloat16 no están implementados ahí para los modelos de MinerU → forzar CPU.
MINERU_DEVICE: str = "cpu"
MINERU_TIMEOUT: int = 600  # segundos, PDFs largos con tablas tardan

# ─────────────────────────────────────────────
# GRADIO
# ─────────────────────────────────────────────
GRADIO_PORT: int = 7865
GRADIO_SERVER: str = "0.0.0.0"
GRADIO_TITLE: str = "SRI IA Multimodal — Asistente Normativa Tributaria Ecuador"

# ─────────────────────────────────────────────
# GRAPHRAG — Grafo de conocimiento tributario
# ─────────────────────────────────────────────
GRAPH_ENABLED: bool = True          # True = usa RAG híbrido (vector + grafo)
GRAPH_DB_PATH: str = os.path.join(BASE_DIR, "graph_db", "sri_graph.json")
GRAPH_TOP_K_TRIPLES: int = 10       # máx triples a retornar por consulta
GRAPH_HOP_DEPTH: int = 2            # saltos de exploración en el grafo (1 ó 2)
GRAPH_MIN_WEIGHT: float = 0.4       # peso mínimo de relación para incluir

# ─────────────────────────────────────────────
# PLANNER AGENT — decisión agéntica de estrategia de retrieval
# ─────────────────────────────────────────────
# Decisión binaria vía tool-calling de Ollama: ¿esta consulta necesita
# GraphRAG además del RAG vectorial (que siempre corre)? Default False:
# el chat de producción sigue con el modo "auto" fijo de HybridRetriever
# hasta validar la confiabilidad del planner con scripts/run_benchmark.py.
USE_AGENTIC_PLANNER: bool = os.getenv("USE_AGENTIC_PLANNER", "false").lower() == "true"
# Corto a propósito: es una decisión de pocos tokens, no una generación
# completa de 400 tokens (ver OLLAMA_TIMEOUT).
PLANNER_TIMEOUT: int = 30

# ─────────────────────────────────────────────
# CREAR DIRECTORIOS NECESARIOS EN IMPORTACIÓN
# ─────────────────────────────────────────────
for _d in [
    LOGS_DIR, TEMP_DIR, PIPER_MODELS_DIR, AUDIO_OUTPUT_DIR,
    os.path.dirname(CHROMA_DB_PATH),
    DATA_DIR,
    os.path.dirname(GRAPH_DB_PATH),
]:
    os.makedirs(_d, exist_ok=True)
