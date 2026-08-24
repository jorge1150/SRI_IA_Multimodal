"""Regenera HTML + summary.json desde el checkpoint real, sin re-correr
generación ni juzgamiento — solo recalcula agregados y vuelve a renderizar."""
import json
from datetime import datetime, timezone
from scripts.run_benchmark import _aggregate, _write_summary_json, _write_html

CKPT = "outputs/benchmarks/benchmark_ragas_full.checkpoint.json"
HTML = "outputs/benchmarks/benchmark_ragas_sample20.html"
SUMMARY = "outputs/benchmarks/benchmark_ragas_sample20_summary.json"

with open(CKPT) as f:
    d = json.load(f)
all_rows = d if isinstance(d, list) else d.get("rows", d)

RAGAS_METRIC_NAMES = ["faithfulness", "answer_relevancy", "answer_correctness", "context_precision", "context_recall"]
# Reporte SOLO con la muestra realmente juzgada (20/celda) — no las 800
# totales, para que el "N" y la cobertura mostrada sean 100% reales
# (40/40 por modo) y no se vea "ruido" tipo 40/200.
rows = [r for r in all_rows if all(r.get(m) is not None for m in RAGAS_METRIC_NAMES)]

models = sorted(set(r.get("model") for r in rows))
modes = sorted(set(r.get("mode_requested") for r in rows))

meta = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "n_questions": len(set(r.get("question") for r in rows)),
    "modes": modes,
    "models": models,
    "judge_model": "claude-haiku-4-5 (muestra estratificada 20/celda, ver nota)",
    "embedding_model": "paraphrase-multilingual-MiniLM-L12-v2",
    "ragas_enabled": True,
}
by_mode = _aggregate(rows, "mode_requested")
by_model = _aggregate(rows, "model")
_write_summary_json(rows, SUMMARY, meta)
_write_html(rows, by_mode, by_model, HTML, meta)
print("Reporte regenerado:", HTML, SUMMARY)
