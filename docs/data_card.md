# Data card — TaxSaathi knowledge base & evaluation set (M2)

*Version KB-2026-10-29. Rebuild everything with `python -m src.ingest.ingest` (KB) and
`python -m experiments.run_experiments --resplit` (splits).*

## 1. Knowledge base (what the system retrieves from)

| Field | Value |
|---|---|
| What it is | 107 short passages ("chunks") in plain English, each summarising one legal provision, rate notification or official FAQ answer |
| Sources | 17 source documents from official publishers: Income Tax Department e-filing help & FAQs (incometax.gov.in), incometaxindia.gov.in section pages of the Income-tax Act, 2025, CBIC tax-information portal (CGST Act & Rules, notifications), PIB release of the 56th GST Council recommendations (GST 2.0), GST portal tutorials. A few mapping/due-date facts only from reputable secondary sources (ClearTax, Upstox) — marked `verified: partial` |
| Download / access date | 2026-10-29 (every URL recorded per chunk and in `docs/research/sources_*.md`) |
| Licence | Public government documents (Government Open Data / public-domain statutory text). Our passages are summaries written by the team |
| Laws covered | `gst` 46 · `general` 23 (rule same under both Income-tax Acts) · `old_act` (1961 Act, income up to 31 Mar 2026) 16 · `new_act` (2025 Act, Tax Year 2026-27 onward) 12 · `mapping` (old → new section numbers) 10 |
| Period metadata | 100% of chunks carry `effective_from` (and `effective_to` when superseded). E.g. GST rate chunks before/after 22 Sep 2025; new-regime slabs FY 2024-25 / FY 2025-26 / Tax Year 2026-27 |
| Verification | 72 chunks `verified: yes` (checked against an official page), 35 `partial` (secondary sources only) |
| Chunk size | 64–174 tokens by the ingest count (median 125); one idea per chunk |
| Language | English (Hinglish is handled at query time) |
| Format | `data/raw/curated/*.md` (front matter + one `## [ID] Title` block per chunk) → `data/processed/chunks.jsonl` |

### Explainer passage (added after the real-world check)
`IT-NEW-REBATE-EXPLAINED` (law `general`, section 156, valid from 1 Apr 2025, `verified: yes`) answers the most
common real confusion we found: *"no tax up to ₹12 lakh, but the slab table says 5% from ₹4 lakh?"* (10 of
the 80 real questions). It explains that slab tax at ₹12 lakh is ₹60,000 and the rebate (87A / section 156)
cancels it, that a salaried person gets about ₹12.75 lakh tax-free after the ₹75,000 standard deduction, and
that above ₹12 lakh every slab is taxed (with marginal relief just above). It is the 107th chunk.

### Preprocessing steps
1. Facts researched and checked against official sources (see `docs/research/`); every claim recorded with its URL.
2. Written as one passage per legal provision ("chunk by legal section", not fixed-length windows) so a citation points to a real section and a provision is never split mid-sentence.
3. Each passage tagged with: law, section number, topic, `effective_from`/`effective_to`, source title/URL/publisher, verification status.
4. `ingest.py` parses, validates (unique IDs, valid dates, required fields) and writes `chunks.jsonl`. It can also parse raw PDFs dropped into `data/raw/pdfs/` with PyMuPDF (header/footer removal, split by section headings, ~400-token windows with overlap for very long sections).

### Known gaps
- Summaries, not full statutory text: provisos and rare exceptions may be missing.
- Out of scope by design: corporate tax, capital gains beyond basics, international tax, exports/e-way bills, GST disputes.
- ITR forms for Tax Year 2026-27 were not yet notified on 2026-10-29; the KB says so.
- Some new-Act section numbers (e.g. 143→270, 148→280) are confirmed only by secondary sources.

## 2. Evaluation set (gold questions)

| Field | Value |
|---|---|
| Size | 176 questions (158 answerable, 18 must be refused) |
| Categories | income_tax 60 · gst 42 · time_trap 26 · calculation 18 · out_of_scope 18 · hinglish 12 |
| Language | English 164 · Hinglish 12 |
| Per row | question, reference answer, gold passage IDs, category, language, difficulty, answerable, key facts, intent |
| Written by | the team, from the three personas (first-job salaried, freelancer, small shop owner); calculation answers hand-worked and cross-checked against the calculator |
| Split | stratified by category, seed 42: **30% dev (53)** for all tuning, **70% test (123)** untouched until final M4 numbers |
| Leakage control | thresholds, prompts and dictionaries tuned on dev only; intent-classifier training data (`intent_train.jsonl`, 342 rows) written separately and checked to contain no gold or real question |

Why a split if nothing is "trained" on the knowledge base? We still *tune* things (refusal threshold,
how many passages, prompt wording). Tuning on the same questions we report would make the numbers look
better than reality — that is test-set leakage. So tuning uses only dev; test is touched once.

## 3. Extra evaluation set: real questions (not used for tuning)

| Field | Value |
|---|---|
| File | `data/eval/real_questions.jsonl`, 80 rows (R001–R080), collected 2026-10-29 |
| Where from | Reddit 36 (r/IndiaTax, r/personalfinanceindia and others), official FAQs 25 (incometax.gov.in 13, GST Council / PIB 56th Council FAQ 9, tutorial.gst.gov.in 3), forums 12 (CAclubindia 11, one YouTube comment), Quora 7 |
| How collected | about 45 Tavily web searches and about 20 pages opened. Reddit and Quora block automated fetching, so those rows use the post title plus the search-result snippet, with the real post URL |
| Cleaning | typos fixed, names and usernames removed, long posts cut to the core question; facts never changed; official FAQ questions verbatim; Hinglish kept as written |
| Labels | gold chunk IDs (only where a chunk clearly answers), `covered` full 51 / partial 18 / none 11, `answerable` 73 / 7 out of scope, key facts only where certain |
| Dates | real posting dates for CAclubindia; Reddit dates estimated from the post ID (about ±1 month); Quora and official FAQs undated |
| Language | 79 English, 1 Hinglish (real written Hinglish is rare in public, indexed text) |
| Use | a one-off real-world check of the final system (see `M3_experiment_log.md`); it was never used to tune thresholds, prompts or the intent classifier |
| Ethics | public pages only, no login; no usernames, names, PANs or phone numbers stored; short quotes or close paraphrases for non-commercial research, each with its source link; not redistributed as a dataset |

Full method, counts and findings: `docs/research/real_questions_sources.md`.

## 4. Privacy
- The knowledge base contains no personal data (only public law).
- Gold and intent data are synthetic; no real taxpayer documents are used. The 80 real questions are public posts with names and usernames removed.
- Every user query is passed through a PII scrubber (PAN, Aadhaar, phone, email) before it is logged
  (`logs/queries.jsonl`); logs store no names or identifiers.
