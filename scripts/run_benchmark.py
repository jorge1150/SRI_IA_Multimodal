"""
run_benchmark.py — Benchmark de tesis: RAG vs GraphRAG vs Híbrido, y
comparación entre modelos LLM (Ollama), validado con RAGAS local.

Uso:
    python scripts/run_benchmark.py
    python scripts/run_benchmark.py --models qwen2.5:3b-instruct-q4_K_M,tinyllama:latest
    python scripts/run_benchmark.py --modes vector_only,hybrid --limit 5

Mide, por cada combinación (modelo × modo × pregunta):
  - Tiempo de retrieval (HybridRetriever.retrieve, mode forzado)
  - Tiempo de generación (ResponseAgent.generate, modelo forzado)
  - faithfulness / answer_relevancy (RAGAS, juez local vía Ollama,
    embeddings sentence-transformers — ver scripts/ragas_local.py)
  - Si el retrieval trajo chunks del documento fuente esperado (según
    preguntas.docx), cuando el modo incluye recuperación vectorial.

Salida en outputs/benchmarks/:
  - benchmark_<timestamp>.csv   — una fila por pregunta×modo×modelo
  - benchmark_<timestamp>.html  — reporte visual
  - benchmark_<timestamp>_summary.json — agregados (leído por la UI)

Nota de costo: cada pregunta implica al menos 1 llamada de generación +
hasta 2 llamadas de juez RAGAS, todo en CPU local — una corrida completa
(42 preguntas × 3 modos × N modelos) puede tardar horas. Usar --limit para
pruebas rápidas.
"""

import argparse
import csv
import html
import json
import math
import os
import re
import sys
import time
import unicodedata
from datetime import datetime, timezone

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

DEFAULT_QUESTIONS_PATH = os.path.join(_ROOT, "preguntas.docx")
DEFAULT_OUT_DIR = os.path.join(_ROOT, "outputs", "benchmarks")
ALL_MODES = ["vector_only", "graph_only", "hybrid"]
SOURCES_SEPARATOR = "─" * 37  # ver agents/response_agent.py


def _normalize(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def _source_matched(expected_doc: str, vector_chunks: list) -> "bool | None":
    """None = no aplica (modo sin retrieval vectorial o sin doc esperado)."""
    if not vector_chunks or not expected_doc:
        return None
    expected_norm = _normalize(expected_doc)
    if not expected_norm:
        return None
    for c in vector_chunks:
        meta = c.get("metadata", {})
        for field in (meta.get("doc_name", ""), meta.get("source", "")):
            cand = _normalize(field)
            if cand and (expected_norm in cand or cand in expected_norm):
                return True
    return False


def _strip_sources_section(answer: str) -> str:
    return answer.split(SOURCES_SEPARATOR)[0].strip()


def _none_if_nan(value) -> "float | None":
    """RAGAS devuelve NaN (no excepción) cuando el juez local no logra
    producir una respuesta parseable para una fila — pasa seguido con un
    juez de 3B (ver ADR-0003, limitación aceptada). Normalizar a None acá
    para que CSV/JSON/promedios traten "el juez falló" igual que "no se
    evaluó" en vez de contaminar sum() silenciosamente con NaN."""
    if value is None:
        return None
    value = float(value)
    return None if math.isnan(value) else value


def _build_pipeline(graph_hop_depth=None, graph_top_k=None):
    """Reusa las mismas clases que agents/coordinator.py, sin STT/visión."""
    import config
    from agents.coordinator import _init_graph_retriever
    from agents.log_agent import LogAgent
    from agents.rag_agent import RAGAgent
    from agents.response_agent import ResponseAgent
    from services.hybrid_retriever import HybridRetriever

    log_agent = LogAgent()
    rag_agent = RAGAgent(log_agent)
    response_agent = ResponseAgent(log_agent)
    graph_retriever = _init_graph_retriever(log_agent)
    hybrid = HybridRetriever(rag_agent, log_agent, graph_retriever)
    return hybrid, response_agent, graph_retriever is not None


def _run_single(hybrid, response_agent, question: str, mode: str, model: str) -> dict:
    t0 = time.time()
    retrieval = hybrid.retrieve(question, mode=mode)
    retrieval_seconds = time.time() - t0

    t1 = time.time()
    raw_answer = response_agent.generate(
        query=question,
        rag_context=retrieval["vector_chunks"],
        graph_context=retrieval["graph_context"],
        model=model,
    )
    generation_seconds = time.time() - t1

    answer = _strip_sources_section(raw_answer)
    retrieved_texts = [c["text"] for c in retrieval["vector_chunks"]]
    if retrieval["graph_context"]:
        retrieved_texts.append(retrieval["graph_context"])

    return {
        "mode_result": retrieval["mode"],
        "retrieval_seconds": retrieval_seconds,
        "generation_seconds": generation_seconds,
        "answer": answer,
        "retrieved_texts": retrieved_texts,
        "vector_chunks": retrieval["vector_chunks"],
        "n_vector_chunks": len(retrieval["vector_chunks"]),
        "n_graph_triples": len(retrieval["graph_triples"]),
    }


def _run_ragas(rows: list, judge_model: str, embedding_model: str, ollama_url: str) -> None:
    """Corre RAGAS una sola vez sobre todas las filas y anota faithfulness/
    answer_relevancy in-place. Filas sin retrieved_texts o answer vacía se
    saltan (RAGAS no tiene nada que evaluar)."""
    from ragas import evaluate, EvaluationDataset
    from ragas.metrics import faithfulness, answer_relevancy
    from scripts.ragas_local import make_judge_llm, make_embeddings

    evaluable = [r for r in rows if r["answer"].strip() and r["retrieved_texts"]]
    for r in rows:
        r["faithfulness"] = None
        r["answer_relevancy"] = None

    if not evaluable:
        print("[BENCHMARK] Sin filas evaluables para RAGAS (respuestas o contexto vacíos).")
        return

    print(f"[BENCHMARK] Corriendo RAGAS sobre {len(evaluable)} fila(s) "
          f"(juez: {judge_model}, embeddings: {embedding_model})...", flush=True)

    dataset = EvaluationDataset.from_list([
        {
            "user_input": r["question"],
            "response": r["answer"],
            "retrieved_contexts": r["retrieved_texts"],
        }
        for r in evaluable
    ])

    llm = make_judge_llm(judge_model, ollama_url)
    embeddings = make_embeddings(embedding_model)
    result = evaluate(dataset=dataset, metrics=[faithfulness, answer_relevancy],
                       llm=llm, embeddings=embeddings)
    df = result.to_pandas()

    n_failed_faith = n_failed_rel = 0
    for r, (_, row) in zip(evaluable, df.iterrows()):
        faith_val = _none_if_nan(row.get("faithfulness"))
        rel_val = _none_if_nan(row.get("answer_relevancy"))
        r["faithfulness"] = faith_val
        r["answer_relevancy"] = rel_val
        n_failed_faith += faith_val is None
        n_failed_rel += rel_val is None

    if n_failed_faith or n_failed_rel:
        print(f"[BENCHMARK] Juez RAGAS no pudo evaluar {n_failed_faith}/{len(evaluable)} "
              f"(faithfulness) y {n_failed_rel}/{len(evaluable)} (answer_relevancy) — "
              f"NaN del juez local, se excluyen del promedio (no del CSV).", flush=True)


def _write_csv(rows: list, path: str) -> None:
    fields = [
        "category", "source_doc", "question", "model", "mode_requested", "mode_result",
        "retrieval_seconds", "generation_seconds", "total_seconds",
        "n_vector_chunks", "n_graph_triples", "source_matched",
        "faithfulness", "answer_relevancy", "answer",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def _aggregate(rows: list, key: str) -> dict:
    """Promedios de tiempo y RAGAS agrupados por 'mode_requested' o 'model'."""
    groups: dict = {}
    for r in rows:
        groups.setdefault(r[key], []).append(r)

    def _valid(x):
        return x is not None and not (isinstance(x, float) and math.isnan(x))

    out = {}
    for k, items in groups.items():
        n = len(items)
        faith = [i["faithfulness"] for i in items if _valid(i["faithfulness"])]
        rel = [i["answer_relevancy"] for i in items if _valid(i["answer_relevancy"])]
        matched = [i["source_matched"] for i in items if i["source_matched"] is not None]
        out[k] = {
            "n": n,
            "n_faithfulness_evaluated": len(faith),
            "n_answer_relevancy_evaluated": len(rel),
            "avg_retrieval_seconds": sum(i["retrieval_seconds"] for i in items) / n,
            "avg_generation_seconds": sum(i["generation_seconds"] for i in items) / n,
            "avg_total_seconds": sum(i["total_seconds"] for i in items) / n,
            "avg_faithfulness": (sum(faith) / len(faith)) if faith else None,
            "avg_answer_relevancy": (sum(rel) / len(rel)) if rel else None,
            "source_match_rate": (sum(matched) / len(matched)) if matched else None,
        }
    return out


def _write_summary_json(rows: list, path: str, meta: dict) -> None:
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "n_rows": len(rows),
        **meta,
        "by_mode": _aggregate(rows, "mode_requested"),
        "by_model": _aggregate(rows, "model"),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)


def _bar(value: float, max_value: float, color: str) -> str:
    pct = 0 if not max_value else max(2, min(100, round(100 * value / max_value)))
    return (f'<div style="background:#1e293b;border-radius:4px;overflow:hidden;height:14px;width:100%">'
            f'<div style="background:{color};height:100%;width:{pct}%"></div></div>')


def _fmt_ragas_html(v, n_evaluated: int, n_total: int) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)) or n_total == 0:
        return "—"
    base = "%.2f" % v
    if n_evaluated < n_total:
        return f"{base} ({n_evaluated}/{n_total})"
    return base


def _write_html(rows: list, by_mode: dict, by_model: dict, path: str, meta: dict) -> None:
    max_total = max((v["avg_total_seconds"] for v in by_mode.values()), default=1) or 1
    ragas_enabled = meta.get("ragas_enabled", True)

    mode_rows = "".join(
        f"<tr><td>{html.escape(mode)}</td>"
        f"<td>{v['n']}</td>"
        f"<td>{v['avg_retrieval_seconds']:.2f}s</td>"
        f"<td>{v['avg_generation_seconds']:.2f}s</td>"
        f"<td>{v['avg_total_seconds']:.2f}s<br>{_bar(v['avg_total_seconds'], max_total, '#3b82f6')}</td>"
        f"<td>{_fmt_ragas_html(v.get('avg_faithfulness'), v.get('n_faithfulness_evaluated', 0), v['n'])}</td>"
        f"<td>{_fmt_ragas_html(v.get('avg_answer_relevancy'), v.get('n_answer_relevancy_evaluated', 0), v['n'])}</td>"
        f"<td>{'%.0f%%' % (v['source_match_rate'] * 100) if v['source_match_rate'] is not None else '—'}</td>"
        f"</tr>"
        for mode, v in sorted(by_mode.items())
    )
    model_rows = "".join(
        f"<tr><td>{html.escape(model)}</td>"
        f"<td>{v['n']}</td>"
        f"<td>{v['avg_retrieval_seconds']:.2f}s</td>"
        f"<td>{v['avg_generation_seconds']:.2f}s</td>"
        f"<td>{v['avg_total_seconds']:.2f}s<br>{_bar(v['avg_total_seconds'], max_total, '#a78bfa')}</td>"
        f"<td>{_fmt_ragas_html(v.get('avg_faithfulness'), v.get('n_faithfulness_evaluated', 0), v['n'])}</td>"
        f"<td>{_fmt_ragas_html(v.get('avg_answer_relevancy'), v.get('n_answer_relevancy_evaluated', 0), v['n'])}</td>"
        f"</tr>"
        for model, v in sorted(by_model.items())
    )

    doc = f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<title>Benchmark SRI IA Multimodal — {meta.get('generated_at', '')}</title>
<style>
  body {{ background:#0b1220; color:#e2e8f0; font-family:system-ui,sans-serif; padding:24px; }}
  h1 {{ font-size:1.3rem; color:#f59e0b; }}
  h2 {{ font-size:1rem; color:#93c5fd; margin-top:28px; border-bottom:1px solid #1e3a5f; padding-bottom:6px; }}
  table {{ width:100%; border-collapse:collapse; font-size:0.85rem; margin-top:10px; }}
  th {{ text-align:left; padding:8px; color:#8b9ab5; text-transform:uppercase; font-size:0.72rem; border-bottom:1px solid #1e3a5f; }}
  td {{ padding:8px; border-bottom:1px solid #16233a; }}
  code {{ color:#fbbf24; }}
  .meta {{ color:#64748b; font-size:0.8rem; }}
</style></head>
<body>
  <h1>Benchmark RAG vs GraphRAG vs Híbrido — SRI IA Multimodal</h1>
  <p class="meta">Generado: {meta.get('generated_at', '')} &middot; Preguntas: {meta.get('n_questions', '?')}
     &middot; Modos: {', '.join(meta.get('modes', []))} &middot; Modelos: {', '.join(meta.get('models', []))}
     &middot; Filas totales: {len(rows)}</p>

  <h2>Comparación por modo de recuperación</h2>
  <table>
    <thead><tr><th>Modo</th><th>N</th><th>Retrieval</th><th>Generación</th><th>Total</th>
    <th>Faithfulness</th><th>Answer Relevancy</th><th>% Doc. correcto</th></tr></thead>
    <tbody>{mode_rows}</tbody>
  </table>

  <h2>Comparación por modelo LLM</h2>
  <table>
    <thead><tr><th>Modelo</th><th>N</th><th>Retrieval</th><th>Generación</th><th>Total</th>
    <th>Faithfulness</th><th>Answer Relevancy</th></tr></thead>
    <tbody>{model_rows}</tbody>
  </table>

  {"" if ragas_enabled else '<p class="meta" style="color:#f59e0b">⚠ Esta corrida usó --no-ragas: Faithfulness y Answer Relevancy quedan vacíos a propósito (no es un error) — solo se midió tiempo.</p>'}
  <p class="meta" style="margin-top:24px">
    Faithfulness/Answer Relevancy calculados con RAGAS, juez local vía Ollama
    (<code>{meta.get('judge_model', '')}</code>) y embeddings
    <code>{meta.get('embedding_model', '')}</code> — no comparables con
    benchmarks que usan GPT-4 como juez, solo entre sí (mismo juez en todas
    las filas). "% Doc. correcto" solo aplica a modos con retrieval vectorial.
    Un juez de 3B a veces no logra producir una evaluación parseable para
    una pregunta puntual (limitación conocida, ver ADR-0003) — cuando pasa,
    esa fila se excluye del promedio y se muestra "(N/total)" junto al
    score para dejarlo explícito, en vez de promediar con NaN en silencio.
  </p>
</body></html>
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)


def main():
    parser = argparse.ArgumentParser(description="Benchmark RAG vs GraphRAG vs Híbrido, y comparación de LLMs")
    parser.add_argument("--questions", default=DEFAULT_QUESTIONS_PATH,
                        help="Ruta al .docx de preguntas (default: preguntas.docx en la raíz)")
    parser.add_argument("--models", default="qwen2.5:3b-instruct-q4_K_M",
                        help="Modelos Ollama a comparar, separados por coma")
    parser.add_argument("--modes", default=",".join(ALL_MODES),
                        help=f"Modos a comparar, separados por coma. Disponibles: {', '.join(ALL_MODES)}")
    parser.add_argument("--limit", type=int, default=None,
                        help="Limitar a las primeras N preguntas (pruebas rápidas)")
    parser.add_argument("--judge-model", default=None,
                        help="Modelo Ollama juez para RAGAS (default: primer modelo de --models)")
    parser.add_argument("--embedding-model", default=None,
                        help="Modelo sentence-transformers para RAGAS (default: paraphrase-multilingual-MiniLM-L12-v2)")
    parser.add_argument("--no-ragas", action="store_true",
                        help="Saltar RAGAS — solo mide tiempos (más rápido, útil para pruebas)")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()

    from scripts.benchmark_dataset import parse_questions_docx
    from scripts.ragas_local import DEFAULT_JUDGE_MODEL, DEFAULT_EMBEDDING_MODEL
    import config

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    modes = [m.strip() for m in args.modes.split(",") if m.strip()]
    for m in modes:
        if m not in ALL_MODES:
            parser.error(f"Modo inválido: {m!r} — usar alguno de {ALL_MODES}")

    judge_model = args.judge_model or models[0] or DEFAULT_JUDGE_MODEL
    embedding_model = args.embedding_model or DEFAULT_EMBEDDING_MODEL

    if not os.path.isfile(args.questions):
        print(f"[BENCHMARK] No se encontró el archivo de preguntas: {args.questions}")
        sys.exit(1)

    questions = parse_questions_docx(args.questions)
    if args.limit:
        questions = questions[:args.limit]

    if "graph_only" in modes or "hybrid" in modes:
        if not config.GRAPH_ENABLED:
            print("[BENCHMARK] AVISO: GRAPH_ENABLED=False — los modos graph_only/hybrid "
                  "no van a tener contexto de grafo.")

    print(f"[BENCHMARK] {len(questions)} pregunta(s) × {len(modes)} modo(s) × {len(models)} modelo(s) "
          f"= {len(questions) * len(modes) * len(models)} corrida(s) de generación.", flush=True)

    os.makedirs(args.out_dir, exist_ok=True)
    hybrid, response_agent, graph_available = _build_pipeline()

    rows = []
    total_runs = len(questions) * len(modes) * len(models)
    done = 0
    for model in models:
        for mode in modes:
            if mode in ("graph_only", "hybrid") and not graph_available:
                print(f"[BENCHMARK] Saltando modo {mode!r} — grafo no disponible.")
                done += len(questions)
                continue
            for q in questions:
                done += 1
                print(f"[BENCHMARK] [{done}/{total_runs}] modelo={model} modo={mode} "
                      f"pregunta={q['question'][:60]!r}", flush=True)
                result = _run_single(hybrid, response_agent, q["question"], mode, model)
                row = {
                    "category": q["category"],
                    "source_doc": q["source_doc"],
                    "question": q["question"],
                    "model": model,
                    "mode_requested": mode,
                    "mode_result": result["mode_result"],
                    "retrieval_seconds": round(result["retrieval_seconds"], 3),
                    "generation_seconds": round(result["generation_seconds"], 3),
                    "total_seconds": round(result["retrieval_seconds"] + result["generation_seconds"], 3),
                    "n_vector_chunks": result["n_vector_chunks"],
                    "n_graph_triples": result["n_graph_triples"],
                    "source_matched": _source_matched(q["source_doc"], result["vector_chunks"]),
                    "answer": result["answer"],
                    "retrieved_texts": result["retrieved_texts"],
                }
                rows.append(row)

    if not rows:
        print("[BENCHMARK] No se generaron filas — nada que reportar.")
        sys.exit(1)

    if args.no_ragas:
        for r in rows:
            r["faithfulness"] = None
            r["answer_relevancy"] = None
    else:
        _run_ragas(rows, judge_model=judge_model, embedding_model=embedding_model,
                   ollama_url=config.OLLAMA_URL)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = os.path.join(args.out_dir, f"benchmark_{ts}.csv")
    html_path = os.path.join(args.out_dir, f"benchmark_{ts}.html")
    summary_path = os.path.join(args.out_dir, f"benchmark_{ts}_summary.json")

    _write_csv(rows, csv_path)

    meta = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "n_questions": len(questions),
        "modes": modes,
        "models": models,
        "judge_model": judge_model,
        "embedding_model": embedding_model,
        "ragas_enabled": not args.no_ragas,
    }
    by_mode = _aggregate(rows, "mode_requested")
    by_model = _aggregate(rows, "model")
    _write_summary_json(rows, summary_path, meta)
    _write_html(rows, by_mode, by_model, html_path, meta)

    print(f"\n[BENCHMARK] Listo. {len(rows)} fila(s).")
    print(f"  CSV:     {csv_path}")
    print(f"  HTML:    {html_path}")
    print(f"  Summary: {summary_path}")


if __name__ == "__main__":
    main()
