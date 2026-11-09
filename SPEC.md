# TaxSaathi — build spec (shared contract for everyone working on this repo)

TaxSaathi answers Indian income-tax and GST questions in English and Hinglish, cites the
official source for every claim, is aware of which law applies to which period, refuses /
escalates to a CA when unsure, and computes tax with a deterministic calculator (never the LLM).
This is a 4th-year NLP course project. Scope = milestones M1–M3 (problem brief, data prep,
baseline + experiments B0–C5) plus a demo web app and a presentation.

"Today" for the system = 2026-10-29. Current income-tax law = Income-tax Act, 2025 (in force
1 Apr 2026, "Tax Year 2026-27"). Income earned up to 31 Mar 2026 = Income-tax Act, 1961.
GST 2.0 rates in force from 22 Sep 2025.

Code runs on a Linux VPS (4 vCPU, 8 GB RAM, no GPU) in /opt/taxsaathi; it is authored on the
Mac in ~/taxsaathi and rsynced. Python 3.12. Local LLM via Ollama (http://127.0.0.1:11434),
model `qwen2.5:3b` or `qwen2.5:1.5b` (env TAXSAATHI_LLM). Embeddings `intfloat/multilingual-e5-small`
(prefix "query: " / "passage: "). Reranker `BAAI/bge-reranker-base` (CrossEncoder).

## Repository layout

```
taxsaathi/
├── data/raw/curated/*.md      # knowledge base source files (format below)
├── data/processed/chunks.jsonl# produced by `python -m src.ingest.ingest`
├── data/eval/gold.jsonl       # gold Q&A set (format below)
├── data/eval/intent_train.jsonl # intent classifier training data (separate from gold!)
├── data/eval/splits.json      # dev/test ids (30/70 stratified)
├── src/ingest/                # parse curated md (+ optional PDFs via PyMuPDF), chunk, metadata
├── src/retrieval/             # bm25.py dense.py hybrid.py reranker.py date_filter.py
├── src/nlp/                   # hinglish.py (normaliser), dates.py (period extraction), entities.py (section numbers, amounts)
├── src/guardrails/            # intent.py (TF-IDF+LogReg), refusal.py, pii.py, citation_check.py
├── src/generation/            # llm.py (ollama client), prompts.py, generate.py
├── src/calculator/            # tax.py (deterministic), parse.py (query → inputs)
├── src/pipeline.py            # TaxSaathi.ask(question, config) -> AnswerResult with full trace
├── src/api/main.py            # FastAPI: /ask /compare /calculate /health /experiments /kb/stats; serves app/static
├── app/static/                # demo web UI (index.html, app.js, style.css) — no build step
├── experiments/run_experiments.py  # B0–C5 on dev set, logs to MLflow + experiments/results.json
├── notebooks/ or scripts/eda.py    # EDA → docs/figures/*.png + docs/eda.md
├── docs/                      # M1 brief, data card, experiment log, explainers, research
├── tests/                     # pytest (calculator hand-worked examples!)
└── presentation/              # .pptx
```

## Knowledge-base file format (data/raw/curated/*.md)

Each file = one source document. YAML-ish front matter, then one `##` block per chunk.

```
---
doc_id: it25_regime
source_title: Income-tax Act, 2025 — Section 202 (new tax regime) as amended by Finance Act 2026
source_url: https://incometaxindia.gov.in/...
publisher: Income Tax Department, Government of India
law: new_act            # one of: new_act | old_act | gst | mapping | general
doc_type: act           # act | rules | notification | circular | faq | budget | mapping
downloaded: 2026-10-29
---

## [IT25-202-SLABS] Section 202 — New tax regime slab rates (Tax Year 2026-27)
section: 202
effective_from: 2026-04-01
effective_to:
topic: slabs
verified: yes           # yes = confirmed against an official/primary source; partial = secondary sources only

Passage text in plain English, 60–220 words, faithful to the law, with concrete numbers.
One idea per chunk. Mention the section number and the period it applies to in the text.
```

Rules: chunk IDs are unique, UPPERCASE, stable. `effective_from`/`effective_to` are ISO dates or
empty (= open-ended). A chunk is eligible for a query period if the date ranges overlap.

## chunks.jsonl (one JSON per line)

`{"id","doc_id","title","text","section","law","doc_type","topic","effective_from","effective_to",
"source_title","source_url","publisher","verified","n_tokens"}`

## Gold set format (data/eval/gold.jsonl)

`{"id":"Q001","question":"...","reference_answer":"...","gold_chunk_ids":["IT25-202-SLABS"],
"category":"income_tax|gst|time_trap|calculation|out_of_scope|hinglish","language":"en|hinglish",
"difficulty":"easy|medium|hard","answerable":true,"key_facts":["75,000"],"intent":"question|calculation|out_of_scope"}`

`key_facts`: short strings (numbers, form names, section numbers) that a correct answer must
contain; matched case-insensitively after removing ₹, commas and spaces.

## Intent training data (data/eval/intent_train.jsonl)

`{"text":"...","label":"question|calculation|out_of_scope"}` — ~300 rows, English + Hinglish,
MUST NOT copy gold questions (leakage).

## Pipeline (fixed, same order every query)

1. PII scrub (PAN `[A-Z]{5}[0-9]{4}[A-Z]`, Aadhaar 12 digits, phone) — for logs.
2. Hinglish normalisation (dictionary + rules; detects language).
3. Intent classification → question | calculation | out_of_scope.
4. Period extraction (FY/AY/Tax Year/month-year/"before GST 2.0"/"last year") → [start,end]; default = today, flagged "assumed current law".
5. Section-number entity recognition (e.g. "80C") → mapping lookup boost.
6. Retrieval: BM25 + dense → RRF (k=60) → date filter → top-20 → cross-encoder rerank → top-5.
7. Guardrail gate: out_of_scope intent OR top rerank score < threshold → refuse + CA escalation.
8. Calculation intent: parse salary/deductions → calculator (missing salary → follow-up question).
9. Grounded generation with passage IDs `[CHUNK-ID]`; LLM explains, never computes.
10. Citation check: drop sentences with no/invalid citation; fallback to extractive answer.
11. Disclaimer appended. Full trace returned for the demo UI.

Configs (experiments): B0 LLM alone · B1 BM25 top-5 · C1 dense top-5 · C2 hybrid RRF ·
C3 hybrid top-20→rerank→top-5 · C4 C3+date filter · C5 C4+Hinglish normalisation.

## API contract (FastAPI, port 8000)

- `GET /health` → `{"status":"ok","llm":"qwen2.5:3b","chunks":N}`
- `POST /ask` `{"question":str,"config":"C5"}` →
  ```
  {"answer":str, "refused":bool, "refusal_reason":str|null, "follow_up":str|null,
   "citations":[{"id","title","section","source_title","source_url","effective_from","effective_to","text"}],
   "calculation": <calculator result or null>,
   "disclaimer":str, "latency_ms":int, "config":str,
   "trace":[{"step":"pii|hinglish|intent|period|entities|bm25|dense|fusion|date_filter|rerank|gate|calculator|generate|citation_check",
             "label":str, "summary":str, "ms":int, "data":{...}}]}
  ```
  trace data examples: hinglish `{"original","normalised","language","replaced":[["kitna","how much"]]}`;
  intent `{"label","probs":{"question":0.9,...}}`; period `{"start","end","reason","assumed_current":bool}`;
  bm25/dense/fusion/rerank `{"results":[{"id","title","score"}]}`; date_filter `{"before":20,"after":14,"removed":[ids]}`;
  gate `{"passed":bool,"top_score":float,"threshold":float}`; citation_check `{"kept":n,"dropped":n,"invalid_ids":[]}`.
- `POST /compare` `{"question"}` → `{"plain": <B0 result>, "taxsaathi": <C5 result>}`
- `POST /calculate` `{"gross_salary":int,"deductions_80c":int,"deductions_80d":int,"hra_exemption":int,
  "home_loan_interest":int,"nps_80ccd1b":int,"other_deductions":int,"employer_nps":int,"age":"below60|60to80|above80",
  "tax_year":"2024-25|2025-26|2026-27","salaried":true}` →
  `{"old":{"gross","std_deduction","deductions","taxable","slab_tax","rebate","surcharge","cess","total","slabs":[{"from","to","rate","tax"}]},
    "new":{...same...}, "better":"old|new|same", "saving":int, "law":"Income-tax Act, 2025 s.202 / ...", "notes":[str]}`
- `GET /experiments` → contents of experiments/results.json
- `GET /kb/stats` → chunk counts per law/topic, sources list
