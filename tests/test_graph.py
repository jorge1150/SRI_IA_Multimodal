"""
tests/test_graph.py — Pruebas unitarias para el módulo GraphRAG.
Ejecutar: python -m pytest tests/test_graph.py -v
"""

import os
import sys
import json
import tempfile
import unittest

# Agregar raíz al path
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)


# ─────────────────────────────────────────────────────────────
# EntityExtractor
# ─────────────────────────────────────────────────────────────

class TestEntityExtractor(unittest.TestCase):

    def setUp(self):
        from graph.entity_extractor import EntityExtractor
        self.extractor = EntityExtractor()

    def test_extract_iva(self):
        text = "El IVA tiene una tarifa del 12% para bienes y servicios."
        entities = self.extractor.extract(text)
        names = [e.name for e in entities]
        self.assertIn("IVA", names)

    def test_extract_ruc(self):
        text = "Para inscribirse en el RUC debe presentar cédula de identidad."
        entities = self.extractor.extract(text)
        names = [e.name for e in entities]
        self.assertIn("RUC", names)

    def test_extract_multiple_entities(self):
        text = "El contribuyente debe pagar el IVA y el Impuesto a la Renta."
        entities = self.extractor.extract(text)
        names = [e.name for e in entities]
        self.assertIn("IVA", names)
        self.assertIn("Impuesto a la Renta", names)

    def test_no_overlap(self):
        text = "La tarifa del IVA vigente."
        entities = self.extractor.extract(text)
        # Verificar que no hay entidades que se solapan
        spans = [(e.start, e.end) for e in entities]
        for i in range(len(spans)):
            for j in range(i + 1, len(spans)):
                s1, e1 = spans[i]
                s2, e2 = spans[j]
                self.assertFalse(
                    s1 < e2 and s2 < e1,
                    f"Solapamiento entre entidades en posiciones {spans[i]} y {spans[j]}"
                )

    def test_extract_unique(self):
        text = "El IVA se aplica al IVA y también al IVA en exportaciones."
        unique = self.extractor.extract_unique(text)
        iva_list = [e for e in unique if e["name"] == "IVA"]
        self.assertEqual(len(iva_list), 1)
        self.assertEqual(iva_list[0]["occurrences"], 3)

    def test_alias_recognition(self):
        text = "El impuesto al valor agregado grava el consumo final."
        entities = self.extractor.extract(text)
        names = [e.name for e in entities]
        # "impuesto al valor agregado" debe mapearse a "IVA"
        self.assertIn("IVA", names)

    def test_empty_text(self):
        entities = self.extractor.extract("")
        self.assertEqual(entities, [])

    def test_text_without_entities(self):
        text = "El sol sale por el oriente cada mañana."
        entities = self.extractor.extract(text)
        self.assertEqual(entities, [])


# ─────────────────────────────────────────────────────────────
# RelationExtractor
# ─────────────────────────────────────────────────────────────

class TestRelationExtractor(unittest.TestCase):

    def setUp(self):
        from graph.relation_extractor import RelationExtractor
        self.extractor = RelationExtractor()

    def test_extract_debe_presentar(self):
        text = "El contribuyente debe presentar la declaración del IVA mensualmente."
        triples = self.extractor.extract(text, "LRTI")
        self.assertGreater(len(triples), 0)
        relations = [t.relation for t in triples]
        self.assertIn("debe_presentar", relations)

    def test_extract_esta_exento(self):
        text = "Los alimentos básicos están exentos del IVA."
        triples = self.extractor.extract(text, "LRTI")
        relations = [t.relation for t in triples]
        self.assertIn("esta_exento", relations)

    def test_triple_has_document(self):
        text = "El contribuyente debe retener el IVA."
        triples = self.extractor.extract(text, "Resolución NAC-001")
        for t in triples:
            self.assertEqual(t.document, "Resolución NAC-001")

    def test_triple_weight_range(self):
        text = "El agente de retención debe retener el impuesto a la renta."
        triples = self.extractor.extract(text, "LRTI")
        for t in triples:
            self.assertGreater(t.weight, 0.0)
            self.assertLessEqual(t.weight, 1.0)

    def test_empty_text(self):
        triples = self.extractor.extract("", "doc")
        self.assertEqual(triples, [])


# ─────────────────────────────────────────────────────────────
# GraphStore
# ─────────────────────────────────────────────────────────────

class TestGraphStore(unittest.TestCase):

    def setUp(self):
        from graph.relation_extractor import Triple
        self.Triple = Triple
        self._tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        self._tmp.close()
        self._db_path = self._tmp.name

    def tearDown(self):
        if os.path.exists(self._db_path):
            os.unlink(self._db_path)

    def _make_store(self):
        from graph.graph_store import GraphStore
        return GraphStore(self._db_path)

    def _sample_triples(self):
        return [
            self.Triple(
                source="Contribuyente", source_type="sujeto",
                relation="debe_presentar", target="Declaración IVA",
                target_type="obligacion", evidence="debe presentar la declaración",
                document="LRTI", weight=0.75,
            ),
            self.Triple(
                source="IVA", source_type="impuesto",
                relation="aplica_tarifa", target="12%",
                target_type="concepto", evidence="tarifa del 12%",
                document="LRTI", weight=0.75,
            ),
        ]

    def test_add_and_stats(self):
        store = self._make_store()
        n_new = store.add_triples(self._sample_triples(), "LRTI")
        self.assertGreater(n_new, 0)
        stats = store.stats()
        self.assertGreater(stats["n_nodes"], 0)
        self.assertGreater(stats["n_edges"], 0)

    def test_save_and_load(self):
        store = self._make_store()
        store.add_triples(self._sample_triples(), "LRTI")
        store.save()

        store2 = self._make_store()
        ok = store2.load()
        self.assertTrue(ok)
        stats = store2.stats()
        self.assertGreater(stats["n_nodes"], 0)

    def test_is_empty_before_triples(self):
        store = self._make_store()
        self.assertTrue(store.is_empty())

    def test_is_not_empty_after_triples(self):
        store = self._make_store()
        store.add_triples(self._sample_triples(), "LRTI")
        self.assertFalse(store.is_empty())

    def test_get_neighbors(self):
        store = self._make_store()
        store.add_triples(self._sample_triples(), "LRTI")
        neighbors = store.get_neighbors("IVA", hops=1)
        self.assertIn("IVA", neighbors)

    def test_json_format(self):
        store = self._make_store()
        store.add_triples(self._sample_triples(), "LRTI")
        store.save()

        with open(self._db_path, encoding="utf-8") as f:
            data = json.load(f)

        self.assertIn("metadata", data)
        self.assertIn("nodes", data)
        self.assertIn("edges", data)
        self.assertIn("n_nodes", data["metadata"])

    def test_duplicate_triples_merge(self):
        store = self._make_store()
        triples = self._sample_triples()
        store.add_triples(triples, "LRTI")
        store.add_triples(triples, "LRTI")  # mismas triples otra vez
        stats = store.stats()
        # Aristas no deben duplicarse (se suman pesos)
        self.assertEqual(stats["n_edges"], len(triples))


# ─────────────────────────────────────────────────────────────
# GraphRetriever
# ─────────────────────────────────────────────────────────────

class TestGraphRetriever(unittest.TestCase):

    def setUp(self):
        import tempfile, os
        from graph.relation_extractor import Triple
        from graph.graph_store import GraphStore
        from graph.graph_retriever import GraphRetriever

        self._tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        self._tmp.close()
        self._db_path = self._tmp.name

        store = GraphStore(self._db_path)
        triples = [
            Triple("Contribuyente", "sujeto", "debe_presentar",
                   "Declaración IVA", "obligacion",
                   "debe presentar la declaración del IVA", "LRTI", 0.75),
            Triple("IVA", "impuesto", "aplica_tarifa",
                   "12%", "concepto",
                   "tarifa del 12%", "LRTI", 0.75),
            Triple("Agente de Retención", "sujeto", "debe_retener",
                   "IVA", "impuesto",
                   "debe retener el IVA", "LRTI", 0.75),
        ]
        store.add_triples(triples, "LRTI")
        self.retriever = GraphRetriever(store, hop_depth=1, top_k=5)

    def tearDown(self):
        if os.path.exists(self._db_path):
            os.unlink(self._db_path)

    def test_retrieve_returns_string(self):
        result = self.retriever.retrieve("¿Cuánto es el IVA?")
        self.assertIsInstance(result, str)

    def test_retrieve_iva_query(self):
        result = self.retriever.retrieve("tarifa del IVA en Ecuador")
        # Debe encontrar algo relacionado con IVA
        self.assertGreater(len(result), 0)

    def test_get_triples_returns_list(self):
        triples = self.retriever.get_triples("declaración IVA contribuyente")
        self.assertIsInstance(triples, list)

    def test_get_triples_structure(self):
        triples = self.retriever.get_triples("IVA")
        if triples:
            t = triples[0]
            self.assertIn("source", t)
            self.assertIn("relation", t)
            self.assertIn("target", t)
            self.assertIn("weight", t)

    def test_stats_for_query(self):
        stats = self.retriever.stats_for_query("IVA contribuyente")
        self.assertIn("entities_detected", stats)
        self.assertIn("triples_found", stats)

    def test_no_results_unknown_query(self):
        result = self.retriever.retrieve("xyzzy token inexistente 99999")
        # No debe lanzar excepción; puede retornar string vacío o sin triples
        self.assertIsInstance(result, str)


# ─────────────────────────────────────────────────────────────
# HybridRetriever
# ─────────────────────────────────────────────────────────────

class TestHybridRetriever(unittest.TestCase):

    def _make_mock_rag_agent(self, chunks=None):
        class MockRAGAgent:
            def retrieve(self, query, top_k=None):
                return chunks or []
        return MockRAGAgent()

    def _make_mock_log_agent(self):
        class MockLogAgent:
            def log(self, tag, msg):
                pass
        return MockLogAgent()

    def test_vector_only_mode_without_graph(self):
        from services.hybrid_retriever import HybridRetriever
        rag = self._make_mock_rag_agent([{"text": "chunk1", "similarity": 0.9, "metadata": {}}])
        log = self._make_mock_log_agent()

        retriever = HybridRetriever(rag_agent=rag, log_agent=log, graph_retriever=None)
        result = retriever.retrieve("¿Qué es el IVA?")

        self.assertEqual(result["mode"], "vector_only")
        self.assertEqual(len(result["vector_chunks"]), 1)
        self.assertEqual(result["graph_context"], "")

    def test_hybrid_mode_with_graph(self):
        import tempfile, os
        from graph.relation_extractor import Triple
        from graph.graph_store import GraphStore
        from graph.graph_retriever import GraphRetriever
        from services.hybrid_retriever import HybridRetriever

        tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        tmp.close()
        db_path = tmp.name

        try:
            store = GraphStore(db_path)
            store.add_triples([
                Triple("IVA", "impuesto", "aplica_tarifa", "12%", "concepto",
                       "tarifa del 12%", "LRTI", 0.75),
            ], "LRTI")

            graph_ret = GraphRetriever(store, hop_depth=1, top_k=3)
            rag = self._make_mock_rag_agent([{"text": "texto", "similarity": 0.8, "metadata": {}}])
            log = self._make_mock_log_agent()

            retriever = HybridRetriever(rag_agent=rag, log_agent=log, graph_retriever=graph_ret)
            result = retriever.retrieve("tarifa IVA")

            self.assertIn(result["mode"], ["hybrid", "vector_only"])
            self.assertIn("vector_chunks", result)
            self.assertIn("graph_context", result)
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)

    def test_fallback_on_graph_error(self):
        from services.hybrid_retriever import HybridRetriever

        class BrokenGraphRetriever:
            def retrieve(self, query):
                raise RuntimeError("simulated graph failure")
            def stats_for_query(self, query):
                raise RuntimeError("simulated graph failure")

        rag = self._make_mock_rag_agent()
        log = self._make_mock_log_agent()
        retriever = HybridRetriever(rag_agent=rag, log_agent=log,
                                    graph_retriever=BrokenGraphRetriever())
        result = retriever.retrieve("IVA")
        # Fallback silencioso — no debe lanzar excepción
        self.assertEqual(result["mode"], "vector_only")

    def test_result_keys(self):
        from services.hybrid_retriever import HybridRetriever
        rag = self._make_mock_rag_agent()
        log = self._make_mock_log_agent()
        retriever = HybridRetriever(rag_agent=rag, log_agent=log, graph_retriever=None)
        result = retriever.retrieve("consulta")

        for key in ("vector_chunks", "graph_context", "graph_triples", "graph_entities", "mode"):
            self.assertIn(key, result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
