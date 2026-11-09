# M3 Experiment Log — TaxSaathi (B0 → C6)

Hypotheses were written before the runs (see `M3_experiment_log_template.md`, kept unchanged).
All numbers are on the **dev split (53 questions)**; the 70% test split is untouched and reserved for M4.
Every run is in MLflow (`experiments/mlruns`, experiment `taxsaathi-m3`) and `experiments/results.json`.

## Common setup

| Item | Value |
|---|---|
| Hardware | VPS, 4 vCPU (AMD EPYC), 8 GB RAM, no GPU |
| LLM | `qwen2.5:3b` via Ollama (Q4_K_M), temperature 0, top-3 passages shown |
| Embedder / reranker | `intfloat/multilingual-e5-small` / `BAAI/bge-reranker-base` |
| Knowledge base | 107 chunks from 17 sources (72 verified against official pages) |
| Gold set | 176 questions; dev 53 / test 123; stratified by category, seed 42 |
| Refusal threshold θ | −5.834 (reranker logit), tuned on dev |
| Intent classifier | TF-IDF + logistic regression, 342 training rows (no gold/real questions), 5-fold CV 0.90 |
| Calculator tests | 99 pytest tests incl. hand-worked cases; 16/16 gold calculations exact |

## Results by config

| Config | What changed | Hypothesis (before) | Result | Conclusion |
|---|---|---|---|---|
| **B0** | LLM alone, no retrieval | Lowest key-fact accuracy; outdated answers | Key-fact acc **0.104**; never cites; 0% out-of-scope refused | Confirmed. The LLM states pre-2025 rules. Retrieval is necessary. |
| **B1** | + BM25 top-5, grounded generation | Big jump over B0; weak on paraphrase/Hinglish | Recall@5 0.812, MRR 0.730, key-fact 0.646, citation validity 1.00 | Confirmed: ×6 key facts. Lowest recall on calculation/income-tax paraphrases. |
| **C1** | Dense embeddings only | Better on paraphrase, worse on exact sections | Recall@5 0.875 but MRR 0.680 and **period acc 0.75** | Partly confirmed. Embeddings blur "Aug 2025" vs "now". |
| **C2** | BM25 + dense, RRF (k=60) | Best of both | Recall@5 0.839, **MRR 0.755**, period 0.875, key-fact 0.604 | Best ranking of the single-stage systems; still falls for some time traps. |
| **C3** | + cross-encoder reranks top-20 | Biggest single gain | Recall@5 0.804, MRR **0.656** (↓) | **Rejected.** The English/Chinese reranker promotes related or wrong-period passages. |
| **C4** | + date filter | Fixes time traps | Period acc **1.000**, Recall@5 0.861, key-fact 0.688 | Confirmed. |
| **C5** | + Hinglish normalisation | Helps Hinglish | Same retrieval as C4 on dev (Hinglish recall already 1.0 on 4 dev Qs) | Inconclusive on dev (n=4); kept because it costs nothing and makes the trace readable. |
| **C6 (final)** | C5, but the reranker only gates refusals (fusion order kept) + period substitution | Recover the ranking lost in C3 | **Recall@5 0.917, MRR 0.830, nDCG@5 0.831**, period 1.000, key-fact 0.688, citation validity 1.00, faithfulness 1.00, p50 16.8 s | Best overall. Chosen as the final system. |

## Other decisions logged

- **Refusal threshold** swept on dev (`--tune-threshold`). All 5 dev out-of-scope questions are already caught by the intent classifier, so we picked the middle of the equally good range to avoid an effectively disabled gate.
- **Multilingual reranker** `bge-reranker-v2-m3`: ~25 s per query on CPU, so the run was stopped. Left for M4 with GPU/quantisation.
- **Passages shown to the LLM** reduced from 5 to 3 to cut CPU latency (prompt processing ≈ 66 tokens/s). Retrieval metrics are still @5.
- **Fixes after running real-world questions** (all regression-tested on dev with no metric drop):
  - currency and per-month amount parsing;
  - freelancer income under s.58 / 44ADA in the calculator;
  - calculator-only verdicts in calculation answers;
  - dropping "not covered" and "the passage mentions" filler;
  - period substitution in the date filter;
  - an explainer passage for the "₹12 lakh vs 5% slab" confusion.

## Real-world check (not used for tuning)

80 real questions from Reddit, Quora, CAclubindia and official FAQs (`data/eval/real_questions.jsonl`):
- **Coverage:** 64% fully covered by the knowledge base, 23% partly, 14% not at all.
- **Retrieval on the 51 fully covered questions:**
  - C6: Recall@5 0.62 by exact passage, 0.78 at rule level.
  - C2: 0.86. The gap is mostly temporal labelling: 2025 posts are labelled with FY 2025-26 passages, while C6 answers with today's law.
- **Out-of-scope:** only 57% of the real out-of-scope questions were refused, a known weakness for M4.

## Next (M4)

- Run the frozen C6 once on the test split.
- Error analysis by category.
- LLM-judge faithfulness.
- Faster serving (GPU or API).
- CA review of 30–50 gold answers.
