# M3 Experiment Log: TaxSaathi (B0–C5)

**Rules of this log**
1. Hypotheses below were written **before** any run (2026-10-29) and must not be edited afterwards. Add corrections as dated notes underneath.
2. All runs use the **dev split** (`data/eval/splits.json`). Test is run once per frozen config, at the end, and logged in §Final test.
3. Every run is also in MLflow (experiment `taxsaathi-m3`) and `experiments/results.json`. Paste the MLflow run ID.
4. Report numbers exactly as produced. Failed or odd runs are kept, not deleted.

**Common setup (fill once)**

| Item | Value |
|---|---|
| Hardware | VPS 4 vCPU / 8 GB RAM / no GPU |
| LLM | `qwen2.5:____` via Ollama (quantisation: ____) |
| Embedder | `intfloat/multilingual-e5-small` |
| Reranker | `BAAI/bge-reranker-base` |
| KB version | chunks.jsonl, N = ____ chunks, git/rsync date ____ |
| Gold set | N = ____ (dev ____ / test ____), split seed ____ |
| Refusal threshold θ | ____ (chosen on dev, see §Threshold) |
| Code version | ____ |

**Metrics recorded for every config:** Recall@5, MRR, nDCG@5, refusal accuracy (OOS), false-refusal rate (answerable), period accuracy (time_trap), key-fact accuracy (mean / strict), citation validity (pre / post check), faithfulness proxy, median and p90 latency (ms).

---

## B0: LLM alone (no retrieval)

| Field | Entry |
|---|---|
| **What changed** | No retrieval; the LLM answers from its own memory. Guardrail intent check still active; no citations possible. |
| **Hypothesis (pre-registered)** | Key-fact accuracy will be lowest of all configs, and period accuracy on time_trap questions will be near chance or worse, because the model's training data predates the Income-tax Act, 2025 (in force 1 Apr 2026) and GST 2.0 (22 Sep 2025). Citation validity and faithfulness are 0 by construction. Latency per query will be lowest among configs that call the LLM. |
| **Expected direction** | KFA ↓↓, period acc ↓↓, latency lowest |
| MLflow run ID | |
| Recall@5 / MRR / nDCG@5 | n/a |
| Refusal acc / false-refusal | |
| Period acc | |
| KFA (mean / strict) | |
| Citation validity / faithfulness | 0 / 0 (by construction) |
| Latency median / p90 | |
| **Conclusion** | |

## B1: BM25 top-5

| Field | Entry |
|---|---|
| **What changed vs B0** | Add BM25 retrieval (top 5) and grounded generation with citations + citation check. |
| **Hypothesis** | KFA and faithfulness rise sharply over B0. Recall@5 is good on questions containing exact tokens (section numbers, form names) but weaker on paraphrased and Hinglish questions. We expect B1 Recall@5 below the 0.85 target overall, with the largest gap in the `hinglish` category. |
| **Expected direction** | vs B0: KFA ↑↑, faithfulness ↑↑; Hinglish recall lowest category |
| MLflow run ID | |
| Recall@5 / MRR / nDCG@5 | |
| Refusal acc / false-refusal | |
| Period acc | |
| KFA (mean / strict) | |
| Citation validity (pre / post) | |
| Faithfulness proxy | |
| Latency median / p90 | |
| Per-category Recall@5 | income_tax __ · gst __ · time_trap __ · calculation __ · hinglish __ |
| **Conclusion** | |

## C1: Dense (mE5) top-5

| Field | Entry |
|---|---|
| **What changed vs B1** | Replace BM25 with dense retrieval (`multilingual-e5-small`, query/passage prefixes). |
| **Hypothesis** | Recall on paraphrased and Hinglish questions improves over B1, while recall on exact-section questions (e.g. "80C", "44ADA") drops. Overall Recall@5 is about the same as B1 (within ±0.05). The two retrievers make *different* errors, which motivates C2. |
| **Expected direction** | Hinglish ↑, exact-token ↓, overall ≈ |
| MLflow run ID | |
| Recall@5 / MRR / nDCG@5 | |
| Overlap of failures with B1 | ___ of ___ B1 misses fixed; ___ new misses |
| Other metrics | |
| Latency median / p90 | |
| **Conclusion** | |

## C2: Hybrid BM25 + dense, RRF (k = 60), top-5

| Field | Entry |
|---|---|
| **What changed vs C1** | Fuse BM25 and dense rankings with RRF, k = 60. |
| **Hypothesis** | Recall@5 exceeds both B1 and C1, because RRF promotes cards that both retrievers rank well and keeps cards that only one finds. MRR improves less than recall (fusion fixes misses more than it fixes ordering). Latency increase over C1 is negligible (< 100 ms). |
| **Expected direction** | Recall@5 > max(B1, C1); MRR ↑ slightly |
| MLflow run ID | |
| Recall@5 / Recall@20 / MRR / nDCG@5 | |
| Other metrics | |
| Latency median / p90 | |
| **Conclusion** | |

## C3: Hybrid top-20 → cross-encoder rerank → top-5

| Field | Entry |
|---|---|
| **What changed vs C2** | Take the RRF top 20 and rerank with `bge-reranker-base`; keep the top 5. Reranker score also feeds the refusal gate. |
| **Hypothesis** | MRR and nDCG@5 rise clearly over C2 (the reranker fixes ordering). Recall@5 rises only as far as the C2 Recall@20 ceiling allows. Refusal accuracy improves because the reranker score is a better "do we have an answer?" signal than fusion scores. Latency rises by the cost of 20 cross-encoder passes on CPU, the largest retrieval-side cost. |
| **Expected direction** | MRR ↑↑, nDCG ↑↑, refusal ↑, latency ↑ |
| MLflow run ID | |
| Recall@5 / MRR / nDCG@5 | |
| Refusal acc / false-refusal | |
| Other metrics | |
| Rerank step ms (median) | |
| **Conclusion** | |

## C4: C3 + date filter (period-aware)

| Field | Entry |
|---|---|
| **What changed vs C3** | Apply period extraction + `effective_from`/`effective_to` overlap filter after fusion, before reranking. |
| **Hypothesis** | Period accuracy on `time_trap` questions improves substantially over C3, which often cites the wrong-period card because old and new cards are textually similar. Overall Recall@5 stays the same or improves slightly (wrong-period distractors removed). Risk: period-extraction errors may filter out the gold card. We will count these cases. |
| **Expected direction** | period acc ↑↑ (time_trap); overall recall ≈/↑ |
| MLflow run ID | |
| Period acc (time_trap) | |
| Recall@5 / MRR / nDCG@5 | |
| # gold cards wrongly filtered | |
| Other metrics | |
| **Conclusion** | |

## C5: C4 + Hinglish normalisation (full system)

| Field | Entry |
|---|---|
| **What changed vs C4** | Run the dictionary + rules Hinglish normaliser before intent, retrieval and reranking. |
| **Hypothesis** | Recall@5 and KFA on the `hinglish` category improve over C4, mainly through BM25 and the English-centric reranker. English-category metrics do not change (normaliser is a no-op on English). Intent accuracy on Hinglish improves. C5 is the first config expected to meet Recall@5 ≥ 0.85 overall. |
| **Expected direction** | Hinglish ↑, English ≈ |
| MLflow run ID | |
| Hinglish Recall@5 / KFA | |
| English Recall@5 / KFA | |
| All metrics vs targets | Recall@5 __ (≥0.85) · Faithfulness __ (≥0.90) · Refusal __ (≥90%) · Calculator __ (100%) · Median latency __ (≤5 s on GPU; CPU actual) |
| **Conclusion** | |

---

## Threshold selection (dev only)

| θ | Refusal acc (OOS) | False-refusal (answerable) | Notes |
|---|---|---|---|
| | | | |

Chosen θ = ____ because ____. Frozen on ____ (date).

## Calculator tests

| Test case | Tax year | Regime | Hand total | Calculator total | Match |
|---|---|---|---|---|---|
| | | | | | |

## Final test-set run (once, frozen configs)

| Config | Recall@5 | MRR | nDCG@5 | Refusal | Period | KFA | Cit. valid | Faithful | Lat. med |
|---|---|---|---|---|---|---|---|---|---|
| B0 | | | | | | | | | |
| B1 | | | | | | | | | |
| C1 | | | | | | | | | |
| C2 | | | | | | | | | |
| C3 | | | | | | | | | |
| C4 | | | | | | | | | |
| C5 | | | | | | | | | |

Was the test set used for any decision? ☐ No ☐ Yes (describe; mark results as contaminated)

## Error analysis (C5, dev)

| Q id | Category | What went wrong (retrieval / period / normaliser / gate / generation / citation) | Fix idea |
|---|---|---|---|
| | | | |

## Dated notes / deviations from plan
- 2026-__-__:
