"""
interface.py — Interfaz Gradio del Asistente Tributario SRI IA Multimodal.
Diseño: dark professional · glassmorphism · Ecuador flag accents · RAG dashboard.
"""

import html
import re
import gradio as gr
from vision.capture import capture_screenshot
from ui.styles import CSS
from config import GRADIO_PORT, GRADIO_SERVER, GRADIO_TITLE, LLM_MODEL, is_cloud_model

GRADIO_THEME = gr.themes.Base(
    primary_hue=gr.themes.colors.blue,
    secondary_hue=gr.themes.colors.amber,
    neutral_hue=gr.themes.colors.slate,
)

# ── RAG panel ────────────────────────────────────────────────────────────────
# Renderiza directo desde ResponseAgent.last_sources (lista estructurada,
# shape {num, tipo, doc, año, articulo, pagina, sim}) — el texto de fuentes
# del chat ya no se re-parsea con regex.

def _rag_panel_html(fragments: list) -> str:
    search_icon = (
        '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="2" aria-hidden="true">'
        '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>'
    )

    if not fragments:
        return (
            '<div class="rag-panel" role="region" aria-label="Fragmentos normativos recuperados">'
            f'<div class="rag-panel-title">{search_icon}'
            'Fragmentos Normativos Recuperados</div>'
            '<div class="rag-empty">Sin fragmentos recuperados &mdash; '
            'realice una consulta para ver los documentos normativos utilizados.</div>'
            '</div>'
        )

    cards = ''
    for f in fragments:
        sim_pct = min(int(f['sim'] * 100), 100)
        if f['sim'] >= 0.80:
            sim_color = '#10b981'
        elif f['sim'] >= 0.60:
            sim_color = '#f59e0b'
        else:
            sim_color = '#64748b'

        tipo_badge = (
            f'<span class="rag-tipo">{f["tipo"]}</span>' if f['tipo'] else ''
        )
        ano_badge = (
            f'<span class="rag-ano">{f["año"]}</span>' if f['año'] else ''
        )
        art_tag = (
            f'<span class="rag-meta-item">{f["articulo"]}</span>'
            if f['articulo'] else ''
        )
        pag_tag = (
            f'<span class="rag-meta-item">P&aacute;g. {f["pagina"]}</span>'
            if f['pagina'] else ''
        )
        meta_row = (
            f'<div class="rag-fragment-meta">{art_tag}{pag_tag}</div>'
            if art_tag or pag_tag else ''
        )

        cards += (
            '<div class="rag-fragment">'
            '<div class="rag-fragment-top">'
            f'<div class="rag-fragment-num">[{f["num"]}]</div>'
            '<div class="rag-fragment-info">'
            f'<div class="rag-fragment-doc" title="{f["doc"]}">{f["doc"]}</div>'
            f'<div class="rag-fragment-badges">{tipo_badge}{ano_badge}</div>'
            '</div>'
            '<div class="rag-sim-wrap">'
            f'<div class="rag-sim-value" style="color:{sim_color}">{f["sim"]:.2f}</div>'
            '<div class="rag-sim-bar">'
            f'<div class="rag-sim-fill" style="width:{sim_pct}%;background:{sim_color}"></div>'
            '</div>'
            '</div>'
            '</div>'
            f'{meta_row}'
            '</div>'
        )

    count = len(fragments)
    plural = 's' if count > 1 else ''
    return (
        '<div class="rag-panel" role="region" aria-label="Fragmentos normativos recuperados">'
        f'<div class="rag-panel-title">{search_icon}'
        f'{count} Fragmento{plural} Recuperado{plural} &middot; Base Normativa SRI'
        '<span style="font-size:11px;font-weight:400;color:#64748b;margin-left:8px">'
        '&mdash; puntuaci&oacute;n incluye boost por palabras clave (puede superar 1.0)</span></div>'
        f'{cards}'
        '</div>'
    )


# ── Diagrama de flujo de agentes (vivo) ─────────────────────────────────────────
# Consume los eventos estructurados de LogAgent.get_events() — un diagrama de
# nodos conectados como aporte visual de tesis ("software agéntico"): se ve al
# coordinador pasarle el turno a cada agente, con el PlannerAgent marcado como
# el único punto de decisión real (el resto son pasos fijos, no negociación).
# Las etapas son las constantes Stage de agents/log_agent.py — la fuente única
# de verdad del vocabulario; acá solo se agrupan en nodos de presentación.

from agents.log_agent import Stage as _Stage

_AGENT_FLOW_NODES = [
    {"tags": (_Stage.INICIO,),                              "label": "Coordinador", "icon": "🧭"},
    {"tags": (_Stage.STT,),                                 "label": "STT",         "icon": "🎤"},
    {"tags": (_Stage.VISION, _Stage.VIDEO),                 "label": "Visión",      "icon": "👁️"},
    {"tags": (_Stage.REFINADOR,), "label": "Refinador", "icon": "✏️"},
    {"tags": (_Stage.VALIDADOR,), "label": "Validador", "icon": "✅", "decision": True},
    {"tags": (_Stage.PLANNER,), "label": "Planner", "icon": "🧠", "decision": True},
    {"tags": (_Stage.RAG, _Stage.NORMATIVA, _Stage.GRAPH), "label": "RAG / Grafo", "icon": "📋"},
    {"tags": (_Stage.GENERANDO, _Stage.RESPUESTA),          "label": "Generación",  "icon": "🤖"},
    {"tags": (_Stage.TTS,),                                 "label": "TTS",         "icon": "🔊"},
]


def _last_message_by_stage(events: list) -> dict:
    """Último mensaje visto por cada etapa, desde los eventos estructurados."""
    messages: dict = {}
    for ev in events or []:
        messages[ev["stage"]] = ev["message"]
    return messages


def _count_validator_rejections(events: list) -> int:
    """Cuántas veces el Validador rechazó (✗ Rechazada / ✗ Fuera de dominio)
    en esta consulta — a diferencia de _last_message_by_stage, que solo ve
    el ÚLTIMO mensaje por etapa (y tras un rechazo+aprobación posterior,
    ocultaría que hubo una vuelta atrás real). Ver ADR-0006/ADR-0007."""
    return sum(
        1 for ev in (events or [])
        if ev["stage"] == _Stage.VALIDADOR and ev["message"].startswith("✗")
    )


def _render_agent_flow_html(events: list) -> str:
    messages = _last_message_by_stage(events)
    finished = _Stage.FIN in messages or _Stage.ERROR in messages
    n_rejections = _count_validator_rejections(events)

    reached = [any(tag in messages for tag in node["tags"]) for node in _AGENT_FLOW_NODES]
    active_index = max((i for i, r in enumerate(reached) if r), default=-1)

    nodes_html = []
    for i, node in enumerate(_AGENT_FLOW_NODES):
        node_msg = next((messages[t] for t in node["tags"] if t in messages), None)

        if i == active_index and not finished:
            status = "active"
        elif reached[i]:
            status = "done"
        else:
            status = "pending"

        decision_cls = " decision" if node.get("decision") else ""
        detail = html.escape(node_msg[:60]) if node_msg else "—"
        title_attr = html.escape(node_msg) if node_msg else node["label"]

        nodes_html.append(
            f'<div class="agent-flow-node-wrap {status}{decision_cls}">'
            f'<div class="agent-flow-node {status}{decision_cls}" title="{title_attr}">{node["icon"]}</div>'
            f'<div class="agent-flow-label">{node["label"]}</div>'
            f'<div class="agent-flow-detail">{detail}</div>'
            f'</div>'
        )

        if i < len(_AGENT_FLOW_NODES) - 1:
            dest_index = i + 1
            if active_index < 0:
                line_status = "pending"
            elif finished:
                line_status = "done" if dest_index <= active_index else "pending"
            elif dest_index < active_index:
                line_status = "done"
            elif dest_index == active_index:
                line_status = "flowing"
            else:
                line_status = "pending"
            nodes_html.append(f'<div class="agent-flow-line-wrap"><div class="agent-flow-line {line_status}"></div></div>')

    backline_html = ""
    if n_rejections > 0:
        # Arco de retroceso Validador→Refinador — visible solo si hubo al
        # menos 1 rechazo real (si el Validador aprobó a la primera, no hay
        # loop que mostrar). "flowing" mientras la consulta sigue en curso,
        # "done" fijo con el badge ×N al terminar (ver ADR-0006/ADR-0007).
        n_total = len(_AGENT_FLOW_NODES)
        refinador_i = next(i for i, n in enumerate(_AGENT_FLOW_NODES) if _Stage.REFINADOR in n["tags"])
        validador_i = next(i for i, n in enumerate(_AGENT_FLOW_NODES) if _Stage.VALIDADOR in n["tags"])
        left_pct = (refinador_i + 0.5) / n_total * 100
        width_pct = (validador_i - refinador_i) / n_total * 100
        back_status = "done" if finished else "flowing"
        backline_html = (
            f'<div class="agent-flow-backline {back_status}" '
            f'style="left:{left_pct:.2f}%;width:{width_pct:.2f}%">'
            f'<span class="agent-flow-backline-badge">×{n_rejections}</span>'
            f'</div>'
        )

    return f'<div class="agent-flow-track">{"".join(nodes_html)}{backline_html}</div>'


# ── Contexto conversacional (ADR-0010) ──────────────────────────────────────────
# Funciones puras (sin closure sobre `coordinator`) — viven a nivel de módulo
# para poder testearlas directo, mismo criterio que _render_agent_flow_html.

def _text_only(content) -> str:
    """Extrae solo las partes de texto de un content de gr.Chatbot (puede
    ser str, o lista mixta de str/dict con imágenes adjuntas)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(p for p in content if isinstance(p, str))
    return ""


def _extract_previous_exchange(history: list) -> tuple:
    """
    Último intercambio (pregunta+respuesta) del historial, como texto
    plano — (None, None) si no hay turno previo o si el turno era solo
    multimedia sin texto. Se llama sobre `history` ANTES de appendear el
    turno nuevo — ver ADR-0010 (contexto conversacional).
    """
    if not history:
        return None, None
    last_user = next((h for h in reversed(history) if h["role"] == "user"), None)
    last_assistant = next((h for h in reversed(history) if h["role"] == "assistant"), None)
    prev_q = _text_only(last_user["content"]).strip() if last_user else ""
    prev_a = _text_only(last_assistant["content"]).strip() if last_assistant else ""
    return (prev_q or None), (prev_a or None)


# ── Main interface ────────────────────────────────────────────────────────────

def build_interface(coordinator) -> gr.Blocks:
    import os
    import uuid
    from PIL import Image as _PILImage
    from config import TEMP_DIR
    import config

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _save_pil_temp(img) -> str | None:
        """Save PIL image to a unique temp file so chatbot can display it."""
        if img is None:
            return None
        if isinstance(img, str) and os.path.exists(img):
            return img
        if isinstance(img, _PILImage.Image):
            path = os.path.join(TEMP_DIR, f"chat_{uuid.uuid4().hex[:10]}.jpg")
            img.save(path, "JPEG", quality=85)
            return path
        return None

    # IMAGE_EXTS / VIDEO_EXTS para detección por extensión
    _IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".tif"}
    _VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".m4v", ".flv", ".wmv"}

    def _detect_media(media_path: str | None):
        """
        Detecta si un archivo es imagen o video.
        Retorna ("image", PIL.Image) | ("video", filepath) | (None, None).
        Estrategia: MIME type → extensión → intento de apertura PIL.
        """
        if media_path is None:
            return None, None
        import mimetypes
        mime, _ = mimetypes.guess_type(media_path)
        ext = os.path.splitext(media_path)[1].lower()
        # Decisión por MIME
        if mime:
            if mime.startswith("video"):
                return "video", media_path
            if mime.startswith("image"):
                try:
                    return "image", _PILImage.open(media_path).convert("RGB")
                except Exception:
                    pass
        # Decisión por extensión
        if ext in _VIDEO_EXTS:
            return "video", media_path
        if ext in _IMAGE_EXTS:
            try:
                return "image", _PILImage.open(media_path).convert("RGB")
            except Exception:
                pass
        # Último recurso: intentar PIL
        try:
            return "image", _PILImage.open(media_path).convert("RGB")
        except Exception:
            return "video", media_path

    def _user_chat_content(text: str, image, video, audio):
        """
        Construye el contenido del bubble de usuario en gr.Chatbot (Gradio 6).
        image: PIL.Image | None
        video: filepath str | None
        audio: filepath str | None
        """
        parts = []
        img_path = _save_pil_temp(image)
        if img_path:
            parts.append({"path": img_path, "is_stream": False})
        if video:
            parts.append("📹 *Video adjunto*")
        if audio:
            parts.append("🎤 *Audio adjunto*")
        if text and text.strip():
            parts.append(text.strip())
        if not parts:
            return "(consulta vacía)"
        return parts if len(parts) > 1 else parts[0]

    # ── Event handlers ───────────────────────────────────────────────────────

    def send(text, media, audio, history):
        """
        Recibe un único campo multimedia (imagen O video) + audio + texto.
        Detecta automáticamente si media es imagen o video y lo enruta al
        parámetro correcto de coordinator.process().
        """
        if not text and media is None and audio is None:
            yield (history or []), "", None, _rag_panel_html([]), None, "", _render_agent_flow_html([])
            return

        media_type, media_data = _detect_media(media)
        image = media_data if media_type == "image" else None
        video = media_data if media_type == "video" else None

        # Contexto conversacional: extraído ANTES de appendear los bubbles
        # nuevos, para no capturar el turno actual como "anterior" (ADR-0010).
        previous_query, previous_answer = _extract_previous_exchange(history)

        history = list(history or [])
        history.append({
            "role": "user",
            "content": _user_chat_content(text, image, video, audio),
        })
        history.append({
            "role": "assistant",
            "content": "⏳ Analizando consulta...",
        })

        # Primer yield: muestra bubble de usuario + limpia entradas
        yield history, "", None, _rag_panel_html([]), None, "", _render_agent_flow_html([])

        # Streaming del pipeline
        for stt, resp, audio_path, logs in coordinator.process(
            image_input=image,
            audio_input=audio,
            text_input=text,
            video_input=video,
            previous_query=previous_query,
            previous_answer=previous_answer,
        ):
            # Respuesta limpia y fuentes estructuradas directo del agente —
            # sin re-parsear el texto del chat (candidata B del review).
            if resp:
                main_text = coordinator.response_agent.last_answer or resp
                rag_html = _rag_panel_html(coordinator.response_agent.last_sources)
            else:
                main_text, rag_html = "", _rag_panel_html([])

            # Voz sin texto: actualiza bubble con transcripción STT
            if stt and not (text and text.strip()):
                history[-2]["content"] = _user_chat_content(stt, image, video, audio)

            history[-1]["content"] = main_text if main_text else "⏳ Procesando..."
            # Eventos estructurados directo del LogAgent — el diagrama no
            # re-parsea el texto del log (el string `logs` queda solo para
            # el panel de trazabilidad humano).
            yield history, "", None, rag_html, audio_path, logs, \
                _render_agent_flow_html(coordinator.log_agent.get_events())

    def clear_all():
        return [], "", None, None, _rag_panel_html([]), None, "", _render_agent_flow_html([])

    def toggle_agent_flow(is_visible):
        new_state = not is_visible
        label = "🕸️  Ocultar Flujo de Agentes" if new_state else "🕸️  Ver Flujo de Agentes"
        return new_state, gr.update(visible=new_state), gr.update(value=label)

    def take_screenshot():
        """Captura pantalla y guarda en temp/ — retorna ruta para gr.File."""
        pil_img = capture_screenshot()
        if pil_img is None:
            return None
        path = os.path.join(TEMP_DIR, f"screenshot_{uuid.uuid4().hex[:8]}.jpg")
        pil_img.save(path, "JPEG", quality=90)
        return path

    # ── Layout ───────────────────────────────────────────────────────────────

    with gr.Blocks(title=GRADIO_TITLE) as demo:
        gr.HTML(f"<style>{CSS}</style>")

        # ── Ecuador topbar + header ───────────────────────────────────────
        # Badge dinámico: RAG/GraphRAG/STT/Visión/TTS siguen 100% locales
        # siempre — solo el LLM de texto puede ser local o cloud (ADR-0008).
        _llm_badge = (
            f"🌐 LLM Cloud ({html.escape(LLM_MODEL)})" if is_cloud_model(LLM_MODEL)
            else "💻 100% Local"
        )
        gr.HTML(f"""
        <div class="sri-topbar" role="presentation"></div>
        <header class="sri-header">
            <div class="sri-header-badge" role="status">
                <span class="dot" aria-hidden="true"></span>
                Sistema Activo &middot; {_llm_badge}
            </div>
            <h1>⚖️ SRI IA Multimodal</h1>
            <p class="subtitle">
                Asistente Virtual de Normativa Tributaria &nbsp;&middot;&nbsp;
                Servicio de Rentas Internas del Ecuador
            </p>
            <div class="tech-chips" role="list" aria-label="Tecnologías del sistema">
                <span class="chip chip-hybrid" role="listitem">RAG + GraphRAG Híbrido</span>
                <span class="chip" role="listitem">Ollama</span>
                <span class="chip" role="listitem">ChromaDB &middot; OpenCLIP</span>
                <span class="chip chip-graph" role="listitem">NetworkX &middot; Grafo</span>
                <span class="chip" role="listitem">Whisper STT</span>
                <span class="chip" role="listitem">Piper TTS</span>
                <span class="chip" role="listitem">Moondream Vision</span>
            </div>
            <p class="institution">
                Maestría en Inteligencia Artificial Aplicada &nbsp;&middot;&nbsp; UIsrael
            </p>
        </header>
        """)

        # ── Disclaimer ────────────────────────────────────────────────────
        gr.HTML("""
        <div class="disclaimer-bar" role="note">
            &#9888;&nbsp; Las respuestas son <strong>orientativas e informativas</strong>.
            No constituyen asesoría legal ni tributaria definitiva.
            Verifique siempre en <strong>sri.gob.ec</strong> o consulte con un profesional.
        </div>
        """)

        with gr.Tabs():

            # ═══════════════════════════════════════════════════════════════
            # TAB 1 — Consulta Tributaria (chat)
            # ═══════════════════════════════════════════════════════════════
            with gr.Tab("⚖️  Consulta Tributaria"):

                with gr.Row(equal_height=False):

                    # ── Columna chat (izquierda) ──────────────────────────
                    with gr.Column(scale=3, min_width=420):

                        # Historial de conversación
                        chatbot = gr.Chatbot(
                            value=[],
                            height=460,
                            show_label=False,
                            elem_classes=["chat-window"],
                            placeholder=(
                                "Bienvenido al asistente tributario SRI.\n"
                                "Escribe tu consulta abajo, o adjunta una imagen, audio o video."
                            ),
                            render_markdown=True,
                            layout="bubble",
                            buttons=["copy"],
                        )

                        # Adjuntos — acordeón colapsable
                        with gr.Accordion(
                            "📎  Adjuntar multimedia — imagen o video + audio se combinan con tu consulta",
                            open=False,
                            elem_classes=["attach-accordion"],
                        ):
                            with gr.Row():
                                media_input = gr.File(
                                    label="📷 Imagen / 📹 Video — sube cualquiera de los dos",
                                    file_types=["image", "video"],
                                    file_count="single",
                                    scale=1,
                                    elem_classes=["attach-media"],
                                )
                                with gr.Column(scale=1):
                                    audio_input = gr.Audio(
                                        label="🎤 Voz / Audio",
                                        sources=["microphone", "upload"],
                                        type="filepath",
                                    )

                            btn_screenshot = gr.Button(
                                "📸  Capturar Pantalla del Portal SRI (guarda como imagen)",
                                variant="secondary",
                                size="sm",
                                elem_classes=["btn-screenshot"],
                            )

                        # Compositor de mensajes
                        with gr.Row(elem_classes=["composer-row"]):
                            text_input = gr.Textbox(
                                placeholder=(
                                    "Escribe tu consulta tributaria...  "
                                    "Puedes adjuntar imagen, audio o video arriba  ·  Enter para enviar"
                                ),
                                lines=2,
                                max_lines=6,
                                show_label=False,
                                scale=5,
                                elem_classes=["chat-input"],
                            )
                            with gr.Column(scale=1, min_width=110):
                                btn_send = gr.Button(
                                    "Enviar ↗",
                                    variant="primary",
                                    elem_classes=["btn-send"],
                                )
                                btn_clear = gr.Button(
                                    "Limpiar",
                                    variant="secondary",
                                    size="sm",
                                    elem_classes=["btn-clear"],
                                )

                    # ── Columna lateral (derecha) ─────────────────────────
                    with gr.Column(scale=2, min_width=280, elem_classes=["chat-sidebar"]):

                        gr.HTML("""
                        <div class="section-title blue" style="margin-bottom:4px">
                            <div class="icon-wrap" aria-hidden="true">&#128269;</div>
                            <span>Fragmentos Normativos Recuperados</span>
                        </div>
                        """)

                        rag_output = gr.HTML(value=_rag_panel_html([]))

                        audio_output = gr.Audio(
                            label="Respuesta en Voz · Piper TTS · Español",
                            type="filepath",
                            autoplay=True,
                            interactive=False,
                        )

                # ── Flujo de agentes en vivo (toggle) ─────────────────────
                btn_agent_flow = gr.Button(
                    "🕸️  Ver Flujo de Agentes",
                    variant="secondary",
                    size="sm",
                    elem_classes=["agent-flow-toggle"],
                )
                agent_flow_visible = gr.State(False)
                with gr.Column(visible=False, elem_classes=["agent-flow-panel"]) as agent_flow_panel:
                    gr.HTML("""
                    <div class="section-title gold" style="margin-bottom:2px">
                        <div class="icon-wrap" aria-hidden="true">🕸️</div>
                        <span>Flujo de Agentes — Consulta en Vivo</span>
                    </div>
                    <p style="font-size:0.72rem;color:var(--text-muted);margin:4px 0 12px">
                        Cada nodo es un agente del pipeline. El nodo dorado pulsante
                        es el que está trabajando ahora mismo. El Planner (borde
                        punteado) es el único que <em>decide</em> — el resto ejecuta
                        una tarea fija. Pasá el cursor sobre un nodo para ver el
                        mensaje completo de esa etapa.
                    </p>
                    """)
                    agent_flow_output = gr.HTML(value=_render_agent_flow_html([]))

                # ── Trazabilidad del pipeline (colapsable) ────────────────
                with gr.Accordion(
                    "🔎  Trazabilidad — Pipeline RAG + GraphRAG Híbrido",
                    open=False,
                    elem_classes=["logs-accordion"],
                ):
                    gr.HTML("""
                    <div class="logs-pipeline" role="list" aria-label="Etapas del pipeline"
                         style="margin:8px 0">
                        <span class="pipeline-step" role="listitem">INICIO</span>
                        <span class="arrow">&#8594;</span>
                        <span class="pipeline-step" role="listitem">STT</span>
                        <span class="arrow">&#8594;</span>
                        <span class="pipeline-step" role="listitem">VISION</span>
                        <span class="arrow">&#8594;</span>
                        <span class="pipeline-step pipeline-step-hybrid" role="listitem">RAG Vector</span>
                        <span class="arrow">&#8214;</span>
                        <span class="pipeline-step pipeline-step-graph" role="listitem">GRAPH</span>
                        <span class="arrow">&#8594;</span>
                        <span class="pipeline-step pipeline-step-hybrid" role="listitem">HYBRID</span>
                        <span class="arrow">&#8594;</span>
                        <span class="pipeline-step" role="listitem">GENERANDO</span>
                        <span class="arrow">&#8594;</span>
                        <span class="pipeline-step" role="listitem">TTS</span>
                        <span class="arrow">&#8594;</span>
                        <span class="pipeline-step" role="listitem">FIN</span>
                    </div>
                    """)
                    logs_output = gr.Textbox(
                        lines=8,
                        interactive=False,
                        show_label=False,
                        elem_classes=["logs-console"],
                        placeholder=(
                            "[HH:MM:SS] [INICIO] Asistente SRI IA Multimodal iniciado.\n"
                            "[HH:MM:SS] [STT]    Transcribiendo consulta de audio...\n"
                            "[HH:MM:SS] [VISION] Analizando imagen con Moondream...\n"
                            "[HH:MM:SS] [RAG]    Buscando normativa: vector + grafo híbrido...\n"
                            "[HH:MM:SS] [GRAPH]  ✓ Entidades detectadas: IVA, RUC... | N triples.\n"
                            f"[HH:MM:SS] [GENERANDO] Generando respuesta con {config.LLM_MODEL}...\n"
                            "[HH:MM:SS] [TTS]    Sintetizando audio con Piper TTS...\n"
                            "[HH:MM:SS] [FIN]    Consulta procesada correctamente."
                        ),
                    )

            # ═══════════════════════════════════════════════════════════════
            # TAB 2 — Base de Conocimiento (se refresca al entrar a la tab)
            # ═══════════════════════════════════════════════════════════════
            with gr.Tab("📚  Base de Conocimiento") as tab_knowledge:
                knowledge_html = gr.HTML(value=_knowledge_tab_html())

            # ═══════════════════════════════════════════════════════════════
            # TAB 2b — Benchmark RAGAS (tesis; se refresca al entrar)
            # ═══════════════════════════════════════════════════════════════
            with gr.Tab("📊  Benchmark RAGAS") as tab_benchmark:
                benchmark_html = gr.HTML(value=_benchmark_tab_html())
                _initial_models = _benchmark_model_names()
                model_dropdown = gr.Dropdown(
                    label="Ver detalle de un modelo",
                    choices=_initial_models,
                    value=(_initial_models[0] if _initial_models else None),
                )
                model_detail_html = gr.HTML(value=_model_detail_html(_initial_models[0]) if _initial_models else "")

            # ═══════════════════════════════════════════════════════════════
            # TAB 3 — Estado del Sistema (se refresca al entrar)
            # ═══════════════════════════════════════════════════════════════
            with gr.Tab("⚙️  Estado del Sistema") as tab_system:
                system_html = gr.HTML(value=_system_tab_html())

            # ═══════════════════════════════════════════════════════════════
            # TAB 4 — Guía de Uso
            # ═══════════════════════════════════════════════════════════════
            with gr.Tab("📖  Guia de Uso"):
                _build_guide_tab()

        # ── Footer ────────────────────────────────────────────────────────
        # RAG/GraphRAG/STT/Visión/TTS son 100% locales en cualquier caso —
        # solo el LLM de generación puede ser cloud (ADR-0008), así que ya
        # no se puede prometer "sin conexión a internet" a secas.
        gr.HTML("""
        <footer class="sri-footer">
            SRI IA Multimodal &nbsp;&middot;&nbsp;
            RAG + GraphRAG 100% local &middot; LLM configurable (local o Ollama Cloud)
            &nbsp;&middot;&nbsp; Ollama &middot; ChromaDB &middot; Whisper &middot;
            Piper TTS &middot; Moondream &nbsp;&middot;&nbsp; Maestría IA Aplicada &middot; UIsrael
        </footer>
        """)

        # ── Event bindings ────────────────────────────────────────────────
        _send_inputs  = [text_input, media_input, audio_input, chatbot]
        _send_outputs = [
            chatbot, text_input, media_input,
            rag_output, audio_output, logs_output, agent_flow_output,
        ]

        btn_send.click(fn=send, inputs=_send_inputs, outputs=_send_outputs)
        text_input.submit(fn=send, inputs=_send_inputs, outputs=_send_outputs)
        btn_screenshot.click(fn=take_screenshot, inputs=[], outputs=[media_input])
        btn_clear.click(fn=clear_all, inputs=[], outputs=[
            chatbot, text_input, media_input, audio_input,
            rag_output, audio_output, logs_output, agent_flow_output,
        ])
        btn_agent_flow.click(
            fn=toggle_agent_flow,
            inputs=[agent_flow_visible],
            outputs=[agent_flow_visible, agent_flow_panel, btn_agent_flow],
        )

        # Refresh al entrar a cada tab dinámica — los datos (Chroma, grafo,
        # benchmarks en disco) se recalculan en ese momento, no quedan
        # congelados al arranque de la app (candidata C del review).
        tab_knowledge.select(fn=_knowledge_tab_html, outputs=[knowledge_html])
        tab_benchmark.select(fn=_benchmark_tab_html, outputs=[benchmark_html])
        tab_benchmark.select(fn=_benchmark_model_choices, outputs=[model_dropdown])
        tab_benchmark.select(fn=_benchmark_first_model_detail_html, outputs=[model_detail_html])
        model_dropdown.change(fn=_model_detail_html, inputs=[model_dropdown], outputs=[model_detail_html])
        tab_system.select(fn=_system_tab_html, outputs=[system_html])

    return demo


# ── Tabs auxiliares ───────────────────────────────────────────────────────────
# Cada tab dinámica se separa en dos: _X_tab_html() calcula los datos EN EL
# MOMENTO de llamarse (Chroma, grafo, benchmarks en disco) y retorna el HTML;
# el componente se registra una vez y se refresca con el evento Tab.select —
# antes los datos se horneaban al arrancar la app y quedaban congelados.

def _knowledge_tab_html() -> str:
    import config, chromadb, glob, os, json

    n_chunks = 0
    try:
        client = chromadb.PersistentClient(path=config.CHROMA_DB_PATH)
        col = client.get_collection(config.CHROMA_COLLECTION)
        n_chunks = col.count()
    except Exception:
        pass

    # GraphRAG stats
    g_nodes = g_edges = 0
    g_enabled = getattr(config, 'GRAPH_ENABLED', False)
    g_docs = 0
    g_rel_types = {}
    g_build_seconds = 0.0
    try:
        gpath = getattr(config, 'GRAPH_DB_PATH', '')
        if gpath and os.path.exists(gpath):
            with open(gpath, encoding='utf-8') as f:
                gdata = json.load(f)
            meta = gdata.get('metadata', {})
            g_nodes = meta.get('n_nodes', 0)
            g_edges = meta.get('n_edges', 0)
            g_docs  = meta.get('n_documents', 0)
            g_build_seconds = meta.get('build_seconds', 0.0)
            # Contar tipos de relación desde aristas. El JSON guardado por
            # GraphStore.save() usa "relation" (str) por fila, una fila por
            # evidencia — no "relations" (dict), que es solo la forma en
            # memoria de GraphStore.G. Leer la llave equivocada dejaba esto
            # siempre vacío.
            for e in gdata.get('edges', []):
                rel = e.get('relation')
                if rel:
                    g_rel_types[rel] = g_rel_types.get(rel, 0) + 1
    except Exception:
        pass

    # Tiempo de construcción del vector store (ver rag/ingesta.py)
    v_build_seconds = 0.0
    try:
        vpath = getattr(config, 'VECTOR_BUILD_METADATA_PATH', '')
        if vpath and os.path.exists(vpath):
            with open(vpath, encoding='utf-8') as f:
                v_build_seconds = json.load(f).get('build_seconds', 0.0)
    except Exception:
        pass

    def _fmt_duration(seconds: float) -> str:
        if seconds <= 0:
            return "—"
        seconds = int(seconds)
        h, rem = divmod(seconds, 3600)
        m, s = divmod(rem, 60)
        if h:
            return f"{h}h {m}m"
        if m:
            return f"{m}m {s}s"
        return f"{s}s"

    graph_status_color = "#10b981" if g_nodes > 0 else ("#f59e0b" if g_enabled else "#ef4444")
    graph_status_text  = f"{g_nodes} nodos" if g_nodes > 0 else ("Sin grafo" if g_enabled else "Desactivado")

    pdf_backend_label = "MinerU (layout + tablas + OCR)" if getattr(config, 'USE_MINERU_PDF', False) \
        else "PyMuPDF (texto plano)"
    pdf_backend_color = "#a78bfa" if getattr(config, 'USE_MINERU_PDF', False) else "#f59e0b"

    doc_counts = {}
    for data_dir in config.get_data_dirs():
        tipo = os.path.basename(data_dir)
        count = sum(
            len(glob.glob(os.path.join(data_dir, f"*{ext}")))
            for ext in [".pdf", ".txt", ".docx", ".md"]
        )
        doc_counts[tipo] = count

    total_docs = sum(doc_counts.values())
    status_color = "#10b981" if n_chunks > 0 else "#ef4444"
    status_text  = "Activa" if n_chunks > 0 else "Vacía"

    rows_html = "".join(
        f"<tr><td>{tipo}</td>"
        f"<td style='text-align:center;color:#fbbf24;font-weight:700'>{count}</td>"
        f"<td style='text-align:center;color:#6ee7b7'>"
        f"{'&#10003;' if count > 0 else '<span style=\"color:#64748b\">&mdash;</span>'}</td></tr>"
        for tipo, count in doc_counts.items()
    )

    rel_badges = "".join(
        f'<span style="background:rgba(245,158,11,0.1);border:1px solid rgba(245,158,11,0.25);'
        f'border-radius:4px;padding:2px 8px;font-size:0.68rem;color:#fbbf24;white-space:nowrap">'
        f'{rel} <span style="color:#8b9ab5">({cnt})</span></span> '
        for rel, cnt in sorted(g_rel_types.items(), key=lambda x: -x[1])
    ) if g_rel_types else '<span style="color:#64748b;font-size:0.78rem">Sin relaciones extraídas aún</span>'

    return (f"""
    <div style="padding: 20px 8px; animation: slideInUp 0.4s ease;">

      <div class="stat-grid">
        <div class="stat-card">
          <div class="stat-value">{n_chunks}</div>
          <div class="stat-label">Fragmentos en ChromaDB</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{total_docs}</div>
          <div class="stat-label">Documentos Cargados</div>
        </div>
        <div class="stat-card">
          <div class="stat-value" style="color:{status_color};font-size:1.2rem">{status_text}</div>
          <div class="stat-label">Base Vectorial RAG</div>
        </div>
        <div class="stat-card">
          <div class="stat-value" style="color:{graph_status_color};font-size:1.2rem">{graph_status_text}</div>
          <div class="stat-label">Grafo GraphRAG</div>
        </div>
      </div>

      <!-- Ingesta: backend PDF + tiempos de construcción -->
      <h3 style="color:#f59e0b;font-size:0.85rem;font-weight:700;text-transform:uppercase;
                 letter-spacing:0.08em;margin:20px 0 10px;border-bottom:1px solid #1e3a5f;
                 padding-bottom:8px">
        Ingesta &mdash; Backend y Tiempos de Construcci&oacute;n
      </h3>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px;margin-bottom:12px">
        <div class="stat-card" style="padding:12px">
          <div class="stat-value" style="font-size:1.05rem;color:{pdf_backend_color}">{pdf_backend_label}</div>
          <div class="stat-label">Backend de parseo PDF</div>
        </div>
        <div class="stat-card" style="padding:12px">
          <div class="stat-value" style="font-size:1.4rem;color:#93c5fd">{_fmt_duration(v_build_seconds)}</div>
          <div class="stat-label">Construcci&oacute;n Base Vectorial (acumulado)</div>
        </div>
        <div class="stat-card" style="padding:12px">
          <div class="stat-value" style="font-size:1.4rem;color:#a78bfa">{_fmt_duration(g_build_seconds)}</div>
          <div class="stat-label">Construcci&oacute;n GraphRAG (acumulado)</div>
        </div>
      </div>
      <p style="font-size:0.76rem;color:#64748b;margin:0 0 16px">
        "Acumulado" suma el tiempo de todas las corridas desde el último <code>--reset</code>
        (incluye corridas interrumpidas y retomadas).
      </p>

      <!-- GraphRAG panel -->
      <h3 style="color:#f59e0b;font-size:0.85rem;font-weight:700;text-transform:uppercase;
                 letter-spacing:0.08em;margin:20px 0 10px;border-bottom:1px solid #1e3a5f;
                 padding-bottom:8px">
        Grafo de Conocimiento Tributario (GraphRAG)
      </h3>

      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px;margin-bottom:12px">
        <div class="stat-card" style="padding:12px">
          <div class="stat-value" style="font-size:1.6rem;color:#a78bfa">{g_nodes}</div>
          <div class="stat-label">Entidades</div>
        </div>
        <div class="stat-card" style="padding:12px">
          <div class="stat-value" style="font-size:1.6rem;color:#a78bfa">{g_edges}</div>
          <div class="stat-label">Relaciones</div>
        </div>
        <div class="stat-card" style="padding:12px">
          <div class="stat-value" style="font-size:1.6rem;color:#a78bfa">{len(g_rel_types)}</div>
          <div class="stat-label">Tipos Relación</div>
        </div>
        <div class="stat-card" style="padding:12px">
          <div class="stat-value" style="font-size:1.1rem;color:{'#10b981' if g_enabled else '#ef4444'}">
            {'ON' if g_enabled else 'OFF'}
          </div>
          <div class="stat-label">GRAPH_ENABLED</div>
        </div>
      </div>

      <div class="info-card" style="margin-bottom:8px">
        <strong style="color:#c4b5fd">Relaciones extraídas por tipo:</strong><br>
        <div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:8px">{rel_badges}</div>
      </div>

      <div class="info-card gold" style="margin-bottom:16px">
        <strong style="color:#e8edf5">Reconstruir grafo tras agregar documentos:</strong><br>
        <code style="color:#fbbf24">python scripts/build_graph.py --reset</code>
        &nbsp;&middot;&nbsp; Reconstruir desde cero<br>
        <code style="color:#fbbf24">python scripts/build_graph.py --stats-only</code>
        &nbsp;&middot;&nbsp; Ver estadísticas sin reconstruir<br>
        <code style="color:#fbbf24">python scripts/build_graph.py --export-graphml</code>
        &nbsp;&middot;&nbsp; Exportar a Gephi/Cytoscape
      </div>

      <h3 style="color:#f59e0b;font-size:0.85rem;font-weight:700;text-transform:uppercase;
                 letter-spacing:0.08em;margin:20px 0 10px;border-bottom:1px solid #1e3a5f;
                 padding-bottom:8px">
        Documentos por Categoría
      </h3>
      <table style="width:100%;border-collapse:collapse;font-size:0.83rem" role="table">
        <thead>
          <tr style="background:#141d2e">
            <th style="text-align:left;padding:9px 12px;color:#8b9ab5;font-size:0.72rem;
                       text-transform:uppercase;letter-spacing:0.06em;border-bottom:1px solid #1e3a5f"
                scope="col">Tipo de Normativa</th>
            <th style="text-align:center;padding:9px 12px;color:#8b9ab5;font-size:0.72rem;
                       text-transform:uppercase;letter-spacing:0.06em;border-bottom:1px solid #1e3a5f"
                scope="col">Documentos</th>
            <th style="text-align:center;padding:9px 12px;color:#8b9ab5;font-size:0.72rem;
                       text-transform:uppercase;letter-spacing:0.06em;border-bottom:1px solid #1e3a5f"
                scope="col">Estado</th>
          </tr>
        </thead>
        <tbody>{rows_html}</tbody>
      </table>

      <h3 style="color:#f59e0b;font-size:0.85rem;font-weight:700;text-transform:uppercase;
                 letter-spacing:0.08em;margin:20px 0 10px;border-bottom:1px solid #1e3a5f;
                 padding-bottom:8px">
        Cómo Cargar Documentos SRI
      </h3>

      <div class="info-card">
        <strong style="color:#e8edf5">Paso 1 &mdash; Copiar documentos</strong><br>
        Cada subcarpeta de <code>data/</code> es una categoría — el nombre de la
        carpeta se usa como tipo de normativa (ver tabla de categorías arriba).
      </div>

      <div class="info-card gold" style="margin-top:8px">
        <strong style="color:#e8edf5">Paso 2 &mdash; Reconstruir base vectorial + grafo</strong><br>
        <code style="color:#fbbf24">python rag/build_db.py --reset</code>
        &nbsp;&middot;&nbsp; Reconstruye vectores ChromaDB<br>
        <code style="color:#fbbf24">python scripts/build_graph.py --reset</code>
        &nbsp;&middot;&nbsp; Reconstruye grafo GraphRAG
      </div>

      <h3 style="color:#f59e0b;font-size:0.85rem;font-weight:700;text-transform:uppercase;
                 letter-spacing:0.08em;margin:20px 0 10px;border-bottom:1px solid #1e3a5f;
                 padding-bottom:8px">
        Formatos Soportados
      </h3>
      <table style="width:100%;border-collapse:collapse;font-size:0.82rem" role="table">
        <thead>
          <tr style="background:#141d2e">
            <th style="padding:8px 12px;color:#8b9ab5;font-size:0.72rem;text-transform:uppercase;
                       border-bottom:1px solid #1e3a5f" scope="col">Formato</th>
            <th style="padding:8px 12px;color:#8b9ab5;font-size:0.72rem;text-transform:uppercase;
                       border-bottom:1px solid #1e3a5f" scope="col">Soporte</th>
            <th style="padding:8px 12px;color:#8b9ab5;font-size:0.72rem;text-transform:uppercase;
                       border-bottom:1px solid #1e3a5f" scope="col">Metadatos Extra</th>
          </tr>
        </thead>
        <tbody>
          <tr><td><code>.pdf</code></td><td>&#10003; Total</td><td>Página, artículo detectado</td></tr>
          <tr><td><code>.txt</code></td><td>&#10003; Total</td><td>Artículo detectado</td></tr>
          <tr><td><code>.docx</code></td><td>&#10003; Total</td><td>Artículo detectado</td></tr>
          <tr><td><code>.md</code></td><td>&#10003; Total</td><td>Artículo detectado</td></tr>
        </tbody>
      </table>
    </div>
    """)


def _load_latest_summary() -> tuple[dict | None, str | None]:
    """
    Localiza y carga el JSON de resumen más reciente de
    scripts/run_benchmark.py. Retorna (summary, path) — (None, None) si no
    hay ninguno todavía. Compartido entre la tab de benchmark, el combo de
    modelos y la tarjeta de detalle — un solo lugar donde cambia cómo se
    localiza/carga el archivo.
    """
    import config, glob, json, os

    bench_dir = os.path.join(config.BASE_DIR, "outputs", "benchmarks")
    summaries = sorted(glob.glob(os.path.join(bench_dir, "*_summary.json")))
    if not summaries:
        return None, None

    latest_path = summaries[-1]
    try:
        with open(latest_path, encoding="utf-8") as f:
            return json.load(f), latest_path
    except Exception:
        return None, latest_path


def _benchmark_model_names() -> list[str]:
    """Nombres de modelo del último benchmark, ordenados — usado tanto para
    construir el combo inicial como para refrescarlo en tab_benchmark.select."""
    summary, _ = _load_latest_summary()
    return sorted((summary or {}).get("by_model", {}).keys())


def _benchmark_model_choices():
    """Actualización del combo de modelos (Gradio gr.update) — se refresca
    junto con benchmark_html en tab_benchmark.select."""
    models = _benchmark_model_names()
    return gr.update(choices=models, value=(models[0] if models else None))


def _benchmark_first_model_detail_html() -> str:
    """Detalle del primer modelo del último benchmark (o vacío si no hay
    ninguno) — usado para refrescar la tarjeta al re-entrar a la tab."""
    models = _benchmark_model_names()
    return _model_detail_html(models[0]) if models else ""


def _model_detail_html(model: str) -> str:
    """
    Tarjeta de detalle de un modelo específico del último benchmark — solo
    lectura, no dispara ninguna corrida nueva (mismo principio que el resto
    de la tab: correr el benchmark sigue siendo por terminal).
    """
    if not model:
        return ""

    from services.benchmark_format import (
        fmt_number, fmt_planning_seconds, fmt_refinement, fmt_ragas_parts,
        fmt_rate_pct, fmt_tokens, is_cloud_model, EMPTY,
    )

    summary, _ = _load_latest_summary()
    v = (summary or {}).get("by_model", {}).get(model)
    if v is None:
        return "<div class='info-card'>Sin datos para este modelo en el último benchmark.</div>"

    def _ragas_cell(val, n_eval, n_total):
        base, note = fmt_ragas_parts(val, n_eval, n_total)
        if base is None:
            return EMPTY
        return f"{base} <span style='color:#64748b;font-size:0.72em'>({note})</span>" if note else base

    badge = "🌐 Cloud" if is_cloud_model(model) else "💻 Local"
    return f"""
    <div class="info-card" style="margin-top:12px">
      <strong style="color:#c4b5fd;font-size:0.95rem">{html.escape(model)}</strong>
      <span style="margin-left:8px;font-size:0.78rem;color:#93c5fd">{badge}</span><br>
      <table style="width:100%;border-collapse:collapse;font-size:0.82rem;margin-top:10px" role="table">
        <tbody>
          <tr><td style="padding:5px 8px;color:#8b9ab5">Preguntas evaluadas</td><td style="padding:5px 8px">{v.get('n', 0)}</td></tr>
          <tr><td style="padding:5px 8px;color:#8b9ab5">Refinamiento</td><td style="padding:5px 8px">{fmt_refinement(v.get('avg_refinement_seconds'), v.get('avg_refinement_iterations'))}</td></tr>
          <tr><td style="padding:5px 8px;color:#8b9ab5">Planning</td><td style="padding:5px 8px">{fmt_planning_seconds(v.get('avg_planning_seconds'))}</td></tr>
          <tr><td style="padding:5px 8px;color:#8b9ab5">Retrieval</td><td style="padding:5px 8px">{fmt_number(v.get('avg_retrieval_seconds'), 's')}</td></tr>
          <tr><td style="padding:5px 8px;color:#8b9ab5">Generación</td><td style="padding:5px 8px">{fmt_number(v.get('avg_generation_seconds'), 's')}</td></tr>
          <tr><td style="padding:5px 8px;color:#8b9ab5">Total</td><td style="padding:5px 8px;font-weight:700;color:#fbbf24">{fmt_number(v.get('avg_total_seconds'), 's')}</td></tr>
          <tr><td style="padding:5px 8px;color:#8b9ab5">Tokens promedio</td><td style="padding:5px 8px">{fmt_tokens(v.get('avg_total_tokens'))}</td></tr>
          <tr><td style="padding:5px 8px;color:#8b9ab5">Faithfulness</td><td style="padding:5px 8px">{_ragas_cell(v.get('avg_faithfulness'), v.get('n_faithfulness_evaluated', 0), v.get('n', 0))}</td></tr>
          <tr><td style="padding:5px 8px;color:#8b9ab5">Answer Relevancy</td><td style="padding:5px 8px">{_ragas_cell(v.get('avg_answer_relevancy'), v.get('n_answer_relevancy_evaluated', 0), v.get('n', 0))}</td></tr>
        </tbody>
      </table>
    </div>
    """


def _benchmark_tab_html() -> str:
    """
    Solo lectura: resumen del último benchmark corrido con
    scripts/run_benchmark.py (RAG vs GraphRAG vs Híbrido vs Agéntico,
    validado con RAGAS). Correr el benchmark sigue siendo por terminal —
    esta tab no lanza procesos, solo lee el JSON más reciente al momento
    de entrar a la tab.
    """
    summary, latest_path = _load_latest_summary()

    if summary is None and latest_path is None:
        return """
        <div style="padding: 20px 8px; animation: slideInUp 0.4s ease;">
          <div class="info-card gold">
            <strong style="color:#e8edf5">Todavía no hay ningún benchmark corrido.</strong><br>
            Ejecuta desde terminal:<br>
            <code style="color:#fbbf24">python scripts/run_benchmark.py --limit 5</code>
            &nbsp;&middot;&nbsp; prueba rápida<br>
            <code style="color:#fbbf24">python scripts/run_benchmark.py</code>
            &nbsp;&middot;&nbsp; corrida completa (puede tardar horas en CPU)<br><br>
            Compara RAG vectorial, GraphRAG y modo híbrido — tiempo de
            respuesta y calidad (RAGAS: faithfulness, answer relevancy) —
            y permite comparar distintos modelos Ollama entre sí (local o
            cloud, ver ADR-0008).
          </div>
        </div>
        """
    if summary is None:
        return f"<div style='padding:20px'>Error leyendo {latest_path}</div>"

    # Convenciones de formato compartidas con scripts/run_benchmark.py —
    # la semántica ("—" vacío, "(N/total)" evaluación parcial) vive en
    # services/benchmark_format.py; acá solo se aplica el estilo visual.
    from services.benchmark_format import (
        EMPTY, fmt_number, fmt_planning_seconds, fmt_ragas_parts, fmt_rate_pct,
        fmt_tokens, is_cloud_model, compute_model_ranking,
    )

    def _fmt_ragas_styled(v, n_evaluated, n_total):
        base, note = fmt_ragas_parts(v, n_evaluated, n_total)
        if base is None:
            return EMPTY
        if note:
            return f"{base} <span style='color:#64748b;font-size:0.72em'>({note})</span>"
        return base

    def _rows(agg: dict) -> str:
        return "".join(
            f"<tr><td>{k}</td>"
            f"<td style='text-align:center'>{v.get('n', 0)}</td>"
            f"<td style='text-align:center;color:#93c5fd'>{fmt_planning_seconds(v.get('avg_planning_seconds'))}</td>"
            f"<td style='text-align:center;color:#93c5fd'>{fmt_number(v.get('avg_retrieval_seconds'), 's')}</td>"
            f"<td style='text-align:center;color:#93c5fd'>{fmt_number(v.get('avg_generation_seconds'), 's')}</td>"
            f"<td style='text-align:center;color:#fbbf24;font-weight:700'>{fmt_number(v.get('avg_total_seconds'), 's')}</td>"
            f"<td style='text-align:center;color:#a78bfa'>{_fmt_ragas_styled(v.get('avg_faithfulness'), v.get('n_faithfulness_evaluated', 0), v.get('n', 0))}</td>"
            f"<td style='text-align:center;color:#a78bfa'>{_fmt_ragas_styled(v.get('avg_answer_relevancy'), v.get('n_answer_relevancy_evaluated', 0), v.get('n', 0))}</td>"
            f"<td style='text-align:center;color:#6ee7b7'>{fmt_rate_pct(v.get('source_match_rate'))}</td>"
            f"<td style='text-align:center;color:#6ee7b7'>{fmt_rate_pct(v.get('planner_graph_usage_rate'))}</td>"
            f"</tr>"
            for k, v in sorted(agg.items())
        )

    thead = (
        "<thead><tr>"
        "<th style='text-align:left'>Grupo</th><th>N</th><th>Planning</th><th>Retrieval</th>"
        "<th>Generación</th><th>Total</th><th>Faithfulness</th>"
        "<th>Answer Relevancy</th><th>% Doc. correcto</th><th>Grafo usado (planner)</th>"
        "</tr></thead>"
    )

    def _model_rows(agg: dict) -> str:
        return "".join(
            f"<tr><td style='text-align:left'>{'🌐' if is_cloud_model(k) else '💻'} {k}</td>"
            f"<td style='text-align:center'>{v.get('n', 0)}</td>"
            f"<td style='text-align:center;color:#93c5fd'>{fmt_planning_seconds(v.get('avg_planning_seconds'))}</td>"
            f"<td style='text-align:center;color:#93c5fd'>{fmt_number(v.get('avg_retrieval_seconds'), 's')}</td>"
            f"<td style='text-align:center;color:#93c5fd'>{fmt_number(v.get('avg_generation_seconds'), 's')}</td>"
            f"<td style='text-align:center;color:#fbbf24;font-weight:700'>{fmt_number(v.get('avg_total_seconds'), 's')}</td>"
            f"<td style='text-align:center;color:#fcd34d'>{fmt_tokens(v.get('avg_total_tokens'))}</td>"
            f"<td style='text-align:center;color:#a78bfa'>{_fmt_ragas_styled(v.get('avg_faithfulness'), v.get('n_faithfulness_evaluated', 0), v.get('n', 0))}</td>"
            f"<td style='text-align:center;color:#a78bfa'>{_fmt_ragas_styled(v.get('avg_answer_relevancy'), v.get('n_answer_relevancy_evaluated', 0), v.get('n', 0))}</td>"
            f"</tr>"
            for k, v in sorted(agg.items())
        )

    model_thead = (
        "<thead><tr>"
        "<th style='text-align:left'>Modelo</th><th>N</th><th>Planning</th><th>Retrieval</th>"
        "<th>Generación</th><th>Total</th><th>Tokens</th><th>Faithfulness</th>"
        "<th>Answer Relevancy</th>"
        "</tr></thead>"
    )

    ranking = compute_model_ranking(summary.get('by_model', {}))
    ranking_html = ""
    if ranking:
        ranking_rows = "".join(
            f"<tr><td style='text-align:center'>#{i+1}</td>"
            f"<td style='text-align:left'>{'🌐' if r['is_cloud'] else '💻'} {r['model']}</td>"
            f"<td style='text-align:center;color:#fbbf24;font-weight:700'>{r['score']:.2f}</td></tr>"
            for i, r in enumerate(ranking)
        )
        ranking_html = f"""
      <h3 style="color:#f59e0b;font-size:0.85rem;font-weight:700;text-transform:uppercase;
                 letter-spacing:0.08em;margin:20px 0 10px;border-bottom:1px solid #1e3a5f;
                 padding-bottom:8px">
        🏆 Ranking Recomendado
      </h3>
      <table style="width:100%;border-collapse:collapse;font-size:0.83rem" role="table">
        <thead><tr><th style='text-align:center'>#</th><th style='text-align:left'>Modelo</th><th>Score</th></tr></thead>
        <tbody>{ranking_rows}</tbody>
      </table>
      <p style="font-size:0.75rem;color:#64748b;margin-top:8px">
        Heurística de comparación (ver ADR-0009), no una medición absoluta &mdash;
        score = 50% calidad (Faithfulness+Answer Relevancy) + 30% velocidad + 20%
        costo (tokens totales), normalizado entre los modelos de esta corrida.
        Modelos sin RAGAS evaluado quedan fuera del ranking.
      </p>
    """

    ragas_enabled = summary.get('ragas_enabled', True)
    ragas_warning = "" if ragas_enabled else """
      <div class="info-card gold" style="margin-bottom:16px;border-left-color:#f59e0b">
        <strong style="color:#fbbf24">⚠ Esta corrida usó <code>--no-ragas</code>:</strong>
        Faithfulness y Answer Relevancy salen vacíos (&mdash;) a propósito &mdash;
        no es un error, esa corrida solo midió tiempos. Para tenerlos, correr
        <code style="color:#fbbf24">python scripts/run_benchmark.py</code> sin ese flag.
      </div>
    """

    glossary = """
      <details style="margin-bottom:16px">
        <summary style="cursor:pointer;color:#93c5fd;font-size:0.85rem;font-weight:600">
          ¿Qué significa cada columna?
        </summary>
        <table style="width:100%;border-collapse:collapse;font-size:0.8rem;margin-top:10px" role="table">
          <tbody>
            <tr><td style="color:#c4b5fd;padding:6px 10px;white-space:nowrap">Planning</td>
                <td style="padding:6px 10px">Solo en el modo <code>agentic</code> &mdash; tiempo en que el <strong>PlannerAgent</strong> decide, vía tool-calling de Ollama, si esta consulta necesita GraphRAG además del RAG vectorial (que siempre corre). Vacío (&mdash;) en los demás modos, que no tienen este paso.</td></tr>
            <tr><td style="color:#c4b5fd;padding:6px 10px;white-space:nowrap">Retrieval</td>
                <td style="padding:6px 10px">Tiempo en <em>buscar</em> contexto — vectorial (ChromaDB) y/o grafo (NetworkX), según el modo.</td></tr>
            <tr><td style="color:#c4b5fd;padding:6px 10px">Generación</td>
                <td style="padding:6px 10px">Tiempo en que el LLM <em>redacta</em> la respuesta con ese contexto ya encontrado.</td></tr>
            <tr><td style="color:#c4b5fd;padding:6px 10px">Total</td>
                <td style="padding:6px 10px">Planning + Retrieval + Generación.</td></tr>
            <tr><td style="color:#c4b5fd;padding:6px 10px">Faithfulness</td>
                <td style="padding:6px 10px">0&ndash;1 (RAGAS) &mdash; si la respuesta está <em>basada</em> en el contexto recuperado, o el LLM inventó algo no sustentado ahí. Vacío (&mdash;) si se corrió con <code>--no-ragas</code>. Si ves "(2/3)" junto al número, el juez local no logró evaluar todas las preguntas del grupo (limitación de usar un modelo chico como juez, ver ADR-0003) — el promedio es solo de las que sí evaluó.</td></tr>
            <tr><td style="color:#c4b5fd;padding:6px 10px">Answer Relevancy</td>
                <td style="padding:6px 10px">0&ndash;1 (RAGAS) &mdash; si la respuesta contesta la pregunta hecha, sin divagar. Mismas reglas de vacío y "(N/total)" que Faithfulness.</td></tr>
            <tr><td style="color:#c4b5fd;padding:6px 10px">% Doc. correcto</td>
                <td style="padding:6px 10px">De las preguntas con retrieval vectorial, en cuántas se recuperó el documento fuente real esperado (según <code>preguntas.docx</code>). Vacío en <code>graph_only</code> a propósito &mdash; ese modo nunca consulta ChromaDB.</td></tr>
            <tr><td style="color:#c4b5fd;padding:6px 10px">Grafo usado (planner)</td>
                <td style="padding:6px 10px">Solo en el modo <code>agentic</code> &mdash; % de preguntas donde el PlannerAgent decidió activar GraphRAG. Es descriptivo, no una métrica de acierto: no hay forma objetiva de saber si "debería" haber usado grafo en cada pregunta.</td></tr>
          </tbody>
        </table>
        <p style="font-size:0.75rem;color:#64748b;margin-top:8px">
          Más tiempo no es mejor respuesta: un modo con más contexto (ej.
          híbrido) tarda más en generar porque el LLM tiene más texto que
          procesar antes de responder, no porque "razone más". La calidad se
          mide con Faithfulness / Answer Relevancy / % Doc. correcto.
        </p>
      </details>
    """

    return (f"""
    <div style="padding: 20px 8px; animation: slideInUp 0.4s ease;">

      {ragas_warning}

      <div class="info-card" style="margin-bottom:16px">
        <strong style="color:#c4b5fd">Último benchmark:</strong>
        {summary.get('generated_at', '—')} &mdash;
        {summary.get('n_questions', '?')} pregunta(s) &middot;
        modos: {', '.join(summary.get('modes', []))} &middot;
        modelos: {', '.join(summary.get('models', []))} &middot;
        {summary.get('n_rows', 0)} fila(s) totales<br>
        <span style="font-size:0.76rem;color:#64748b">
          Juez RAGAS: {summary.get('judge_model', '—')} &middot;
          Embeddings: {summary.get('embedding_model', '—')}
        </span>
      </div>

      {glossary}

      <h3 style="color:#f59e0b;font-size:0.85rem;font-weight:700;text-transform:uppercase;
                 letter-spacing:0.08em;margin:0 0 10px;border-bottom:1px solid #1e3a5f;
                 padding-bottom:8px">
        Por Modo de Recuperación
      </h3>
      <table style="width:100%;border-collapse:collapse;font-size:0.83rem" role="table">
        {thead}
        <tbody>{_rows(summary.get('by_mode', {}))}</tbody>
      </table>

      <h3 style="color:#f59e0b;font-size:0.85rem;font-weight:700;text-transform:uppercase;
                 letter-spacing:0.08em;margin:20px 0 10px;border-bottom:1px solid #1e3a5f;
                 padding-bottom:8px">
        Por Modelo LLM
      </h3>
      <table style="width:100%;border-collapse:collapse;font-size:0.83rem" role="table">
        {model_thead}
        <tbody>{_model_rows(summary.get('by_model', {}))}</tbody>
      </table>

      {ranking_html}

      <div class="info-card gold" style="margin-top:16px">
        <strong style="color:#e8edf5">Reporte completo (HTML) y datos crudos (CSV):</strong><br>
        <code style="color:#fbbf24">{latest_path.replace('_summary.json', '.html')}</code><br>
        <code style="color:#fbbf24">{latest_path.replace('_summary.json', '.csv')}</code>
      </div>
    </div>
    """)


def _system_tab_html() -> str:
    import config, torch, os

    cuda_ok = torch.cuda.is_available()
    graph_enabled = getattr(config, 'GRAPH_ENABLED', False)
    graph_db_path = getattr(config, 'GRAPH_DB_PATH', '')
    graph_exists = os.path.exists(graph_db_path) if graph_db_path else False
    graph_hop    = getattr(config, 'GRAPH_HOP_DEPTH', 2)
    graph_top_k  = getattr(config, 'GRAPH_TOP_K_TRIPLES', 10)
    graph_min_w  = getattr(config, 'GRAPH_MIN_WEIGHT', 0.4)

    mode_label = "Híbrido RAG + GraphRAG" if graph_enabled else "Solo RAG Vectorial"
    mode_color = "#a78bfa" if graph_enabled else "#f59e0b"

    return (f"""
    <div style="padding: 20px 8px; animation: slideInUp 0.4s ease;">

      <h3 style="color:#f59e0b;font-size:0.85rem;font-weight:700;text-transform:uppercase;
                 letter-spacing:0.08em;margin:0 0 12px;border-bottom:1px solid #1e3a5f;
                 padding-bottom:8px">
        Pipeline RAG + GraphRAG H&iacute;brido
      </h3>

      <div class="pipeline-flow" role="list" aria-label="Pipeline del sistema">
        <span class="pipeline-node entry" role="listitem">Audio</span>
        <span class="pipeline-arrow">&rarr;</span>
        <span class="pipeline-node entry" role="listitem">Imagen</span>
        <span class="pipeline-arrow">&rarr;</span>
        <span class="pipeline-node entry" role="listitem">Texto</span>
        <span class="pipeline-arrow">&rArr;</span>
        <span class="pipeline-node rag" role="listitem">Whisper STT</span>
        <span class="pipeline-arrow">+</span>
        <span class="pipeline-node rag" role="listitem">Moondream</span>
        <span class="pipeline-arrow">&rArr;</span>
        <span class="pipeline-node rag" role="listitem">OpenCLIP &rarr; ChromaDB</span>
        <span class="pipeline-arrow">&#8214;</span>
        <span class="pipeline-node graph" role="listitem">Entidades &rarr; NetworkX</span>
        <span class="pipeline-arrow">&rArr;</span>
        <span class="pipeline-node hybrid" role="listitem">HybridRetriever</span>
        <span class="pipeline-arrow">&rArr;</span>
        <span class="pipeline-node llm" role="listitem">LLM (Ollama)</span>
        <span class="pipeline-arrow">&rArr;</span>
        <span class="pipeline-node output" role="listitem">Respuesta + Citas</span>
        <span class="pipeline-arrow">&rArr;</span>
        <span class="pipeline-node output" role="listitem">Piper TTS</span>
      </div>

      <div class="info-card" style="margin:10px 0 18px;border-left-color:#a78bfa">
        <strong style="color:#c4b5fd">Modo activo:</strong>
        <span style="color:{mode_color};font-weight:700">&nbsp;{mode_label}</span>
        &nbsp;&mdash;&nbsp;
        <span style="color:#8b9ab5;font-size:0.82rem">
          Configurable con <code>GRAPH_ENABLED</code> en <code>config.py</code>.
          Si el grafo no existe, fallback autom&aacute;tico a RAG vectorial.
        </span>
      </div>

      <h3 style="color:#f59e0b;font-size:0.85rem;font-weight:700;text-transform:uppercase;
                 letter-spacing:0.08em;margin:20px 0 10px;border-bottom:1px solid #1e3a5f;
                 padding-bottom:8px">
        Estado de Componentes
      </h3>
      <table style="width:100%;border-collapse:collapse;font-size:0.83rem" role="table">
        <thead>
          <tr style="background:#141d2e">
            <th style="padding:8px 12px;color:#8b9ab5;font-size:0.72rem;text-transform:uppercase;
                       border-bottom:1px solid #1e3a5f" scope="col">Componente</th>
            <th style="padding:8px 12px;color:#8b9ab5;font-size:0.72rem;text-transform:uppercase;
                       border-bottom:1px solid #1e3a5f" scope="col">Valor / Estado</th>
          </tr>
        </thead>
        <tbody style="font-size:0.82rem">
          <tr><td>Dispositivo c&oacute;mputo</td>
              <td><code style="color:#fbbf24">{config.DEVICE}</code></td></tr>
          <tr><td>CUDA disponible</td>
              <td><code style="color:{'#10b981' if cuda_ok else '#ef4444'}">{cuda_ok}</code></td></tr>
          <tr><td>LLM (Ollama)</td>
              <td><code style="color:#c4b5fd">{config.LLM_MODEL}</code></td></tr>
          <tr><td>Visi&oacute;n (Ollama)</td>
              <td><code style="color:#c4b5fd">{config.VISION_MODEL}</code></td></tr>
          <tr><td>STT (Whisper)</td>
              <td><code style="color:#93c5fd">faster-whisper &middot; {config.WHISPER_MODEL_SIZE}</code></td></tr>
          <tr><td>Embeddings RAG</td>
              <td><code style="color:#93c5fd">OpenCLIP ViT-B-32</code></td></tr>
          <tr><td>Vector DB</td>
              <td><code style="color:#6ee7b7">ChromaDB &middot; cosine &middot; {config.CHROMA_COLLECTION}</code></td></tr>
          <tr style="background:rgba(124,58,237,0.05)"><td><strong style="color:#c4b5fd">GraphRAG activado</strong></td>
              <td><code style="color:{'#10b981' if graph_enabled else '#ef4444'}">{graph_enabled}</code></td></tr>
          <tr style="background:rgba(124,58,237,0.05)"><td>Grafo JSON</td>
              <td><code style="color:{'#6ee7b7' if graph_exists else '#ef4444'}">
                {'&#10003; Existe' if graph_exists else '&#10007; No generado &mdash; python scripts/build_graph.py'}
              </code></td></tr>
          <tr style="background:rgba(124,58,237,0.05)"><td>Graph hop depth</td>
              <td><code style="color:#a78bfa">{graph_hop} saltos</code></td></tr>
          <tr style="background:rgba(124,58,237,0.05)"><td>Graph top-K triples</td>
              <td><code style="color:#a78bfa">{graph_top_k} triples</code></td></tr>
          <tr style="background:rgba(124,58,237,0.05)"><td>Graph min weight</td>
              <td><code style="color:#a78bfa">{graph_min_w}</code></td></tr>
          <tr><td>TTS</td>
              <td><code style="color:#6ee7b7">Piper TTS / macOS say</code></td></tr>
          <tr><td>Puerto Gradio</td>
              <td><code style="color:#fbbf24">localhost:{config.GRADIO_PORT}</code></td></tr>
          <tr><td>Top-K RAG</td>
              <td><code style="color:#fbbf24">{config.RAG_TOP_K} fragmentos</code></td></tr>
          <tr><td>Umbral similitud</td>
              <td><code style="color:#fbbf24">{config.RAG_MIN_SIMILARITY}</code>
              <span style="font-size:11px;color:#94a3b8;margin-left:6px">(coseno base, antes de boost por palabras clave)</span></td></tr>
        </tbody>
      </table>

      <div class="info-card gold" style="margin-top:16px">
        <strong style="color:#e8edf5">Modelos Ollama requeridos</strong><br>
        <code style="color:#fbbf24">ollama pull {config.LLM_MODEL}</code> &nbsp;&rarr;&nbsp; Generaci&oacute;n de respuestas<br>
        <code style="color:#fbbf24">ollama pull {config.VISION_MODEL}</code> &nbsp;&rarr;&nbsp; An&aacute;lisis visual de formularios
      </div>
    </div>
    """)


def _build_guide_tab():
    import config

    gr.HTML(f"""
    <div style="padding: 20px 8px; animation: slideInUp 0.4s ease;">

      <h3 style="color:#f59e0b;font-size:0.85rem;font-weight:700;text-transform:uppercase;
                 letter-spacing:0.08em;margin:0 0 12px;border-bottom:1px solid #1e3a5f;
                 padding-bottom:8px">
        Modalidades de Consulta
      </h3>

      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));
                  gap:10px;margin-bottom:18px">

        <div class="stat-card" style="text-align:left;padding:14px">
          <div style="font-size:1.4rem;margin-bottom:8px" aria-hidden="true">&#128172;</div>
          <div style="font-weight:700;color:#e8edf5;font-size:0.85rem;margin-bottom:6px">Texto</div>
          <div style="color:#8b9ab5;font-size:0.78rem;line-height:1.5">
            Escribe tu consulta tributaria y presiona <em>Consultar Normativa</em>.
          </div>
        </div>

        <div class="stat-card" style="text-align:left;padding:14px">
          <div style="font-size:1.4rem;margin-bottom:8px" aria-hidden="true">&#127908;</div>
          <div style="font-weight:700;color:#e8edf5;font-size:0.85rem;margin-bottom:6px">Voz</div>
          <div style="color:#8b9ab5;font-size:0.78rem;line-height:1.5">
            Graba tu consulta con el micrófono. Whisper transcribe automáticamente en español.
          </div>
        </div>

        <div class="stat-card" style="text-align:left;padding:14px">
          <div style="font-size:1.4rem;margin-bottom:8px" aria-hidden="true">&#128247;</div>
          <div style="font-weight:700;color:#e8edf5;font-size:0.85rem;margin-bottom:6px">Imagen</div>
          <div style="color:#8b9ab5;font-size:0.78rem;line-height:1.5">
            Sube captura del portal SRI, formulario o comprobante. Moondream lo analiza.
          </div>
        </div>

        <div class="stat-card" style="text-align:left;padding:14px">
          <div style="font-size:1.4rem;margin-bottom:8px" aria-hidden="true">&#127909;</div>
          <div style="font-weight:700;color:#e8edf5;font-size:0.85rem;margin-bottom:6px">Video</div>
          <div style="color:#8b9ab5;font-size:0.78rem;line-height:1.5">
            Sube video de un proceso tributario. El sistema extrae y analiza frames clave.
          </div>
        </div>

      </div>

      <h3 style="color:#f59e0b;font-size:0.85rem;font-weight:700;text-transform:uppercase;
                 letter-spacing:0.08em;margin:18px 0 10px;border-bottom:1px solid #1e3a5f;
                 padding-bottom:8px">
        Ejemplos de Consultas
      </h3>

      <div class="query-chip-grid" role="list" aria-label="Ejemplos de consultas tributarias">
        <span class="query-chip" role="listitem">¿Cuál es la tarifa del IVA en Ecuador?</span>
        <span class="query-chip" role="listitem">¿Cómo obtengo el RUC como persona natural?</span>
        <span class="query-chip" role="listitem">¿Plazos para declarar el IVA mensual?</span>
        <span class="query-chip" role="listitem">¿Qué gastos son deducibles del IR?</span>
        <span class="query-chip" role="listitem">¿Qué es el RISE y quién puede acogerse?</span>
        <span class="query-chip" role="listitem">¿Qué comprobantes electrónicos existen?</span>
        <span class="query-chip" role="listitem">¿Tarifa del impuesto a la renta para sociedades?</span>
        <span class="query-chip" role="listitem">¿Sanciones por no declarar el IVA a tiempo?</span>
        <span class="query-chip" role="listitem">¿Cómo calcular el anticipo de impuesto a la renta?</span>
        <span class="query-chip" role="listitem">¿Qué es una nota de crédito electrónica?</span>
      </div>

      <h3 style="color:#f59e0b;font-size:0.85rem;font-weight:700;text-transform:uppercase;
                 letter-spacing:0.08em;margin:18px 0 10px;border-bottom:1px solid #1e3a5f;
                 padding-bottom:8px">
        Comportamiento del Asistente
      </h3>

      <div class="info-card green">
        <strong style="color:#6ee7b7">Cuando encuentra normativa:</strong>
        Responde citando la fuente exacta &mdash; nombre del documento, artículo y página si aplica.
        Las fuentes se muestran en el panel de fragmentos RAG.
      </div>
      <div class="info-card" style="margin-top:6px">
        <strong style="color:#93c5fd">Cuando no tiene contexto suficiente:</strong>
        Indica explícitamente que no encontró normativa y recomienda consultar sri.gob.ec.
      </div>
      <div class="info-card gold" style="margin-top:6px">
        <strong style="color:#fbbf24">Siempre:</strong>
        Las respuestas son orientativas. Para trámites oficiales, visita <strong>sri.gob.ec</strong>.
      </div>

      <h3 style="color:#f59e0b;font-size:0.85rem;font-weight:700;text-transform:uppercase;
                 letter-spacing:0.08em;margin:18px 0 10px;border-bottom:1px solid #1e3a5f;
                 padding-bottom:8px">
        Benchmark de Tesis — Tab "Benchmark RAGAS"
      </h3>

      <div class="info-card" style="margin-bottom:8px">
        Compara <strong>RAG vectorial</strong>, <strong>GraphRAG</strong> y
        modo <strong>híbrido</strong> — tiempo de respuesta y calidad — y
        permite comparar distintos modelos Ollama entre sí. Se corre por
        terminal, la tab solo <em>muestra</em> el último resultado (no lanza
        el proceso, que puede tardar horas en CPU):<br>
        <code style="color:#fbbf24">python scripts/run_benchmark.py --limit 5</code>
        &nbsp;&middot;&nbsp; prueba rápida (sin RAGAS: agregar <code>--no-ragas</code>)<br>
        <code style="color:#fbbf24">python scripts/run_benchmark.py</code>
        &nbsp;&middot;&nbsp; corrida completa sobre <code>preguntas.docx</code>
      </div>
      <table style="width:100%;border-collapse:collapse;font-size:0.82rem" role="table">
        <thead>
          <tr style="background:#141d2e">
            <th style="text-align:left;padding:8px 12px;color:#8b9ab5;font-size:0.72rem;
                       text-transform:uppercase;border-bottom:1px solid #1e3a5f" scope="col">Columna</th>
            <th style="text-align:left;padding:8px 12px;color:#8b9ab5;font-size:0.72rem;
                       text-transform:uppercase;border-bottom:1px solid #1e3a5f" scope="col">Qué mide</th>
          </tr>
        </thead>
        <tbody>
          <tr><td>Retrieval</td><td>Tiempo en <em>buscar</em> contexto (vectorial y/o grafo, según el modo)</td></tr>
          <tr><td>Generación</td><td>Tiempo en que el LLM redacta la respuesta con ese contexto ya encontrado</td></tr>
          <tr><td>Faithfulness</td><td>0&ndash;1 (RAGAS) &mdash; si la respuesta está basada en el contexto recuperado, o el LLM inventó algo no sustentado ahí</td></tr>
          <tr><td>Answer Relevancy</td><td>0&ndash;1 (RAGAS) &mdash; si la respuesta contesta la pregunta hecha, sin divagar</td></tr>
          <tr><td>% Doc. correcto</td><td>De las preguntas con retrieval vectorial, en cuántas se recuperó el documento fuente real esperado</td></tr>
        </tbody>
      </table>
      <p style="font-size:0.76rem;color:#64748b;margin-top:8px">
        Más tiempo no es mejor respuesta — un modo con más contexto (ej.
        híbrido) tarda más en generar simplemente porque el LLM tiene más
        texto que procesar antes de responder, no porque "razone más". La
        calidad se mide con Faithfulness / Answer Relevancy / % Doc. correcto,
        no con el tiempo.
      </p>

      <h3 style="color:#f59e0b;font-size:0.85rem;font-weight:700;text-transform:uppercase;
                 letter-spacing:0.08em;margin:18px 0 10px;border-bottom:1px solid #1e3a5f;
                 padding-bottom:8px">
        Solución de Problemas
      </h3>

      <table style="width:100%;border-collapse:collapse;font-size:0.82rem" role="table">
        <thead>
          <tr style="background:#141d2e">
            <th style="padding:8px 12px;color:#8b9ab5;font-size:0.72rem;text-transform:uppercase;
                       border-bottom:1px solid #1e3a5f" scope="col">Problema</th>
            <th style="padding:8px 12px;color:#8b9ab5;font-size:0.72rem;text-transform:uppercase;
                       border-bottom:1px solid #1e3a5f" scope="col">Solución</th>
          </tr>
        </thead>
        <tbody>
          <tr><td>Sin respuesta de Ollama</td>
              <td><code>ollama serve</code> en terminal</td></tr>
          <tr><td>Base vectorial vacía</td>
              <td>Copiar docs en <code>data/</code> &rarr; <code>python rag/build_db.py</code></td></tr>
          <tr><td>Sin voz en respuesta</td>
              <td><code>python audio/download_piper.py</code></td></tr>
          <tr><td>Modelos Ollama faltantes</td>
              <td><code>ollama pull {config.LLM_MODEL} &amp;&amp; ollama pull {config.VISION_MODEL}</code></td></tr>
          <tr><td>MinerU: timeout parseando PDF (&gt;{config.MINERU_TIMEOUT}s)</td>
              <td>Cae autom&aacute;ticamente a PyMuPDF (fallback). Para evitarlo, subir
                  <code>MINERU_TIMEOUT</code> en <code>config.py</code></td></tr>
          <tr><td>MinerU: binario no encontrado</td>
              <td><code>python3.12 -m venv venv_mineru &amp;&amp; venv_mineru/bin/pip install "mineru[pipeline]"</code></td></tr>
          <tr><td>Error de PyMuPDF (fallback PDF)</td>
              <td><code>pip install pymupdf</code></td></tr>
          <tr><td>Error de python-docx (DOCX)</td>
              <td><code>pip install python-docx</code></td></tr>
          <tr><td>Tab "Benchmark RAGAS" vacía</td>
              <td>Todavía no corriste el script &rarr;
                  <code>python scripts/run_benchmark.py --limit 5</code></td></tr>
        </tbody>
      </table>

    </div>
    """)
