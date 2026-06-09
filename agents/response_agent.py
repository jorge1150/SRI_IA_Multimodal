"""
response_agent.py — Agente de Respuesta Tributaria SRI
Estrategia para TinyLlama (modelo pequeño):
  - System prompt mínimo (evita que el modelo lo repita en la salida)
  - Contexto RAG en el mensaje de usuario
  - Las fuentes se construyen en Python, no por el LLM
  - Post-procesamiento que limpia líneas de instrucciones filtradas
"""

import re
import requests

from config import OLLAMA_URL, LLM_MODEL, LLM_TEMPERATURE, OLLAMA_TIMEOUT
from .log_agent import LogAgent

# System prompt mínimo — TinyLlama repite prompts largos con reglas numeradas
_SYSTEM_PROMPT = (
    "Eres un asistente tributario del SRI Ecuador. "
    "Responde SOLO en español. "
    "Usa únicamente el contexto normativo dado. "
    "Si no hay contexto, di que no tienes información."
)

# Frases del system prompt que el modelo puede filtrar en la salida
_LEAK_PATTERNS = [
    r'(?i)^reglas\s+obligatorias',
    r'(?i)^basa\s+tu\s+respuesta',
    r'(?i)^cita\s+(siempre|exactamente)',
    r'(?i)^nunca\s+invent',
    r'(?i)^para\s+casos\s+específicos',
    r'(?i)^explica\s+en\s+lenguaje',
    r'(?i)^importante[:\s]',
    r'(?i)^esta\s+respuesta\s+es\s+orientativa',
    r'(?i)^responde\s+siempre\s+en\s+español',
    r'(?i)^\d+\.\s+(basa|cita|nunca|para|explica|responde)',
    r'sri\.gober\.ec',
    r'(?i)^asesor\s+tributari',
    r'(?i)^no\s+constituye.*asesor',
]


class ResponseAgent:

    def __init__(self, log_agent: LogAgent):
        self.log = log_agent

    # ── API pública ──────────────────────────────────────────────────────────

    def generate(
        self,
        query: str,
        rag_context: list[dict],
        visual_description: str = "",
        graph_context: str = "",
    ) -> str:
        """
        Genera la respuesta tributaria.
        El LLM produce solo el texto de respuesta.
        Las fuentes consultadas se construyen en Python y se añaden al final.
        """
        self.log.log("GENERANDO", f"Enviando consulta a {LLM_MODEL}...")

        try:
            user_msg = self._build_user_message(query, rag_context, visual_description, graph_context)

            payload = {
                "model": LLM_MODEL,
                "messages": [
                    {"role": "system",    "content": _SYSTEM_PROMPT},
                    {"role": "user",      "content": user_msg},
                    {"role": "assistant", "content": ""},
                ],
                "stream": False,
                "options": {
                    "temperature": LLM_TEMPERATURE,
                    "num_predict": 512,
                    "stop": ["Usuario:", "Consulta:", "NORMATIVA:", "REGLAS"],
                },
            }

            resp = requests.post(
                f"{OLLAMA_URL}/api/chat",
                json=payload,
                timeout=OLLAMA_TIMEOUT,
            )
            resp.raise_for_status()

            raw = resp.json().get("message", {}).get("content", "").strip()
            answer = self._clean_response(raw)

            if not answer:
                answer = (
                    "No encontré normativa específica sobre este tema en la base de conocimiento. "
                    "Le recomiendo consultar directamente en sri.gob.ec "
                    "o con un profesional tributario."
                )

            # Añadir fuentes construidas en Python (sin depender del LLM)
            sources_section = self._build_sources_section(rag_context)
            final = answer + sources_section

            self.log.log("RESPUESTA", f"✓ Respuesta lista ({len(final)} caracteres).")
            return final

        except requests.exceptions.ConnectionError:
            msg = "[ERROR] Ollama no está ejecutándose. Inicia con: ollama serve"
            self.log.log("ERROR", msg)
            return msg
        except requests.exceptions.Timeout:
            msg = f"[ERROR] Timeout después de {OLLAMA_TIMEOUT}s."
            self.log.log("ERROR", msg)
            return msg
        except Exception as exc:
            msg = f"[ERROR] {exc}"
            self.log.log("ERROR", msg)
            return msg

    # ── Construcción del mensaje de usuario ──────────────────────────────────

    def _build_user_message(
        self,
        query: str,
        rag_context: list[dict],
        visual_description: str,
        graph_context: str = "",
    ) -> str:
        """
        Formato optimizado para TinyLlama:
        contexto vectorial → relaciones de grafo → pregunta → instrucción.
        """
        parts = []

        if rag_context:
            parts.append("NORMATIVA OFICIAL SRI:")
            for i, c in enumerate(rag_context[:3], 1):
                label = self._source_label(i, c.get("metadata", {}))
                parts.append(f"\n{label}\n{c['text'][:450]}")
            parts.append("")

        # Contexto del grafo de conocimiento (GraphRAG)
        if graph_context:
            parts.append(graph_context)
            parts.append("")

        if visual_description and "[" not in visual_description:
            parts.append(f"Imagen analizada: {visual_description}\n")

        if not rag_context and not graph_context:
            parts.append("(No se encontró normativa en la base de conocimiento)\n")

        parts.append(f"Consulta: {query}")
        parts.append("\nResponde en español usando solo la normativa anterior:")

        return "\n".join(parts)

    # ── Fuentes (construidas en Python, no por el LLM) ───────────────────────

    def _build_sources_section(self, rag_context: list[dict]) -> str:
        """
        Construye la sección de fuentes fuera del LLM para garantizar
        que el formato sea correcto sin importar la calidad del modelo.
        """
        if not rag_context:
            return (
                "\n\n─────────────────────────────────────\n"
                "📋 FUENTES: No se consultó normativa local.\n"
                "   Verifique en sri.gob.ec"
            )

        lines = ["\n\n─────────────────────────────────────", "📋 FUENTES CONSULTADAS:"]
        for i, c in enumerate(rag_context[:4], 1):
            meta = c.get("metadata", {})
            doc  = meta.get("doc_name") or meta.get("source", "Documento SRI")
            tipo = meta.get("tipo_normativa", "")
            art  = meta.get("articulo_seccion", "")
            pag  = meta.get("pagina", "")
            año  = meta.get("año", "")
            sim  = c.get("similarity", 0)

            line = f"  [{i}] "
            if tipo:
                line += f"{tipo}: "
            line += doc
            if año:
                line += f" ({año})"
            if art:
                line += f" — {art}"
            if pag:
                line += f" — Pág. {pag}"
            line += f"  [sim: {sim:.2f}]"
            lines.append(line)

        lines.append("─────────────────────────────────────")
        lines.append("⚠️  Respuesta orientativa. Verifique en sri.gob.ec")
        return "\n".join(lines)

    # ── Post-procesamiento ───────────────────────────────────────────────────

    def _clean_response(self, text: str) -> str:
        """
        Elimina líneas en las que el modelo repitió instrucciones del
        system prompt. TinyLlama (1.1B) tiende a filtrar el prompt en
        la salida cuando las instrucciones son largas o numeradas.
        """
        if not text:
            return ""

        result_lines = []
        for line in text.splitlines():
            stripped = line.strip()
            if any(re.search(pat, stripped) for pat in _LEAK_PATTERNS):
                continue
            result_lines.append(line)

        cleaned = "\n".join(result_lines).strip()

        # Si lo que quedó empieza con una lista numerada de reglas, quitar
        if re.match(r'^\d+\.', cleaned):
            # Intentar encontrar la primera oración real
            sentences = re.split(r'(?<=[.!?])\s+', cleaned)
            real = [s for s in sentences if not re.match(r'^\d+\.', s.strip())]
            cleaned = " ".join(real).strip()

        return cleaned

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _source_label(num: int, meta: dict) -> str:
        doc  = meta.get("doc_name") or meta.get("source", "Documento SRI")
        tipo = meta.get("tipo_normativa", "")
        art  = meta.get("articulo_seccion", "")
        pag  = meta.get("pagina", "")
        año  = meta.get("año", "")

        parts = [f"[Fuente {num}]"]
        if tipo:
            parts.append(tipo + ":")
        parts.append(doc)
        if año:
            parts.append(f"({año})")
        if art:
            parts.append(f"| {art}")
        if pag:
            parts.append(f"| Pág. {pag}")
        return " ".join(parts)
