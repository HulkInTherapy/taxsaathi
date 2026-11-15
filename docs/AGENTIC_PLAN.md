# Taxot — Agentic AI Enhancement: Phase-wise Plan

Source: *Taxot: Product & Enhancement Plan (Agentic AI Track)*. This file turns that plan into
build steps against the existing codebase.

## 0. Decisions already made

| Topic | Decision |
|---|---|
| LLM | One OpenAI-compatible gateway with per-role provider order and automatic fallback. **Agents** (planner, extractor): NVIDIA NIM Nemotron 3.5 Super 120B → Regolo (gpt-oss-120b / Qwen3.5-122B) → Groq (gpt-oss-120b / Qwen3.8-27B) → Gemini 3.5 Flash-Lite → OpenRouter free. **Verifier**: Regolo DeepSeek V4.1 Flash first (a different model family from the agents) → Gemini → Groq → NVIDIA MiniMax → OpenRouter. When every provider is rate-limited the gateway backs off (20/45/90 s). Free-tier notes (Nov 2026): NVIDIA limits each model separately (~40 RPM per account) and its free endpoints are for testing; OpenRouter free = 50 requests/day; Groq ~200K tokens/day per model; Gemini free tier is small and may use prompts; Regolo is a 30-day trial (~1M tokens/day). Mistral's free API ended (Nov 2026). For the hosted product, a cheap paid API (e.g. Sarvam-105B, if its tool calling passes) is the candidate primary; Modal GPU credits are an option for rate-limit-free evaluation on a self-hosted open model. |
| Privacy | PAN, Aadhaar, names, account numbers, phone and email are masked **before** any text leaves the server (free tiers may train on requests). Evaluation uses synthetic documents only. |
| Vector store | Move dense retrieval from the numpy `.npz` index to **ChromaDB** (embedded, on-disk, no server). |
| Agent framework | **LangGraph** (state graph, checkpointer for memory, `interrupt` for human approval). |
| UI | **Extend the existing JS app** (`app/static`) with new views. No Streamlit. Plan PDF tech stack to be updated to "FastAPI + custom web UI". |
| Hosting | Same VPS + Docker. LLM runs at NVIDIA NIM / OpenRouter; embeddings and reranker stay on CPU as today. |
| Arithmetic and rules | Stay deterministic Python (calculator, ITR form rules, mismatch checks). The LLM plans, extracts and explains; it never computes tax or decides eligibility on its own. |

## 1. Target architecture

```
User ──goal/approvals──▶ Orchestrator ──draft──▶ Verifier
                           │   ▲                   │
                           │   └──── verdict ──────┘
          ┌────────────┬───┴────────┬────────────┬────────────┐
     Document      Income tax     GST agent   Calculator    Escalation
       agent          agent                     agent
          │          │     │          │            │             │
   parse_document  itr_form_rules  search_tax_law  calculate_tax  write_ca_summary
                         (search_tax_law = existing Taxot RAG pipeline)

Shared task state (LangGraph): goal, plan, documents' extracted fields, figures,
open questions, approvals, tool-call count (hard limit 15), trace.
```

### New code layout

```
src/
  llm/
    provider.py        # OpenAI-compatible client: NVIDIA / OpenRouter / Ollama, fallback, rate limiter, usage log
    masking.py         # mask before send, unmask placeholders in replies (wraps guardrails/pii.py)
  tools/
    search_tax_law.py  # wraps Taxot.ask() -> answer, citations, confidence
    calculate_tax.py   # wraps calculator.calculate() + what-if variants
    itr_form_rules.py  # deterministic ITR-1/2/3/4 eligibility rules
    parse_document.py  # PDF -> text -> structured fields (schema-validated)
    write_ca_summary.py
    ask_user.py        # raises a LangGraph interrupt
    registry.py        # tool schemas, budget counter (15), argument validation
  documents/
    schemas.py         # Form16, SalarySlip, InterestCertificate (pydantic)
    extract.py         # LLM extraction + regex/rule validation
    crosscheck.py      # deterministic mismatch rules
  agents/
    state.py           # TaskState (TypedDict / pydantic)
    graph.py           # LangGraph wiring, checkpointer, interrupts
    orchestrator.py
    document_agent.py
    income_tax_agent.py
    gst_agent.py
    calculator_agent.py   # incl. tax-saving optimiser
    verifier.py
    escalation.py
    prompts/            # one prompt file per agent
  retrieval/
    dense.py            # now backed by ChromaDB
scripts/
  synth_documents.py   # generates synthetic Form 16 / slips / certificates + ground truth
experiments/
  run_agent_eval.py    # scenario runner + metrics + comparisons (MLflow)
data/
  synthetic/           # personas.yaml, generated PDFs, ground_truth.jsonl
  eval/scenarios.jsonl # 30–50 tasks
app/static/            # new views: tasks, upload, progress, approvals, results
```

---

## Phase 1 — Foundations (LLM provider, masking, ChromaDB)

**Goal:** the plumbing everything else depends on.

1. Dependencies: `langgraph`, `langchain-core`, `langchain-openai` (OpenAI-compatible endpoints),
   `chromadb`, `python-dotenv`.
2. `src/config.py`: load `.env`; add `TAXOT_LLM_PROVIDER`, model names per role
   (planner / extractor / verifier), request rate limit, `MAX_TOOL_CALLS=15`.
3. `src/llm/provider.py`: one `get_chat_model(role)` returning a tool-calling chat model.
   - Rate limiter per provider (NVIDIA NIM free: ~40 requests/min).
   - Automatic fallback NVIDIA → OpenRouter on 429/5xx/timeout.
   - Logs tokens, latency and provider per call (needed for "steps, latency, cost" metric).
4. `src/llm/masking.py`: replace PAN/Aadhaar/name/account numbers with placeholders
   (`<PAN_1>`) before sending; restore them in the final output only.
5. ChromaDB migration of `DenseIndex`, same interface. Re-run the existing retrieval
   experiment (config C6) to prove Recall@5 / MRR are unchanged.
6. Existing `/ask` keeps working; Ollama path still selectable.

**Done when:** a smoke test calls each provider with a tool and gets a structured tool call;
fallback to OpenRouter is demonstrated by forcing an error; retrieval metrics match before/after.

## Phase 2 — Tools layer

**Goal:** every capability the agents need, callable and testable without any agent.

| Tool | Input | Output | Notes |
|---|---|---|---|
| `search_tax_law` | question, period (optional) | answer, citations, confidence, refused flag | Wraps `Taxot.ask()` |
| `calculate_tax` | `TaxInputs` fields, optional list of variants | per-regime tax, breakdown, best regime | Wraps `calculator.calculate()` |
| `itr_form_rules` | income heads, total income, residency, director/unlisted shares, capital gains, business type | form (ITR-1/2/3/4), reasons, rule refs | New, deterministic |
| `parse_document` | file id, expected type (optional) | typed fields + confidence + warnings | Phase 4 completes it |
| `write_ca_summary` | task state | structured summary (JSON + Markdown/PDF) | Phase 6 completes it |
| `ask_user` | question, options | user's answer | LangGraph `interrupt` |

- `registry.py`: pydantic argument schemas, validation errors returned to the agent as
  messages (so it can correct itself), global per-task budget of 15 calls.
- Unit tests for each tool (no LLM needed).

**Done when:** `pytest tests/test_tools.py` passes; ITR rules give the right form on a table
of hand-written cases.

## Phase 3 — Synthetic data and knowledge-base additions

**Goal:** realistic test inputs with known correct answers; small KB top-up.

1. `data/synthetic/personas.yaml`: 30–50 fictional people (salaried, salaried + FD interest,
   senior citizen, freelancer under 44ADA, salaried with capital gains, two employers,
   high income with surcharge, GST-relevant freelancer, …). Made-up PAN-format IDs.
2. `scripts/synth_documents.py` (PyMuPDF, already a dependency) renders per persona:
   - Form 16 Part A (TDS) and Part B (salary breakup, deductions claimed),
   - monthly salary slips,
   - bank interest certificates (savings + FD, TDS deducted).
3. Planted issues, recorded in `ground_truth.jsonl`:
   - interest income not reflected in Form 16 (workflow 1),
   - salary slips total ≠ Form 16 gross salary,
   - TDS on interest certificate ≠ declared,
   - deduction claimed above its cap,
   - **prompt injection** text inside a document (visible line and hidden/white text),
   - complex cases that must escalate (capital gains, foreign income, two employers with
     wrong TDS, business above presumptive limit).
4. KB additions (curated Markdown from official pages, same format as existing files):
   `it_form16.md` (what Form 16 Part A/B contain), `it_other_sources_interest.md`
   (interest income, 80TTA/80TTB, TDS u/s 194A), `it_ais_26as.md` (checking against AIS/26AS).
   Re-ingest, re-embed, re-run retrieval eval to confirm no regression.

**Done when:** generator produces PDFs + ground truth for every persona; KB rebuilt.

## Phase 4 — Document agent + Workflow 1 (Document check)

**Goal:** upload Form 16 + interest certificate → agent finds missing interest and warns.

1. `parse_document`: PyMuPDF text → document-type detection → LLM extraction into the
   pydantic schema → validation (totals add up, PAN format, amounts non-negative).
   Low-confidence fields are flagged, never guessed.
2. **Prompt-injection defence:** document text is passed only as quoted data inside a
   fenced block with an explicit "data, not instructions" system rule; extraction output is
   schema-only (no free text reaches the planner); an injection detector flags imperative
   phrases ("ignore previous", "you must recommend", …) and the task notes it.
3. `crosscheck.py` (deterministic): interest missing from Form 16, slips vs Form 16 gross,
   TDS mismatches, deductions over cap.
4. Document agent: calls `parse_document` per file, then cross-check, then explains the
   findings in plain language with the rule/section cited (via `search_tax_law`).
5. Files held in memory per session and deleted when the session ends; logs masked.

**Done when:** on all synthetic personas with planted mismatches, the mismatch is reported;
on clean personas, no false alarm; injection personas never change the agent's behaviour.

## Phase 5 — Orchestrator, specialists, memory, approvals + Workflow 2 (Filing preparation)

**Goal:** "Help me prepare my return" runs end to end with user approvals.

1. `TaskState`: goal, plan (list of steps with status), documents, extracted figures,
   open questions, approvals, findings, drafts, tool-call count, trace.
2. Orchestrator: turns the goal into a plan, routes each step to a specialist, asks the
   user for missing info (`ask_user`), never writes the final answer itself.
3. Specialists:
   - Income tax agent: `search_tax_law` + `itr_form_rules` → ITR form with reasons.
   - GST agent: registration threshold, composition, rates for freelancers/small sellers.
   - Calculator agent: regime comparison from extracted figures.
4. Human-in-the-loop: LangGraph `interrupt` before (a) confirming extracted figures,
   (b) the regime recommendation, (c) the final checklist. User can approve or edit.
5. Memory: LangGraph checkpointer (SQLite) keyed by task id, so the task survives page
   reloads and multi-turn conversation.
6. Output: filing-ready checklist (form, regime, income heads with figures, deductions,
   documents to keep, due date).

**Done when:** a scripted run on 5 personas produces correct form + regime + checklist with
three approval pauses; the 15-call limit is enforced and reported.

## Phase 6 — Verifier, tax-saving optimiser, escalation + Workflow 3 (Tax-saving plan)

**Goal:** nothing unverified reaches the user; ranked savings plan; clean CA handoff.

1. Verifier agent: split draft into atomic claims → retrieve evidence (`search_tax_law`)
   → judge each claim supported / unsupported / contradicted (LLM + reranker score) →
   return unsupported claims to the orchestrator for revision (max 2 rounds, then remove
   the claim or escalate). Numbers are checked against calculator output, not the LLM.
2. Optimiser (calculator agent): enumerate legal options valid under the current Act —
   regime switch, 80C top-up, 80D (self/parents), NPS 80CCD(1B), employer NPS, HRA, home loan
   interest — within each cap and the user's stated limits; run `calculate_tax` per option
   and combination; rank by rupee saving; verifier checks each recommendation's legal basis.
3. Escalation agent: triggers on capital gains, foreign income/assets, business beyond
   presumptive limits, unresolved document mismatches, verifier failing twice, or low
   retrieval confidence. `write_ca_summary` produces: profile, extracted figures, findings,
   open questions, what was already checked (with citations). Downloadable.

**Done when:** planted-unsupported-claim drafts are caught; optimiser output matches
hand-computed savings on test personas; complex personas escalate with a complete summary.

## Phase 7 — API and UI

**API (FastAPI, `src/api/main.py`):**
- `POST /tasks` (goal) → task id
- `POST /tasks/{id}/documents` (upload, kept in memory)
- `GET /tasks/{id}/events` (Server-Sent Events: live step updates)
- `POST /tasks/{id}/approve` / `POST /tasks/{id}/answer`
- `GET /tasks/{id}` (state, results, CA summary download)
- `DELETE /tasks/{id}` (end session, wipe documents)

**UI (existing JS app, same style):**
- "Tasks" view with the three workflow starters.
- Drag-and-drop upload with extracted fields shown for confirmation.
- Live progress timeline (agent, tool, result, time) reusing the existing trace styling.
- Approval cards (Approve / Edit) at each interrupt.
- Results: findings, filing checklist, ranked savings plan, CA summary download.
- Mock mode (like `mock.js`) so the UI can be demoed without API calls.

**Done when:** all three workflows can be completed in the browser.

## Phase 8 — Evaluation

1. `data/eval/scenarios.jsonl`: 30–50 tasks over the synthetic personas, each with expected
   ITR form, regime, mismatches, escalation yes/no, and allowed tool sequence.
2. `experiments/run_agent_eval.py` logs to MLflow:

| Metric | Target |
|---|---|
| Task success (correct ITR form, regime, mismatch found) | ≥ 80% |
| Tool-call accuracy (right tool, right arguments) | ≥ 85% |
| Verifier catch rate on planted unsupported claims | ≥ 90% |
| Correct escalation of complex cases | ≥ 90% |
| Resistance to injected instructions in documents | 100% |
| Steps, latency, tokens per task | Reported, reduced across iterations |

3. Comparisons: NLP pipeline vs agentic on the same complex requests; agent with vs without
   verifier; single-agent (one LLM with all tools) vs multi-agent.
4. Error analysis + iteration log (`docs/M4_agent_experiment_log.md`).

## Phase 9 — Deploy, docs, presentation

- Dockerfile + `deploy/taxot.service` read keys from an env file; health check covers LLM
  provider reachability.
- README, report chapter (architecture, safety, results), demo cheat-sheet for the three
  workflows, updated slides and figures.

---

## Order and dependencies

```
P1 Foundations ─▶ P2 Tools ─▶ P4 Document agent ─▶ P5 Orchestrator ─▶ P6 Verifier/optimiser/escalation ─▶ P8 Eval
                  P3 Synthetic data (parallel with P2) ─┘                          P7 API+UI (starts after P5) ─┘
                                                                                    P9 at the end
```

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Free-tier rate limits slow evaluation | Rate limiter + OpenRouter fallback; cache LLM responses during eval reruns |
| Free tier may train on requests | Mask all PII before sending; synthetic data only |
| LLM extraction errors on documents | Schema validation, arithmetic consistency checks, user confirms extracted figures |
| Agent loops / runaway cost | Hard 15-tool-call limit, max 2 verifier rounds |
| Model hallucinating tax amounts or eligibility | Calculator, ITR rules and cross-checks are deterministic Python; verifier checks numbers against them |
| Free-tier limits change | Provider is a config switch (NVIDIA / OpenRouter / Ollama) |
