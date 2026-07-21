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

Guardrail de dominio (ADR-0007): además de "rechazar_pregunta" (pregunta SÍ
tributaria pero mal formulada — el Refinador debe reformularla), existe
"pregunta_fuera_de_dominio" (pregunta que NO tiene nada que ver con SRI —
el Refinador NUNCA debe "arreglarla" para que suene tributaria; el pipeline
corta directo con un mensaje fijo, ver coordinator.py). Un fast-path vía
OffTopicMemory evita gastar una llamada a Ollama en preguntas ya vistas.

Activado con config.USE_AGENTIC_PLANNER (mismo flag que PlannerAgent y
QueryRefinerAgent).
"""

import requests

from config import OLLAMA_URL, LLM_MODEL, VALIDATOR_TIMEOUT
from .log_agent import LogAgent, Stage
from .token_usage import extract_token_usage

_REJECT_TOOL = {
    "type": "function",
    "function": {
        "name": "rechazar_pregunta",
        "description": (
            "Llama a esta función SOLO si la pregunta ES sobre normativa "
            "tributaria del SRI Ecuador pero es imposible de responder con "
            "los fragmentos dados: está vacía o incoherente, o NINGUNO de "
            "los fragmentos recuperados es relevante al tema de la pregunta. "
            "NO la llames solo porque la pregunta es amplia o los fragmentos no "
            "cubren absolutamente todos los detalles posibles — una pregunta "
            "general ('¿qué medidas... ?', '¿qué obligaciones... ?') es válida "
            "y respondible con los fragmentos relevantes que sí haya, aunque no "
            "los liste todos. Rechazar por amplitud hace que el sistema nunca "
            "converja. Si la pregunta no es sobre tributación en absoluto, usa "
            "pregunta_fuera_de_dominio en vez de esta."
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

_OFF_TOPIC_TOOL = {
    "type": "function",
    "function": {
        "name": "pregunta_fuera_de_dominio",
        "description": (
            "Llama a esta función si la pregunta NO tiene absolutamente nada "
            "que ver con normativa tributaria del SRI Ecuador (ej. clima, "
            "deportes, saludos, preguntas de otro dominio por completo). "
            "NO la llames si la pregunta es sobre impuestos/normativa aunque "
            "esté mal formulada — para eso está rechazar_pregunta."
        ),
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
}

_OFF_TOPIC_MESSAGE = (
    "Esta pregunta no tiene relación con la normativa tributaria del SRI "
    "Ecuador. Por favor, formula una consulta sobre impuestos, "
    "declaraciones u obligaciones tributarias."
)


class QueryValidatorAgent:
    """
    Decide sí/no si una pregunta refinada alcanza para responder, contra un
    retrieval de prueba real. Ante cualquier falla (Ollama caído, timeout,
    respuesta sin tool_calls parseable) degrada a aprobar (approved=True) —
    aprobar por defecto es la opción segura: no reintenta indefinidamente y
    deja que el resto del pipeline siga con lo que ya se tiene.
    """

    def __init__(self, log_agent: LogAgent, rag_agent, off_topic_memory=None):
        self.log = log_agent
        self.rag = rag_agent
        self.off_topic_memory = off_topic_memory
        # Side-channel de tokens de la última llamada — solo para
        # benchmark/comparación de modelos (ADR-0009), no se usa en el chat.
        self.last_token_usage: dict = {}

    def check_off_topic(self, query: str, model: str = None,
                         previous_query: str = None, previous_answer: str = None) -> dict:
        """
        Chequeo liviano de dominio — SIN retrieval, sin la tool
        `rechazar_pregunta` — pensado para correr sobre la pregunta
        ORIGINAL, antes de que el Refinador la toque (ver
        coordinator.py::run_refinement_loop). El Refinador nunca debe
        "arreglar" una pregunta fuera de tema para que suene tributaria
        (ADR-0007). Retorna {"off_topic": bool, "reason": str}.

        previous_query/previous_answer: último intercambio de la conversación
        (ver ADR-0010) — sin esto, un follow-up genérico ("dime los pasos")
        no tiene palabras clave tributarias por sí solo y podría marcarse
        fuera de dominio sin el contexto real de la conversación.
        """
        model = model or LLM_MODEL
        self.last_token_usage = {}

        if self.off_topic_memory is not None:
            match = self.off_topic_memory.similar(query, top_k=1)
            if match:
                self.log.log(Stage.VALIDADOR, f"✗ Fuera de dominio (ya visto en memoria): «{query[:80]}»")
                return {"off_topic": True, "reason": _OFF_TOPIC_MESSAGE}

        try:
            user_msg = self._build_off_topic_message(query, previous_query, previous_answer)
            resp = requests.post(
                f"{OLLAMA_URL}/api/chat",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": user_msg}],
                    "tools": [_OFF_TOPIC_TOOL],
                    "stream": False,
                    "options": {"temperature": 0.1},
                },
                timeout=VALIDATOR_TIMEOUT,
            )
            resp.raise_for_status()
            resp_json = resp.json()
            self.last_token_usage = extract_token_usage(resp_json)
            tool_calls = resp_json.get("message", {}).get("tool_calls") or []
            names = [tc.get("function", {}).get("name") for tc in tool_calls]

            if "pregunta_fuera_de_dominio" in names:
                if self.off_topic_memory is not None:
                    self.off_topic_memory.record(query)
                self.log.log(Stage.VALIDADOR, f"✗ Fuera de dominio: «{query[:80]}»")
                return {"off_topic": True, "reason": _OFF_TOPIC_MESSAGE}

            return {"off_topic": False, "reason": ""}

        except requests.exceptions.ConnectionError:
            self.log.log(Stage.VALIDADOR, "⚠ Ollama no disponible — se asume dentro del dominio.")
            return {"off_topic": False, "reason": ""}
        except requests.exceptions.Timeout:
            self.log.log(Stage.VALIDADOR, f"⚠ Timeout después de {VALIDATOR_TIMEOUT}s — se asume dentro del dominio.")
            return {"off_topic": False, "reason": ""}
        except Exception as exc:
            self.log.log(Stage.VALIDADOR, f"⚠ Error verificando dominio: {exc} — se asume dentro del dominio.")
            return {"off_topic": False, "reason": ""}

    def validate(self, query: str, model: str = None) -> dict:
        """
        Retorna {"approved": bool, "off_topic": bool, "reason": str,
        "chunks": list[dict]}. chunks es el retrieval de prueba (vector_only)
        — se reusa en [RAG] final si la pregunta es aprobada (coordinator.py).
        Si off_topic=True, el resto del pipeline (Planner/RAG/Generación) se
        salta por completo — ver coordinator.py::run_refinement_loop.
        """
        model = model or LLM_MODEL
        self.last_token_usage = {}

        # Fast-path: pregunta ya vista y marcada fuera de dominio antes —
        # corta sin retrieval ni llamada a Ollama.
        if self.off_topic_memory is not None:
            match = self.off_topic_memory.similar(query, top_k=1)
            if match:
                self.log.log(Stage.VALIDADOR, f"✗ Fuera de dominio (ya visto en memoria): «{query[:80]}»")
                return {"approved": False, "off_topic": True, "reason": _OFF_TOPIC_MESSAGE, "chunks": []}

        chunks = self.rag.retrieve(query)

        try:
            user_msg = self._build_user_message(query, chunks)
            resp = requests.post(
                f"{OLLAMA_URL}/api/chat",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": user_msg}],
                    "tools": [_REJECT_TOOL, _OFF_TOPIC_TOOL],
                    "stream": False,
                    "options": {"temperature": 0.1},
                },
                timeout=VALIDATOR_TIMEOUT,
            )
            resp.raise_for_status()
            resp_json = resp.json()
            self.last_token_usage = extract_token_usage(resp_json)
            tool_calls = resp_json.get("message", {}).get("tool_calls") or []
            names = [tc.get("function", {}).get("name") for tc in tool_calls]

            if "pregunta_fuera_de_dominio" in names:
                if self.off_topic_memory is not None:
                    self.off_topic_memory.record(query)
                self.log.log(Stage.VALIDADOR, f"✗ Fuera de dominio: «{query[:80]}»")
                return {"approved": False, "off_topic": True, "reason": _OFF_TOPIC_MESSAGE, "chunks": chunks}

            if tool_calls:
                args = tool_calls[0].get("function", {}).get("arguments", {}) or {}
                reason = args.get("motivo") or "sin motivo especificado"
                self.log.log(Stage.VALIDADOR, f"✗ Rechazada ({len(chunks)} fragmento(s) encontrados): {reason}")
                return {"approved": False, "off_topic": False, "reason": reason, "chunks": chunks}

            self.log.log(Stage.VALIDADOR, f"✓ Aprobada ({len(chunks)} fragmento(s) encontrados).")
            return {"approved": True, "off_topic": False, "reason": "", "chunks": chunks}

        except requests.exceptions.ConnectionError:
            self.log.log(Stage.VALIDADOR, "⚠ Ollama no disponible — se aprueba por defecto.")
            return {"approved": True, "off_topic": False, "reason": "", "chunks": chunks}
        except requests.exceptions.Timeout:
            self.log.log(Stage.VALIDADOR, f"⚠ Timeout después de {VALIDATOR_TIMEOUT}s — se aprueba por defecto.")
            return {"approved": True, "off_topic": False, "reason": "", "chunks": chunks}
        except Exception as exc:
            self.log.log(Stage.VALIDADOR, f"⚠ Error validando pregunta: {exc} — se aprueba por defecto.")
            return {"approved": True, "off_topic": False, "reason": "", "chunks": chunks}

    # ── Construcción del mensaje de usuario ──────────────────────────────────

    def _build_off_topic_message(self, query: str, previous_query: str = None,
                                  previous_answer: str = None) -> str:
        parts = []
        if previous_query:
            parts.append(f"Pregunta anterior en esta conversación: {previous_query}")
            if previous_answer:
                parts.append(f"Respuesta anterior: {previous_answer[:400]}")
            parts.append("Juzga la pregunta nueva en el contexto de la conversación completa, no aislada.")
            parts.append("")
        parts.append(f"PREGUNTA: {query}")
        return "\n".join(parts)

    def _build_user_message(self, query: str, chunks: list[dict]) -> str:
        parts = [f"PREGUNTA: {query}", ""]

        if chunks:
            parts.append("FRAGMENTOS NORMATIVOS RECUPERADOS:")
            for i, c in enumerate(chunks, 1):
                parts.append(f"[{i}] {c['text'][:400]}")
        else:
            parts.append("(No se recuperó ningún fragmento normativo para esta pregunta)")

        return "\n".join(parts)
