"""
token_usage.py — Extracción compartida de conteo de tokens de Ollama
Ollama devuelve `prompt_eval_count`/`eval_count` en la raíz de la respuesta
de /api/chat (no dentro de "message"). Un solo lugar para esta extracción,
reusado por los 4 agentes que llaman Ollama (ResponseAgent, PlannerAgent,
QueryRefinerAgent, QueryValidatorAgent) — solo para benchmark/comparación
de modelos (ver ADR-0009), no se expone en el chat en vivo.
"""


def extract_token_usage(resp_json: dict) -> dict:
    """
    Retorna {"prompt_tokens": int, "completion_tokens": int, "total_tokens": int},
    o {} si la respuesta no trae esos campos (versión vieja de Ollama, o
    algún proxy que no los reenvía).
    """
    prompt = resp_json.get("prompt_eval_count")
    completion = resp_json.get("eval_count")
    if prompt is None and completion is None:
        return {}
    prompt = prompt or 0
    completion = completion or 0
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": prompt + completion,
    }


def add_token_usage(acc: dict, usage: dict) -> dict:
    """Suma `usage` (posiblemente {}) sobre el acumulador `acc` — usado para
    sumar tokens de varias llamadas dentro de un mismo loop de refinamiento
    o de una corrida de benchmark. No muta ninguno de los dos dicts."""
    return {
        "prompt_tokens": acc.get("prompt_tokens", 0) + usage.get("prompt_tokens", 0),
        "completion_tokens": acc.get("completion_tokens", 0) + usage.get("completion_tokens", 0),
        "total_tokens": acc.get("total_tokens", 0) + usage.get("total_tokens", 0),
    }
