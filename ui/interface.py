"""
interface.py — Interfaz Gradio del Asistente Tributario SRI IA Multimodal.
Diseño: dark professional · glassmorphism · Ecuador flag accents · RAG dashboard.
"""

import re
import gradio as gr
from vision.capture import capture_screenshot
from ui.styles import CSS
from config import GRADIO_PORT, GRADIO_SERVER, GRADIO_TITLE

GRADIO_THEME = gr.themes.Base(
    primary_hue=gr.themes.colors.blue,
    secondary_hue=gr.themes.colors.amber,
    neutral_hue=gr.themes.colors.slate,
)

_SEPARATOR = "─" * 37  # ─────────────────────────────────────


# ── RAG parsing helpers ───────────────────────────────────────────────────────

def _parse_source_line(line: str):
    """Parse one source line: [N] Tipo: Doc (year) — Art. X — Pág. N  [sim: 0.XX]"""
    m_num = re.match(r'\s*\[(\d+)\]\s*', line)
    if not m_num:
        return None
    m_sim = re.search(r'\[sim:\s*([\d.]+)\]', line)
    if not m_sim:
        return None

    num = m_num.group(1)
    sim = float(m_sim.group(1))
    content = line[m_num.end():m_sim.start()].strip()

    tipo = ''
    m_tipo = re.match(r'^([\w\s/À-ž]+):\s*', content)
    if m_tipo:
        tipo = m_tipo.group(1).strip()
        content = content[m_tipo.end():]

    parts = [p.strip() for p in content.split('—')]  # em dash —

    doc = año = articulo = pagina = ''

    if parts:
        m_year = re.search(r'\((\d{4})\)$', parts[0])
        if m_year:
            año = m_year.group(1)
            doc = parts[0][:m_year.start()].strip()
        else:
            doc = parts[0].strip()

    for part in parts[1:]:
        m_pag = re.match(r'Pág\.\s*(\d+)', part.strip())  # Pág.
        if m_pag:
            pagina = m_pag.group(1)
        elif part.strip():
            articulo = part.strip()

    return {'num': num, 'tipo': tipo, 'doc': doc,
            'año': año, 'articulo': articulo, 'pagina': pagina, 'sim': sim}


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


def _parse_response(text: str):
    """Split full LLM output into (answer_body, rag_html)."""
    if not text:
        return '', _rag_panel_html([])

    if _SEPARATOR in text:
        idx = text.index(_SEPARATOR)
        main = text[:idx].strip()
        sources_block = text[idx:]
        fragments = [
            f for f in (_parse_source_line(l) for l in sources_block.splitlines())
            if f is not None
        ]
    else:
        main = text.strip()
        fragments = []

    return main, _rag_panel_html(fragments)


# ── Main interface ────────────────────────────────────────────────────────────

def build_interface(coordinator) -> gr.Blocks:

    def consultar(image, audio, text_input, video):
        for stt, resp, audio_path, logs in coordinator.process(
            image_input=image,
            audio_input=audio,
            text_input=text_input,
            video_input=video,
        ):
            main_text, rag_html = _parse_response(resp)
            yield stt, main_text, rag_html, audio_path, logs

    def take_screenshot():
        return capture_screenshot()

    def clear_all():
        return None, None, "", None, "", "", _rag_panel_html([]), None, ""

    with gr.Blocks(title=GRADIO_TITLE) as demo:
        gr.HTML(f"<style>{CSS}</style>")

        # ── Ecuador topbar + header ───────────────────────────────────────
        gr.HTML("""
        <div class="sri-topbar" role="presentation"></div>
        <header class="sri-header">
            <div class="sri-header-badge" role="status">
                <span class="dot" aria-hidden="true"></span>
                Sistema Activo &middot; 100% Local
            </div>
            <h1>⚖️ SRI IA Multimodal</h1>
            <p class="subtitle">
                Asistente Virtual de Normativa Tributaria &nbsp;&middot;&nbsp;
                Servicio de Rentas Internas del Ecuador
            </p>
            <div class="tech-chips" role="list" aria-label="Tecnologías del sistema">
                <span class="chip chip-hybrid" role="listitem">RAG + GraphRAG Híbrido</span>
                <span class="chip" role="listitem">Ollama &middot; TinyLlama</span>
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
            # TAB 1 — Consulta Tributaria
            # ═══════════════════════════════════════════════════════════════
            with gr.Tab("⚖️  Consulta Tributaria"):

                with gr.Row(equal_height=False):

                    # ── Panel izquierdo: ENTRADAS ─────────────────────────
                    with gr.Column(scale=1, min_width=300):
                        gr.HTML("""
                        <div class="input-card">
                        <div class="section-title gold">
                            <div class="icon-wrap" aria-hidden="true">&#128229;</div>
                            <span>Modalidad de Consulta</span>
                        </div>
                        """)

                        img_input = gr.Image(
                            label="Imagen — Formulario, Portal SRI o Comprobante",
                            sources=["webcam", "upload"],
                            type="pil",
                            elem_classes=["image-container"],
                            height=170,
                        )

                        btn_screenshot = gr.Button(
                            "Capturar Pantalla del Portal SRI",
                            variant="secondary",
                            elem_classes=["btn-screenshot"],
                        )

                        audio_input = gr.Audio(
                            label="Voz — Consulta por Micrófono o Archivo",
                            sources=["microphone", "upload"],
                            type="filepath",
                        )

                        text_input = gr.Textbox(
                            label="Consulta Tributaria",
                            placeholder=(
                                "Ej: ¿Cuál es la tarifa del IVA en Ecuador?\n"
                                "¿Cómo obtengo el RUC como persona natural?\n"
                                "¿Cuáles son los plazos para declarar el IVA?"
                            ),
                            lines=4,
                            elem_classes=["consulta-box"],
                        )

                        video_input = gr.Video(
                            label="Video — Tutorial SRI o Proceso Tributario",
                            sources=["upload"],
                            elem_classes=["video-container"],
                        )

                        gr.HTML("</div>")  # cierre input-card

                        with gr.Row():
                            btn_consultar = gr.Button(
                                "Consultar Normativa Tributaria",
                                variant="primary",
                                elem_classes=["btn-consultar"],
                            )
                            btn_clear = gr.Button(
                                "Limpiar",
                                variant="secondary",
                                elem_classes=["btn-clear"],
                                size="sm",
                            )

                    # ── Panel derecho: RESPUESTA ──────────────────────────
                    with gr.Column(scale=1, min_width=380):
                        gr.HTML("""
                        <div class="output-card">
                        <div class="section-title green">
                            <div class="icon-wrap" aria-hidden="true">&#128196;</div>
                            <span>Respuesta con Fuentes Normativas</span>
                        </div>
                        """)

                        stt_output = gr.Textbox(
                            label="Consulta Transcrita (Whisper STT)",
                            lines=2,
                            interactive=False,
                            placeholder="La transcripción de tu consulta por voz aparecerá aquí...",
                            elem_classes=["stt-box"],
                        )

                        response_output = gr.Textbox(
                            label="Respuesta Tributaria",
                            lines=10,
                            interactive=False,
                            placeholder=(
                                "La respuesta basada en normativa SRI aparecerá aquí...\n\n"
                                "El sistema buscará en la base normativa y responderá\n"
                                "citando los artículos relevantes encontrados.\n\n"
                                "Las fuentes consultadas se mostrarán en el panel inferior."
                            ),
                            elem_classes=["response-box"],
                        )

                        # RAG fragments panel
                        rag_output = gr.HTML(
                            value=_rag_panel_html([]),
                        )

                        audio_output = gr.Audio(
                            label="Respuesta en Voz (Piper TTS · Español)",
                            type="filepath",
                            autoplay=True,
                            interactive=False,
                        )

                        gr.HTML("</div>")  # cierre output-card

                # ── Trazabilidad RAG ──────────────────────────────────────
                gr.HTML("""
                <div class="divider" role="separator"></div>
                <div class="logs-wrap" role="region" aria-label="Trazabilidad del proceso">
                    <div class="logs-header">
                        <div class="logs-title">
                            Trazabilidad &mdash; Pipeline RAG + GraphRAG H&iacute;brido
                        </div>
                    </div>
                    <div class="logs-pipeline" role="list" aria-label="Etapas del pipeline">
                        <span class="pipeline-step" role="listitem">INICIO</span>
                        <span class="arrow" aria-hidden="true">&#8594;</span>
                        <span class="pipeline-step" role="listitem">STT</span>
                        <span class="arrow" aria-hidden="true">&#8594;</span>
                        <span class="pipeline-step" role="listitem">VISION</span>
                        <span class="arrow" aria-hidden="true">&#8594;</span>
                        <span class="pipeline-step pipeline-step-hybrid" role="listitem">RAG Vector</span>
                        <span class="arrow" aria-hidden="true">&#8214;</span>
                        <span class="pipeline-step pipeline-step-graph" role="listitem">GRAPH</span>
                        <span class="arrow" aria-hidden="true">&#8594;</span>
                        <span class="pipeline-step pipeline-step-hybrid" role="listitem">HYBRID</span>
                        <span class="arrow" aria-hidden="true">&#8594;</span>
                        <span class="pipeline-step" role="listitem">GENERANDO</span>
                        <span class="arrow" aria-hidden="true">&#8594;</span>
                        <span class="pipeline-step" role="listitem">TTS</span>
                        <span class="arrow" aria-hidden="true">&#8594;</span>
                        <span class="pipeline-step" role="listitem">FIN</span>
                    </div>
                """)

                logs_output = gr.Textbox(
                    label="",
                    lines=8,
                    interactive=False,
                    placeholder=(
                        "[HH:MM:SS] [INICIO] Asistente SRI IA Multimodal iniciado.\n"
                        "[HH:MM:SS] [STT] Transcribiendo consulta de audio...\n"
                        "[HH:MM:SS] [VISION] Analizando imagen con Moondream...\n"
                        "[HH:MM:SS] [RAG] Buscando normativa: vector + grafo híbrido...\n"
                        "[HH:MM:SS] [RAG] ✓ N artículos relevantes [+grafo].\n"
                        "[HH:MM:SS] [GRAPH] ✓ Entidades detectadas: IVA, RUC... | N triples.\n"
                        "[HH:MM:SS] [GENERANDO] Generando respuesta con TinyLlama...\n"
                        "[HH:MM:SS] [TTS] Sintetizando audio con Piper TTS...\n"
                        "[HH:MM:SS] [FIN] Consulta tributaria procesada correctamente."
                    ),
                    elem_classes=["logs-console"],
                )

                gr.HTML("</div>")  # cierre logs-wrap

            # ═══════════════════════════════════════════════════════════════
            # TAB 2 — Base de Conocimiento
            # ═══════════════════════════════════════════════════════════════
            with gr.Tab("📚  Base de Conocimiento"):
                _build_knowledge_tab()

            # ═══════════════════════════════════════════════════════════════
            # TAB 3 — Estado del Sistema
            # ═══════════════════════════════════════════════════════════════
            with gr.Tab("⚙️  Estado del Sistema"):
                _build_system_tab()

            # ═══════════════════════════════════════════════════════════════
            # TAB 4 — Guía de Uso
            # ═══════════════════════════════════════════════════════════════
            with gr.Tab("📖  Guia de Uso"):
                _build_guide_tab()

        # ── Footer ────────────────────────────────────────────────────────
        gr.HTML("""
        <footer class="sri-footer">
            SRI IA Multimodal &nbsp;&middot;&nbsp;
            Sistema 100% Local &middot; Sin conexión a internet en tiempo de ejecución
            &nbsp;&middot;&nbsp; Ollama &middot; ChromaDB &middot; Whisper &middot;
            Piper TTS &middot; Moondream &nbsp;&middot;&nbsp; Maestría IA Aplicada &middot; UIsrael
        </footer>
        """)

        # ── Eventos ───────────────────────────────────────────────────────
        btn_consultar.click(
            fn=consultar,
            inputs=[img_input, audio_input, text_input, video_input],
            outputs=[stt_output, response_output, rag_output, audio_output, logs_output],
            show_progress="full",
        )
        btn_screenshot.click(fn=take_screenshot, inputs=[], outputs=[img_input])
        btn_clear.click(
            fn=clear_all,
            inputs=[],
            outputs=[img_input, audio_input, text_input, video_input,
                     stt_output, response_output, rag_output, audio_output, logs_output],
        )

    return demo


# ── Tabs auxiliares ───────────────────────────────────────────────────────────

def _build_knowledge_tab():
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
    try:
        gpath = getattr(config, 'GRAPH_DB_PATH', '')
        if gpath and os.path.exists(gpath):
            with open(gpath, encoding='utf-8') as f:
                gdata = json.load(f)
            meta = gdata.get('metadata', {})
            g_nodes = meta.get('n_nodes', 0)
            g_edges = meta.get('n_edges', 0)
            g_docs  = meta.get('n_documents', 0)
            # contar tipos de relación desde aristas
            for e in gdata.get('edges', []):
                for rel in e.get('relations', {}).keys():
                    g_rel_types[rel] = g_rel_types.get(rel, 0) + 1
    except Exception:
        pass

    graph_status_color = "#10b981" if g_nodes > 0 else ("#f59e0b" if g_enabled else "#ef4444")
    graph_status_text  = f"{g_nodes} nodos" if g_nodes > 0 else ("Sin grafo" if g_enabled else "Desactivado")

    doc_counts = {}
    for data_dir in config.ALL_DATA_DIRS:
        folder = os.path.basename(data_dir)
        tipo = config.TIPO_BY_FOLDER.get(folder, folder)
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

    gr.HTML(f"""
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
        Coloca los archivos PDF, TXT, DOCX o MD del SRI en las carpetas correspondientes:
        <ul style="margin:6px 0 0 16px;line-height:2">
          <li><code>data/normativas_sri/</code> &rarr; LORTI, Código Tributario, Reglamentos</li>
          <li><code>data/resoluciones/</code> &rarr; Resoluciones NAC-DGERCGC del SRI</li>
          <li><code>data/guias_tributarias/</code> &rarr; Guías de declaración, RUC, comprobantes</li>
          <li><code>data/formularios/</code> &rarr; Instructivos formularios 104, 101, etc.</li>
        </ul>
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


def _build_system_tab():
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

    gr.HTML(f"""
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
        <span class="pipeline-node llm" role="listitem">TinyLlama</span>
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
        <code style="color:#fbbf24">ollama pull tinyllama</code> &nbsp;&rarr;&nbsp; Generaci&oacute;n de respuestas<br>
        <code style="color:#fbbf24">ollama pull moondream</code> &nbsp;&rarr;&nbsp; An&aacute;lisis visual de formularios
      </div>
    </div>
    """)


def _build_guide_tab():
    gr.HTML("""
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
              <td><code>ollama pull tinyllama &amp;&amp; ollama pull moondream</code></td></tr>
          <tr><td>Error de PyMuPDF (PDF)</td>
              <td><code>pip install pymupdf</code></td></tr>
          <tr><td>Error de python-docx (DOCX)</td>
              <td><code>pip install python-docx</code></td></tr>
        </tbody>
      </table>

    </div>
    """)
