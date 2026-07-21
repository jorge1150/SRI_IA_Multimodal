"""
off_topic_memory.py — Memoria de preguntas fuera de dominio ya detectadas
Guarda preguntas que QueryValidatorAgent identificó como completamente
ajenas a la normativa tributaria del SRI (ej. "¿qué clima hace hoy?").
Permite un fast-path: antes de gastar una llamada a Ollama, se compara la
consulta nueva contra las ya vistas — si es (casi) el mismo texto literal,
se corta directo con el mensaje fijo de fuera de dominio.

Match por TEXTO NORMALIZADO, no por embeddings — a diferencia de
RefinementMemory. Pruebas reales mostraron que OpenCLIP no discrimina
similitud semántica entre preguntas cortas en español: el mismo rango de
similitud coseno (~0.83-0.90) aparecía tanto entre parafraseos de la misma
pregunta como entre preguntas de temas completamente distintos (incluso
tributarias). Con un umbral bajo (heredado de RAG_MIN_SIMILARITY=0.18,
pensado para relevancia de chunks, no para "es la misma pregunta") una
sola entrada terminaba marcando CUALQUIER pregunta como fuera de dominio.
Ver ADR-0007.
"""

import difflib
import json
import os
import re
import unicodedata
from datetime import datetime

from config import OFF_TOPIC_MEMORY_PATH
from .log_agent import LogAgent, Stage

# Umbral alto a propósito: el objetivo es detectar la MISMA pregunta
# repetida con variaciones triviales (mayúsculas, tildes, puntuación,
# "?" final), no preguntas "parecidas" — eso es exactamente lo que
# rompía con similitud CLIP.
_NEAR_MATCH_THRESHOLD = 0.92


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", "", text)
    return re.sub(r"\s+", " ", text).strip()


class OffTopicMemory:
    """
    Persistencia simple en JSON (mismo espíritu que graph_db/sri_graph.json)
    de preguntas ya marcadas fuera de dominio. Nunca lanza: cualquier fallo
    de I/O degrada a memoria vacía.
    """

    def __init__(self, log_agent: LogAgent, path: str = None):
        self.log = log_agent
        self.path = path or OFF_TOPIC_MEMORY_PATH
        self._entries: list[dict] = self._load()

    def _load(self) -> list[dict]:
        if not os.path.exists(self.path):
            return []
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            self.log.log(Stage.VALIDADOR, f"⚠ No se pudo leer memoria fuera de dominio: {exc}")
            return []

    def _save(self) -> None:
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self._entries, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            self.log.log(Stage.VALIDADOR, f"⚠ No se pudo guardar memoria fuera de dominio: {exc}")

    def record(self, query: str) -> None:
        self._entries.append({"query": query, "timestamp": datetime.now().isoformat(timespec="seconds")})
        self._save()

    def similar(self, query: str, top_k: int = 1, min_similarity: float = None) -> list[dict]:
        """
        Hasta `top_k` entradas cuyo texto normalizado es (casi) igual a
        `query` — literal con variaciones triviales, NO parecido
        semánticamente. `min_similarity` se ignora (queda en la firma por
        compatibilidad de interfaz) — el umbral real es `_NEAR_MATCH_THRESHOLD`.
        """
        target = _normalize(query)
        if not target:
            return []
        scored = []
        for entry in self._entries:
            ratio = difflib.SequenceMatcher(None, target, _normalize(entry["query"])).ratio()
            if ratio >= _NEAR_MATCH_THRESHOLD:
                scored.append((ratio, entry))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in scored[:top_k]]
