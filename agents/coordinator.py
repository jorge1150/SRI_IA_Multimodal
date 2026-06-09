"""
coordinator.py — Agente Coordinador (Orquestador)
Dirige el pipeline completo del asistente SRI, emite actualizaciones
de log en tiempo real hacia la UI de Gradio y garantiza que cada
agente reciba los datos correctos.

Pipeline:
  [INICIO] → [STT] → [VISION] → [VIDEO] → [RAG/NORMATIVA] → [GENERANDO] → [TTS] → [FIN]
"""

from typing import Generator

from .log_agent import LogAgent
from .voice_agent import VoiceAgent
from .vision_agent import VisionAgent
from .video_agent import VideoAgent
from .rag_agent import RAGAgent
from .response_agent import ResponseAgent
from .tts_agent import TTSAgent


_Update = tuple[str, str, str | None, str]


class CoordinatorAgent:
    """
    Orquestador multiagente del sistema SRI IA Multimodal.
    Se instancia UNA sola vez al arrancar app.py (singleton).
    """

    def __init__(self):
        self.log_agent = LogAgent()
        self.voice_agent = VoiceAgent(self.log_agent)
        self.vision_agent = VisionAgent(self.log_agent)
        self.video_agent = VideoAgent(self.log_agent, self.vision_agent)
        self.rag_agent = RAGAgent(self.log_agent)
        self.response_agent = ResponseAgent(self.log_agent)
        self.tts_agent = TTSAgent(self.log_agent)

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

        # ── [RAG] — Búsqueda de normativa relacionada ────────────────────────
        rag_query = full_query
        if all_visual and "[" not in all_visual:
            rag_query = f"{full_query} {all_visual}"

        self.log_agent.log("RAG", f"Buscando normativa relacionada: «{rag_query[:80]}»...")
        yield stt_text, response, None, self.log_agent.get_all()

        rag_chunks = self.rag_agent.retrieve(rag_query)
        n_chunks = len(rag_chunks)
        if n_chunks:
            self.log_agent.log("RAG", f"✓ Recuperando {n_chunks} artículo(s)/resolución(es) relevante(s).")
        else:
            self.log_agent.log("RAG", "⚠ Sin normativa en base vectorial. Respuesta basada en conocimiento general.")
        yield stt_text, response, None, self.log_agent.get_all()

        # ── [GENERANDO] — Generación de respuesta tributaria ─────────────────
        self.log_agent.log("GENERANDO", f"Generando respuesta tributaria con {__import__('config').LLM_MODEL}...")
        yield stt_text, response, None, self.log_agent.get_all()

        response = self.response_agent.generate(
            query=full_query,
            rag_context=rag_chunks,
            visual_description=all_visual,
        )
        self.log_agent.log("RESPUESTA", f"✓ Respuesta lista ({len(response)} caracteres).")
        yield stt_text, response, None, self.log_agent.get_all()

        # ── [TTS] — Síntesis de voz ──────────────────────────────────────────
        self.log_agent.log("TTS", "Generando audio con Piper TTS...")
        yield stt_text, response, None, self.log_agent.get_all()

        audio_path = self.tts_agent.synthesize(response)
        if audio_path:
            self.log_agent.log("TTS", f"✓ Audio generado: {audio_path}")
        else:
            self.log_agent.log("TTS", "⚠ No se generó audio (ver logs de TTS).")

        # ── [FIN] ────────────────────────────────────────────────────────────
        self.log_agent.log("FIN", "Consulta tributaria procesada correctamente.")
        yield stt_text, response, audio_path, self.log_agent.get_all()
