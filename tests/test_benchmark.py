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
from scripts.run_benchmark import _normalize, _source_matched, _aggregate, _none_if_nan


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


class TestBenchmarkFormat(unittest.TestCase):
    """Formateadores compartidos entre el HTML del script y la tab de la UI —
    la convención vive en UN solo lugar (services/benchmark_format.py)."""

    def test_fmt_number(self):
        from services.benchmark_format import fmt_number, EMPTY
        self.assertEqual(fmt_number(1.5, "s"), "1.50s")
        self.assertEqual(fmt_number(None), EMPTY)
        self.assertEqual(fmt_number(float("nan")), EMPTY)
        self.assertEqual(fmt_number(0.0, "s"), "0.00s")  # cero es un valor, no "falta"

    def test_fmt_ragas_parts(self):
        from services.benchmark_format import fmt_ragas_parts
        self.assertEqual(fmt_ragas_parts(None, 0, 3), (None, None))       # --no-ragas
        self.assertEqual(fmt_ragas_parts(float("nan"), 0, 3), (None, None))
        self.assertEqual(fmt_ragas_parts(0.42, 3, 3), ("0.42", None))     # todo evaluado
        self.assertEqual(fmt_ragas_parts(0.42, 2, 3), ("0.42", "2/3"))    # juez falló en 1
        self.assertEqual(fmt_ragas_parts(0.42, 0, 0), (None, None))       # grupo vacío

    def test_fmt_planning_seconds(self):
        from services.benchmark_format import fmt_planning_seconds, EMPTY
        self.assertEqual(fmt_planning_seconds(16.3), "16.30s")
        self.assertEqual(fmt_planning_seconds(0.0), EMPTY)   # modos sin paso de planning
        self.assertEqual(fmt_planning_seconds(None), EMPTY)

    def test_fmt_rate_pct(self):
        from services.benchmark_format import fmt_rate_pct, EMPTY
        self.assertEqual(fmt_rate_pct(0.5), "50%")
        self.assertEqual(fmt_rate_pct(0.0), "0%")   # tasa cero es un dato real
        self.assertEqual(fmt_rate_pct(None), EMPTY)  # no aplica (ej. graph_only)

    def test_fmt_tokens(self):
        from services.benchmark_format import fmt_tokens, EMPTY
        self.assertEqual(fmt_tokens(1234), "1 234")
        self.assertEqual(fmt_tokens(0), EMPTY)
        self.assertEqual(fmt_tokens(None), EMPTY)

    def test_is_cloud_model(self):
        from services.benchmark_format import is_cloud_model
        self.assertTrue(is_cloud_model("gemma3:27b-cloud"))
        self.assertFalse(is_cloud_model("qwen2.5:3b-instruct-q4_K_M"))


class TestComputeModelRanking(unittest.TestCase):
    """Heurística de comparación entre modelos (ADR-0009) — no un score
    validado: pesos fijos declarados (50% calidad / 30% velocidad / 20%
    costo), normalizados dentro de los modelos presentes en la corrida."""

    def test_ranks_by_weighted_score(self):
        from services.benchmark_format import compute_model_ranking
        # Costo igual en los 3 (cost_n empata en 1.0 para todos — cubre la
        # rama hi==lo de la normalización) — el orden queda determinado por
        # calidad (50%) y velocidad (30%), sin ambigüedad de a quién favorece.
        by_model = {
            "modelo_a_mejor": {
                "avg_faithfulness": 0.9, "avg_answer_relevancy": 0.9,
                "avg_total_seconds": 2.0, "avg_total_tokens": 100,
            },
            "modelo_b_intermedio": {
                "avg_faithfulness": 0.5, "avg_answer_relevancy": 0.7,
                "avg_total_seconds": 4.0, "avg_total_tokens": 100,
            },
            "modelo_c_peor": {
                "avg_faithfulness": 0.3, "avg_answer_relevancy": 0.3,
                "avg_total_seconds": 8.0, "avg_total_tokens": 100,
            },
        }
        ranking = compute_model_ranking(by_model)
        self.assertEqual([r["model"] for r in ranking],
                          ["modelo_a_mejor", "modelo_b_intermedio", "modelo_c_peor"])
        self.assertAlmostEqual(ranking[0]["score"], 1.0, places=4)
        self.assertAlmostEqual(ranking[2]["score"], 0.2, places=4)

    def test_excludes_models_without_ragas(self):
        from services.benchmark_format import compute_model_ranking
        by_model = {
            "con_ragas_a": {"avg_faithfulness": 0.7, "avg_answer_relevancy": 0.7,
                             "avg_total_seconds": 2.0, "avg_total_tokens": 200},
            "con_ragas_b": {"avg_faithfulness": 0.5, "avg_answer_relevancy": 0.5,
                             "avg_total_seconds": 3.0, "avg_total_tokens": 300},
            "sin_ragas": {"avg_faithfulness": None, "avg_answer_relevancy": None,
                          "avg_total_seconds": 1.0, "avg_total_tokens": 50},
        }
        ranking = compute_model_ranking(by_model)
        models_ranked = {r["model"] for r in ranking}
        self.assertNotIn("sin_ragas", models_ranked)
        self.assertEqual(models_ranked, {"con_ragas_a", "con_ragas_b"})

    def test_empty_when_fewer_than_two_models_have_quality_data(self):
        from services.benchmark_format import compute_model_ranking
        by_model = {
            "unico": {"avg_faithfulness": 0.8, "avg_answer_relevancy": 0.8,
                      "avg_total_seconds": 1.0, "avg_total_tokens": 100},
        }
        self.assertEqual(compute_model_ranking(by_model), [])

    def test_marks_cloud_models(self):
        from services.benchmark_format import compute_model_ranking
        by_model = {
            "gemma3:27b-cloud": {"avg_faithfulness": 0.8, "avg_answer_relevancy": 0.8,
                                  "avg_total_seconds": 15.0, "avg_total_tokens": 500},
            "qwen2.5:3b-instruct-q4_K_M": {"avg_faithfulness": 0.6, "avg_answer_relevancy": 0.6,
                                            "avg_total_seconds": 5.0, "avg_total_tokens": 300},
        }
        ranking = compute_model_ranking(by_model)
        by_name = {r["model"]: r for r in ranking}
        self.assertTrue(by_name["gemma3:27b-cloud"]["is_cloud"])
        self.assertFalse(by_name["qwen2.5:3b-instruct-q4_K_M"]["is_cloud"])


if __name__ == "__main__":
    unittest.main()
