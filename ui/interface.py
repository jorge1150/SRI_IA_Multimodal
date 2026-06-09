"""
interface.py — Interfaz Gradio premium del Asistente Tributario SRI IA Multimodal.
Diseño: dark professional · glassmorphism · Ecuador flag accents.
"""

import gradio as gr
from vision.capture import capture_screenshot
from ui.styles import CSS
from config import GRADIO_PORT, GRADIO_SERVER, GRADIO_TITLE

GRADIO_THEME = gr.themes.Base(
    primary_hue=gr.themes.colors.blue,
    secondary_hue=gr.themes.colors.amber,
    neutral_hue=gr.themes.colors.slate,
)


def build_interface(coordinator) -> gr.Blocks:

    def consultar(image, audio, text_input, video):
        for stt, resp, audio_path, logs in coordinator.process(
            image_input=image,
            audio_input=audio,
            text_input=text_input,
            video_input=video,
        ):
            yield stt, resp, audio_path, logs

    def take_screenshot():
        return capture_screenshot()

    def clear_all():
        return None, None, "", None, "", "", None, ""

    with gr.Blocks(title=GRADIO_TITLE) as demo:
        gr.HTML(f"<style>{CSS}</style>")

        # ── Franja tricolor Ecuador + Header ─────────────────────────────
        gr.HTML("""
        <div class="sri-topbar"></div>
        <div class="sri-header">
            <div class="sri-header-badge">
                <span class="dot"></span>
                Sistema Activo · 100% Local
            </div>
            <h1>⚖️ SRI IA Multimodal</h1>
            <p class="subtitle">
                Asistente Virtual de Normativa Tributaria &nbsp;·&nbsp;
                Servicio de Rentas Internas del Ecuador
            </p>
            <div class="tech-chips">
                <span class="chip">RAG Multimodal</span>
                <span class="chip">Ollama + TinyLlama</span>
                <span class="chip">ChromaDB</span>
                <span class="chip">Whisper STT</span>
                <span class="chip">Piper TTS</span>
                <span class="chip">Moondream Vision</span>
                <span class="chip">OpenCLIP Embeddings</span>
            </div>
            <p class="institution">
                Maestría en Inteligencia Artificial Aplicada &nbsp;·&nbsp; UIsrael
            </p>
        </div>
        """)

        # ── Disclaimer ────────────────────────────────────────────────────
        gr.HTML("""
        <div class="disclaimer-bar">
            ⚠️&nbsp; Las respuestas son <strong>orientativas e informativas</strong>.
            No constituyen asesoría legal ni tributaria definitiva.
            Verifique siempre en <strong>sri.gob.ec</strong> o consulte con un profesional tributario.
        </div>
        """)

        with gr.Tabs():

            # ═══════════════════════════════════════════════════════════════
            # TAB 1 — Consulta Tributaria
            # ═══════════════════════════════════════════════════════════════
            with gr.Tab("⚖️  Consulta Tributaria"):

                with gr.Row(equal_height=False):

                    # ── Panel izquierdo: ENTRADAS ────────────────────────
                    with gr.Column(scale=1, min_width=330):
                        gr.HTML("""
                        <div class="input-card">
                        <div class="section-title gold">
                            <div class="icon-wrap">📥</div>
                            <span>Modalidad de Consulta</span>
                        </div>
                        """)

                        img_input = gr.Image(
                            label="📷  Imagen — Formulario · Portal SRI · Comprobante",
                            sources=["webcam", "upload"],
                            type="pil",
                            elem_classes=["image-container"],
                            height=180,
                        )

                        btn_screenshot = gr.Button(
                            "🖥️  Capturar Pantalla del Portal SRI",
                            variant="secondary",
                            elem_classes=["btn-screenshot"],
                        )

                        audio_input = gr.Audio(
                            label="🎤  Voz — Consulta por Micrófono o Archivo",
                            sources=["microphone", "upload"],
                            type="filepath",
                        )

                        text_input = gr.Textbox(
                            label="💬  Consulta Tributaria",
                            placeholder=(
                                "Ej: ¿Cuál es la tarifa del IVA en Ecuador?\n"
                                "¿Cómo obtengo el RUC como persona natural?\n"
                                "¿Cuáles son los plazos para declarar el IVA?\n"
                                "¿Qué gastos son deducibles del impuesto a la renta?"
                            ),
                            lines=4,
                            elem_classes=["consulta-box"],
                        )

                        video_input = gr.Video(
                            label="🎬  Video — Tutorial SRI o Proceso Tributario",
                            sources=["upload"],
                            elem_classes=["video-container"],
                        )

                        gr.HTML("</div>")  # cierre input-card

                        with gr.Row():
                            btn_consultar = gr.Button(
                                "🔍  Consultar Normativa Tributaria",
                                variant="primary",
                                elem_classes=["btn-consultar"],
                            )
                            btn_clear = gr.Button(
                                "✕ Limpiar",
                                variant="secondary",
                                elem_classes=["btn-clear"],
                                size="sm",
                            )

                    # ── Panel derecho: RESPUESTA ─────────────────────────
                    with gr.Column(scale=1, min_width=400):
                        gr.HTML("""
                        <div class="output-card">
                        <div class="section-title green">
                            <div class="icon-wrap">📤</div>
                            <span>Respuesta con Fuentes Normativas</span>
                        </div>
                        """)

                        stt_output = gr.Textbox(
                            label="🎙️  Consulta Transcrita (Whisper STT)",
                            lines=2,
                            interactive=False,
                            placeholder="La transcripción de tu consulta por voz aparecerá aquí...",
                            elem_classes=["stt-box"],
                        )

                        response_output = gr.Textbox(
                            label="⚖️  Respuesta Tributaria · Fuentes Citadas",
                            lines=13,
                            interactive=False,
                            placeholder=(
                                "La respuesta basada en normativa SRI aparecerá aquí...\n\n"
                                "Incluirá:\n"
                                "  • Fuente: nombre del documento\n"
                                "  • Tipo: Ley / Resolución / Guía\n"
                                "  • Artículo o sección específica\n"
                                "  • Número de página (para PDFs)\n\n"
                                "Si no hay normativa disponible, el sistema lo indicará\n"
                                "y recomendará consultar sri.gob.ec"
                            ),
                            elem_classes=["response-box"],
                        )

                        audio_output = gr.Audio(
                            label="🔊  Respuesta en Voz (Piper TTS · Español)",
                            type="filepath",
                            autoplay=True,
                            interactive=False,
                        )

                        gr.HTML("</div>")  # cierre output-card

                # ── Trazabilidad RAG ─────────────────────────────────────
                gr.HTML("""
                <div class="divider"></div>
                <div class="logs-wrap">
                    <div class="logs-header">
                        <div class="logs-title">
                            📋&nbsp; Trazabilidad del Proceso RAG
                        </div>
                    </div>
                    <div class="logs-pipeline">
                        <span class="pipeline-step">🚀 INICIO</span>
                        <span class="arrow">→</span>
                        <span class="pipeline-step">🎤 STT</span>
                        <span class="arrow">→</span>
                        <span class="pipeline-step">👁️ VISION</span>
                        <span class="arrow">→</span>
                        <span class="pipeline-step">📋 RAG</span>
                        <span class="arrow">→</span>
                        <span class="pipeline-step">⚖️ NORMATIVA</span>
                        <span class="arrow">→</span>
                        <span class="pipeline-step">🤖 GENERANDO</span>
                        <span class="arrow">→</span>
                        <span class="pipeline-step">🔊 TTS</span>
                        <span class="arrow">→</span>
                        <span class="pipeline-step">✅ FIN</span>
                    </div>
                """)

                logs_output = gr.Textbox(
                    label="",
                    lines=9,
                    interactive=False,
                    placeholder=(
                        "[HH:MM:SS] 🚀 [INICIO] Asistente SRI IA Multimodal iniciado.\n"
                        "[HH:MM:SS] 🎤 [STT] Recibiendo consulta por voz — transcribiendo audio...\n"
                        "[HH:MM:SS] 👁️ [VISION] Analizando imagen o captura con Moondream...\n"
                        "[HH:MM:SS] 📋 [RAG] Buscando normativa relacionada...\n"
                        "[HH:MM:SS] ⚖️ [NORMATIVA] Recuperando artículos relevantes...\n"
                        "[HH:MM:SS] 🤖 [GENERANDO] Generando respuesta tributaria con TinyLlama...\n"
                        "[HH:MM:SS] 🔊 [TTS] Generando audio con Piper TTS...\n"
                        "[HH:MM:SS] ✅ [FIN] Consulta tributaria procesada correctamente."
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
            # TAB 3 — Sistema
            # ═══════════════════════════════════════════════════════════════
            with gr.Tab("⚙️  Estado del Sistema"):
                _build_system_tab()

            # ═══════════════════════════════════════════════════════════════
            # TAB 4 — Guía de Uso
            # ═══════════════════════════════════════════════════════════════
            with gr.Tab("📖  Guía de Uso"):
                _build_guide_tab()

        # ── Footer ────────────────────────────────────────────────────────
        gr.HTML("""
        <div class="sri-footer">
            SRI IA Multimodal &nbsp;·&nbsp; Sistema 100% Local · Sin conexión a internet en tiempo de ejecución &nbsp;·&nbsp;
            Ollama · ChromaDB · Whisper · Piper TTS · Moondream &nbsp;·&nbsp;
            Maestría IA Aplicada · UIsrael
        </div>
        """)

        # ── Eventos ───────────────────────────────────────────────────────
        btn_consultar.click(
            fn=consultar,
            inputs=[img_input, audio_input, text_input, video_input],
            outputs=[stt_output, response_output, audio_output, logs_output],
            show_progress="full",
        )
        btn_screenshot.click(fn=take_screenshot, inputs=[], outputs=[img_input])
        btn_clear.click(
            fn=clear_all,
            inputs=[],
            outputs=[img_input, audio_input, text_input, video_input,
                     stt_output, response_output, audio_output, logs_output],
        )

    return demo


# ── Tabs auxiliares ───────────────────────────────────────────────────────────

def _build_knowledge_tab():
    import config, chromadb, glob, os

    n_chunks = 0
    try:
        client = chromadb.PersistentClient(path=config.CHROMA_DB_PATH)
        col = client.get_collection(config.CHROMA_COLLECTION)
        n_chunks = col.count()
    except Exception:
        pass

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
        f"<tr><td>{tipo}</td><td style='text-align:center;color:#fbbf24;font-weight:700'>{count}</td>"
        f"<td style='text-align:center;color:#6ee7b7'>"
        f"{'✅' if count > 0 else '<span style=\"color:#64748b\">—</span>'}</td></tr>"
        for tipo, count in doc_counts.items()
    )

    gr.HTML(f"""
    <div style="padding: 20px 8px; animation: slideInUp 0.4s ease;">

      <!-- Stats row -->
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
          <div class="stat-label">Estado Base Vectorial</div>
        </div>
        <div class="stat-card">
          <div class="stat-value" style="font-size:1.2rem">4</div>
          <div class="stat-label">Categorías Normativas</div>
        </div>
      </div>

      <!-- Documentos por categoría -->
      <h3 style="color:#f59e0b;font-size:0.85rem;font-weight:700;text-transform:uppercase;
                 letter-spacing:0.08em;margin:20px 0 10px;border-bottom:1px solid #1e3a5f;padding-bottom:8px">
        Documentos por Categoría
      </h3>
      <table style="width:100%;border-collapse:collapse;font-size:0.83rem">
        <thead>
          <tr style="background:#141d2e">
            <th style="text-align:left;padding:9px 12px;color:#8b9ab5;font-size:0.72rem;
                       text-transform:uppercase;letter-spacing:0.06em;border-bottom:1px solid #1e3a5f">
              Tipo de Normativa
            </th>
            <th style="text-align:center;padding:9px 12px;color:#8b9ab5;font-size:0.72rem;
                       text-transform:uppercase;letter-spacing:0.06em;border-bottom:1px solid #1e3a5f">
              Documentos
            </th>
            <th style="text-align:center;padding:9px 12px;color:#8b9ab5;font-size:0.72rem;
                       text-transform:uppercase;letter-spacing:0.06em;border-bottom:1px solid #1e3a5f">
              Estado
            </th>
          </tr>
        </thead>
        <tbody>{rows_html}</tbody>
      </table>

      <!-- Instrucciones -->
      <h3 style="color:#f59e0b;font-size:0.85rem;font-weight:700;text-transform:uppercase;
                 letter-spacing:0.08em;margin:20px 0 10px;border-bottom:1px solid #1e3a5f;padding-bottom:8px">
        Cómo Cargar Documentos SRI
      </h3>

      <div class="info-card">
        <strong style="color:#e8edf5">Paso 1 — Copiar documentos</strong><br>
        Coloca los archivos PDF, TXT, DOCX o MD del SRI en las carpetas correspondientes:
        <ul style="margin:6px 0 0 16px;line-height:2">
          <li><code>data/normativas_sri/</code> → LORTI, Código Tributario, Reglamentos</li>
          <li><code>data/resoluciones/</code> → Resoluciones NAC-DGERCGC del SRI</li>
          <li><code>data/guias_tributarias/</code> → Guías de declaración, RUC, comprobantes</li>
          <li><code>data/formularios/</code> → Instructivos formularios 104, 101, etc.</li>
        </ul>
      </div>

      <div class="info-card gold" style="margin-top:8px">
        <strong style="color:#e8edf5">Paso 2 — Reconstruir la base vectorial</strong><br>
        <code style="color:#fbbf24">python rag/build_db.py</code> &nbsp;·&nbsp;
        Actualización incremental (no borra lo existente)<br>
        <code style="color:#fbbf24">python rag/build_db.py --reset</code> &nbsp;·&nbsp;
        Reconstruir desde cero
      </div>

      <!-- Formatos -->
      <h3 style="color:#f59e0b;font-size:0.85rem;font-weight:700;text-transform:uppercase;
                 letter-spacing:0.08em;margin:20px 0 10px;border-bottom:1px solid #1e3a5f;padding-bottom:8px">
        Formatos Soportados
      </h3>
      <table style="width:100%;border-collapse:collapse;font-size:0.82rem">
        <thead>
          <tr style="background:#141d2e">
            <th style="padding:8px 12px;color:#8b9ab5;font-size:0.72rem;text-transform:uppercase;
                       border-bottom:1px solid #1e3a5f">Formato</th>
            <th style="padding:8px 12px;color:#8b9ab5;font-size:0.72rem;text-transform:uppercase;
                       border-bottom:1px solid #1e3a5f">Soporte</th>
            <th style="padding:8px 12px;color:#8b9ab5;font-size:0.72rem;text-transform:uppercase;
                       border-bottom:1px solid #1e3a5f">Metadatos Extra</th>
          </tr>
        </thead>
        <tbody>
          <tr><td><code>.pdf</code></td><td>✅ Total</td><td>Página, artículo auto-detectado</td></tr>
          <tr><td><code>.txt</code></td><td>✅ Total</td><td>Artículo auto-detectado</td></tr>
          <tr><td><code>.docx</code></td><td>✅ Total</td><td>Artículo auto-detectado</td></tr>
          <tr><td><code>.md</code></td><td>✅ Total</td><td>Artículo auto-detectado</td></tr>
        </tbody>
      </table>
    </div>
    """)


def _build_system_tab():
    import config, torch

    cuda_ok = torch.cuda.is_available()

    gr.HTML(f"""
    <div style="padding: 20px 8px; animation: slideInUp 0.4s ease;">

      <!-- Pipeline visual -->
      <h3 style="color:#f59e0b;font-size:0.85rem;font-weight:700;text-transform:uppercase;
                 letter-spacing:0.08em;margin:0 0 12px;border-bottom:1px solid #1e3a5f;padding-bottom:8px">
        Pipeline RAG Multimodal
      </h3>

      <div class="pipeline-flow">
        <span class="pipeline-node entry">🎤 Audio</span>
        <span class="pipeline-arrow">→</span>
        <span class="pipeline-node entry">📷 Imagen</span>
        <span class="pipeline-arrow">→</span>
        <span class="pipeline-node entry">💬 Texto</span>
        <span class="pipeline-arrow">⟹</span>
        <span class="pipeline-node rag">Whisper STT</span>
        <span class="pipeline-arrow">+</span>
        <span class="pipeline-node rag">Moondream</span>
        <span class="pipeline-arrow">⟹</span>
        <span class="pipeline-node rag">OpenCLIP Vector</span>
        <span class="pipeline-arrow">⟹</span>
        <span class="pipeline-node rag">ChromaDB</span>
        <span class="pipeline-arrow">⟹</span>
        <span class="pipeline-node rag">Fragmentos + Metadatos</span>
        <span class="pipeline-arrow">⟹</span>
        <span class="pipeline-node llm">TinyLlama</span>
        <span class="pipeline-arrow">⟹</span>
        <span class="pipeline-node output">Respuesta + Citas</span>
        <span class="pipeline-arrow">⟹</span>
        <span class="pipeline-node output">🔊 Piper TTS</span>
      </div>

      <!-- Estado de componentes -->
      <h3 style="color:#f59e0b;font-size:0.85rem;font-weight:700;text-transform:uppercase;
                 letter-spacing:0.08em;margin:20px 0 10px;border-bottom:1px solid #1e3a5f;padding-bottom:8px">
        Estado de Componentes
      </h3>
      <table style="width:100%;border-collapse:collapse;font-size:0.83rem">
        <thead>
          <tr style="background:#141d2e">
            <th style="padding:8px 12px;color:#8b9ab5;font-size:0.72rem;text-transform:uppercase;
                       border-bottom:1px solid #1e3a5f">Componente</th>
            <th style="padding:8px 12px;color:#8b9ab5;font-size:0.72rem;text-transform:uppercase;
                       border-bottom:1px solid #1e3a5f">Valor</th>
          </tr>
        </thead>
        <tbody style="font-size:0.82rem">
          <tr><td>🖥️ Dispositivo cómputo</td>
              <td><code style="color:#fbbf24">{config.DEVICE}</code></td></tr>
          <tr><td>⚡ CUDA disponible</td>
              <td><code style="color:{'#10b981' if cuda_ok else '#ef4444'}">{cuda_ok}</code></td></tr>
          <tr><td>🤖 LLM (Ollama)</td>
              <td><code style="color:#c4b5fd">{config.LLM_MODEL}</code></td></tr>
          <tr><td>👁️ Visión (Ollama)</td>
              <td><code style="color:#c4b5fd">{config.VISION_MODEL}</code></td></tr>
          <tr><td>🎤 STT (Whisper)</td>
              <td><code style="color:#93c5fd">faster-whisper · {config.WHISPER_MODEL_SIZE}</code></td></tr>
          <tr><td>🔢 Embeddings</td>
              <td><code style="color:#93c5fd">OpenCLIP ViT-B-32</code></td></tr>
          <tr><td>🗄️ Vector DB</td>
              <td><code style="color:#6ee7b7">ChromaDB · cosine · {config.CHROMA_COLLECTION}</code></td></tr>
          <tr><td>🔊 TTS</td>
              <td><code style="color:#6ee7b7">Piper TTS / macOS say</code></td></tr>
          <tr><td>🌐 Puerto Gradio</td>
              <td><code style="color:#fbbf24">localhost:{config.GRADIO_PORT}</code></td></tr>
          <tr><td>📊 Top-K RAG</td>
              <td><code style="color:#fbbf24">{config.RAG_TOP_K} fragmentos</code></td></tr>
          <tr><td>📐 Umbral similitud</td>
              <td><code style="color:#fbbf24">{config.RAG_MIN_SIMILARITY}</code></td></tr>
        </tbody>
      </table>

      <!-- Modelos Ollama -->
      <div class="info-card gold" style="margin-top:16px">
        <strong style="color:#e8edf5">Modelos Ollama requeridos</strong><br>
        <code style="color:#fbbf24">ollama pull tinyllama</code> &nbsp;→&nbsp; Generación de respuestas<br>
        <code style="color:#fbbf24">ollama pull moondream</code> &nbsp;→&nbsp; Análisis visual de formularios
      </div>
    </div>
    """)


def _build_guide_tab():
    gr.HTML("""
    <div style="padding: 20px 8px; animation: slideInUp 0.4s ease;">

      <!-- Modos de consulta -->
      <h3 style="color:#f59e0b;font-size:0.85rem;font-weight:700;text-transform:uppercase;
                 letter-spacing:0.08em;margin:0 0 12px;border-bottom:1px solid #1e3a5f;padding-bottom:8px">
        Modalidades de Consulta
      </h3>

      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px;margin-bottom:18px">

        <div class="stat-card" style="text-align:left;padding:14px">
          <div style="font-size:1.5rem;margin-bottom:8px">💬</div>
          <div style="font-weight:700;color:#e8edf5;font-size:0.85rem;margin-bottom:6px">Texto</div>
          <div style="color:#8b9ab5;font-size:0.78rem;line-height:1.5">
            Escribe tu consulta tributaria en el campo de texto y presiona <em>Consultar Normativa</em>.
          </div>
        </div>

        <div class="stat-card" style="text-align:left;padding:14px">
          <div style="font-size:1.5rem;margin-bottom:8px">🎤</div>
          <div style="font-weight:700;color:#e8edf5;font-size:0.85rem;margin-bottom:6px">Voz</div>
          <div style="color:#8b9ab5;font-size:0.78rem;line-height:1.5">
            Graba tu consulta con el micrófono. Whisper transcribe automáticamente en español.
          </div>
        </div>

        <div class="stat-card" style="text-align:left;padding:14px">
          <div style="font-size:1.5rem;margin-bottom:8px">📷</div>
          <div style="font-weight:700;color:#e8edf5;font-size:0.85rem;margin-bottom:6px">Imagen</div>
          <div style="color:#8b9ab5;font-size:0.78rem;line-height:1.5">
            Sube captura del portal SRI, formulario o comprobante. Moondream lo analiza visualmente.
          </div>
        </div>

        <div class="stat-card" style="text-align:left;padding:14px">
          <div style="font-size:1.5rem;margin-bottom:8px">🎬</div>
          <div style="font-weight:700;color:#e8edf5;font-size:0.85rem;margin-bottom:6px">Video</div>
          <div style="color:#8b9ab5;font-size:0.78rem;line-height:1.5">
            Sube un video de un proceso tributario. El sistema extrae y analiza frames clave.
          </div>
        </div>

      </div>

      <!-- Ejemplos de consulta -->
      <h3 style="color:#f59e0b;font-size:0.85rem;font-weight:700;text-transform:uppercase;
                 letter-spacing:0.08em;margin:18px 0 10px;border-bottom:1px solid #1e3a5f;padding-bottom:8px">
        Ejemplos de Consultas
      </h3>

      <div class="query-chip-grid">
        <span class="query-chip">¿Cuál es la tarifa del IVA en Ecuador?</span>
        <span class="query-chip">¿Cómo obtengo el RUC como persona natural?</span>
        <span class="query-chip">¿Plazos para declarar el IVA mensual?</span>
        <span class="query-chip">¿Qué gastos son deducibles del IR?</span>
        <span class="query-chip">¿Qué es el RISE y quién puede acogerse?</span>
        <span class="query-chip">¿Qué comprobantes electrónicos existen?</span>
        <span class="query-chip">¿Tarifa del impuesto a la renta para sociedades?</span>
        <span class="query-chip">¿Sanciones por no declarar el IVA a tiempo?</span>
        <span class="query-chip">¿Cómo calcular el anticipo de impuesto a la renta?</span>
        <span class="query-chip">¿Qué es una nota de crédito electrónica?</span>
      </div>

      <!-- Comportamiento del sistema -->
      <h3 style="color:#f59e0b;font-size:0.85rem;font-weight:700;text-transform:uppercase;
                 letter-spacing:0.08em;margin:18px 0 10px;border-bottom:1px solid #1e3a5f;padding-bottom:8px">
        Comportamiento del Asistente
      </h3>

      <div class="info-card green">
        ✅ <strong style="color:#6ee7b7">Cuando encuentra normativa:</strong>
        Responde citando la fuente exacta — nombre del documento, artículo, y página si aplica.
      </div>
      <div class="info-card" style="margin-top:6px">
        ⚖️ <strong style="color:#93c5fd">Cuando no tiene suficiente contexto:</strong>
        El sistema indica explícitamente que no encontró normativa y recomienda consultar sri.gob.ec.
      </div>
      <div class="info-card gold" style="margin-top:6px">
        ⚠️ <strong style="color:#fbbf24">Siempre:</strong>
        Las respuestas son orientativas. Para trámites oficiales, visita <strong>sri.gob.ec</strong>.
      </div>

      <!-- Solución de problemas -->
      <h3 style="color:#f59e0b;font-size:0.85rem;font-weight:700;text-transform:uppercase;
                 letter-spacing:0.08em;margin:18px 0 10px;border-bottom:1px solid #1e3a5f;padding-bottom:8px">
        Solución de Problemas
      </h3>

      <table style="width:100%;border-collapse:collapse;font-size:0.82rem">
        <thead>
          <tr style="background:#141d2e">
            <th style="padding:8px 12px;color:#8b9ab5;font-size:0.72rem;text-transform:uppercase;
                       border-bottom:1px solid #1e3a5f">Problema</th>
            <th style="padding:8px 12px;color:#8b9ab5;font-size:0.72rem;text-transform:uppercase;
                       border-bottom:1px solid #1e3a5f">Solución</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Sin respuesta de Ollama</td>
            <td><code>ollama serve</code> en terminal</td>
          </tr>
          <tr>
            <td>Base vectorial vacía</td>
            <td>Copiar docs en <code>data/</code> → <code>python rag/build_db.py</code></td>
          </tr>
          <tr>
            <td>Sin voz en respuesta</td>
            <td><code>python audio/download_piper.py</code></td>
          </tr>
          <tr>
            <td>Modelos Ollama faltantes</td>
            <td><code>ollama pull tinyllama &amp;&amp; ollama pull moondream</code></td>
          </tr>
          <tr>
            <td>Error de PyMuPDF (PDF)</td>
            <td><code>pip install pymupdf</code></td>
          </tr>
          <tr>
            <td>Error de python-docx (DOCX)</td>
            <td><code>pip install python-docx</code></td>
          </tr>
        </tbody>
      </table>

    </div>
    """)
