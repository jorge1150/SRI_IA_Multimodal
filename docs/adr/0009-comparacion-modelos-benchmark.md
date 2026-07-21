# Comparación de modelos en el Benchmark: tokens, selector y ranking recomendado

Con el pivot a modelos local-o-cloud (ADR-0008), comparar modelos deja de ser solo "cuál responde mejor" — también importa cuánto cuesta (tokens, con implicación de costo real en modelos cloud) y cuánto tarda. El benchmark ya comparaba modos/modelos por tiempo y RAGAS (`scripts/run_benchmark.py`); se extiende para cubrir esto.

## Captura de tokens

Ollama devuelve `prompt_eval_count`/`eval_count` en la raíz de la respuesta de `/api/chat` (no dentro de `"message"`). Los 4 agentes que llaman Ollama (`ResponseAgent`, `PlannerAgent`, `QueryRefinerAgent`, `QueryValidatorAgent`) exponen un side-channel `last_token_usage: dict` (`{"prompt_tokens", "completion_tokens", "total_tokens"}`, `{}` si la llamada falló) — mismo patrón que `ResponseAgent.last_answer`. Extracción centralizada en `agents/token_usage.py::extract_token_usage()` para no duplicarla 4 veces.

**Alcance deliberadamente acotado**: solo se usa en el benchmark (`scripts/run_benchmark.py` acumula tokens por etapa — refinamiento, planning, generación — y los reporta en CSV/HTML/summary.json). El chat de producción no muestra tokens por consulta — no se pidió, y agregarlo ahí habría sido una superficie de UI nueva sin necesidad clara.

## Selector de modelo en la tab Benchmark (solo lectura)

La tab "📊 Benchmark RAGAS" gana un combo de modelo (`ui/interface.py`) que lista los modelos presentes en el último `summary.json` y muestra una tarjeta de detalle (tiempos, RAGAS, tokens promedio, badge 🌐 Cloud / 💻 Local vía `config.is_cloud_model`). Igual que el resto de la tab, es **estrictamente de solo lectura** — elegir un modelo filtra datos ya calculados, nunca dispara una corrida nueva. Correr el benchmark sigue siendo por terminal.

## Ranking recomendado: heurística declarada, no un score validado

`services/benchmark_format.py::compute_model_ranking(by_model)` calcula un score compuesto por modelo:

```
score = 0.5 × calidad_norm + 0.3 × velocidad_norm + 0.2 × costo_norm
```

- **Calidad** (50%): promedio de faithfulness/answer_relevancy disponibles — pesa más porque el proyecto prioriza que la respuesta sea correcta y fiel al contexto antes que rápida o barata (mismo criterio que ya motivó reemplazar TinyLlama por Qwen2.5, ver ADR-0003).
- **Velocidad** (30%) y **costo/tokens** (20%): normalizados min-max e invertidos (más rápido/barato = mejor) dentro de los modelos presentes en esa corrida — no hay una escala absoluta de "tokens buenos", solo comparación relativa entre lo que se corrió.
- Modelos sin ninguna métrica RAGAS evaluada (ej. corridas con `--no-ragas`) quedan **fuera** del ranking — no se les asigna una calidad de 0, porque eso sería inventar un dato que no se midió.

Se documenta explícitamente como heurística de comparación con pesos fijos y declarados, no aprendidos ni validados contra ningún ground truth — mismo criterio de honestidad que ya aplica a `planner_graph_usage_rate` (ADR-0005): ayuda a decidir, no reemplaza el juicio de quien lee la tabla completa.
