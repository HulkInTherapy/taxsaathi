# M4 Experiment Log: Taxot agents (Phase 8)

This log evaluates the agentic layer (Phases 1–7) against the targets in `docs/AGENTIC_PLAN.md` (Phase 8). It
compares that layer with two baselines on the same scenarios and records each iteration: what failed, why, and
what changed. Every number here is reproducible from `experiments/agent_results/*.json`. The roll-up
(`python -m experiments.run_agent_eval`) logs the numbers to MLflow (experiment `taxot-m4-agents`) and writes
`experiments/agent_results/summary.json`.

> **Status:** iteration 2 finished on 26 Nov (59 tasks, 0 errors). All numbers below come from
> `summary.json` written by `run_agent_eval`.

## Setup

| Item | Value |
|---|---|
| Scenario set | `data/eval/scenarios.jsonl`: 40 scenarios, one per synthetic persona (`scripts/build_scenarios.py`, derived from `data/synthetic/ground_truth.jsonl` so expected answers cannot drift) |
| Workflow mix | 18 document check · 16 filing preparation (6 must escalate) · 6 tax-saving plan |
| Planted problems | 21 scenarios with document findings (interest missing from Form 16, slips vs Form 16, Part A/B TDS, 80C over cap, PAN mismatch, two employers); 4 prompt injections (visible and hidden); 6 escalation cases (capital gains, foreign assets, director/unlisted shares, F&O, above presumptive limit) |
| Expected per scenario | ITR form, cheaper regime and both tax totals (₹1 tolerance), finding codes, escalate yes/no and reasons, injections, GST registration, best saving option and amount, required / allowed tools and their order |
| Simulated user | `experiments/sim_user.py`: answers the agents' questions in prose, from the persona's true facts, and only when asked; approves every approval card |
| Models (free tiers) | Planner and specialists: NVIDIA `nemotron-3.5-super-vl-120b-a12b`. Extractor: same. Verifier: Regolo `deepseek-v4.1-flash` (a different family from the writers). Fallbacks: Groq, Gemini, OpenRouter |
| Safety limits | 15 tool calls per task; at most 2 verifier rounds; PII masked before every LLM call |
| Runs | Sequential (`--workers 1`). Parallel runs exhausted every free provider at once and produced misleading failures |

## Targets

Document check comes from its Phase 4 run (37 personas). Filing and tax-saving come from iteration 2 (22 tasks).
The verifier comes from the Phase 6 planted-claim run.

| Metric | Target | Result | Source |
|---|---|---|---|
| Task success (correct ITR form, regime, exact tax, findings, escalation, approvals) | ≥ 80% | **100%** (59/59) | document check 37/37, filing prep 16/16, tax-saving 6/6 |
| Tool-call accuracy (right tool, right arguments) | ≥ 85% | **100%** | document check 100%; specialists' key calculator arguments 100% |
| Verifier catch rate on planted unsupported claims | ≥ 90% | 100% (19/19), removed 95% | `verifier.json` |
| Correct escalation of complex cases | ≥ 90% | **100%** (6/6 escalated, 0 false escalations) | filing and tax-saving runs |
| Resistance to injected instructions in documents | 100% | 100% (4/4, also with redaction off) | `doc_check.json`, `doc_check_no_redaction.json` |
| Steps, latency, tokens per task | reported | filing prep 6 tool calls, 20.8 LLM calls, 65k tokens, median 265 s; tax-saving 4.3 / 17.2 / 52k / 205 s; document check 5.6 LLM calls, 20k tokens, 32 s | `summary.json` |

## Comparison 1: NLP pipeline vs single agent vs multi-agent

All three systems get the same 22 filing and tax-saving scenarios.

- **NLP pipeline (M3, config C5):** single-shot `/ask` with no LLM generation (Ollama not installed on the
  evaluation machine, so it answered extractively). It got more help than the agents: the true document
  figures and every user fact were written into the question. It was run in two modes:
  - **whole request:** the scenario goal as one question;
  - **decomposed:** the best case, with separate questions for the calculation, the ITR form, "do I need a CA"
    and GST.
- **Single agent:** one LLM with all six tools, the goal, the documents and all facts up front. No orchestrator,
  no deterministic figures step, no reconciliation with the rules, no verifier. Its answer is scored as is.
- **Multi-agent (Taxot):** LangGraph orchestrator. The planner picks the steps, specialists use the tools, every
  figure and decision is reconciled with deterministic code, the verifier checks the text, and there are
  approval interrupts.

| System | Success | ITR | Regime | Exact tax | Escalation | GST | Savings | Findings | LLM calls | Median s |
|---|---|---|---|---|---|---|---|---|---|---|
| NLP pipeline, whole request | 0% | 0% | 0% | 0% | 73% | 0% | 0% | 0% | 0 | 3.1 |
| NLP pipeline, decomposed | 4.5% | 20% | 100% | 56% | 73% | 50% | 0% | 0% | 0 | 11.7 |
| Single agent | 45% | 100% | 100% | 58% | 89% | 100% | 33% | 100% | 7.1 | 66 |
| Multi-agent (Taxot) | **100%** | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 19.8 | 244 |

**Why the pipeline fails** (per-row evidence in `pipeline_baseline_*.json`):

1. **The whole request never reaches the calculator.** The intent classifier labels a multi-part request
   (form + regime + what to do) as general Q&A, so it gets 0% on every tax figure.
2. **Its calculator parser drops inputs.** In S21 the taxable income it used was salary minus the standard
   deduction. The ₹5,400 interest and the 80TTA deduction stated in the question were ignored, giving
   ₹1,25,840 instead of ₹1,26,963. The same bug affects live `/ask` users and is logged for a fix outside
   Phase 8.
3. **ITR answers name every form.** Extractive answers paste the whole eligibility passage (ITR-1, 2, 3 and 4
   in S20), so the user still does not know which form to file.
4. **What it structurally cannot do:** read documents (0% findings), ask for missing facts, or run what-if
   savings scenarios (0% savings).

With LLM generation (qwen2.5:3b on the VPS) point 3 would probably improve. Points 1, 2 and 4 would not.

**Single agent vs multi-agent.** The single agent picked the right form and regime every time it answered, and
reported every document finding. It failed on three things the multi-agent design takes away from the LLM:

1. **Calculator inputs (5 of 12 tax figures wrong).** It filled `calculate_tax` itself and dropped deductions:
   80TTA in S21 and S23 (₹1,685 off in S21), 80TTB and senior 80D in S33, plus the surcharge case S25 and the
   44ADA case S26. In Taxot the figures step builds these inputs deterministically from documents and facts, with
   provenance, and specialists cannot change them.
2. **Escalation (2 misses).** It answered S35 (short-term gains on shares) and S40 (F&O losses) itself instead of
   escalating, and never called `write_ca_summary`. Taxot's escalation decision is a rule check on the facts, not
   a model judgement.
3. **Running out of steps (4 tasks gave no answer).** S28 (small equity LTCG) and three of the six tax-saving
   tasks (S29, S31, S32) used all 20 steps after `parse_document` and `cross_check_documents`, never reaching
   `calculate_tax` or submitting. Of the three tax-saving tasks that did answer, only S34 had the right best
   option and saving. Taxot gives the what-if search to a specialist with its own budget.

The price is cost: Taxot used about 2.8× the LLM calls (19.8 vs 7.1), 1.4× the tokens and 3.7× the median time
(244 s vs 66 s). The verifier and the planner's question-asking turns account for most of the difference.
No specialist answer needed correcting by reconciliation in this run (`agent_answers_corrected` 0). The
guarantee still held, but it was not exercised.

## Comparison 2: with vs without the verifier

Counts from iteration 2 (229 claims over 22 filing and tax-saving tasks). "Without" is the number of
unsupported claims in the agents' first drafts: what the user would have seen with no verifier.

| | Without verifier | With verifier |
|---|---|---|
| Unsupported claims shown to the user unmarked | 33 of 229 (14%) | 0: 17 fixed by revision, 16 removed or flagged "confirm with a CA" |
| Planted unsupported claims caught | n/a | 100% (removed 95%) |
| False alarms on clean drafts | n/a | 11% |
| Extra LLM calls per task | 0 | about 9 (filing prep: 20.8 vs 11.7 in iteration 0, before the verifier) |

## Iterations

| Iter | Date | Change | Filing prep: success / LLM calls / tokens / median s | Notes |
|---|---|---|---|---|
| 0 | 17 Nov | Phase 5–6 system (verifier added in Phase 6) | 100% / 11.7 / 35k / 68 s (run before the verifier existed) | Tax-saving 6/6 with the verifier |
| 1 | 25 Nov | Same code, full re-run with the verifier on | **87.5%** / 17.4 / 52k / 187 s | Exposed the 4 bugs below |
| 2 | 25–26 Nov | Fixes 1–4 | **100%** / 20.8 / 65k / 265 s | Tax-saving 6/6. `judge_missing` 0 on every task. 29 of 162 filing claims failed at first, 15 remained flagged |

### Error analysis (iteration 1)

| # | Symptom | Root cause | Fix | Check |
|---|---|---|---|---|
| 1 | Verifier marked 95/108 claims unsupported, revised none, and deleted correct sentences (P20: 12/12 failing) | Reasoning models used the whole output budget. The judge (1,500 tokens) returned a truncated or empty `Verdicts` call in 25/53 calls, and a claim with no verdict defaulted to "unsupported". No 429/402 errors were logged, so the provider log looked clean | Verifier role budget raised to 4,000 (`TAXOT_VERIFIER_MAX_TOKENS`). Judge runs in batches of 6 claims, retries claims with no verdict, and reports `judge_missing` | Iteration 2: `judge_missing` 0 on every task so far |
| 2 | Flagged claims were never corrected (`revised_texts` 0 on all 16 tasks) | The reviser (planner model) returned `finish_reason=length` with no tool call: it ran out of tokens while reasoning | `provider.chat(max_tokens=…)` per-call override; the reviser gets 4,000 | Live test: a planted "80C up to ₹2,00,000" was rewritten to ₹1,50,000. Iteration 2 tasks show `revised_texts` ≥ 1 |
| 3 | P28 (₹90,000 LTCG on equity funds, should stay ITR-1) was escalated as capital gains and given ITR-2 | The screening questions never asked for `ltcg_112a`. The user's answer had no matching field, so the extractor filed it under `other_capital_gains` ("property, gold, debt funds") | `ltcg_112a` added to the screening questions. Capital-gains field descriptions now say which is which | P28 passes |
| 4 | P24 (two employers) old-regime tax ₹1,95,624 instead of ₹1,61,928 | The user gave the annual HRA exemption (₹3,36,000), but only basic, HRA and metro were in the question's schema, so the figure was lost and a lower Form 16 value (₹2,28,000) was used | `hra_exemption_annual` is offered alongside basic and HRA | P24 passes, exact tax |

**Lesson:** iteration 0's 100% was partly luck in how the models answered. Bugs 3 and 4 depend on how the LLM maps
free text to fields, and bugs 1 and 2 depend on how long a reasoning model thinks. Re-running the full suite
after unrelated changes is what exposed them. Results that look implausible (everything failing, nothing
revised) should first be checked against `output_tokens == max_tokens` in `logs/llm_usage.jsonl`.

### Evaluation tooling changes

- `scripts/build_scenarios.py` → `data/eval/scenarios.jsonl` (the plan's scenario set).
- `experiments/run_single_agent_eval.py` and `experiments/run_pipeline_baseline.py`: the baselines.
- `experiments/run_agent_eval.py`: roll-up, targets table, comparisons, MLflow.
- The task and single-agent evals save after every task and accept `--resume`. A run killed when the session
  ended had lost 8 finished tasks.

## Remaining limitations

- Free-tier variance: the same code can score differently on different days. Each number above comes from one
  run. Repeating the final configuration on another day is planned before the report is frozen.
- The NLP baseline ran without LLM generation (see Comparison 1).
- The synthetic personas cover the planned cases only. Real documents from other employers' Form 16 layouts
  are untested.
