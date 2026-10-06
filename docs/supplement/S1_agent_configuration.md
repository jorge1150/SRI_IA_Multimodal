# Supplementary Material S1: Exact Configuration of the Three Orchestration Agents

This supplement accompanies the manuscript "Multimodal GraphRAG Retrieval of Regulatory Knowledge: An Empirical Evaluation for Ecuadorian Tax Legislation Query Answering." It gives the exact, verbatim configuration of the three agents that make up the agentic orchestration layer described in Section 3.5 (System Architecture and Corpus): the Query Refiner Agent, the Query Validator Agent, and the Planner Agent. All three decide via Ollama's native tool-calling: the model either calls the one tool it was given, or it does not, and that presence/absence is the decision. Tool descriptions are kept in their original Spanish, since that is the language the production system and the benchmark run in; an English paraphrase is given alongside each one for readability.

Source: `agents/query_refiner_agent.py`, `agents/query_validator_agent.py`, `agents/planner_agent.py`, `agents/coordinator.py`, and `config.py`, as of this submission.

---

## 1. Query Validator Agent: domain guardrail (pre-check)

Runs once per query, before any refinement, with no retrieval involved. Checks only whether the query belongs to the tax domain at all.

**Tool:** `pregunta_fuera_de_dominio`

```
Llama a esta función si la pregunta NO tiene relación alguna con
impuestos, tributación o normativa fiscal, de cualquier país
(ej. clima, deportes, saludos, preguntas de otro dominio por
completo). NO la llames si la pregunta es sobre impuestos/
normativa aunque esté mal formulada o hable de otro país, para
eso está rechazar_pregunta. Preguntas sobre impuestos de otros
países (ej. comparaciones de tarifas de IVA regional) SÍ cuentan
como dominio tributario, aunque no sean específicamente del SRI
Ecuador.
```

*(English: call this tool only if the query has no connection to taxes or tax regulation of any country. Do not call it for a tax-related query that is just poorly phrased, or about a foreign country's tax system, since that is a different tool. Tax questions about other countries still count as in-domain.)*

If called, the pipeline stops immediately with a fixed message and never reaches the Refiner, since the system must never "fix" an off-topic query into sounding tax-related.

Timeout: 30 s (`VALIDATOR_TIMEOUT`, `config.py`). On any failure (Ollama unreachable, timeout, no parseable tool call), the agent defaults to **not** off-topic, so the pipeline continues.

---

## 2. Query Refiner Agent ⇄ Query Validator Agent loop

Runs after the domain guardrail passes. Up to **2 rounds** (`REFINEMENT_MAX_ITERATIONS = 2`, `config.py`, overridable via the `REFINEMENT_MAX_ITERATIONS` environment variable).

**Each round:**
1. The Refiner rewrites the query (first round: using conversational context if any; later rounds: using the Validator's rejection reason from the previous round). No fixed tool here; it is a plain rewrite call, described in `agents/query_refiner_agent.py`'s system prompt (not reproduced here for space, see the source file).
2. The Validator runs a **real test retrieval** (`RAGAgent.retrieve`, `vector_only` mode) against the refined query, then decides via tool-calling whether that retrieval is good enough to answer from.

**Validator's tools in this loop:**

`rechazar_pregunta`
```
Llama a esta función SOLO si la pregunta ES sobre impuestos o
tributación (aunque no sea específicamente del SRI Ecuador, ej.
tarifas de IVA de otros países) pero es imposible de responder
con los fragmentos dados: está vacía o incoherente, o NINGUNO de
los fragmentos recuperados es relevante al tema de la pregunta.
NO la llames solo porque la pregunta es amplia o los fragmentos no
cubren absolutamente todos los detalles posibles, una pregunta
general ("¿qué medidas... ?", "¿qué obligaciones... ?") es válida
y respondible con los fragmentos relevantes que sí haya, aunque no
los liste todos. Rechazar por amplitud hace que el sistema nunca
converja. Si la pregunta no es sobre tributación en absoluto, usa
pregunta_fuera_de_dominio en vez de esta.
```

*(English: call this only when the query is tax-related but genuinely unanswerable from the retrieved fragments, empty/incoherent, or none of the retrieved fragments are relevant. Do not call it just because the query is broad or the fragments do not cover every possible detail, a reasonably general question is still valid. Rejecting for breadth alone would stop the loop from ever converging.)*

`pregunta_fuera_de_dominio` (same tool and description as in Section 1 above, also available mid-loop as a safety net).

**Stopping rule, exact (from `agents/coordinator.py::run_refinement_loop`):**
- If the Validator approves: the loop stops immediately. If there had been at least one prior rejection in this same loop, the (rejected query, rejection reason, approved query) triple is recorded into the Refiner's memory (Section 3.5; see also the discussion of this memory's independence limitations in Section 5).
- If the Validator flags the query as off-topic mid-loop: the loop stops immediately, no further refinement is attempted.
- Otherwise, the rejection reason is carried into the next round, up to the 2-round cap.
- **If the query is still not approved after 2 rounds, the pipeline does not block or error out.** It proceeds with whatever query and retrieval the last round produced. This is a deliberate fail-open design, consistent with the rest of the pipeline's error handling.

Timeout per call: 30 s each for the Refiner (`REFINER_TIMEOUT`) and the Validator (`VALIDATOR_TIMEOUT`). On any failure, the Refiner keeps the query unchanged and the Validator defaults to approving, both safe-default choices that keep the pipeline moving rather than blocking it.

---

## 3. Planner Agent: vector-only vs. vector-plus-graph routing

Runs once per query, after the refinement loop, only when `config.USE_AGENTIC_PLANNER` is enabled. Vector retrieval always runs regardless of this decision; the only thing being decided is whether the knowledge graph is also consulted.

**Tool:** `buscar_relaciones_grafo`

```
Busca relaciones estructuradas entre entidades tributarias
(quién debe qué a quién, qué impuesto aplica a qué sujeto, qué
obligaciones tiene cada actor). Llama a esta función SOLO si la
pregunta pide explícitamente una relación, obligación o conexión
entre dos o más conceptos tributarios. NO la llames para
preguntas sobre definiciones simples, tarifas puntuales o el
texto de un artículo.
```

*(English: searches for structured relations between tax entities, who owes what to whom, which tax applies to which taxpayer, what obligations each actor has. Call this tool only if the query explicitly asks for a relationship, obligation, or connection between two or more tax concepts. Do not call it for simple definitions, specific rates, or the text of an article.)*

The decision is binary and based purely on whether the tool was called, not on a boolean field inside the response, which the codebase's comments note is more reliable to parse with a small (3B-class) model. Timeout: 30 s (`PLANNER_TIMEOUT`). On any failure, the agent defaults to **not** using the graph (`vector_only`), the same "vector always runs, graph is the optional complement" principle used throughout the retrieval layer.

---

## Summary table (mirrors the compact version in the main text, Table in Section 3.5)

| Agent / step | Decision | Tool(s) | Timeout | On failure |
|---|---|---|---|---|
| Validator, domain pre-check | in-domain vs. off-topic | `pregunta_fuera_de_dominio` | 30 s | defaults to in-domain |
| Refiner ⇄ Validator loop | approve vs. reject-and-retry, up to 2 rounds | `rechazar_pregunta`, `pregunta_fuera_de_dominio` | 30 s per call | Refiner keeps query unchanged; Validator defaults to approve |
| Planner | vector-only vs. vector + graph | `buscar_relaciones_grafo` | 30 s | defaults to vector-only |
