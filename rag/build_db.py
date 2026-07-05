"""
build_db.py — Construye la base vectorial de normativa tributaria SRI.

Uso:
    python rag/build_db.py           # ingesta incremental (no borra lo existente)
    python rag/build_db.py --reset   # borra la colección y reinicia

Documentos soportados: PDF, TXT, DOCX, MD
Carpetas escaneadas: cada subcarpeta directa de data/ (excepto data/output/)
es una categoría — el nombre de la carpeta se usa como tipo de normativa.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rag.ingesta import ingest_all_documents
import config


def main():
    reset = "--reset" in sys.argv

    print("=" * 70)
    print("  SRI IA MULTIMODAL — Construcción de Base Vectorial Normativa")
    print("=" * 70)
    print(f"  ChromaDB:  {config.CHROMA_DB_PATH}")
    print(f"  Colección: {config.CHROMA_COLLECTION}")
    print(f"  Reset:     {reset}")
    print()
    print("  Carpetas de documentos:")
    for d in config.get_data_dirs():
        print(f"    {d}  [{os.path.basename(d)}]")
    print("=" * 70)

    n = ingest_all_documents(reset=reset)

    print("=" * 70)
    if n > 0:
        print(f"  ✓ Ingesta completada. {n} fragmentos nuevos insertados.")
        print("  ✓ Base vectorial lista. Ejecuta: python app.py")
    else:
        print("  ⚠ No se insertaron fragmentos nuevos.")
        print("  Verifica que existan documentos en las carpetas data/")
    print("=" * 70)


if __name__ == "__main__":
    main()
