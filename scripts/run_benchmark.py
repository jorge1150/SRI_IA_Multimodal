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
  - faithfulness / answer_relevancy / answer_correctness / context_precision /
    context_recall (RAGAS, juez vía Ollama, embeddings sentence-transformers
    — ver scripts/ragas_local.py). Las últimas 3 usan como ground truth el
    campo "respuesta_esperada" de banco_preguntas_v3/banco_preguntas_v3.json
    (verificado contra fuentes oficiales del SRI, no comparan texto idéntico
    sino solape factual + similitud semántica). El juez por defecto es el
    primer modelo cloud presente en --models (si hay alguno): Faithfulness
    le exige al juez extraer afirmaciones atómicas y verificarlas una por
    una contra el contexto, tarea en la que un juez local chico (3B) falla
    mucho más seguido que uno grande — se puede forzar cualquier otro con
    --judge-model.
  - Si el retrieval trajo chunks del documento fuente esperado (según
    banco_preguntas_v3.json), cuando el modo incluye recuperación vectorial.

Salida en outputs/benchmarks/:
  - benchmark_<timestamp>.csv   — una fila por pregunta×modo×modelo
  - benchmark_<timestamp>.html  — reporte visual
  - benchmark_<timestamp>_summary.json — agregados (leído por la UI)

Nota de costo: cada pregunta implica al menos 1 llamada de generación +
hasta 5 llamadas de juez RAGAS, todo en CPU local — una corrida completa
(100 preguntas × 3 modos × N modelos) puede tardar horas. Usar --limit para
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

from services.benchmark_format import (
    EMPTY, fmt_number, fmt_planning_seconds, fmt_ragas_parts, fmt_rate_pct, fmt_refinement,
    fmt_tokens, is_cloud_model, compute_model_ranking, explain_ranking_winner,
)

DEFAULT_QUESTIONS_PATH = os.path.join(_ROOT, "banco_preguntas_v3", "banco_preguntas_v3.json")
DEFAULT_OUT_DIR = os.path.join(_ROOT, "outputs", "benchmarks")
ALL_MODES = ["vector_only", "graph_only", "hybrid", "agentic"]


def _load_questions(path: str) -> list[dict]:
    """Carga banco_preguntas_v3.json — 100 preguntas verificadas contra
    fuentes oficiales del SRI (ver banco_preguntas_v3_resumen.md), con
    respuesta_esperada como ground truth para RAGAS reference-based."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return [
        {
            "categoria": item["categoria"],
            "source_doc": item["fuente_documento"],
            "question": item["pregunta"],
            "ground_truth": item["respuesta_esperada"],
        }
        for item in data
    ]


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


def _build_pipeline():
    """Mismo wiring del tramo retrieval+generación que CoordinatorAgent,
    sin STT/visión/TTS — un solo lugar donde cambia la construcción."""
    from agents.coordinator import build_retrieval_pipeline
    from agents.log_agent import LogAgent

    log_agent = LogAgent()
    _, response_agent, planner_agent, refiner_agent, validator_agent, hybrid, graph_available = \
        build_retrieval_pipeline(log_agent)
    return hybrid, response_agent, planner_agent, refiner_agent, validator_agent, log_agent, graph_available


def _run_single(hybrid, response_agent, planner_agent, refiner_agent, validator_agent,
                 log_agent, question: str, mode: str, model: str) -> dict:
    from agents.token_usage import add_token_usage

    planning_seconds = 0.0
    planner_used_graph = None
    refinement_seconds = 0.0
    refinement_iterations = None
    retrieve_mode = mode
    rag_query = question
    validated_chunks = None
    token_usage = {}
    planning_tokens = {}
    off_topic = False
    off_topic_answer = ""

    if mode == "agentic":
        # Mismo loop Refinador⇄Validador que CoordinatorAgent.process() (ver
        # agents/coordinator.py::run_refinement_loop) — el benchmark de
        # tesis mide el pipeline agentic completo, no solo el Planner.
        # También alimenta outputs/refinement_memory.json (y
        # off_topic_memory.json) con lecciones reales de estas corridas.
        from agents.coordinator import consume_refinement_loop

        t_ref = time.time()
        loop_result = consume_refinement_loop(
            refiner_agent, validator_agent, question, log_agent,
        )
        refinement_seconds = time.time() - t_ref
        rag_query = loop_result["final_query"]
        validated_chunks = loop_result["chunks"]
        refinement_iterations = loop_result["n_iterations"]
        token_usage = loop_result["token_usage"]
        off_topic = loop_result["off_topic"]

        if off_topic:
            # Fuera de dominio (ADR-0007): se mide el corte, no se gasta
            # Planner/retrieval/generación en algo sin normativa que buscar.
            off_topic_answer = loop_result["reason"]
        else:
            t_plan = time.time()
            planner_used_graph = planner_agent.should_use_graph(rag_query, model=model)
            planning_seconds = time.time() - t_plan
            planning_tokens = planner_agent.last_token_usage
            retrieve_mode = "hybrid" if planner_used_graph else "vector_only"

    if off_topic:
        retrieval = {"vector_chunks": [], "graph_context": "", "graph_triples": [], "mode": "vector_only"}
        retrieval_seconds = 0.0
        generation_seconds = 0.0
        generation_tokens = {}
        answer = off_topic_answer
    else:
        t0 = time.time()
        if validated_chunks is not None:
            if retrieve_mode == "hybrid":
                graph_only = hybrid.retrieve(rag_query, mode="graph_only")
                combined_mode = "hybrid" if graph_only.get("graph_context") else "vector_only"
                retrieval = {**graph_only, "vector_chunks": validated_chunks, "mode": combined_mode}
            else:
                retrieval = {
                    "vector_chunks": validated_chunks, "graph_context": "",
                    "graph_triples": [], "graph_entities": [], "mode": "vector_only",
                }
        else:
            retrieval = hybrid.retrieve(rag_query, mode=retrieve_mode)
        retrieval_seconds = time.time() - t0

        t1 = time.time()
        response_agent.generate(
            query=rag_query,
            rag_context=retrieval["vector_chunks"],
            graph_context=retrieval["graph_context"],
            model=model,
        )
        generation_seconds = time.time() - t1
        generation_tokens = response_agent.last_token_usage

        # Respuesta limpia (sin bloque de fuentes) directo del side-channel del
        # agente — antes se cortaba el texto por el separador de display.
        answer = response_agent.last_answer

    retrieved_texts = [c["text"] for c in retrieval["vector_chunks"]]
    if retrieval["graph_context"]:
        retrieved_texts.append(retrieval["graph_context"])

    total_tokens = add_token_usage(add_token_usage(token_usage, planning_tokens), generation_tokens)

    return {
        "mode_result": retrieval["mode"],
        "off_topic": off_topic,
        "refinement_seconds": refinement_seconds,
        "refinement_iterations": refinement_iterations,
        "refinement_tokens": token_usage.get("total_tokens", 0),
        "planning_seconds": planning_seconds,
        "planning_tokens": planning_tokens.get("total_tokens", 0),
        "planner_used_graph": planner_used_graph,
        "retrieval_seconds": retrieval_seconds,
        "generation_seconds": generation_seconds,
        "generation_tokens": generation_tokens.get("total_tokens", 0),
        "total_tokens": total_tokens.get("total_tokens", 0),
        "answer": answer,
        "retrieved_texts": retrieved_texts,
        "vector_chunks": retrieval["vector_chunks"],
        "n_vector_chunks": len(retrieval["vector_chunks"]),
        "n_graph_triples": len(retrieval["graph_triples"]),
    }


RAGAS_METRIC_NAMES = (
    "faithfulness", "answer_relevancy", "answer_correctness",
    "context_precision", "context_recall",
)

# Errores [ERROR] consecutivos que cortan la corrida sola en vez de seguir
# gastando cuota cloud en puro fallo (ej. cuota Ollama Cloud agotada a
# mitad de camino — cada intento siguiente también va a fallar y cuenta
# igual contra la cuota semanal/de sesión). --resume retoma después.
MAX_CONSECUTIVE_ERRORS = 3

# Filas por tanda de juzgamiento RAGAS. evaluate() se llama una vez por tanda
# en vez de una sola vez sobre todas las filas — con corridas grandes (cientos
# de filas × juez cloud) un corte a mitad de camino (red, cuota, VM) antes
# perdía las 5 columnas RAGAS de TODAS las filas, no solo las pendientes. Con
# tandas chicas, cada una se checkpointea al CSV apenas termina (ver
# checkpoint_path en _run_ragas) — un corte solo pierde la tanda en curso.
RAGAS_BATCH_SIZE = 50


def _run_ragas(rows: list, judge_model: str, embedding_model: str, ollama_url: str,
               csv_path: "str | None" = None, json_path: "str | None" = None) -> None:
    """Corre RAGAS en tandas de RAGAS_BATCH_SIZE filas y anota las 5 métricas
    in-place. answer_correctness/context_precision/context_recall usan
    ground_truth (respuesta_esperada de banco_preguntas_v3.json) como
    "reference" — comparan solape factual + similitud semántica contra la
    respuesta del sistema, no exigen texto idéntico. Filas sin retrieved_texts,
    answer o ground_truth vacíos se saltan (RAGAS no tiene nada que evaluar).
    Filas ya juzgadas en una corrida --resume anterior tampoco se reenvían
    (ver _already_judged). Si csv_path/json_path se pasan, se checkpointea
    tras cada tanda — así una corrida larga no pierde el juzgamiento ya
    hecho ante un corte, y --resume puede retomar desde ahí."""
    from ragas import evaluate, EvaluationDataset
    from ragas.metrics import (
        faithfulness, answer_relevancy, answer_correctness,
        context_precision, context_recall,
    )
    from scripts.ragas_local import make_judge_llm, make_embeddings

    # answer.startswith("[ERROR]"): ver ResponseAgent.generate() — mensaje de
    # error propio del proyecto (Ollama caído, modelo no encontrado/retirado,
    # timeout), no una respuesta real. Antes se mandaban igual al juez RAGAS
    # (no está vacío, así que pasaba el filtro) — desperdiciaba horas de
    # llamadas reales evaluando texto de error como si fuera una respuesta,
    # y encima el score real quedaba enmascarado por "0% cobertura" en vez
    # de un aviso claro de que la generación falló.
    def _already_judged(r: dict) -> bool:
        # Fila que viene de una corrida --resume anterior y ya tiene las 5
        # métricas: no volver a gastar cuota del juez en algo ya evaluado.
        # Una fila con NaN parcial (algún metric en None) NO cuenta como
        # juzgada — se reintenta, es barato y puede que ahora sí parsee.
        return all(r.get(name) is not None for name in RAGAS_METRIC_NAMES)

    n_error_answers = sum(1 for r in rows if r["answer"].strip().startswith("[ERROR]"))
    n_already_judged = sum(1 for r in rows if _already_judged(r))
    evaluable = [
        r for r in rows
        if not _already_judged(r)
        and r["answer"].strip() and not r["answer"].strip().startswith("[ERROR]")
        and r["retrieved_texts"] and r.get("ground_truth", "").strip()
    ]
    for r in rows:
        if not _already_judged(r):
            for name in RAGAS_METRIC_NAMES:
                r[name] = None

    if n_error_answers:
        print(f"[BENCHMARK] AVISO: {n_error_answers}/{len(rows)} fila(s) con respuesta "
              f"[ERROR] (falla de generación, no de RAGAS) — excluidas del juez. "
              f"Revisar que el modelo esté disponible: 'docker compose exec ollama ollama pull <modelo>' "
              f"para modelos locales, o que el modelo cloud no esté retirado.", flush=True)

    if n_already_judged:
        print(f"[BENCHMARK] {n_already_judged} fila(s) ya juzgada(s) en una corrida anterior "
              f"(--resume) — no se vuelven a mandar al juez.", flush=True)

    if not evaluable:
        print("[BENCHMARK] Sin filas evaluables para RAGAS (respuestas, contexto o ground_truth vacíos, "
              "todas con [ERROR], o todas ya juzgadas).")
        return

    print(f"[BENCHMARK] Corriendo RAGAS sobre {len(evaluable)} fila(s) en tandas de "
          f"{RAGAS_BATCH_SIZE} (juez: {judge_model}, embeddings: {embedding_model})...", flush=True)

    llm = make_judge_llm(judge_model, ollama_url)
    embeddings = make_embeddings(embedding_model)

    n_failed = {name: 0 for name in RAGAS_METRIC_NAMES}
    n_batches = math.ceil(len(evaluable) / RAGAS_BATCH_SIZE)
    for i in range(0, len(evaluable), RAGAS_BATCH_SIZE):
        batch = evaluable[i:i + RAGAS_BATCH_SIZE]
        batch_n = i // RAGAS_BATCH_SIZE + 1
        print(f"[BENCHMARK] Juez RAGAS — tanda {batch_n}/{n_batches} ({len(batch)} fila(s))...", flush=True)

        dataset = EvaluationDataset.from_list([
            {
                "user_input": r["question"],
                "response": r["answer"],
                "retrieved_contexts": r["retrieved_texts"],
                "reference": r["ground_truth"],
            }
            for r in batch
        ])
        # evaluate() puede tardar minutos y reintentar solo (RunConfig) ante
        # fallos de red/cuota — si igual termina reventando (excepción dura,
        # no NaN), no perder las tandas ya checkpointeadas: se corta el
        # loop de tandas acá, no todo el script.
        try:
            result = evaluate(
                dataset=dataset,
                metrics=[faithfulness, answer_relevancy, answer_correctness, context_precision, context_recall],
                llm=llm, embeddings=embeddings,
            )
            df = result.to_pandas()
        except Exception as exc:
            print(f"[BENCHMARK] AVISO: la tanda {batch_n}/{n_batches} del juez RAGAS reventó ({exc!r}) — "
                  f"probable cuota cloud agotada a mitad del juzgamiento. Se corta acá, lo ya "
                  f"juzgado queda guardado. Reintentá más tarde con --resume.", flush=True)
            break

        for r, (_, row) in zip(batch, df.iterrows()):
            for name in RAGAS_METRIC_NAMES:
                val = _none_if_nan(row.get(name))
                r[name] = val
                n_failed[name] += val is None

        # Ninguna métrica de la tanda parseó — no es el "juez chico falla
        # de vez en cuando" de ADR-0003 (eso es parcial), es más compatible
        # con la cuota cloud agotada a mitad del juzgamiento (mismos
        # RuntimeError de httpcore/anyio por conexiones canceladas que ya
        # se vieron en generación). Seguir mandando tandas solo va a
        # reintentar en fallo — se corta y se deja para el próximo --resume.
        batch_failed = sum(1 for r in batch for name in RAGAS_METRIC_NAMES if r.get(name) is None)
        batch_total = len(batch) * len(RAGAS_METRIC_NAMES)
        if batch_total and batch_failed == batch_total:
            print(f"[BENCHMARK] AVISO: 0/{batch_total} métricas parsearon en la tanda {batch_n}/{n_batches} "
                  f"— probable cuota cloud agotada, no una falla puntual del juez. Se corta el juzgamiento "
                  f"acá (las tandas anteriores ya quedaron guardadas). Reintentá más tarde con --resume.",
                  flush=True)
            if csv_path:
                _write_csv(rows, csv_path)
            if json_path:
                _write_checkpoint_json(rows, json_path)
            break

        if csv_path:
            _write_csv(rows, csv_path)
        if json_path:
            _write_checkpoint_json(rows, json_path)
        if csv_path or json_path:
            print(f"[BENCHMARK] Checkpoint guardado tras tanda {batch_n}/{n_batches}.", flush=True)

    failed_report = ", ".join(f"{n}/{len(evaluable)} ({name})" for name, n in n_failed.items() if n)
    if failed_report:
        print(f"[BENCHMARK] Juez RAGAS no pudo evaluar: {failed_report} — "
              f"NaN del juez local, se excluyen del promedio (no del CSV).", flush=True)


def _write_csv(rows: list, path: str) -> None:
    fields = [
        "categoria", "source_doc", "question", "ground_truth", "model", "mode_requested", "mode_result",
        "off_topic",
        "refinement_seconds", "refinement_iterations", "refinement_tokens",
        "planning_seconds", "planning_tokens", "planner_used_graph",
        "retrieval_seconds", "generation_seconds", "generation_tokens", "total_seconds",
        "total_tokens",
        "n_vector_chunks", "n_graph_triples", "source_matched",
        "faithfulness", "answer_relevancy", "answer_correctness", "context_precision", "context_recall",
        "answer",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def _checkpoint_json_path(csv_path: str) -> str:
    base = csv_path[:-4] if csv_path.endswith(".csv") else csv_path
    return base + ".checkpoint.json"


def _write_checkpoint_json(rows: list, path: str) -> None:
    """Espejo de las filas en JSON, con lo que el CSV no persiste
    (sobre todo retrieved_texts) — --resume lo necesita para poder juzgar
    con RAGAS filas generadas en una corrida anterior sin re-generarlas.
    El CSV (_write_csv) sigue siendo el artefacto legible para humanos;
    este JSON es el que lee --resume, se sobreescribe entero cada vez
    (mismo patrón que _write_csv, no un log append-only)."""
    slim = [{k: v for k, v in r.items() if k != "vector_chunks"} for r in rows]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(slim, f, ensure_ascii=False)


def _load_checkpoint_json(path: str) -> list:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


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
        ragas_vals = {
            name: [i[name] for i in items if _valid(i.get(name))]
            for name in RAGAS_METRIC_NAMES
        }
        matched = [i["source_matched"] for i in items if i["source_matched"] is not None]
        # Descriptivo, no una métrica de acierto — no hay ground truth de
        # "esta pregunta debería haber usado grafo". Solo aplica al modo
        # "agentic"; en el resto, planner_used_graph es siempre None.
        planner_decisions = [i.get("planner_used_graph") for i in items if i.get("planner_used_graph") is not None]
        refinement_iters = [i.get("refinement_iterations") for i in items if i.get("refinement_iterations") is not None]
        out[k] = {
            "n": n,
            **{f"n_{name}_evaluated": len(vals) for name, vals in ragas_vals.items()},
            "avg_refinement_seconds": sum(i.get("refinement_seconds", 0.0) for i in items) / n,
            "avg_refinement_iterations": (sum(refinement_iters) / len(refinement_iters)) if refinement_iters else None,
            "avg_planning_seconds": sum(i.get("planning_seconds", 0.0) for i in items) / n,
            "avg_retrieval_seconds": sum(i["retrieval_seconds"] for i in items) / n,
            "avg_generation_seconds": sum(i["generation_seconds"] for i in items) / n,
            "avg_total_seconds": sum(i["total_seconds"] for i in items) / n,
            "avg_total_tokens": sum(i.get("total_tokens", 0) for i in items) / n,
            **{f"avg_{name}": (sum(vals) / len(vals)) if vals else None for name, vals in ragas_vals.items()},
            "source_match_rate": (sum(matched) / len(matched)) if matched else None,
            "planner_graph_usage_rate": (sum(planner_decisions) / len(planner_decisions)) if planner_decisions else None,
        }
    return out


def _aggregate_by_mode_and_model(rows: list) -> dict:
    """Mismo agregado que _aggregate(rows, 'mode_requested'), pero partido
    también por modelo — {modo: {modelo: {...}}}. "by_mode" mezcla todos los
    modelos de la corrida en un solo promedio por modo, lo que no deja ver
    si el resultado vino del modelo local o del cloud; esto alimenta el
    combo de filtro por modelo de la tab "Por Modo de Recuperación" en la UI
    (ver ADR-0011)."""
    out = {}
    for mode in sorted({r["mode_requested"] for r in rows}):
        out[mode] = _aggregate([r for r in rows if r["mode_requested"] == mode], "model")
    return out


def _write_summary_json(rows: list, path: str, meta: dict) -> None:
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "n_rows": len(rows),
        **meta,
        "by_mode": _aggregate(rows, "mode_requested"),
        "by_model": _aggregate(rows, "model"),
        "by_mode_per_model": _aggregate_by_mode_and_model(rows),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)


def _bar(value: float, max_value: float, color: str) -> str:
    pct = 0 if not max_value else max(2, min(100, round(100 * value / max_value)))
    return (f'<div style="background:#1e293b;border-radius:4px;overflow:hidden;height:14px;width:100%">'
            f'<div style="background:{color};height:100%;width:{pct}%"></div></div>')


def _fmt_ragas_cell(v, n_evaluated: int, n_total: int) -> str:
    base, note = fmt_ragas_parts(v, n_evaluated, n_total)
    if base is None:
        return EMPTY
    return f"{base} ({note})" if note else base


def _write_html(rows: list, by_mode: dict, by_model: dict, path: str, meta: dict) -> None:
    max_total = max((v["avg_total_seconds"] for v in by_mode.values()), default=1) or 1
    ragas_enabled = meta.get("ragas_enabled", True)

    mode_rows = "".join(
        f"<tr><td>{html.escape(mode)}</td>"
        f"<td>{v['n']}</td>"
        f"<td>{fmt_refinement(v.get('avg_refinement_seconds'), v.get('avg_refinement_iterations'))}</td>"
        f"<td>{fmt_planning_seconds(v.get('avg_planning_seconds'))}</td>"
        f"<td>{fmt_number(v['avg_retrieval_seconds'], 's')}</td>"
        f"<td>{fmt_number(v['avg_generation_seconds'], 's')}</td>"
        f"<td>{fmt_number(v['avg_total_seconds'], 's')}<br>{_bar(v['avg_total_seconds'], max_total, '#3b82f6')}</td>"
        f"<td>{_fmt_ragas_cell(v.get('avg_faithfulness'), v.get('n_faithfulness_evaluated', 0), v['n'])}</td>"
        f"<td>{_fmt_ragas_cell(v.get('avg_answer_relevancy'), v.get('n_answer_relevancy_evaluated', 0), v['n'])}</td>"
        f"<td>{_fmt_ragas_cell(v.get('avg_answer_correctness'), v.get('n_answer_correctness_evaluated', 0), v['n'])}</td>"
        f"<td>{_fmt_ragas_cell(v.get('avg_context_precision'), v.get('n_context_precision_evaluated', 0), v['n'])}</td>"
        f"<td>{_fmt_ragas_cell(v.get('avg_context_recall'), v.get('n_context_recall_evaluated', 0), v['n'])}</td>"
        f"<td>{fmt_rate_pct(v['source_match_rate'])}</td>"
        f"<td>{fmt_rate_pct(v.get('planner_graph_usage_rate'))}</td>"
        f"</tr>"
        for mode, v in sorted(by_mode.items())
    )
    model_rows = "".join(
        f"<tr><td>{'🌐' if is_cloud_model(model) else '💻'} {html.escape(model)}</td>"
        f"<td>{v['n']}</td>"
        f"<td>{fmt_refinement(v.get('avg_refinement_seconds'), v.get('avg_refinement_iterations'))}</td>"
        f"<td>{fmt_planning_seconds(v.get('avg_planning_seconds'))}</td>"
        f"<td>{fmt_number(v['avg_retrieval_seconds'], 's')}</td>"
        f"<td>{fmt_number(v['avg_generation_seconds'], 's')}</td>"
        f"<td>{fmt_number(v['avg_total_seconds'], 's')}<br>{_bar(v['avg_total_seconds'], max_total, '#a78bfa')}</td>"
        f"<td>{fmt_tokens(v.get('avg_total_tokens'))}</td>"
        f"<td>{_fmt_ragas_cell(v.get('avg_faithfulness'), v.get('n_faithfulness_evaluated', 0), v['n'])}</td>"
        f"<td>{_fmt_ragas_cell(v.get('avg_answer_relevancy'), v.get('n_answer_relevancy_evaluated', 0), v['n'])}</td>"
        f"<td>{_fmt_ragas_cell(v.get('avg_answer_correctness'), v.get('n_answer_correctness_evaluated', 0), v['n'])}</td>"
        f"<td>{_fmt_ragas_cell(v.get('avg_context_precision'), v.get('n_context_precision_evaluated', 0), v['n'])}</td>"
        f"<td>{_fmt_ragas_cell(v.get('avg_context_recall'), v.get('n_context_recall_evaluated', 0), v['n'])}</td>"
        f"</tr>"
        for model, v in sorted(by_model.items())
    )

    ranking = compute_model_ranking(by_model)
    ranking_html = ""
    if ranking:
        ranking_rows = "".join(
            f"<tr><td>#{i+1}</td>"
            f"<td>{'🌐' if r['is_cloud'] else '💻'} {html.escape(r['model'])}</td>"
            f"<td>{r['score']:.2f}</td></tr>"
            for i, r in enumerate(ranking)
        )
        winner_explanation = explain_ranking_winner(ranking)
        ranking_html = f"""
  <h2>🏆 Ranking recomendado</h2>
  <table>
    <thead><tr><th>#</th><th>Modelo</th><th>Score</th></tr></thead>
    <tbody>{ranking_rows}</tbody>
  </table>
  {f'<p class="meta"><strong>{html.escape(winner_explanation)}</strong></p>' if winner_explanation else ''}
  <p class="meta">Heurística de comparación (ver ADR-0009), no una medición absoluta:
     score = 50% calidad (promedio de Faithfulness/Answer Relevancy/Answer
     Correctness/Context Precision/Context Recall evaluados) + 30% velocidad + 20% costo
     (tokens totales), normalizado entre los modelos de esta corrida. Modelos sin
     RAGAS evaluado quedan fuera del ranking.</p>
"""

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
    <thead><tr><th>Modo</th><th>N</th><th>Refinamiento</th><th>Planning</th><th>Retrieval</th><th>Generación</th><th>Total</th>
    <th>Faithfulness</th><th>Answer Relevancy</th><th>Answer Correctness</th><th>Context Precision</th><th>Context Recall</th><th>% Doc. correcto</th><th>Grafo usado (planner)</th></tr></thead>
    <tbody>{mode_rows}</tbody>
  </table>

  <h2>Comparación por modelo LLM</h2>
  <table>
    <thead><tr><th>Modelo</th><th>N</th><th>Refinamiento</th><th>Planning</th><th>Retrieval</th><th>Generación</th><th>Total</th>
    <th>Tokens</th><th>Faithfulness</th><th>Answer Relevancy</th><th>Answer Correctness</th><th>Context Precision</th><th>Context Recall</th></tr></thead>
    <tbody>{model_rows}</tbody>
  </table>
  {ranking_html}
  {"" if ragas_enabled else '<p class="meta" style="color:#f59e0b">⚠ Esta corrida usó --no-ragas: las 5 métricas RAGAS quedan vacías a propósito (no es un error) — solo se midió tiempo. El ranking recomendado tampoco está disponible sin RAGAS.</p>'}
  <p class="meta" style="margin-top:24px">
    Faithfulness/Answer Relevancy/Answer Correctness/Context Precision/Context Recall
    calculados con RAGAS, juez local vía Ollama (<code>{meta.get('judge_model', '')}</code>)
    y embeddings <code>{meta.get('embedding_model', '')}</code> — no comparables con
    benchmarks que usan GPT-4 como juez, solo entre sí (mismo juez en todas
    las filas). Answer Correctness/Context Precision/Context Recall usan como
    referencia el campo <code>respuesta_esperada</code> de
    <code>banco_preguntas_v3.json</code> (verificado contra fuentes oficiales
    del SRI) — comparan solape factual y similitud semántica, no exigen texto
    idéntico. "% Doc. correcto" solo aplica a modos con retrieval vectorial.
    Un juez de 3B a veces no logra producir una evaluación parseable para
    una pregunta puntual (limitación conocida, ver ADR-0003) — cuando pasa,
    esa fila se excluye del promedio y se muestra "(N/total)" junto al
    score para dejarlo explícito, en vez de promediar con NaN en silencio.
    "Refinamiento", "Planning" y "Grafo usado (planner)" solo aplican al modo
    "agentic" — "Refinamiento" mide el loop Refinador⇄Validador (ver
    ADR-0006, tiempo total y promedio de iteraciones hasta converger o
    forzar el paso), "Planning" es la decisión sí/no GraphRAG que toma el
    PlannerAgent vía tool-calling; "Grafo usado" es descriptivo (qué % de
    preguntas activó el grafo), no una métrica de acierto — no hay ground
    truth de qué debería haber decidido. Esta corrida también alimenta
    <code>outputs/refinement_memory.json</code> con las lecciones reales
    del loop (few-shot para corridas futuras).
  </p>
</body></html>
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)


def main():
    parser = argparse.ArgumentParser(description="Benchmark RAG vs GraphRAG vs Híbrido, y comparación de LLMs")
    parser.add_argument("--questions", default=DEFAULT_QUESTIONS_PATH,
                        help="Ruta al banco de preguntas JSON (default: banco_preguntas_v3/banco_preguntas_v3.json)")
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
    parser.add_argument("--run-id", default=None,
                        help="Nombre fijo para los archivos de salida (en vez del timestamp) — "
                             "necesario para poder usar --resume después. Ej. --run-id ragas_full")
    parser.add_argument("--resume", action="store_true",
                        help="Retomar una corrida anterior con el mismo --run-id: salta combos "
                             "modelo×modo×pregunta ya generados y filas ya juzgadas por RAGAS. "
                             "Requiere --run-id.")
    args = parser.parse_args()

    if args.resume and not args.run_id:
        parser.error("--resume requiere --run-id (así sabe qué corrida retomar)")

    from scripts.ragas_local import DEFAULT_JUDGE_MODEL, DEFAULT_EMBEDDING_MODEL
    import config

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    modes = [m.strip() for m in args.modes.split(",") if m.strip()]
    for m in modes:
        if m not in ALL_MODES:
            parser.error(f"Modo inválido: {m!r} — usar alguno de {ALL_MODES}")

    # Juez por defecto: si hay algún modelo cloud entre --models, se prefiere
    # como juez sobre uno local. RAGAS exige que el juez devuelva salida
    # estructurada parseable (sobre todo faithfulness, que implica extraer
    # afirmaciones atómicas y verificarlas una por una) — un juez de pocos
    # parámetros falla ese parseo mucho más seguido (ver ADR-0003/ADR-0011).
    # Se puede forzar cualquier otro con --judge-model.
    _default_judge = next((m for m in models if is_cloud_model(m)), models[0])
    judge_model = args.judge_model or _default_judge or DEFAULT_JUDGE_MODEL
    embedding_model = args.embedding_model or DEFAULT_EMBEDDING_MODEL

    if not os.path.isfile(args.questions):
        print(f"[BENCHMARK] No se encontró el archivo de preguntas: {args.questions}")
        sys.exit(1)

    questions = _load_questions(args.questions)
    if args.limit:
        questions = questions[:args.limit]

    if {"graph_only", "hybrid", "agentic"} & set(modes):
        if not config.GRAPH_ENABLED:
            print("[BENCHMARK] AVISO: GRAPH_ENABLED=False — los modos graph_only/hybrid/agentic "
                  "no van a tener contexto de grafo.")

    print(f"[BENCHMARK] {len(questions)} pregunta(s) × {len(modes)} modo(s) × {len(models)} modelo(s) "
          f"= {len(questions) * len(modes) * len(models)} corrida(s) de generación.", flush=True)

    os.makedirs(args.out_dir, exist_ok=True)

    # Nombre de archivo: --run-id fijo (necesario para --resume) o timestamp
    # (corridas sueltas, sin retomar — comportamiento previo sin cambios).
    # csv_path/json_path se usan como checkpoint incremental durante la
    # corrida (ver más abajo), no solo como destino final. Corridas largas
    # (cientos de filas × modelo cloud, horas) antes no guardaban nada hasta
    # el final — un corte de VM/red/cuota a mitad de camino perdía todo lo
    # generado.
    base_name = args.run_id or datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = os.path.join(args.out_dir, f"benchmark_{base_name}.csv")
    html_path = os.path.join(args.out_dir, f"benchmark_{base_name}.html")
    summary_path = os.path.join(args.out_dir, f"benchmark_{base_name}_summary.json")
    json_checkpoint_path = _checkpoint_json_path(csv_path)

    rows = []
    done_keys = set()
    if args.resume:
        if os.path.isfile(json_checkpoint_path):
            rows = _load_checkpoint_json(json_checkpoint_path)
            done_keys = {(r["model"], r["mode_requested"], r["question"]) for r in rows}
            print(f"[BENCHMARK] --resume: {len(rows)} fila(s) recuperada(s) de {json_checkpoint_path} "
                  f"— se saltan esos combos modelo×modo×pregunta.", flush=True)
        else:
            print(f"[BENCHMARK] --resume: no hay checkpoint previo en {json_checkpoint_path} "
                  f"— arranca de cero (va a quedar guardado para la próxima).", flush=True)

    hybrid, response_agent, planner_agent, refiner_agent, validator_agent, log_agent, graph_available = _build_pipeline()

    total_runs = len(questions) * len(modes) * len(models)
    done = 0
    consecutive_errors = 0
    quota_likely_exhausted = False
    for model in models:
        for mode in modes:
            if quota_likely_exhausted:
                break
            if mode in ("graph_only", "hybrid") and not graph_available:
                print(f"[BENCHMARK] Saltando modo {mode!r} — grafo no disponible.")
                done += len(questions)
                continue
            for q in questions:
                done += 1
                key = (model, mode, q["question"])
                if key in done_keys:
                    continue
                print(f"[BENCHMARK] [{done}/{total_runs}] modelo={model} modo={mode} "
                      f"pregunta={q['question'][:60]!r}", flush=True)
                result = _run_single(
                    hybrid, response_agent, planner_agent, refiner_agent, validator_agent,
                    log_agent, q["question"], mode, model,
                )
                row = {
                    "categoria": q["categoria"],
                    "source_doc": q["source_doc"],
                    "question": q["question"],
                    "ground_truth": q["ground_truth"],
                    "model": model,
                    "mode_requested": mode,
                    "mode_result": result["mode_result"],
                    "off_topic": result["off_topic"],
                    "refinement_seconds": round(result["refinement_seconds"], 3),
                    "refinement_iterations": result["refinement_iterations"],
                    "refinement_tokens": result["refinement_tokens"],
                    "planning_seconds": round(result["planning_seconds"], 3),
                    "planning_tokens": result["planning_tokens"],
                    "planner_used_graph": result["planner_used_graph"],
                    "retrieval_seconds": round(result["retrieval_seconds"], 3),
                    "generation_seconds": round(result["generation_seconds"], 3),
                    "generation_tokens": result["generation_tokens"],
                    "total_seconds": round(
                        result["refinement_seconds"] + result["planning_seconds"]
                        + result["retrieval_seconds"] + result["generation_seconds"], 3
                    ),
                    "total_tokens": result["total_tokens"],
                    "n_vector_chunks": result["n_vector_chunks"],
                    "n_graph_triples": result["n_graph_triples"],
                    "source_matched": _source_matched(q["source_doc"], result["vector_chunks"]),
                    "answer": result["answer"],
                    "retrieved_texts": result["retrieved_texts"],
                }
                rows.append(row)
                _write_csv(rows, csv_path)                    # checkpoint humano
                _write_checkpoint_json(rows, json_checkpoint_path)  # checkpoint para --resume

                if row["answer"].strip().startswith("[ERROR]"):
                    consecutive_errors += 1
                    if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                        quota_likely_exhausted = True
                        print(f"[BENCHMARK] AVISO: {consecutive_errors} errores seguidos — probable cuota "
                              f"cloud agotada (ver el texto [ERROR] en la última fila del CSV). Se corta la "
                              f"corrida acá para no seguir gastando cuota en puro fallo. Ya está guardado: "
                              f"volvé a mandar el mismo comando con --resume cuando la cuota se reponga.",
                              flush=True)
                        break
                else:
                    consecutive_errors = 0
            if quota_likely_exhausted:
                break

    if not rows:
        print("[BENCHMARK] No se generaron filas — nada que reportar.")
        sys.exit(1)

    n_errors = sum(1 for r in rows if r["answer"].strip().startswith("[ERROR]"))
    if n_errors:
        pct = 100 * n_errors / len(rows)
        print(f"[BENCHMARK] AVISO: {n_errors}/{len(rows)} filas ({pct:.0f}%) tienen respuesta "
              f"[ERROR] — el modelo no generó de verdad en esas filas (ver mensaje de error en "
              f"la columna 'answer' del CSV: modelo no encontrado/no pulled, timeout, o modelo "
              f"cloud retirado). El reporte de tiempos/RAGAS de esas filas no es representativo.",
              flush=True)

    if args.no_ragas:
        for r in rows:
            for name in RAGAS_METRIC_NAMES:
                r[name] = None
        _write_csv(rows, csv_path)
    elif quota_likely_exhausted:
        # Mismo motivo que el corte de generación: si la cuota cloud ya se
        # agotó, mandar las filas al juez (otro modelo cloud, misma cuenta)
        # solo va a sumar más [ERROR]/NaN sin aportar nada. Se deja para el
        # próximo --resume, cuando ya haya cuota repuesta.
        print("[BENCHMARK] Se salta el juzgamiento RAGAS de esta corrida — cuota probablemente agotada "
              "(ver aviso arriba). El próximo --resume retoma generación Y juzgamiento pendientes.",
              flush=True)
    else:
        _run_ragas(rows, judge_model=judge_model, embedding_model=embedding_model,
                   ollama_url=config.OLLAMA_URL, csv_path=csv_path, json_path=json_checkpoint_path)
        _write_csv(rows, csv_path)  # cada tanda ya checkpointea; esto solo cubre el caso "0 filas evaluables"
        _write_checkpoint_json(rows, json_checkpoint_path)

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
