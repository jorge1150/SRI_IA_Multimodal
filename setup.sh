#!/bin/bash
# setup.sh — Instalación automática del SRI IA Multimodal
# Uso: bash setup.sh

set -e

echo "════════════════════════════════════════════════════════"
echo "  SRI IA MULTIMODAL — Instalación automática"
echo "  Asistente RAG Normativa Tributaria SRI Ecuador"
echo "════════════════════════════════════════════════════════"
echo ""

# Verificar Python 3.12
if ! /usr/local/bin/python3.12 --version &>/dev/null; then
    echo "[ERROR] Python 3.12 no encontrado en /usr/local/bin/python3.12"
    echo "  Instala con: brew install python@3.12"
    exit 1
fi

echo "[1/6] Creando entorno virtual Python 3.12..."
/usr/local/bin/python3.12 -m venv venv
source venv/bin/activate

echo "[2/6] Verificando PortAudio (requerido para micrófono)..."
if ! brew list portaudio &>/dev/null; then
    echo "  Instalando portaudio con Homebrew..."
    brew install portaudio
else
    echo "  PortAudio ya instalado."
fi

echo "[3/6] Instalando dependencias Python..."
pip install --upgrade pip
pip install -r requirements.txt

echo "[4/6] Verificando Ollama..."
if ! command -v ollama &>/dev/null; then
    echo "  [ADVERTENCIA] Ollama no encontrado."
    echo "  Instala desde: https://ollama.com"
    echo "  O con: brew install ollama"
else
    echo "  Ollama encontrado: $(ollama --version)"
    echo ""
    echo "  Descargando modelos LLM (puede tardar varios minutos)..."
    ollama pull tinyllama
    ollama pull moondream
fi

echo "[5/6] Descargando modelo Piper TTS (voz española)..."
python audio/download_piper.py

echo "[6/6] Los documentos de demo SRI ya están cargados en data/"
echo "  Construyendo base vectorial de normativa tributaria..."
python rag/build_db.py

echo ""
echo "════════════════════════════════════════════════════════"
echo "  ✅ Instalación completada."
echo ""
echo "  Para iniciar el asistente SRI:"
echo "    source venv/bin/activate"
echo "    ollama serve  (en otra terminal)"
echo "    python app.py"
echo ""
echo "  Interfaz: http://localhost:7865"
echo "════════════════════════════════════════════════════════"
