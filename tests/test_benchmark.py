"""
tests/test_benchmark.py — Pruebas unitarias para el parser de preguntas.docx
y los helpers puros de scripts/run_benchmark.py (sin Ollama/RAGAS).
Ejecutar: python -m pytest tests/test_benchmark.py -v
"""

import os
import sys
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

import math
from scripts.run_benchmark import _normalize, _source_matched, _strip_sources_section, _aggregate, _none_if_nan


class TestNormalize(unittest.TestCase):

    def test_strips_accents_and_case(self):
        self.assertEqual(_normalize("Artículo 153"), _normalize("articulo 153"))

    def test_strips_punctuation_and_spaces(self):
        self.assertEqual(_normalize("LRTI - ultima modificacion"), _normalize("LRTI ultima modificacion!!"))

    def test_empty_string(self):
        self.assertEqual(_normalize(""), "")
        self.assertEqual(_normalize(None), "")


class TestSourceMatched(unittest.TestCase):

    def test_no_chunks_returns_none(self):
        self.assertIsNone(_source_matched("Art 37", []))

    def test_no_expected_doc_returns_none(self):
        chunks = [{"metadata": {"doc_name": "Art 37 Tarifas"}}]
        self.assertIsNone(_source_matched("", chunks))

    def test_matches_by_doc_name(self):
        chunks = [{"metadata": {"doc_name": "Art 37 Tarifas Para Sociedades"}}]
        self.assertTrue(_source_matched("Art 37 Tarifas para sociedades", chunks))

    def test_matches_by_source_filename(self):
        chunks = [{"metadata": {"doc_name": "", "source": "Art_37_Tarifas.pdf"}}]
        self.assertTrue(_source_matched("Art 37 Tarifas", chunks))

    def test_no_match_returns_false(self):
        chunks = [{"metadata": {"doc_name": "Reglamento LRTI 2023", "source": "reglamento.pdf"}}]
        self.assertFalse(_source_matched("Art 37 Tarifas para sociedades", chunks))


class TestStripSourcesSection(unittest.TestCase):

    def test_strips_separator_and_below(self):
        sep = "─" * 37
        answer = f"Esta es la respuesta.\n\n{sep}\n📋 FUENTES CONSULTADAS:\n  [1] LRTI"
        self.assertEqual(_strip_sources_section(answer), "Esta es la respuesta.")

    def test_no_separator_returns_unchanged(self):
        answer = "Respuesta sin fuentes."
        self.assertEqual(_strip_sources_section(answer), answer)


class TestAggregate(unittest.TestCase):

    def test_averages_grouped_by_key(self):
        rows = [
            {"mode_requested": "vector_only", "retrieval_seconds": 2.0, "generation_seconds": 8.0,
             "total_seconds": 10.0, "faithfulness": 0.5, "answer_relevancy": 0.8, "source_matched": True},
            {"mode_requested": "vector_only", "retrieval_seconds": 4.0, "generation_seconds": 12.0,
             "total_seconds": 16.0, "faithfulness": 0.9, "answer_relevancy": None, "source_matched": False},
            {"mode_requested": "graph_only", "retrieval_seconds": 0.1, "generation_seconds": 10.0,
             "total_seconds": 10.1, "faithfulness": None, "answer_relevancy": None, "source_matched": None},
        ]
        agg = _aggregate(rows, "mode_requested")

        self.assertEqual(agg["vector_only"]["n"], 2)
        self.assertAlmostEqual(agg["vector_only"]["avg_total_seconds"], 13.0)
        self.assertAlmostEqual(agg["vector_only"]["avg_faithfulness"], 0.7)
        self.assertAlmostEqual(agg["vector_only"]["avg_answer_relevancy"], 0.8)
        self.assertAlmostEqual(agg["vector_only"]["source_match_rate"], 0.5)

        self.assertEqual(agg["graph_only"]["n"], 1)
        self.assertIsNone(agg["graph_only"]["avg_faithfulness"])
        self.assertIsNone(agg["graph_only"]["source_match_rate"])

    def test_reports_how_many_rows_were_evaluated(self):
        rows = [
            {"mode_requested": "hybrid", "retrieval_seconds": 1.0, "generation_seconds": 1.0,
             "total_seconds": 2.0, "faithfulness": 0.6, "answer_relevancy": None, "source_matched": None},
            {"mode_requested": "hybrid", "retrieval_seconds": 1.0, "generation_seconds": 1.0,
             "total_seconds": 2.0, "faithfulness": None, "answer_relevancy": None, "source_matched": None},
        ]
        agg = _aggregate(rows, "mode_requested")
        self.assertEqual(agg["hybrid"]["n"], 2)
        self.assertEqual(agg["hybrid"]["n_faithfulness_evaluated"], 1)
        self.assertEqual(agg["hybrid"]["n_answer_relevancy_evaluated"], 0)

    def test_nan_from_ragas_does_not_poison_the_average(self):
        # Regresión: un NaN suelto (el juez local de 3B falla seguido en
        # RAGAS, ver ADR-0003) antes contaminaba sum() completo -> el
        # promedio del grupo entero se perdía aunque hubiera scores válidos.
        rows = [
            {"mode_requested": "vector_only", "retrieval_seconds": 1.0, "generation_seconds": 1.0,
             "total_seconds": 2.0, "faithfulness": float("nan"), "answer_relevancy": 0.9, "source_matched": None},
            {"mode_requested": "vector_only", "retrieval_seconds": 1.0, "generation_seconds": 1.0,
             "total_seconds": 2.0, "faithfulness": 0.4, "answer_relevancy": float("nan"), "source_matched": None},
        ]
        agg = _aggregate(rows, "mode_requested")
        self.assertAlmostEqual(agg["vector_only"]["avg_faithfulness"], 0.4)
        self.assertAlmostEqual(agg["vector_only"]["avg_answer_relevancy"], 0.9)
        self.assertEqual(agg["vector_only"]["n_faithfulness_evaluated"], 1)
        self.assertEqual(agg["vector_only"]["n_answer_relevancy_evaluated"], 1)


class TestNoneIfNan(unittest.TestCase):

    def test_none_stays_none(self):
        self.assertIsNone(_none_if_nan(None))

    def test_nan_becomes_none(self):
        self.assertIsNone(_none_if_nan(float("nan")))

    def test_valid_float_passes_through(self):
        self.assertEqual(_none_if_nan(0.42), 0.42)

    def test_zero_is_not_treated_as_missing(self):
        self.assertEqual(_none_if_nan(0.0), 0.0)


if __name__ == "__main__":
    unittest.main()
