"""
graph_store.py — Almacenamiento del grafo de conocimiento tributario SRI.

Backend principal: NetworkX DiGraph con persistencia en JSON.
Backend opcional: Neo4j (si está disponible e instalado).
El sistema funciona 100% local sin Neo4j.
"""

import json
import os
from datetime import datetime
from typing import Optional

try:
    import networkx as nx
    _NX_AVAILABLE = True
except ImportError:
    _NX_AVAILABLE = False

from .relation_extractor import Triple


class GraphStore:
    """
    Grafo de conocimiento tributario respaldado por NetworkX.
    Nodos: entidades (IVA, RUC, contribuyente, etc.)
    Aristas: relaciones (debe_presentar, esta_exento, establece, etc.)
    Cada arista puede tener múltiples instancias (evidencias) de distintos documentos.
    """

    def __init__(self, graph_path: str):
        if not _NX_AVAILABLE:
            raise ImportError(
                "networkx no está instalado. "
                "Ejecuta: pip install networkx"
            )
        self.graph_path = graph_path
        self.G: nx.DiGraph = nx.DiGraph()
        self._documents_processed: set[str] = set()

    # ── Carga / Guardado ─────────────────────────────────────────────────────

    def load(self) -> bool:
        """Carga el grafo desde JSON. Retorna True si se cargó, False si no existe."""
        if not os.path.exists(self.graph_path):
            return False
        try:
            with open(self.graph_path, encoding="utf-8") as f:
                data = json.load(f)

            self.G = nx.DiGraph()

            for node in data.get("nodes", []):
                self.G.add_node(
                    node["id"],
                    entity_type=node.get("entity_type", ""),
                    label=node.get("label", node["id"]),
                )

            for edge in data.get("edges", []):
                src, tgt = edge["source"], edge["target"]
                rel = edge.get("relation", "relacionado_con")
                key = (src, tgt, rel)

                if self.G.has_edge(src, tgt):
                    existing = self.G[src][tgt]
                    # Agregar evidencia a la arista existente
                    if rel not in existing.get("relations", {}):
                        existing.setdefault("relations", {})[rel] = {
                            "weight": edge.get("weight", 1),
                            "evidences": [],
                        }
                    ev = edge.get("evidence", "")
                    if ev:
                        existing["relations"][rel]["evidences"].append({
                            "text": ev,
                            "document": edge.get("document", ""),
                        })
                else:
                    self.G.add_edge(src, tgt,
                        relations={
                            rel: {
                                "weight": edge.get("weight", 1),
                                "evidences": [
                                    {"text": edge.get("evidence", ""),
                                     "document": edge.get("document", "")}
                                ],
                            }
                        }
                    )

            self._documents_processed = set(data.get("metadata", {})
                                              .get("documents_processed", []))
            return True

        except Exception as exc:
            print(f"[GRAPH] Error cargando grafo: {exc}")
            return False

    def save(self) -> None:
        """Persiste el grafo en formato JSON legible."""
        os.makedirs(os.path.dirname(self.graph_path), exist_ok=True)

        nodes = []
        for node_id, attrs in self.G.nodes(data=True):
            nodes.append({
                "id": node_id,
                "entity_type": attrs.get("entity_type", ""),
                "label": attrs.get("label", node_id),
            })

        edges = []
        for src, tgt, attrs in self.G.edges(data=True):
            for rel, rel_data in attrs.get("relations", {}).items():
                for ev in rel_data.get("evidences", [{}]):
                    edges.append({
                        "source": src,
                        "target": tgt,
                        "relation": rel,
                        "weight": rel_data.get("weight", 1),
                        "evidence": ev.get("text", ""),
                        "document": ev.get("document", ""),
                    })

        payload = {
            "metadata": {
                "created_at": datetime.utcnow().isoformat() + "Z",
                "n_nodes": self.G.number_of_nodes(),
                "n_edges": self.G.number_of_edges(),
                "documents_processed": sorted(self._documents_processed),
            },
            "nodes": nodes,
            "edges": edges,
        }

        with open(self.graph_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        print(f"[GRAPH] Grafo guardado: {self.G.number_of_nodes()} nodos, "
              f"{self.G.number_of_edges()} aristas → {self.graph_path}")

    def export_graphml(self) -> str:
        """Exporta a GraphML (compatible con Gephi, yEd, etc.)."""
        graphml_path = self.graph_path.replace(".json", ".graphml")
        # NetworkX solo permite atributos simples en GraphML
        G_export = nx.DiGraph()
        for n, d in self.G.nodes(data=True):
            G_export.add_node(str(n), entity_type=d.get("entity_type", ""))
        for s, t, d in self.G.edges(data=True):
            for rel in d.get("relations", {}).keys():
                G_export.add_edge(str(s), str(t), relation=rel)
        nx.write_graphml(G_export, graphml_path)
        return graphml_path

    # ── Inserción ────────────────────────────────────────────────────────────

    def add_triples(self, triples: list[Triple], document_name: str = "") -> int:
        """
        Agrega una lista de triples al grafo.
        Retorna el número de aristas nuevas creadas.
        """
        new_edges = 0
        for triple in triples:
            # Asegurar que los nodos existen
            if not self.G.has_node(triple.source):
                self.G.add_node(triple.source,
                                entity_type=triple.source_type,
                                label=triple.source)
            if not self.G.has_node(triple.target):
                self.G.add_node(triple.target,
                                entity_type=triple.target_type,
                                label=triple.target)

            rel = triple.relation
            ev_entry = {
                "text": triple.evidence[:300],
                "document": document_name or triple.document,
            }

            if self.G.has_edge(triple.source, triple.target):
                edge_data = self.G[triple.source][triple.target]
                if rel not in edge_data.get("relations", {}):
                    edge_data.setdefault("relations", {})[rel] = {
                        "weight": 1,
                        "evidences": [],
                    }
                    new_edges += 1
                else:
                    edge_data["relations"][rel]["weight"] += 1
                ev = ev_entry.get("text", "")
                existing_evs = [
                    e["text"]
                    for e in edge_data["relations"][rel]["evidences"]
                ]
                if ev and ev not in existing_evs:
                    edge_data["relations"][rel]["evidences"].append(ev_entry)
            else:
                self.G.add_edge(triple.source, triple.target,
                    relations={
                        rel: {
                            "weight": triple.weight,
                            "evidences": [ev_entry],
                        }
                    }
                )
                new_edges += 1

        if document_name:
            self._documents_processed.add(document_name)

        return new_edges

    # ── Consulta ─────────────────────────────────────────────────────────────

    def get_neighbors(self, node: str, hops: int = 1) -> dict:
        """
        Retorna vecinos del nodo hasta `hops` saltos.
        Formato: {"nodes": [...], "edges": [...]}
        """
        if not self.G.has_node(node):
            return {"nodes": [], "edges": []}

        visited = {node}
        frontier = {node}
        all_edges = []

        for _ in range(hops):
            next_frontier = set()
            for n in frontier:
                # Vecinos hacia adelante
                for succ in self.G.successors(n):
                    edge_data = self.G[n][succ]
                    for rel, rel_info in edge_data.get("relations", {}).items():
                        all_edges.append({
                            "source": n,
                            "relation": rel,
                            "target": succ,
                            "weight": rel_info.get("weight", 1),
                            "evidence": (rel_info["evidences"][0]["text"]
                                         if rel_info.get("evidences") else ""),
                            "document": (rel_info["evidences"][0].get("document", "")
                                         if rel_info.get("evidences") else ""),
                        })
                    if succ not in visited:
                        next_frontier.add(succ)
                        visited.add(succ)

                # Vecinos hacia atrás (relaciones inversas)
                for pred in self.G.predecessors(n):
                    edge_data = self.G[pred][n]
                    for rel, rel_info in edge_data.get("relations", {}).items():
                        all_edges.append({
                            "source": pred,
                            "relation": rel,
                            "target": n,
                            "weight": rel_info.get("weight", 1),
                            "evidence": (rel_info["evidences"][0]["text"]
                                         if rel_info.get("evidences") else ""),
                            "document": (rel_info["evidences"][0].get("document", "")
                                         if rel_info.get("evidences") else ""),
                        })
                    if pred not in visited:
                        next_frontier.add(pred)
                        visited.add(pred)

            frontier = next_frontier

        nodes = [
            {"id": n,
             "entity_type": self.G.nodes[n].get("entity_type", "")}
            for n in visited
        ]
        return {"nodes": nodes, "edges": all_edges}

    def stats(self) -> dict:
        """Estadísticas del grafo."""
        relation_counts: dict[str, int] = {}
        for _, _, d in self.G.edges(data=True):
            for rel in d.get("relations", {}).keys():
                relation_counts[rel] = relation_counts.get(rel, 0) + 1

        return {
            "n_nodes": self.G.number_of_nodes(),
            "n_edges": self.G.number_of_edges(),
            "n_documents": len(self._documents_processed),
            "relation_types": relation_counts,
        }

    def is_empty(self) -> bool:
        return self.G.number_of_nodes() == 0
