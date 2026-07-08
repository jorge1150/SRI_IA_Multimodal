"""
response_agent.py — Agente de Respuesta Tributaria SRI
Estrategia pensada originalmente para TinyLlama (modelo pequeño) y mantenida
con Qwen2.5 (ADR-0003) por ser igual de segura con modelos más grandes:
  - System prompt mínimo (evita que el modelo lo repita en la salida)
  - Contexto RAG con etiquetas neutras (no [Fuente N] que el modelo echa en output)
  - Seed del assistant = "Respuesta:" para forzar inicio de contenido real
  - Las fuentes se construyen en Python, no por el LLM
  - Post-procesamiento que limpia líneas de instrucciones filtradas
  - Deduplicación de fuentes por doc_name antes de enviar al LLM
"""

import re
import requests

from config import OLLAMA_URL, LLM_MODEL, LLM_TEMPERATURE, OLLAMA_TIMEOUT
from .log_agent import LogAgent, Stage

# Fuente ÚNICA del separador respuesta/fuentes en el texto del chat.
# Los demás consumidores (coordinator para TTS, benchmark para RAGAS, UI
# para el panel) ya NO cortan por este separador: leen last_answer /
# last_sources directo del agente — el separador es formato de display puro.
SOURCES_SEPARATOR = "─" * 37

_SYSTEM_PROMPT = (
    "Eres un asistente tributario del SRI Ecuador. "
    "Responde en español. "
    "Usa solo el contexto dado."
)

# Patrones de texto que modelos pequeños pueden filtrar/echar desde el prompt
_LEAK_PATTERNS = [
    r'(?i)^reglas\s+obligatorias',
    r'(?i)^basa\s+tu\s+respuesta',
    r'(?i)^cita\s+(siempre|exactamente)',
    r'(?i)^nunca\s+invent',
    r'(?i)^para\s+casos\s+específicos',
    r'(?i)^explica\s+en\s+lenguaje',
    r'(?i)^importante[:\s]',
    r'(?i)^esta\s+respuesta\s+es\s+orientativa',
    r'(?i)^responde[a]?\s+(siempre\s+)?en\s+español',
    r'(?i)^usa[s]?\s+únicamente',
    r'(?i)^usa[s]?\s+solo\s+el\s+contexto',
    r'(?i)^si\s+no\s+hay\s+contexto',
    r'(?i)^\d+\.\s+(basa|cita|nunca|para|explica|responde)',
    r'sri\.gober\.ec',
    r'(?i)^asesor\s+tributari',
    r'(?i)^no\s+constituye.*asesor',
    # Etiquetas de documentos del prompt que el modelo echa en output
    r'(?i)^---\s+(documento|doc)\s+\d+',
    r'(?i)^\[fuente\s*\d+\]',
    r'(?i)^normativa\s+oficial\s+sri',
]


class ResponseAgent:

    def __init__(self, log_agent: LogAgent):
        self.log = log_agent
        # Side-channel de la última generación (mismo patrón que
        # LogAgent.get_events): la respuesta limpia y las fuentes
        # estructuradas quedan legibles sin re-parsear el texto del chat.
        self.last_answer: str = ""
        self.last_sources: list[dict] = []

    # ── API pública ──────────────────────────────────────────────────────────

    def generate(
        self,
        query: str,
        rag_context: list[dict],
        visual_description: str = "",
        graph_context: str = "",
        model: str = None,
    ) -> str:
        """
        model: modelo Ollama a usar para esta llamada puntual (default:
        config.LLM_MODEL). Permite a scripts/run_benchmark.py comparar
        varios LLMs sin cambiar config.py ni afectar el chat de producción.
        """
        model = model or LLM_MODEL
        self.last_answer = ""
        self.last_sources = []
        self.log.log(Stage.GENERANDO, f"Enviando consulta a {model}...")

        try:
            user_msg = self._build_user_message(query, rag_context, visual_description, graph_context)

            payload = {
                "model": model,
                "messages": [
                    {"role": "system",    "content": _SYSTEM_PROMPT},
                    {"role": "user",      "content": user_msg},
                    # Seed explícito: fuerza al modelo a continuar con contenido real
                    # en lugar de echar el último fragmento del prompt de usuario
                    {"role": "assistant", "content": "Respuesta:"},
                ],
                "stream": False,
                "options": {
                    "temperature": LLM_TEMPERATURE,
                    "num_predict": 400,
                    "stop": [
                        "Usuario:", "Consulta:", "NORMATIVA:", "REGLAS",
                        "Responda", "Usa únicamente", "--- Documento",
                        "[Fuente", "PREGUNTA:",
                    ],
                },
            }

            resp = requests.post(
                f"{OLLAMA_URL}/api/chat",
                json=payload,
                timeout=OLLAMA_TIMEOUT,
            )
            resp.raise_for_status()

            raw = resp.json().get("message", {}).get("content", "").strip()
            # Quitar el "Respuesta:" del seed si el modelo lo repite al inicio
            raw = re.sub(r'^Respuesta:\s*', '', raw, flags=re.IGNORECASE).strip()
            answer = self._clean_response(raw)

            if not answer:
                answer = (
                    "No encontré normativa específica sobre este tema en la base de conocimiento. "
                    "Le recomiendo consultar directamente en sri.gob.ec "
                    "o con un profesional tributario."
                )

            sources = self._collect_sources(rag_context)
            final = answer + self._build_sources_section(sources)

            self.last_answer = answer
            self.last_sources = sources

            self.log.log(Stage.RESPUESTA, f"✓ Respuesta lista ({len(final)} caracteres).")
            return final

        except requests.exceptions.ConnectionError:
            msg = "[ERROR] Ollama no está ejecutándose. Inicia con: ollama serve"
            self.log.log(Stage.ERROR, msg)
            self.last_answer = msg
            return msg
        except requests.exceptions.Timeout:
            msg = f"[ERROR] Timeout después de {OLLAMA_TIMEOUT}s."
            self.log.log(Stage.ERROR, msg)
            self.last_answer = msg
            return msg
        except Exception as exc:
            msg = f"[ERROR] {exc}"
            self.log.log(Stage.ERROR, msg)
            self.last_answer = msg
            return msg

    # ── Construcción del mensaje de usuario ──────────────────────────────────

    def _build_user_message(
        self,
        query: str,
        rag_context: list[dict],
        visual_description: str,
        graph_context: str = "",
    ) -> str:
        parts = []

        # Deduplicar por doc_name para no repetir el mismo documento al LLM
        deduped = self._dedup_by_doc(rag_context, max_per_doc=1, max_total=3)

        if deduped:
            parts.append("CONTEXTO NORMATIVO SRI:")
            for i, c in enumerate(deduped, 1):
                # Etiqueta neutra — no usa [Fuente N] que el modelo echa en output
                parts.append(f"\n[{i}] {c['text'][:400]}")
            parts.append("")

        if graph_context:
            parts.append(graph_context)
            parts.append("")

        # Visión/video retornan "" en error — no hace falta filtrar sentinelas.
        if visual_description:
            parts.append(f"Imagen: {visual_description}\n")

        if not deduped and not graph_context:
            parts.append("(Sin normativa disponible)\n")

        parts.append(f"PREGUNTA: {query}")

        return "\n".join(parts)

    # ── Fuentes (construidas en Python) ─────────────────────────────────────

    @staticmethod
    def _collect_sources(rag_context: list[dict]) -> list[dict]:
        """
        Lista estructurada de fuentes, deduplicada por documento — la misma
        estructura alimenta el texto de fuentes del chat y el panel de la UI
        (via self.last_sources), sin serializar-y-reparsear texto.
        Shape por fuente: {num, tipo, doc, año, articulo, pagina, sim}.
        """
        seen: dict[str, dict] = {}
        for c in rag_context or []:
            meta = c.get("metadata", {})
            doc = meta.get("doc_name") or meta.get("source", "Documento SRI")
            if doc not in seen:
                seen[doc] = {"meta": meta, "sim": c.get("similarity", 0)}

        sources = []
        for i, (doc, info) in enumerate(seen.items(), 1):
            meta = info["meta"]
            sources.append({
                "num": str(i),
                "tipo": meta.get("tipo_normativa", ""),
                "doc": doc,
                "año": str(meta.get("año", "") or ""),
                "articulo": meta.get("articulo_seccion", ""),
                "pagina": str(meta.get("pagina", "") or ""),
                "sim": float(info["sim"]),
            })
        return sources

    def _build_sources_section(self, sources: list[dict]) -> str:
        """
        Sección de fuentes en texto para el bubble del chat, renderizada
        desde la lista estructurada de _collect_sources. El separador
        SOURCES_SEPARATOR delimita respuesta y fuentes en el texto plano.
        """
        if not sources:
            return (
                f"\n\n{SOURCES_SEPARATOR}\n"
                "📋 Sin normativa consultada. Verifique en sri.gob.ec"
            )

        lines = [f"\n\n{SOURCES_SEPARATOR}", "📋 FUENTES CONSULTADAS:"]
        for s in sources:
            line = f"  [{s['num']}] "
            if s["tipo"]:
                line += f"{s['tipo']}: "
            line += s["doc"]
            if s["año"]:
                line += f" ({s['año']})"
            if s["articulo"]:
                line += f" — {s['articulo']}"
            if s["pagina"]:
                line += f" — Pág. {s['pagina']}"
            line += f"  [sim: {s['sim']:.2f}]"
            lines.append(line)

        lines.append(SOURCES_SEPARATOR)
        lines.append("⚠️  Respuesta orientativa. Verifique en sri.gob.ec")
        return "\n".join(lines)

    # ── Post-procesamiento ───────────────────────────────────────────────────

    def _clean_response(self, text: str) -> str:
        if not text:
            return ""

        result_lines = []
        for line in text.splitlines():
            stripped = line.strip()
            if any(re.search(pat, stripped) for pat in _LEAK_PATTERNS):
                continue
            result_lines.append(line)

        cleaned = "\n".join(result_lines).strip()

        # Quitar bloques de reglas numeradas al inicio
        if re.match(r'^\d+\.', cleaned):
            sentences = re.split(r'(?<=[.!?])\s+', cleaned)
            real = [s for s in sentences if not re.match(r'^\d+\.', s.strip())]
            cleaned = " ".join(real).strip()

        return cleaned

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _dedup_by_doc(
        rag_context: list[dict],
        max_per_doc: int = 1,
        max_total: int = 3,
    ) -> list[dict]:
        """
        Filtra los chunks para el prompt del LLM:
        - Solo max_per_doc chunk(s) por documento único
        - Máximo max_total chunks en total
        Mantiene el orden de similitud (el RAG ya los entrega ordenados).
        """
        seen: dict[str, int] = {}
        result = []
        for c in rag_context:
            meta = c.get("metadata", {})
            doc  = meta.get("doc_name") or meta.get("source", "doc")
            count = seen.get(doc, 0)
            if count < max_per_doc:
                seen[doc] = count + 1
                result.append(c)
            if len(result) >= max_total:
                break
        return result

