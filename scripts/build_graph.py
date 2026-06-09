"""
build_graph.py — Script CLI para construir el grafo de conocimiento tributario SRI.

Uso:
    python scripts/build_graph.py              # incremental (mantiene lo existente)
    python scripts/build_graph.py --reset      # reconstruir desde cero
    python scripts/build_graph.py --export-graphml  # también exportar GraphML

El grafo se guarda en: graph_db/sri_graph.json
"""

import argparse
import os
import sys
import time

# Agregar raíz al path para importaciones
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)


def main():
    parser = argparse.ArgumentParser(
        description="Construir grafo de conocimiento tributario SRI Ecuador"
    )
    parser.add_argument(
        "--reset", action="store_true",
        help="Borrar grafo existente y reconstruir desde cero"
    )
    parser.add_argument(
        "--export-graphml", action="store_true",
        help="Exportar también en formato GraphML (compatible con Gephi)"
    )
    parser.add_argument(
        "--stats-only", action="store_true",
        help="Solo mostrar estadísticas del grafo existente"
    )
    args = parser.parse_args()

    print("""
╔══════════════════════════════════════════════════════════╗
║   SRI IA Multimodal — Construcción de Grafo de Conocimiento ║
╚══════════════════════════════════════════════════════════╝
""")

    import config
    from graph.graph_store import GraphStore
    from graph.graph_builder import GraphBuilder

    store = GraphStore(config.GRAPH_DB_PATH)

    # Mostrar solo stats si ya existe
    if args.stats_only:
        if store.load():
            stats = store.stats()
            print(f"Nodos: {stats['n_nodes']}")
            print(f"Aristas: {stats['n_edges']}")
            print(f"Documentos procesados: {stats['n_documents']}")
            print(f"Tipos de relación: {stats['relation_types']}")
        else:
            print("[AVISO] No existe grafo guardado en:", config.GRAPH_DB_PATH)
        return

    # Cargar grafo existente si modo incremental
    if not args.reset:
        if store.load():
            old_stats = store.stats()
            print(f"[INFO] Grafo existente cargado: {old_stats['n_nodes']} nodos, "
                  f"{old_stats['n_edges']} aristas.")
        else:
            print("[INFO] Grafo nuevo — construyendo desde cero.")

    t0 = time.time()

    builder = GraphBuilder(store, verbose=True)
    result = builder.build_from_directory(
        data_dirs=config.ALL_DATA_DIRS,
        tipo_by_folder=config.TIPO_BY_FOLDER,
        reset=args.reset,
    )

    elapsed = time.time() - t0

    print(f"\n[OK] Grafo construido en {elapsed:.1f}s")
    print(f"     Nodos:   {result.get('n_nodes', 0)}")
    print(f"     Aristas: {result.get('n_edges', 0)}")
    print(f"     Chunks:  {result.get('chunks_processed', 0)}")

    store.save()

    if args.export_graphml:
        graphml_path = store.export_graphml()
        print(f"[OK] GraphML exportado: {graphml_path}")

    print(f"\n[INFO] Grafo disponible en: {config.GRAPH_DB_PATH}")
    print("[INFO] Activa GraphRAG con GRAPH_ENABLED=True en config.py")


if __name__ == "__main__":
    main()
