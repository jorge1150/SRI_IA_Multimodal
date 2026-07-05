"""
app.py — Punto de entrada principal del sistema SRI IA Multimodal.

Uso:
    python app.py

El sistema arranca en http://localhost:7865
"""

import sys
import os
import faulthandler
faulthandler.enable()

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config


def check_ollama() -> bool:
    import requests
    try:
        r = requests.get(f"{config.OLLAMA_URL}/api/tags", timeout=5)
        models = [m["name"] for m in r.json().get("models", [])]
        print(f"[OK] Ollama activo. Modelos: {models}")
        missing = []
        for model in [config.LLM_MODEL, config.VISION_MODEL]:
            if not any(model in m for m in models):
                missing.append(model)
        if missing:
            print(f"\n[ADVERTENCIA] Modelos faltantes: {missing}")
            for m in missing:
                print(f"  Instalar con: ollama pull {m}")
            print()
        return True
    except Exception:
        print(f"[ERROR] Ollama no está ejecutándose en {config.OLLAMA_URL}")
        print("  Inicialo con: ollama serve")
        return False


def check_vector_db() -> bool:
    import chromadb
    try:
        client = chromadb.PersistentClient(path=config.CHROMA_DB_PATH)
        col = client.get_collection(config.CHROMA_COLLECTION)
        count = col.count()
        print(f"[OK] ChromaDB lista: {count} fragmentos normativos en '{config.CHROMA_COLLECTION}'")
        return count > 0
    except Exception:
        print("[ADVERTENCIA] Base vectorial vacía o inexistente.")
        print("  Carga documentos en data/ y ejecuta: python rag/build_db.py")
        return False


def check_documents() -> int:
    """Cuenta documentos disponibles en todas las carpetas de datos."""
    import glob
    total = 0
    for data_dir in config.get_data_dirs():
        for ext in ("*.pdf", "*.txt", "*.docx", "*.md"):
            total += len(glob.glob(os.path.join(data_dir, ext)))
    return total


def print_banner():
    print("""
╔══════════════════════════════════════════════════════════════════╗
║   SRI IA MULTIMODAL — ASISTENTE NORMATIVA TRIBUTARIA ECUADOR     ║
║   Ollama + ChromaDB + Whisper + Moondream + Piper TTS            ║
╠══════════════════════════════════════════════════════════════════╣
║  Maestría IA Aplicada — UIsrael                                  ║
║  Tema: RAG Multimodal para Normativa Tributaria SRI Ecuador      ║
╚══════════════════════════════════════════════════════════════════╝
""")


def main():
    print_banner()
    print(f"[INFO] Dispositivo de cómputo: {config.DEVICE}")
    print(f"[INFO] Puerto Gradio: {config.GRADIO_PORT}")
    print()

    ollama_ok = check_ollama()
    db_ok = check_vector_db()
    n_docs = check_documents()
    print(f"[INFO] Documentos SRI disponibles en data/: {n_docs}")
    print()

    if not db_ok and n_docs > 0:
        print("[INFO] Construyendo base vectorial desde documentos SRI...")
        from rag.ingesta import ingest_all_documents
        n = ingest_all_documents()
        print(f"[OK] Base vectorial construida: {n} fragmentos normativos.\n")
    elif not db_ok and n_docs == 0:
        print("[ADVERTENCIA] No hay documentos SRI en data/.")
        print("  Copia PDFs, TXTs o DOCXs en una subcarpeta de data/ — el nombre")
        print("  de la carpeta se usa como tipo de normativa (ej. data/IVA/...).")
        print("  Luego ejecuta: python rag/build_db.py")
        print()

    print("[INFO] Inicializando agentes...")
    from agents.coordinator import CoordinatorAgent
    coordinator = CoordinatorAgent()
    print("[OK] Sistema multiagente listo.\n")

    from ui.interface import build_interface
    demo = build_interface(coordinator)

    print(f"[INFO] Iniciando interfaz en http://localhost:{config.GRADIO_PORT}")
    print("[INFO] Presiona Ctrl+C para detener el sistema.\n")

    from ui.interface import GRADIO_THEME
    import config as _cfg
    demo.launch(
        server_name=_cfg.GRADIO_SERVER,
        server_port=_cfg.GRADIO_PORT,
        share=False,
        inbrowser=False,
        theme=GRADIO_THEME,
        allowed_paths=[_cfg.TEMP_DIR],
    )


if __name__ == "__main__":
    main()
