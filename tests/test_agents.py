"""
test_agents.py — Pruebas de los agentes del sistema SRI IA Multimodal.
Uso: python -m pytest tests/test_agents.py -v
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.log_agent import LogAgent


def test_log_agent_basic():
    log = LogAgent()
    log.log("INICIO", "Sistema SRI iniciado.")
    log.log("RAG", "Buscando normativa.")
    output = log.get_all()
    assert "INICIO" in output
    assert "RAG" in output
    assert "Sistema SRI iniciado." in output


def test_log_agent_clear():
    log = LogAgent()
    log.log("INFO", "mensaje de prueba")
    log.clear()
    assert log.get_all() == ""


def test_log_agent_icons():
    log = LogAgent()
    entry = log.log("NORMATIVA", "Recuperando artículos.")
    assert "⚖️" in entry


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

    assert "Ley de Régimen Tributario Interno" in msg
    assert "Art. 65" in msg
    assert "15%" in msg
    assert "NORMATIVA RECUPERADA" in msg
