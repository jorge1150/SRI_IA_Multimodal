"""
styles.py — CSS premium para el Asistente Tributario SRI IA Multimodal.
Diseño: dark professional · glassmorphism · Ecuador flag accents · RAG dashboard.
"""

CSS = """
/* ═══════════════════════════════════════════════════════════════════
   DESIGN TOKENS
═══════════════════════════════════════════════════════════════════ */
:root {
    --c-navy:       #0a0f1e;
    --c-navy2:      #111827;
    --c-navy3:      #1a2235;
    --c-blue:       #1d4ed8;
    --c-blue-l:     #3b82f6;
    --c-blue-xl:    #93c5fd;
    --c-gold:       #f59e0b;
    --c-gold-l:     #fbbf24;
    --c-gold-d:     #d97706;
    --c-green:      #10b981;
    --c-green-l:    #34d399;
    --c-green-d:    #059669;
    --c-red:        #ef4444;
    --c-purple:     #7c3aed;

    --ec-yellow:    #FFD100;
    --ec-blue:      #003DA5;
    --ec-red:       #CE1126;

    --bg:           #080d1a;
    --bg-card:      #0f1623;
    --bg-card2:     #141d2e;
    --bg-card3:     #1a2438;
    --bg-input:     #0b1220;

    --text:         #e8edf5;
    --text-sec:     #a8b8d0;
    --text-muted:   #8b9ab5;
    --text-dim:     #5a6a85;

    --border:       #1c2f4a;
    --border-l:     #2a4570;
    --border-gold:  rgba(245,158,11,0.35);
    --border-green: rgba(16,185,129,0.3);
    --border-blue:  rgba(29,78,216,0.3);

    --shadow:       0 4px 24px rgba(0,0,0,0.6);
    --shadow-lg:    0 8px 40px rgba(0,0,0,0.7);
    --glow-gold:    0 0 24px rgba(245,158,11,0.25), 0 0 48px rgba(245,158,11,0.10);
    --glow-blue:    0 0 24px rgba(29,78,216,0.35);
    --glow-green:   0 0 20px rgba(16,185,129,0.25);

    --radius-xs:    4px;
    --radius-sm:    6px;
    --radius:       12px;
    --radius-lg:    18px;
    --radius-xl:    24px;

    --sp-1: 4px;  --sp-2: 8px;  --sp-3: 12px;
    --sp-4: 16px; --sp-5: 20px; --sp-6: 24px; --sp-8: 32px;
}

/* ═══════════════════════════════════════════════════════════════════
   RESET & BASE
═══════════════════════════════════════════════════════════════════ */
*, *::before, *::after { box-sizing: border-box; }

body, .gradio-container, .gradio-container > div {
    background: var(--bg) !important;
    color: var(--text) !important;
    font-family: 'Inter', 'SF Pro Display', -apple-system,
                 BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif !important;
    font-size: 16px;
    line-height: 1.5;
}

@media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
        animation-duration: 0.01ms !important;
        transition-duration: 0.01ms !important;
    }
}

/* ═══════════════════════════════════════════════════════════════════
   KEYFRAMES
═══════════════════════════════════════════════════════════════════ */
@keyframes gradientShift {
    0%   { background-position: 0% 50%; }
    50%  { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
}
@keyframes pulseGold {
    0%, 100% { box-shadow: 0 0 8px rgba(245,158,11,0.3); }
    50%       { box-shadow: 0 0 24px rgba(245,158,11,0.6), 0 0 48px rgba(245,158,11,0.2); }
}
@keyframes slideInUp {
    from { opacity: 0; transform: translateY(14px); }
    to   { opacity: 1; transform: translateY(0); }
}
@keyframes fadeIn {
    from { opacity: 0; }
    to   { opacity: 1; }
}
@keyframes dotPulse {
    0%, 100% { transform: scale(1);   opacity: 1; }
    50%       { transform: scale(1.4); opacity: 0.6; }
}
@keyframes scanline {
    0%   { background-position: 0 0; }
    100% { background-position: 0 100%; }
}

/* ═══════════════════════════════════════════════════════════════════
   ECUADOR TOPBAR
═══════════════════════════════════════════════════════════════════ */
.sri-topbar {
    height: 5px;
    background: linear-gradient(90deg,
        var(--ec-yellow) 0%, var(--ec-yellow) 33%,
        var(--ec-blue)   33%, var(--ec-blue)   66%,
        var(--ec-red)    66%, var(--ec-red)    100%);
    width: 100%;
}

/* ═══════════════════════════════════════════════════════════════════
   HEADER
═══════════════════════════════════════════════════════════════════ */
.sri-header {
    text-align: center;
    padding: 28px 24px 18px;
    background:
        radial-gradient(ellipse at 20% 0%, rgba(29,78,216,0.12) 0%, transparent 55%),
        radial-gradient(ellipse at 80% 0%, rgba(245,158,11,0.08) 0%, transparent 55%),
        linear-gradient(180deg, #0d1628 0%, var(--bg) 100%);
    border-bottom: 1px solid var(--border);
    position: relative;
    overflow: hidden;
}

.sri-header::before {
    content: '';
    position: absolute;
    inset: 0;
    background: url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none'%3E%3Cg fill='%231d4ed8' fill-opacity='0.03'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E");
    pointer-events: none;
    opacity: 0.5;
}

.sri-header-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(29,78,216,0.15);
    border: 1px solid rgba(29,78,216,0.3);
    border-radius: 20px;
    padding: 4px 14px;
    font-size: 0.7rem;
    font-weight: 700;
    color: var(--c-blue-l);
    letter-spacing: 0.12em;
    text-transform: uppercase;
    margin-bottom: 12px;
}

.sri-header-badge .dot {
    width: 6px;
    height: 6px;
    background: var(--c-green);
    border-radius: 50%;
    animation: dotPulse 2s ease-in-out infinite;
    display: inline-block;
}

.sri-header h1 {
    font-size: 2.2rem;
    font-weight: 900;
    background: linear-gradient(135deg,
        #fbbf24 0%, #f59e0b 20%, #ffffff 45%,
        #93c5fd 65%, #3b82f6 85%, #fbbf24 100%);
    background-size: 200% 200%;
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    animation: gradientShift 6s ease infinite;
    margin: 0 0 6px;
    letter-spacing: -0.5px;
    line-height: 1.1;
}

.sri-header .subtitle {
    color: var(--text-muted);
    font-size: 0.84rem;
    font-weight: 400;
    margin: 4px 0;
}

.sri-header .tech-chips {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 6px;
    margin: 10px 0 8px;
}

.sri-header .chip {
    background: rgba(255,255,255,0.04);
    border: 1px solid var(--border);
    border-radius: 20px;
    padding: 3px 11px;
    font-size: 0.68rem;
    font-weight: 600;
    color: var(--text-muted);
    letter-spacing: 0.04em;
    white-space: nowrap;
}

.sri-header .institution {
    font-size: 0.7rem;
    font-weight: 600;
    color: var(--c-gold-d);
    letter-spacing: 0.1em;
    text-transform: uppercase;
    margin-top: 8px;
    opacity: 0.8;
}

/* ═══════════════════════════════════════════════════════════════════
   DISCLAIMER
═══════════════════════════════════════════════════════════════════ */
.disclaimer-bar {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    background: linear-gradient(135deg,
        rgba(245,158,11,0.06) 0%, rgba(245,158,11,0.03) 100%);
    border: 1px solid var(--border-gold);
    border-radius: var(--radius-sm);
    padding: 9px 18px;
    font-size: 0.74rem;
    color: #c08a0e;
    margin: 8px 0 12px;
    font-weight: 500;
}

/* ═══════════════════════════════════════════════════════════════════
   CARDS
═══════════════════════════════════════════════════════════════════ */
.input-card, .output-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: var(--sp-5);
    box-shadow: var(--shadow);
    animation: slideInUp 0.35s ease both;
}

.output-card {
    border-color: rgba(16,185,129,0.15);
    background: linear-gradient(180deg,
        rgba(16,185,129,0.02) 0%, var(--bg-card) 50%);
}

.section-title {
    display: flex;
    align-items: center;
    gap: 10px;
    margin: 0 0 var(--sp-4);
    padding-bottom: 10px;
    border-bottom: 1px solid var(--border);
}

.section-title .icon-wrap {
    width: 30px;
    height: 30px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.9rem;
    flex-shrink: 0;
}

.section-title.gold .icon-wrap  { background: rgba(245,158,11,0.15); }
.section-title.green .icon-wrap { background: rgba(16,185,129,0.15); }
.section-title.blue .icon-wrap  { background: rgba(29,78,216,0.15);  }

.section-title span {
    font-size: 0.82rem;
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
}

.section-title.gold span  { color: var(--c-gold);   }
.section-title.green span { color: var(--c-green);  }
.section-title.blue span  { color: var(--c-blue-l); }

/* ═══════════════════════════════════════════════════════════════════
   TABS
═══════════════════════════════════════════════════════════════════ */
.tabs > .tab-nav {
    background: var(--bg-card) !important;
    border-bottom: 1px solid var(--border) !important;
    padding: 0 8px !important;
    gap: 2px !important;
}

.tabs > .tab-nav button {
    color: var(--text-dim) !important;
    font-weight: 500 !important;
    font-size: 0.82rem !important;
    padding: 10px 16px !important;
    border-radius: var(--radius-sm) var(--radius-sm) 0 0 !important;
    transition: color 0.2s ease, background 0.2s ease !important;
    border: none !important;
    margin-bottom: -1px !important;
}

.tabs > .tab-nav button:hover {
    color: var(--text) !important;
    background: rgba(255,255,255,0.04) !important;
}

.tabs > .tab-nav button.selected {
    color: var(--c-gold) !important;
    background: var(--bg) !important;
    border-bottom: 2px solid var(--c-gold) !important;
    font-weight: 700 !important;
}

/* ═══════════════════════════════════════════════════════════════════
   LABELS
═══════════════════════════════════════════════════════════════════ */
label span, .label-wrap span {
    color: var(--text-dim) !important;
    font-size: 0.72rem !important;
    font-weight: 700 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.08em !important;
}

/* ═══════════════════════════════════════════════════════════════════
   INPUTS
═══════════════════════════════════════════════════════════════════ */
textarea, input[type="text"] {
    background: var(--bg-input) !important;
    color: var(--text) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius-sm) !important;
    font-family: 'Inter', system-ui, sans-serif !important;
    font-size: 0.88rem !important;
    transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
    min-height: 44px;
}

textarea:focus, input[type="text"]:focus {
    border-color: rgba(245,158,11,0.5) !important;
    box-shadow: 0 0 0 3px rgba(245,158,11,0.08),
                inset 0 1px 3px rgba(0,0,0,0.3) !important;
    outline: none !important;
}

button:focus-visible, textarea:focus-visible, input:focus-visible,
a:focus-visible {
    outline: 2px solid var(--c-gold) !important;
    outline-offset: 2px !important;
}

.consulta-box textarea {
    font-size: 0.92rem !important;
    line-height: 1.65 !important;
    padding: 12px !important;
    min-height: 108px !important;
}

/* ═══════════════════════════════════════════════════════════════════
   STT OUTPUT
═══════════════════════════════════════════════════════════════════ */
.stt-box textarea {
    background: rgba(29,78,216,0.06) !important;
    border: 1px solid rgba(59,130,246,0.2) !important;
    color: #93c5fd !important;
    font-size: 0.85rem !important;
    font-style: italic !important;
    line-height: 1.6 !important;
}

/* ═══════════════════════════════════════════════════════════════════
   RESPONSE BOX — clean, readable (no terminal style)
═══════════════════════════════════════════════════════════════════ */
.response-box textarea {
    background: rgba(16,185,129,0.04) !important;
    color: #d1fae5 !important;
    border: 1px solid rgba(16,185,129,0.18) !important;
    font-family: 'Inter', system-ui, sans-serif !important;
    font-size: 0.9rem !important;
    line-height: 1.75 !important;
    padding: 14px !important;
}

/* ═══════════════════════════════════════════════════════════════════
   RAG FRAGMENTS PANEL
═══════════════════════════════════════════════════════════════════ */
.rag-panel {
    background: var(--bg-card2);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    overflow: hidden;
    margin-top: 10px;
    animation: fadeIn 0.3s ease both;
}

.rag-panel-title {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 14px;
    background: rgba(29,78,216,0.08);
    border-bottom: 1px solid var(--border);
    font-size: 0.72rem;
    font-weight: 700;
    color: var(--c-blue-xl);
    text-transform: uppercase;
    letter-spacing: 0.08em;
}

.rag-panel-title svg {
    flex-shrink: 0;
    opacity: 0.8;
}

.rag-empty {
    padding: 18px 14px;
    font-size: 0.8rem;
    color: var(--text-dim);
    text-align: center;
    font-style: italic;
}

.rag-fragment {
    padding: 11px 14px;
    border-bottom: 1px solid rgba(28,47,74,0.6);
    transition: background 0.15s ease;
}

.rag-fragment:last-child { border-bottom: none; }

.rag-fragment:hover { background: rgba(255,255,255,0.02); }

.rag-fragment-top {
    display: flex;
    align-items: flex-start;
    gap: 10px;
}

.rag-fragment-num {
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    font-size: 0.7rem;
    font-weight: 700;
    color: var(--c-gold-d);
    background: rgba(245,158,11,0.1);
    border: 1px solid rgba(245,158,11,0.2);
    border-radius: var(--radius-xs);
    padding: 2px 7px;
    white-space: nowrap;
    flex-shrink: 0;
    margin-top: 1px;
}

.rag-fragment-info {
    flex: 1;
    min-width: 0;
}

.rag-fragment-doc {
    font-size: 0.83rem;
    font-weight: 600;
    color: var(--text);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    line-height: 1.3;
}

.rag-fragment-badges {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    margin-top: 4px;
}

.rag-tipo {
    font-size: 0.62rem;
    font-weight: 700;
    color: var(--c-blue-xl);
    background: rgba(29,78,216,0.12);
    border: 1px solid rgba(59,130,246,0.22);
    border-radius: 3px;
    padding: 1px 6px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

.rag-ano {
    font-size: 0.62rem;
    font-weight: 600;
    color: var(--text-dim);
    background: rgba(255,255,255,0.04);
    border: 1px solid var(--border);
    border-radius: 3px;
    padding: 1px 6px;
}

.rag-sim-wrap {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 5px;
    flex-shrink: 0;
    min-width: 52px;
}

.rag-sim-value {
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    font-size: 0.76rem;
    font-weight: 700;
    line-height: 1;
}

.rag-sim-bar {
    width: 48px;
    height: 4px;
    background: rgba(255,255,255,0.06);
    border-radius: 2px;
    overflow: hidden;
}

.rag-sim-fill {
    height: 100%;
    border-radius: 2px;
}

.rag-fragment-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 5px;
    margin-top: 7px;
    padding-left: 44px;
}

.rag-meta-item {
    font-size: 0.7rem;
    color: var(--text-muted);
    background: rgba(255,255,255,0.03);
    border: 1px solid var(--border);
    border-radius: 3px;
    padding: 1px 7px;
    white-space: nowrap;
}

/* ═══════════════════════════════════════════════════════════════════
   LOGS / PIPELINE
═══════════════════════════════════════════════════════════════════ */
.logs-wrap {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: var(--sp-4);
    margin-top: 8px;
}

.logs-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 10px;
}

.logs-title {
    font-size: 0.75rem;
    font-weight: 700;
    color: var(--c-gold);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    display: flex;
    align-items: center;
    gap: 8px;
}

.logs-pipeline {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    margin-bottom: 8px;
    font-size: 0.64rem;
    font-family: monospace;
}

.pipeline-step {
    background: rgba(255,255,255,0.03);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 3px 9px;
    color: var(--text-dim);
    white-space: nowrap;
    transition: all 0.2s ease;
}

.pipeline-step.active {
    background: rgba(245,158,11,0.12);
    border-color: rgba(245,158,11,0.4);
    color: var(--c-gold);
    box-shadow: 0 0 8px rgba(245,158,11,0.15);
}

.pipeline-step.done {
    background: rgba(16,185,129,0.07);
    border-color: rgba(16,185,129,0.22);
    color: var(--c-green);
}

.arrow { color: var(--text-dim); padding: 0 1px; }

.logs-console textarea {
    background: #040810 !important;
    color: #f0a500 !important;
    font-family: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace !important;
    font-size: 0.72rem !important;
    line-height: 1.7 !important;
    border: 1px solid rgba(240,165,0,0.1) !important;
    border-radius: 6px !important;
    padding: 12px !important;
    background-image: repeating-linear-gradient(
        transparent 0px, transparent 27px,
        rgba(240,165,0,0.02) 27px, rgba(240,165,0,0.02) 28px
    ) !important;
    box-shadow: inset 0 0 40px rgba(0,0,0,0.7) !important;
}

/* ═══════════════════════════════════════════════════════════════════
   BUTTONS
═══════════════════════════════════════════════════════════════════ */
.btn-consultar {
    position: relative;
    background: linear-gradient(135deg,
        #1a3a8f 0%, #1d4ed8 40%, #d97706 100%) !important;
    background-size: 200% 200% !important;
    color: #fff !important;
    font-size: 0.92rem !important;
    font-weight: 800 !important;
    letter-spacing: 0.06em !important;
    text-transform: uppercase !important;
    border: none !important;
    border-radius: var(--radius) !important;
    padding: 14px 28px !important;
    width: 100% !important;
    cursor: pointer !important;
    touch-action: manipulation !important;
    transition: transform 0.2s ease, box-shadow 0.2s ease !important;
    box-shadow: 0 4px 20px rgba(29,78,216,0.4), 0 2px 8px rgba(0,0,0,0.5) !important;
    animation: pulseGold 3s ease-in-out infinite !important;
    overflow: hidden !important;
    min-height: 48px !important;
}

.btn-consultar::after {
    content: '';
    position: absolute;
    top: -50%; left: -60%;
    width: 30%; height: 200%;
    background: linear-gradient(105deg,
        transparent 20%, rgba(255,255,255,0.14) 50%, transparent 80%);
    transform: skewX(-20deg);
    transition: left 0.5s ease;
}

.btn-consultar:hover::after { left: 140%; }

.btn-consultar:hover {
    transform: translateY(-2px) scale(1.01) !important;
    box-shadow: 0 8px 30px rgba(29,78,216,0.5),
                0 0 0 1px rgba(245,158,11,0.4) !important;
    animation: none !important;
}

.btn-consultar:active {
    transform: translateY(0) scale(0.98) !important;
    transition-duration: 0.1s !important;
}

.btn-screenshot {
    background: var(--bg-card2) !important;
    color: var(--text-muted) !important;
    border: 1px solid var(--border-l) !important;
    border-radius: var(--radius-sm) !important;
    font-size: 0.78rem !important;
    font-weight: 600 !important;
    padding: 8px 14px !important;
    width: 100% !important;
    touch-action: manipulation !important;
    transition: all 0.2s ease !important;
    letter-spacing: 0.03em !important;
    min-height: 44px !important;
}

.btn-screenshot:hover {
    border-color: rgba(245,158,11,0.4) !important;
    color: var(--c-gold) !important;
    background: rgba(245,158,11,0.06) !important;
}

.btn-clear {
    background: transparent !important;
    color: var(--text-dim) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius-sm) !important;
    font-size: 0.78rem !important;
    font-weight: 500 !important;
    touch-action: manipulation !important;
    transition: all 0.2s ease !important;
    min-height: 44px !important;
}

.btn-clear:hover {
    border-color: var(--c-red) !important;
    color: var(--c-red) !important;
    background: rgba(239,68,68,0.06) !important;
}

/* ═══════════════════════════════════════════════════════════════════
   AUDIO / IMAGE / VIDEO
═══════════════════════════════════════════════════════════════════ */
audio {
    width: 100% !important;
    border-radius: var(--radius-sm) !important;
    background: var(--bg-input) !important;
    filter: invert(0.85) hue-rotate(200deg) brightness(0.8) !important;
}

.image-container {
    border: 2px dashed var(--border-l) !important;
    border-radius: var(--radius) !important;
    overflow: hidden !important;
    transition: border-color 0.2s ease !important;
    background: var(--bg-input) !important;
}

.image-container:hover { border-color: rgba(245,158,11,0.4) !important; }

.video-container {
    border: 1px dashed var(--border) !important;
    border-radius: var(--radius-sm) !important;
    overflow: hidden !important;
    background: var(--bg-input) !important;
}

/* ═══════════════════════════════════════════════════════════════════
   KNOWLEDGE / SYSTEM / GUIDE TABS
═══════════════════════════════════════════════════════════════════ */
.stat-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 12px;
    margin: 16px 0;
}

.stat-card {
    background: var(--bg-card2);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 16px;
    text-align: center;
    transition: border-color 0.2s ease, transform 0.2s ease;
}

.stat-card:hover {
    border-color: var(--border-gold);
    transform: translateY(-2px);
}

.stat-card .stat-value {
    font-size: 2rem;
    font-weight: 900;
    color: var(--c-gold);
    line-height: 1;
    margin-bottom: 4px;
}

.stat-card .stat-label {
    font-size: 0.72rem;
    font-weight: 600;
    color: var(--text-dim);
    text-transform: uppercase;
    letter-spacing: 0.06em;
}

.info-card {
    background: var(--bg-card2);
    border: 1px solid var(--border);
    border-left: 3px solid var(--c-blue);
    border-radius: var(--radius-sm);
    padding: 12px 16px;
    margin: 8px 0;
    font-size: 0.84rem;
    color: var(--text-muted);
    line-height: 1.65;
}

.info-card.gold  { border-left-color: var(--c-gold);  }
.info-card.green { border-left-color: var(--c-green); }
.info-card.red   { border-left-color: var(--c-red);   }

.query-chip-grid {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin: 12px 0;
}

.query-chip {
    background: var(--bg-card2);
    border: 1px solid var(--border);
    border-radius: 20px;
    padding: 6px 14px;
    font-size: 0.78rem;
    color: var(--text-muted);
    cursor: default;
    transition: all 0.2s ease;
}

.query-chip:hover {
    border-color: rgba(245,158,11,0.4);
    color: var(--c-gold-l);
    background: rgba(245,158,11,0.05);
}

.pipeline-flow {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 4px;
    padding: 16px;
    background: var(--bg-card2);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    margin: 12px 0;
    font-size: 0.78rem;
}

.pipeline-node {
    background: var(--bg-card);
    border: 1px solid var(--border-l);
    border-radius: 8px;
    padding: 6px 12px;
    font-weight: 600;
    color: var(--text);
    white-space: nowrap;
    font-size: 0.74rem;
}

.pipeline-node.entry  { border-color: rgba(29,78,216,0.5);  color: #93c5fd; }
.pipeline-node.rag    { border-color: rgba(245,158,11,0.5); color: var(--c-gold); }
.pipeline-node.graph  { border-color: rgba(124,58,237,0.5); color: #c4b5fd;
                        background: rgba(124,58,237,0.07); }
.pipeline-node.hybrid { border-color: rgba(16,185,129,0.4); color: #6ee7b7;
                        background: rgba(16,185,129,0.07);
                        font-weight: 700; }
.pipeline-node.llm    { border-color: rgba(124,58,237,0.5); color: #c4b5fd; }
.pipeline-node.output { border-color: rgba(16,185,129,0.5); color: #6ee7b7; }

.pipeline-arrow { color: var(--text-dim); font-size: 1rem; }

/* Pipeline steps en trazabilidad de consulta */
.pipeline-step-hybrid {
    background: rgba(16,185,129,0.08) !important;
    border-color: rgba(16,185,129,0.3) !important;
    color: #6ee7b7 !important;
}
.pipeline-step-graph {
    background: rgba(124,58,237,0.08) !important;
    border-color: rgba(124,58,237,0.3) !important;
    color: #c4b5fd !important;
}

/* Header chips especiales */
.sri-header .chip.chip-hybrid {
    background: rgba(16,185,129,0.1) !important;
    border-color: rgba(16,185,129,0.3) !important;
    color: #6ee7b7 !important;
    font-weight: 700 !important;
}
.sri-header .chip.chip-graph {
    background: rgba(124,58,237,0.1) !important;
    border-color: rgba(124,58,237,0.3) !important;
    color: #c4b5fd !important;
}

/* ═══════════════════════════════════════════════════════════════════
   PROSE
═══════════════════════════════════════════════════════════════════ */
.prose h2 {
    font-size: 1.1rem;
    font-weight: 700;
    color: var(--c-gold);
    border-bottom: 1px solid var(--border);
    padding-bottom: 8px;
    margin: 20px 0 10px;
}

.prose h3 {
    font-size: 0.95rem;
    font-weight: 600;
    color: var(--c-blue-l);
    margin: 16px 0 6px;
}

.prose table { width: 100%; border-collapse: collapse; font-size: 0.82rem; }

.prose th {
    background: var(--bg-card2);
    color: var(--text-muted);
    font-weight: 700;
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    padding: 8px 12px;
    border-bottom: 1px solid var(--border-l);
}

.prose td {
    padding: 7px 12px;
    border-bottom: 1px solid var(--border);
    color: var(--text);
}

.prose tr:last-child td { border-bottom: none; }
.prose tr:hover td { background: rgba(255,255,255,0.02); }

.prose code {
    background: var(--bg-input);
    border: 1px solid var(--border);
    color: var(--c-gold-l);
    padding: 1px 6px;
    border-radius: 4px;
    font-family: monospace;
    font-size: 0.82em;
}

.prose pre {
    background: var(--bg-input);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    padding: 14px;
    overflow-x: auto;
    font-size: 0.8rem;
    color: #86efac;
}

/* ═══════════════════════════════════════════════════════════════════
   SCROLLBARS
═══════════════════════════════════════════════════════════════════ */
::-webkit-scrollbar       { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: var(--bg); }
::-webkit-scrollbar-thumb { background: var(--border-l); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: rgba(245,158,11,0.5); }

/* ═══════════════════════════════════════════════════════════════════
   DIVIDER / FOOTER
═══════════════════════════════════════════════════════════════════ */
.divider {
    height: 1px;
    background: linear-gradient(90deg,
        transparent 0%, var(--border-l) 20%,
        var(--border-gold) 50%, var(--border-l) 80%, transparent 100%);
    margin: 16px 0;
    border: none;
}

.sri-footer {
    text-align: center;
    padding: 12px;
    font-size: 0.68rem;
    color: var(--text-dim);
    border-top: 1px solid var(--border);
    margin-top: 8px;
}

/* ═══════════════════════════════════════════════════════════════════
   CHAT INTERFACE
═══════════════════════════════════════════════════════════════════ */

/* Chatbot container */
.chat-window {
    border: 1px solid var(--border) !important;
    border-radius: var(--radius-lg) !important;
    background: var(--bg-card) !important;
    box-shadow: var(--shadow) !important;
}

/* User message bubbles */
.chat-window .message.user > div,
.chat-window [data-testid="user"] > div {
    background: linear-gradient(135deg,
        rgba(29,78,216,0.22) 0%, rgba(29,78,216,0.12) 100%) !important;
    border: 1px solid rgba(59,130,246,0.28) !important;
    color: #dbeafe !important;
    border-radius: var(--radius) var(--radius) var(--radius-xs) var(--radius) !important;
}

/* Bot / assistant message bubbles */
.chat-window .message.bot > div,
.chat-window [data-testid="bot"] > div,
.chat-window .message.assistant > div {
    background: linear-gradient(135deg,
        rgba(16,185,129,0.1) 0%, rgba(16,185,129,0.04) 100%) !important;
    border: 1px solid rgba(16,185,129,0.22) !important;
    color: #d1fae5 !important;
    border-radius: var(--radius) var(--radius) var(--radius) var(--radius-xs) !important;
    font-size: 0.9rem !important;
    line-height: 1.75 !important;
}

/* Placeholder text inside empty chatbot */
.chat-window .placeholder {
    color: var(--text-dim) !important;
    font-size: 0.85rem !important;
    font-style: italic !important;
}

/* Attach accordion styling */
.attach-accordion > div:first-child {
    background: var(--bg-card2) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
    font-size: 0.8rem !important;
    color: var(--text-muted) !important;
    font-weight: 600 !important;
    letter-spacing: 0.03em !important;
    padding: 10px 14px !important;
    cursor: pointer !important;
    transition: background 0.2s ease, color 0.2s ease !important;
}

.attach-accordion > div:first-child:hover {
    background: rgba(245,158,11,0.06) !important;
    color: var(--c-gold-l) !important;
    border-color: var(--border-gold) !important;
}

/* Chat text input (composer) */
.chat-input textarea {
    background: var(--bg-input) !important;
    border: 1px solid var(--border-l) !important;
    border-radius: var(--radius) !important;
    font-size: 0.9rem !important;
    line-height: 1.65 !important;
    padding: 12px 16px !important;
    resize: none !important;
    transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
    color: var(--text) !important;
    min-height: 56px !important;
}

.chat-input textarea:focus {
    border-color: rgba(245,158,11,0.5) !important;
    box-shadow: 0 0 0 3px rgba(245,158,11,0.08),
                inset 0 1px 3px rgba(0,0,0,0.25) !important;
    outline: none !important;
}

/* Send button */
.btn-send {
    background: linear-gradient(135deg,
        #1a3a8f 0%, #1d4ed8 45%, #d97706 100%) !important;
    color: #fff !important;
    font-weight: 800 !important;
    letter-spacing: 0.06em !important;
    text-transform: uppercase !important;
    border: none !important;
    border-radius: var(--radius) !important;
    width: 100% !important;
    min-height: 52px !important;
    font-size: 0.88rem !important;
    transition: transform 0.15s ease, box-shadow 0.15s ease !important;
    box-shadow: 0 4px 18px rgba(29,78,216,0.4),
                0 2px 8px rgba(0,0,0,0.5) !important;
    cursor: pointer !important;
    touch-action: manipulation !important;
}

.btn-send:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 7px 28px rgba(29,78,216,0.5),
                0 0 0 1px rgba(245,158,11,0.35) !important;
}

.btn-send:active {
    transform: translateY(0) scale(0.97) !important;
    transition-duration: 0.08s !important;
}

/* Composer row */
.composer-row {
    margin-top: 8px !important;
    gap: 10px !important;
    align-items: flex-end !important;
}

/* Chat sidebar */
.chat-sidebar {
    padding-left: 12px !important;
}

/* Attachment image inside chat */
.attach-img {
    border: 2px dashed var(--border-l) !important;
    border-radius: var(--radius) !important;
    overflow: hidden !important;
    background: var(--bg-input) !important;
    transition: border-color 0.2s ease !important;
}

.attach-img:hover {
    border-color: rgba(245,158,11,0.4) !important;
}

/* Logs accordion */
.logs-accordion {
    margin-top: 10px !important;
}

.logs-accordion > div:first-child {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
    font-size: 0.78rem !important;
    color: var(--c-gold) !important;
    font-weight: 700 !important;
    letter-spacing: 0.06em !important;
    text-transform: uppercase !important;
    padding: 10px 14px !important;
    cursor: pointer !important;
}

/* ═══════════════════════════════════════════════════════════════════
   RESPONSIVE
═══════════════════════════════════════════════════════════════════ */
@media (max-width: 768px) {
    .sri-header h1     { font-size: 1.6rem; }
    .sri-header        { padding: 20px 16px 14px; }
    .input-card, .output-card { padding: var(--sp-3) var(--sp-4); }
    .stat-grid         { grid-template-columns: repeat(2, 1fr); }
    .query-chip        { font-size: 0.74rem; padding: 5px 11px; }
    .btn-consultar     { font-size: 0.85rem !important; padding: 12px 20px !important; }
    .pipeline-flow     { font-size: 0.68rem; gap: 3px; padding: 10px 12px; }
    .rag-fragment-meta { padding-left: 0; }
}

@media (max-width: 480px) {
    .sri-header h1      { font-size: 1.3rem; letter-spacing: 0; }
    .sri-header .chip   { font-size: 0.62rem; padding: 2px 8px; }
    .stat-grid          { grid-template-columns: 1fr 1fr; }
    .stat-card .stat-value { font-size: 1.5rem; }
    .rag-fragment-meta  { padding-left: 0; }
}
"""
