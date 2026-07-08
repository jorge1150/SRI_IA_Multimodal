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


def fmt_rate_pct(rate) -> str:
    """Tasa 0..1 como porcentaje entero, o EMPTY si no aplica (None)."""
    if _is_missing(rate):
        return EMPTY
    return f"{rate * 100:.0f}%"
