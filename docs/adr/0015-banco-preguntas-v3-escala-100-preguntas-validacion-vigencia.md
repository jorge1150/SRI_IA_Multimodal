# banco_preguntas_v3 reemplaza v2 como ground truth, escala a 100 preguntas / 51 documentos, con validación de vigencia obligatoria por entrada

`banco_preguntas_v2/banco_preguntas_v2.json` (20 preguntas, ADR-0012) se reemplaza por completo por `banco_preguntas_v3/banco_preguntas_v3.json`: 100 preguntas, generadas en 5 corridas secuenciales (~16 preguntas c/u) del subagente `contador-experto` (`.claude/agents/contador-experto.md`), con la misma metodología de v2 (navegación en vivo a sri.gob.ec vía `agent-browser --headed`, PDF fuente descargado a `data/<categoria>/`, `respuesta_esperada` citando texto textual verificado) más un requisito nuevo: validación activa de vigencia por artículo citado, registrada en un campo `vigencia_verificada` por entrada. Objetivo: robustez estadística para publicación Q1 (>100 preguntas, >50 documentos normativos).

## Por qué el reemplazo, no una unión

Mismo razonamiento que ADR-0012: mantener v2 y v3 como bancos separados dejaría 20 preguntas sin el campo `vigencia_verificada` conviviendo con 80 que sí lo tienen, complicando la agregación de resultados del benchmark sin aportar nada. `banco_preguntas_v3.json` incluye las 20 preguntas originales de v2 con sus mismos IDs (q01-q20) — no se re-generaron ni se re-verificó su vigencia retroactivamente (fuera de alcance de esta expansión); su campo `vigencia_verificada` quedó explícitamente marcado `{"revisado": false, "nota": "hereda estado previo, no re-verificado en esta corrida"}`, salvo q06 que documenta inline la corrección ya conocida de ADR-0012.

## Motivación de la validación de vigencia obligatoria

ADR-0012 documentó que q06 citó una resolución (NAC-DGERCGC25-00000014) sin detectar que había sido reformada por una posterior (NAC-DGERCGC25-00000017) — un experto contable externo lo detectó *después* de cerrado el banco. Para v3, la instrucción al subagente (punto 6 de `.claude/agents/contador-experto.md`) exige buscar activamente reformas/derogatorias antes de aceptar cada pregunta, no como hallazgo posterior. El campo `vigencia_verificada` por entrada documenta cómo se hizo esa verificación (lectura del PDF descargado, cruce con una página institucional en vivo, o ambas).

### Deuda de schema: `reforma_encontrada` en texto libre, no booleano confiable

El subagente no siguió el schema estructurado pedido (`{"revisado": bool, "fecha": str, "reforma_encontrada": bool, "nota": str}`) para q21-q100 — devolvió `vigencia_verificada` como una sola cadena de texto describiendo el proceso de verificación. Se normalizó post-hoc envolviendo ese texto en `nota` y fijando `reforma_encontrada: null` para esas 80 entradas (no se infirió el booleano por keyword-matching sobre el texto libre, para no introducir falsos positivos/negativos silenciosos). Consecuencia práctica: **`reforma_encontrada` NO es un campo confiable para filtrar programáticamente "qué preguntas tuvieron una reforma detectada"** — hay que leer `nota` entrada por entrada. La única excepción es q06 (heredada de v2), donde `reforma_encontrada: true` sí está confirmado. Corrección futura: si se vuelve a invocar `contador-experto` para más batches, reforzar en el prompt de invocación que `vigencia_verificada` debe ser el objeto JSON exacto, no una descripción en prosa.

## Escala y ritmo de descarga de PDFs

El primer batch bajó solo 2 PDFs nuevos de 16 preguntas (reuso extensivo de fuentes ya en `data/`), insuficiente para llegar a 50+ documentos en 5 batches. Se corrigió a partir del batch 2 imponiendo una cuota mínima explícita de PDFs nuevos por corrida (8 para batches 2-4, 10 para el batch 5 de cierre) en el mensaje de invocación — no es una regla permanente del agente, sino una instrucción operativa de esta expansión particular. Resultado: 2 + 11 + 9 + 8 + 11 = 41 PDFs nuevos, para un total de 51 en `data/` (10 preexistentes de v2 se conservan intactos, verificado con `git status` y comparación de rutas tras cada batch).

## Categorías: de 5 fijas a 25 libres

`.claude/agents/contador-experto.md` dejó de restringir `categoria` a un enum de 5 valores — el agente puede abrir carpetas nuevas en `data/`, que `config.get_data_dirs()` ya descubre automáticamente (sin tabla de mapeo, ver ADR-0002/nota en CONTEXT.md). El banco final cubre 25 categorías: las 5 originales (IVA, Retenciones en la fuente, Impuesto a la Renta, Facturación electrónica, RIMPE) más 20 nuevas (ICE, Precios de Transferencia, Otros, Comercio Exterior, RUC, Impuestos Vehiculares, Impuesto a las Tierras Rurales, Impuesto Redimible a las Botellas Plásticas, Herencias/Legados/Donaciones, Beneficios Tributarios - Discapacidad/Turismo/Tercera Edad, Impuesto a los Activos en el Exterior, ZEDE, Ley de Eficiencia Económica, Consultas Tributarias, Facilidades de Pago, Anexo RDEP, Anexo Dividendos, Fiscalidad Internacional, Vivienda de Interés Social, RIVUT, Sector Bananero, Ganancias de Capital, Devolución IVA a Proveedores de Exportadores). Distribución final no es uniforme (Impuesto a la Renta 14, la mayoría de categorías nuevas 2) — refleja disponibilidad real de normativa verificable, no una cuota impuesta.

## Dedup: dependencia externa al repo

`preguntas.docx` (42 preguntas sin ground truth, usado como referencia de dedup en ADR-0012) ya no existe en el repo — se eliminó en el mismo commit que introdujo `banco_preguntas_v2/`. El subagente lo recuperó de una copia en `~/Downloads` del usuario para poder deduplicar contra él en los 5 batches. Riesgo: si esa copia local desaparece, una futura expansión del banco no tiene con qué chequear duplicado contra esas 42 preguntas originales — recomendación pendiente: subir esa copia a un lugar versionado (o confirmar que ya no aporta valor y descartar el chequeo formalmente).

## Pendiente fuera de este ADR

- Revisión humana final (experto tributario externo) sobre las 100 preguntas — no ejecutada como parte de esta expansión, queda a cargo del usuario.
- Reconstrucción de `vector_db/chroma_sri` y `graph_db/sri_graph.json` con el corpus de 51 PDFs, y re-run de `scripts/run_benchmark.py` con las 100 preguntas — comandos entregados al usuario, no ejecutados aquí.
- ~~`scripts/run_benchmark.py` seguía con `DEFAULT_QUESTIONS_PATH` apuntando a v2~~ — corregido el mismo día a pedido explícito del usuario: `DEFAULT_QUESTIONS_PATH` y todos los comentarios/docstrings que mencionaban `banco_preguntas_v2`/"20 preguntas" ahora apuntan a `banco_preguntas_v3`/"100 preguntas". Correr `python scripts/run_benchmark.py` sin `--questions` ya usa v3 por default.
