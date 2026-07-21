"""
query_refiner_agent.py — Agente Refinador de Consultas
Reescribe la pregunta del usuario (texto+STT+descripción visual/video ya
combinados) para que sea más clara y específica al consultar la base
normativa SRI. Corre en loop con QueryValidatorAgent — ver
agents/coordinator.py::run_refinement_loop — hasta REFINEMENT_MAX_ITERATIONS.

Usa la misma RefinementMemory (ver refinement_memory.py) para inyectar
few-shot de correcciones pasadas similares: aprendizaje in-context, no
reentrenamiento de pesos. Ver ADR-0006.

Activado con config.USE_AGENTIC_PLANNER (mismo flag que PlannerAgent y
QueryValidatorAgent — los 3 agentes agénticos del pipeline comparten un
único punto de activación).
"""

import requests

from config import OLLAMA_URL, LLM_MODEL, LLM_TEMPERATURE, REFINER_TIMEOUT
from .log_agent import LogAgent, Stage
from .token_usage import extract_token_usage

_SYSTEM_PROMPT = (
    "Eres un asistente que reformula preguntas de normativa tributaria del "
    "SRI Ecuador para que sean más claras, específicas y fáciles de buscar "
    "en una base de documentos legales. Responde ÚNICAMENTE con la pregunta "
    "reformulada, sin explicaciones ni comentarios adicionales."
)


class QueryRefinerAgent:
    """
    Reescribe una pregunta tributaria para mejorar su recuperación en el
    RAG/GraphRAG. Ante cualquier falla (Ollama caído, timeout, respuesta
    vacía) degrada devolviendo la pregunta de entrada sin cambios — nunca
    bloquea el loop de refinamiento.
    """

    def __init__(self, log_agent: LogAgent, refinement_memory=None):
        self.log = log_agent
        self.memory = refinement_memory
        # Side-channel de tokens de la última llamada — solo para
        # benchmark/comparación de modelos (ADR-0009), no se usa en el chat.
        self.last_token_usage: dict = {}

    def refine(self, query: str, rejection_reason: str = "", model: str = None,
               previous_query: str = None, previous_answer: str = None) -> str:
        """
        previous_query/previous_answer: último intercambio de la conversación
        (solo relevante en la primera vuelta, ver coordinator.py::run_refinement_loop)
        — permite condensar un follow-up ambiguo ("dime los pasos") en una
        pregunta autocontenida usando el tema real de la conversación. Ver ADR-0010.
        """
        model = model or LLM_MODEL
        self.last_token_usage = {}

        examples = self.memory.similar(query) if self.memory is not None else []
        user_msg = self._build_user_message(query, rejection_reason, examples, previous_query, previous_answer)

        try:
            resp = requests.post(
                f"{OLLAMA_URL}/api/chat",
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": user_msg},
                    ],
                    "stream": False,
                    "options": {"temperature": LLM_TEMPERATURE},
                },
                timeout=REFINER_TIMEOUT,
            )
            resp.raise_for_status()
            resp_json = resp.json()
            self.last_token_usage = extract_token_usage(resp_json)
            refined = resp_json.get("message", {}).get("content", "").strip()

            if not refined:
                self.log.log(Stage.REFINADOR, "⚠ Respuesta vacía del refinador — se mantiene la pregunta original.")
                return query

            n_examples = len(examples)
            extra = f" (usando {n_examples} ejemplo(s) de memoria)" if n_examples else ""
            self.log.log(
                Stage.REFINADOR,
                f"Original: «{query[:150]}» → Refinada: «{refined[:150]}»{extra}",
            )
            return refined

        except requests.exceptions.ConnectionError:
            self.log.log(Stage.REFINADOR, "⚠ Ollama no disponible — se mantiene la pregunta original.")
            return query
        except requests.exceptions.Timeout:
            self.log.log(Stage.REFINADOR, f"⚠ Timeout después de {REFINER_TIMEOUT}s — se mantiene la pregunta original.")
            return query
        except Exception as exc:
            self.log.log(Stage.REFINADOR, f"⚠ Error refinando pregunta: {exc} — se mantiene la pregunta original.")
            return query

    # ── Construcción del mensaje de usuario ──────────────────────────────────

    def _build_user_message(self, query: str, rejection_reason: str, examples: list[dict],
                             previous_query: str = None, previous_answer: str = None) -> str:
        parts = []

        if examples:
            parts.append("Ejemplos de correcciones anteriores similares:")
            for ex in examples:
                parts.append(
                    f'- Pregunta mal formulada: «{ex["rejected_query"]}» '
                    f'(problema: {ex["motivo"]}) → versión corregida: «{ex["approved_query"]}»'
                )
            parts.append("")

        if previous_query:
            parts.append("CONTEXTO DE LA CONVERSACIÓN ANTERIOR:")
            parts.append(f"Pregunta anterior: {previous_query}")
            if previous_answer:
                parts.append(f"Respuesta anterior: {previous_answer[:400]}")
            parts.append(
                "Si la pregunta nueva es una continuación de la anterior (ej. "
                "'dime los pasos', 'y eso cuánto cuesta', sin mencionar el tema "
                "explícitamente), reescríbela como una pregunta autocontenida que "
                "incluya el tema real, usando el contexto de arriba."
            )
            parts.append("")

        if rejection_reason:
            parts.append(f"La siguiente pregunta fue rechazada porque: {rejection_reason}")
            parts.append("Reformúlala corrigiendo ese problema específico.")
        else:
            parts.append("Reformula la siguiente pregunta para que sea más clara y específica.")

        parts.append(f"\nPregunta: {query}")

        return "\n".join(parts)
