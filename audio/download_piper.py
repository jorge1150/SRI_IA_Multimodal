"""
download_piper.py — Descarga el modelo Piper TTS es_ES-sharvard-medium.

Uso: python audio/download_piper.py
"""

import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import PIPER_MODELS_DIR, PIPER_MODEL_NAME

BASE_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_ES/sharvard/medium"
FILES = [
    f"{PIPER_MODEL_NAME}.onnx",
    f"{PIPER_MODEL_NAME}.onnx.json",
]


def download_file(url: str, dest: str):
    print(f"Descargando: {os.path.basename(dest)}")

    def progress(block_num, block_size, total_size):
        downloaded = block_num * block_size
        if total_size > 0:
            pct = min(100, downloaded * 100 // total_size)
            bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
            print(f"\r  [{bar}] {pct}%  ", end="", flush=True)

    urllib.request.urlretrieve(url, dest, reporthook=progress)
    print(f"\n  ✓ Guardado en: {dest}")


def main():
    os.makedirs(PIPER_MODELS_DIR, exist_ok=True)
    print(f"\nDescargando modelo Piper TTS: {PIPER_MODEL_NAME}")
    print(f"Destino: {PIPER_MODELS_DIR}\n")
    for filename in FILES:
        dest = os.path.join(PIPER_MODELS_DIR, filename)
        if os.path.exists(dest):
            print(f"  ✓ Ya existe: {filename}")
            continue
        url = f"{BASE_URL}/{filename}"
        try:
            download_file(url, dest)
        except Exception as e:
            print(f"\n  ✗ Error: {e}")
            print(f"  Descarga manual: {url}")
    print("\n✓ Modelo Piper TTS listo para el asistente SRI.")


if __name__ == "__main__":
    main()
