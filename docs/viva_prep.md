# Viva Prep: TaxSaathi

Short, correct answers. Say the first sentence, then add detail only if they ask. Paper numbers like [2] refer to `related_work.md`.

---

## A. Problem and motivation

**1. What problem are you solving?**
Routine Indian tax questions usually need a paid CA or unreliable web search. We built a free assistant that answers from official law, cites the section and period, refuses when unsure, and computes tax exactly.

**2. Why is this an NLP problem and not just a FAQ page?**
Users ask in free text, often in Hinglish, about different periods, and phrase things in ways no FAQ anticipates. That needs retrieval by meaning, language handling, period understanding and generation, which are all NLP tasks.

**3. What changed in the law that makes this hard?**
The Income-tax Act, 2025 came into force on 1 April 2026 and introduced the "Tax Year". GST rates changed on 22 September 2025 to mainly 5% and 18%, plus 40% for a few goods. The right answer now depends on *when*.

**4. Are you replacing CAs?**
No. We are a first-answer helper. Anything personal, disputed or outside the knowledge base is refused with a CA recommendation, and every answer has a disclaimer.

**5. Isn't there already a government chatbot?**
Yes. The Income Tax Department launched "Kar Saathi" in April 2026. Ours is an open research prototype: the full trace, citations with effective dates and a published evaluation are all visible. It is not affiliated with the department.

## B. Retrieval

**6. Why hybrid retrieval instead of only BM25 or only dense?**
BM25 is great at exact tokens like "80C" or "Form 16" but misses paraphrases. Dense search catches meaning ("tax kam kaise karein" → deductions) but can blur exact section numbers. Combined, each covers the other's blind spots. C2 vs B1/C1 tests this.

**7. What is RRF and why k = 60?**
Each card gets the sum of 1/(60 + its rank) over both lists. It uses ranks, not raw scores, so we don't have to calibrate BM25 against cosine scores. k = 60 is the value the original paper found near-optimal [2], and it stops the top rank from dominating.

**8. Why does the reranker only see the top 20, and what does it do in the final system?**
A cross-encoder reads question and card together, which is accurate but slow, roughly one model pass per card. Scoring 20 on CPU is affordable; the whole corpus is not. In the final system (C6) it **does not reorder** those 20: its best score is only the confidence signal for the refusal gate. Letting it reorder (C3) lowered MRR from 0.755 to 0.656 (see Q39).

**9. Why chunk by legal section instead of fixed-size windows?**
A section is the unit people cite, and one idea per chunk gives precise retrieval and precise citations. Fixed windows can cut a proviso off from its rule or mix two sections.

**10. Why multilingual-e5-small?**
It is multilingual (about 100 languages), small (12 layers, 384-dimensional vectors) so it runs on CPU, and E5 models are strong zero-shot retrievers [4].

**11. What is the "query: / passage: " prefix?**
E5 was trained with those prefixes to tell questions apart from documents. The model card says to always add them, otherwise quality drops.

## C. Period awareness

**12. How does period-aware filtering work?**
We extract a date range from the question (FY, AY, Tax Year, month-year, "before GST 2.0", "last year"). Each chunk has `effective_from` and `effective_to`. We keep only chunks whose range overlaps the question's range, and when a removed chunk has an in-period version of the same rule we swap that in (*period substitution*, Q40). With no period mentioned, we assume today and tell the user. Period accuracy: 0.875 (C2) → 1.000 (C4–C6).

**13. Why not let the LLM figure out the period?**
Neural models are known to be weak at temporal reasoning (TimeQA: best model 46% vs 87% for humans [15]). Rules are exact, testable and visible in the trace.

**14. Where is the filter applied, and why there?**
After fusion and before the reranker scores anything. Fusion sees everything, so no early recall loss, and the expensive reranker only scores eligible cards, so the confidence score is about the right period's law.

**15. What is a "time-trap" question?**
The same question for two periods, e.g. GST on cement before and after 22 Sep 2025. It checks whether we cite the law that was valid for that period.

## D. Language

**16. How does Hinglish work?**
A dictionary of about 150 entries plus rules rewrites common romanised Hindi words (kitna → how much, kaise → how, milta hai → is available) and keeps tax terms. The multilingual embedder is a second safety net. C5 vs C4 measures the gain: on the 4 Hinglish dev questions Recall@5 was already 1.0, so the result is inconclusive (n = 4); we kept it because it costs nothing and makes the trace readable. Honest caveat: key-fact accuracy on Hinglish is 0.50, and real written Hinglish is rare (1 of 80 real questions).

**17. Why not translate with an LLM?**
It would add seconds on CPU, might change numbers or section IDs, and is harder to test. A dictionary is instant, deterministic and every replacement shows in the trace.

**18. Does the reranker understand Hinglish?**
Not well. The `bge-reranker-base` card lists only Chinese and English, which is another reason we normalise first, and part of why reordering by it hurt. The multilingual `bge-reranker-v2-m3` took about 25 s per query on CPU, so it is left for M4 with a GPU.

## E. Safety and guardrails

**19. Why TF-IDF + logistic regression for intent instead of an LLM?**
Three classes and 342 examples is a small, simple task (5-fold CV accuracy about 0.90). LogReg trains in seconds, runs in milliseconds on CPU, gives probabilities, and you can see which words drove a decision. An LLM would be slower and harder to calibrate.

**20. How is the refusal threshold chosen?**
On the dev set only. We sweep the threshold on the top reranker score and pick the value that reaches ≥ 90% correct refusal on out-of-scope questions with the lowest false-refusal rate on answerable ones. All 5 dev out-of-scope questions were already caught by the intent classifier, so many thresholds tied; we took the middle of that range (θ = −5.834) rather than an effectively disabled gate. Then we freeze it for test. Result: 100% out-of-scope refusal, 2.1% false refusals.

**21. Why not just use the LLM's confidence to refuse?**
Model confidence is overconfident on unfamiliar inputs. Kamath et al. [18] showed that a separate signal works better, and our gate is separate from the generator.

**22. How are citations checked?**
The LLM must put `[CHUNK-ID]` after each sentence. We split the answer into sentences and drop any with no ID, or with an ID that wasn't among the 3 passages we gave it. If nothing useful remains, we show the top passage directly. For calculation answers it is stricter: the calculator's own explanation leads, and any LLM sentence with a number or a verdict ("no tax", "new regime is better") is dropped. Citation validity 1.00 on dev.

**23. Why is the calculator not an LLM?**
LLMs make arithmetic mistakes and never signal uncertainty [19, 20]. Tax needs exact, repeatable results, so we wrote deterministic code with 99 unit tests including hand-worked cases; it is exact on all 16 gold calculations (100%). The LLM only explains, and numbers and verdicts in the answer come only from the calculator. It handles salary, freelancers (section 58 / old 44ADA: 50% of receipts is income), foreign currency (RBI/FBIL reference rate) and "per month" amounts.

**24. What if the user doesn't give their salary?**
The calculator doesn't guess. It returns a follow-up question asking for the missing input.

**25. How do you handle privacy?**
Regex scrubbing of PAN, Aadhaar, phone numbers and emails before logging. Gold and training data are synthetic; the 80 real questions are public posts with names and usernames removed.

## F. Evaluation

**26. What does Recall@5 mean?**
How often the correct card appears in our top 5. Target ≥ 0.85; final C6 gets 0.917 on dev.

**27. What does MRR mean?**
Mean Reciprocal Rank: for each question, 1 divided by the position of the first correct card (1st = 1, 2nd = 0.5, 3rd = 0.33), averaged. It rewards putting the right card at the top.

**28. And nDCG?**
It scores the whole ranked list, with correct cards lower down counting less (divided by log₂(position+1)), normalised so a perfect ordering = 1.

**29. How do you prevent test-set leakage?**
(1) Stratified 30% dev / 70% test split with a fixed seed. (2) All tuning on dev only, with test run once per frozen config. (3) Intent training data written separately and automatically screened for copies or near-duplicates of gold questions. (4) Gold questions written from personas, not from chunks.

**30. How do you measure faithfulness without a big LLM judge?**
A proxy: the share of answer sentences kept by the citation check (supported by a valid citation). C6 scores 1.00. It is cheap and CPU-friendly but generous (a sentence can cite a real card and still misstate it), so an LLM-judge version is planned for M4.

**31. Why is B0 (LLM alone) included?**
To show what happens without retrieval: no citations, old or invented law, wrong arithmetic. It gets only 10.4% of key facts right (vs 68.8% for C6) and refuses 0% of out-of-scope questions. It is the "normal chatbot" in our Compare tab.

**32. Why does each config change only one thing?**
So any difference between neighbouring configs can be attributed to that one change (an ablation ladder).

**33. Why a local small LLM?**
Free, private (questions never leave our server), works offline, and fits a 4-vCPU / 8 GB server. Because retrieval, guardrails and the calculator do the heavy lifting, the LLM only has to phrase things.

**34. Your latency target is 5 s. Do you meet it?**
No: median 16.8 s on dev, the one M1 target we miss (4 of 5 met). See Q44 for why and how to fix it.

## G. Limitations and future

**35. Main limitations?**
Curated summary corpus (107 passages) rather than full Acts; gold set written by us and not yet CA-reviewed; real-question recall lower than dev (0.78 at rule level); only 57% of real out-of-scope questions refused; small LLM and 16.8 s latency on CPU; English-centric reranker; rule-based periods; limited calculator scope; legal liability (hence the disclaimer).

**36. What would you do with more time?**
Run frozen C6 once on the 123 test questions (M4), CA review of 30–50 gold answers, full-text Act ingestion, a multilingual reranker, LLM-judge faithfulness, GPU/API generation, a stronger out-of-scope classifier trained on real phrasing, a user study, and an agentic layer that picks tools while keeping the calculator and citation check as hard rules.

**37. What would break your system?**
A new notification we haven't ingested (stale knowledge base), unusual period phrasing, or a question that needs combining many sections. The trace and refusal gate are designed to make these failures visible rather than silent.

**38. If a cited card is wrong, what happens?**
The answer will be wrong but traceable: the citation points to the exact card to fix, and fixing it fixes every future answer. Cards are flagged `verified: yes/partial` (72 yes, 35 partial).

## H. The final system (C6), real questions and the demo

**39. Why did the reranker make things worse, and what did you do?**
When we let the cross-encoder reorder the top 20 (C3), MRR fell from 0.755 to 0.656 and Recall@5 from 0.839 to 0.804. `bge-reranker-base` only knows English and Chinese, and it often promoted a *related* passage or the *wrong period's* version of the right rule (it can't read dates). So in the final config C6 we keep the hybrid + date-filter order and use the reranker only as a confidence signal: "is the best passage good enough to answer?" That gave the best ranking of any config: Recall@5 0.917, MRR 0.830, nDCG@5 0.831. A negative result we report, not hide.

**40. What is period substitution?**
An addition to the date filter. When a retrieved passage is from the wrong period, we don't just drop it: the same rule's version for the asked period takes its place, matched by ID stem (`GST-RATE-AC-POST` → `GST-RATE-AC-PRE`) or by topic. If the question is about a year before our sources start, we keep the closest (oldest) version and the trace marks it "kept closest", instead of answering with nothing. You can see the swaps in "How this was found" under the date filter. It was regression-tested on dev with no metric drop.

**41. How do you handle "I earn $5k a month remote"?**
The entity parser sees a foreign currency and "per month": US$5,000 × 12 = US$60,000, converted at the RBI/FBIL reference rate (₹95.2278 per US$, 28 Oct 2026) = ₹57,13,668. Remote work paid in foreign currency is treated as freelance/professional income, so the presumptive rule applies: section 58 of the 2025 Act (old 44ADA), 50% of receipts = ₹28,56,834 taxable, no standard deduction. The calculator then computes both regimes (new ₹4,54,532 vs old ₹6,96,332 including cess). The answer states every assumption (rate used, freelance not salary, resident) and offers to recalculate as salary. All numbers come from the calculator, not the LLM. This feature came directly from real questions.

**42. Why only 57% refusal on real out-of-scope questions?**
4 of 7 real out-of-scope questions were refused, vs 100% on our synthetic dev set. Real out-of-scope questions are wrapped in ordinary tax vocabulary ("ITR-2 for AY 2026-27 under the new regime… STCG of ₹11,387", "pending notices under the 1961 Act", "residential status… section 6"), so most likely the intent classifier, trained on our own phrasings, sees a normal tax question, and the reranker finds a related passage (rebate, ITR forms) that passes the confidence gate. It is a known weakness logged for M4: more out-of-scope training examples in real phrasing, and topic rules for NRI/crypto/capital gains/notices. Only 7 questions, so the estimate is rough.

**43. Why is real-question recall lower than dev recall?**
On the 51 real questions our knowledge base fully covers, C6 Recall@5 is 0.62 by exact passage, but **0.78 at rule level** (any period version of the gold rule); on dev it is 0.917. Two reasons. (1) Temporal labelling: posts written in 2025 were labelled with FY 2025-26 passages, while C6 deliberately answers with the law in force today (Tax Year 2026-27), so it retrieves the right rule's newer version and "misses" by the exact-ID measure. That is also why C2 (no date filter) scores 0.86 there. (2) Real posts are long, informal and mix several issues, unlike our one-question-per-row gold set. The real set was never used for tuning.

**44. Your latency is 16.8 s. Why, and how would you fix it?**
Almost all of it is the 3B LLM writing on a 4-vCPU CPU server with no GPU: prompt processing is about 66 tokens/s, so even 3 passages take seconds before the first word, then generation. The reranker adds several seconds on CPU too; the rest (BM25, dense search, rules) is milliseconds. We already cut the passages shown from 5 to 3. Fixes: GPU or a hosted API for the LLM (a few seconds), a quantised or ONNX reranker, caching frequent questions, and streaming the answer so the first words appear in 1–2 s. The "How this was found" panel shows the time split for every answer.

**45. Where did the real questions come from, and is that ethical?**
80 questions: Reddit 36, official FAQs 25 (incometax.gov.in, GST Council/PIB 56th Council FAQ, GST tutorial portal), CAclubindia 11 plus 1 YouTube comment, Quora 7. Found with about 45 web searches; about 20 pages opened. Only public pages, no logins or private groups. No usernames, names, PANs or phone numbers stored; posts were trimmed to the core question without changing facts. Each row keeps its source link, it is used only for non-commercial research evaluation (fair dealing), and we don't redistribute it as a dataset. Reference answers come from our own passages, not copied from the pages. Full method: `docs/research/real_questions_sources.md`.

**46. What does the logo mean?**
A speech bubble that is also a page of law. The bubble is the conversation with your *saathi* (companion), in English or Hinglish. Its top-right corner is folded like a document: every answer is backed by an official source. The check mark inside: the answer was verified (right law, right date, citations checked). Deep teal (#0F766E). It "breathes" while an answer is being prepared and pulses once when the answer lands.

---

## Who presents what (4-person team, about 12–15 min + Q&A)

| Person | Sections | Owns these viva questions |
|---|---|---|
| **P1, Problem & Data** | Problem, law changes, statistics, personas, success metrics; knowledge base (107 passages, 17 sources), chunking, metadata, gold set, split and leakage; the 80 real questions | 1–5, 9, 15, 29, 35, 43, 45 |
| **P2, Retrieval** | BM25, dense, RRF, date filter and period substitution, reranker (and why it only gates); ablation B1 → C6; retrieval metrics | 6–8, 10–14, 26–28, 32, 39, 40 |
| **P3, Language & Safety** | Hinglish normaliser, intent classifier, refusal gate and threshold, citation check, PII, disclaimer | 16–22, 25, 30, 38, 42 |
| **P4, Generation, Calculator & Demo** | Local LLM, calculator, live demo (Compare tab B0 vs C6, trace view), results, latency, future work, logo | 23, 24, 31, 33, 34, 36, 37, 41, 44, 46 |

## Demo script (P4, about 4 min)

Live site: https://taxsaathi.taild58d86.ts.net. Answers take **15–40 s** on CPU (Compare 1–2 min). **Fill every wait** by opening "How this was found" on the previous answer, or by saying what the pipeline is doing right now.

1. **Compare tab:** click the trap pill "GST on AC in Aug 2025" (or type *What was GST on AC in August 2025?*) → Compare. Left: the plain LLM, no source. Right: TaxSaathi, **28%**, cited, "law for August 2025", "8 outdated passages dropped". Point at the timeline at the bottom.
2. **Ask tab, Hinglish:** *Naye regime mein standard deduction kitna hai?* → ₹75,000 under section 19 of the Income-tax Act, 2025. Open "How this was found": the Hinglish fix (naye → new, kitna → how much) and "no date mentioned, using current law".
3. *Is 80C still available in the new Income-tax Act?* → yes, as section 123, up to ₹1,50,000; and the new regime does not allow it. Point at the "Section map · 80C → 123" source card.
4. *how much tax do i have to pay if i am earning 5k us dollars per month remote* → the calculator card: US$ converted at the RBI reference rate, freelancer under section 58 (50%), new regime ₹4,54,532 vs old ₹6,96,332. Say: "numbers by code, not the AI".
5. *How do I avoid tax on foreign crypto income?* → refused: "This needs a Chartered Accountant". Say: saying no is a feature.

**Backup plan.** If the server is slow or down: Advanced (sliders icon, top right) → "Switch to offline demo mode", or open https://taxsaathi.taild58d86.ts.net/?mock=1. It replays recorded answers with the same screens. If even the site won't load, use the screenshots in the slides. One-page version: `docs/DEMO_CHEATSHEET.md`.

### Q47. Some answers look hand-written. Isn't that cheating?
For a few very common confusions (for example "no tax up to ₹12 lakh, but 5% from ₹4 lakh?", which came up in 10 real Reddit posts), the knowledge-base passage carries a **reviewed short answer** written and checked by the team. When that passage is the top search result, TaxSaathi shows the reviewed answer word for word, with its citation, instead of letting the small 3B model paraphrase it. The model had been dropping the key step ("the rebate then cancels the slab tax"), which made the answer contradict itself. Search still has to find the right passage, and the safety gate and citation check still apply. It is the same idea as a help desk's reviewed FAQ: deterministic where correctness matters most, like the calculator.
