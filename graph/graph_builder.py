"""
graph_builder.py — Construye el grafo de conocimiento desde documentos SRI.

Flujo:
  1. Recorre todos los chunks (fragmentos) de los documentos SRI.
  2. Extrae entidades y relaciones de cada chunk.
  3. Agrega los triples al GraphStore.
  4. Guarda el grafo en disco.

Puede reusar los chunks ya procesados por el RAG pipeline (rag/chunker.py).
"""

import os
import sys

# Permitir importación cuando se ejecuta como script
_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BASE not in sys.path:
    sys.path.insert(0, _BASE)

from .entity_extractor import EntityExtractor
from .relation_extractor import RelationExtractor
from .graph_store import GraphStore


class GraphBuilder:
    """
    Constructor del grafo de conocimiento tributario.
    Procesa fragmentos de texto y alimenta el GraphStore.
    """

    def __init__(self, graph_store: GraphStore, verbose: bool = True):
        self.store = graph_store
        self.verbose = verbose
        self._entity_extractor = EntityExtractor()
        self._relation_extractor = RelationExtractor()

    # ── API pública ──────────────────────────────────────────────────────────

    def build_from_chunks(self, chunks: list[dict], reset: bool = False) -> dict:
        """
        Construye o actualiza el grafo a partir de una lista de chunks RAG.
        Cada chunk es el dict plano que produce rag.chunker.chunk_document:
          {"text": ..., "doc_name": ..., "source": ..., "kind": ..., ...}

        reset=True: vacía el grafo antes de reconstruir.
        Retorna estadísticas de construcción.
        """
        if reset:
            import networkx as nx
            self.store.G = nx.DiGraph()
            self.store._documents_processed = set()
            self.store._build_seconds = 0.0
            if self.verbose:
                print("[GRAPH_BUILDER] Grafo reiniciado.")

        total_triples = 0
        total_entities = 0
        processed_chunks = 0

        for i, chunk in enumerate(chunks):
            text = chunk.get("text", "")
            doc_name = chunk.get("doc_name") or chunk.get("source") or f"chunk_{i}"

            # Tabla/ecuación: el HTML/LaTeX de "text" rompe el sentence-splitter
            # de RelationExtractor. Solo caption/footnote (graph_text) son prosa
            # segura para extraer entidades y relaciones.
            if chunk.get("kind") in ("table", "equation"):
                text = chunk["graph_text"]

            if not text.strip():
                continue

            # Extraer entidades
            entities = self._entity_extractor.extract_unique(text)
            total_entities += len(entities)

            # Extraer relaciones
            triples = self._relation_extractor.extract(text, document_name=doc_name)

            # Agregar al grafo
            new_edges = self.store.add_triples(triples, document_name=doc_name)
            total_triples += new_edges
            processed_chunks += 1

            if self.verbose and (i + 1) % 20 == 0:
                print(f"[GRAPH_BUILDER] Procesados {i+1}/{len(chunks)} chunks "
                      f"| {self.store.stats()['n_nodes']} nodos "
                      f"| {self.store.stats()['n_edges']} aristas")

        stats = self.store.stats()
        if self.verbose:
            print(f"\n[GRAPH_BUILDER] Construcción completada:")
            print(f"  Chunks procesados:  {processed_chunks}")
            print(f"  Entidades únicas:   {stats['n_nodes']}")
            print(f"  Relaciones únicas:  {stats['n_edges']}")
            print(f"  Nuevos triples:     {total_triples}")
            print(f"  Tipos de relación:  {stats['relation_types']}")

        return {
            "chunks_processed": processed_chunks,
            "n_nodes": stats["n_nodes"],
            "n_edges": stats["n_edges"],
            "new_triples": total_triples,
        }

    def build_from_directory(self, data_dirs: list[str], reset: bool = False) -> dict:
        """
        Construye el grafo leyendo directamente desde los directorios de documentos.
        Reutiliza el chunker del proyecto RAG. tipo_normativa es el nombre de
        cada carpeta en data_dirs (ver config.get_data_dirs).
        """
        import glob
        try:
            from rag.chunker import chunk_document
        except ImportError:
            print("[GRAPH_BUILDER] ERROR: No se pudo importar rag.chunker")
            return {}

        SUPPORTED = ("*.pdf", "*.txt", "*.docx", "*.md")
        all_chunks: list[dict] = []

        # Recopilar todos los archivos primero para mostrar progreso
        all_files = []
        for data_dir in data_dirs:
            tipo = os.path.basename(data_dir)
            for ext in SUPPORTED:
                for filepath in glob.glob(os.path.join(data_dir, ext)):
                    all_files.append((filepath, tipo))

        total_files = len(all_files)
        if self.verbose:
            print(f"[GRAPH_BUILDER] {total_files} archivos a procesar...")

        for idx, (filepath, tipo) in enumerate(all_files, 1):
            if self.verbose:
                pct = idx * 100 // total_files
                print(f"[GRAPH_BUILDER] [{idx}/{total_files} {pct}%] {os.path.basename(filepath)}")
            try:
                chunks = chunk_document(filepath, tipo_normativa=tipo)
                all_chunks.extend(chunks)
            except Exception as exc:
                print(f"[GRAPH_BUILDER] Error en {filepath}: {exc}")

        print(f"[GRAPH_BUILDER] Total chunks para grafo: {len(all_chunks)}")
        return self.build_from_chunks(all_chunks, reset=reset)
