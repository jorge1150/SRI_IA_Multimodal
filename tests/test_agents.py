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
