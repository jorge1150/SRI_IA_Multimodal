"""
similarity_memory.py — Base de memoria por similitud (JSON + embedding CLIP)
Lógica compartida entre RefinementMemory (correcciones pasadas del
QueryRefinerAgent) y OffTopicMemory (preguntas fuera de dominio ya vistas):
persistencia simple en JSON, embedding con el mismo OpenCLIP que ya usa
RAGAgent, y búsqueda de los ejemplos más parecidos por similitud coseno.

Nunca lanza: cualquier fallo de I/O o de embedding degrada a memoria vacía
— el llamador simplemente no recibe matches ese turno. Ver ADR-0006/ADR-0007.
"""

import json
import os
from datetime import datetime

import numpy as np

from .log_agent import LogAgent, Stage


class SimilarityMemory:
    """
    Persistencia simple en JSON (mismo espíritu que graph_db/sri_graph.json)
    de entradas {**payload, vector, timestamp}, para búsqueda de ejemplos
    similares vía similitud coseno sobre `vector` (embedding CLIP).
    """

    def __init__(
        self, rag_agent, log_agent: LogAgent, path: str,
        top_k_default: int, min_similarity_default: float,
        stage: str = Stage.REFINADOR,
    ):
        self.rag = rag_agent
        self.log = log_agent
        self.path = path
        self.top_k_default = top_k_default
        self.min_similarity_default = min_similarity_default
        self.stage = stage
        self._entries: list[dict] = self._load()

    # ── Persistencia ─────────────────────────────────────────────────────────

    def _load(self) -> list[dict]:
        if not os.path.exists(self.path):
            return []
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            self.log.log(self.stage, f"⚠ No se pudo leer memoria ({self.path}): {exc}")
            return []

    def _save(self) -> None:
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self._entries, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            self.log.log(self.stage, f"⚠ No se pudo guardar memoria ({self.path}): {exc}")

    # ── API pública ──────────────────────────────────────────────────────────

    def add(self, key_text: str, payload: dict) -> bool:
        """Embebe `key_text` y guarda `payload` junto con el vector y timestamp.
        Retorna False sin guardar nada si el embedding falla."""
        vector = self._embed(key_text)
        if vector is None:
            return False
        self._entries.append({
            **payload,
            "vector": vector,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        })
        self._save()
        return True

    def similar(self, query: str, top_k: int = None, min_similarity: float = None) -> list[dict]:
        """Top-k entradas más parecidas por similitud coseno con `query`,
        filtradas por umbral mínimo. Lista vacía si no hay memoria, no hay
        nada por encima del umbral, o falla el embedding."""
        top_k = top_k if top_k is not None else self.top_k_default
        min_similarity = min_similarity if min_similarity is not None else self.min_similarity_default

        if not self._entries:
            return []

        query_vector = self._embed(query)
        if query_vector is None:
            return []

        q = np.array(query_vector)
        q_norm = np.linalg.norm(q)
        if q_norm == 0:
            return []

        scored = []
        for entry in self._entries:
            v = np.array(entry["vector"])
            v_norm = np.linalg.norm(v)
            if v_norm == 0:
                continue
            similarity = float(np.dot(q, v) / (q_norm * v_norm))
            if similarity >= min_similarity:
                scored.append((similarity, entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in scored[:top_k]]

    def __len__(self) -> int:
        return len(self._entries)

    # ── Embeddings ───────────────────────────────────────────────────────────

    def _embed(self, text: str) -> list[float] | None:
        try:
            # OpenCLIP se carga lazy en RAGAgent — solo retrieve()/embed_image()
            # lo disparaban antes; sin esto, _embed_text() ve _tokenizer=None
            # en la primera consulta ("'NoneType' object is not callable").
            self.rag._load_clip()
            return self.rag._embed_text(text)
        except Exception as exc:
            self.log.log(self.stage, f"⚠ Error vectorizando para memoria: {exc}")
            return None
