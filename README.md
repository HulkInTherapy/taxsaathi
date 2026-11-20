# Taxot — GST & Income-Tax Copilot

**Ask an Indian tax question in English or Hinglish → get a short answer where every sentence
cites the official rule it came from, using the law that applied *on the date you asked about*.**
Numbers come from a calculator, never from the AI. If it isn't sure, it says so and sends you to a CA.

4th-year NLP course project · milestones **M1–M3** done (problem brief, data prep, baseline + experiments) ·
**M4 agents** done: three multi-agent workflows that read your documents and do the work, evaluated in
[`docs/M4_agent_experiment_log.md`](docs/M4_agent_experiment_log.md).

🔴 **Live demo:** http://167.86.114.152:8000  (tabs: Ask · Plain LLM vs Taxot · Calculator · Tasks · Experiments · How it works)

---

## Start here (for teammates)

| You want to… | Open |
|---|---|
| Understand the whole thing with zero NLP background | [`docs/EXPLAINED_SIMPLY.md`](docs/EXPLAINED_SIMPLY.md) |
| Present it | [`presentation/Taxot.pptx`](presentation/Taxot.pptx) (speaker notes on every slide) |
| Prepare for the viva + demo script | [`docs/viva_prep.md`](docs/viva_prep.md) |
| M1 — problem & business case | [`docs/M1_problem_brief.md`](docs/M1_problem_brief.md) |
| M2 — data card, EDA | [`docs/data_card.md`](docs/data_card.md), [`docs/eda.md`](docs/eda.md) |
| M3 — experiment log & results | [`docs/M3_experiment_log.md`](docs/M3_experiment_log.md) |
| M4 — agents: plan, experiment log | [`docs/AGENTIC_PLAN.md`](docs/AGENTIC_PLAN.md), [`docs/M4_agent_experiment_log.md`](docs/M4_agent_experiment_log.md) |
| Demo script (Ask + Tasks) | [`docs/DEMO_CHEATSHEET.md`](docs/DEMO_CHEATSHEET.md) |
| Research-paper-style report | [`docs/report_draft.md`](docs/report_draft.md) |
| Literature review (20 real papers) | [`docs/related_work.md`](docs/related_work.md) |
| Where every tax fact came from | [`docs/research/`](docs/research/) |

## How it works (one picture)

```
OFFLINE (once)                                   ONLINE (every question, same fixed steps)
official docs ──► split by legal section ──►     question ─► hide PAN/phone ─► Hinglish → English
tag each piece with law + dates + URL ──►        ─► intent? (question / calculation / out-of-scope)
BM25 keyword index  +  embedding index           ─► which period? (FY 2024-25, Aug 2025, now…)
                                                 ─► keyword search + meaning search ─► merge (RRF)
                                                 ─► drop passages from the wrong period
                                                 ─► reranker confidence ─► safety gate (refuse → CA)
                                                 ─► calculator (if numbers)  ─► local LLM writes answer
                                                 ─► citation check (drop unsupported sentences) ─► answer
```

| Piece | What we use | Why (one line) |
|---|---|---|
| Knowledge base | 106 passages from 17 official sources (Income-tax Act 2025/1961, CBIC/GST Council) | Every answer must point to a real rule |
| Keyword search | BM25 (`rank_bm25`) | Finds exact terms like "80C", "ITR-4" |
| Meaning search | `intfloat/multilingual-e5-small` | Finds paraphrases and Hinglish |
| Merge | Reciprocal Rank Fusion (k=60) | Two judges' rankings → one list |
| Period filter | rule-based date extraction + effective-date metadata | GST on AC was 28% in Aug 2025, 18% now |
| Confidence gate | `BAAI/bge-reranker-base` cross-encoder + TF-IDF/LogReg intent classifier | Refuse when unsure / out of scope |
| Calculator | plain Python, 94 unit tests | LLMs are bad at arithmetic |
| Writer | Groq `gpt-oss-20b` via the provider gateway (fallback Regolo, Gemini); `qwen2.5:3b` via local Ollama with `TAXOT_GEN_BACKEND=ollama` (the M3 measurements) | Explains only; must cite every sentence |

## Agents (M4): the Tasks tab

The Ask tab answers one question. The **Tasks** tab does a job: upload Form 16 / AIS / interest certificates
(or pick a sample taxpayer), and a team of agents works through it, asks you only what is missing, and stops
for your approval at every decision.

| Workflow | What you get |
|---|---|
| **Check my documents** | Every figure extracted, documents cross-checked (interest missing from Form 16, TDS mismatches, 80C over the cap, PAN mismatch, two employers), instructions hidden in documents flagged and ignored |
| **Prepare my return** | ITR form, both regimes computed and the cheaper one recommended, GST check for freelancers, a filing checklist; complex cases (capital gains, foreign assets, F&O, directors…) go to a CA with a case summary |
| **Save tax legally** | What-if scenarios over your remaining 80C / 80D / NPS room, best option and exact rupee saving |

```
           ┌──────────── Orchestrator (LangGraph, planner LLM) ────────────┐
documents ─► Document agent ─► figures (deterministic, with provenance) ─► you approve
           │   Income-tax agent · GST agent · Calculator agent · Escalation check
           │   Verifier agent (other model family): every claim checked, fixed or flagged
           └─► approvals (figures, regime, plan, checklist) ─► answer / CA summary
```

Safety by design: tax figures, ITR rules and cross-checks are plain Python (the LLM never does arithmetic);
PII is masked before any LLM call; documents are data, never instructions; at most 15 tool calls and
2 verifier rounds per task. LLMs are free-tier cloud APIs (NVIDIA NIM first, then Regolo, Groq, Gemini,
OpenRouter), keys in `.env` (see `.env.example`). The Ask tab's answer writer uses the same gateway (role `writer`).

**Results (59 synthetic tasks, M4 log):** task success 100% (target ≥ 80%), tool-call accuracy 100%,
verifier catch rate 100% on planted claims, escalation 100%, injection resistance 100%. On the same 22
filing / tax-saving tasks: NLP pipeline 4.5%, single agent with all tools 45%, Taxot 100%, at about 2.8× the
LLM calls of the single agent (median ≈ 4 min per task).

```bash
cp .env.example .env                                   # add at least one API key
python -m experiments.run_doc_eval --workers 1        # document check, 37 personas
python -m experiments.run_task_eval --workflow filing_prep --workers 1 --resume
python -m experiments.run_task_eval --workflow tax_saving --workers 1 --resume
python -m experiments.run_verifier_eval                # planted unsupported claims
python -m experiments.run_single_agent_eval --resume   # baseline
python -m experiments.run_pipeline_baseline --mode decomposed   # NLP-pipeline baseline
python -m experiments.run_agent_eval                   # targets + comparisons -> summary.json, MLflow
```

Run evaluations with `--workers 1`: parallel runs exhaust the free tiers and produce misleading failures.

## Repository

```
data/raw/curated/      knowledge base source files (one per official document)
data/processed/        chunks.jsonl, intent model, tuned threshold
data/eval/             gold.jsonl (176 Qs), splits.json (53 dev / 123 test), intent_train.jsonl, scenarios.jsonl (40 agent tasks)
data/synthetic/        40 fictitious taxpayers: PDFs + ground truth
src/                   ingest · nlp (hinglish, dates, entities) · retrieval · guardrails · calculator · generation · pipeline · api
src/agents, src/tools   orchestrator graph, specialists, verifier, figures · tool registry (M4)
src/llm/               provider gateway: masking, rate limits, fallback, usage log
app/static/            demo web UI (no build step)
experiments/           run_experiments.py, results.json, MLflow runs
scripts/eda.py         EDA figures → docs/figures
tests/                 pytest (calculator hand-worked cases, NLP utils, guardrails)
presentation/          Taxot.pptx / .pdf + build_deck.py
deploy/                systemd unit (keys from /opt/taxot/.env)
```

## Run it (VPS: /opt/taxot, Ubuntu, 4 vCPU / 8 GB, no GPU)

```bash
make setup                     # venv + CPU torch + requirements
ollama pull qwen2.5:3b         # optional: only with TAXOT_GEN_BACKEND=ollama (M3 setup)
make ingest                    # data/raw/curated/*.md -> data/processed/chunks.jsonl
make train-intent              # intent classifier
make test                      # pytest
cp .env.example .env           # agent API keys (Tasks tab); optional for Ask
make serve                     # API + UI on :8000   (deployed as systemd service `taxot`)
curl -s localhost:8000/health  # status ok/degraded + which LLM providers answer
python -m src.pipeline "80C ki limit kya hai?" --config C6     # one question from the CLI
```

Experiments (M3):

```bash
make eda                                   # docs/figures + docs/eda.md
python -m experiments.run_experiments      # retrieval/refusal metrics, dev set, B1..C6
python -m experiments.run_experiments --generate --configs B0,B1,C1,C2,C3,C4,C5,C6   # + LLM answers
mlflow ui --backend-store-uri experiments/mlruns
```

The 70% test split is deliberately **untouched** — it is reserved for the final numbers in M4.

## Results (dev set, 53 questions)

<!-- RESULTS -->

## Honest limitations

- The knowledge base is a curated set of faithful summaries of official documents (not the full Acts); 71/106 passages verified directly against official sources, the rest against reputable secondary sources (`verified: partial`).
- The gold questions were written by the team and are not yet reviewed by a CA.
- M3 answer-quality numbers were measured with the small local `qwen2.5:3b` (10–40 s per answer on CPU). With the hosted writer now used live, C6 scores 79% key facts (was 69%) at an 8.1 s median, citations still 100% valid (`experiments/results_api_writer.json`); on free tiers about 15% of answers fall back to the extractive answer when the writer is rate-limited.
- Not affiliated with the Income Tax Department (whose own assistant is called "Kar Saathi"). Not professional advice.
