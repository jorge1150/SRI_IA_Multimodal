"""
coordinator.py — Agente Coordinador (Orquestador)
Dirige el pipeline completo del asistente SRI, emite actualizaciones
de log en tiempo real hacia la UI de Gradio y garantiza que cada
agente reciba los datos correctos.

Pipeline:
  [INICIO] → [STT] → [VISION] → [VIDEO] → [REFINADOR⇄VALIDADOR] → [PLANNER] → [RAG/NORMATIVA] → [GENERANDO] → [TTS] → [FIN]

[REFINADOR⇄VALIDADOR] y [PLANNER] son los únicos pasos donde el LLM decide
dinámicamente (vía tool-calling / reescritura) en vez de seguir una regla
fija — los 3 corren detrás de config.USE_AGENTIC_PLANNER=True; si no, la
estrategia de retrieval sigue siendo el modo "auto" fijo de HybridRetriever
(comportamiento sin cambios). Ver ADR-0005 (Planner) y ADR-0006 (Refiner/
Validator + memoria de aprendizaje in-context).
"""

from typing import Generator

import config as _cfg
from .log_agent import LogAgent, Stage
from .voice_agent import VoiceAgent
from .vision_agent import VisionAgent
from .video_agent import VideoAgent
from .planner_agent import PlannerAgent
from .query_refiner_agent import QueryRefinerAgent
from .query_validator_agent import QueryValidatorAgent
from .refinement_memory import RefinementMemory
from .rag_agent import RAGAgent
from .response_agent import ResponseAgent
from .tts_agent import TTSAgent


_Update = tuple[str, str, str | None, str]


def build_retrieval_pipeline(log_agent):
    """
    Wiring compartido del tramo retrieval+generación del pipeline:
    RAGAgent + ResponseAgent + PlannerAgent + QueryRefinerAgent +
    QueryValidatorAgent + GraphRetriever + HybridRetriever.
    Lo usan CoordinatorAgent (que suma encima sus agentes de media) y
    scripts/run_benchmark.py (que no necesita STT/visión/TTS) — un solo
    lugar donde cambiar los argumentos de construcción.

    Retorna (rag_agent, response_agent, planner_agent, refiner_agent,
    validator_agent, hybrid_retriever, graph_available).
    """
    rag_agent = RAGAgent(log_agent)
    response_agent = ResponseAgent(log_agent)
    planner_agent = PlannerAgent(log_agent)
    refinement_memory = RefinementMemory(rag_agent, log_agent)
    refiner_agent = QueryRefinerAgent(log_agent, refinement_memory)
    validator_agent = QueryValidatorAgent(log_agent, rag_agent)
    graph_retriever = _init_graph_retriever(log_agent)

    from services.hybrid_retriever import HybridRetriever
    hybrid_retriever = HybridRetriever(
        rag_agent=rag_agent,
        log_agent=log_agent,
        graph_retriever=graph_retriever,
    )
    return (rag_agent, response_agent, planner_agent, refiner_agent,
            validator_agent, hybrid_retriever, graph_retriever is not None)


def run_refinement_loop(refiner_agent, validator_agent, query: str, log_agent,
                         max_iterations: int = None):
    """
    Generador compartido entre CoordinatorAgent.process() (que necesita
    streaming de logs en tiempo real hacia la UI) y scripts/run_benchmark.py
    (que solo necesita el resultado final) — evita duplicar la lógica del
    loop Refinador⇄Validador en dos lugares.

    Hace yield de log_agent.get_all() después de cada paso, y termina con
    `return (final_query, validated_chunks, n_iterations)` — recuperable vía
    StopIteration.value (o transparente con `yield from` / next() en loop).

    Si el Validador aprueba después de al menos 1 rechazo, graba la lección
    en refiner_agent.memory (ver refinement_memory.py) — aprendizaje
    in-context, no reentrenamiento de pesos.
    """
    max_iterations = max_iterations or _cfg.REFINEMENT_MAX_ITERATIONS
    rejection_reason = ""
    last_rejected_query = None
    result = None
    final_query = query
    i = 0

    for i in range(max_iterations):
        log_agent.log(Stage.REFINADOR, f"Refinando pregunta (vuelta {i + 1})...")
        yield log_agent.get_all()

        final_query = refiner_agent.refine(final_query, rejection_reason)
        yield log_agent.get_all()

        log_agent.log(Stage.VALIDADOR, "Validando pregunta refinada...")
        yield log_agent.get_all()

        result = validator_agent.validate(final_query)
        yield log_agent.get_all()

        if result["approved"]:
            if last_rejected_query is not None and refiner_agent.memory is not None:
                refiner_agent.memory.record(last_rejected_query, rejection_reason, final_query)
            break

        rejection_reason = result["reason"]
        last_rejected_query = final_query

    validated_chunks = result["chunks"] if result is not None else []
    return final_query, validated_chunks, i + 1


def consume_refinement_loop(refiner_agent, validator_agent, query: str, log_agent,
                             max_iterations: int = None):
    """
    Agota run_refinement_loop() descartando los logs intermedios (para
    consumidores que no hacen streaming, ej. scripts/run_benchmark.py) y
    retorna (final_query, validated_chunks, n_iterations).
    """
    gen = run_refinement_loop(refiner_agent, validator_agent, query, log_agent, max_iterations)
    try:
        while True:
            next(gen)
    except StopIteration as e:
        return e.value


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
            log_agent.log(Stage.GRAPH, "⚠ Grafo no encontrado o vacío. "
                          "Ejecuta: python scripts/build_graph.py")
            return None

        stats = store.stats()
        log_agent.log(Stage.GRAPH, f"✓ Grafo cargado: {stats['n_nodes']} nodos, "
                      f"{stats['n_edges']} aristas.")
        return GraphRetriever(
            store,
            hop_depth=_cfg.GRAPH_HOP_DEPTH,
            top_k=_cfg.GRAPH_TOP_K_TRIPLES,
        )
    except ImportError:
        log_agent.log(Stage.GRAPH, "⚠ networkx no instalado. GraphRAG deshabilitado.")
        return None
    except Exception as exc:
        log_agent.log(Stage.GRAPH, f"⚠ Error iniciando GraphRAG: {exc}")
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
        self.tts_agent = TTSAgent(self.log_agent)

        # Tramo retrieval+generación — wiring compartido con el benchmark
        (self.rag_agent, self.response_agent, self.planner_agent,
         self.refiner_agent, self.validator_agent,
         self.hybrid_retriever, _) = build_retrieval_pipeline(self.log_agent)

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
        # Side-channel de la consulta anterior fuera — si esta consulta
        # termina antes de generar (ej. sin entrada), la UI no debe leer
        # respuesta/fuentes stale.
        self.response_agent.last_answer = ""
        self.response_agent.last_sources = []
        stt_text = ""
        response = ""

        # ── [INICIO] ────────────────────────────────────────────────────────
        self.log_agent.log(Stage.INICIO, "Asistente SRI IA Multimodal iniciado.")
        yield stt_text, response, None, self.log_agent.get_all()

        # ── [STT] — Transcripción de audio ──────────────────────────────────
        if audio_input is not None:
            self.log_agent.log(Stage.STT, "Recibiendo consulta por voz — transcribiendo audio...")
            yield stt_text, response, None, self.log_agent.get_all()

            stt_text = self.voice_agent.transcribe(audio_input)
            if stt_text:
                self.log_agent.log(Stage.STT, f"✓ Transcripción completa: «{stt_text[:60]}...»")
            else:
                self.log_agent.log(Stage.STT, "No se detectó voz en el audio.")
            yield stt_text, response, None, self.log_agent.get_all()

        # Combinar texto escrito + texto de voz
        full_query = " ".join(
            filter(None, [str(text_input or "").strip(), stt_text.strip()])
        ).strip()

        if not full_query and image_input is None and video_input is None:
            self.log_agent.log(Stage.ERROR, "No hay entrada. Proporcione texto, voz o imagen.")
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
            self.log_agent.log(Stage.VISION, "Analizando imagen o captura con Moondream...")
            yield stt_text, response, None, self.log_agent.get_all()

            visual_description = self.vision_agent.analyze(image_input)
            self.log_agent.log(Stage.VISION, f"✓ Descripción: «{visual_description[:80]}»")
            yield stt_text, response, None, self.log_agent.get_all()

        # ── [VIDEO] — Extracción de información del video ────────────────────
        video_description = ""
        if video_input is not None:
            self.log_agent.log(Stage.VIDEO, "Extrayendo información del video...")
            yield stt_text, response, None, self.log_agent.get_all()

            video_description = self.video_agent.process(str(video_input))
            self.log_agent.log(Stage.VIDEO, f"✓ Video analizado: {video_description[:60]}...")
            yield stt_text, response, None, self.log_agent.get_all()

        all_visual = " | ".join(filter(None, [visual_description, video_description]))

        # ── [REFINADOR⇄VALIDADOR] + [PLANNER] — Refinamiento y decisión ──────
        # agéntica de estrategia de retrieval. Los agentes de visión/video
        # retornan "" en error (nunca sentinelas "[...]"), así que basta
        # chequear no-vacío.
        rag_query = full_query
        if all_visual:
            rag_query = f"{full_query} {all_visual}"

        retrieve_kwargs = {}
        validated_chunks = None
        if _cfg.USE_AGENTIC_PLANNER:
            refinement_gen = run_refinement_loop(
                self.refiner_agent, self.validator_agent, rag_query, self.log_agent,
            )
            try:
                while True:
                    logs = next(refinement_gen)
                    yield stt_text, response, None, logs
            except StopIteration as done:
                rag_query, validated_chunks, _n_iterations = done.value

            self.log_agent.log(Stage.PLANNER, "Decidiendo si esta consulta necesita GraphRAG...")
            yield stt_text, response, None, self.log_agent.get_all()

            needs_graph = self.planner_agent.should_use_graph(rag_query)
            retrieve_kwargs["mode"] = "hybrid" if needs_graph else "vector_only"
            yield stt_text, response, None, self.log_agent.get_all()

        # ── [RAG] — Búsqueda de normativa relacionada ────────────────────────
        self.log_agent.log(Stage.RAG, f"Buscando normativa relacionada: «{rag_query[:150]}»...")
        yield stt_text, response, None, self.log_agent.get_all()

        if validated_chunks is not None:
            # El Validador ya corrió un retrieval vectorial real sobre esta
            # misma pregunta — se reusa en vez de duplicar la búsqueda.
            if retrieve_kwargs.get("mode") == "hybrid":
                graph_only = self.hybrid_retriever.retrieve(rag_query, mode="graph_only")
                # HybridRetriever(mode="graph_only") siempre devuelve
                # mode="graph_only" en el dict (ver hybrid_retriever.py) —
                # se recalcula acá para reflejar que también hay chunks
                # vectoriales reusados, y así el tag "[+grafo]" del log sea
                # correcto.
                combined_mode = "hybrid" if graph_only.get("graph_context") else "vector_only"
                hybrid_result = {**graph_only, "vector_chunks": validated_chunks, "mode": combined_mode}
            else:
                hybrid_result = {
                    "vector_chunks": validated_chunks, "graph_context": "",
                    "graph_triples": [], "graph_entities": [], "mode": "vector_only",
                }
        else:
            hybrid_result = self.hybrid_retriever.retrieve(rag_query, **retrieve_kwargs)

        rag_chunks   = hybrid_result["vector_chunks"]
        graph_context = hybrid_result["graph_context"]

        n_chunks = len(rag_chunks)
        mode_tag = " [+grafo]" if hybrid_result.get("mode") == "hybrid" else ""
        if n_chunks:
            self.log_agent.log(Stage.RAG, f"✓ {n_chunks} artículo(s) relevante(s){mode_tag}.")
        else:
            self.log_agent.log(Stage.RAG, "⚠ Sin normativa en base vectorial. Respuesta basada en conocimiento general.")
        yield stt_text, response, None, self.log_agent.get_all()

        # ── [GENERANDO] — Generación de respuesta tributaria ─────────────────
        self.log_agent.log(Stage.GENERANDO, f"Generando respuesta tributaria con {_cfg.LLM_MODEL}...")
        yield stt_text, response, None, self.log_agent.get_all()

        response = self.response_agent.generate(
            query=rag_query,
            rag_context=rag_chunks,
            visual_description=all_visual,
            graph_context=graph_context,
        )
        self.log_agent.log(Stage.RESPUESTA, f"✓ Respuesta lista ({len(response)} caracteres).")
        yield stt_text, response, None, self.log_agent.get_all()

        # ── [TTS] — Síntesis de voz ──────────────────────────────────────────
        self.log_agent.log(Stage.TTS, "Generando audio con Piper TTS...")
        yield stt_text, response, None, self.log_agent.get_all()

        # Respuesta limpia (sin bloque de fuentes) directo del agente —
        # no se corta el texto por el separador de display.
        tts_text = self.response_agent.last_answer or response
        audio_path = self.tts_agent.synthesize(tts_text)
        if audio_path:
            self.log_agent.log(Stage.TTS, f"✓ Audio generado: {audio_path}")
        else:
            self.log_agent.log(Stage.TTS, "⚠ No se generó audio (ver logs de TTS).")

        # ── [FIN] ────────────────────────────────────────────────────────────
        self.log_agent.log(Stage.FIN, "Consulta tributaria procesada correctamente.")
        yield stt_text, response, audio_path, self.log_agent.get_all()
