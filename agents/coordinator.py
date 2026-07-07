"""
coordinator.py — Agente Coordinador (Orquestador)
Dirige el pipeline completo del asistente SRI, emite actualizaciones
de log en tiempo real hacia la UI de Gradio y garantiza que cada
agente reciba los datos correctos.

Pipeline:
  [INICIO] → [STT] → [VISION] → [VIDEO] → [PLANNER] → [RAG/NORMATIVA] → [GENERANDO] → [TTS] → [FIN]

[PLANNER] es el único paso donde el LLM decide dinámicamente (vía
tool-calling) en vez de seguir una regla fija — solo corre si
config.USE_AGENTIC_PLANNER=True; si no, la estrategia de retrieval sigue
siendo el modo "auto" fijo de HybridRetriever (comportamiento sin cambios).
"""

from typing import Generator

import config as _cfg
from .log_agent import LogAgent
from .voice_agent import VoiceAgent
from .vision_agent import VisionAgent
from .video_agent import VideoAgent
from .planner_agent import PlannerAgent
from .rag_agent import RAGAgent
from .response_agent import ResponseAgent
from .tts_agent import TTSAgent


_Update = tuple[str, str, str | None, str]


def _init_graph_retriever(log_agent):
    """
    Inicializa el GraphRetriever si GRAPH_ENABLED=True y el grafo existe.
    Retorna None silenciosamente si no está disponible.
    """
    if not _cfg.GRAPH_ENABLED:
        return None
    try:
        from graph.graph_store import GraphStore
        from graph.graph_retriever import GraphRetriever

        store = GraphStore(_cfg.GRAPH_DB_PATH)
        loaded = store.load()
        if not loaded or store.is_empty():
            log_agent.log("GRAPH", "⚠ Grafo no encontrado o vacío. "
                          "Ejecuta: python scripts/build_graph.py")
            return None

        stats = store.stats()
        log_agent.log("GRAPH", f"✓ Grafo cargado: {stats['n_nodes']} nodos, "
                      f"{stats['n_edges']} aristas.")
        return GraphRetriever(
            store,
            hop_depth=_cfg.GRAPH_HOP_DEPTH,
            top_k=_cfg.GRAPH_TOP_K_TRIPLES,
        )
    except ImportError:
        log_agent.log("GRAPH", "⚠ networkx no instalado. GraphRAG deshabilitado.")
        return None
    except Exception as exc:
        log_agent.log("GRAPH", f"⚠ Error iniciando GraphRAG: {exc}")
        return None


class CoordinatorAgent:
    """
    Orquestador multiagente del sistema SRI IA Multimodal.
    Se instancia UNA sola vez al arrancar app.py (singleton).
    Usa HybridRetriever (RAG vectorial + GraphRAG) cuando GRAPH_ENABLED=True.
    """

    def __init__(self):
        self.log_agent = LogAgent()
        self.voice_agent = VoiceAgent(self.log_agent)
        self.vision_agent = VisionAgent(self.log_agent)
        self.video_agent = VideoAgent(self.log_agent, self.vision_agent)
        self.planner_agent = PlannerAgent(self.log_agent)
        self.rag_agent = RAGAgent(self.log_agent)
        self.response_agent = ResponseAgent(self.log_agent)
        self.tts_agent = TTSAgent(self.log_agent)

        # GraphRAG — inicialización lazy-tolerant
        graph_retriever = _init_graph_retriever(self.log_agent)

        from services.hybrid_retriever import HybridRetriever
        self.hybrid_retriever = HybridRetriever(
            rag_agent=self.rag_agent,
            log_agent=self.log_agent,
            graph_retriever=graph_retriever,
        )

    # ── API pública ──────────────────────────────────────────────────────────

    def process(
        self,
        image_input,
        audio_input,
        text_input: str,
        video_input,
    ) -> Generator[_Update, None, None]:
        """
        Generador que ejecuta el pipeline de consulta tributaria.
        Hace yield de actualizaciones parciales para streaming en tiempo real.

        Yield: (stt_text, response, audio_path, logs)
        """
        self.log_agent.clear()
        stt_text = ""
        response = ""

        # ── [INICIO] ────────────────────────────────────────────────────────
        self.log_agent.log("INICIO", "Asistente SRI IA Multimodal iniciado.")
        yield stt_text, response, None, self.log_agent.get_all()

        # ── [STT] — Transcripción de audio ──────────────────────────────────
        if audio_input is not None:
            self.log_agent.log("STT", "Recibiendo consulta por voz — transcribiendo audio...")
            yield stt_text, response, None, self.log_agent.get_all()

            stt_text = self.voice_agent.transcribe(audio_input)
            if stt_text:
                self.log_agent.log("STT", f"✓ Transcripción completa: «{stt_text[:60]}...»")
            else:
                self.log_agent.log("STT", "No se detectó voz en el audio.")
            yield stt_text, response, None, self.log_agent.get_all()

        # Combinar texto escrito + texto de voz
        full_query = " ".join(
            filter(None, [str(text_input or "").strip(), stt_text.strip()])
        ).strip()

        if not full_query and image_input is None and video_input is None:
            self.log_agent.log("ERROR", "No hay entrada. Proporcione texto, voz o imagen.")
            yield (
                stt_text,
                "Por favor, proporcione al menos una consulta por texto, voz o imagen.",
                None,
                self.log_agent.get_all(),
            )
            return

        if not full_query:
            full_query = "analiza el documento o imagen y describe qué trámite tributario muestra"

        # ── [VISION] — Análisis de imagen/formulario ─────────────────────────
        visual_description = ""
        if image_input is not None:
            self.log_agent.log("VISION", "Analizando imagen o captura con Moondream...")
            yield stt_text, response, None, self.log_agent.get_all()

            visual_description = self.vision_agent.analyze(image_input)
            self.log_agent.log("VISION", f"✓ Descripción: «{visual_description[:80]}»")
            yield stt_text, response, None, self.log_agent.get_all()

        # ── [VIDEO] — Extracción de información del video ────────────────────
        video_description = ""
        if video_input is not None:
            self.log_agent.log("VIDEO", "Extrayendo información del video...")
            yield stt_text, response, None, self.log_agent.get_all()

            video_description = self.video_agent.process(str(video_input))
            self.log_agent.log("VIDEO", f"✓ Video analizado: {video_description[:60]}...")
            yield stt_text, response, None, self.log_agent.get_all()

        all_visual = " | ".join(filter(None, [visual_description, video_description]))

        # ── [PLANNER] — Decisión agéntica de estrategia de retrieval ─────────
        rag_query = full_query
        if all_visual and "[" not in all_visual:
            rag_query = f"{full_query} {all_visual}"

        retrieve_kwargs = {}
        if _cfg.USE_AGENTIC_PLANNER:
            self.log_agent.log("PLANNER", "Decidiendo si esta consulta necesita GraphRAG...")
            yield stt_text, response, None, self.log_agent.get_all()

            needs_graph = self.planner_agent.should_use_graph(rag_query)
            retrieve_kwargs["mode"] = "hybrid" if needs_graph else "vector_only"
            yield stt_text, response, None, self.log_agent.get_all()

        # ── [RAG] — Búsqueda de normativa relacionada ────────────────────────
        self.log_agent.log("RAG", f"Buscando normativa relacionada: «{rag_query[:80]}»...")
        yield stt_text, response, None, self.log_agent.get_all()

        hybrid_result = self.hybrid_retriever.retrieve(rag_query, **retrieve_kwargs)
        rag_chunks   = hybrid_result["vector_chunks"]
        graph_context = hybrid_result["graph_context"]

        n_chunks = len(rag_chunks)
        mode_tag = " [+grafo]" if hybrid_result.get("mode") == "hybrid" else ""
        if n_chunks:
            self.log_agent.log("RAG", f"✓ {n_chunks} artículo(s) relevante(s){mode_tag}.")
        else:
            self.log_agent.log("RAG", "⚠ Sin normativa en base vectorial. Respuesta basada en conocimiento general.")
        yield stt_text, response, None, self.log_agent.get_all()

        # ── [GENERANDO] — Generación de respuesta tributaria ─────────────────
        self.log_agent.log("GENERANDO", f"Generando respuesta tributaria con {_cfg.LLM_MODEL}...")
        yield stt_text, response, None, self.log_agent.get_all()

        response = self.response_agent.generate(
            query=full_query,
            rag_context=rag_chunks,
            visual_description=all_visual,
            graph_context=graph_context,
        )
        self.log_agent.log("RESPUESTA", f"✓ Respuesta lista ({len(response)} caracteres).")
        yield stt_text, response, None, self.log_agent.get_all()

        # ── [TTS] — Síntesis de voz ──────────────────────────────────────────
        self.log_agent.log("TTS", "Generando audio con Piper TTS...")
        yield stt_text, response, None, self.log_agent.get_all()

        _sep = "─" * 37
        tts_text = response.split(_sep)[0].strip() if _sep in response else response
        audio_path = self.tts_agent.synthesize(tts_text)
        if audio_path:
            self.log_agent.log("TTS", f"✓ Audio generado: {audio_path}")
        else:
            self.log_agent.log("TTS", "⚠ No se generó audio (ver logs de TTS).")

        # ── [FIN] ────────────────────────────────────────────────────────────
        self.log_agent.log("FIN", "Consulta tributaria procesada correctamente.")
        yield stt_text, response, audio_path, self.log_agent.get_all()
