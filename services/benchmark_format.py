"""
benchmark_format.py — Formateo compartido de métricas del benchmark.

Un solo lugar para las convenciones de presentación que antes estaban
duplicadas entre el reporte HTML de scripts/run_benchmark.py y la tab
"Benchmark RAGAS" de ui/interface.py:
  - "—" (em-dash) para valores no medidos / no aplicables,
  - "(N/total)" cuando el juez RAGAS solo pudo evaluar parte del grupo,
  - segundos con 2 decimales, tasas como porcentaje entero.

Los consumidores componen su propio estilo visual (span coloreado en la UI,
texto plano en el HTML del script) sobre estas piezas — acá vive solo la
semántica.
"""

import math

EMPTY = "—"


def _is_missing(v) -> bool:
    return v is None or (isinstance(v, float) and math.isnan(v))


def fmt_number(v, suffix: str = "") -> str:
    """Número con 2 decimales, o EMPTY si falta/NaN. Ej.: fmt_number(1.5, 's') → '1.50s'."""
    if not isinstance(v, (int, float)) or _is_missing(v):
        return EMPTY
    return f"{v:.2f}{suffix}"


def fmt_ragas_parts(v, n_evaluated: int, n_total: int) -> tuple:
    """
    (score, nota) para una métrica RAGAS agregada:
      - (None, None)   → no evaluado (--no-ragas, o grupo sin filas evaluables)
      - ("0.42", None) → todas las filas del grupo evaluadas
      - ("0.42", "2/3")→ el juez local falló en parte del grupo — el promedio
                          es solo de las que sí evaluó (limitación juez 3B,
                          ver ADR-0003); la nota lo hace explícito.
    """
    if _is_missing(v) or not n_total:
        return None, None
    base = f"{v:.2f}"
    if n_evaluated < n_total:
        return base, f"{n_evaluated}/{n_total}"
    return base, None


def fmt_planning_seconds(avg_planning_seconds) -> str:
    """Solo el modo agentic tiene paso de planning — 0/None → EMPTY."""
    p = avg_planning_seconds or 0.0
    return fmt_number(p, "s") if p > 0 else EMPTY


def fmt_refinement(avg_refinement_seconds, avg_refinement_iterations) -> str:
    """Solo el modo agentic tiene loop Refinador⇄Validador — 0/None → EMPTY.
    Ej.: '1.42s (1.8 it.)'."""
    s = avg_refinement_seconds or 0.0
    if s <= 0:
        return EMPTY
    it = fmt_number(avg_refinement_iterations) if avg_refinement_iterations is not None else EMPTY
    return f"{fmt_number(s, 's')} ({it} it.)"


def fmt_rate_pct(rate) -> str:
    """Tasa 0..1 como porcentaje entero, o EMPTY si no aplica (None)."""
    if _is_missing(rate):
        return EMPTY
    return f"{rate * 100:.0f}%"


def fmt_tokens(avg_total_tokens) -> str:
    """Tokens promedio por consulta (prompt+completion, todas las llamadas
    Ollama de la corrida), 0/None → EMPTY. Ver ADR-0009."""
    t = avg_total_tokens or 0
    return f"{t:,.0f}".replace(",", " ") if t > 0 else EMPTY


def is_cloud_model(model: str) -> bool:
    """Reexporta config.is_cloud_model para que este módulo no dependa de
    importar `config` en cada consumidor — heurística por convención de
    nombre de Ollama Cloud (sufijo '-cloud', ver ADR-0008)."""
    return model.endswith("-cloud")


def compute_model_ranking(by_model: dict) -> list[dict]:
    """
    Heurística de comparación entre modelos — NO un score validado, ver
    ADR-0009: pesos fijos declarados, no aprendidos, mismo criterio
    "descriptivo, no ground truth" que ya aplica a planner_graph_usage_rate.

    score = 0.5×calidad_norm + 0.3×velocidad_norm + 0.2×costo_norm, con
    min-max normalizado dentro de los modelos presentes en `by_model`
    (velocidad y costo invertidos: más rápido/barato = mejor).

    Modelos sin ninguna métrica RAGAS evaluada quedan fuera del ranking
    (no se inventa una calidad de 0) — se listan aparte con nota.

    Retorna lista ordenada de {"model": str, "score": float, "is_cloud": bool},
    o [] si menos de 2 modelos tienen calidad evaluable (no hay nada que
    comparar).
    """
    def _quality(v: dict) -> float | None:
        parts = [x for x in (v.get("avg_faithfulness"), v.get("avg_answer_relevancy")) if not _is_missing(x)]
        return sum(parts) / len(parts) if parts else None

    ranked_candidates = {
        model: v for model, v in by_model.items() if _quality(v) is not None
    }
    if len(ranked_candidates) < 2:
        return []

    def _minmax_norm(values: dict, invert: bool = False) -> dict:
        lo, hi = min(values.values()), max(values.values())
        if hi == lo:
            return {k: 1.0 for k in values}
        return {
            k: (hi - v) / (hi - lo) if invert else (v - lo) / (hi - lo)
            for k, v in values.items()
        }

    quality = {m: _quality(v) for m, v in ranked_candidates.items()}
    speed = {m: v.get("avg_total_seconds", 0.0) for m, v in ranked_candidates.items()}
    cost = {m: v.get("avg_total_tokens", 0.0) for m, v in ranked_candidates.items()}

    quality_n = _minmax_norm(quality)
    speed_n = _minmax_norm(speed, invert=True)
    cost_n = _minmax_norm(cost, invert=True)

    scored = [
        {
            "model": m,
            "score": round(0.5 * quality_n[m] + 0.3 * speed_n[m] + 0.2 * cost_n[m], 4),
            "is_cloud": is_cloud_model(m),
        }
        for m in ranked_candidates
    ]
    return sorted(scored, key=lambda x: x["score"], reverse=True)
