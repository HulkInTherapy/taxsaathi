# TaxSaathi: Period-Aware, Citation-Grounded Retrieval-Augmented QA for Indian Income Tax and GST in English and Hinglish

*Technical report, milestones M1–M3 · 2026-10-29 · TaxSaathi team (4th-year NLP course project)*

---

## Abstract

Indian taxpayers rely heavily on chartered accountants (CAs) for routine questions, and two recent law
changes made this worse: the Income-tax Act, 2025 (in force 1 April 2026, introducing the "Tax Year")
and the GST rate rationalisation ("GST 2.0", effective 22 September 2025). A general-purpose LLM cannot
tell which law applies to which period, cannot cite its sources, and makes arithmetic errors. We present
**TaxSaathi**, a retrieval-augmented QA system that (i) accepts English and romanised Hindi–English
(Hinglish), (ii) attaches a verifiable citation with an effective-date range to every claim, (iii)
extracts the period a question refers to and filters the knowledge base to the law in force for that
period, (iv) abstains and escalates to a CA when the question is out of scope or retrieval confidence is
low, and (v) delegates all tax computation to a deterministic, unit-tested calculator. Everything runs
on a 4-vCPU CPU-only server: hybrid BM25 + multilingual-E5 retrieval fused with Reciprocal Rank Fusion,
a rule-based period filter, a cross-encoder used as a confidence gate, and a small local LLM
(Qwen2.5-3B) that only phrases grounded explanations. On a 53-question development set, the final configuration (C6) reaches Recall@5 0.917 and MRR 0.830, answers every time-sensitive question with the law in force for the asked period, refuses 100% of out-of-scope questions with 2% false refusals, computes tax with 100% exact match, and raises key-fact accuracy from 10.4% (the same LLM without retrieval) to 68.8% with every citation valid. On 80 real questions collected from public forums and official FAQs, it retrieves the right rule for 78% of covered questions.

---

## 1 Introduction

India's direct-tax base is large: about 8.5 crore individual taxpayers (CBDT Chairman, Feb 2025) filed
a record 7.8 crore+ returns for AY 2026-27 by 31 Aug 2026, and there are 1.67 crore active GST
registrations (GSTN, 30 June 2026); sources in `M1_problem_brief.md`. Most questions from this
population are routine, yet answering them usually means paying a CA or trusting unsourced content.

Tax QA is a demanding NLP testbed for three reasons:

1. **The answer depends on the period.** From 1 April 2026 the Income-tax Act, 2025 replaces the 1961
   Act; GST rates changed on 22 September 2025 to a 5% / 18% / 40% structure. The same question has
   different correct answers for different dates — a known weakness of QA systems (Zhang & Choi, 2021;
   Chen et al., 2021).
2. **Fluent wrong answers are costly.** Even commercial legal RAG tools hallucinate 17–33% of the time
   (Magesh et al., 2025).
3. **Users code-mix.** Many write Hinglish ("80C mein kitna milta hai?"), where standard models
   underperform (Khanuja et al., 2020).

**Contributions.** (1) A period-aware RAG pipeline: symbolic period extraction plus an interval-overlap
filter over chunk-level `effective_from`/`effective_to` metadata. (2) A safety layer suited to a small
model: intent classifier + reranker-score gate for abstention, post-hoc citation validation with numeric
faithfulness checks and extractive fallback, PII scrubbing, and a mandatory disclaimer. (3) A
deterministic tax calculator for both regimes and three tax years; the LLM explains but never computes.
(4) An evaluation protocol with targets fixed in advance, a leakage-controlled split, and an ablation
ladder (B0 → C6) that isolates each component.

## 2 Related Work (full review: `related_work.md`)

**Retrieval.** BM25 (Robertson & Zaragoza, 2009) remains a strong lexical baseline; dense dual encoders
(DPR; Karpukhin et al., 2020) and contrastively pre-trained embeddings (E5/mE5; Wang et al., 2022, 2024)
capture paraphrase; BGE-M3 (Chen et al., 2024) unifies dense and sparse signals. Reciprocal Rank Fusion
(Cormack et al., 2009) merges rankings without score calibration. Cross-encoder rerankers (Nogueira &
Cho, 2019) trade compute for precision on a short candidate list.
**RAG and attribution.** RAG (Lewis et al., 2020) gives provenance and an updatable memory; ALCE (Gao et
al., 2023) and Liu et al. (2023) show LLM citations are often incomplete; RAGAS (Es et al., 2024)
evaluates faithfulness without references.
**Legal NLP.** CaseHOLD (Zheng et al., 2021), ILDC (Malik et al., 2021), LegalBench-RAG (Pipitone &
Houir Alami, 2024), and hallucination in legal RAG (Magesh et al., 2025).
**Time, code-mixing, abstention, tools.** SituatedQA and TimeQA show temporal brittleness; GLUECoS and
LinCE (Aguilar et al., 2020) benchmark Hindi–English code-switching; Kamath et al. (2020) study
selective QA; PAL (Gao et al., 2023) and Toolformer (Schick et al., 2023) show LLMs should delegate
arithmetic to tools.
**Gap.** We found no open system combining period-aware retrieval, Hinglish input, citation validation,
abstention and deterministic computation for Indian tax law, nor a public Indian tax-QA benchmark.

## 3 Problem and Users

**Task.** Given a question *q* (English or Hinglish) and an implicit or explicit period, return (a) a
grounded answer whose every sentence cites a passage valid for that period, (b) a calculator result plus
explanation, (c) a follow-up question when inputs are missing, or (d) a refusal with CA escalation.

**Personas** (M1 §4): P1 salaried first-jobber with Form 16; P2 freelancer / content creator; P3 small
shop owner (composition scheme, period-correct GST rates, Hinglish).

**Success criteria fixed before building:** Recall@5 ≥ 0.85; faithfulness ≥ 0.90; correct refusal ≥ 90%
on out-of-scope; calculator exact match 100%; median latency ≤ 5 s (assumes GPU/API serving; CPU actuals
reported).

## 4 Data

### 4.1 Knowledge sources
A curated corpus of **107 passages from 17 official source documents** (`data/raw/curated/*.md`):
Income-tax Act, 2025 section pages and e-filing help/FAQs (incometaxindia.gov.in, incometax.gov.in),
1961-Act provisions for pre-April-2026 periods, CBIC's CGST Act/Rules/notifications, the PIB release of
the 56th GST Council recommendations, GST portal tutorials, and an old→new section mapping. Every chunk
records `source_url`, `publisher`, `law ∈ {new_act, old_act, gst, mapping, general}`, and a
`verified ∈ {yes, partial}` flag (72 yes / 35 partial). See `data_card.md`.

*Why curated summaries rather than raw Acts?* Several official sites block automated download; the
2025 Act is long and heavily cross-referenced, so raw-PDF chunks would mix ideas and dilute retrieval and
citation; and a compact, clean index keeps CPU latency manageable. The ingestion code also supports raw
PDFs (PyMuPDF, section-heading splitting) for future full-text ingestion. The risk that summaries drift
from the statute is listed in §8.

### 4.2 Chunking by legal section
Each chunk is one provision, 64–164 words (median 125), with a stable ID (e.g. `IT-NEW-REBATE-FY2526`).
We chunk by section, not fixed windows, because the citation unit users and CAs understand is a section;
fixed windows split provisos from the rule they qualify; and each chunk states its own section and
period, so it is self-describing out of context.

### 4.3 Temporal metadata
100% of chunks carry `effective_from`, and superseded chunks carry `effective_to`. A chunk is eligible
for a query period [s, e] iff `effective_from ≤ e` and (`effective_to` is empty or `effective_to ≥ s`).
For example, the new-regime slab passages exist in three versions (FY 2024-25, FY 2025-26, Tax Year
2026-27) and each GST rate group has a pre- and post-22-Sep-2025 passage.

### 4.4 Gold set
176 questions written from the personas (not from the chunks): income_tax 60, gst 42, time_trap 26,
calculation 18, out_of_scope 18, hinglish 12. Each has a reference answer, gold chunk IDs, `key_facts`
(short strings a correct answer must contain), category, language, difficulty and intent. Time traps ask
the same thing for different periods; calculation answers were hand-worked and cross-checked against the
calculator (one disagreement, about the 80D cap for parents, was traced to a calculator limitation and
fixed by adding a separate parents' 80D field).

### 4.5 Split and leakage prevention
30% dev (53) / 70% test (123), stratified by category, seed 42. Every tunable choice (refusal threshold,
number of passages, prompt wording, Hinglish dictionary) is made on dev only; **the test split has not
been used** and is reserved for M4. The intent classifier's 324 training rows were written separately and
checked to contain no gold question.

### 4.6 Privacy
No real taxpayer data. A PII scrubber masks PAN, Aadhaar, phone and e-mail before any query is logged.

## 5 System

| # | Step | Implementation | Why |
|---|---|---|---|
| 1 | PII scrub | regex | Log safety |
| 2 | Hinglish normalisation | language detection + ~150-entry dictionary | Map "kitna / milta hai / naye" to English so BM25 and the English-centric reranker can match; every replacement is shown in the trace |
| 3 | Intent | TF-IDF (word 1–2 + char 2–5 grams) + logistic regression, 3 classes; injection regex | Fast, interpretable, trainable on 324 rows (5-fold CV acc. 0.92) |
| 4 | Period extraction | rules for FY/AY/Tax Year/month-year/"before GST 2.0"/"last year"; default = today, flagged *assumed current law* | Temporal reasoning done symbolically |
| 5 | Section entities | regex ("80C", "u/s 44ADA", "115BAC") → mapping-chunk boost | Bridges 1961 ↔ 2025 numbering |
| 6 | Retrieval | BM25 + `multilingual-e5-small` → RRF (k = 60) → date filter → top 20 | Lexical precision + semantic recall |
| 7 | Confidence gate | `bge-reranker-base` scores the top 20; refuse if intent = out_of_scope or best score < θ (θ = −5.83, tuned on dev) | Abstention independent of the generator (Kamath et al., 2020) |
| 8 | Calculator | parse salary/deductions → `calculator/tax.py`; follow-up question if salary missing | Exact arithmetic (99 unit tests incl. hand-worked cases) |
| 9 | Generation | Ollama `qwen2.5:3b`, temperature 0, top-3 passages labelled `[CHUNK-ID]`; "explain, don't compute" | Local, free, private |
| 10 | Citation check | sentence split; a sentence must carry (or be followed in its paragraph by) a valid ID from the retrieved set; for calculations, any amount stated by the LLM must appear in the calculator output or passages; else fall back to an extractive answer | Don't trust LLM citations (Gao et al., 2023) |
| 11 | Disclaimer + trace | fixed text; full JSON trace to the UI | Transparency |

**Final configuration (C6).** In C3–C5 the cross-encoder *reorders* the candidates. On dev this lowered
MRR (§7), so the final system keeps the hybrid + date-filter order and uses the cross-encoder only as the
confidence signal for the refusal gate.

## 6 Experimental Setup

### 6.1 Ablation ladder

| Config | Retrieval | Date filter | Hinglish | Reranker | Generation |
|---|---|---|---|---|---|
| **B0** | none (LLM alone) | – | – | – | plain LLM, no passages |
| **B1** | BM25 top-5 | – | – | – | grounded |
| **C1** | dense (mE5) top-5 | – | – | – | grounded |
| **C2** | BM25 + dense → RRF | – | – | – | grounded |
| **C3** | C2 top-20 | – | – | reorders → top-5, gate | grounded |
| **C4** | C3 | ✓ | – | reorders, gate | grounded |
| **C5** | C4 | ✓ | ✓ | reorders, gate | grounded |
| **C6** | C2 order | ✓ | ✓ | gate only (no reorder) | grounded |

Each step changes one thing. Retrieval/refusal metrics were computed for all configs; LLM-answer metrics
(about 25 s per answer on CPU) for B0, B1, C2, C4 and C6 — the configs that mark each major step. All
runs are logged to MLflow (`experiments/mlruns`) and `experiments/results.json`.

### 6.2 Metrics
Let G_q be the gold chunks of q and R_q^k the top-k retrieved list (answerable questions only).
- **Recall@5** = mean_q |G_q ∩ R_q^5| / |G_q|.
- **MRR@10** = mean_q 1/rank of the first gold chunk (0 if not in top 10).
- **nDCG@5** with binary relevance (Järvelin & Kekäläinen, 2002).
- **Period accuracy** (time traps): the top-1 chunk is valid for the question's period.
- **Refusal accuracy**: refused ⇔ not answerable, over all questions; also **false-refusal rate** on answerable questions.
- **Calculator exact match**: every gold key fact (each regime's total tax and the better regime) appears in the calculator output.
- **Key-fact accuracy**: share of questions whose final answer contains *all* key facts (normalised: lower-case, ₹/commas/spaces removed).
- **Citation validity**: share of cited IDs that were among the passages shown to the LLM.
- **Faithfulness (proxy)**: share of answer sentences kept by the citation check (supported by a valid citation). A cheap CPU stand-in for RAGAS faithfulness; an LLM-judge version is planned for M4.
- **Latency**: end-to-end wall clock per question, p50/p95, on the 4-vCPU VPS.

## 7 Results

### 7.1 Main results (dev set, 53 questions)

| Config | Recall@5 | MRR@10 | nDCG@5 | Period acc. | Refusal acc. | False refusal | Key-fact acc. | Citation valid. | Faithful. (proxy) | p50 latency (s) |
|---|---|---|---|---|---|---|---|---|---|---|
| B0 | — | — | — | — | 0.906 | 0.000 | 0.104 | — | — | 1.4 |
| B1 | 0.812 | 0.730 | 0.708 | **1.000** | **0.981** | 0.021 | 0.646 | **1.000** | 0.987 | 15.4 |
| C1 | 0.875 | 0.680 | 0.710 | 0.750 | **0.981** | 0.021 | — | — | — | — |
| C2 | 0.839 | 0.755 | 0.748 | 0.875 | **0.981** | 0.021 | 0.604 | 0.990 | 0.993 | 47.0 |
| C3 | 0.804 | 0.656 | 0.647 | **1.000** | **0.981** | 0.021 | — | — | — | — |
| C4 | 0.861 | 0.695 | 0.705 | **1.000** | **0.981** | 0.021 | **0.688** | **1.000** | 0.971 | 17.4 |
| C5 | 0.861 | 0.709 | 0.716 | **1.000** | **0.981** | 0.021 | — | — | — | — |
| **C6** | **0.917** | **0.830** | **0.831** | **1.000** | **0.981** | 0.021 | **0.688** | **1.000** | **1.000** | 16.8 |

*Dev split, 53 questions. Latency is end-to-end on a 4-vCPU CPU server with the LLM (configs with generated answers only); C2's 47 s is inflated because it ran concurrently with another evaluation job. — = not applicable / not run with the LLM.*

### 7.2 Per-category breakdown (Recall@5 / key-fact accuracy)

| Config | income_tax | gst | time_trap | hinglish | calculation |
|---|---|---|---|---|---|
| B0 | — / 0.06 | — / 0.23 | — / 0.12 | — / 0.00 | — / 0.00 |
| B1 | 0.78 / 0.39 | 0.92 / 0.77 | 1.00 / 0.88 | 0.75 / 0.50 | 0.40 / 1.00 |
| C1 | 0.92 / — | 0.92 / — | 0.88 / — | 1.00 / — | 0.50 / — |
| C2 | 0.89 / 0.44 | 0.88 / 0.62 | 0.88 / 0.75 | 0.88 / 0.50 | 0.45 / 1.00 |
| C3 | 0.81 / — | 0.88 / — | 0.81 / — | 0.88 / — | 0.52 / — |
| C4 | 0.83 / 0.56 | 0.88 / 0.69 | 1.00 / 0.88 | 1.00 / 0.50 | 0.57 / 1.00 |
| C5 | 0.83 / — | 0.88 / — | 1.00 / — | 1.00 / — | 0.57 / — |
| C6 | 0.92 / 0.50 | 1.00 / 0.77 | 1.00 / 0.88 | 1.00 / 0.50 | 0.50 / 1.00 |

*Cells: Recall@5 / key-fact accuracy. Dev category sizes are small (hinglish 4, time_trap 8, calculation 5), so treat per-category differences as indicative.*

### 7.3 Discussion

**Targets fixed in M1 (dev set, final config C6).** Recall@5 0.917 (target ≥ 0.85 ✅); faithfulness proxy 1.00 (≥ 0.90 ✅); out-of-scope refusal 100% with 2.1% false refusals (≥ 90% ✅); calculator exact match 100% on all 16 hand-worked gold calculations and 99 unit tests (100% ✅); median latency 16.8 s on a 4-vCPU CPU server (≤ 5 s ❌ — dominated by the 3B LLM on CPU; GPU/API serving is M5 work).

1. **Retrieval is what makes the LLM useful.** The same Qwen2.5-3B answering from memory (B0) gets only **10.4%** of key facts right — it states pre-2025 rules (old slabs, ₹7 lakh rebate, 28% GST on ACs) and never cites. Grounded generation lifts this to **64.6%** with BM25 alone (B1) and **68.8%** in C6, with 100% citation validity.
2. **Hybrid beats either retriever alone, but not on every metric.** Dense alone (C1) has higher Recall@5 than BM25 (0.875 vs 0.812) but the worst period accuracy (0.75) — embeddings see "GST on AC in Aug 2025" and "GST on AC now" as the same meaning. BM25 catches exact tokens (section numbers, "August 2025"). RRF fusion (C2) gives the best MRR among single-stage systems (0.755).
3. **The reranker hurt when allowed to reorder.** C3 dropped MRR from 0.755 to 0.656: `bge-reranker-base` (English/Chinese only) often promotes a related passage or the wrong period's version. Keeping the fusion order and using the reranker only as a confidence signal for refusal (C6) gave the best ranking overall (Recall@5 0.917, MRR 0.830, nDCG@5 0.831). The multilingual `bge-reranker-v2-m3` was too slow on CPU (~25 s/query) to test fully.
4. **The date filter fixes time traps.** Period accuracy goes 0.875 (C2) → 1.000 (C4). We further improved it with *period substitution*: when a passage is from the wrong period, the same rule's in-period version takes its place (matched by ID stem or topic), and questions about years before our sources keep the closest version instead of returning nothing.
5. **Hinglish.** On the 4 Hinglish dev questions Recall@5 is already 1.0 from C4; normalisation (C5) mostly improves the reranker/LLM input. Key-fact accuracy on Hinglish (0.50) and long-form income-tax answers (0.50) is the main weakness: the 3B model paraphrases numbers or omits one of several required facts.
6. **Real-world check (80 real questions from Reddit, Quora, CAclubindia and official FAQs).** Our knowledge base fully covers 64%, partly 23%, not at all 14% (8% of in-scope questions). On the 51 fully covered ones, C6 Recall@5 is 0.62 by exact passage and **0.78 at rule level** (any period version of the gold rule), vs 0.86 for C2. Most of the gap is temporal: posts written in 2025 were labelled with FY 2025-26 passages, while C6 deliberately answers with the law in force today (Tax Year 2026-27). Real out-of-scope questions are harder than our synthetic ones: only 57% (4/7) were refused. The most common real confusion ("no tax up to ₹12 lakh but 5% from ₹4 lakh?", 10 posts) exposed a knowledge gap that we closed with an explainer passage.
7. **Error analysis preview (M4).** Remaining misses: (a) the LLM paraphrasing away a required number; (b) calculation questions retrieving old-regime rather than rebate passages (the calculator answer is still exact); (c) regime-switching and filing-procedure questions phrased very differently from our passages.

## 8 Limitations and Ethics

- **Curated summaries, not full Acts.** 35 of 107 chunks are checked only against secondary sources; a summary can omit a proviso that matters to a user.
- **Gold set authored by the team, not CA-reviewed;** the same people wrote corpus and questions, which may inflate retrieval scores. The dev set is small (53), so differences of a few points are within noise.
- **Small CPU LLM.** Qwen2.5-3B on CPU is slow (tens of seconds) and sometimes phrases the period clumsily; we constrain it heavily.
- **English-centric reranker.** `bge-reranker-base` lists only Chinese and English; the multilingual `bge-reranker-v2-m3` took ~25 s per query on our CPU and was not usable.
- **Rule-based period extraction** covers common patterns; anything else falls back to "assumed current law", which is shown to the user.
- **Calculator scope:** salaried individuals, both regimes, FY 2024-25 to Tax Year 2026-27; no capital gains or business income computation.
- **Legal liability.** Informational only; not affiliated with the Income Tax Department (whose own assistant is "Kar Saathi"); every answer carries a disclaimer; notices, disputes and evasion requests are refused with a CA referral.

## 9 Future Work

- **M4:** run the untouched test split once; error analysis by category; LLM-judge faithfulness; GPU or quantised multilingual reranker; CA review of 30–50 gold answers; full-text Act ingestion.
- **M5:** GPU/API generation to meet the 5 s target; Docker deployment; monitoring dashboard from `logs/queries.jsonl` and feedback.
- **M6:** user study with the three personas.
- **Agentic layer:** planner that chooses tools (retriever, calculator, document parser, CA-summary writer) with a verifier agent, keeping the calculator and citation check as hard constraints.

## References

- Aguilar, G., Kar, S., Solorio, T. (2020). LinCE: A Centralized Benchmark for Linguistic Code-switching Evaluation. *LREC 2020*. https://aclanthology.org/2020.lrec-1.223
- Chen, J., Xiao, S., Zhang, P., Luo, K., Lian, D., Liu, Z. (2024). M3-Embedding. *Findings of ACL 2024*. https://aclanthology.org/2024.findings-acl.137
- Chen, W., Wang, X., Wang, W. Y. (2021). A Dataset for Answering Time-Sensitive Questions. *NeurIPS Datasets & Benchmarks*. https://arxiv.org/abs/2108.06314
- Cormack, G. V., Clarke, C. L. A., Buettcher, S. (2009). Reciprocal Rank Fusion outperforms Condorcet and Individual Rank Learning Methods. *SIGIR 2009*. https://doi.org/10.1145/1571941.1572114
- Es, S., James, J., Espinosa-Anke, L., Schockaert, S. (2024). RAGAS. *EACL 2024 Demos*. https://aclanthology.org/2024.eacl-demo.16
- Gao, L., et al. (2023). PAL: Program-aided Language Models. *ICML 2023*. https://proceedings.mlr.press/v202/gao23f.html
- Gao, T., Yen, H., Yu, J., Chen, D. (2023). Enabling Large Language Models to Generate Text with Citations. *EMNLP 2023*. https://aclanthology.org/2023.emnlp-main.398
- Järvelin, K., Kekäläinen, J. (2002). Cumulated Gain-Based Evaluation of IR Techniques. *ACM TOIS* 20(4). https://doi.org/10.1145/582415.582418
- Kamath, A., Jia, R., Liang, P. (2020). Selective Question Answering under Domain Shift. *ACL 2020*. https://aclanthology.org/2020.acl-main.503
- Karpukhin, V., et al. (2020). Dense Passage Retrieval for Open-Domain Question Answering. *EMNLP 2020*. https://aclanthology.org/2020.emnlp-main.550
- Khanuja, S., Dandapat, S., Srinivasan, A., Sitaram, S., Choudhury, M. (2020). GLUECoS. *ACL 2020*. https://aclanthology.org/2020.acl-main.329
- Lewis, P., et al. (2020). Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks. *NeurIPS 2020*. https://arxiv.org/abs/2005.11401
- Liu, N. F., Zhang, T., Liang, P. (2023). Evaluating Verifiability in Generative Search Engines. *Findings of EMNLP 2023*. https://arxiv.org/abs/2304.09848
- Magesh, V., Surani, F., Dahl, M., Suzgun, M., Manning, C. D., Ho, D. E. (2025). Hallucination-Free? Assessing the Reliability of Leading AI Legal Research Tools. *J. Empirical Legal Studies* 22(2). https://doi.org/10.1111/jels.12413
- Malik, V., et al. (2021). ILDC for CJPE. *ACL-IJCNLP 2021*. https://aclanthology.org/2021.acl-long.313
- Nogueira, R., Cho, K. (2019). Passage Re-ranking with BERT. https://arxiv.org/abs/1901.04085
- Pipitone, N., Houir Alami, G. (2024). LegalBench-RAG. https://arxiv.org/abs/2408.10343
- Qwen Team (2024). Qwen2.5 Technical Report. https://arxiv.org/abs/2412.15115
- Robertson, S., Zaragoza, H. (2009). The Probabilistic Relevance Framework: BM25 and Beyond. *FnTIR* 4(1–2). https://doi.org/10.1561/1500000019
- Schick, T., et al. (2023). Toolformer. *NeurIPS 2023*. https://arxiv.org/abs/2302.04761
- Wang, L., et al. (2022). Text Embeddings by Weakly-Supervised Contrastive Pre-training. https://arxiv.org/abs/2212.03533
- Wang, L., et al. (2024). Multilingual E5 Text Embeddings: A Technical Report. https://arxiv.org/abs/2402.05672
- Zhang, M. J. Q., Choi, E. (2021). SituatedQA. *EMNLP 2021*. https://aclanthology.org/2021.emnlp-main.586
- Zheng, L., Guha, N., Anderson, B. R., Henderson, P., Ho, D. E. (2021). When Does Pretraining Help? (CaseHOLD). *ICAIL 2021*. https://arxiv.org/abs/2104.08671
