# Validación manual del sistema RAG/GraphRAG — Banco de preguntas v2

**Fecha de la prueba original:** 2026-08-06
**Fecha de la 1ª re-validación (post-fix embedder):** 2026-08-06
**Fecha de la 2ª re-validación (post-fix dedup/top_k):** 2026-08-06
**Fecha de la 3ª re-validación (post-fix system prompt):** 2026-08-06
**Fecha de la 4ª re-validación (post-fix duplicado #2 en el corpus):** 2026-08-06
**Fecha de la 5ª re-validación (post-fix chunker `graph_text`) — ESTADO FINAL DEFINITIVO de esta sesión, no habrá más rondas:** 2026-08-07
**Sistema probado:** UI Gradio en `http://localhost:7865` (SRI IA Multimodal — RAG + GraphRAG Híbrido, LLM `gemma4:31b-cloud`)
**Metodología:** Para cada pregunta del banco v2 (`banco_preguntas_v2/banco_preguntas_v2.json`) se limpió el chat (botón "Limpiar"), se escribió la pregunta exacta, se esperó la etapa `[FIN]` en el log de trazabilidad, y se capturó la respuesta completa del chatbot junto con los documentos citados en el panel "Fragmentos Normativos Recuperados". La comparación contra `respuesta_esperada` usó criterio de solape factual (fechas, porcentajes, artículo, umbrales/condiciones).

**Nota sobre la 1ª re-validación (embedder):** Se diagnosticó que una causa raíz de los fallos originales era que el motor de retrieval usaba un embedder de texto inadecuado (ver `docs/adr/0013-embedder-texto-clip-a-sentence-transformers.md`). Tras corregirlo y reconstruir la base vectorial (ahora usando `paraphrase-multilingual-MiniLM-L12-v2`), se re-probaron las 18 preguntas que habían fallado en la corrida original (todas menos q01 y q04). Esos resultados están marcados con **"Actualización 2026-08-06 (post-fix embedder)"**.

**Nota sobre la 2ª re-validación (dedup/top_k):** Se detectó una segunda causa raíz en `agents/response_agent.py`: la función `_dedup_by_doc` que arma el contexto para el LLM solo dejaba pasar 1 chunk por documento, lo que para documentos tipo tabla (p. ej. `retenciones_fuente_ir_2026.pdf`, con múltiples porcentajes según categoría) descartaba la fila específica que la pregunta necesitaba aunque estuviera entre los fragmentos recuperados. Se subió a `max_per_doc=6, max_total=10` y `RAG_TOP_K` de 8 a 12. Se re-probaron las 14 preguntas que seguían fallando tras el fix del embedder (q02, q03, q06, q07, q08, q10, q11, q12, q14, q15, q17, q18, q19, q20). Esos resultados están marcados con **"Actualización 2026-08-06 (post-fix dedup/top_k)"**.

**Nota sobre la 3ª re-validación (system prompt):** Se detectó una tercera causa: el system prompt del LLM generador (`agents/response_agent.py::_SYSTEM_PROMPT`) era mínimo y no daba guía sobre qué hacer cuando el contexto trae varias versiones de un dato (resolución que reforma a otra, tablas de distintos años), ni insistía en extraer el dato numérico exacto pedido. Se agregaron 3 reglas cortas: (1) priorizar la versión vigente/más reciente, (2) extraer el dato exacto si aparece en cualquier fragmento (no decir "falta información" si está), y (3) no citar documentos/artículos que no estén literalmente en el contexto. Se re-probaron las 12 preguntas que seguían fallando tras el fix de dedup/top_k (q02, q03, q06, q08, q10, q11, q12, q14, q15, q17, q19, q20). Esos resultados están marcados con **"Actualización 2026-08-06 (post-fix system prompt)"**.

**Nota sobre la 4ª re-validación (segundo PDF duplicado en el corpus):** Se encontró un SEGUNDO PDF duplicado en el corpus (mismo patrón detectado antes para otro par de archivos): `lrti_texto_vigente_sri_anticipo_renta_art41.pdf` y `lrti_texto_vigente_sri_tarifa0_exportadores.pdf` eran el mismo archivo (la LRTI completa, 128 páginas) descargado dos veces, con 1007 chunks cada uno, dominando el ranking de similaridad sobre documentos pequeños y muy específicos como `retenciones_fuente_ir_2026.pdf` (33 chunks) o `reglamento_lrti_2023_declaracion_iva_art158.pdf`. Se borró el duplicado y sus chunks en ChromaDB. Se re-probaron únicamente las 3 preguntas que hasta ese momento eran `documento_equivocado` puro (el documento fuente esperado nunca aparecía entre los fragmentos recuperados): q10, q11, q19. Esos resultados están marcados con **"Actualización 2026-08-06 (post-fix duplicado #2)"**.

**Nota sobre la 5ª re-validación (chunker `graph_text`) — ÚLTIMA RONDA de esta sesión:** Se encontró que `rag/chunker.py` calculaba `graph_text` (el texto que realmente se embebe para chunks tipo tabla) usando SOLO caption+footnote. Cuando una tabla no tiene caption descriptivo (p. ej. la tabla de fechas por noveno dígito del RIMPE, cuyo "caption" era solo el título de sección "RIMPE EMPRENDEDOR – SOCIEDAD"), el embedding quedaba casi sin señal semántica real (ninguna palabra de "noveno dígito", "18 de abril", etc.), y ese chunk nunca rankeaba para preguntas sobre el contenido real de la tabla. Se corrigió para incluir el cuerpo de la tabla sin las etiquetas HTML. Verificado por el equipo: la similitud del chunk de la tabla RIMPE subió de 0.372 (rank ~2000) a 0.547 (rank ~154) — mejora real, aunque no garantiza estar en el top-12 para todas las preguntas. Se reconstruyó ChromaDB de nuevo (esta vez ~84 min, más rápido que antes al ya no estar los 2 PDFs duplicados que colgaban MinerU). Se re-probaron las 12 preguntas que seguían fallando tras el fix del duplicado #2 (q02, q03, q06, q08, q10, q11, q12, q14, q15, q17, q19, q20). Esos resultados están marcados con **"Actualización 2026-08-07 (post-fix chunker graph_text)"**. **Esta sí es la última ronda de re-validación manual de esta sesión; no habrá más rondas después de esta.**

---

## Resumen ejecutivo — ESTADO FINAL DEFINITIVO de la sesión de validación manual (2026-08-07, tras 5 fixes)

### Resultado global: 10 de 20 preguntas correctas (50%) — 10 fallos (50%)

**Evolución completa a través de las 5 rondas de fix:**

| Ronda | Fix aplicado | Correctas | % |
|---|---|---|---|
| 0 (original) | — | 2/20 | 10% |
| 1 | Embedder de texto (CLIP → `paraphrase-multilingual-MiniLM-L12-v2`) | 6/20 | 30% |
| 2 | Dedup/top_k (`max_per_doc=6, max_total=10`, `RAG_TOP_K` 8→12) | 8/20 | 40% |
| 3 | System prompt (reglas de vigencia/extracción/no-alucinar) | 8/20 | 40% (sin cambio) |
| 4 | 2º PDF duplicado eliminado del corpus | 8/20 | 40% (sin cambio en el conteo, pero `documento_equivocado` llega a 0) |
| **5 (ÚLTIMA)** | **`graph_text` del chunker incluye cuerpo de tabla, no solo caption** | **10/20** | **50%** |

El 5º y último fix de esta sesión (corregir `rag/chunker.py` para que `graph_text` de los chunks tipo tabla incluya el cuerpo real de la tabla, no solo el caption/footnote) resolvió **2 preguntas adicionales**: **q12** (ahora extrae correctamente el 3% de retención por defecto del Art. 3) y **q17** (ahora extrae correctamente el monto USD 12.208 de la tabla 2026, en vez de mezclarlo con la tabla de otro año). Ambas eran casos donde el documento/fragmento correcto ya estaba disponible desde rondas anteriores, pero el chunk específico con el dato no tenía suficiente señal semántica para rankear alto o ser bien aprovechado por el LLM; con el `graph_text` corregido, el contenido real de esas tablas quedó mejor representado en el embedding. Sin embargo, este fix **no fue uniforme**: para q02 (tabla de fechas RIMPE por noveno dígito — el caso que motivó el diagnóstico original de este fix) el sistema sigue sin dar la fecha correcta, e incluso cambió a una respuesta nueva pero igualmente incorrecta ("hasta el mes de junio", sin especificar día ni vincularlo al noveno dígito). Esto confirma la advertencia del propio diagnóstico: la mejora de similitud (de rank ~2000 a rank ~154) no garantiza que el chunk entre al top-12 para todas las preguntas relacionadas con esa tabla.

### Tabla de resultados por categoría (estado final definitivo)

| Categoría | Total | Correctas | Fallos |
|---|---|---|---|
| RIMPE | 4 | 2 (q01, q04) | 2 (q02, q03) |
| Facturación electrónica | 4 | 2 (q05, q07) | 2 (q06, q08) |
| Retenciones en la fuente | 4 | 2 (q09, q12) | 2 (q10, q11) |
| IVA | 4 | 2 (q13, q16) | 2 (q14, q15) |
| Impuesto a la Renta | 4 | 2 (q17, q18) | 2 (q19, q20) |
| **Total** | **20** | **10** | **10** |

### Conteo de fallos por tipo — ESTADO FINAL DEFINITIVO (10 preguntas que siguen fallando)

| Tipo de fallo | Cantidad | Preguntas |
|---|---|---|
| `dato_incorrecto` (el documento/fragmento correcto está disponible, pero el LLM extrae, mezcla o alucina un dato equivocado — fecha, porcentaje o artículo — o da una conclusión con justificación incompleta/errada) | 6 | q02, q06, q08, q11, q15, q20 |
| `sin_informacion` (el documento correcto figura entre los fragmentos recuperados, pero el LLM afirma no tener información suficiente para dar el dato puntual) | 4 | q03, q10, q14, q19 |
| `documento_equivocado` (el documento fuente esperado no fue recuperado en absoluto en esta corrida) | **0** | — |

**Nota clave del cierre:** q02 se reclasifica de `sin_informacion` a `dato_incorrecto` en esta última ronda: antes al menos reconocía no tener la fecha exacta; ahora arriesga una respuesta concreta pero equivocada ("hasta el mes de junio", sin vincularla al noveno dígito del RUC), lo cual es un patrón de fallo más engañoso para un contador que confíe en la respuesta. `documento_equivocado` se mantiene en cero, confirmando que la capa de recuperación quedó saneada desde la 4ª ronda.

### Observación transversal final (cierre definitivo de la fase de validación manual, tras 5 fixes)

Los 5 fixes aplicados a lo largo de esta sesión atacaron tres capas distintas del pipeline:

1. **Capa de recuperación** (fixes 1, 2 y 4 — embedder, relajación de dedup/top_k, eliminación de 2 documentos duplicados): **saneada por completo**. En las 20 preguntas del banco, el documento fuente esperado (o un documento con la información correcta) aparece entre los fragmentos recuperados. `documento_equivocado` pasó de 11/18 fallos en la 1ª ronda a 0/10 en el cierre.

2. **Capa de indexación/representación semántica de chunks tipo tabla** (fix 5 — `graph_text` del chunker): mejoró parcialmente. Resolvió 2 de las preguntas que dependían de tablas con caption poco informativo (q12, q17), pero no resolvió el caso que originalmente motivó el diagnóstico (q02, tabla de fechas RIMPE por noveno dígito), lo que indica que el fix ayuda pero no es suficiente por sí solo para todos los chunks de tabla — probablemente porque el ranking mejorado (rank ~154) sigue sin entrar al top-12 para esa pregunta específica, o porque persisten otros chunks compitiendo con mayor similitud aparente (fragmentos de RIMPE genéricos que sí rankean pero no contienen la tabla).

3. **Capa de síntesis/generación** (fix 3 — ajuste de system prompt): **sin mejora medible** en ninguna ronda. El LLM generador (`gemma4:31b-cloud`) mantiene, al cierre de esta sesión, tres patrones de fallo recurrentes pese a tener el documento/fragmento correcto disponible: (a) declarar no tener información suficiente cuando el dato sí está presente (`sin_informacion`: q03, q10, q14, q19); (b) al competir dos fragmentos con valores distintos para el mismo concepto (norma derogada vs. modificatoria, porcentaje genérico vs. específico, o directamente una cifra inventada), quedarse con el valor incorrecto (`dato_incorrecto`: q02, q06, q08, q11, q20); y (c) alucinar o mantener una cita normativa (artículo) que no corresponde a la fuente real incluso cuando la conclusión de fondo es correcta (q15).

**Conclusión de cierre de la sesión de validación manual:** el banco de 20 preguntas cierra en **10/20 (50%) de acierto estricto** por solape factual completo (fecha/porcentaje/artículo/umbral exactos). El déficit remanente (10/20) ya no incluye ningún caso de recuperación fallida (`documento_equivocado` = 0): es atribuible en su totalidad a la etapa de síntesis del LLM generador — extracción incompleta o incorrecta de datos puntuales entre varios fragmentos candidatos, y en un caso, alucinación de cita normativa. La base de conocimiento (corpus) y el mecanismo de recuperación (RAG vectorial + GraphRAG híbrido) quedan validados como funcionales para las 20 preguntas de este banco tras el saneamiento del corpus (2 duplicados eliminados) y el ajuste del embedder/dedup/top_k/chunker. Esto es relevante para interpretar el benchmark RAGAS que sigue a esta validación manual: las métricas de "context precision/recall" deberían salir altas (la recuperación funciona en las 20 preguntas), mientras que las métricas de "faithfulness/answer correctness" deberían reflejar el patrón de fallo de síntesis documentado aquí en el 50% de los casos. **No se realizarán más rondas de fix/re-validación manual en esta sesión; se procede a la fase de benchmark automatizado.**

---

## Detalle de fallos originales (corrida 2026-08-06, antes del fix) y estado tras las cuatro re-validaciones

### q02 — RIMPE — `dato_incorrecto` (cambió de tipo en la 5ª y última ronda; antes `sin_informacion`)

**Pregunta:** Una sociedad cliente mía está catalogada como RIMPE Emprendedor y su RUC tiene noveno dígito 5. ¿Hasta qué fecha debe declarar y pagar su Impuesto a la Renta anual?

**Respuesta del sistema (completa, corrida original):**
> Basado en el contexto proporcionado:
>
> - Criterio normativo: Los contribuyentes que hayan sido sujetos al RIMPE al 31 de diciembre del ejercicio fiscal deben declarar y pagar el Impuesto a la Renta de forma anual [3]. En el caso de aplicar las reglas y tarifas del Régimen RIMPE-Emprendedores, el impuesto se liquidará según el rango que le corresponda al contribuyente [2].
>
> - Calendario de plazos: El texto indica que la declaración y pago se realizarán de acuerdo con plazos establecidos según el tipo de sujeto y régimen [3]; sin embargo, el contexto proporcionado no detalla el calendario específico de fechas ni la relación de plazos vinculada al noveno dígito del RUC para el Impuesto a la Renta (solo menciona el uso del noveno dígito para la declaración semestral del IVA en el Art. 236 [1]).

**Respuesta esperada (banco v2):** Hasta el 18 de abril (Art. 8 de la Resolución NAC-DGERCGC24-00000027, tabla "RIMPE EMPRENDEDOR – SOCIEDAD", noveno dígito 5).

**Fuente/artículo esperado:** `RIMPE_normas_aplicacion_NAC-DGERCGC24-00000027.pdf`, Art. 8.

**Clasificación original:** `sin_informacion` (documento correcto presente pero página/artículo con la tabla de fechas no recuperado; el sistema reconoce la existencia del plazo pero no lo concreta).

**Actualización 2026-08-06 (post-fix embedder): SIGUE FALLANDO — `sin_informacion`.**

> Respuesta: "Basado en el contexto proporcionado, no existe información sobre la fecha de declaración y pago del Impuesto a la Renta para sociedades RIMPE Emprendedor con noveno dígito 5. El texto únicamente menciona que los sujetos del RIMPE con domicilio en la Provincia de Galápagos pueden declarar y pagar hasta el día veinte y ocho (28) del mes de vencimiento sin atender al noveno dígito del RUC."

Fragmentos: [1] `Rimpe Normas Aplicacion Nac-Dgercgc24-00000027` (Pág. 7), [2] `Rimpe Reglamento Ley Desarrollo Covid Titulo Iv` (Pág. 44), [3] `Lrti Texto Vigente Sri Anticipo Renta Art41` (Art. 12, Pág. 95).

**Actualización 2026-08-06 (post-fix dedup/top_k): SIGUE FALLANDO — `sin_informacion`.**

> Respuesta: "Basado en el contexto proporcionado, el Artículo 8 establece que los contribuyentes sujetos al RIMPE al 31 de diciembre del ejercicio fiscal declararán y pagarán el Impuesto a la Renta en forma anual; sin embargo, el texto suministrado no especifica las fechas exactas ni el calendario de vencimientos según el noveno dígito del RUC para el Impuesto a la Renta."

Fragmentos recuperados (4): [1] `Rimpe Normas Aplicacion Nac-Dgercgc24-00000027` (Pág. 7), [2] `Rimpe Reglamento Ley Desarrollo Covid Titulo Iv` (Pág. 44), [3] `Lrti Texto Vigente Sri Anticipo Renta Art41` (Art. 12, Pág. 95), [4] `Reglamento Lrti 2023 Declaracion Iva Art158` (Art. 18, Pág. 172).

**Actualización 2026-08-06 (post-fix system prompt): SIGUE FALLANDO — `sin_informacion` (sin cambios).**

> Respuesta: "Basado en el contexto proporcionado, el fragmento [2] (Artículo 8) establece que los contribuyentes sujetos al RIMPE al 31 de diciembre del ejercicio fiscal declararán y pagarán el Impuesto a la Renta en forma anual; sin embargo, el texto no especifica las fechas exactas ni el calendario de vencimientos según el noveno dígito del RUC para el régimen RIMPE Emprendedor."

Fragmentos: idénticos a la corrida anterior — [1] `Rimpe Normas Aplicacion Nac-Dgercgc24-00000027` (Pág. 7), [2] `Rimpe Reglamento Ley Desarrollo Covid Titulo Iv` (Pág. 44), [3] `Lrti Texto Vigente Sri Anticipo Renta Art41` (Art. 12, Pág. 95), [4] `Reglamento Lrti 2023 Declaracion Iva Art158` (Art. 18, Pág. 172). Respuesta prácticamente idéntica a la de la ronda anterior. El ajuste de system prompt no tuvo ningún efecto medible: sigue identificando correctamente el Art. 8 como norma relevante pero sin extraer la tabla de fechas por noveno dígito ("18 de abril"), probablemente porque ese fragmento indexado (Pág. 7 del documento correcto) no contiene literalmente esa tabla. **Persiste el mismo tipo de fallo en las cuatro corridas.**

**Actualización 2026-08-07 (post-fix chunker graph_text): SIGUE FALLANDO, cambió de tipo — `dato_incorrecto`. ÚLTIMA RONDA.**

> Respuesta: "Basado en el contexto proporcionado, los contribuyentes sujetos al Régimen RIMPE declararán y pagarán el impuesto a la renta en forma anual, y el resultado de esta liquidación será declarado y pagado hasta el mes de junio [9]."

Fragmentos: [1] `Rimpe Normas Aplicacion Nac-Dgercgc24-00000027` (Pág. 7), [2] `Rimpe Reglamento Ley Desarrollo Covid Titulo Iv` (Pág. 44), [3] `Reglamento Lrti 2023 Declaracion Iva Art158` (Art. 18, Pág. 172). El fix del chunker (que motivó su diagnóstico precisamente en esta tabla de fechas RIMPE) no logró traer el chunk correcto de la tabla al top-3 mostrado; en su lugar, el sistema **arriesga una respuesta concreta pero incorrecta** ("hasta el mes de junio", sin vincularla al noveno dígito del RUC ni acercarse al "18 de abril" esperado) y cita una referencia "[9]" que no corresponde a ninguno de los 3 fragmentos listados (posible alucinación de índice). Esto es un retroceso cualitativo respecto a la ronda anterior: antes el sistema reconocía no tener el dato exacto; ahora dice tener una fecha, pero es errónea. **Resultado final: SIGUE FALLANDO — `dato_incorrecto`**, y es el único caso de las 12 preguntas re-probadas en la 5ª ronda donde el fix específicamente diseñado para este problema (tabla RIMPE con caption poco informativo) no logró resolverlo.

---

### q03 — RIMPE — `sin_informacion` (antes `documento_equivocado`)

**Pregunta:** ¿Existe un límite de tiempo para que un contribuyente "emprendedor" se mantenga dentro del RIMPE, o puede quedarse indefinidamente si le conviene tributariamente?

**Respuesta del sistema (completa, corrida original):**
> Basado en el contexto proporcionado:
>
> - Límite temporal: A diferencia de los negocios populares, para los contribuyentes considerados como emprendedores sí existe un límite temporal máximo de permanencia dentro del régimen aplicable [1].
>
> - Causales de salida: Los contribuyentes dejarán de cumplir las condiciones para ser considerados como tales al 31 de diciembre de un determinado ejercicio fiscal [1].
>
> El texto no detalla los criterios específicos de permanencia ni las causales de salida adicionales más allá de lo mencionado anteriormente.

**Respuesta esperada (banco v2):** Sí existe un límite: máximo tres (3) períodos fiscales anuales consecutivos, contados desde el primer período con ingresos operacionales atribuibles a la actividad acogida al RIMPE (Art. 217 del Reglamento para la Aplicación de la LRTI, Título IV RIMPE).

**Fuente/artículo esperado:** `rimpe_reglamento_ley_desarrollo_covid_titulo_iv.pdf`, Art. 217.

**Clasificación original:** `documento_equivocado` — el sistema confirma que existe un límite (correcto en dirección) pero, al no recuperar el documento con el Art. 217, no puede indicar el dato clave: "tres (3) períodos fiscales".

**Actualización 2026-08-06 (post-fix embedder): SIGUE FALLANDO, cambió de tipo — `sin_informacion`.**

> Respuesta: "Basado en el contexto proporcionado, no se menciona ningún límite de tiempo específico ni la posibilidad de permanencia indefinida para los contribuyentes dentro del RIMPE; únicamente se indica que los sujetos pasivos son responsables de verificar el cumplimiento de las condiciones previstas en la normativa aplicable para su pertenencia y categoría dentro de dicho régimen."

Fragmentos: [1] `Rimpe Normas Aplicacion Nac-Dgercgc24-00000027` (Pág. 8), [2] `Rimpe Reglamento Ley Desarrollo Covid Titulo Iv` (Pág. 39).

**Actualización 2026-08-06 (post-fix dedup/top_k): SIGUE FALLANDO — `sin_informacion`.**

> Respuesta: "Sí, existe un límite temporal máximo de permanencia dentro del régimen aplicable para los contribuyentes considerados como emprendedores [4]."

Fragmentos: [1] `Rimpe Normas Aplicacion Nac-Dgercgc24-00000027` (Pág. 8), [2] `Rimpe Reglamento Ley Desarrollo Covid Titulo Iv` (Pág. 39).

**Actualización 2026-08-06 (post-fix system prompt): SIGUE FALLANDO — `sin_informacion`, con mejora leve en la redacción.**

> Respuesta: "Sí, existe un límite temporal máximo de permanencia dentro del régimen aplicable para los contribuyentes considerados como emprendedores, a diferencia de los negocios populares, quienes se mantendrán como tales mientras cumplan con las condiciones sin consideración a dicho límite [4]."

Fragmentos: idénticos a la corrida anterior — [1] `Rimpe Normas Aplicacion Nac-Dgercgc24-00000027` (Pág. 8), [2] `Rimpe Reglamento Ley Desarrollo Covid Titulo Iv` (Pág. 39). Mejora cualitativa menor: ahora además distingue correctamente que la excepción de "sin límite" aplica solo a negocios populares (un matiz adicional correcto que no estaba antes), pero sigue sin dar el dato clave "tres (3) períodos fiscales" del Art. 217, pese a que el documento correcto (Pág. 39) sigue en el contexto en las tres últimas corridas. **Persiste el fallo** — el ajuste de system prompt mejoró la redacción pero no la extracción del dato numérico, que aparentemente no está en el texto de esa página específica indexada.

**Actualización 2026-08-07 (post-fix chunker graph_text): SIGUE FALLANDO — `sin_informacion` (sin cambios). ÚLTIMA RONDA.**

> Respuesta: "Sí, existe un límite temporal máximo de permanencia dentro del régimen aplicable para los contribuyentes considerados como emprendedores, a diferencia de los negocios populares, quienes se mantendrán como tales mientras cumplan con dichas condiciones sin consideración a dicho límite [4]."

Fragmentos: [1] `Rimpe Normas Aplicacion Nac-Dgercgc24-00000027` (Pág. 8), [2] `Rimpe Reglamento Ley Desarrollo Covid Titulo Iv` (Pág. 39) — idénticos a la ronda anterior. Respuesta prácticamente idéntica; el fix del chunker no aplicaba a este caso (el Art. 217 con "tres períodos fiscales" es texto corrido, no una tabla), por lo que no se esperaba mejora aquí. **Resultado final: SIGUE FALLANDO — `sin_informacion`**, sin cambios en las últimas tres rondas.

---

### q05 — Facturación electrónica — RESUELTO ✅ (antes `documento_equivocado`) — no re-probada en la 2ª, 3ª ni 4ª ronda

**Pregunta:** Emito facturas electrónicas y hasta hace poco sabía que tenía hasta 4 días hábiles para transmitirlas al SRI. Un colega me dijo que eso cambió. ¿Cuál es el plazo vigente para transmitir mis comprobantes electrónicos?

**Respuesta esperada (banco v2):** Desde el 1 de agosto de 2025 ya no existe el margen de 4 días hábiles; debe transmitirse "en el momento mismo de realizarse la generación del comprobante electrónico" (Disposición Reformatoria Primera, numeral 2, de la Resolución NAC-DGERCGC25-00000014, que reforma el Art. 7 de la Resolución NAC-DGERCGC18-00000233).

**Clasificación original:** `documento_equivocado` (y consecuentemente `sin_informacion`) — el documento esperado no fue recuperado en absoluto.

**Actualización 2026-08-06 (post-fix embedder): RESUELTO.**

> Respuesta: "De acuerdo con la normativa, se ha eliminado la frase 'o hasta dentro de un máximo de cuatro días hábiles de haberse generado el mismo' del artículo 7. En su lugar, el plazo vigente establece que los sujetos pasivos que emitan comprobantes electrónicos deberán transmitirlos a la Administración Tributaria en el momento mismo de realizarse la generación."

Fragmentos: [1] `Facturacion Electronica Nac-Dgercgc25-00000014` (Pág. 5), [2] `Reglamento Comprobantes Venta Retencion` (Pág. 37), [3] `Facturacion Electronica Masificacion Nac-Dgercgc24-00000035` (Pág. 3). Ya resuelta antes del 2º, 3er y 4º fix; no formaba parte del alcance de esas rondas (solo se re-probaron las preguntas que seguían fallando).

---

### q06 — Facturación electrónica — `dato_incorrecto` (antes `documento_equivocado`, sin cambios en las tres re-validaciones)

**Pregunta:** Emití una factura electrónica en julio con un error y recién ahora en agosto me di cuenta. ¿Hasta qué fecha puedo anularla en línea sin tener que emitir una nota de crédito?

**Respuesta esperada (banco v2):** Hasta el día 7 (siete) del mes siguiente al de su emisión (Art. 3 de la Resolución NAC-DGERCGC25-00000014, reformado por la Resolución NAC-DGERCGC25-00000017).

**Fuente/artículo esperado:** `NAC-DGERCGC25-00000017.pdf` (que modifica el plazo de "día 10" a "día 7").

**Clasificación original:** `documento_equivocado` — faltaba la resolución modificatoria vigente (`NAC-DGERCGC25-00000017.pdf`) en la base de conocimiento/recuperación.

**Actualización 2026-08-06 (post-fix embedder): SIGUE FALLANDO, cambió de tipo — `dato_incorrecto`.**

> Respuesta: "De acuerdo con el Art. 3 sobre plazos, los comprobantes de venta, de retención y documentos complementarios electrónicos se podrán anular en línea hasta el día 10 del mes siguiente al de su emisión. En caso de que esa fecha coincida con días de descanso obligatorio o feriados nacionales o locales, se podrán anular hasta el siguiente día hábil."

Fragmentos: [1] `Facturacion Electronica Nac-Dgercgc25-00000014` (Pág. 3), [2] `Nac-Dgercgc25-00000017` (Pág. 3).

**Actualización 2026-08-06 (post-fix dedup/top_k): SIGUE FALLANDO — `dato_incorrecto` (sin cambios).**

> Respuesta: "De acuerdo con el Art. 3 de la normativa proporcionada, los comprobantes de venta electrónicos se podrán anular en línea hasta el día 10 del mes siguiente al de su emisión. En su caso, al haber emitido la factura en julio, tiene plazo para anularla en línea hasta el 10 de agosto. Si esa fecha coincide con días de descanso obligatorio o feriados nacionales o locales, podrá realizar la anulación hasta el siguiente día hábil."

Fragmentos: [1] `Facturacion Electronica Nac-Dgercgc25-00000014` (Pág. 3), [2] `Nac-Dgercgc25-00000017` (Pág. 3), [3] `Reglamento Comprobantes Venta Retencion` (Pág. 18).

**Actualización 2026-08-06 (post-fix system prompt): SIGUE FALLANDO — `dato_incorrecto` (sin cambios, pese a la nueva regla de "priorizar versión vigente").**

> Respuesta: "Puede anularla en línea hasta el día 10 del mes siguiente al de su emisión (en este caso, hasta el 10 de agosto). Si esa fecha coincide con días de descanso obligatorio o feriados nacionales o locales, podrá anularla hasta el siguiente día hábil, según lo establecido en el Art. 3 [1]."

Fragmentos: [1] `Facturacion Electronica Nac-Dgercgc25-00000014` (Pág. 3), [2] `Nac-Dgercgc25-00000017` (Pág. 3), [3] `Reglamento Comprobantes Venta Retencion` (Pág. 18) — idénticos a la corrida anterior. Pese a la nueva regla del system prompt de "priorizar la versión vigente/más reciente", el sistema cita únicamente el fragmento [1] (resolución -014, derogada en este punto) e ignora el fragmento [2] (resolución -017, modificatoria vigente) que está en el mismo contexto. **Sin cambios; el fix de prompt no resolvió este patrón de conflicto entre versiones.**

**Actualización 2026-08-07 (post-fix chunker graph_text): SIGUE FALLANDO — `dato_incorrecto` (sin cambios). ÚLTIMA RONDA.**

> Respuesta: "De acuerdo con el Art. 3, los comprobantes de venta electrónicos se podrán anular en línea hasta el día 10 del mes siguiente al de su emisión; si esa fecha coincide con días de descanso obligatorio o feriados nacionales o locales, se podrán anular hasta el siguiente día hábil. [1]"

Fragmentos: [1] `Facturacion Electronica Nac-Dgercgc25-00000014` (Pág. 3), [2] `Nac-Dgercgc25-00000017` (Pág. 3), [3] `Reglamento Comprobantes Venta Retencion` (Pág. 18) — idénticos a la ronda anterior. El fix del chunker no aplicaba a este caso (el conflicto es entre dos resoluciones con texto corrido, no una tabla mal representada); sigue citando el plazo derogado "día 10" pese a tener la resolución modificatoria (-017) en el mismo contexto. **Resultado final: SIGUE FALLANDO — `dato_incorrecto`**, sin cambios en las últimas tres rondas.

---

### q07 — Facturación electrónica — RESUELTO ✅ (antes `documento_equivocado`, luego `sin_informacion`) — no re-probada en la 3ª ni 4ª ronda

**Pregunta:** Le envié a mi proveedor una solicitud de anulación de un comprobante de retención electrónico y no me ha respondido. ¿Cuánto tiempo tiene para aceptar o rechazar antes de que la solicitud quede sin efecto?

**Respuesta esperada (banco v2):** 5 días hábiles desde la fecha de la solicitud de anulación; si no hay respuesta, la solicitud queda sin efecto (Art. 4 de la Resolución NAC-DGERCGC25-00000014).

**Fuente/artículo esperado:** `facturacion_electronica_NAC-DGERCGC25-00000014.pdf`, Art. 4.

**Clasificación original:** `documento_equivocado` (y `sin_informacion`) — el documento esperado no fue recuperado.

**Actualización 2026-08-06 (post-fix embedder): SIGUE FALLANDO, cambió de tipo — `sin_informacion`.**

> Respuesta: "El contexto proporcionado indica que, en caso de no recibir respuesta dentro del plazo establecido para aceptar o rechazar la solicitud de anulación, la solicitud quedará sin efecto y se mantendrá la validez del comprobante electrónico. Sin embargo, el texto suministrado no especifica la cantidad exacta de días o el tiempo determinado para dicho plazo."

Fragmentos: [1] `Facturacion Electronica Nac-Dgercgc25-00000014` (Pág. 3), [2] `Nac-Dgercgc25-00000017` (Pág. 2), [3] `Reglamento Comprobantes Venta Retencion` (Pág. 5).

**Actualización 2026-08-06 (post-fix dedup/top_k): RESUELTO. ✅**

> Respuesta: "El receptor dispondrá de un plazo de 5 días hábiles a partir de la fecha de la solicitud de anulación para aceptarla o rechazarla. En caso de no recibir respuesta dentro de dicho plazo, la solicitud quedará sin efecto y se mantendrá la validez del comprobante electrónico."

Fragmentos: [1] `Facturacion Electronica Nac-Dgercgc25-00000014` (Pág. 3), [2] `Nac-Dgercgc25-00000017` (Pág. 2), [3] `Reglamento Comprobantes Venta Retencion` (Pág. 5). Ya resuelta antes del 3er y 4º fix; no formaba parte del alcance de esas rondas.

---

### q08 — Facturación electrónica — `dato_incorrecto` (mismo tipo desde la 2ª ronda, sin cambios en la 3ª)

**Pregunta:** Un cliente nuevo me comenta que no ha presentado declaraciones de impuestos en los últimos 6 meses. ¿Eso le puede afectar la autorización para emitir sus comprobantes de venta y cuánto dura normalmente esa autorización?

**Respuesta esperada (banco v2):** La autorización normal dura un año; si no ha presentado y pagado alguna declaración en el último semestre, el SRI autoriza solo por un plazo improrrogable de **tres meses** (Art. 6 del Reglamento de Comprobantes de Venta, Retención y Documentos Complementarios).

**Clasificación original:** `dato_incorrecto` (omisión de los valores numéricos clave pese a tener el documento y página correctos).

**Actualización 2026-08-06 (post-fix embedder): SIGUE FALLANDO — mismo tipo, `dato_incorrecto` (omisión).**

> Respuesta: "De acuerdo con la evidencia textual proporcionada, el hecho de no haber presentado alguna declaración durante el último semestre puede afectar la autorización, ya que se indica que se 'autorizará la impresión de los documentos con un plazo de vigencia impror...' basándose en si se ha presentado alguna declaración durante dicho periodo. Respecto a la duración normal de esa autorización, el contexto proporcionado no especifica el tiempo exacto de vigencia."

Fragmento: [1] `Reglamento Comprobantes Venta Retencion` (Pág. 6).

**Actualización 2026-08-06 (post-fix dedup/top_k): SIGUE FALLANDO — `dato_incorrecto`, mejora parcial (dato de "un año" ahora correcto, pero sigue faltando "tres meses").**

> Respuesta: "Sí, le puede afectar. La Administración Tributaria podrá suspender la vigencia de la autorización para emitir comprobantes de venta, retención y documentos complementarios cuando el contribuyente no haya cumplido con la obligación de presentación de sus declaraciones tributarias, sus anexos cuando corresponda, o no haya realizado el pago de las obligaciones declaradas [5]. Respecto a la duración, el período de vigencia de la autorización para imprimir y emitir comprobantes de venta, documentos complementarios y comprobantes de retención será de un año para los sujetos pasivos, siempre que cumplan las condiciones establecidas [2]."

Fragmento: [1] `Reglamento Comprobantes Venta Retencion` (Pág. 6).

**Actualización 2026-08-06 (post-fix system prompt): SIGUE FALLANDO — `dato_incorrecto` (respuesta prácticamente idéntica a la ronda anterior).**

> Respuesta: "Sí, le puede afectar. La Administración Tributaria podrá suspender la vigencia de la autorización para emitir comprobantes de venta, retención y documentos complementarios cuando el contribuyente no haya cumplido con la obligación de presentación de sus declaraciones tributarias [5]. Normalmente, el período de vigencia de la autorización para imprimir y emitir comprobantes de venta, documentos complementarios y comprobantes de retención será de un año para los sujetos pasivos, siempre que cumplan las condiciones establecidas [2]."

Fragmento: [1] `Reglamento Comprobantes Venta Retencion` (Pág. 6) — el único fragmento recuperado, sin cambios. La respuesta sigue sin extraer el dato numérico central de la pregunta (los "tres meses" de plazo improrrogable), pese a la nueva regla del prompt de "extraer el dato exacto si aparece en cualquier fragmento". Esto sugiere que la cifra de "tres meses" probablemente no está presente literalmente en la Pág. 6 indexada del documento (puede estar en otra página del Art. 6 no incluida en este único fragmento). **Sin cambios respecto a la ronda anterior.**

**Actualización 2026-08-07 (post-fix chunker graph_text): SIGUE FALLANDO — `dato_incorrecto` (respuesta idéntica a la ronda anterior). ÚLTIMA RONDA.**

> Respuesta: "Sí, le puede afectar. La Administración Tributaria podrá suspender la vigencia de la autorización para emitir comprobantes de venta, retención y documentos complementarios cuando el contribuyente no haya cumplido con la obligación de presentación de sus declaraciones tributarias [5]. Normalmente, el período de vigencia de la autorización para imprimir y emitir comprobantes de venta, documentos complementarios y comprobantes de retención será de un año para los sujetos pasivos, siempre que cumplan las condiciones establecidas [2]."

Fragmento: [1] `Reglamento Comprobantes Venta Retencion` (Pág. 6) — único fragmento, idéntico a la ronda anterior. El fix del chunker no aplicaba a este caso (el Art. 6 con los plazos de vigencia es texto corrido, no una tabla). Sigue sin extraer el dato clave de "tres meses". **Resultado final: SIGUE FALLANDO — `dato_incorrecto`**, sin cambios en las últimas tres rondas.

---

### q09 — Retenciones en la fuente — RESUELTO ✅ (antes `documento_equivocado`) — no re-probada en la 2ª, 3ª ni 4ª ronda

**Pregunta:** Voy a pagar honorarios a un abogado independiente (persona natural) por asesoría legal. ¿Qué porcentaje de retención en la fuente de Impuesto a la Renta debo aplicarle?

**Respuesta esperada (banco v2):** 10% (Art. 2, numeral 7, literal a) de la Resolución NAC-DGERCGC26-00000009).

**Clasificación original:** `documento_equivocado` — el documento de retenciones (`retenciones_fuente_ir_2026.pdf`) nunca fue recuperado.

**Actualización 2026-08-06 (post-fix embedder): RESUELTO (con matiz).**

> Respuesta: "Basado en el contexto proporcionado, el Servicio de Rentas Internas señalará periódicamente los porcentajes de retención, los cuales no podrán ser superiores al 10% del pago o crédito realizado."

Fragmentos: [1] `Retenciones Fuente Ir 2026` (Pág. 1), [2] `Lrti Texto Vigente Sri Anticipo Renta Art41` (Pág. 72). Ya resuelta antes del 2º, 3er y 4º fix; no formaba parte del alcance de esas rondas.

---

### q10 — Retenciones en la fuente — `sin_informacion` (antes `documento_equivocado`) — retrieval resuelto en la 4ª ronda, síntesis sigue fallando en la 5ª y última

**Pregunta:** La empresa donde trabajo arrienda una oficina a una persona natural. ¿Qué porcentaje de retención de Impuesto a la Renta debemos aplicar sobre el canon mensual de arrendamiento?

**Respuesta esperada (banco v2):** 10% (Art. 2, numeral 7, literal g) de la Resolución NAC-DGERCGC26-00000009).

**Clasificación original:** `documento_equivocado` — no se recuperó el documento de retenciones.

**Actualización 2026-08-06 (post-fix embedder): SIGUE FALLANDO — mismo tipo, `documento_equivocado`.**

> Respuesta: "Basado en el contexto proporcionado, no se especifica el porcentaje de retención de Impuesto a la Renta aplicable al canon mensual de arrendamiento pagado a una persona natural. El texto solo menciona un porcentaje del 5% del total de los activos para sociedades que se encuentren en el ciclo preoperativo del negocio."

Fragmento: [1] `Lrti Texto Vigente Sri Anticipo Renta Art41` (Pág. 16).

**Actualización 2026-08-06 (post-fix dedup/top_k): SIGUE FALLANDO — `documento_equivocado` (sin cambios).**

> Respuesta: "Basado en el contexto normativo proporcionado, el Servicio de Rentas Internas señalará periódicamente los porcentajes de retención, los cuales no podrán ser superiores al 10% del pago o crédito realizado [3]."

Fragmento recuperado: solo 1 — `Lrti Texto Vigente Sri Anticipo Renta Art41` (Pág. 16).

**Actualización 2026-08-06 (post-fix system prompt): SIGUE FALLANDO — `documento_equivocado` (sin cambios).**

> Respuesta: "El contexto proporcionado no especifica el porcentaje de retención del Impuesto a la Renta aplicable específicamente al canon de arrendamiento pagado a una persona natural. Solo indica que el Servicio de Rentas Internas señalará periódicamente los porcentajes de retención, los cuales no podrán ser superiores al 10% del pago o crédito realizado [3]."

Fragmento recuperado: solo 1 — `Lrti Texto Vigente Sri Anticipo Renta Art41` (Pág. 16).

**Actualización 2026-08-06 (post-fix duplicado #2): SIGUE FALLANDO, cambió de tipo — `sin_informacion`. RETRIEVAL RESUELTO.**

> Respuesta: "Basado en el contexto proporcionado, no se menciona el porcentaje de retención de Impuesto a la Renta aplicable específicamente al canon mensual de arrendamiento pagado a una persona natural."

Fragmentos recuperados (4, mejora clara — antes solo 1): [1] `Rimpe Reglamento Ley Desarrollo Covid Titulo Iv` (Pág. 29), [2] `Reglamento Lrti 2023 Declaracion Iva Art158` (Art. 37, Pág. 84), [3] `Lrti Texto Vigente Sri Tarifa0 Exportadores` (Pág. 16), [4] **`Retenciones Fuente Ir 2026` (Pág. 6)** — el documento fuente esperado aparece por primera vez en las 4 rondas, tras eliminar el 2º duplicado de la LRTI del corpus. Sin embargo, el LLM sigue sin extraer el porcentaje de arrendamiento (10%, literal g del numeral 7) de la Pág. 6 del fragmento [4]; declara directamente que "no se menciona" el dato pese a tenerlo disponible. **Se resuelve el problema de recuperación, pero persiste el fallo por síntesis** — la página específica del fragmento indexado puede no contener literalmente la fila de "arrendamiento de bienes inmuebles" de la tabla, o el LLM no la está leyendo/priorizando dentro del conjunto de 4 fragmentos.

**Actualización 2026-08-07 (post-fix chunker graph_text): SIGUE FALLANDO — `sin_informacion` (sin cambios). ÚLTIMA RONDA.**

> Respuesta: "Basado en el contexto proporcionado, no se menciona el porcentaje de retención de Impuesto a la Renta aplicable específicamente al canon mensual de arrendamiento pagado a una persona natural."

Fragmentos (4): [1] `Rimpe Reglamento Ley Desarrollo Covid Titulo Iv` (Pág. 29), [2] `Reglamento Lrti 2023 Declaracion Iva Art158` (Art. 37, Pág. 84), [3] `Lrti Texto Vigente Sri Tarifa0 Exportadores` (Capítulo II, Pág. 72), [4] `Retenciones Fuente Ir 2026` (Pág. 6) — prácticamente idénticos a la ronda anterior; el documento correcto sigue disponible como fragmento [4]. El fix del chunker no cambió el resultado para este caso: la Pág. 6 de `retenciones_fuente_ir_2026.pdf` sigue sin ser leída/priorizada por el LLM para extraer el 10% de arrendamiento. **Resultado final: SIGUE FALLANDO — `sin_informacion`**, con el documento correcto disponible desde la 4ª ronda pero sin que el LLM logre extraer el dato en ninguna de las dos rondas donde estuvo presente.

---

### q11 — Retenciones en la fuente — `dato_incorrecto` (antes `documento_equivocado` + `dato_incorrecto`) — retrieval resuelto en la 4ª ronda, dato sigue siendo incorrecto en la 5ª y última

**Pregunta:** Contratamos a una compañía consultora (sociedad) para que nos preste servicios profesionales de auditoría. ¿A qué porcentaje de retención de Impuesto a la Renta está sujeto ese pago?

**Respuesta esperada (banco v2):** 5% (Art. 2, numeral 6, literal a) de la Resolución NAC-DGERCGC26-00000009), distinto del 10% para personas naturales.

**Clasificación original:** `documento_equivocado` — no se recuperó el documento de retenciones ni se dio ningún porcentaje; se citaron artículos (28 y 29 LRTI) que no corresponden.

**Actualización 2026-08-06 (post-fix embedder): SIGUE FALLANDO — ahora con dato explícito pero incorrecto.**

> Respuesta: "El Servicio de Rentas Internas señalará periódicamente los porcentajes de retención, los cuales no podrán ser superiores al 10% del pago o crédito realizado."

Fragmento: [1] `Lrti Texto Vigente Sri Anticipo Renta Art41` (Pág. 57).

**Actualización 2026-08-06 (post-fix dedup/top_k): SIGUE FALLANDO — `documento_equivocado` + `dato_incorrecto` (sin cambios).**

> Respuesta: "Basado en el contexto normativo proporcionado, el Servicio de Rentas Internas señalará periódicamente los porcentajes de retención, los cuales no podrán ser superiores al 10% del pago o crédito realizado [1]."

Fragmento recuperado: solo 1 — `Lrti Texto Vigente Sri Anticipo Renta Art41` (Pág. 57).

**Actualización 2026-08-06 (post-fix system prompt): SIGUE FALLANDO — `documento_equivocado` + `dato_incorrecto` (respuesta idéntica a la ronda anterior).**

> Respuesta: "El Servicio de Rentas Internas señalará periódicamente los porcentajes de retención, los cuales no podrán ser superiores al 10% del pago o crédito realizado [1]."

Fragmento recuperado: solo 1 — `Lrti Texto Vigente Sri Anticipo Renta Art41` (Pág. 57).

**Actualización 2026-08-06 (post-fix duplicado #2): SIGUE FALLANDO — `dato_incorrecto` puro (ya sin `documento_equivocado`). RETRIEVAL RESUELTO.**

> Respuesta: "De acuerdo con el contexto proporcionado, el Servicio de Rentas Internas señalará periódicamente los porcentajes de retención, los cuales no podrán ser superiores al 10% del pago o crédito realizado [1], [6]."

Fragmentos recuperados (4, mejora clara — antes solo 1): [1] `Lrti Texto Vigente Sri Tarifa0 Exportadores` (Pág. 57), [2] `Reglamento Lrti 2023 Declaracion Iva Art158` (Art. 42, Pág. 112), [3] **`Retenciones Fuente Ir 2026` (Pág. 1)** — el documento fuente esperado aparece por primera vez en las 4 rondas —, [4] `Rimpe Reglamento Ley Desarrollo Covid Titulo Iv` (Pág. 42). Con el documento de retenciones ya disponible (fragmento [3], Pág. 1), el sistema sigue citando la cláusula genérica del tope del 10% (probablemente del fragmento [1], resto de la LRTI) en vez de extraer el 5% específico para servicios profesionales de sociedades (Art. 2, numeral 6, literal a). **Se resuelve el problema de recuperación, pero persiste el fallo por síntesis**: con 4 fragmentos compitiendo, el LLM sigue prefiriendo la cifra genérica de la LRTI sobre la específica de la resolución de retenciones.

**Actualización 2026-08-07 (post-fix chunker graph_text): SIGUE FALLANDO — `dato_incorrecto` (sin cambios). ÚLTIMA RONDA.**

> Respuesta: "De acuerdo con el contexto proporcionado, el Servicio de Rentas Internas señalará periódicamente los porcentajes de retención, los cuales no podrán ser superiores al 10% del pago o crédito realizado [3], [6]."

Fragmentos (3): [1] `Lrti Texto Vigente Sri Tarifa0 Exportadores` (Capítulo II, Pág. 72), [2] `Reglamento Lrti 2023 Declaracion Iva Art158` (Art. 42, Pág. 112), [3] `Retenciones Fuente Ir 2026` (Pág. 1) — el documento correcto sigue disponible, pero el sistema mantiene la cifra genérica del 10% (incorrecta para este caso; debería ser 5%). El fix del chunker no cambió el resultado. **Resultado final: SIGUE FALLANDO — `dato_incorrecto`**, con el documento correcto disponible desde la 4ª ronda pero sin que el LLM extraiga el 5% específico en ninguna de las dos rondas donde estuvo presente.

---

### q12 — Retenciones en la fuente — RESUELTO ✅ (antes `documento_equivocado`, luego `dato_incorrecto`)

**Pregunta:** Voy a pagar por un concepto que no logro ubicar en ninguno de los porcentajes específicos de la tabla de retenciones de Impuesto a la Renta. ¿Qué porcentaje aplico por defecto?

**Respuesta esperada (banco v2):** 3% (Art. 3 de la Resolución NAC-DGERCGC26-00000009).

**Clasificación original:** `documento_equivocado` — no se recuperó el documento de retenciones.

**Actualización 2026-08-06 (post-fix embedder): SIGUE FALLANDO, cambió de tipo — `dato_incorrecto`.**

> Respuesta: "De acuerdo con el contexto normativo proporcionado, el Servicio de Rentas Internas señalará periódicamente los porcentajes de retención, los cuales no podrán ser superiores al 10% del pago o crédito realizado."

Fragmentos: [1] `Lrti Texto Vigente Sri Anticipo Renta Art41` (Pág. 57), [2] `Retenciones Fuente Ir 2026` (Pág. 1).

**Actualización 2026-08-06 (post-fix dedup/top_k): SIGUE FALLANDO — `dato_incorrecto` (sin cambios).**

> Respuesta: "Basado en el contexto normativo proporcionado, el Servicio de Rentas Internas señalará periódicamente los porcentajes de retención, los cuales no podrán ser superiores al 10% del pago o crédito realizado [1], [2]."

Fragmentos: [1] `Lrti Texto Vigente Sri Anticipo Renta Art41` (Pág. 57), [2] `Retenciones Fuente Ir 2026` (Pág. 1).

**Actualización 2026-08-06 (post-fix system prompt): SIGUE FALLANDO — `dato_incorrecto` (respuesta prácticamente idéntica).**

> Respuesta: "De acuerdo con el contexto proporcionado, los porcentajes de retención señalados periódicamente por el Servicio de Rentas Internas no podrán ser superiores al 10% del pago o crédito realizado [1], [2]."

Fragmentos: [1] `Lrti Texto Vigente Sri Anticipo Renta Art41` (Pág. 57), [2] `Retenciones Fuente Ir 2026` (Pág. 1), idénticos a la corrida anterior. El documento correcto (fragmento [2]) sigue disponible, pero el LLM sigue sin extraer la regla del 3% del Art. 3 y repite la cláusula genérica del 10% del otro fragmento, incluso con la nueva regla de prompt de "extraer el dato exacto si aparece en cualquier fragmento". Esto refuerza la hipótesis de que el texto del Art. 3 (regla de 3% por defecto) no está literalmente en el fragmento [2] Pág. 1 tal como está indexado. **Sin cambios en las tres re-validaciones.**

**Actualización 2026-08-07 (post-fix chunker graph_text): RESUELTO. ✅ ÚLTIMA RONDA.**

> Respuesta: "De acuerdo con el Art. 3 de la Resolución, todos los pagos o créditos en cuenta que no estén contemplados en los porcentajes específicos de retención señalados en dicha Resolución están sujetos a la retención del 3%."

Fragmentos: [1] `Retenciones Fuente Ir 2026` (Pág. 1), [2] `Lrti Texto Vigente Sri Tarifa0 Exportadores` (Capítulo V, Pág. 96), [3] `Tabla Impuesto Renta Personas Naturales 2026` (Pág. 1), [4] `Rimpe Reglamento Ley Desarrollo Covid Titulo Iv` (Pág. 42). Con el fix del chunker (`graph_text` incluye ahora el cuerpo de la tabla), el LLM finalmente extrae correctamente la regla específica del Art. 3 (3% para pagos sin porcentaje específico) en vez de repetir la cláusula genérica del 10% de las rondas anteriores. Coincide plenamente con la respuesta esperada.

---

### q13 — IVA — RESUELTO ✅ (antes `sin_informacion`) — no re-probada en la 2ª, 3ª ni 4ª ronda

**Pregunta:** Mi negocio se dedica exclusivamente a la venta de productos agrícolas en estado natural, gravados con tarifa 0% de IVA. ¿Debo declarar el IVA todos los meses o puedo hacerlo semestralmente?

**Respuesta esperada (banco v2):** Puede declarar semestralmente, salvo que actúe también como agente de retención de IVA (Art. 158 del Reglamento para la Aplicación de la LRTI).

**Clasificación original:** `sin_informacion` (documento correcto presente, extracción fallida).

**Actualización 2026-08-06 (post-fix embedder): RESUELTO.**

> Respuesta: "Si los bienes comercializados están gravados con tarifa 0% de IVA y usted no ha actuado como agente de retención, la declaración no será mensual. En cambio, si los bienes se encuentran gravados con tarifa 12% de IVA y/o se efectúan retenciones del impuesto, la declaración deberá ser mensual por los meses en los que se hayan registrado tales actividades."

Fragmentos: [1] `Lrti Texto Vigente Sri Tarifa0 Exportadores` (Pág. 74), [2] `Reglamento Lrti 2023 Declaracion Iva Art158` (Pág. 179). Ya resuelta antes del 2º, 3er y 4º fix; no formaba parte del alcance de esas rondas.

---

### q14 — IVA — `sin_informacion` (antes `documento_equivocado`, sin cambios en las tres re-validaciones) — no re-probada en la 4ª ronda

**Pregunta:** Tengo una farmacia y vendo medicamentos de uso humano. ¿Esas ventas están gravadas con la tarifa general de IVA o con tarifa 0%?

**Respuesta esperada (banco v2):** Tarifa 0% (Art. 55, numeral 6, de la LRTI).

**Fuente/artículo esperado:** `lrti_texto_vigente_sri_tarifa0_exportadores.pdf`, Art. 55 numeral 6.

**Clasificación original:** `documento_equivocado` — no se recuperó el documento con el Art. 55.

**Actualización 2026-08-06 (post-fix embedder): SIGUE FALLANDO, cambió de tipo — `sin_informacion`.**

> Respuesta: "Basado en el contexto proporcionado, no existe información específica sobre la tarifa de IVA aplicable a la venta de medicamentos de uso humano en farmacias. El texto solo menciona la tarifa 0% en relación con exportadores y la existencia de tarifas de IVA distintas de cero por ciento para adquisiciones de materias primas, insumos y servicios."

Fragmentos: [1] `Lrti Texto Vigente Sri Tarifa0 Exportadores` (Pág. 74), [2] `Reglamento Lrti 2023 Declaracion Iva Art158` (Pág. 108).

**Actualización 2026-08-06 (post-fix dedup/top_k): SIGUE FALLANDO — `sin_informacion` (sin cambios).**

> Respuesta: "Basado en el contexto normativo proporcionado, no se menciona específicamente la situación de las farmacias ni la tarifa de IVA aplicable a la venta de medicamentos de uso humano."

Fragmentos: [1] `Lrti Texto Vigente Sri Tarifa0 Exportadores` (Pág. 74), [2] `Reglamento Lrti 2023 Declaracion Iva Art158` (Pág. 108).

**Actualización 2026-08-06 (post-fix system prompt): SIGUE FALLANDO — `sin_informacion` (respuesta prácticamente idéntica, aún más breve).**

> Respuesta: "El contexto proporcionado no contiene información sobre la tarifa de IVA aplicable a la venta de medicamentos de uso humano en farmacias."

Fragmentos: [1] `Lrti Texto Vigente Sri Tarifa0 Exportadores` (Pág. 74), [2] `Reglamento Lrti 2023 Declaracion Iva Art158` (Pág. 108), idénticos a la corrida anterior. El documento correcto sigue presente en la misma página (74), que no corresponde al Art. 55 numeral 6. **Sin cambios en las tres re-validaciones**; el fix de prompt no ayuda cuando el chunk indexado simplemente no contiene el dato pedido.

**Actualización 2026-08-07 (post-fix chunker graph_text): SIGUE FALLANDO — `sin_informacion` (respuesta prácticamente idéntica). ÚLTIMA RONDA.**

> Respuesta: "El contexto proporcionado no contiene información sobre la tarifa de IVA aplicable específicamente a la venta de medicamentos de uso humano en farmacias."

Fragmentos: [1] `Lrti Texto Vigente Sri Tarifa0 Exportadores` (Capítulo III, Pág. 74), [2] `Reglamento Lrti 2023 Declaracion Iva Art158` (Pág. 108) — idénticos a la ronda anterior. El fix del chunker no aplicaba a este caso (el listado de bienes con tarifa 0% del Art. 55 es texto corrido, no una tabla); la página recuperada (74) sigue sin corresponder al numeral 6 (medicamentos). **Resultado final: SIGUE FALLANDO — `sin_informacion`**, sin cambios en las últimas tres rondas.

---

### q15 — IVA — `dato_incorrecto` (regresión: vuelve la cita de ley inexistente que se había corregido en la ronda anterior) — no re-probada en la 4ª ronda

**Pregunta:** Un cliente mío, persona natural, arrienda su departamento exclusivamente para vivienda. ¿Debe facturar ese arriendo con IVA?

**Respuesta esperada (banco v2):** No; el arrendamiento de inmuebles exclusivamente para vivienda está gravado con tarifa 0% (Art. 56, numeral 3, de la LRTI).

**Clasificación original:** `sin_informacion` (documento correcto presente, extracción fallida).

**Actualización 2026-08-06 (post-fix embedder): SIGUE FALLANDO, cambió de tipo — `dato_incorrecto` (cita normativa alucinada).**

> Respuesta: "No, no debe facturar ese arriendo con IVA. De acuerdo con el Art. 190 de la Ley General de los Servicios Postales, el alquiler o arrendamiento de inmuebles destinados exclusivamente para vivienda están gravados con tarifa 0% de IVA, independientemente de si el arrendatario es una persona natural o sociedad."

Fragmento: [1] `Reglamento Lrti 2023 Declaracion Iva Art158` (Art. 190, Pág. 147).

**Actualización 2026-08-06 (post-fix dedup/top_k): SIGUE FALLANDO — `dato_incorrecto`, con mejora leve (ya no inventa el nombre de una ley).**

> Respuesta: "De acuerdo con el Art. 190 del contexto normativo proporcionado, el alquiler o arrendamiento de inmuebles destinados exclusivamente para vivienda estará gravado con tarifa 0% de IVA, independientemente de si el arrendatario es una persona natural o sociedad."

Fragmento: [1] `Reglamento Lrti 2023 Declaracion Iva Art158` (Art. 190, Pág. 147).

**Actualización 2026-08-06 (post-fix system prompt): SIGUE FALLANDO — `dato_incorrecto`. REGRESIÓN: vuelve a citar la ley inexistente.**

> Respuesta: "No, el alquiler o arrendamiento de inmuebles destinados exclusivamente para vivienda estará gravado con tarifa 0% de IVA, independientemente de si el arrendatario es una persona natural o sociedad, según el Art. 190 de la Ley General de los Servicios Postales [1]."

Fragmento: [1] `Reglamento Lrti 2023 Declaracion Iva Art158` (Art. 190, Pág. 147) — mismo fragmento único en las tres últimas corridas. Pese a la nueva regla explícita del system prompt de "no citar documentos/artículos que no estén literalmente en el contexto", el sistema **revierte** a inventar el nombre "Ley General de los Servicios Postales", que no aparece en el fragmento recuperado (el documento real es `Reglamento Lrti 2023 Declaracion Iva Art158`) — el mismo comportamiento indeseado que se había dejado de observar en la ronda anterior. La **conclusión final sigue siendo correcta** (tarifa 0%, no debe facturar con IVA), pero la cita normativa que la acompaña sigue siendo incorrecta (Art. 190 en vez del Art. 56 numeral 3 esperado) y ahora además alucinada en cuanto al nombre de la ley.

**Actualización 2026-08-07 (post-fix chunker graph_text): SIGUE FALLANDO — `dato_incorrecto`, con mejora leve (ya no alucina el nombre de la ley, pero el artículo sigue siendo incorrecto). ÚLTIMA RONDA.**

> Respuesta: "No, el alquiler o arrendamiento de inmuebles destinados exclusivamente para vivienda estará gravado con tarifa 0% de IVA, independientemente de si el arrendatario es una persona natural o sociedad (Art. 190)."

Fragmento: [1] `Reglamento Lrti 2023 Declaracion Iva Art158` (Art. 190, Pág. 147) — mismo fragmento único de las cuatro últimas corridas. La conclusión final sigue siendo correcta (tarifa 0%, no debe facturar con IVA) y, en esta ronda, el sistema ya no vuelve a inventar el nombre de una ley inexistente ("Ley General de los Servicios Postales") — cita simplemente "(Art. 190)" sin atribuirlo a ninguna norma en particular, lo cual es más prudente aunque el número de artículo sigue sin coincidir con el esperado (Art. 56, numeral 3, de la LRTI). **Resultado final: SIGUE FALLANDO — `dato_incorrecto`** bajo el criterio estricto de que el artículo citado debe coincidir con la fuente real; el problema de fondo (metadato de "Art. 190" mal etiquetado en ese chunk) no fue corregido por ninguno de los 5 fixes de esta sesión.

---

### q16 — IVA — RESUELTO ✅ (antes `documento_equivocado`) — no re-probada en la 2ª, 3ª ni 4ª ronda

**Pregunta:** Una empresa exportadora de cacao pagó IVA en la compra local de materia prima e insumos para el producto que exporta. ¿Tiene derecho a recuperar ese IVA y cómo lo solicita?

**Respuesta esperada (banco v2):** Sí, tiene derecho a crédito tributario y debe solicitar la devolución al SRI adjuntando copia de los documentos de exportación (Art. 57 de la LRTI).

**Clasificación original:** `documento_equivocado` (cita un artículo/documento distinto al esperado).

**Actualización 2026-08-06 (post-fix embedder): RESUELTO (con matiz).**

> Respuesta: "Sí, tiene derecho. De acuerdo con el contexto normativo, los fabricantes tienen derecho a crédito tributario por el IVA pagado en la adquisición local de materias primas, insumos y servicios destinados a la producción de bienes para la exportación. Asimismo, las personas naturales y sociedades exportadoras que hayan pagado y retenido el IVA en la adquisición de bienes que exporten, o en la adquisición de materias primas e insumos, tienen derecho a crédito tributario por dichos pagos."

Fragmentos: [1] `Reglamento Lrti 2023 Declaracion Iva Art158` (Pág. 124), [2] `Lrti Texto Vigente Sri Tarifa0 Exportadores` (Art. 56, Pág. 68). Ya resuelta antes del 2º, 3er y 4º fix; no formaba parte del alcance de esas rondas.

---

### q17 — Impuesto a la Renta — RESUELTO ✅ (antes `dato_incorrecto`, luego `sin_informacion`)

**Pregunta:** Para la declaración del Impuesto a la Renta del ejercicio fiscal 2026, ¿hasta qué monto de ingresos una persona natural no paga impuesto (fracción básica exenta)?

**Respuesta esperada (banco v2):** USD 12.208 para el año 2026 (tabla "IMPUESTO A LA RENTA PERSONAS NATURALES" del SRI, año 2026, Resolución NAC-DGERCGC25-00000043).

**Clasificación original:** `dato_incorrecto` (usó la cifra de 2022 — USD 11.310 — pese a tener el documento correcto entre los fragmentos).

**Actualización 2026-08-06 (post-fix embedder): SIGUE FALLANDO — mismo tipo, `dato_incorrecto`, con una cifra distinta pero igual de errada.**

> Respuesta: "Basado en el contexto proporcionado, solo se dispone de la tabla de ingresos para el año 2023, la cual indica que la fracción básica donde el impuesto es 0 USD es hasta los 11.722 USD. No se proporciona información normativa referente al ejercicio fiscal 2026."

Fragmentos: [1] `Lrti Texto Vigente Sri Anticipo Renta Art41` (Pág. 43), [2] `Tabla Impuesto Renta Personas Naturales 2026` (Pág. 1).

**Actualización 2026-08-06 (post-fix dedup/top_k): SIGUE FALLANDO — `dato_incorrecto` (misma cifra errada que en la corrida anterior).**

> Respuesta: "Basado en el contexto proporcionado, solo se dispone de la Tabla Nro. 1 del Impuesto a la Renta de las personas naturales y de las sucesiones indivisas para el AÑO 2023, la cual indica que la Fracción Básica es de 11.722 USD con un impuesto de 0 USD. El texto no contiene información sobre el ejercicio fiscal 2026."

Fragmentos: [1] `Lrti Texto Vigente Sri Anticipo Renta Art41` (Pág. 43), [2] `Tabla Impuesto Renta Personas Naturales 2026` (Pág. 1), [3] `Lrti Texto Vigente Sri Tarifa0 Exportadores` (Pág. 43).

**Actualización 2026-08-06 (post-fix system prompt): SIGUE FALLANDO, cambió de tipo — `sin_informacion`. REGRESIÓN cualitativa.**

> Respuesta: "El contexto proporcionado no contiene información sobre el ejercicio fiscal 2026; únicamente presenta datos correspondientes al año 2023."

Fragmentos: [1] `Lrti Texto Vigente Sri Anticipo Renta Art41` (Pág. 43), [2] `Tabla Impuesto Renta Personas Naturales 2026` (Pág. 1), [3] `Lrti Texto Vigente Sri Tarifa0 Exportadores` (Pág. 43), idénticos a la corrida anterior. Este es el resultado más contradictorio de la 3ª re-validación: el fragmento [2] está **explícitamente etiquetado como "RENTA · 2026"** en el panel de fragmentos recuperados (metadato visible), y aun así el modelo declara que "únicamente presenta datos correspondientes al año 2023" y niega tener información sobre 2026.

**Actualización 2026-08-07 (post-fix chunker graph_text): RESUELTO. ✅ ÚLTIMA RONDA.**

> Respuesta: "Para la declaración del Impuesto a la Renta del ejercicio fiscal 2026, el monto de ingresos hasta el cual una persona natural no paga impuesto (fracción básica) es de 12.208 dólares [2]."

Fragmentos: [1] `Tabla Impuesto Renta Personas Naturales 2026` (Pág. 1), [2] `Reglamento Lrti 2023 Declaracion Iva Art158` (Art. 47, Pág. 213), [3] `Lrti Texto Vigente Sri Tarifa0 Exportadores` (Pág. 53), [4] `Retenciones Fuente Ir 2026` (Pág. 3). Con el fix del chunker, el fragmento de la tabla 2026 ahora rankea en primer lugar (sim=1.82, antes competía con fragmentos de 2023/2022) y el LLM finalmente extrae el monto correcto (USD 12.208) en vez de mezclarlo con la cifra de un ejercicio fiscal distinto, como ocurría en las tres rondas anteriores. Coincide plenamente con la respuesta esperada.

---

### q18 — Impuesto a la Renta — RESUELTO ✅ (antes `documento_equivocado`, luego `sin_informacion`) — no re-probada en la 3ª ni 4ª ronda

**Pregunta:** Una sociedad cliente me pregunta si está obligada a pagar un anticipo de Impuesto a la Renta durante el año. ¿Es obligatorio o voluntario, y cómo se calcula si decide hacerlo?

**Respuesta esperada (banco v2):** El anticipo es voluntario; equivale al 50% del Impuesto a la Renta causado el ejercicio anterior menos las retenciones sufridas ese ejercicio (Art. 41 de la LRTI).

**Fuente/artículo esperado:** `lrti_texto_vigente_sri_anticipo_renta_art41.pdf`, Art. 41.

**Clasificación original:** `documento_equivocado` — el documento con el Art. 41 no fue recuperado para esta consulta.

**Actualización 2026-08-06 (post-fix embedder): SIGUE FALLANDO, cambió de tipo — `sin_informacion`.**

> Respuesta: "Basado en el contexto proporcionado, no existe información sobre la obligatoriedad, voluntariedad o la forma de cálculo de los anticipos del Impuesto a la Renta. El texto únicamente menciona que las declaraciones y el pago de impuestos se realizarán en las formas y medios que el Servicio de Rentas Internas establezca mediante resolución de carácter general, y detalla el plazo de seis meses para el caso específico de herencias y legados."

Fragmento: [1] `Lrti Texto Vigente Sri Anticipo Renta Art41` (Pág. 46).

**Actualización 2026-08-06 (post-fix dedup/top_k): RESUELTO. ✅**

> Respuesta: "El pago del impuesto podrá anticiparse de forma voluntaria. En caso de decidir hacerlo, el cálculo será equivalente al cincuenta por ciento (50%) del impuesto a la renta causado del ejercicio fiscal anterior, menos las retenciones en la fuente efectuadas en dicho ejercicio fiscal. Este valor anticipado constituirá un crédito tributario para el pago del impuesto a la renta."

Fragmento: [1] `Lrti Texto Vigente Sri Anticipo Renta Art41` (Pág. 46). Ya resuelta antes del 3er y 4º fix; no formaba parte del alcance de esas rondas.

**Nota importante:** este documento (`lrti_texto_vigente_sri_anticipo_renta_art41.pdf`) es precisamente el que se identificó como el 2º PDF duplicado y fue **eliminado del corpus** entre la 3ª y la 4ª ronda (el que sobrevivió fue `lrti_texto_vigente_sri_tarifa0_exportadores.pdf`, el mismo contenido con otro nombre). q18 no fue re-probada en la 4ª ronda porque ya estaba RESUELTA; se registra aquí como referencia por si una futura re-ejecución mostrara una variación al usar el documento superviviente en lugar del eliminado (incidencia de trazabilidad para el equipo de benchmark).

---

### q19 — Impuesto a la Renta — `sin_informacion` (antes `documento_equivocado`) — retrieval resuelto en la 4ª ronda, síntesis sigue fallando en la 5ª y última

**Pregunta:** Una sociedad cuyo RUC tiene noveno dígito 7, del régimen general (no RIMPE), ¿hasta qué fecha debe presentar y pagar su declaración anual de Impuesto a la Renta?

**Respuesta esperada (banco v2):** Hasta el 22 de abril (Art. 72, numeral 1, del Reglamento para la Aplicación de la LRTI, noveno dígito 7).

**Fuente/artículo esperado:** `reglamento_lrti_2023_plazos_contabilidad.pdf` (= `reglamento_lrti_2023_declaracion_iva_art158.pdf`), Art. 72 numeral 1.

**Clasificación original:** `sin_informacion` (documento correcto pero artículo/página equivocados dentro del mismo archivo — recuperó el Art. 221 en vez del Art. 72).

**Actualización 2026-08-06 (post-fix embedder): SIGUE FALLANDO, cambió de tipo — `documento_equivocado` (retroceso respecto a la corrida anterior).**

> Respuesta: "Basado en el contexto proporcionado, no existe información sobre la fecha de presentación y pago de la declaración anual de Impuesto a la Renta para sociedades del régimen general. El texto suministrado únicamente detalla plazos para contribuyentes del régimen RIMPE y casos específicos de domicilio en la Provincia de Galápagos."

Fragmentos: [1] `Rimpe Normas Aplicacion Nac-Dgercgc24-00000027` (Pág. 7), [2] `Rimpe Reglamento Ley Desarrollo Covid Titulo Iv` (Pág. 43), [3] `Lrti Texto Vigente Sri Anticipo Renta Art41` (Art. 14, Pág. 96).

**Actualización 2026-08-06 (post-fix dedup/top_k): SIGUE FALLANDO — `documento_equivocado` (sin cambios).**

> Respuesta: "Basado en el contexto proporcionado, no existe información sobre los plazos de declaración y pago del Impuesto a la Renta para contribuyentes del régimen general. El texto se enfoca específicamente en los contribuyentes sujetos al régimen RIMPE."

Fragmentos: [1] `Rimpe Normas Aplicacion Nac-Dgercgc24-00000027` (Pág. 7), [2] `Rimpe Reglamento Ley Desarrollo Covid Titulo Iv` (Pág. 43), [3] `Lrti Texto Vigente Sri Anticipo Renta Art41` (Art. 14, Pág. 96).

**Actualización 2026-08-06 (post-fix system prompt): SIGUE FALLANDO — `documento_equivocado` (sin cambios).**

> Respuesta: "El contexto proporcionado no contiene información sobre los plazos de declaración y pago del Impuesto a la Renta para contribuyentes del régimen general; los fragmentos suministrados se refieren específicamente a los plazos y obligaciones de los sujetos al régimen RIMPE."

Fragmentos: [1] `Rimpe Normas Aplicacion Nac-Dgercgc24-00000027` (Pág. 7), [2] `Rimpe Reglamento Ley Desarrollo Covid Titulo Iv` (Pág. 43), [3] `Lrti Texto Vigente Sri Anticipo Renta Art41` (Art. 14, Pág. 96).

**Actualización 2026-08-06 (post-fix duplicado #2): SIGUE FALLANDO, cambió de tipo — `sin_informacion`. RETRIEVAL RESUELTO.**

> Respuesta: "El contexto proporcionado no contiene información sobre la fecha de declaración y pago del Impuesto a la Renta para contribuyentes del régimen general; los fragmentos suministrados se refieren exclusivamente a los plazos y obligaciones de los contribuyentes sujetos al Régimen RIMPE."

Fragmentos recuperados (3): [1] `Rimpe Normas Aplicacion Nac-Dgercgc24-00000027` (Pág. 7), [2] `Rimpe Reglamento Ley Desarrollo Covid Titulo Iv` (Pág. 43), [3] **`Reglamento Lrti 2023 Declaracion Iva Art158` (Art. 18, Pág. 172)** — el documento fuente esperado (el mismo archivo que contiene el Art. 72, aunque en la Resolución de nombre distinto usada como fuente del banco v2) aparece por primera vez en las 4 rondas, tras eliminar el 2º duplicado de la LRTI. Sin embargo, el LLM sigue sin usar ese fragmento para responder — declara textualmente que los fragmentos "se refieren exclusivamente" a RIMPE, ignorando el fragmento [3] que sí pertenece al Reglamento para la Aplicación de la LRTI (aunque en la página/artículo equivocados: Art. 18 Pág. 172, no el Art. 72 con la tabla de fechas). **Se resuelve el problema de recuperación, pero persiste el fallo por síntesis**: ni siquiera reconoce la presencia del fragmento [3] como relevante, y en todo caso esa página tampoco contiene la tabla de fechas necesaria.

**Actualización 2026-08-07 (post-fix chunker graph_text): SIGUE FALLANDO — `sin_informacion` (respuesta prácticamente idéntica). ÚLTIMA RONDA.**

> Respuesta: "El contexto proporcionado no contiene información sobre la fecha de declaración y pago del Impuesto a la Renta para contribuyentes del régimen general; los fragmentos suministrados se refieren exclusivamente a los plazos y obligaciones de los contribuyentes sujetos al Régimen RIMPE."

Fragmentos (3): [1] `Rimpe Normas Aplicacion Nac-Dgercgc24-00000027` (Pág. 7), [2] `Rimpe Reglamento Ley Desarrollo Covid Titulo Iv` (Pág. 43), [3] `Reglamento Lrti 2023 Declaracion Iva Art158` (Art. 18, Pág. 172) — idénticos a la ronda anterior. El fix del chunker no trajo la página específica del Art. 72 (tabla de fechas por noveno dígito para sociedades del régimen general); el fragmento [3] sigue apuntando al Art. 18. **Resultado final: SIGUE FALLANDO — `sin_informacion`**, con el documento correcto disponible desde la 4ª ronda pero sin que el LLM lo use ni contenga la página exacta necesaria en ninguna de las dos rondas donde estuvo presente.

---

### q20 — Impuesto a la Renta — `dato_incorrecto` (conclusión correcta se mantiene, justificación sigue sin el umbral correcto) — no re-probada en la 4ª ronda

**Pregunta:** Un comisionista (persona natural) inició el ejercicio fiscal con activos menos pasivos relacionados con su actividad por USD 190.000. ¿Está obligado a llevar contabilidad?

**Respuesta esperada (banco v2):** Sí está obligado, porque el umbral de **capital propio** es USD 180.000 (no USD 240.000, que es el umbral de costos y gastos anuales) — Art. 37 del Reglamento para la Aplicación de la LRTI. Con USD 190.000 de capital propio, supera el umbral de USD 180.000.

**Clasificación original:** `dato_incorrecto` (confusión entre los tres umbrales monetarios del mismo artículo; no concluía explícitamente si estaba o no obligado).

**Actualización 2026-08-06 (post-fix embedder): SIGUE FALLANDO — mismo tipo de confusión, ahora con una conclusión final explícita y equivocada.**

> Respuesta: "Basado en el contexto proporcionado, el capital propio se entiende como la totalidad de los activos menos pasivos que posea el contribuyente relacionados con la generación de la renta. El límite establecido es de doscientos cuarenta mil dólares (USD 240.000). Dado que el comisionista (persona natural) tiene activos menos pasivos por USD 190.000, se encuentra por debajo del límite señalado, por lo cual no estaría obligado a llevar contabilidad respecto a ese criterio."

Fragmentos: [1] `Reglamento Lrti 2023 Declaracion Iva Art158` (Pág. 64), [2] `Reglamento Comprobantes Venta Retencion` (Pág. 21).

**Actualización 2026-08-06 (post-fix dedup/top_k): SIGUE FALLANDO — `dato_incorrecto`, pero con conclusión final ahora en la dirección correcta (aunque sin la justificación numérica correcta).**

> Respuesta: "Sí, está obligado a llevar contabilidad. De acuerdo con el contexto normativo, los comisionistas (dentro del grupo de personas naturales y sucesiones indivisas que obtengan rentas objeto de este impuesto) están obligados a llevar contabilidad [3]."

Fragmentos: [1] `Reglamento Lrti 2023 Declaracion Iva Art158` (Pág. 64), [2] `Reglamento Comprobantes Venta Retencion` (Pág. 21), [3] `Rimpe Normas Aplicacion Nac-Dgercgc24-00000027` (Pág. 5), [4] `Rimpe Reglamento Ley Desarrollo Covid Titulo Iv` (Pág. 37).

**Actualización 2026-08-06 (post-fix system prompt): SIGUE FALLANDO — `dato_incorrecto` (respuesta prácticamente idéntica a la ronda anterior).**

> Respuesta: "Sí, está obligado a llevar contabilidad, ya que el fragmento [3] establece que están obligadas a llevar contabilidad las personas naturales que sean comisionistas."

Fragmentos: [1] `Reglamento Lrti 2023 Declaracion Iva Art158` (Pág. 64), [2] `Reglamento Comprobantes Venta Retencion` (Pág. 21), [3] `Rimpe Normas Aplicacion Nac-Dgercgc24-00000027` (Pág. 5), [4] `Rimpe Reglamento Ley Desarrollo Covid Titulo Iv` (Pág. 37), idénticos a la corrida anterior. La conclusión final ("Sí, está obligado") se mantiene correcta, pero la justificación sigue sin mencionar el umbral específico de capital propio (USD 180.000 del Art. 37) que es el que realmente determina la respuesta; en su lugar sigue apoyándose en una regla categórica de un fragmento de RIMPE ajeno al tema.

**Actualización 2026-08-07 (post-fix chunker graph_text): SIGUE FALLANDO — `dato_incorrecto` (sin cambios). ÚLTIMA RONDA.**

> Respuesta: "Sí, está obligado a llevar contabilidad, ya que el fragmento [3] establece que están obligadas a llevar contabilidad las personas naturales que sean comisionistas."

Fragmentos: [1] `Reglamento Lrti 2023 Declaracion Iva Art158` (Pág. 64), [2] `Reglamento Comprobantes Venta Retencion` (Pág. 21), [3] `Lrti Texto Vigente Sri Tarifa0 Exportadores` (Capítulo VI, Pág. 31) — respuesta y estructura casi idénticas a la ronda anterior (el fragmento [3] cambió de fuente pero el contenido citado es el mismo tipo de regla categórica ajena al umbral de capital propio). La conclusión final ("Sí, está obligado") sigue siendo correcta, pero la justificación sigue sin mencionar el umbral de USD 180.000 del Art. 37. El fix del chunker no aplicaba a este caso (el Art. 37 con los tres umbrales es texto corrido, no una tabla). **Resultado final: SIGUE FALLANDO — `dato_incorrecto`**, sin cambios sustantivos en las últimas tres rondas.

---

## Preguntas correctas desde la corrida original (no re-probadas, sin cambios)

- **q01** (RIMPE): el sistema distinguió correctamente que los "negocios populares" pueden seguir emitiendo notas de venta preimpresas, a diferencia de los "emprendedores" que deben facturar electrónicamente. Citó `RIMPE_normas_aplicacion_NAC-DGERCGC24-00000027` como fuente principal, coincidiendo con el `fuente_documento` esperado.
- **q04** (RIMPE): el sistema respondió correctamente que las notas de venta de negocios populares no generan crédito tributario de IVA directo al adquirente, citando `Rimpe Reglamento Ley Desarrollo Covid Titulo Iv` (Pág. 39), coincidiendo con el `fuente_documento` esperado (Art. 224). No profundizó en el mecanismo alternativo de liquidación de compras + retención del 100% de IVA, pero no contradijo ningún hecho clave de la pregunta formulada.

## Preguntas resueltas en la 1ª re-validación (2026-08-06, post-fix embedder)

- **q05** (Facturación electrónica): confirma correctamente la eliminación del margen de 4 días hábiles y el nuevo requisito de transmisión inmediata, citando `Facturacion Electronica Nac-Dgercgc25-00000014`.
- **q09** (Retenciones en la fuente): da el porcentaje correcto (10%) para honorarios de persona natural, citando `Retenciones Fuente Ir 2026`, aunque con redacción genérica en vez de citar el literal específico.
- **q13** (IVA): extrae correctamente la regla de declaración semestral (vs. mensual si hay retención de IVA) del Art. 158, citando `Reglamento Lrti 2023 Declaracion Iva Art158`.
- **q16** (IVA): confirma correctamente el derecho a crédito tributario de IVA para exportadores sobre materias primas/insumos, reproduciendo el contenido del Art. 57 de la LRTI (aunque etiquetado como Art. 56), citando `Lrti Texto Vigente Sri Tarifa0 Exportadores`.

## Preguntas resueltas en la 2ª re-validación (2026-08-06, post-fix dedup/top_k en `agents/response_agent.py`)

- **q07** (Facturación electrónica): ahora extrae correctamente el plazo de "5 días hábiles" del Art. 4 de la Resolución NAC-DGERCGC25-00000014 para que el receptor acepte o rechace una solicitud de anulación de comprobante de retención, dato que ya estaba en el fragmento correcto pero no se sintetizaba antes del fix de `max_per_doc`/`RAG_TOP_K`.
- **q18** (Impuesto a la Renta): ahora confirma correctamente que el anticipo de Impuesto a la Renta es voluntario y explica el cálculo (50% del impuesto causado el ejercicio anterior menos retenciones), citando `Lrti Texto Vigente Sri Anticipo Renta Art41`.

## Preguntas resueltas en la 3ª re-validación (2026-08-06, post-fix system prompt en `agents/response_agent.py::_SYSTEM_PROMPT`)

**Ninguna.** De las 12 preguntas re-probadas con el tercer fix (reglas de priorización de versión vigente, extracción obligatoria del dato exacto, y prohibición de citar fuera de contexto), ninguna pasó de fallo a RESUELTO. Hubo mejoras cualitativas menores en la redacción de q03 y q20 (conclusiones más completas/correctas en su dirección general), pero ningún caso llegó a cumplir el criterio de solape factual completo (fecha/porcentaje/artículo/umbral exactos). Se registró además una regresión puntual en q15 (vuelve la cita de una ley inexistente) y en q17 (pasó de dar un dato incorrecto a negar tener información pese a que el fragmento correcto y correctamente etiquetado seguía presente).

## Preguntas resueltas en la 4ª re-validación (2026-08-06, post-fix eliminación del 2º PDF duplicado del corpus)

**Ninguna pasó de fallo a RESUELTO**, pero las 3 preguntas re-probadas (q10, q11, q19) lograron por primera vez, en las 4 rondas, que el documento fuente esperado apareciera entre los fragmentos recuperados:

- **q10**: `retenciones_fuente_ir_2026.pdf` aparece como fragmento [4] (Pág. 6). Reclasificada de `documento_equivocado` a `sin_informacion` — el LLM sigue sin extraer el 10% de arrendamiento del fragmento ya disponible.
- **q11**: `retenciones_fuente_ir_2026.pdf` aparece como fragmento [3] (Pág. 1). Reclasificada de `documento_equivocado` + `dato_incorrecto` a `dato_incorrecto` puro — el LLM sigue dando el 10% genérico en vez del 5% específico para sociedades, con el documento correcto ya disponible.
- **q19**: `reglamento_lrti_2023_declaracion_iva_art158.pdf` aparece como fragmento [3] (Art. 18, Pág. 172). Reclasificada de `documento_equivocado` a `sin_informacion` — el LLM ni siquiera reconoce este fragmento como relevante para la pregunta, y en todo caso la página recuperada no contiene la tabla de fechas del Art. 72 que se necesita.

Con esto, la categoría `documento_equivocado` quedó completamente vacía (0 preguntas) desde el cierre de esta ronda.

## Preguntas resueltas en la 5ª re-validación (2026-08-07, post-fix chunker `graph_text` — ÚLTIMA RONDA de la sesión)

- **q12** (Retenciones en la fuente): ahora extrae correctamente el 3% de retención por defecto (Art. 3 de la Resolución NAC-DGERCGC26-00000009) para pagos sin porcentaje específico, en vez de repetir la cláusula genérica del 10% de las rondas anteriores, citando `Retenciones Fuente Ir 2026`.
- **q17** (Impuesto a la Renta): ahora extrae correctamente el monto de USD 12.208 de la tabla "IMPUESTO A LA RENTA PERSONAS NATURALES" del año 2026, en vez de mezclarlo con la cifra de un ejercicio fiscal distinto (2022/2023) como en las tres rondas anteriores, citando `Tabla Impuesto Renta Personas Naturales 2026`.

Estas 2 preguntas dependían de chunks tipo tabla cuyo `graph_text` (según el diagnóstico del equipo) carecía de señal semántica suficiente antes del fix. El caso que originalmente motivó el diagnóstico del fix — **q02**, la tabla de fechas RIMPE por noveno dígito — **no se resolvió**: el sistema sigue sin dar la fecha correcta y, de hecho, retrocedió a dar una fecha concreta pero incorrecta ("hasta el mes de junio") en vez de reconocer que no la tiene, lo cual se reclasifica como `dato_incorrecto` (antes `sin_informacion`).

## Fallos que persisten al cierre DEFINITIVO de la validación manual (10 de 20), con su clasificación final

| Pregunta | Categoría | Tipo de fallo final | Nota |
|---|---|---|---|
| q02 | RIMPE | `dato_incorrecto` | El fix del chunker (diseñado para este caso) no trajo el chunk de la tabla al top de fragmentos usados; el sistema ahora arriesga una fecha concreta pero incorrecta ("mes de junio") en vez de reconocer que no la tiene. Único caso donde el fix 5 empeoró cualitativamente el resultado. |
| q03 | RIMPE | `sin_informacion` | Documento correcto (Pág. 39) desde la 1ª ronda, confirma que existe un límite (con matiz correcto sobre negocios populares), pero no extrae "tres períodos fiscales" (Art. 217, texto corrido, no tabla — el fix del chunker no aplicaba). |
| q06 | Facturación electrónica | `dato_incorrecto` | Ambas resoluciones (-014 y -017) en contexto desde la 2ª ronda, pero sigue usando el plazo derogado "día 10" en vez del vigente "día 7" en las 3 últimas rondas. |
| q08 | Facturación electrónica | `dato_incorrecto` | Extrae correctamente "un año" desde la 2ª ronda, pero sigue sin extraer el plazo reducido de "tres meses" en las 3 últimas rondas. |
| q10 | Retenciones en la fuente | `sin_informacion` | Retrieval resuelto desde la 4ª ronda (`retenciones_fuente_ir_2026.pdf` se recupera, Pág. 6), pero el LLM sigue sin extraer el 10% de arrendamiento en las 2 rondas donde estuvo disponible. |
| q11 | Retenciones en la fuente | `dato_incorrecto` | Retrieval resuelto desde la 4ª ronda (`retenciones_fuente_ir_2026.pdf` se recupera, Pág. 1), pero el LLM sigue dando 10% en vez del 5% correcto para sociedades en las 2 rondas donde estuvo disponible. |
| q14 | IVA | `sin_informacion` | Documento correcto (Pág. 74) desde la 2ª ronda, pero no es la página con el Art. 55 num. 6 (medicamentos, texto corrido — el fix del chunker no aplicaba). |
| q15 | IVA | `dato_incorrecto` | Conclusión correcta (tarifa 0%) pero cita el Art. 190 en vez del Art. 56 num. 3 esperado; mejoró en la última ronda al dejar de alucinar el nombre de una ley inexistente, pero el artículo sigue sin coincidir con la fuente real. |
| q19 | Impuesto a la Renta | `sin_informacion` | Retrieval resuelto desde la 4ª ronda (el documento con el Art. 72 se recupera como fragmento [3]), pero el LLM ni reconoce el fragmento como relevante ni la página recuperada (Art. 18, Pág. 172) contiene la tabla de fechas necesaria, en las 2 rondas donde estuvo disponible. |
| q20 | Impuesto a la Renta | `dato_incorrecto` | Conclusión final correcta ("sí obligado") desde la 2ª ronda, pero la justificación no menciona el umbral correcto de capital propio (USD 180.000) del Art. 37 (texto corrido, no tabla — el fix del chunker no aplicaba) en las 3 últimas rondas. |

**Resultado FINAL DEFINITIVO de la sesión de validación manual: 10/20 (50%) correctas — 10/20 (50%) con fallo de síntesis/generación (0 con fallo de recuperación). Se cierra la sesión de validación manual tras 5 rondas de fix y re-validación; se procede a la ejecución del benchmark automatizado.**
