# Juez RAGAS por defecto, desglose por-modo-y-modelo, y explicación del ranking

La tab "📊 Benchmark RAGAS" mezclaba resultados de forma que dificultaba interpretarlos: el juez RAGAS por defecto era el primer modelo de `--models` (casi siempre el 3B local, ver ADR-0003), la tabla "Por Modo de Recuperación" promediaba todos los modelos de la corrida sin indicar cuál produjo qué, y el ranking recomendado (ADR-0009) mostraba un score sin explicar por qué el #1 ganó. Se corrigen los tres puntos.

## El juez local falla sistemáticamente en Faithfulness, no solo "seguido"

Hasta ahora `n_faithfulness_evaluated` era **0 en absolutamente todas las corridas guardadas**, incluida una de 168 filas — no una tasa baja, sino 0% de éxito siempre, con `qwen2.5:3b-instruct-q4_K_M` como juez en todos los casos. Una prueba en vivo confirmó que el juez local **sí** puede evaluar Faithfulness correctamente con un ejemplo trivial (una pregunta, un contexto corto de una oración) — `faithfulness=1.0`. Esto descarta que sea una incapacidad total del modelo, y apunta a que falla con el contexto real del benchmark: fragmentos largos de texto legal, donde Faithfulness exige extraer afirmaciones atómicas de la respuesta y verificar cada una contra el contexto — una tarea de salida estructurada bastante más compleja que la que requiere Answer Relevancy (que sí logra evaluar parcialmente en las mismas corridas).

## Juez por defecto: prefiere el modelo cloud presente en `--models`

`scripts/run_benchmark.py` — si `--models` incluye algún modelo cuyo nombre termina en `-cloud` (`is_cloud_model`, ver ADR-0008), se usa automáticamente como juez RAGAS en vez del primero de la lista. Un modelo grande es más confiable produciendo la salida estructurada que RAGAS necesita, sobre todo para Faithfulness. Sigue siendo posible forzar cualquier otro juez con `--judge-model`. Es un cambio de comportamiento por defecto (antes: siempre el primer `--models`) — se documenta acá porque corridas viejas con el mismo comando ahora eligen un juez distinto.

## `by_mode_per_model`: desglose por modo Y modelo

`by_mode` y `by_model` (existentes) agregan por un solo eje cada uno — no había forma de saber si, por ejemplo, el modo `hybrid` tardó tanto por el modelo local o el cloud. `_aggregate_by_mode_and_model()` en `scripts/run_benchmark.py` reutiliza `_aggregate()` agrupando primero por modo y, dentro de cada modo, por modelo (`{modo: {modelo: {...}}}`), y se agrega al `summary.json` como `by_mode_per_model`. La tab "Benchmark RAGAS" (`ui/interface.py::_mode_section_html`) gana un combo "Todos los modelos / 🌐 modelo / 💻 modelo" que filtra la tabla "Por Modo de Recuperación" usando esta estructura — "Todos" sigue mostrando el agregado mezclado de siempre.

## Aviso de baja cobertura RAGAS

Un score como "0.31 (1/10)" es fácil de leer como "score bajo" cuando el problema real es que el juez solo pudo evaluar 1 de 10 filas — el promedio no es representativo. `ragas_coverage_warning()` en `services/benchmark_format.py` genera un aviso explícito cuando menos del 50% de un grupo (modo o modelo) tiene faithfulness/answer_relevancy evaluado, sugiriendo un juez más grande o correr sin `--limit`. Mismo umbral en todos los grupos, reutilizable porque el problema es el mismo sea cual sea el eje de agregación.

## Ranking recomendado: por qué gana el #1, no solo el score

`compute_model_ranking()` (ADR-0009) ahora expone también los subscores crudos y normalizados (`quality_raw/n`, `speed_raw/n`, `cost_raw/n`) usados internamente para el score compuesto, y `explain_ranking_winner()` compara el #1 contra el #2 y señala cuál de los tres factores (calidad 50% / velocidad 30% / costo 20%) tuvo mayor contribución ponderada a la diferencia — o indica que quedaron "muy parejos" si la diferencia es marginal (≤0.02). La tab muestra esta frase junto a una tabla desplegable con los subscores, para que la recomendación se pueda verificar en vez de solo confiar en un número.
