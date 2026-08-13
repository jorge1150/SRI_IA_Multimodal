# Dockerfile — SRI IA Multimodal
#
# Imagen de la app (Gradio + agentes + RAG + GraphRAG + STT/TTS).
# NO incluye MinerU (requiere numpy>=2/opencv>=2, incompatible con
# torch==2.2.2 de aquí — ver comentario en config.py y requirements.txt).
# Para ingesta con MinerU usar Dockerfile.mineru en la VM de ingesta
# (ver docs/adr/0014-despliegue-cloud-azure.md).
#
# Build:  docker build -t sri-ia-multimodal .
# Run:    ver docker-compose.yml (necesita el servicio `ollama` para
#         moondream/LLM local y, para el modelo cloud, `ollama signin`
#         corrido una vez dentro del volumen persistente de ese servicio).

FROM python:3.12-slim

# Dependencias de sistema:
# - libportaudio2: requerido para importar sounddevice aunque no haya
#   micrófono físico en el contenedor (el audio real llega desde el
#   navegador del usuario vía Gradio, no desde el dispositivo del server).
# - tesseract-ocr + spa: fallback OCR de bloques de imagen (ADR-0004).
# - libgl1 + libglib2.0-0: requeridos por opencv-python en runtime headless.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libportaudio2 \
    tesseract-ocr \
    tesseract-ocr-spa \
    libgl1 \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

# Modelo Piper TTS se descarga en build para no depender de red en runtime.
RUN python audio/download_piper.py || true

ENV GRADIO_ANALYTICS_ENABLED=False \
    KMP_DUPLICATE_LIB_OK=TRUE \
    OMP_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    PYTHONUNBUFFERED=1

EXPOSE 7865

CMD ["python", "app.py"]
