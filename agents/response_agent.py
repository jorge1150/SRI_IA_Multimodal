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
from .log_agent import LogAgent

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
        self.log.log("GENERANDO", f"Enviando consulta a {model}...")

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

        if visual_description and "[" not in visual_description:
            parts.append(f"Imagen: {visual_description}\n")

        if not deduped and not graph_context:
            parts.append("(Sin normativa disponible)\n")

        parts.append(f"PREGUNTA: {query}")

        return "\n".join(parts)

    # ── Fuentes (construidas en Python) ─────────────────────────────────────

    def _build_sources_section(self, rag_context: list[dict]) -> str:
        """
        Sección de fuentes compacta al final de la respuesta.
        Formato: resumen una línea + lista deduplicada por doc.
        El separador ─────... permite al UI dividir respuesta y fuentes.
        """
        if not rag_context:
            return (
                "\n\n─────────────────────────────────────\n"
                "📋 Sin normativa consultada. Verifique en sri.gob.ec"
            )

        # Deduplicar fuentes — el panel HTML ya muestra todos los fragmentos
        seen: dict[str, dict] = {}
        for c in rag_context:
            meta = c.get("metadata", {})
            doc  = meta.get("doc_name") or meta.get("source", "Documento SRI")
            if doc not in seen:
                seen[doc] = {"meta": meta, "sim": c.get("similarity", 0)}

        lines = ["\n\n─────────────────────────────────────", "📋 FUENTES CONSULTADAS:"]
        for i, (doc, info) in enumerate(seen.items(), 1):
            meta = info["meta"]
            tipo = meta.get("tipo_normativa", "")
            art  = meta.get("articulo_seccion", "")
            pag  = meta.get("pagina", "")
            año  = meta.get("año", "")
            sim  = info["sim"]

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

    @staticmethod
    def _source_label(num: int, meta: dict) -> str:
        doc  = meta.get("doc_name") or meta.get("source", "Documento SRI")
        tipo = meta.get("tipo_normativa", "")
        art  = meta.get("articulo_seccion", "")
        pag  = meta.get("pagina", "")
        año  = meta.get("año", "")

        parts = [f"[{num}]"]
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
