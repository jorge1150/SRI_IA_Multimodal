"""
log_agent.py — Agente de Trazabilidad y Logs
Registra cada etapa del pipeline con timestamp, nivel y stage.
Thread-safe para uso concurrente.

Este módulo es el DUEÑO del vocabulario de etapas (clase Stage): todos los
productores (coordinator, planner, retrievers, agentes de media) referencian
Stage.X en vez de literales, y los consumidores máquina (íconos, diagrama de
flujo de agentes en ui/interface.py) se cuelgan de las mismas constantes.
Renombrar una etapa = cambiar una línea acá; un typo en un productor falla
con AttributeError visible, no con degradación silenciosa.
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


class Stage:
    """Vocabulario único de etapas del pipeline (strings planos — compatibles
    con cualquier consumidor que espere str)."""
    INICIO      = "INICIO"
    STT         = "STT"
    VISION      = "VISION"
    VIDEO       = "VIDEO"
    PLANNER     = "PLANNER"
    RAG         = "RAG"
    GRAPH       = "GRAPH"
    NORMATIVA   = "NORMATIVA"
    GENERANDO   = "GENERANDO"
    RESPUESTA   = "RESPUESTA"
    TTS         = "TTS"
    FIN         = "FIN"
    ERROR       = "ERROR"
    INFO        = "INFO"
    ADVERTENCIA = "ADVERTENCIA"


class LogAgent:
    """
    Agente de logs con tres destinos:
      1. Lista de texto en memoria (para el panel de logs de Gradio).
      2. Archivo en disco (para auditoría académica).
      3. Lista de eventos estructurados (stage, message, timestamp) — la
         consume el diagrama de flujo de agentes sin re-parsear texto.
    """

    _STAGE_ICONS = {
        Stage.INICIO:      "🚀",
        Stage.STT:         "🎤",
        Stage.VISION:      "👁️",
        Stage.VIDEO:       "🎬",
        Stage.PLANNER:     "🧠",
        Stage.RAG:         "📋",
        Stage.GRAPH:       "🕸️",
        Stage.NORMATIVA:   "⚖️",
        Stage.GENERANDO:   "🤖",
        Stage.RESPUESTA:   "💬",
        Stage.TTS:         "🔊",
        Stage.FIN:         "✅",
        Stage.ERROR:       "❌",
        Stage.INFO:        "ℹ️",
        Stage.ADVERTENCIA: "⚠️",
    }

    def __init__(self):
        self._entries: list[str] = []
        self._events: list[dict] = []
        self._lock = threading.Lock()

    def log(self, stage: str, message: str) -> str:
        ts = datetime.now().strftime("%H:%M:%S")
        icon = self._STAGE_ICONS.get(stage.upper(), "•")
        entry = f"[{ts}] {icon} [{stage}] {message}"
        with self._lock:
            self._entries.append(entry)
            self._events.append({"stage": stage.upper(), "message": message, "timestamp": ts})
        _file_logger.info("[%s] %s", stage, message)
        return entry

    def get_all(self) -> str:
        with self._lock:
            return "\n".join(self._entries)

    def get_events(self) -> list[dict]:
        """Snapshot de los eventos estructurados de la consulta en curso."""
        with self._lock:
            return list(self._events)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self._events.clear()

    def last(self) -> str:
        with self._lock:
            return self._entries[-1] if self._entries else ""
