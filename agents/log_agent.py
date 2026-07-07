"""
log_agent.py — Agente de Trazabilidad y Logs
Registra cada etapa del pipeline con timestamp, nivel y stage.
Thread-safe para uso concurrente.
"""

import threading
import logging
import os
from datetime import datetime
from config import LOGS_DIR

logging.basicConfig(
    filename=os.path.join(LOGS_DIR, "sri_system.log"),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
_file_logger = logging.getLogger("sri_multimodal")


class LogAgent:
    """
    Agente de logs con dos destinos:
      1. Lista en memoria (para Gradio en tiempo real).
      2. Archivo en disco (para auditoría académica).
    """

    _STAGE_ICONS = {
        "INICIO":           "🚀",
        "STT":              "🎤",
        "VISION":           "👁️",
        "VIDEO":            "🎬",
        "PLANNER":          "🧠",
        "RAG":              "📋",
        "GRAPH":            "🕸️",
        "NORMATIVA":        "⚖️",
        "GENERANDO":        "🤖",
        "RESPUESTA":        "💬",
        "TTS":              "🔊",
        "FIN":              "✅",
        "ERROR":            "❌",
        "INFO":             "ℹ️",
        "ADVERTENCIA":      "⚠️",
    }

    def __init__(self):
        self._entries: list[str] = []
        self._lock = threading.Lock()

    def log(self, stage: str, message: str) -> str:
        ts = datetime.now().strftime("%H:%M:%S")
        icon = self._STAGE_ICONS.get(stage.upper(), "•")
        entry = f"[{ts}] {icon} [{stage}] {message}"
        with self._lock:
            self._entries.append(entry)
        _file_logger.info("[%s] %s", stage, message)
        return entry

    def get_all(self) -> str:
        with self._lock:
            return "\n".join(self._entries)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def last(self) -> str:
        with self._lock:
            return self._entries[-1] if self._entries else ""
