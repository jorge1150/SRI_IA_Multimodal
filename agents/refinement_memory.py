"""
refinement_memory.py — Memoria de aprendizaje in-context del QueryRefinerAgent
Guarda casos donde el QueryValidatorAgent rechazó una pregunta y el
QueryRefinerAgent luego la corrigió con éxito: {rejected_query, motivo,
approved_query, vector}. El vector se calcula con el mismo OpenCLIP que ya
usa RAGAgent (sin nueva dependencia ni segundo modelo en memoria).

En cada refine() nuevo, se buscan por similitud coseno los ejemplos más
parecidos guardados y se inyectan como few-shot en el prompt — el modelo
"aprende" vía contexto acumulado entre consultas, no vía reentrenamiento de
pesos (no hay pipeline de fine-tuning en este proyecto, 100% de inferencia
local). Ver ADR-0006.
"""

import json
import os
from datetime import datetime

import numpy as np

from config import (
    REFINEMENT_MEMORY_PATH, REFINEMENT_MEMORY_TOP_K,
    REFINEMENT_MEMORY_MIN_SIMILARITY,
)
from .log_agent import LogAgent, Stage


class RefinementMemory:
    """
    Persistencia simple en JSON (mismo espíritu que graph_db/sri_graph.json)
    de pares (pregunta rechazada, motivo, pregunta aprobada) con su vector
    CLIP, para búsqueda de ejemplos similares vía similitud coseno.
    Nunca lanza: cualquier fallo de I/O o de embedding degrada a memoria
    vacía — el Refinador simplemente no recibe few-shot ese turno.
    """

    def __init__(self, rag_agent, log_agent: LogAgent, path: str = None):
        self.rag = rag_agent
        self.log = log_agent
        self.path = path or REFINEMENT_MEMORY_PATH
        self._entries: list[dict] = self._load()

    # ── Persistencia ─────────────────────────────────────────────────────────

    def _load(self) -> list[dict]:
        if not os.path.exists(self.path):
            return []
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            self.log.log(Stage.REFINADOR, f"⚠ No se pudo leer memoria de refinamiento: {exc}")
            return []

    def _save(self) -> None:
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self._entries, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            self.log.log(Stage.REFINADOR, f"⚠ No se pudo guardar memoria de refinamiento: {exc}")

    # ── API pública ──────────────────────────────────────────────────────────

    def record(self, rejected_query: str, motivo: str, approved_query: str) -> None:
        """Guarda una lección nueva: se llama solo cuando hubo al menos un
        rechazo real antes de converger (ver coordinator.py)."""
        vector = self._embed(rejected_query)
        if vector is None:
            return
        self._entries.append({
            "rejected_query": rejected_query,
            "motivo": motivo,
            "approved_query": approved_query,
            "vector": vector,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        })
        self._save()
        self.log.log(Stage.REFINADOR, f"✓ Lección guardada en memoria ({len(self._entries)} en total).")

    def similar(self, query: str, top_k: int = None, min_similarity: float = None) -> list[dict]:
        """Top-k ejemplos más parecidos por similitud coseno con `query`,
        filtrados por umbral mínimo. Lista vacía si no hay memoria, no hay
        nada por encima del umbral, o falla el embedding."""
        top_k = top_k if top_k is not None else REFINEMENT_MEMORY_TOP_K
        min_similarity = min_similarity if min_similarity is not None else REFINEMENT_MEMORY_MIN_SIMILARITY

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

    # ── Embeddings ───────────────────────────────────────────────────────────

    def _embed(self, text: str) -> list[float] | None:
        try:
            return self.rag._embed_text(text)
        except Exception as exc:
            self.log.log(Stage.REFINADOR, f"⚠ Error vectorizando para memoria de refinamiento: {exc}")
            return None
