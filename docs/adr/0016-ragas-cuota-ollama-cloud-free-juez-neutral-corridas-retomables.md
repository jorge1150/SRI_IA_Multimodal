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

## Update 2026-08-24: bug de reset en `--resume`, juez alternativo vía API de Anthropic, muestra estratificada

En producción (VM de demo), el `--resume` de arriba no aceleraba el
juzgamiento — se sentía "atascado en el juez, vuelve a mandarlo". Dos
causas reales, encontradas en vivo:

**Bug de reset destructivo (ya arreglado, commit `ffd7106`)**: antes de
cada tanda, `_run_ragas()` reseteaba a `None` las 5 métricas de
CUALQUIER fila sin las 5 completas — incluidas filas con 3-4 métricas ya
bien parseadas de una corrida anterior. Como el checkpoint escribe
`rows` completo tras cada tanda, ese reset se grababa en disco aunque la
fila reseteada no llegara a re-procesarse en esa corrida. Verificado en
vivo: 189/800 filas juzgadas antes de un `--resume`, 8/800 después. Fix:
sacar el reset — el loop de post-tanda ya sobrescribe cada métrica con
el resultado fresco cuando esa fila se re-evalúa, no hace falta limpiar
antes.

**`RAGAS_BATCH_SIZE` bajado de 50 a 10**: con un juez "thinking" (razona
antes de responder cada métrica), una tanda de 50 filas son 250
sub-evaluaciones a 5-45s cada una — 40-45 min por tanda, y el checkpoint
solo se guarda al CERRAR la tanda completa. Un corte a mitad (Ctrl+C,
ssh caído) perdía toda la tanda. Con 10 filas el checkpoint cae cada
~8-9 min.

### Juez alternativo: API de Anthropic (Claude), no solo Ollama

`scripts/ragas_local.py` — `is_claude_model()` + `make_claude_judge_llm()`.
Si `--judge-model` empieza con `claude-`, `run_benchmark.py` enruta a la
API de Anthropic (`langchain-anthropic`, `ANTHROPIC_API_KEY` en el
entorno) en vez de Ollama. Motivación: cuota Free de Ollama Cloud +
juez "thinking" lento hacía que 800 filas tomaran días repartidos en
sesiones; la API de Anthropic es prepago sin techo semanal.

**Gotchas encontrados en vivo, ambos con impacto real de costo/tiempo**:
- `claude-sonnet-5` / `claude-opus-5` (thinking adaptativo por defecto)
  devuelven `400 temperature is deprecated for this model` — no es un
  parámetro que pasemos nosotros, es RAGAS mismo
  (`ragas/llms/base.py: LangchainLLMWrapper.generate`) forzando
  `langchain_llm.temperature = 1e-8` en cada llamada porque detecta el
  atributo. Fix: usar `claude-sonnet-4-6` (generación anterior, sigue
  aceptando `temperature`) en vez de parchear el wrapper.
- `claude-haiku-4-5` con el `max_tokens` default del wrapper truncaba
  sistemáticamente `answer_correctness`
  (`LLMDidNotFinishException`, 0/2 parseadas en prueba real). Fix:
  `ChatAnthropic(model=model, max_tokens=4096)` explícito en
  `make_claude_judge_llm` — con eso, 100% cobertura también con Haiku.

**Costo real medido (no estimado)**, cuenta API prepago separada de
Claude Pro (ver CONTEXT.md "Cuota Ollama Cloud" — la API de Anthropic
no tiene ese concepto, es saldo prepago que se agota y no se recarga
solo salvo que se active recarga automática, que se dejó desactivada a
propósito):
- `claude-sonnet-4-6`: **~$0.34/fila** — 800 filas completas ≈ $270,
  inviable con presupuesto de estudiante. Se abandonó como juez de la
  corrida completa tras gastar ~$10 en una corrida parcial.
- `claude-haiku-4-5` (con el fix de `max_tokens`): **~$0.04/fila** —
  800 filas completas ≈ $32, mucho más viable, pero seguía por encima
  del saldo disponible en el momento (quedaban $8.30).

_Avoid_: asumir que el costo de un juez LLM escala solo con el precio
por token publicado — el contexto recuperado (`retrieved_texts`) se
reenvía COMPLETO en cada una de las 5 llamadas por fila (RAGAS no lo
cachea entre métricas), así que el costo real por fila depende del
tamaño del contexto de cada modo (`hybrid`/`agentic` mandan más
contexto que `vector_only`), no solo del modelo.

### Muestra estratificada (`scripts/sample_judge.py`) para avances de tesis con presupuesto/tiempo acotado

Cuando ni el tiempo (Ollama Free, días) ni el presupuesto (Claude, ~$32
para las 800 completas) alcanzan para un avance urgente, se juzga una
muestra estratificada en vez de la corrida completa: N filas por cada
combinación (`model`, `mode_requested`) de las ya generadas (la
generación de las 800 respuestas no cuesta nada extra — ya está hecha;
lo caro es solo el juzgamiento RAGAS).

`scripts/sample_judge.py <judge_model> <n_por_celda> [celda1,celda2,...]`
— celda = `"modelo|modo"`, sin filtro = todas las combinaciones
presentes. Escribe el resultado DIRECTO en el checkpoint/CSV reales
(a diferencia de un script de prueba descartable) — mismo formato que
`run_benchmark.py`, así que es compatible con `--resume` después si se
decide extender la muestra o completar el corpus entero más adelante.

`scripts/regen_report.py` — regenera el HTML + `_summary.json` desde el
checkpoint SIN re-correr generación ni juzgamiento, filtrando a solo las
filas con las 5 métricas completas (evita que el reporte muestre
cobertura tipo "40/200" — ruido — cuando en realidad se juzgó
deliberadamente una muestra, no el corpus completo). Guarda con un
nombre de archivo distinto (`benchmark_ragas_sample20*`, no
`benchmark_ragas_full*`) para no pisar el reporte de la corrida completa
cuando esa eventualmente se complete — la UI (`ui/interface.py`,
`_load_latest_summary()`) toma el `*_summary.json` que ordene último
alfabéticamente como "el más reciente", así que un nombre que ordene
después de `..._full_summary.json` (ej. `..._sample20_summary.json`,
`s` > `f`) se muestra automático sin cambios de código.

**Resultado real de este avance (2026-08-24)**: 160 filas (20 por cada
una de las 8 combinaciones modo×modelo), 100% cobertura en las 5
métricas, juez `claude-haiku-4-5`. Costo real total de la sesión (incluye
el experimento fallido con Sonnet 4.6 + el fix de una celda contaminada
por un proceso que siguió corriendo en background más de lo esperado):
$8.30 → $0.17, es decir **~$8.13 gastados**, más que el ~$6.40
estimado (160 × $0.04) solo por los tropiezos del camino — lección para
la próxima corrida: matar un proceso de juzgamiento con `sudo kill` y
CONFIRMAR que terminó antes de seguir con otra cosa, no asumir que
cortar el monitoreo corta el proceso.

_Avoid_: mezclar en el mismo reporte filas juzgadas por jueces distintos
(ej. nemotron + Claude, o Sonnet + Haiku) — jueces distintos no puntúan
igual la misma respuesta; un promedio que mezcla ambos no es comparable
entre celdas. Si un juez cambia a mitad de camino, resetear (a `None`)
las filas ya juzgadas por el juez anterior antes de continuar con el
nuevo — ver el bug de reset arriba para la forma correcta de hacerlo sin
perder lo demás.
