# TaxSaathi — GST & Income-Tax Copilot

**Ask an Indian tax question in English or Hinglish → get a short answer where every sentence
cites the official rule it came from, using the law that applied *on the date you asked about*.**
Numbers come from a calculator, never from the AI. If it isn't sure, it says so and sends you to a CA.

4th-year NLP course project · milestones **M1–M3** done (problem brief, data prep, baseline + experiments).

🔴 **Live demo:** http://167.86.114.152:8000  (tabs: Ask · Plain LLM vs TaxSaathi · Calculator · Experiments · How it works)

---

## Start here (for teammates)

| You want to… | Open |
|---|---|
| Understand the whole thing with zero NLP background | [`docs/EXPLAINED_SIMPLY.md`](docs/EXPLAINED_SIMPLY.md) |
| Present it | [`presentation/TaxSaathi.pptx`](presentation/TaxSaathi.pptx) (speaker notes on every slide) |
| Prepare for the viva + demo script | [`docs/viva_prep.md`](docs/viva_prep.md) |
| M1 — problem & business case | [`docs/M1_problem_brief.md`](docs/M1_problem_brief.md) |
| M2 — data card, EDA | [`docs/data_card.md`](docs/data_card.md), [`docs/eda.md`](docs/eda.md) |
| M3 — experiment log & results | [`docs/M3_experiment_log.md`](docs/M3_experiment_log.md) |
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
| Writer | `qwen2.5:3b` via Ollama (local, free, CPU) | Explains only; must cite every sentence |

## Repository

```
data/raw/curated/      knowledge base source files (one per official document)
data/processed/        chunks.jsonl, intent model, tuned threshold
data/eval/             gold.jsonl (176 Qs), splits.json (53 dev / 123 test), intent_train.jsonl
src/                   ingest · nlp (hinglish, dates, entities) · retrieval · guardrails · calculator · generation · pipeline · api
app/static/            demo web UI (no build step)
experiments/           run_experiments.py, results.json, MLflow runs
scripts/eda.py         EDA figures → docs/figures
tests/                 pytest (calculator hand-worked cases, NLP utils, guardrails)
presentation/          TaxSaathi.pptx / .pdf + build_deck.py
deploy/                systemd unit
```

## Run it (VPS: /opt/taxsaathi, Ubuntu, 4 vCPU / 8 GB, no GPU)

```bash
make setup                     # venv + CPU torch + requirements
ollama pull qwen2.5:3b         # local LLM
make ingest                    # data/raw/curated/*.md -> data/processed/chunks.jsonl
make train-intent              # intent classifier
make test                      # pytest
make serve                     # API + UI on :8000   (deployed as systemd service `taxsaathi`)
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
- Small CPU-only LLM → answers take ~10–40 s and wording is sometimes clumsy.
- Not affiliated with the Income Tax Department (whose own assistant is called "Kar Saathi"). Not professional advice.
