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

LLM_MODEL: str = "tinyllama"
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
MOONDREAM_PROMPT: str = (
    "Describe what is shown in this image. "
    "It may be a tax form, web portal screenshot, electronic invoice, "
    "tax declaration, or government system screen. "
    "Be concise, maximum 40 words."
)

# ─────────────────────────────────────────────
# VIDEO
# ─────────────────────────────────────────────
VIDEO_FRAME_INTERVAL: int = 30
VIDEO_MAX_FRAMES: int = 2

# ─────────────────────────────────────────────
# RUTAS DEL SISTEMA — Documentos SRI
# ─────────────────────────────────────────────
DATA_DIR: str = os.path.join(BASE_DIR, "data")
NORMATIVAS_DIR: str = os.path.join(DATA_DIR, "normativas_sri")
RESOLUCIONES_DIR: str = os.path.join(DATA_DIR, "resoluciones")
GUIAS_DIR: str = os.path.join(DATA_DIR, "guias_tributarias")
FORMULARIOS_DIR: str = os.path.join(DATA_DIR, "formularios")

OUTPUTS_DIR: str = os.path.join(BASE_DIR, "outputs")
AUDIO_OUTPUT_DIR: str = os.path.join(OUTPUTS_DIR, "respuestas_audio")
LOGS_DIR: str = os.path.join(OUTPUTS_DIR, "logs")
TEMP_DIR: str = os.path.join(BASE_DIR, "temp")

# Mapeo directorio → tipo de normativa (para metadatos RAG)
TIPO_BY_FOLDER: dict = {
    "normativas_sri": "Ley / Normativa",
    "resoluciones": "Resolución SRI",
    "guias_tributarias": "Guía Tributaria",
    "formularios": "Formulario SRI",
}

# Todos los directorios de documentos SRI
ALL_DATA_DIRS: list = [NORMATIVAS_DIR, RESOLUCIONES_DIR, GUIAS_DIR, FORMULARIOS_DIR]

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
# CREAR DIRECTORIOS NECESARIOS EN IMPORTACIÓN
# ─────────────────────────────────────────────
for _d in [
    LOGS_DIR, TEMP_DIR, PIPER_MODELS_DIR, AUDIO_OUTPUT_DIR,
    os.path.dirname(CHROMA_DB_PATH),
    NORMATIVAS_DIR, RESOLUCIONES_DIR, GUIAS_DIR, FORMULARIOS_DIR,
    os.path.dirname(GRAPH_DB_PATH),
]:
    os.makedirs(_d, exist_ok=True)
