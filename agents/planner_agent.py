"""
planner_agent.py — Agente Planificador
Decide, vía tool-calling nativo de Ollama, si una consulta necesita
GraphRAG además del RAG vectorial (que siempre corre). Es el único punto
del pipeline donde el LLM decide dinámicamente en vez de seguir una regla
fija programada — el resto de agentes (STT, Visión, RAG, Respuesta, TTS)
ejecutan una tarea determinística, no deciden nada.

Activado con config.USE_AGENTIC_PLANNER (default False). Mientras está en
False, CoordinatorAgent sigue usando el modo "auto" fijo de HybridRetriever.
"""

import requests

from config import OLLAMA_URL, LLM_MODEL, PLANNER_TIMEOUT
from .log_agent import LogAgent, Stage

# Una sola herramienta: si el modelo la llama, la consulta necesita grafo.
# Si no la llama, alcanza con RAG vectorial. La decisión es la presencia
# o ausencia del tool_call, no un parámetro booleano dentro de él — más
# simple y más confiable de parsear con un modelo chico (3B).
_GRAPH_TOOL = {
    "type": "function",
    "function": {
        "name": "buscar_relaciones_grafo",
        "description": (
            "Busca relaciones estructuradas entre entidades tributarias "
            "(quién debe qué a quién, qué impuesto aplica a qué sujeto, qué "
            "obligaciones tiene cada actor). Llama a esta función SOLO si la "
            "pregunta pide explícitamente una relación, obligación o conexión "
            "entre dos o más conceptos tributarios. NO la llames para "
            "preguntas sobre definiciones simples, tarifas puntuales o el "
            "texto de un artículo."
        ),
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "la consulta a buscar en el grafo"}},
            "required": ["query"],
        },
    },
}


class PlannerAgent:
    """
    Decide sí/no usar GraphRAG para una consulta puntual.
    Ante cualquier falla (Ollama caído, timeout, respuesta sin tool_calls
    parseable) degrada a False — mismo criterio de "vector siempre corre,
    grafo es el complemento opcional" que ya usa HybridRetriever cuando el
    grafo no está disponible (ver _init_graph_retriever en coordinator.py).
    """

    def __init__(self, log_agent: LogAgent):
        self.log = log_agent

    def should_use_graph(self, query: str, model: str = None) -> bool:
        """
        model: modelo Ollama a usar para esta decisión puntual (default:
        config.LLM_MODEL). Permite a scripts/run_benchmark.py comparar el
        pipeline agéntico completo con distintos modelos, igual que
        ResponseAgent.generate(model=...).
        """
        model = model or LLM_MODEL
        try:
            resp = requests.post(
                f"{OLLAMA_URL}/api/chat",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": query}],
                    "tools": [_GRAPH_TOOL],
                    "stream": False,
                    "options": {"temperature": 0.1},
                },
                timeout=PLANNER_TIMEOUT,
            )
            resp.raise_for_status()
            tool_calls = resp.json().get("message", {}).get("tool_calls") or []
            decision = len(tool_calls) > 0

            self.log.log(
                "PLANNER",
                f"Decidió: {'usar GraphRAG además del RAG vectorial' if decision else 'solo RAG vectorial'}.",
            )
            return decision

        except requests.exceptions.ConnectionError:
            self.log.log(Stage.PLANNER, "⚠ Ollama no disponible — usando solo RAG vectorial.")
            return False
        except requests.exceptions.Timeout:
            self.log.log(Stage.PLANNER, f"⚠ Timeout después de {PLANNER_TIMEOUT}s — usando solo RAG vectorial.")
            return False
        except Exception as exc:
            self.log.log(Stage.PLANNER, f"⚠ Error decidiendo estrategia: {exc} — usando solo RAG vectorial.")
            return False
