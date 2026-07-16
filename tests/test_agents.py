"""
test_agents.py — Pruebas de los agentes del sistema SRI IA Multimodal.
Uso: python -m pytest tests/test_agents.py -v
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.log_agent import LogAgent, Stage


def test_log_agent_basic():
    log = LogAgent()
    log.log(Stage.INICIO, "Sistema SRI iniciado.")
    log.log(Stage.RAG, "Buscando normativa.")
    output = log.get_all()
    assert "INICIO" in output
    assert "RAG" in output
    assert "Sistema SRI iniciado." in output


def test_log_agent_clear():
    log = LogAgent()
    log.log(Stage.INFO, "mensaje de prueba")
    log.clear()
    assert log.get_all() == ""
    assert log.get_events() == []


def test_log_agent_icons():
    log = LogAgent()
    entry = log.log(Stage.NORMATIVA, "Recuperando artículos.")
    assert "⚖️" in entry


def test_log_agent_structured_events():
    log = LogAgent()
    log.log(Stage.INICIO, "arranque")
    log.log(Stage.PLANNER, "decidiendo...")
    log.log(Stage.PLANNER, "decidió: usar grafo")

    events = log.get_events()
    assert len(events) == 3
    assert events[0] == {"stage": "INICIO", "message": "arranque", "timestamp": events[0]["timestamp"]}
    # Dos eventos de la misma etapa se conservan ambos (el diagrama usa el último)
    assert [e["message"] for e in events if e["stage"] == "PLANNER"] == \
        ["decidiendo...", "decidió: usar grafo"]


def test_log_agent_events_snapshot_is_a_copy():
    log = LogAgent()
    log.log(Stage.RAG, "x")
    snapshot = log.get_events()
    snapshot.append({"stage": "FALSO", "message": "no debe entrar", "timestamp": ""})
    assert len(log.get_events()) == 1


def test_agent_flow_html_renders_from_events():
    from ui.interface import _render_agent_flow_html

    events = [
        {"stage": Stage.INICIO, "message": "arranque", "timestamp": "10:00:00"},
        {"stage": Stage.PLANNER, "message": "decidió: usar GraphRAG", "timestamp": "10:00:02"},
        {"stage": Stage.RAG, "message": "buscando normativa", "timestamp": "10:00:03"},
    ]
    html_out = _render_agent_flow_html(events)

    # RAG es la última etapa alcanzada → nodo activo; INICIO y PLANNER done;
    # STT/Visión no aparecieron → pending; el nodo Planner lleva clase decision.
    assert 'agent-flow-node active' in html_out
    assert html_out.count('agent-flow-node-wrap done') == 2
    assert 'decision' in html_out
    assert 'decidió: usar GraphRAG' in html_out


def test_agent_flow_html_finished_run_has_no_active_node():
    from ui.interface import _render_agent_flow_html

    events = [
        {"stage": Stage.INICIO, "message": "arranque", "timestamp": "10:00:00"},
        {"stage": Stage.RAG, "message": "ok", "timestamp": "10:00:01"},
        {"stage": Stage.GENERANDO, "message": "ok", "timestamp": "10:00:02"},
        {"stage": Stage.TTS, "message": "ok", "timestamp": "10:00:03"},
        {"stage": Stage.FIN, "message": "listo", "timestamp": "10:00:04"},
    ]
    html_out = _render_agent_flow_html(events)
    assert 'agent-flow-node active' not in html_out
    assert 'agent-flow-line flowing' not in html_out


def test_agent_flow_html_empty_events_all_pending():
    from ui.interface import _render_agent_flow_html
    html_out = _render_agent_flow_html([])
    assert 'agent-flow-node active' not in html_out
    assert 'agent-flow-node-wrap done' not in html_out


def test_planner_agent_decides_graph_when_tool_called(monkeypatch):
    from agents.planner_agent import PlannerAgent
    import agents.planner_agent as planner_module

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"message": {"content": "", "tool_calls": [
                {"function": {"name": "buscar_relaciones_grafo", "arguments": {"query": "x"}}}
            ]}}

    monkeypatch.setattr(planner_module.requests, "post", lambda *a, **k: FakeResponse())

    log = LogAgent()
    planner = PlannerAgent(log)
    assert planner.should_use_graph("¿Qué relación hay entre X e Y?") is True
    assert "usar GraphRAG" in log.get_all()


def test_planner_agent_decides_vector_only_when_no_tool_call(monkeypatch):
    from agents.planner_agent import PlannerAgent
    import agents.planner_agent as planner_module

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"message": {"content": "no hace falta la herramienta", "tool_calls": None}}

    monkeypatch.setattr(planner_module.requests, "post", lambda *a, **k: FakeResponse())

    log = LogAgent()
    planner = PlannerAgent(log)
    assert planner.should_use_graph("¿Cuál es la tarifa del IVA?") is False
    assert "solo RAG vectorial" in log.get_all()


def test_planner_agent_falls_back_to_false_on_connection_error(monkeypatch):
    import requests
    from agents.planner_agent import PlannerAgent
    import agents.planner_agent as planner_module

    def raise_connection_error(*a, **k):
        raise requests.exceptions.ConnectionError("Ollama no disponible")

    monkeypatch.setattr(planner_module.requests, "post", raise_connection_error)

    log = LogAgent()
    planner = PlannerAgent(log)
    assert planner.should_use_graph("¿Cuál es la tarifa del IVA?") is False


def test_planner_agent_falls_back_to_false_on_timeout(monkeypatch):
    import requests
    from agents.planner_agent import PlannerAgent
    import agents.planner_agent as planner_module

    def raise_timeout(*a, **k):
        raise requests.exceptions.Timeout("timeout")

    monkeypatch.setattr(planner_module.requests, "post", raise_timeout)

    log = LogAgent()
    planner = PlannerAgent(log)
    assert planner.should_use_graph("¿Cuál es la tarifa del IVA?") is False


def test_planner_agent_falls_back_to_false_on_malformed_response(monkeypatch):
    from agents.planner_agent import PlannerAgent
    import agents.planner_agent as planner_module

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {}  # sin "message" — respuesta inesperada

    monkeypatch.setattr(planner_module.requests, "post", lambda *a, **k: FakeResponse())

    log = LogAgent()
    planner = PlannerAgent(log)
    assert planner.should_use_graph("¿Cuál es la tarifa del IVA?") is False


def test_response_agent_builds_message():
    from agents.response_agent import ResponseAgent
    log = LogAgent()
    agent = ResponseAgent(log)

    rag_context = [
        {
            "text": "Art. 65.- La tarifa del IVA es del 15%.",
            "similarity": 0.85,
            "id": "iva_lorti_0010",
            "metadata": {
                "doc_name": "Ley de Régimen Tributario Interno",
                "tipo_normativa": "Ley / Normativa",
                "año": "2024",
                "pagina": "45",
                "articulo_seccion": "Art. 65",
            },
        }
    ]

    msg = agent._build_user_message(
        query="¿Cuál es la tarifa del IVA?",
        rag_context=rag_context,
        visual_description="",
    )

    # Formato actual (ver docstring de response_agent): encabezado
    # "CONTEXTO NORMATIVO SRI:" y etiquetas neutras "[N]" — a propósito
    # NO se inyecta doc_name/metadata en el prompt (el modelo los echaba
    # en el output); las fuentes se construyen en Python aparte.
    assert "CONTEXTO NORMATIVO SRI:" in msg
    assert "[1]" in msg
    assert "Art. 65" in msg          # vive en el texto del chunk
    assert "15%" in msg
    assert "PREGUNTA: ¿Cuál es la tarifa del IVA?" in msg
    assert "Ley de Régimen Tributario Interno" not in msg  # metadata fuera del prompt, por diseño


def _rag_context_ejemplo():
    return [
        {
            "text": "Art. 65.- La tarifa del IVA es del 15%.",
            "similarity": 0.85,
            "id": "iva_lorti_0010",
            "metadata": {
                "doc_name": "Ley de Régimen Tributario Interno",
                "tipo_normativa": "Ley / Normativa",
                "año": "2024",
                "pagina": "45",
                "articulo_seccion": "Art. 65",
            },
        },
        {   # segundo chunk del MISMO doc — debe deduplicarse en fuentes
            "text": "Otro fragmento de la misma ley.",
            "similarity": 0.70,
            "id": "iva_lorti_0011",
            "metadata": {
                "doc_name": "Ley de Régimen Tributario Interno",
                "tipo_normativa": "Ley / Normativa",
                "año": "2024",
                "pagina": "46",
                "articulo_seccion": "",
            },
        },
    ]


def test_response_agent_collect_sources_structured():
    from agents.response_agent import ResponseAgent
    sources = ResponseAgent._collect_sources(_rag_context_ejemplo())

    assert len(sources) == 1  # deduplicado por doc
    s = sources[0]
    assert s["num"] == "1"
    assert s["doc"] == "Ley de Régimen Tributario Interno"
    assert s["tipo"] == "Ley / Normativa"
    assert s["año"] == "2024"
    assert s["articulo"] == "Art. 65"
    assert s["pagina"] == "45"
    assert s["sim"] == 0.85


def test_response_agent_side_channel_after_generate(monkeypatch):
    from agents.response_agent import ResponseAgent, SOURCES_SEPARATOR
    import agents.response_agent as ra_module

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"message": {"content": "La tarifa del IVA es del 15%."}}

    monkeypatch.setattr(ra_module.requests, "post", lambda *a, **k: FakeResponse())

    agent = ResponseAgent(LogAgent())
    final = agent.generate(query="¿Tarifa del IVA?", rag_context=_rag_context_ejemplo())

    # El string completo mantiene el formato del chat (respuesta + separador + fuentes)
    assert final.startswith("La tarifa del IVA es del 15%.")
    assert SOURCES_SEPARATOR in final
    assert "FUENTES CONSULTADAS" in final

    # Side-channel: respuesta limpia y fuentes estructuradas, sin re-parsear texto
    assert agent.last_answer == "La tarifa del IVA es del 15%."
    assert len(agent.last_sources) == 1
    assert agent.last_sources[0]["doc"] == "Ley de Régimen Tributario Interno"


def test_response_agent_side_channel_on_error(monkeypatch):
    import requests
    from agents.response_agent import ResponseAgent
    import agents.response_agent as ra_module

    def raise_connection_error(*a, **k):
        raise requests.exceptions.ConnectionError("sin ollama")

    monkeypatch.setattr(ra_module.requests, "post", raise_connection_error)

    agent = ResponseAgent(LogAgent())
    agent.last_sources = [{"doc": "stale"}]  # simula consulta anterior
    result = agent.generate(query="x", rag_context=[])

    assert result.startswith("[ERROR]")
    assert agent.last_answer == result   # el error también queda legible
    assert agent.last_sources == []      # sin fuentes stale de la consulta anterior


def test_vision_agent_returns_empty_on_connection_error(monkeypatch):
    import requests
    from PIL import Image
    from agents.vision_agent import VisionAgent
    import agents.vision_agent as va_module

    def raise_connection_error(*a, **k):
        raise requests.exceptions.ConnectionError("sin ollama")

    monkeypatch.setattr(va_module.requests, "post", raise_connection_error)

    agent = VisionAgent(LogAgent())
    result = agent.analyze(Image.new("RGB", (50, 50)))
    # "" en error — nunca un sentinela "[...]" que fluya al prompt como dato
    assert result == ""


def test_vision_agent_returns_empty_on_timeout(monkeypatch):
    import requests
    from PIL import Image
    from agents.vision_agent import VisionAgent
    import agents.vision_agent as va_module

    def raise_timeout(*a, **k):
        raise requests.exceptions.Timeout("timeout")

    monkeypatch.setattr(va_module.requests, "post", raise_timeout)

    agent = VisionAgent(LogAgent())
    assert agent.analyze(Image.new("RGB", (50, 50))) == ""


def test_refinement_memory_similar_returns_closest_above_threshold(tmp_path):
    from agents.refinement_memory import RefinementMemory

    class FakeRag:
        def _embed_text(self, text):
            # Vectores 2D fijos y conocidos — similitud coseno predecible
            # sin cargar OpenCLIP real.
            return {
                "rechazada cercana": [1.0, 0.1],
                "rechazada lejana": [0.0, 1.0],
                "consulta nueva": [1.0, 0.0],
            }[text]

    path = tmp_path / "refinement_memory.json"
    mem = RefinementMemory(FakeRag(), LogAgent(), path=str(path))
    mem.record("rechazada cercana", "muy ambigua", "pregunta corregida cercana")
    mem.record("rechazada lejana", "otro motivo", "pregunta corregida lejana")

    results = mem.similar("consulta nueva", top_k=1, min_similarity=0.5)
    assert len(results) == 1
    assert results[0]["approved_query"] == "pregunta corregida cercana"


def test_refinement_memory_similar_empty_when_no_file(tmp_path):
    from agents.refinement_memory import RefinementMemory

    class FakeRag:
        def _embed_text(self, text):
            return [1.0, 0.0]

    path = tmp_path / "no_existe.json"
    mem = RefinementMemory(FakeRag(), LogAgent(), path=str(path))
    assert mem.similar("cualquier cosa") == []


def test_refinement_memory_persists_to_disk(tmp_path):
    from agents.refinement_memory import RefinementMemory

    class FakeRag:
        def _embed_text(self, text):
            return [1.0, 0.0]

    path = tmp_path / "refinement_memory.json"
    mem = RefinementMemory(FakeRag(), LogAgent(), path=str(path))
    mem.record("rechazada", "motivo", "aprobada")

    reloaded = RefinementMemory(FakeRag(), LogAgent(), path=str(path))
    assert len(reloaded.similar("rechazada", min_similarity=0.99)) == 1


def test_query_refiner_agent_rewrites_query(monkeypatch):
    from agents.query_refiner_agent import QueryRefinerAgent
    import agents.query_refiner_agent as refiner_module

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"message": {"content": "¿Cuál es la tarifa del IVA para servicios en Ecuador?"}}

    monkeypatch.setattr(refiner_module.requests, "post", lambda *a, **k: FakeResponse())

    log = LogAgent()
    refiner = QueryRefinerAgent(log)
    result = refiner.refine("iva cuanto")
    assert result == "¿Cuál es la tarifa del IVA para servicios en Ecuador?"
    assert "Refinada" in log.get_all()


def test_query_refiner_agent_falls_back_to_original_on_connection_error(monkeypatch):
    import requests
    from agents.query_refiner_agent import QueryRefinerAgent
    import agents.query_refiner_agent as refiner_module

    def raise_connection_error(*a, **k):
        raise requests.exceptions.ConnectionError("sin ollama")

    monkeypatch.setattr(refiner_module.requests, "post", raise_connection_error)

    log = LogAgent()
    refiner = QueryRefinerAgent(log)
    assert refiner.refine("iva cuanto") == "iva cuanto"


def test_query_refiner_agent_uses_memory_examples(monkeypatch):
    from agents.query_refiner_agent import QueryRefinerAgent
    import agents.query_refiner_agent as refiner_module

    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"message": {"content": "pregunta reformulada"}}

    def fake_post(url, json, timeout):
        captured["messages"] = json["messages"]
        return FakeResponse()

    monkeypatch.setattr(refiner_module.requests, "post", fake_post)

    class FakeMemory:
        def similar(self, query):
            return [{"rejected_query": "x", "motivo": "ambigua", "approved_query": "x mejor"}]

    log = LogAgent()
    refiner = QueryRefinerAgent(log, refinement_memory=FakeMemory())
    refiner.refine("pregunta vaga")

    user_content = captured["messages"][1]["content"]
    assert "x mejor" in user_content
    assert "ambigua" in user_content


def test_query_validator_agent_approves_when_no_tool_call(monkeypatch):
    from agents.query_validator_agent import QueryValidatorAgent
    import agents.query_validator_agent as validator_module

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"message": {"content": "ok", "tool_calls": None}}

    monkeypatch.setattr(validator_module.requests, "post", lambda *a, **k: FakeResponse())

    class FakeRag:
        def retrieve(self, query, top_k=None):
            return [{"text": "Art. 65.- tarifa 15%", "similarity": 0.8, "id": "x", "metadata": {}}]

    validator = QueryValidatorAgent(LogAgent(), FakeRag())
    result = validator.validate("¿Cuál es la tarifa del IVA?")
    assert result["approved"] is True
    assert result["reason"] == ""
    assert len(result["chunks"]) == 1


def test_query_validator_agent_rejects_with_reason_when_tool_called(monkeypatch):
    from agents.query_validator_agent import QueryValidatorAgent
    import agents.query_validator_agent as validator_module

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"message": {"content": "", "tool_calls": [
                {"function": {"name": "rechazar_pregunta", "arguments": {"motivo": "pregunta muy ambigua"}}}
            ]}}

    monkeypatch.setattr(validator_module.requests, "post", lambda *a, **k: FakeResponse())

    class FakeRag:
        def retrieve(self, query, top_k=None):
            return []

    validator = QueryValidatorAgent(LogAgent(), FakeRag())
    result = validator.validate("algo")
    assert result["approved"] is False
    assert result["reason"] == "pregunta muy ambigua"
    assert result["chunks"] == []


def test_query_validator_agent_approves_by_default_on_connection_error(monkeypatch):
    import requests
    from agents.query_validator_agent import QueryValidatorAgent
    import agents.query_validator_agent as validator_module

    def raise_connection_error(*a, **k):
        raise requests.exceptions.ConnectionError("sin ollama")

    monkeypatch.setattr(validator_module.requests, "post", raise_connection_error)

    class FakeRag:
        def retrieve(self, query, top_k=None):
            return []

    validator = QueryValidatorAgent(LogAgent(), FakeRag())
    result = validator.validate("algo")
    assert result["approved"] is True


def test_run_refinement_loop_converges_on_first_approval():
    from agents.coordinator import consume_refinement_loop

    class ApprovingRefiner:
        memory = None

        def refine(self, query, rejection_reason=""):
            return query + " refinada"

    class ApprovingValidator:
        def validate(self, query):
            return {"approved": True, "reason": "", "chunks": [{"text": "x"}]}

    log = LogAgent()
    final_query, chunks, n_iterations = consume_refinement_loop(
        ApprovingRefiner(), ApprovingValidator(), "pregunta", log,
    )
    assert final_query == "pregunta refinada"
    assert chunks == [{"text": "x"}]
    assert n_iterations == 1


def test_run_refinement_loop_forces_pass_at_max_iterations():
    from agents.coordinator import consume_refinement_loop

    class RejectingRefiner:
        memory = None

        def refine(self, query, rejection_reason=""):
            return query + "+"

    class RejectingValidator:
        def validate(self, query):
            return {"approved": False, "reason": "nunca alcanza", "chunks": []}

    log = LogAgent()
    final_query, chunks, n_iterations = consume_refinement_loop(
        RejectingRefiner(), RejectingValidator(), "pregunta", log, max_iterations=2,
    )
    assert final_query == "pregunta++"
    assert n_iterations == 2


def test_run_refinement_loop_records_memory_after_rejection_then_approval():
    from agents.coordinator import consume_refinement_loop

    recorded = {}

    class FakeMemory:
        def record(self, rejected_query, motivo, approved_query):
            recorded["args"] = (rejected_query, motivo, approved_query)

    class Refiner:
        memory = FakeMemory()

        def __init__(self):
            self.calls = 0

        def refine(self, query, rejection_reason=""):
            self.calls += 1
            return f"version-{self.calls}"

    class Validator:
        def __init__(self):
            self.calls = 0

        def validate(self, query):
            self.calls += 1
            if self.calls == 1:
                return {"approved": False, "reason": "poco clara", "chunks": []}
            return {"approved": True, "reason": "", "chunks": [{"text": "y"}]}

    log = LogAgent()
    final_query, chunks, n_iterations = consume_refinement_loop(
        Refiner(), Validator(), "pregunta", log, max_iterations=2,
    )
    assert final_query == "version-2"
    assert n_iterations == 2
    assert recorded["args"] == ("version-1", "poco clara", "version-2")


def test_response_agent_keeps_legit_brackets_in_visual_description():
    from agents.response_agent import ResponseAgent

    agent = ResponseAgent(LogAgent())
    # Descripción legítima con corchetes (checkbox de formulario) — antes
    # el filtro '"[" not in' la descartaba como si visión hubiera fallado.
    msg = agent._build_user_message(
        query="¿Qué significa esta casilla?",
        rag_context=[],
        visual_description="Formulario 104 con casilla [X] marcada en el campo [RUC]",
    )
    assert "Formulario 104 con casilla [X]" in msg
