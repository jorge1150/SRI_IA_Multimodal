"""
graph_retriever.py — Recupera contexto del grafo de conocimiento para responder preguntas.

Flujo para una pregunta del usuario:
  1. Detectar entidades mencionadas en la pregunta.
  2. Para cada entidad, buscar su nodo en el grafo.
  3. Recuperar vecinos a 1-2 saltos.
  4. Formatear las relaciones como contexto legible para el LLM.
"""

import os
import sys

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BASE not in sys.path:
    sys.path.insert(0, _BASE)

from .entity_extractor import EntityExtractor
from .graph_store import GraphStore


# Mapa de tipos de relación → texto legible en español
_RELATION_LABELS: dict[str, str] = {
    "debe_presentar":   "debe presentar / declarar",
    "debe_retener":     "debe retener",
    "puede_deducir":    "puede deducir",
    "esta_exento":      "está exento de",
    "aplica_tarifa":    "aplica tarifa a",
    "debe_inscribirse": "debe inscribirse en",
    "establece":        "establece / regula",
    "declara_en":       "se declara en",
    "genera_obligacion":"genera obligación hacia",
    "tiene_plazo":      "tiene plazo para",
    "puede_acogerse":   "puede acogerse a",
    "relacionado_con":  "está relacionado con",
}


class GraphRetriever:
    """
    Recupera sub-grafos relevantes para responder preguntas tributarias.
    """

    def __init__(
        self,
        graph_store: GraphStore,
        hop_depth: int = 2,
        top_k: int = 10,
    ):
        self.store = graph_store
        self.hop_depth = hop_depth
        self.top_k = top_k
        self._entity_extractor = EntityExtractor()

    # ── API pública ──────────────────────────────────────────────────────────

    def retrieve(self, query: str) -> str:
        """
        Recupera contexto del grafo como texto legible para el LLM.
        Retorna string vacío si el grafo está vacío o no hay entidades.
        """
        if self.store.is_empty():
            return ""

        triples = self.get_triples(query)
        if not triples:
            return ""

        return self._format_context(query, triples)

    def get_triples(self, query: str) -> list[dict]:
        """
        Retorna lista de triples relevantes para la consulta.
        Cada triple: {"source", "relation", "target", "weight", "evidence", "document"}
        """
        if self.store.is_empty():
            return []

        # 1. Detectar entidades en la pregunta
        entities_in_query = self._entity_extractor.extract(query)
        if not entities_in_query:
            # Si no hay entidades reconocidas, buscar por texto parcial
            entities_in_query = self._fuzzy_match_nodes(query)

        if not entities_in_query:
            return []

        # 2. Para cada entidad, recuperar vecindad del grafo
        all_edges: list[dict] = []
        seen_pairs: set[tuple] = set()
        query_entity_names = {e.name if hasattr(e, 'name') else e for e in entities_in_query}

        for entity in entities_in_query:
            node_name = entity.name if hasattr(entity, 'name') else entity
            subgraph = self.store.get_neighbors(node_name, hops=self.hop_depth)
            for edge in subgraph["edges"]:
                key = (edge["source"], edge["relation"], edge["target"])
                if key not in seen_pairs:
                    seen_pairs.add(key)
                    all_edges.append(edge)

        # 3. Priorizar: triples con mayor peso y evidencia textual
        all_edges.sort(key=lambda e: (e.get("weight", 1), bool(e.get("evidence"))),
                       reverse=True)

        # 4. Boost: priorizar triples que conectan entidades de la consulta
        boosted = []
        rest = []
        for edge in all_edges:
            if edge["source"] in query_entity_names or edge["target"] in query_entity_names:
                boosted.append(edge)
            else:
                rest.append(edge)

        return (boosted + rest)[: self.top_k]

    def detected_entities(self, query: str) -> list[str]:
        """Retorna nombres canónicos de entidades detectadas en la consulta."""
        entities = self._entity_extractor.extract(query)
        return [e.name for e in entities]

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _fuzzy_match_nodes(self, query: str) -> list:
        """
        Búsqueda parcial por si no se detectaron entidades formales.
        Compara tokens del query contra nombres de nodos del grafo.
        """
        import unicodedata

        def norm(s: str) -> str:
            nfkd = unicodedata.normalize("NFKD", s.lower())
            return "".join(c for c in nfkd if not unicodedata.combining(c))

        query_tokens = set(norm(query).split())
        matched = []

        class _FakeEntity:
            def __init__(self, name): self.name = name

        for node in self.store.G.nodes():
            node_tokens = set(norm(node).split())
            if query_tokens & node_tokens:
                matched.append(_FakeEntity(node))

        return matched[:5]  # máximo 5 nodos por búsqueda difusa

    def _format_context(self, query: str, triples: list[dict]) -> str:
        """
        Convierte los triples en texto legible para incluir en el prompt del LLM.
        """
        lines = ["RELACIONES DEL GRAFO NORMATIVO SRI:"]
        for t in triples:
            rel_label = _RELATION_LABELS.get(t["relation"], t["relation"])
            line = f"  • {t['source']} → [{rel_label}] → {t['target']}"
            if t.get("document"):
                line += f"  (Fuente: {t['document']})"
            lines.append(line)

        if any(t.get("evidence") for t in triples[:3]):
            lines.append("\nEvidencia textual:")
            for t in triples[:3]:
                if t.get("evidence"):
                    lines.append(f"  \"{t['evidence'][:120]}...\"")

        return "\n".join(lines)

    def stats_for_query(self, query: str) -> dict:
        """Estadísticas de lo que se recuperó para una consulta (para logs)."""
        entities = self._entity_extractor.extract(query)
        triples = self.get_triples(query)
        return {
            "entities_detected": [e.name for e in entities],
            "triples_found": len(triples),
            "relations_types": list({t["relation"] for t in triples}),
        }
