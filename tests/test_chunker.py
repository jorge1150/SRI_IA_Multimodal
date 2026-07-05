"""
tests/test_chunker.py — Pruebas unitarias para rag/chunker.py (path MinerU).
Usa fixtures sintéticas de content_list.json — no invoca el binario MinerU.
Ejecutar: python -m pytest tests/test_chunker.py -v
"""

import os
import sys
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from rag.chunker import _chunks_from_mineru_blocks


def _run(blocks, **kwargs):
    defaults = dict(
        name_no_ext="doc", filename="doc.pdf", doc_name="Doc",
        tipo_normativa="Resolución", año="2024", filepath="/x/doc.pdf",
        chunk_size=500, overlap=60,
    )
    defaults.update(kwargs)
    return _chunks_from_mineru_blocks(blocks, **defaults)


class TestHeadingSections(unittest.TestCase):

    def test_heading_opens_new_section(self):
        blocks = [
            {"type": "text", "text": "Artículo 5.- Hecho generador", "text_level": 1, "page_idx": 0},
            {"type": "text", "text": "El impuesto se genera por la venta.", "page_idx": 0},
            {"type": "text", "text": "Artículo 6.- Base imponible", "text_level": 1, "page_idx": 0},
            {"type": "text", "text": "La base imponible es el valor de la transacción.", "page_idx": 0},
        ]
        chunks = _run(blocks)
        # Cada sección (heading + su párrafo) es corta y cabe en un solo
        # chunk de chunk_text — 1 chunk por sección, no 1 por bloque.
        self.assertEqual([c["kind"] for c in chunks], ["paragraph"] * 2)
        art5 = [c for c in chunks if "Artículo 5" in c["articulo_seccion"]]
        art6 = [c for c in chunks if "Artículo 6" in c["articulo_seccion"]]
        self.assertEqual(len(art5), 1)
        self.assertEqual(len(art6), 1)
        # ningún chunk de Art. 5 debe contener texto de Art. 6 ni viceversa
        for c in art5:
            self.assertNotIn("Base imponible", c["text"])
        for c in art6:
            self.assertNotIn("Hecho generador", c["text"])

    def test_heading_without_pattern_match_leaves_articulo_empty(self):
        blocks = [
            {"type": "text", "text": "CONSIDERANDO:", "text_level": 1, "page_idx": 0},
            {"type": "text", "text": "Que conforme a la ley...", "page_idx": 0},
        ]
        chunks = _run(blocks)
        self.assertEqual(chunks[0]["articulo_seccion"], "")

    def test_page_boundary_forces_split_but_keeps_articulo(self):
        blocks = [
            {"type": "text", "text": "Artículo 5.- Hecho generador", "text_level": 1, "page_idx": 0},
            {"type": "text", "text": "Texto en página uno.", "page_idx": 0},
            {"type": "text", "text": "Texto que continúa en página dos.", "page_idx": 1},
        ]
        chunks = _run(blocks)
        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0]["pagina"], 1)
        self.assertEqual(chunks[1]["pagina"], 2)
        self.assertEqual(chunks[0]["articulo_seccion"], chunks[1]["articulo_seccion"])
        self.assertIn("Artículo 5", chunks[0]["articulo_seccion"])

    def test_preamble_before_first_heading_has_empty_articulo(self):
        blocks = [
            {"type": "text", "text": "Texto introductorio sin heading.", "page_idx": 0},
        ]
        chunks = _run(blocks)
        self.assertEqual(chunks[0]["articulo_seccion"], "")


class TestTableChunks(unittest.TestCase):

    def test_table_inherits_current_articulo_and_kind(self):
        blocks = [
            {"type": "text", "text": "Artículo 10.- Tarifas", "text_level": 1, "page_idx": 0},
            {
                "type": "table", "page_idx": 0,
                "table_caption": ["Tabla de tarifas de IVA vigentes desde 2024"],
                "table_body": "<table><tr><td>IVA</td><td>12.5%</td></tr></table>",
                "table_footnote": ["*Tarifa referencial."],
            },
        ]
        chunks = _run(blocks)
        tbl = [c for c in chunks if c["kind"] == "table"]
        self.assertEqual(len(tbl), 1)
        self.assertIn("Artículo 10", tbl[0]["articulo_seccion"])
        self.assertIn("<table>", tbl[0]["text"])
        self.assertIn("Tabla de tarifas", tbl[0]["text"])
        self.assertIn("Tarifa referencial", tbl[0]["text"])

    def test_table_graph_text_excludes_html(self):
        blocks = [
            {
                "type": "table", "page_idx": 0,
                "table_caption": ["Tabla de tarifas de IVA"],
                "table_body": "<table><tr><td>IVA</td><td>12.5%</td></tr></table>",
                "table_footnote": ["*Vigente desde 2024."],
            },
        ]
        chunks = _run(blocks)
        tbl = chunks[0]
        self.assertNotIn("<table>", tbl["graph_text"])
        self.assertIn("Tabla de tarifas", tbl["graph_text"])
        self.assertIn("Vigente desde 2024", tbl["graph_text"])

    def test_table_without_caption_or_footnote_has_empty_graph_text(self):
        blocks = [
            {"type": "table", "page_idx": 0, "table_body": "<table><tr><td>x</td></tr></table>"},
        ]
        chunks = _run(blocks)
        self.assertEqual(chunks[0]["graph_text"], "")


class TestEquationChunks(unittest.TestCase):

    def test_equation_with_latex_becomes_own_chunk(self):
        blocks = [
            {"type": "text", "text": "Artículo 7.- Cálculo", "text_level": 1, "page_idx": 0},
            {"type": "equation", "page_idx": 0, "text": r"IVA = Base \times 0.12", "text_format": "latex"},
        ]
        chunks = _run(blocks)
        eq = [c for c in chunks if c["kind"] == "equation"]
        self.assertEqual(len(eq), 1)
        self.assertEqual(eq[0]["text"], r"IVA = Base \times 0.12")
        self.assertIn("Artículo 7", eq[0]["articulo_seccion"])
        self.assertEqual(eq[0]["graph_text"], "")

    def test_equation_without_text_produces_no_chunk(self):
        blocks = [
            {"type": "equation", "page_idx": 0, "img_path": "images/eq1.png"},
        ]
        chunks = _run(blocks)
        self.assertEqual(len(chunks), 0)


class TestImageCaption(unittest.TestCase):

    def test_image_caption_key_is_read(self):
        blocks = [
            {"type": "image", "page_idx": 0, "img_path": "images/fig1.png",
             "image_caption": ["Figura 1. Flujo de declaración de IVA."]},
        ]
        chunks = _run(blocks)
        self.assertEqual(len(chunks), 1)
        self.assertIn("Flujo de declaración de IVA", chunks[0]["text"])

    def test_image_without_caption_produces_no_chunk(self):
        blocks = [
            {"type": "image", "page_idx": 0, "img_path": "images/fig1.png", "image_caption": []},
        ]
        chunks = _run(blocks)
        self.assertEqual(len(chunks), 0)


class TestSkipTypes(unittest.TestCase):

    def test_page_number_footer_header_are_dropped(self):
        blocks = [
            {"type": "page_number", "text": "1", "page_idx": 0},
            {"type": "footer", "text": "Registro Oficial", "page_idx": 0},
            {"type": "header", "text": "SRI", "page_idx": 0},
            {"type": "text", "text": "Contenido real del artículo.", "page_idx": 0},
        ]
        chunks = _run(blocks)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]["text"], "Contenido real del artículo.")


if __name__ == "__main__":
    unittest.main()
