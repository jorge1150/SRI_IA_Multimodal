# RAGAS completo en cuota Free de Ollama Cloud: juez neutral, corridas retomables

Se necesitaba correr el benchmark RAGAS completo (100 preguntas × 4 modos ×
2 modelos cloud = 800 filas) en la VM de demo, sobre el corpus ampliado
(62 PDFs, ver commit `76036a1`), para tener datos reales para la
presentación de tesis — no una muestra chica de prueba. Una corrida
anterior con el mismo comando dio cobertura muy baja (~80/400 celdas
RAGAS llenas) pese a que el fix de `4e0093d` (excluir respuestas
`[ERROR]` del juez, avisar tasa de error) ya estaba en producción.

## La causa real: cuota de Ollama Cloud agotada a mitad de corrida, no los errores ya conocidos

`4e0093d` documentó tres causas reales de `[ERROR]` (modelo local no
pulled, modelo cloud retirado, OOM del 3B local) — ninguna es cuota. Se
confirmó en vivo que la corrida de baja cobertura fue **posterior** a ese
fix, y que una prueba manual del usuario devolvió explícitamente "cuota
agotada". Revisando `ollama.com` (cuenta Free) se vieron dos cupos
independientes: **sesión** (resetea cada pocas horas) y **semanal**
(resetea en días) — con una muestra chica (72 requests = 1.2% de la
cuota semanal) el techo semanal estimado ronda ~6000 llamadas.

La matriz completa no es solo un problema de pacing por sesión: cada fila
implica ~1 llamada de generación (más en modo `agentic`, que suma
Planner/Refinador/Validador) y hasta ~5-7 llamadas de juez RAGAS (5
métricas), todas cayendo sobre la misma cuenta. 800 filas × esas
llamadas da un total estimado de 6000-8000 llamadas — probablemente NO
entra en una semana de cuota Free en una sola corrida.

## Ollama Pro quedó descartado — no por elección, por el método de pago

La opción más simple (pagar Ollama Pro, $20/mes, 50x cuota) no se pudo
ejecutar: Ollama no acepta tarjetas del país del usuario. No es una
decisión de costo/beneficio, es un bloqueo externo. Esto fija la
estrategia: la corrida completa se hace en cuota **Free**, repartida en
varias sesiones a medida que la cuota semanal/de sesión se repone —
"de a poco hasta completarla" en vez de una sola corrida de una sentada.

## Juez: tercer modelo neutral, no el mismo que genera

Con `--models gemma4:31b-cloud,gpt-oss:20b-cloud`, el default de
`run_benchmark.py` (ADR-0011: primer modelo cloud de `--models`) elegiría
`gemma4:31b-cloud` como juez — evaluando también sus propias respuestas.
Self-preference bias (un juez LLM tiende a puntuarse mejor a sí mismo) es
un problema conocido en la literatura de LLM-as-judge y compromete la
comparación entre los dos modelos generadores. Se decidió forzar
`--judge-model` a un tercer modelo cloud que no compite en la
comparación de generación.

## Selección real del juez: "Usage Level" de Ollama Cloud, no solo tamaño

Probado en vivo contra la cuenta Free real de la VM de demo
(`docker compose exec ollama ollama run <modelo> "responde solo: ok"`):

| Modelo probado | Resultado | Motivo (ollama.com/library) |
|---|---|---|
| `deepseek-v4-pro:cloud` | 403 — requiere suscripción | "Extra High Usage" |
| `qwen3.5:397b-cloud` | 403 — requiere suscripción | 397B, tier alto |
| `gemma4:31b-cloud` | OK (ya en uso, generación) | "Low Usage" |
| `gpt-oss:20b-cloud` | OK (ya en uso, generación) | "Low Usage" |
| `nemotron-3-nano:30b-cloud` | OK — **elegido como juez** | "Low Usage", 30B |

Ollama Cloud etiqueta cada modelo cloud con un "Usage Level" (Low/Medium/
High/Extra High) en su ficha — es el peso de cada llamada contra la
cuota, no una medida de capacidad. Los modelos "Extra High Usage" que
probamos son todos modelos flagship enormes (397B-1T+, ej. también
`glm-5.1:cloud` 756B, `kimi-k2.6:cloud` 1.04T) — quedan detrás de Pro.
Los modelos "Low/Medium Usage" (~20-30B, la misma liga que
`gemma4:31b-cloud` y `gpt-oss:20b-cloud`) sí están disponibles en Free, y
además consumen menos cuota por llamada — doblemente conveniente para
un juez que se invoca cientos de veces.

`nemotron-3-nano:30b-cloud` (NVIDIA) se eligió por: familia distinta a
Google (Gemma) y OpenAI (GPT-OSS) — no compite ni comparte sesgos de
familia con ninguno de los dos modelos generadores —, tamaño (30B) en la
misma liga que `gemma4:31b-cloud`, el juez cloud ya validado en vivo en
ADR-0011 (ahí Faithfulness pasó de 0/N con el juez local de 3B a 5/5 con
un juez cloud ~30B), y "Low Usage" — no compite por cuota de forma
desproporcionada con los dos modelos de generación.

## Límite metodológico, documentado a propósito

Un juez de 30B en la nube es una mejora real sobre el juez local de 3B
(ADR-0003: 0% de Faithfulness evaluable en TODAS las corridas históricas
por salida no parseable) — pero sigue sin ser GPT-4 ni una medida
absoluta de calidad. `scripts/ragas_local.py` ya documenta este límite
para el juez local y aplica igual acá: los scores de Faithfulness/Answer
Relevancy/etc. sirven para comparar `gemma4:31b-cloud` vs
`gpt-oss:20b-cloud` **entre sí** (mismo juez, mismo criterio, en todas
las filas) — no como benchmark absoluto frente a la literatura. Se deja
explícito en la metodología de tesis, mismo criterio que ADR-0003/0011.

## Corridas retomables — `scripts/run_benchmark.py`

Para poder repartir la corrida completa en varias sesiones sin perder lo
ya pagado en cuota ni repetir trabajo:

- **`--run-id <nombre>`**: nombre fijo de archivo en vez de timestamp —
  necesario para que dos invocaciones apunten al mismo checkpoint.
- **`--resume`**: carga el checkpoint de una corrida anterior con el
  mismo `--run-id`, salta combos modelo×modo×pregunta ya generados, y
  salta filas ya evaluadas por RAGAS (una fila con alguna métrica en
  `None` por fallo del juez SÍ se reintenta — es barato y puede que
  ahora sí parsee).
- **Corte automático**: 3 respuestas `[ERROR]` seguidas paran la corrida
  sola (probable cuota agotada — seguir intentando solo suma más
  `[ERROR]` contra la misma cuota) en vez de recorrer las ~800 filas
  restantes en fallo silencioso. Mismo criterio se aplica antes de mandar
  al juez: si la corrida se cortó por esto, se salta el juzgamiento de
  esa invocación entero (el juez es otro modelo cloud de la misma
  cuenta — también va a fallar) y se deja todo para el próximo
  `--resume`.
- **Checkpoint doble**: el CSV (legible, como siempre) más un
  `.checkpoint.json` con lo que el CSV no persiste (`retrieved_texts`) —
  necesario para poder juzgar con RAGAS una fila generada en una sesión
  anterior sin tener que regenerarla. Se reescribe tras cada fila
  generada y tras cada tanda de juzgamiento (`RAGAS_BATCH_SIZE = 50`
  filas por llamada a `evaluate()`, en vez de una sola llamada sobre
  todo el dataset — un corte a mitad del juzgamiento ya no pierde las 5
  columnas RAGAS de filas que sí llegaron a evaluarse).

## Comando final

```bash
docker compose exec app python scripts/run_benchmark.py \
  --models gemma4:31b-cloud,gpt-oss:20b-cloud \
  --modes vector_only,graph_only,hybrid,agentic \
  --judge-model nemotron-3-nano:30b-cloud \
  --run-id ragas_full
```

Y, cada vez que la cuota se agote y se reponga (sesión/semana), el mismo
comando con `--resume`:

```bash
docker compose exec app python scripts/run_benchmark.py \
  --models gemma4:31b-cloud,gpt-oss:20b-cloud \
  --modes vector_only,graph_only,hybrid,agentic \
  --judge-model nemotron-3-nano:30b-cloud \
  --run-id ragas_full --resume
```
