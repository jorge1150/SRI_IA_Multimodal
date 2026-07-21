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

Delegar la persistencia/similitud a SimilarityMemory (similarity_memory.py)
— misma lógica que reusa OffTopicMemory (ADR-0007), sin duplicarla.
"""

from config import (
    REFINEMENT_MEMORY_PATH, REFINEMENT_MEMORY_TOP_K,
    REFINEMENT_MEMORY_MIN_SIMILARITY,
)
from .log_agent import LogAgent, Stage
from .similarity_memory import SimilarityMemory


class RefinementMemory:
    """
    Envoltorio delgado sobre SimilarityMemory con la forma específica de
    una lección de refinamiento: pregunta rechazada, motivo, y la versión
    que terminó siendo aprobada.
    """

    def __init__(self, rag_agent, log_agent: LogAgent, path: str = None):
        self._mem = SimilarityMemory(
            rag_agent, log_agent, path or REFINEMENT_MEMORY_PATH,
            top_k_default=REFINEMENT_MEMORY_TOP_K,
            min_similarity_default=REFINEMENT_MEMORY_MIN_SIMILARITY,
            stage=Stage.REFINADOR,
        )

    def record(self, rejected_query: str, motivo: str, approved_query: str) -> None:
        """Guarda una lección nueva: se llama solo cuando hubo al menos un
        rechazo real antes de converger (ver coordinator.py)."""
        added = self._mem.add(rejected_query, {
            "rejected_query": rejected_query,
            "motivo": motivo,
            "approved_query": approved_query,
        })
        if added:
            self._mem.log.log(Stage.REFINADOR, f"✓ Lección guardada en memoria ({len(self._mem)} en total).")

    def similar(self, query: str, top_k: int = None, min_similarity: float = None) -> list[dict]:
        return self._mem.similar(query, top_k=top_k, min_similarity=min_similarity)
