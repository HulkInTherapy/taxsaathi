# M1 — Problem Brief: TaxSaathi

*A grounded, period-aware tax helper for Indian income tax and GST, in English and Hinglish.*
Version 1.0 · 2026-10-29 · Course project (4th-year NLP), milestones M1 to M3

---

## 1. The problem: everyday tax questions route through a CA

Most Indian taxpayers' questions are not hard cases. They are routine ones: "Which regime is better for me?", "Is my YouTube income business income?", "What GST rate applies to this item now?". Today people answer them in one of three ways:

1. **Pay a Chartered Accountant (CA) or an assisted-filing service.** This costs money and takes time, even when the question needs one paragraph of the law.
2. **Search the web.** The results mix outdated blog posts, pre-reform rates and marketing pages.
3. **Ask a general chatbot.** It answers fluently, but it does not say which law or period its answer rests on, and it can make things up (see §8 and `related_work.md`, Magesh et al. 2025).

In 2025–26 the problem got worse, because **two major law changes landed within seven months of each other**. Answers that were correct in 2025 are now wrong for current periods, and the reverse is also true.

## 2. The two law changes, and why they make "period" a first-class concept

| Change | What happened | Verified source |
|---|---|---|
| **Income-tax Act, 2025** | Replaces the Income-tax Act, 1961. Passed by Parliament 12 Aug 2025; Presidential assent 21 Aug 2025; **in force from 1 April 2026**. The Income-tax Rules, 2026 were notified on 20 Mar 2026. The Act replaces "Assessment Year" and "Previous Year" with a single **"Tax Year"**, "defined as the twelve-month period of the financial year commencing on the 1st April". | PIB backgrounder "The Income Tax Act, 2025: Reshaping Tax Framework" (3 Sep 2025), [static.pib.gov.in PDF](https://static.pib.gov.in/WriteReadData/specificdocs/documents/2025/sep/doc202593626601.pdf); CBDT press release of 1 Apr 2026, [PIB PRID 2248005](https://www.pib.gov.in/PressReleasePage.aspx?PRID=2248005), as reproduced on [TaxGuru](https://taxguru.in/income-tax/income-tax-act-2025-force-1st-april-2026.html) |
| **"GST 2.0" (next-generation GST reforms)** | The 56th GST Council meeting (3 Sep 2025) recommended replacing the four-slab structure with "a 2 rate structure with a Standard Rate of 18% and a Merit Rate of 5%; a special de-merit rate of 40% for a select few". Rate changes were to be "implemented with effect from **22nd September 2025**". Tobacco products and pan masala stay at the existing rates until the compensation-cess loans are repaid. | PIB release "Recommendations of the 56th Meeting of the GST Council", 3 Sep 2025, [gstcouncil.gov.in PDF](https://gstcouncil.gov.in/sites/default/files/2025-09/press_release_press_information_bureau_0.pdf) ([PIB PRID 2163555](https://www.pib.gov.in/PressReleasePage.aspx?PRID=2163555)) |

**What this means for the system.** The same question ("What's the GST on a small car?", "Which section gives the 80C-type deduction?") now has **different correct answers depending on the period**:

- Income earned up to 31 Mar 2026 → Income-tax Act, 1961 (FY/AY vocabulary).
- Tax Year 2026-27 onward → Income-tax Act, 2025 (Tax Year vocabulary, renumbered sections).
- GST supplies before 22 Sep 2025 → old slabs; from 22 Sep 2025 → 5% / 18% / 40%.

A model trained on pre-2026 web text cannot know which applies. TaxSaathi therefore treats **the period as an input to retrieval**: every knowledge chunk carries `effective_from` / `effective_to` dates (SPEC §KB format).

## 3. Scale of the problem (verified statistics)

| Statistic | Value | Source (accessed 2026-10-29) |
|---|---|---|
| ITRs filed for AY 2026-27 (income of FY 2025-26) | "A record **7.8 crore+** ITRs have been filed for AY 2026-27 as on August 31, 2026" (I-T Department post on X, reported by PTI) | [Telangana Today / PTI, 1 Sep 2026](https://telanganatoday.com/record-7-8-crore-itrs-filed-for-ay-2026-27) |
| Individual taxpayers | "There are about **8.5 crore** individual taxpayers" (CBDT Chairman Ravi Agrawal, 3 Feb 2025) | [Business Today, 3 Feb 2025](https://www.businesstoday.in/latest/economy/story/budget-2025-cbdt-chief-dismisses-talk-of-silent-burial-for-old-tax-regime-expects-97-shift-to-new-system-463213-2025-02-03) |
| Share choosing the new regime | "In AY 2025-26, **88%** of income taxpayers under ITRs 1,2,3,4 had moved to the new income tax regime", up from **76%** in AY 2024-25 (attributed to a post-Budget interview with the CBDT Chairman) | [Business Today, 4 Feb 2026](https://www.businesstoday.in/personal-finance/tax/story/taxpayers-to-get-simplified-income-tax-regime-from-april-1-as-budget-proposals-new-i-t-act-come-into-play-514641-2026-02-04) |
| Active GST taxpayers | **1,67,14,646** total active taxpayers as on 30 Jun 2026 (1,48,70,332 normal) | GSTN, *9 Years of GST: A Statistical Report*, [tutorial.gst.gov.in PDF](https://tutorial.gst.gov.in/offlineutilities/gst_statistics/9YearsReport.pdf) |
| Composition taxpayers | **13,55,180** as on 30 Jun 2026 | same GSTN report |
| CA fee, ICAI recommended minimum (individual return with salary / other sources) | "Rs. 6,000/- & Above" (Class A cities), "Rs. 4,000/- & Above" (Class B). These are recommended *minimum* scales, not market prices. The copy we found is hosted on a state-government site, and its PDF metadata dates it to 2018. | ICAI "Revised Minimum Recommended Scale of Fees", [copy hosted by NHM UP](https://nhm.up.gov.in/assets/site-files/tenders/new_document/Minimum%20fee%20recomended%20by%20ICAI.pdf) |
| CA fee, typical market rate | "According to Motilal Oswal, Chartered Accountant fees for full tax filing services typically range from Rs 1,500 to Rs 2,000"; complex filings up to about Rs 20,000 | [Republic World, 31 Jul 2024](https://www.republicworld.com/business/personal-finance/how-much-is-your-tax-filing-really-worth-uncovering-the-range-of-ca-fees) |
| Assisted-filing platform price | ClearTax "Salary/House rent income" plan shown at ₹999, next to ₹1,999 (the page does not say which is the sale price) | [clear.in/s/pricing](https://www.clear.in/s/pricing/) (accessed 2026-10-29) |

**Reading the numbers.** About 7.8 crore returns and about 1.67 crore GST registrations a year. Even at the low end of the market (about ₹1,000–2,000 per assisted return), simple help adds up to a large aggregate spend. Much of it goes to questions a cited paragraph of the law could answer. We do **not** claim a total market size, because we found no verified figure for how many filers actually pay a CA.

## 4. Personas and realistic questions

| Persona | Situation | Example questions (English / Hinglish) | What they need |
|---|---|---|---|
| **Priya, 23, salaried first-jobber** | First job in Pune, received Form 16, has never filed | "Old regime ya new regime, kaunsa better hai mere liye? Salary 9.5 lakh hai." · "What is the standard deduction for Tax Year 2026-27?" · "Form 16 mein jo 'Part B' hai woh kya hota hai?" | A regime comparison she can trust (deterministic calculator), plain-language explanations, a citation she can show her HR or parents |
| **Arjun, 27, freelancer / content creator** | YouTube + brand deals + some freelance design | "YouTube income pe tax kaise lagta hai — salary ya business?" · "Do I need GST registration for brand deals?" · "Presumptive taxation freelancers ke liye applicable hai kya?" | Correct *category* of income, thresholds, a clear signal when the case is complex enough to need a CA |
| **Ramesh-ji, 52, small kirana/hardware shop owner** | Composition-scheme GST dealer in a tier-3 town | "22 September ke baad cement pe GST kitna hai?" · "Composition scheme mein kya main bill pe GST charge kar sakta hoon?" · "Pichhle saal ke invoice pe purana rate lagega ya naya?" | Period-correct GST rates (before/after 22 Sep 2025), Hinglish, short answers, refusal plus "talk to your CA" on notices or disputes |

> Example questions are illustrative and written by the team. TaxSaathi's answers to them come from the curated knowledge base, not from this brief.

## 5. Business objective

**Give a first answer to routine Indian tax questions for free and in seconds, with a citation and a period on every answer, and hand off hard cases to a CA.** We do not try to replace the CA. We aim to:

1. Cut the number of routine questions that need a paid consultation.
2. Make the user better informed when they do go to a CA ("I'm on the new regime; my question is about s.202 for Tax Year 2026-27").
3. Never give a confident wrong answer in a domain where wrong answers cost money.

## 6. Success metrics, fixed before building

These targets were set **before** any experiment was run. They are not tuned after seeing results.

| # | Metric | Target | Measured on |
|---|---|---|---|
| 1 | Retrieval **Recall@5** (gold chunk in the top 5) | **≥ 0.85** | answerable dev/test questions |
| 2 | **Faithfulness** (share of answer sentences supported by a cited passage) | **≥ 0.90** | answerable questions |
| 3 | **Correct refusal** on out-of-scope questions | **≥ 90%** | `category = out_of_scope` |
| 4 | **Calculator exact match** with hand-worked examples | **100%** | `tests/` hand-computed cases |
| 5 | **Median latency** | **≤ 5 s** | see note |

*Latency note.* The 5 s target assumes a GPU or hosted-API deployment. Our project VPS has 4 vCPU, 8 GB RAM and no GPU, and runs a 1.5B–3B local model. On it we **report measured latency honestly** and do not claim the target unless we hit it.

Secondary diagnostics (defined in `report_draft.md` §6): MRR, nDCG@5, period accuracy, key-fact accuracy, citation validity.

## 7. Feasibility and risks

| Area | Assessment | Mitigation |
|---|---|---|
| Data | Official sources are public (incometaxindia.gov.in, cbic-gst.gov.in, PIB). Some government sites block automated download (we hit HTTP 403 on incometaxindia.gov.in during research). | A curated summary corpus written section by section, each chunk with its source URL and `verified: yes/partial` |
| Compute | CPU-only VPS; a small LLM is slow and weak | The LLM only *explains*. Retrieval, refusal and arithmetic do not depend on it. Reranking runs on the top 20 only. |
| Correctness | Legal text is renumbered (1961 → 2025 Act); mistakes are costly | Date filter, section-mapping chunks, citation check, CA escalation, disclaimer |
| Evaluation | No public Indian-tax QA benchmark that we found | Team-authored gold set with a stratified dev/test split. Limitation: not yet CA-reviewed. |
| Legal / ethical | Users may treat answers as advice | Clear "informational, not professional advice" disclaimer; refusals on notices, disputes and personal-liability questions |
| Privacy | Users may type PAN, Aadhaar or phone numbers | Regex PII scrub before logging (SPEC step 1) |
| Naming | The I-T Department launched an AI assistant called **"Kar Saathi"** (*kar* = tax) in April 2026 | Make clear in the demo that TaxSaathi is a student project with no link to the department; consider renaming before any public release |

## 8. Positioning: a helper, not a CA

TaxSaathi is an **informational assistant**. It explains what the law says, for which period, and where it says it. It does not file returns, give personalised professional advice, or represent anyone before the department. When the question goes beyond the knowledge base, or retrieval confidence is low, it says so and recommends a CA.

## 9. Landscape (verified claims only)

| Offering | What we verified | How TaxSaathi differs |
|---|---|---|
| **Income Tax Department "Kar Saathi"** | An "AI-based virtual assistant integrated into the newly revamped Income Tax portal", announced 2 Apr 2026. It answers questions on filing, notices, refunds and compliance, and its FAQs and guidance cover "over 2,000+ topics" ([Business Today, 12 Apr 2026](https://www.businesstoday.in/personal-finance/tax/story/bt-explainer-what-is-kar-saathi-income-tax-depts-ai-chatbot-to-simplify-itr-filing-525230-2026-04-12)). The article does not say which languages it supports or how accurate it is. | Ours is an open, inspectable research prototype. It shows per-answer citations with effective dates, Hinglish normalisation, an explicit period trace, and a published evaluation. |
| **ClearTax (assisted filing)** | Sells CA/expert-assisted filing plans; salaried plan listed at ₹999 / ₹1,999 on the pricing page ([clear.in/s/pricing](https://www.clear.in/s/pricing/)). One plan lists "Accuracy Check (AI + Expert)" ([cleartax.in/ca-for-itr-filing](https://cleartax.in/ca-for-itr-filing)). | Ours is free, explains rather than files, and escalates to a CA instead of selling a filing service. |
| **General chatbots** | No India-specific claim verified. The best evidence we have is indirect: in a preregistered study, even legal-research RAG tools "each hallucinate between 17% and 33% of the time", while general chatbots (GPT-4) hallucinated more ([Magesh et al.](https://arxiv.org/abs/2405.20362)). | Ours answers only from a dated, cited corpus; arithmetic is done by code; it refuses when unsure. |

---
*Sources are listed inline. Every number in this brief was checked against the linked page on 2026-10-29. Where we could only reach a mirror (incometaxindia.gov.in and pib.gov.in returned HTTP 403 to our fetcher), the mirror is named.*
