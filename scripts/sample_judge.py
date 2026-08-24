"""
Juzgamiento RAGAS por MUESTRA ESTRATIFICADA — escribe de verdad en el
checkpoint real (benchmark_ragas_full.checkpoint.json + .csv), a diferencia
de test_claude_judge.py que solo probaba en un dataset descartable.

Toma hasta N filas por combinación (model, mode_requested) de las filas
evaluables (no [ERROR], con retrieved_texts y ground_truth), las juzga con
el juez Claude indicado, y escribe el resultado SOLO en esas filas — el
resto queda sin tocar (None), documentado como "muestra parcial" en vez de
corrida completa.

Uso: docker compose exec app python scripts/sample_judge.py <judge_model> <n_per_cell> [cell1,cell2,...]
  cell = "modelo|modo", ej. "gemma4:31b-cloud|vector_only". Sin lista = todas
  las combinaciones (model, mode_requested) presentes en los datos.
"""
import json
import sys
import time
from collections import defaultdict

JUDGE_MODEL = sys.argv[1] if len(sys.argv) > 1 else "claude-haiku-4-5"
N_PER_CELL = int(sys.argv[2]) if len(sys.argv) > 2 else 15
CELLS_ARG = sys.argv[3] if len(sys.argv) > 3 else None
RESTRICT_CELLS = set(tuple(c.split("|")) for c in CELLS_ARG.split(",")) if CELLS_ARG else None

from ragas import evaluate, EvaluationDataset
from ragas.metrics import faithfulness, answer_relevancy, answer_correctness, context_precision, context_recall
from scripts.ragas_local import make_claude_judge_llm, make_embeddings

CKPT = "outputs/benchmarks/benchmark_ragas_full.checkpoint.json"
CSV = "outputs/benchmarks/benchmark_ragas_full.csv"
RAGAS_METRIC_NAMES = ["faithfulness", "answer_relevancy", "answer_correctness", "context_precision", "context_recall"]

with open(CKPT) as f:
    d = json.load(f)
rows = d if isinstance(d, list) else d.get("rows", d)

def already_judged(r):
    return all(r.get(name) is not None for name in RAGAS_METRIC_NAMES)

evaluable = [
    r for r in rows
    if not already_judged(r)
    and r["answer"].strip() and not r["answer"].strip().startswith("[ERROR]")
    and r["retrieved_texts"] and r.get("ground_truth", "").strip()
]

by_cell = defaultdict(list)
for r in evaluable:
    key = (r.get("model"), r.get("mode_requested"))
    by_cell[key].append(r)

picked = []
for key, group in by_cell.items():
    if RESTRICT_CELLS is not None and key not in RESTRICT_CELLS:
        continue
    picked.extend(group[:N_PER_CELL])

print(f"[SAMPLE] juez={JUDGE_MODEL} celdas={len(by_cell) if RESTRICT_CELLS is None else len(RESTRICT_CELLS)} "
      f"n_por_celda={N_PER_CELL} total_filas={len(picked)}", flush=True)
for key in sorted(by_cell):
    if RESTRICT_CELLS is not None and key not in RESTRICT_CELLS:
        continue
    n_this = min(N_PER_CELL, len(by_cell[key]))
    print(f"  {key}: {n_this} filas", flush=True)

if not picked:
    print("[SAMPLE] nada para juzgar con esos filtros.")
    sys.exit(0)

dataset = EvaluationDataset.from_list([
    {
        "user_input": r["question"],
        "response": r["answer"],
        "retrieved_contexts": r["retrieved_texts"],
        "reference": r["ground_truth"],
    }
    for r in picked
])

llm = make_claude_judge_llm(JUDGE_MODEL)
embeddings = make_embeddings()

t0 = time.time()
result = evaluate(
    dataset=dataset,
    metrics=[faithfulness, answer_relevancy, answer_correctness, context_precision, context_recall],
    llm=llm, embeddings=embeddings,
)
elapsed = time.time() - t0
df = result.to_pandas()

for r, (_, row) in zip(picked, df.iterrows()):
    for name in RAGAS_METRIC_NAMES:
        val = row.get(name)
        r[name] = None if (val is None or str(val) == "nan") else float(val)

n_sub = len(picked) * len(RAGAS_METRIC_NAMES)
n_ok = sum(1 for r in picked for name in RAGAS_METRIC_NAMES if r.get(name) is not None)
print(f"[SAMPLE] {elapsed:.1f}s total, {n_ok}/{n_sub} sub-evaluaciones parseadas "
      f"({100*n_ok/n_sub:.0f}% cobertura)", flush=True)

# Guardar de vuelta en el checkpoint real (rows completo, no solo picked)
with open(CKPT, "w") as f:
    json.dump(d, f, ensure_ascii=False)
print(f"[SAMPLE] checkpoint actualizado: {CKPT}", flush=True)

# CSV: regenerar con pandas simple a partir de rows completo
import pandas as pd
pd.DataFrame(rows).to_csv(CSV, index=False)
print(f"[SAMPLE] csv actualizado: {CSV}", flush=True)
