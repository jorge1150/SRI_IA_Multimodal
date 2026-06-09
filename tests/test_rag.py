"""
test_rag.py — Pruebas del motor RAG de normativa tributaria SRI.
Uso: python -m pytest tests/test_rag.py -v
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rag.chunker import chunk_txt, chunk_document, _extract_articulo, _extract_year


def test_extract_year():
    assert _extract_year("lorti_2023.pdf") == "2023"
    assert _extract_year("resolucion_nac_2024_01.txt") == "2024"
    assert _extract_year("sin_año.txt") == ""


def test_extract_articulo():
    assert _extract_articulo("Art. 65.- Tarifa del IVA") == "Art. 65"
    assert _extract_articulo("Artículo 36 del LORTI") == "Artículo 36"
    assert _extract_articulo("Texto sin referencia a artículos") == ""


def test_chunk_txt_basic():
    """chunk_txt produce chunks con metadatos completos."""
    import tempfile, os
    content = "Art. 52.- Objeto del IVA. " * 30
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False,
                                     encoding='utf-8') as f:
        f.write(content)
        tmp = f.name
    try:
        chunks = chunk_txt(tmp, chunk_size=200, overlap=30, tipo_normativa="Ley / Normativa")
        assert len(chunks) > 0
        for c in chunks:
            assert "id" in c
            assert "text" in c
            assert "doc_name" in c
            assert "tipo_normativa" in c
            assert c["tipo_normativa"] == "Ley / Normativa"
    finally:
        os.unlink(tmp)


def test_chunk_document_dispatch():
    """chunk_document despacha al método correcto por extensión."""
    import tempfile, os
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False,
                                     encoding='utf-8') as f:
        f.write("Contenido de prueba tributaria SRI Ecuador. " * 10)
        tmp_txt = f.name
    try:
        chunks = chunk_document(tmp_txt, tipo_normativa="Guía Tributaria")
        assert isinstance(chunks, list)
        if chunks:
            assert chunks[0]["tipo_normativa"] == "Guía Tributaria"
    finally:
        os.unlink(tmp_txt)
