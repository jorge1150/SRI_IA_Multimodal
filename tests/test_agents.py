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


def test_extract_previous_exchange_empty_history_returns_none():
    from ui.interface import _extract_previous_exchange
    assert _extract_previous_exchange([]) == (None, None)
    assert _extract_previous_exchange(None) == (None, None)


def test_extract_previous_exchange_plain_text_turn():
    from ui.interface import _extract_previous_exchange
    history = [
        {"role": "user", "content": "¿Cómo obtengo el RUC como persona natural?"},
        {"role": "assistant", "content": "Debes ingresar a SRI en Línea..."},
    ]
    prev_q, prev_a = _extract_previous_exchange(history)
    assert prev_q == "¿Cómo obtengo el RUC como persona natural?"
    assert prev_a == "Debes ingresar a SRI en Línea..."


def test_extract_previous_exchange_filters_multimedia_parts():
    from ui.interface import _extract_previous_exchange
    history = [
        {"role": "user", "content": [{"path": "/tmp/img.png", "is_stream": False}, "¿qué formulario es este?"]},
        {"role": "assistant", "content": "Es el Formulario 104."},
    ]
    prev_q, prev_a = _extract_previous_exchange(history)
    assert prev_q == "¿qué formulario es este?"
    assert prev_a == "Es el Formulario 104."


def test_extract_previous_exchange_only_media_returns_none_query():
    from ui.interface import _extract_previous_exchange
    history = [
        {"role": "user", "content": [{"path": "/tmp/img.png", "is_stream": False}]},
        {"role": "assistant", "content": "Es el Formulario 104."},
    ]
    prev_q, prev_a = _extract_previous_exchange(history)
    assert prev_q is None
    assert prev_a == "Es el Formulario 104."


def test_extract_previous_exchange_uses_last_turn_only():
    from ui.interface import _extract_previous_exchange
    history = [
        {"role": "user", "content": "primera pregunta"},
        {"role": "assistant", "content": "primera respuesta"},
        {"role": "user", "content": "segunda pregunta"},
        {"role": "assistant", "content": "segunda respuesta"},
    ]
    prev_q, prev_a = _extract_previous_exchange(history)
    assert prev_q == "segunda pregunta"
    assert prev_a == "segunda respuesta"


def test_agent_flow_html_shows_backline_after_rejection():
    from ui.interface import _render_agent_flow_html

    events = [
        {"stage": Stage.INICIO, "message": "arranque", "timestamp": "10:00:00"},
        {"stage": Stage.REFINADOR, "message": "Refinando pregunta (vuelta 1)...", "timestamp": "10:00:01"},
        {"stage": Stage.VALIDADOR, "message": "✗ Rechazada (0 fragmento(s) encontrados): poco clara", "timestamp": "10:00:02"},
        {"stage": Stage.REFINADOR, "message": "Refinando pregunta (vuelta 2)...", "timestamp": "10:00:03"},
        {"stage": Stage.VALIDADOR, "message": "✓ Aprobada (2 fragmento(s) encontrados).", "timestamp": "10:00:04"},
        {"stage": Stage.RAG, "message": "ok", "timestamp": "10:00:05"},
        {"stage": Stage.FIN, "message": "listo", "timestamp": "10:00:06"},
    ]
    html_out = _render_agent_flow_html(events)
    assert "agent-flow-backline" in html_out
    assert "×1" in html_out
    # Terminada la consulta, la línea de retroceso queda fija, no animada.
    assert "agent-flow-backline done" in html_out
    assert "agent-flow-backline flowing" not in html_out


def test_agent_flow_html_no_backline_when_approved_on_first_try():
    from ui.interface import _render_agent_flow_html

    events = [
        {"stage": Stage.INICIO, "message": "arranque", "timestamp": "10:00:00"},
        {"stage": Stage.REFINADOR, "message": "Refinando pregunta (vuelta 1)...", "timestamp": "10:00:01"},
        {"stage": Stage.VALIDADOR, "message": "✓ Aprobada (2 fragmento(s) encontrados).", "timestamp": "10:00:02"},
        {"stage": Stage.RAG, "message": "ok", "timestamp": "10:00:03"},
        {"stage": Stage.FIN, "message": "listo", "timestamp": "10:00:04"},
    ]
    html_out = _render_agent_flow_html(events)
    assert "agent-flow-backline" not in html_out


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
        def _load_clip(self):
            pass

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
        def _load_clip(self):
            pass

        def _embed_text(self, text):
            return [1.0, 0.0]

    path = tmp_path / "no_existe.json"
    mem = RefinementMemory(FakeRag(), LogAgent(), path=str(path))
    assert mem.similar("cualquier cosa") == []


def test_refinement_memory_persists_to_disk(tmp_path):
    from agents.refinement_memory import RefinementMemory

    class FakeRag:
        def _load_clip(self):
            pass

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


def test_query_refiner_agent_condenses_followup_with_conversation_context(monkeypatch):
    """
    ADR-0010: un follow-up ambiguo ("dime los pasos") debe recibir el
    intercambio anterior en el prompt para poder condensarse en una
    pregunta autocontenida (corrige el bug real: "¿Cómo obtengo el RUC
    como persona natural?" + "Dime los pasos que debo seguir" perdía el
    tema RUC/persona natural por completo).
    """
    from agents.query_refiner_agent import QueryRefinerAgent
    import agents.query_refiner_agent as refiner_module

    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"message": {"content": "¿cuáles son los pasos para obtener el RUC como persona natural?"}}

    def fake_post(url, json, timeout):
        captured["messages"] = json["messages"]
        return FakeResponse()

    monkeypatch.setattr(refiner_module.requests, "post", fake_post)

    log = LogAgent()
    refiner = QueryRefinerAgent(log)
    refiner.refine(
        "Dime los pasos que debo seguir",
        previous_query="¿Cómo obtengo el RUC como persona natural?",
        previous_answer="Debes ingresar a SRI en Línea y completar el formulario.",
    )

    user_content = captured["messages"][1]["content"]
    assert "¿Cómo obtengo el RUC como persona natural?" in user_content
    assert "SRI en Línea" in user_content


def test_query_refiner_agent_without_previous_query_omits_context_block(monkeypatch):
    """Sin previous_query, el prompt no debe mencionar ningún contexto de
    conversación — mismo comportamiento que antes de ADR-0010."""
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

    log = LogAgent()
    refiner = QueryRefinerAgent(log)
    refiner.refine("¿Cuál es la tarifa del IVA?")

    user_content = captured["messages"][1]["content"]
    assert "CONTEXTO DE LA CONVERSACIÓN ANTERIOR" not in user_content


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


def test_query_validator_agent_off_topic_tool_short_circuits(monkeypatch):
    from agents.query_validator_agent import QueryValidatorAgent
    import agents.query_validator_agent as validator_module

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"message": {"content": "", "tool_calls": [
                {"function": {"name": "pregunta_fuera_de_dominio", "arguments": {}}}
            ]}}

    monkeypatch.setattr(validator_module.requests, "post", lambda *a, **k: FakeResponse())

    class FakeRag:
        def retrieve(self, query, top_k=None):
            return []

    recorded = []

    class FakeOffTopicMemory:
        def similar(self, query, top_k=1):
            return []

        def record(self, query):
            recorded.append(query)

    validator = QueryValidatorAgent(LogAgent(), FakeRag(), FakeOffTopicMemory())
    result = validator.validate("¿qué clima hace hoy?")
    assert result["approved"] is False
    assert result["off_topic"] is True
    assert recorded == ["¿qué clima hace hoy?"]


def test_query_validator_agent_off_topic_fast_path_skips_ollama(monkeypatch):
    from agents.query_validator_agent import QueryValidatorAgent
    import agents.query_validator_agent as validator_module

    def fail_if_called(*a, **k):
        raise AssertionError("no debería llamar a Ollama si hay match en OffTopicMemory")

    monkeypatch.setattr(validator_module.requests, "post", fail_if_called)

    class FakeRag:
        def retrieve(self, query, top_k=None):
            raise AssertionError("no debería retrievar si el fast-path corta antes")

    class FakeOffTopicMemory:
        def similar(self, query, top_k=1):
            return [{"query": "pregunta parecida ya vista"}]

    validator = QueryValidatorAgent(LogAgent(), FakeRag(), FakeOffTopicMemory())
    result = validator.validate("otra pregunta sin sentido")
    assert result["approved"] is False
    assert result["off_topic"] is True
    assert result["chunks"] == []


def test_query_validator_agent_rejection_does_not_flag_off_topic(monkeypatch):
    from agents.query_validator_agent import QueryValidatorAgent
    import agents.query_validator_agent as validator_module

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"message": {"content": "", "tool_calls": [
                {"function": {"name": "rechazar_pregunta", "arguments": {"motivo": "muy ambigua"}}}
            ]}}

    monkeypatch.setattr(validator_module.requests, "post", lambda *a, **k: FakeResponse())

    class FakeRag:
        def retrieve(self, query, top_k=None):
            return []

    validator = QueryValidatorAgent(LogAgent(), FakeRag())
    result = validator.validate("algo tributario mal formulado")
    assert result["approved"] is False
    assert result["off_topic"] is False


def test_check_off_topic_flags_without_retrieval(monkeypatch):
    """check_off_topic() no debe tocar RAGAgent.retrieve — es el chequeo
    liviano previo al loop, sobre la pregunta ORIGINAL (ver ADR-0007)."""
    from agents.query_validator_agent import QueryValidatorAgent
    import agents.query_validator_agent as validator_module

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"message": {"content": "", "tool_calls": [
                {"function": {"name": "pregunta_fuera_de_dominio", "arguments": {}}}
            ]}}

    monkeypatch.setattr(validator_module.requests, "post", lambda *a, **k: FakeResponse())

    class FakeRag:
        def retrieve(self, query, top_k=None):
            raise AssertionError("check_off_topic no debería retrievar")

    validator = QueryValidatorAgent(LogAgent(), FakeRag())
    result = validator.check_off_topic("¿qué clima hace hoy?")
    assert result["off_topic"] is True
    assert "SRI" in result["reason"]


def test_check_off_topic_approves_when_no_tool_call(monkeypatch):
    from agents.query_validator_agent import QueryValidatorAgent
    import agents.query_validator_agent as validator_module

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"message": {"content": "", "tool_calls": None}}

    monkeypatch.setattr(validator_module.requests, "post", lambda *a, **k: FakeResponse())

    class FakeRag:
        def retrieve(self, query, top_k=None):
            raise AssertionError("check_off_topic no debería retrievar")

    validator = QueryValidatorAgent(LogAgent(), FakeRag())
    result = validator.check_off_topic("¿cuál es la tarifa del IVA?")
    assert result["off_topic"] is False


def test_check_off_topic_degrades_to_in_domain_on_connection_error(monkeypatch):
    import requests
    from agents.query_validator_agent import QueryValidatorAgent
    import agents.query_validator_agent as validator_module

    def raise_connection_error(*a, **k):
        raise requests.exceptions.ConnectionError("sin ollama")

    monkeypatch.setattr(validator_module.requests, "post", raise_connection_error)

    class FakeRag:
        def retrieve(self, query, top_k=None):
            raise AssertionError("check_off_topic no debería retrievar")

    validator = QueryValidatorAgent(LogAgent(), FakeRag())
    result = validator.check_off_topic("algo")
    assert result["off_topic"] is False


def test_check_off_topic_includes_conversation_context_in_prompt(monkeypatch):
    """
    ADR-0010: un follow-up genérico ("dime los pasos") no tiene palabras
    clave tributarias por sí solo — check_off_topic debe recibir el
    intercambio anterior para juzgar con el contexto real, no aislado
    (evita reintroducir el problema corregido en ADR-0007).
    """
    from agents.query_validator_agent import QueryValidatorAgent
    import agents.query_validator_agent as validator_module

    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"message": {"content": "", "tool_calls": None}}

    def fake_post(url, json, timeout):
        captured["messages"] = json["messages"]
        return FakeResponse()

    monkeypatch.setattr(validator_module.requests, "post", fake_post)

    class FakeRag:
        def retrieve(self, query, top_k=None):
            raise AssertionError("check_off_topic no debería retrievar")

    validator = QueryValidatorAgent(LogAgent(), FakeRag())
    result = validator.check_off_topic(
        "Dime los pasos que debo seguir",
        previous_query="¿Cómo obtengo el RUC como persona natural?",
        previous_answer="Debes ingresar a SRI en Línea...",
    )

    assert result["off_topic"] is False
    user_content = captured["messages"][0]["content"]
    assert "¿Cómo obtengo el RUC como persona natural?" in user_content


def test_planner_agent_captures_token_usage(monkeypatch):
    from agents.planner_agent import PlannerAgent
    import agents.planner_agent as planner_module

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"message": {"content": "", "tool_calls": None},
                    "prompt_eval_count": 40, "eval_count": 5}

    monkeypatch.setattr(planner_module.requests, "post", lambda *a, **k: FakeResponse())

    planner = PlannerAgent(LogAgent())
    planner.should_use_graph("¿Cuál es la tarifa del IVA?")
    assert planner.last_token_usage == {"prompt_tokens": 40, "completion_tokens": 5, "total_tokens": 45}


def test_query_refiner_agent_captures_token_usage(monkeypatch):
    from agents.query_refiner_agent import QueryRefinerAgent
    import agents.query_refiner_agent as refiner_module

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"message": {"content": "pregunta reformulada"},
                    "prompt_eval_count": 100, "eval_count": 12}

    monkeypatch.setattr(refiner_module.requests, "post", lambda *a, **k: FakeResponse())

    refiner = QueryRefinerAgent(LogAgent())
    refiner.refine("pregunta vaga")
    assert refiner.last_token_usage == {"prompt_tokens": 100, "completion_tokens": 12, "total_tokens": 112}


def test_query_validator_agent_captures_token_usage(monkeypatch):
    from agents.query_validator_agent import QueryValidatorAgent
    import agents.query_validator_agent as validator_module

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"message": {"content": "", "tool_calls": None},
                    "prompt_eval_count": 80, "eval_count": 3}

    monkeypatch.setattr(validator_module.requests, "post", lambda *a, **k: FakeResponse())

    class FakeRag:
        def retrieve(self, query, top_k=None):
            return []

    validator = QueryValidatorAgent(LogAgent(), FakeRag())
    validator.validate("¿cuál es la tarifa del IVA?")
    assert validator.last_token_usage == {"prompt_tokens": 80, "completion_tokens": 3, "total_tokens": 83}


def test_response_agent_captures_token_usage(monkeypatch):
    from agents.response_agent import ResponseAgent
    import agents.response_agent as ra_module

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"message": {"content": "La tarifa del IVA es del 15%."},
                    "prompt_eval_count": 200, "eval_count": 20}

    monkeypatch.setattr(ra_module.requests, "post", lambda *a, **k: FakeResponse())

    agent = ResponseAgent(LogAgent())
    agent.generate(query="¿Tarifa del IVA?", rag_context=[])
    assert agent.last_token_usage == {"prompt_tokens": 200, "completion_tokens": 20, "total_tokens": 220}


def test_off_topic_memory_matches_near_exact_repeat_only(tmp_path):
    """
    Match por texto normalizado (near-exact), NO por similitud CLIP — ver
    ADR-0007. Similitud coseno de OpenCLIP no discrimina preguntas cortas en
    español (medido: ~0.83-0.90 tanto entre parafraseos como entre temas
    distintos), lo que causaba que UNA sola entrada marcara cualquier
    pregunta tributaria real como fuera de dominio.
    """
    from agents.off_topic_memory import OffTopicMemory

    path = tmp_path / "off_topic_memory.json"
    mem = OffTopicMemory(LogAgent(), path=str(path))

    mem.record("¿Qué clima hace hoy?")

    # Variación trivial del mismo texto (mayúsculas/tildes/puntuación) -> match
    assert len(mem.similar("que clima hace hoy")) == 1

    # Pregunta distinta, mismo tema general -> NO debe matchear
    assert mem.similar("¿cómo está el clima en Quito mañana?") == []

    # Pregunta de otro dominio por completo -> tampoco
    assert mem.similar("¿cuál es la tarifa del IVA?") == []


def test_run_refinement_loop_converges_on_first_approval():
    from agents.coordinator import consume_refinement_loop

    class ApprovingRefiner:
        memory = None
        last_token_usage = {}

        def refine(self, query, rejection_reason="", **kwargs):
            return query + " refinada"

    class ApprovingValidator:
        last_token_usage = {}

        def check_off_topic(self, query, **kwargs):
            return {"off_topic": False, "reason": ""}

        def validate(self, query):
            return {"approved": True, "off_topic": False, "reason": "", "chunks": [{"text": "x"}]}

    log = LogAgent()
    result = consume_refinement_loop(
        ApprovingRefiner(), ApprovingValidator(), "pregunta", log,
    )
    assert result["final_query"] == "pregunta refinada"
    assert result["chunks"] == [{"text": "x"}]
    assert result["n_iterations"] == 1
    assert result["off_topic"] is False


def test_run_refinement_loop_forces_pass_at_max_iterations():
    from agents.coordinator import consume_refinement_loop

    class RejectingRefiner:
        memory = None
        last_token_usage = {}

        def refine(self, query, rejection_reason="", **kwargs):
            return query + "+"

    class RejectingValidator:
        last_token_usage = {}

        def check_off_topic(self, query, **kwargs):
            return {"off_topic": False, "reason": ""}

        def validate(self, query):
            return {"approved": False, "off_topic": False, "reason": "nunca alcanza", "chunks": []}

    log = LogAgent()
    result = consume_refinement_loop(
        RejectingRefiner(), RejectingValidator(), "pregunta", log, max_iterations=2,
    )
    assert result["final_query"] == "pregunta++"
    assert result["n_iterations"] == 2
    assert result["rejections"] == 2
    assert result["off_topic"] is False


def test_run_refinement_loop_records_memory_after_rejection_then_approval():
    from agents.coordinator import consume_refinement_loop

    recorded = {}

    class FakeMemory:
        def record(self, rejected_query, motivo, approved_query):
            recorded["args"] = (rejected_query, motivo, approved_query)

    class Refiner:
        memory = FakeMemory()
        last_token_usage = {}

        def __init__(self):
            self.calls = 0

        def refine(self, query, rejection_reason="", **kwargs):
            self.calls += 1
            return f"version-{self.calls}"

    class Validator:
        last_token_usage = {}

        def __init__(self):
            self.calls = 0

        def check_off_topic(self, query, **kwargs):
            return {"off_topic": False, "reason": ""}

        def validate(self, query):
            self.calls += 1
            if self.calls == 1:
                return {"approved": False, "off_topic": False, "reason": "poco clara", "chunks": []}
            return {"approved": True, "off_topic": False, "reason": "", "chunks": [{"text": "y"}]}

    log = LogAgent()
    result = consume_refinement_loop(
        Refiner(), Validator(), "pregunta", log, max_iterations=2,
    )
    assert result["final_query"] == "version-2"
    assert result["n_iterations"] == 2
    assert recorded["args"] == ("version-1", "poco clara", "version-2")


def test_run_refinement_loop_short_circuits_on_off_topic_before_refining():
    """
    El guardrail de dominio corre sobre la pregunta ORIGINAL, ANTES de
    entrar al loop — el Refinador no debe tocarla en absoluto (ver
    ADR-0007, corrige el bug real donde el Refinador reescribía preguntas
    ajenas al SRI hasta que sonaban tributarias).
    """
    from agents.coordinator import consume_refinement_loop

    class Refiner:
        memory = None
        last_token_usage = {}

        def __init__(self):
            self.calls = 0

        def refine(self, query, rejection_reason="", **kwargs):
            self.calls += 1
            return query

    class OffTopicValidator:
        last_token_usage = {}

        def check_off_topic(self, query, **kwargs):
            return {
                "off_topic": True,
                "reason": "Esta pregunta no tiene relación con la normativa tributaria del SRI Ecuador.",
            }

        def validate(self, query):
            raise AssertionError("validate() no debería llamarse — el gate previo ya cortó")

    refiner = Refiner()
    log = LogAgent()
    result = consume_refinement_loop(refiner, OffTopicValidator(), "qué clima hace hoy", log, max_iterations=3)

    assert result["off_topic"] is True
    assert refiner.calls == 0  # el Refinador nunca llega a tocar la pregunta
    assert result["n_iterations"] == 0
    assert result["final_query"] == "qué clima hace hoy"
    assert "SRI" in result["reason"]


def test_run_refinement_loop_proceeds_when_pre_check_passes():
    """El gate previo solo corta si es off_topic — si pasa, el loop sigue normal."""
    from agents.coordinator import consume_refinement_loop

    class Refiner:
        memory = None
        last_token_usage = {}

        def refine(self, query, rejection_reason="", **kwargs):
            return query + " refinada"

    class Validator:
        last_token_usage = {}

        def check_off_topic(self, query, **kwargs):
            return {"off_topic": False, "reason": ""}

        def validate(self, query):
            return {"approved": True, "off_topic": False, "reason": "", "chunks": [{"text": "z"}]}

    log = LogAgent()
    result = consume_refinement_loop(Refiner(), Validator(), "pregunta", log)

    assert result["off_topic"] is False
    assert result["final_query"] == "pregunta refinada"
    assert result["n_iterations"] == 1


def test_run_refinement_loop_propagates_context_to_check_off_topic_always_and_refine_only_first_vuelta():
    """
    ADR-0010: previous_query/previous_answer llegan a check_off_topic()
    siempre (la ambigüedad de un follow-up es sobre la pregunta ORIGINAL),
    pero solo a refine() en la primera vuelta — una vez condensada la
    pregunta, las vueltas de rechazo ya trabajan sobre texto autocontenido.
    """
    from agents.coordinator import consume_refinement_loop

    off_topic_calls = []
    refine_calls = []

    class Refiner:
        memory = None
        last_token_usage = {}

        def __init__(self):
            self.calls = 0

        def refine(self, query, rejection_reason="", previous_query=None, previous_answer=None):
            self.calls += 1
            refine_calls.append((previous_query, previous_answer))
            return f"version-{self.calls}"

    class Validator:
        last_token_usage = {}

        def __init__(self):
            self.calls = 0

        def check_off_topic(self, query, previous_query=None, previous_answer=None):
            off_topic_calls.append((previous_query, previous_answer))
            return {"off_topic": False, "reason": ""}

        def validate(self, query):
            self.calls += 1
            if self.calls == 1:
                return {"approved": False, "off_topic": False, "reason": "poco clara", "chunks": []}
            return {"approved": True, "off_topic": False, "reason": "", "chunks": []}

    log = LogAgent()
    result = consume_refinement_loop(
        Refiner(), Validator(), "Dime los pasos que debo seguir", log, max_iterations=2,
        previous_query="¿Cómo obtengo el RUC como persona natural?",
        previous_answer="Debes ingresar a SRI en Línea...",
    )

    assert result["n_iterations"] == 2
    # check_off_topic recibe el contexto (única llamada, antes del loop)
    assert off_topic_calls == [("¿Cómo obtengo el RUC como persona natural?", "Debes ingresar a SRI en Línea...")]
    # refine() solo recibe el contexto en la vuelta 1; vuelta 2 sin contexto
    assert refine_calls[0] == ("¿Cómo obtengo el RUC como persona natural?", "Debes ingresar a SRI en Línea...")
    assert refine_calls[1] == (None, None)


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
