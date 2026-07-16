"""
query_validator_agent.py — Agente Validador de Consultas
Decide, vía tool-calling nativo de Ollama, si una pregunta ya refinada
alcanza para responder correctamente — validando contra un retrieval de
prueba real (RAGAgent.retrieve, vector_only), no solo la forma lingüística
de la pregunta. Corre en loop con QueryRefinerAgent — ver
agents/coordinator.py::run_refinement_loop.

Mismo patrón de decisión que PlannerAgent: la presencia o ausencia de un
único tool_call decide, no un parámetro booleano dentro de la respuesta —
más confiable de parsear con un modelo de 3B (ver ADR-0005, ADR-0006).

Activado con config.USE_AGENTIC_PLANNER (mismo flag que PlannerAgent y
QueryRefinerAgent).
"""

import requests

from config import OLLAMA_URL, LLM_MODEL, VALIDATOR_TIMEOUT
from .log_agent import LogAgent, Stage

_REJECT_TOOL = {
    "type": "function",
    "function": {
        "name": "rechazar_pregunta",
        "description": (
            "Llama a esta función SOLO si la pregunta es imposible de responder "
            "con los fragmentos dados: está vacía o incoherente, no tiene "
            "relación con normativa tributaria del SRI Ecuador, o NINGUNO de "
            "los fragmentos recuperados es relevante al tema de la pregunta. "
            "NO la llames solo porque la pregunta es amplia o los fragmentos no "
            "cubren absolutamente todos los detalles posibles — una pregunta "
            "general ('¿qué medidas... ?', '¿qué obligaciones... ?') es válida "
            "y respondible con los fragmentos relevantes que sí haya, aunque no "
            "los liste todos. Rechazar por amplitud hace que el sistema nunca "
            "converja."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "motivo": {
                    "type": "string",
                    "description": "por qué no alcanza, en una frase breve",
                },
            },
            "required": ["motivo"],
        },
    },
}


class QueryValidatorAgent:
    """
    Decide sí/no si una pregunta refinada alcanza para responder, contra un
    retrieval de prueba real. Ante cualquier falla (Ollama caído, timeout,
    respuesta sin tool_calls parseable) degrada a aprobar (approved=True) —
    aprobar por defecto es la opción segura: no reintenta indefinidamente y
    deja que el resto del pipeline siga con lo que ya se tiene.
    """

    def __init__(self, log_agent: LogAgent, rag_agent):
        self.log = log_agent
        self.rag = rag_agent

    def validate(self, query: str, model: str = None) -> dict:
        """
        Retorna {"approved": bool, "reason": str, "chunks": list[dict]}.
        chunks es el retrieval de prueba (vector_only) — se reusa en [RAG]
        final si la pregunta es aprobada (ver coordinator.py).
        """
        model = model or LLM_MODEL
        chunks = self.rag.retrieve(query)

        try:
            user_msg = self._build_user_message(query, chunks)
            resp = requests.post(
                f"{OLLAMA_URL}/api/chat",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": user_msg}],
                    "tools": [_REJECT_TOOL],
                    "stream": False,
                    "options": {"temperature": 0.1},
                },
                timeout=VALIDATOR_TIMEOUT,
            )
            resp.raise_for_status()
            tool_calls = resp.json().get("message", {}).get("tool_calls") or []

            if tool_calls:
                args = tool_calls[0].get("function", {}).get("arguments", {}) or {}
                reason = args.get("motivo") or "sin motivo especificado"
                self.log.log(Stage.VALIDADOR, f"✗ Rechazada ({len(chunks)} fragmento(s) encontrados): {reason}")
                return {"approved": False, "reason": reason, "chunks": chunks}

            self.log.log(Stage.VALIDADOR, f"✓ Aprobada ({len(chunks)} fragmento(s) encontrados).")
            return {"approved": True, "reason": "", "chunks": chunks}

        except requests.exceptions.ConnectionError:
            self.log.log(Stage.VALIDADOR, "⚠ Ollama no disponible — se aprueba por defecto.")
            return {"approved": True, "reason": "", "chunks": chunks}
        except requests.exceptions.Timeout:
            self.log.log(Stage.VALIDADOR, f"⚠ Timeout después de {VALIDATOR_TIMEOUT}s — se aprueba por defecto.")
            return {"approved": True, "reason": "", "chunks": chunks}
        except Exception as exc:
            self.log.log(Stage.VALIDADOR, f"⚠ Error validando pregunta: {exc} — se aprueba por defecto.")
            return {"approved": True, "reason": "", "chunks": chunks}

    # ── Construcción del mensaje de usuario ──────────────────────────────────

    def _build_user_message(self, query: str, chunks: list[dict]) -> str:
        parts = [f"PREGUNTA: {query}", ""]

        if chunks:
            parts.append("FRAGMENTOS NORMATIVOS RECUPERADOS:")
            for i, c in enumerate(chunks, 1):
                parts.append(f"[{i}] {c['text'][:400]}")
        else:
            parts.append("(No se recuperó ningún fragmento normativo para esta pregunta)")

        return "\n".join(parts)
