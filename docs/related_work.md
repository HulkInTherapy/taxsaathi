# Related Work: TaxSaathi

Each entry below was checked on 2026-10-29 against the arXiv API, the ACL Anthology, Crossref (DOI), or the publisher's proceedings page. Figures quoted in the "relevance" notes come from the paper's own abstract. Entries are grouped by the design question they inform.

---

## A. Lexical, dense and hybrid retrieval

**[1] Robertson & Zaragoza (2009).** Stephen Robertson, Hugo Zaragoza. *The Probabilistic Relevance Framework: BM25 and Beyond.* Foundations and Trends in Information Retrieval, vol. 4, no. 1–2, pp. 1–174, 2009 (per Crossref). DOI: [10.1561/1500000019](https://doi.org/10.1561/1500000019)
*Relevance.* This is the standard reference for BM25, our lexical retriever (config B1). BM25 scores a passage by how often the query terms appear in it, adjusted for passage length and term rarity. That is why it is strong for exact legal tokens such as "80C", "44ADA" or "Form 16", which dense models tend to blur.

**[2] Cormack, Clarke & Buettcher (2009).** Gordon V. Cormack, Charles L. A. Clarke, Stefan Buettcher. *Reciprocal Rank Fusion outperforms Condorcet and Individual Rank Learning Methods.* SIGIR 2009, pp. 758–759. DOI: [10.1145/1571941.1572114](https://doi.org/10.1145/1571941.1572114) · [author PDF](http://cormack.uwaterloo.ca/cormack/cormacksigir09-rrf.pdf)
*Relevance.* This paper defines RRF, RRFscore(d) = Σ_r 1/(k + r(d)). The paper states that "k = 60 was fixed during a pilot investigation" and was near-optimal, and RRF beat Condorcet, CombMNZ and the best single system by 4–5% on average. We use RRF with k = 60 (C2–C5) because it combines BM25 and dense rankings without having to calibrate their very different score scales.

**[3] Karpukhin et al. (2020), DPR.** Vladimir Karpukhin, Barlas Oğuz, Sewon Min, Patrick Lewis, Ledell Wu, Sergey Edunov, Danqi Chen, Wen-tau Yih. *Dense Passage Retrieval for Open-Domain Question Answering.* EMNLP 2020, pp. 6769–6781. [arXiv:2004.04906](https://arxiv.org/abs/2004.04906) · [ACL Anthology](https://aclanthology.org/2020.emnlp-main.550)
*Relevance.* DPR showed that a dual encoder (one vector per question, one per passage) beats Lucene-BM25 by 9–19 points absolute in top-20 retrieval accuracy on open-domain QA. This is the paradigm behind our dense retriever (C1). It is the motivation for retrieving by meaning, e.g. "salary pe tax kam kaise karein" should find a deductions passage that shares no words with the query.

**[4] Wang et al. (2022, 2024), E5 and multilingual E5.** (a) Liang Wang, Nan Yang, Xiaolong Huang, Binxing Jiao, Linjun Yang, Daxin Jiang, Rangan Majumder, Furu Wei. *Text Embeddings by Weakly-Supervised Contrastive Pre-training.* arXiv preprint, 2022. [arXiv:2212.03533](https://arxiv.org/abs/2212.03533). (b) Liang Wang, Nan Yang, Xiaolong Huang, Linjun Yang, Rangan Majumder, Furu Wei. *Multilingual E5 Text Embeddings: A Technical Report.* arXiv preprint, 2024. [arXiv:2402.05672](https://arxiv.org/abs/2402.05672)
*Relevance.* E5 was "the first model that outperforms the strong BM25 baseline on the BEIR retrieval benchmark without using any labeled data". mE5 extends the recipe with contrastive pre-training on about 1 billion multilingual text pairs, released in small, base and large sizes. We use `intfloat/multilingual-e5-small`: 12 layers, 384-dimensional embeddings, inputs prefixed "query: " / "passage: " (per the [model card](https://huggingface.co/intfloat/multilingual-e5-small)). The small size fits our CPU budget and the model is multilingual.

**[5] Chen et al. (2024), BGE M3-Embedding.** Jianlv Chen, Shitao Xiao, Peitian Zhang, Kun Luo, Defu Lian, Zheng Liu. *M3-Embedding: Multi-Linguality, Multi-Functionality, Multi-Granularity Text Embeddings Through Self-Knowledge Distillation.* Findings of ACL 2024, pp. 2318–2335. [arXiv:2402.03216](https://arxiv.org/abs/2402.03216) · [ACL Anthology](https://aclanthology.org/2024.findings-acl.137)
*Relevance.* BGE-M3 does dense, sparse and multi-vector retrieval in one model across 100+ languages. That confirms the community view that lexical and semantic signals complement each other, which is the idea behind our hybrid design. Our reranker comes from the same BAAI family. Its multilingual successor `bge-reranker-v2-m3` is a candidate upgrade (see "How TaxSaathi builds on this").

## B. Reranking

**[6] Nogueira & Cho (2019).** Rodrigo Nogueira, Kyunghyun Cho. *Passage Re-ranking with BERT.* arXiv preprint, 2019. [arXiv:1901.04085](https://arxiv.org/abs/1901.04085)
*Relevance.* This paper introduced the cross-encoder reranker. BERT reads the query and the passage *together* and outputs a relevance score. It took first place on the MS MARCO passage leaderboard, beating the previous state of the art by 27% relative in MRR@10. Our C3 config follows the same retrieve-then-rerank pattern: cheap retrieval of 20 candidates, then expensive cross-encoder scoring of only those 20.

## C. Retrieval-augmented generation and its evaluation

**[7] Lewis et al. (2020), RAG.** Patrick Lewis, Ethan Perez, Aleksandra Piktus, Fabio Petroni, Vladimir Karpukhin, Naman Goyal, Heinrich Küttler, Mike Lewis, Wen-tau Yih, Tim Rocktäschel, Sebastian Riedel, Douwe Kiela. *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks.* NeurIPS 2020. [arXiv:2005.11401](https://arxiv.org/abs/2005.11401)
*Relevance.* RAG pairs a generator with an external, swappable document index. The authors note that the index addresses "providing provenance" and "updating their world knowledge". Both are central here: the tax law changed in 2025–26, and we need to update the knowledge base, not retrain a model.

**[8] Es et al. (2024), RAGAS.** Shahul Es, Jithin James, Luis Espinosa-Anke, Steven Schockaert. *RAGAS: Automated Evaluation of Retrieval Augmented Generation.* EACL 2024 System Demonstrations, pp. 150–158. [arXiv:2309.15217](https://arxiv.org/abs/2309.15217) · [ACL Anthology](https://aclanthology.org/2024.eacl-demo.16)
*Relevance.* RAGAS breaks RAG evaluation into dimensions such as context relevance and faithfulness (is the answer supported by the retrieved passages?), with reference-free metrics. Our "faithfulness proxy" (report §6) borrows this idea in a cheaper form suited to a CPU-only setup.

**[9] Gao et al. (2023), ALCE.** Tianyu Gao, Howard Yen, Jiatong Yu, Danqi Chen. *Enabling Large Language Models to Generate Text with Citations.* EMNLP 2023. [arXiv:2305.14627](https://arxiv.org/abs/2305.14627) · [ACL Anthology](https://aclanthology.org/2023.emnlp-main.398)
*Relevance.* ALCE is a benchmark for LLM answers with inline citations, scored on fluency, correctness and citation quality. It found that "even the best models lack complete citation support 50% of the time" on ELI5. This is why TaxSaathi does not trust the LLM's citations: a post-hoc citation check (pipeline step 10) drops sentences whose `[CHUNK-ID]` is missing or invalid.

## D. Hallucination and retrieval in the legal domain

**[10] Magesh et al. (2025).** Varun Magesh, Faiz Surani, Matthew Dahl, Mirac Suzgun, Christopher D. Manning, Daniel E. Ho. *Hallucination-Free? Assessing the Reliability of Leading AI Legal Research Tools.* Journal of Empirical Legal Studies 22(2):216–242, 2025. DOI: [10.1111/jels.12413](https://doi.org/10.1111/jels.12413) · preprint [arXiv:2405.20362](https://arxiv.org/abs/2405.20362) (2024)
*Relevance.* This is the first preregistered evaluation of commercial legal RAG tools. Lexis+ AI and Westlaw AI tools "each hallucinate between 17% and 33% of the time", although they do better than GPT-4. It is the main evidence that **RAG alone does not make a legal assistant safe**, and it motivates our refusal gate, citation check and disclaimer.

**[11] Pipitone & Houir Alami (2024), LegalBench-RAG.** Nicholas Pipitone, Ghita Houir Alami. *LegalBench-RAG: A Benchmark for Retrieval-Augmented Generation in the Legal Domain.* arXiv preprint, 2024. [arXiv:2408.10343](https://arxiv.org/abs/2408.10343)
*Relevance.* A retrieval-focused legal benchmark: 6,858 query–answer pairs over a corpus of more than 79M characters, annotated by legal experts. It argues for retrieving "minimal, highly relevant text segments" instead of large imprecise chunks, so the LLM can cite precisely. This supports our choice of one-idea-per-chunk, section-level passages, and our separate evaluation of retrieval (Recall@k, MRR, nDCG) before generation.

**[12] Zheng et al. (2021), CaseHOLD.** Lucia Zheng, Neel Guha, Brandon R. Anderson, Peter Henderson, Daniel E. Ho. *When Does Pretraining Help? Assessing Self-Supervised Learning for Law and the CaseHOLD Dataset.* ICAIL 2021. [arXiv:2104.08671](https://arxiv.org/abs/2104.08671)
*Relevance.* CaseHOLD has more than 53,000 multiple-choice questions about case holdings. The paper shows that legal language is distinct enough that domain pretraining helps on hard legal tasks. We cannot pretrain on CPU. Instead we compensate with domain *data* (a curated corpus, section-number entity boosting, mapping chunks between the 1961 and 2025 Acts).

**[13] Malik et al. (2021), ILDC.** Vijit Malik, Rishabh Sanjay, Shubham Kumar Nigam, Kripa Ghosh, Shouvik Kumar Guha, Arnab Bhattacharya, Ashutosh Modi. *ILDC for CJPE: Indian Legal Documents Corpus for Court Judgment Prediction and Explanation.* ACL-IJCNLP 2021, pp. 4046–4062. [arXiv:2105.13562](https://arxiv.org/abs/2105.13562) · [ACL Anthology](https://aclanthology.org/2021.acl-long.313)
*Relevance.* This is the main Indian legal NLP resource: 35k Supreme Court cases, best model at 78% accuracy against 94% for legal experts. It shows how large the gap to experts still is in Indian legal NLP, and it shows there is no ready-made Indian *tax-QA* dataset. That is why we build our own gold set and treat CA review as necessary future work.

## E. Time-sensitive question answering

**[14] Zhang & Choi (2021), SituatedQA.** Michael J. Q. Zhang, Eunsol Choi. *SituatedQA: Incorporating Extra-Linguistic Contexts into QA.* EMNLP 2021, pp. 7371–7387. [arXiv:2109.06157](https://arxiv.org/abs/2109.06157) · [ACL Anthology](https://aclanthology.org/2021.emnlp-main.586)
*Relevance.* About 16.5% of NQ-Open questions have answers that depend on when or where they are asked. Models trained on past data drop about 15 points in accuracy on present-day questions, *even with an updated evidence corpus*. Tax questions are temporal by nature ("GST on cement" before or after 22 Sep 2025). This paper is the direct motivation for period extraction plus a date filter (C4) rather than simply refreshing the corpus.

**[15] Chen, Wang & Wang (2021), TimeQA.** Wenhu Chen, Xinyi Wang, William Yang Wang. *A Dataset for Answering Time-Sensitive Questions.* NeurIPS 2021 Datasets and Benchmarks Track. [arXiv:2108.06314](https://arxiv.org/abs/2108.06314)
*Relevance.* On TimeQA the best model (FiD) reaches 46% against 87% for humans, which shows that neural readers handle temporal reasoning poorly. We therefore do the temporal step **symbolically** (rule-based period extraction plus an interval-overlap filter on `effective_from`/`effective_to`) instead of asking the LLM to work out which law applies.

## F. Code-mixed Hindi–English (Hinglish)

**[16] Khanuja et al. (2020), GLUECoS.** Simran Khanuja, Sandipan Dandapat, Anirudh Srinivasan, Sunayana Sitaram, Monojit Choudhury. *GLUECoS: An Evaluation Benchmark for Code-Switched NLP.* ACL 2020, pp. 3575–3585. [arXiv:2004.12376](https://arxiv.org/abs/2004.12376) · [ACL Anthology](https://aclanthology.org/2020.acl-main.329)
*Relevance.* A code-switching benchmark covering English–Hindi, including language identification and QA. Multilingual models fine-tuned on code-switched data did best on most tasks. Hinglish is how many of our users write. Lacking code-switched training data, we use a cheap alternative: dictionary-plus-rules normalisation of romanised Hindi function words (C5), then a multilingual encoder.

**[17] Aguilar, Kar & Solorio (2020), LinCE.** Gustavo Aguilar, Sudipta Kar, Thamar Solorio. *LinCE: A Centralized Benchmark for Linguistic Code-switching Evaluation.* LREC 2020, pp. 1803–1813. [arXiv:2005.04322](https://arxiv.org/abs/2005.04322) · [ACL Anthology](https://aclanthology.org/2020.lrec-1.223)
*Relevance.* LinCE has ten corpora over four language pairs, including Hindi–English, for language ID, NER, POS tagging and sentiment. It confirms that code-switching is a recognised and still-hard setting, and it gives us the vocabulary (language identification, code-switch point) behind our Hinglish detector in `src/nlp/hinglish.py`.

## G. Abstention / selective prediction

**[18] Kamath, Jia & Liang (2020).** Amita Kamath, Robin Jia, Percy Liang. *Selective Question Answering under Domain Shift.* ACL 2020, pp. 5684–5696. [arXiv:2006.09462](https://arxiv.org/abs/2006.09462) · [ACL Anthology](https://aclanthology.org/2020.acl-main.503)
*Relevance.* QA systems must know when to abstain. Softmax confidence "fare[s] poorly" because models are overconfident on out-of-domain inputs. A separate calibrator answered 56% of questions at 80% accuracy, against 48% for raw probabilities. Our refusal gate follows the same idea: a signal separate from the generator (intent classifier plus top reranker score against a threshold tuned on dev) decides whether to answer.

## H. LLMs, arithmetic and tools

**[19] Gao et al. (2023), PAL.** Luyu Gao, Aman Madaan, Shuyan Zhou, Uri Alon, Pengfei Liu, Yiming Yang, Jamie Callan, Graham Neubig. *PAL: Program-aided Language Models.* ICML 2023 (PMLR 202). [arXiv:2211.10435](https://arxiv.org/abs/2211.10435) · [PMLR](https://proceedings.mlr.press/v202/gao23f.html)
*Relevance.* LLMs "often make logical and arithmetic mistakes in the solution part, even when the problem is decomposed correctly". Handing the computation to a Python interpreter fixes this. TaxSaathi goes one step further: the arithmetic is a **hand-written, unit-tested calculator**, and the LLM is never asked to compute.

**[20] Schick et al. (2023), Toolformer.** Timo Schick, Jane Dwivedi-Yu, Roberto Dessì, Roberta Raileanu, Maria Lomeli, Luke Zettlemoyer, Nicola Cancedda, Thomas Scialom. *Toolformer: Language Models Can Teach Themselves to Use Tools.* NeurIPS 2023. [arXiv:2302.04761](https://arxiv.org/abs/2302.04761) · [NeurIPS proceedings](https://papers.nips.cc/paper_files/paper/2023/hash/d842425e4bf79ba039352da0f658a906-Abstract-Conference.html)
*Relevance.* LMs "struggle with basic functionality, such as arithmetic or factual lookup, where much simpler and smaller models excel". The fix is calling tools, including a calculator and a calendar. This underpins two design choices: the calculator route (pipeline step 8) and the planned agentic layer (M4+), where tool selection could be learned or prompted rather than rule-routed.

---

### Supplementary method references (verified, cited in the report)

- **[S1]** Kalervo Järvelin, Jaana Kekäläinen. *Cumulated Gain-Based Evaluation of IR Techniques.* ACM TOIS 20(4):422–446, 2002. DOI: [10.1145/582415.582418](https://doi.org/10.1145/582415.582418). Origin of (n)DCG.
- **[S2]** Qwen Team (An Yang et al.). *Qwen2.5 Technical Report.* arXiv preprint, 2024. [arXiv:2412.15115](https://arxiv.org/abs/2412.15115). Our local generator family (`qwen2.5:1.5b` / `qwen2.5:3b`).
- **[S3]** Shitao Xiao, Zheng Liu, Peitian Zhang, Niklas Muennighoff, Defu Lian, Jian-Yun Nie. *C-Pack: Packed Resources for General Chinese Embeddings.* SIGIR 2024. [arXiv:2309.07597](https://arxiv.org/abs/2309.07597). Introduces the BGE model family that our reranker comes from.
- **[S4]** Nils Reimers, Iryna Gurevych. *Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks.* EMNLP-IJCNLP 2019, pp. 3982–3992. [arXiv:1908.10084](https://arxiv.org/abs/1908.10084). The `sentence-transformers` library we load E5 and the CrossEncoder through.
- **[S5]** Nelson F. Liu, Tianyi Zhang, Percy Liang. *Evaluating Verifiability in Generative Search Engines.* Findings of EMNLP 2023. [arXiv:2304.09848](https://arxiv.org/abs/2304.09848). Citation recall/precision for generative search.
- **[S6]** Bhuwan Dhingra, Jeremy R. Cole, Julian Martin Eisenschlos, Daniel Gillick, Jacob Eisenstein, William W. Cohen. *Time-Aware Language Models as Temporal Knowledge Bases.* TACL 10:257–273, 2022. DOI: [10.1162/tacl_a_00459](https://doi.org/10.1162/tacl_a_00459). Facts change over time; models trained at one point in time go stale.
- **[S7]** Ziwei Ji et al. *Survey of Hallucination in Natural Language Generation.* ACM Computing Surveys, 2022. DOI: [10.1145/3571730](https://doi.org/10.1145/3571730). Definitions of intrinsic and extrinsic hallucination.

---

## How TaxSaathi builds on this

| Design decision | What the literature says | Our adaptation | Config / step |
|---|---|---|---|
| Keep BM25 as a first-class retriever | BM25 is a strong, cheap baseline [1]; exact tokens matter in law | Section numbers, form names and amounts are preserved by the tokenizer | B1, all hybrids |
| Add a dense retriever | Dense dual encoders beat BM25 on semantic matching [3]; E5/mE5 are strong zero-shot [4] | `multilingual-e5-small` with query/passage prefixes, CPU-friendly | C1 |
| Fuse with RRF, k = 60 | RRF is robust, needs no score calibration, k = 60 near-optimal [2]; lexical + semantic signals complement each other [5] | Union of BM25 top-N and dense top-N, fused by rank | C2 |
| Rerank only the top 20 | Cross-encoders are more accurate but expensive [6]; the model card recommends rerank-after-retrieve | `bge-reranker-base` on 20 candidates → top 5 | C3 |
| Small, section-level chunks with source metadata | Precise snippets enable precise citations [11]; RAG gives provenance and updatable memory [7] | One idea per chunk, 60–220 words, ID = section, plus `source_url` | ingest |
| Period-aware filtering done symbolically | Answers depend on time [14]; neural temporal reasoning is weak [15]; LMs go stale [S6] | Period extractor → [start, end] → interval-overlap filter; default = today, flagged | C4, steps 4 & 6 |
| Hinglish normalisation before retrieval | Code-switching is hard [16, 17]; fine-tuning on CS data helps, but we have none | Dictionary + rules → English-ish query; multilingual encoder as backup | C5, step 2 |
| Separate abstention signal | Softmax confidence is overconfident under domain shift; use a separate calibrator [18] | TF-IDF+LogReg intent + reranker-score threshold chosen on dev | step 3, step 7 |
| Never let the LLM do arithmetic | LLMs make arithmetic errors; offload to programs/tools [19, 20] | Deterministic `calculator/tax.py`, unit-tested, 100% exact-match target | step 8 |
| Verify citations after generation | Even the best LLMs lack full citation support about half the time [9]; verifiability matters [S5] | Drop sentences with missing or invalid `[CHUNK-ID]`; extractive fallback | step 10 |
| Measure faithfulness, not just fluency | Reference-free faithfulness metrics [8]; hallucination taxonomy [S7] | Faithfulness proxy based on cited-passage support | eval |
| Treat legal RAG as fallible | Commercial legal RAG still hallucinates 17–33% [10]; experts far ahead [13] | Refusal + CA escalation + disclaimer; gold set to be CA-reviewed | steps 7, 11 |
| No domain pretraining | Domain pretraining helps on hard legal tasks [12], but needs GPUs | Domain data instead: mapping chunks, section-entity boost | step 5 |
| Upgrade path | BGE-M3 is multilingual [5]. The `bge-reranker-base` card lists **Chinese and English only**, while `bge-reranker-v2-m3` is listed as multilingual | Candidate ablation in M4: swap the reranker for Hinglish queries | future |
