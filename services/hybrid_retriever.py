"""
hybrid_retriever.py — Recuperación híbrida: RAG vectorial + GraphRAG.

Combina:
  1. Chunks vectoriales de ChromaDB (RAG tradicional).
  2. Contexto del grafo de conocimiento (GraphRAG).

El contexto combinado es más rico que cada fuente por separado:
  - RAG vectorial aporta fragmentos textuales exactos con similitud coseno.
  - GraphRAG aporta relaciones estructurales entre entidades tributarias.
"""

import os
import sys

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BASE not in sys.path:
    sys.path.insert(0, _BASE)


class HybridRetriever:
    """
    Orquesta la recuperación vectorial y de grafo para cada consulta.
    Si GraphRAG está deshabilitado o el grafo está vacío, funciona
    solo con el RAG vectorial (sin degradar el sistema existente).
    """

    def __init__(self, rag_agent, log_agent, graph_retriever=None):
        """
        rag_agent:       instancia de RAGAgent (ya existente).
        log_agent:       instancia de LogAgent (ya existente).
        graph_retriever: instancia de GraphRetriever (None = deshabilitado).
        """
        self.rag = rag_agent
        self.log = log_agent
        self.graph = graph_retriever  # puede ser None

    # ── API pública ──────────────────────────────────────────────────────────

    def retrieve(self, query: str, top_k: int = None) -> dict:
        """
        Ejecuta recuperación híbrida y retorna un dict con:
          - vector_chunks:  list[dict] igual al formato de RAGAgent.retrieve()
          - graph_context:  str con relaciones del grafo (vacío si deshabilitado)
          - graph_triples:  list[dict] con triples estructurados
          - graph_entities: list[str] entidades detectadas en la consulta
          - mode:           "hybrid" | "vector_only"
        """
        # 1. Recuperación vectorial (siempre activa)
        kwargs = {"top_k": top_k} if top_k else {}
        vector_chunks = self.rag.retrieve(query, **kwargs)

        self.log.log("RAG", f"✓ Vectorial: {len(vector_chunks)} fragmento(s) recuperado(s).")

        # 2. Recuperación de grafo (solo si disponible)
        graph_context = ""
        graph_triples = []
        graph_entities = []
        mode = "vector_only"

        if self.graph is not None:
            try:
                graph_stats = self.graph.stats_for_query(query)
                graph_entities = graph_stats["entities_detected"]

                if graph_entities:
                    self.log.log(
                        "GRAPH",
                        f"Entidades detectadas: {', '.join(graph_entities[:5])}"
                    )

                graph_triples = self.graph.get_triples(query)

                if graph_triples:
                    graph_context = self.graph.retrieve(query)
                    mode = "hybrid"
                    self.log.log(
                        "GRAPH",
                        f"✓ Grafo: {len(graph_triples)} relación(es) recuperada(s) "
                        f"[{', '.join(graph_stats['relations_types'][:3])}]"
                    )
                else:
                    self.log.log("GRAPH", "Sin relaciones relevantes en el grafo para esta consulta.")

            except Exception as exc:
                self.log.log("GRAPH", f"⚠ Error en GraphRAG: {exc} — usando solo RAG vectorial.")

        return {
            "vector_chunks": vector_chunks,
            "graph_context": graph_context,
            "graph_triples": graph_triples,
            "graph_entities": graph_entities,
            "mode": mode,
        }

    def format_combined_context(
        self, vector_chunks: list[dict], graph_context: str
    ) -> str:
        """
        Genera un resumen del contexto combinado para logging / debug.
        """
        lines = []

        if vector_chunks:
            lines.append(f"[Vectorial] {len(vector_chunks)} fragmento(s):")
            for c in vector_chunks[:2]:
                meta = c.get("metadata", {})
                doc = meta.get("doc_name", "—")
                sim = c.get("similarity", 0)
                lines.append(f"  • {doc} (sim={sim:.2f})")

        if graph_context:
            lines.append("[Grafo] Relaciones:")
            for line in graph_context.splitlines()[:5]:
                lines.append(f"  {line}")

        return "\n".join(lines)
