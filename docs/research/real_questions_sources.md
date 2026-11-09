# Real taxpayer questions: sources, method and findings

File: `data/eval/real_questions.jsonl` (80 rows, ids R001–R080). Collected 2026-10-29.

The gold set (`data/eval/gold.jsonl`) was written by the team. This file holds questions that real Indian
taxpayers asked in public, plus official FAQ questions, so we can check TaxSaathi on real wording and real
confusions and measure how much of real demand the 106-chunk knowledge base covers.

## How the data was collected

1. **Search.** About 45 Tavily web-search API calls, mostly restricted to `reddit.com`, `quora.com` and
   `caclubindia.com`. Queries covered new-regime standard deduction, the 12 lakh rebate, old vs new regime,
   GST registration for freelancers, composition scheme, GST 2.0 rate cuts, health-insurance GST,
   44ADA, advance tax, HRA, NPS 80CCD(2), late fees, Income-tax Act 2025 / tax year, 80C to section 123,
   crypto/NRI (for out-of-scope), and Hinglish phrasings ("lena padega", "milega kya", "kitna tax lagega").
2. **Opening pages.** About 20 pages were opened with WebFetch:
   - 11 CAclubindia threads, to get the exact question text and posting date.
   - 3 official FAQ pages: the incometax.gov.in new-vs-old regime FAQ, the incometax.gov.in
     "Objective and scope of the New Act" FAQ, and the tutorial.gst.gov.in composition FAQ.
   - The GST Council PDF "FAQs on the decisions of the 56th GST Council" (PIB, 3 Sep 2025, 73 questions),
     extracted with `pdftotext`.
3. **Reddit and Quora could not be opened.** Both block automated fetching (403 errors, and Tavily
   extract also failed). For these rows the question comes from the post **title plus the post-text
   snippet shown in search results**. The source URL is the real post URL from those results.
4. **Light cleaning.** Typos were fixed, usernames and names removed, and long posts cut to the core
   question. Where only a title or fragment was visible, a short clause was added to make the question
   explicit. This applies to R002, R004, R023, R024, R035, R039, R040, R041, R044, R049, R070, R077, R078
   and R079; the facts in each question were not changed. Official FAQ questions are verbatim. In R018–R020
   the bracketed tail summarises a question that the FAQ page cut short. All Hinglish and informal wording
   is kept as written.
5. **Labelling.**
   - Each question was checked against the text of all 106 chunks in `data/processed/chunks.jsonl`.
   - `gold_chunk_ids` is filled only when a chunk clearly answers the question.
   - `covered`: full means the KB answers the whole question, partial means part of it, none means the KB
     does not answer it.
   - `answerable=false` marks questions outside TaxSaathi's scope: NRI or residency, crypto, foreign stocks,
     capital-gains detail, notices, assessment and GAAR, ITR-U, and help with tax evasion.
   - `key_facts` is given only when the correct answer is certain.
6. **Validation.** Checked with system `python3`: every line parses, all 12 fields are present, the enum
   values are valid, ids are unique, and every `gold_chunk_id` exists in `chunks.jsonl` (0 missing).
   58 distinct chunks are used as gold.

**Dates.**
- CAclubindia dates are the real posting dates.
- GST Council FAQ rows are dated 2025-09.
- Reddit rows (36) have **estimated** dates. The estimate interpolates the base-36 Reddit post ID between
  known anchors: the Budget-day posts of 1 Feb 2025, the GST Council announcement of 3 Sep 2025,
  1 Jan 2026 and the ITR deadline of 31 Jul / 1 Aug 2026. Treat these as accurate to about ±1 month.
- Quora, incometax.gov.in and tutorial.gst.gov.in rows have `date: null` because those pages show no date.

## Counts

| Source type | Rows | Domains |
|---|---|---|
| reddit | 36 | r/IndiaTax, r/personalfinanceindia, r/IncomeTax_India, r/FinancialAdviceIndia, r/IndianStockMarket, r/IndianGaming, r/CryptoIndia |
| official_faq | 25 | incometax.gov.in (13), GST Council / PIB 56th Council FAQ (9), tutorial.gst.gov.in (3) |
| forum | 12 | caclubindia.com (11), YouTube comment (1) |
| quora | 7 | quora.com |

| Category | Rows | | Coverage | Rows |
|---|---|---|---|---|
| income_tax | 31 | | full | 51 |
| gst | 23 | | partial | 18 |
| time_trap | 11 | | none | 11 |
| calculation | 7 | | | |
| out_of_scope | 7 | | | |
| hinglish | 1 | | | |

- **Language:** en 79, hinglish 1.
- **Intent:** question 66, calculation 7, out_of_scope 7.
- **Answerable:** 73 true, 7 false. Among the 73 in-scope questions, coverage is full 51 (70%),
  partial 16 (22%) and none 6 (8%).
- **Year of question:** 2024: 5, 2025: 35, 2026: 16, unknown: 24.

| Coverage by source | full | partial | none |
|---|---|---|---|
| reddit | 22 | 9 | 5 |
| official_faq | 19 | 3 | 3 |
| quora | 6 | 0 | 1 |
| forum | 4 | 6 | 2 |

Real forum questions (CAclubindia and Reddit) are much less often fully covered than official FAQs. They
mix several issues in one post, such as inter-state clients plus "GST inclusive" pricing plus income tax.

**Main gaps the KB does not cover:**
- GST transition rules: old stock, credit notes, invoice date vs supply date (3 rows, all none).
- Export of services and foreign clients (3 rows, partial).
- Whether a person is required to file a return at all.
- GST penalties for not registering.
- Medicines and other items with no rate chunk.
- Restaurant or retail price behaviour after GST cuts (the anti-profiteering type).

**Hinglish finding.** Real Hinglish *written* questions are rare in public, indexed text. Reddit, Quora and
CAclubindia users write in English. The Hinglish we found was in YouTube video titles written by creators
(not taxpayers, so excluded) and in YouTube comments, which search indexes very poorly. Only 1 genuine
Hinglish question (R054) was found. Hinglish evaluation should still rely on the team-written Hinglish
gold items, or on a small user study. This is worth saying in the presentation.

## Licensing and ethics

- Only public pages were used. No login, no scraping behind authentication, no private groups.
- No usernames, real names, PANs or phone numbers are stored. The one personal name in a CAclubindia post
  (R052) was removed.
- Questions are short quotes or close paraphrases kept only for non-commercial research evaluation, each
  with a link to its source. This is fair use or fair dealing for research.
- Reddit, Quora and CAclubindia content stays under their own terms. The file is not redistributed as a
  dataset.
- Official FAQs (incometax.gov.in, GST Council/PIB, GSTN tutorial) are Government of India publications,
  quoted with attribution.
- The answers on those pages were not copied as reference answers. Gold answers come only from our own
  knowledge-base chunks.

## Top 10 real confusions observed (rows can count in more than one theme)

| # | Confusion | Rows | Coverage |
|---|---|---|---|
| 1 | "Zero tax up to 12 / 12.75 lakh" vs the 5% slab on 4–8 lakh: rebate vs slabs, marginal relief just above 12 lakh, who gets the 75k | 10 (R001–R004, R006–R009, R011, R080) | 7 full, 3 partial |
| 2 | Old vs new regime: which to pick, and which deductions survive (80C, 80D, HRA, home loan) | 10 | 8 full, 2 partial |
| 3 | GST 2.0: what is the rate on item X now (car, AC/TV, soap, clothes, hotel, coffee, GPU, medicines) vs before 22 Sep 2025 | 9 | 5 full, 3 partial, 1 none |
| 4 | GST registration threshold for freelancers and small service providers: 20 lakh, when to register, what happens on crossing it | 8 | 4 full, 3 partial, 1 none |
| 5 | Income-tax Act 2025: tax year vs AY, renumbered sections (80C to 123, 115BAC to 202), which Act applies | 8 | 5 full, 2 partial, 1 none |
| 6 | Switching regimes: the myth that you can never go back, Form 10-IEA, employer declaration vs the choice in the ITR | 5 | 4 full, 1 partial |
| 7 | Presumptive taxation for freelancers: 44ADA 50%, 44AD 6/8%, new section 58, salaried + freelance | 5 | 4 full, 1 partial |
| 8 | Composition scheme eligibility and procedure: multiple GSTINs, e-commerce sales, services, CMP-02, returns | 5 | 5 full |
| 9 | Health/life insurance GST exemption: does my renewal or premium date fall before or after 22 Sep 2025 | 4 | 4 full |
| 10 | Standard deduction amount and who gets it (50k vs 75k, salary only) | 3 | 3 full |

Smaller themes:
- GST rate-change transition (stock, credit notes, invoice timing): 3 rows, all none.
- Foreign clients and export of services: 3 rows, all partial.
- Late filing fee (234F, 1,000 vs 5,000): 2 rows.
- Advance tax for freelancers: 2 rows.

Out-of-scope questions people really ask (7 rows): NRI or residency, crypto, US stocks under LRS,
STCG with the rebate, notices and proceedings, GAAR, and a fake-rent HRA claim that should be refused.

**Takeaway for the presentation.**
- Real questions cluster on time-sensitive numbers: 12 lakh, 75k, 22 Sep 2025, AY vs tax year. This
  supports the date-aware retrieval design.
- Two official FAQs are themselves time traps. R017 asks about a "Rs 50,000 standard deduction" that is
  now ₹75,000. R021's page still describes the AY 2024-25 rebate.
- The KB fully answers about 70% of in-scope real questions. The misses are mostly multi-issue forum posts
  and GST transition mechanics.

## Demo examples

Six real questions as asked. All are answerable and covered=full.

1. **Regime choice** (R011, Quora): "If a person is earning Rs 10 lakh per annum in India which tax regime are you going to suggest him, new tax regime or old tax regime?"
   - Gold: IT-NEW-REBATE-TY2627, IT-NEW-STDDED-TY2627, IT-OLD-DEDUCTIONS
2. **Standard deduction** (R005, CAclubindia, Jan 2025): "Could someone please advise the standard deduction for old regime and new regime applicable for the Financial Year 2024-25 (salaries)?"
   - Gold: IT-NEW-STDDED-1961
   - Key facts: 75,000 / 50,000
3. **GST on an item now vs before** (R069, Quora): "Will I get the benefit of 0% GST on paying premium after 22nd September 2025?"
   - Gold: GST-RATE-INSURANCE-POST, GST-RATE-INSURANCE-PRE
4. **GST registration threshold for freelancers** (R047, r/IndiaTax, about Feb 2026): "I just started freelancing as a software consultant. My current turnover is below ₹20L but I may add more clients going forward. Is GST registration mandatory?"
   - Gold: GST-REG-FREELANCER, GST-REG-THRESHOLD, GST-REG-VOLUNTARY
   - Key fact: 20 lakh
5. **80C under the new Act** (R027, r/FinancialAdviceIndia, about Aug–Sep 2026): "My ABSLI tax certificate says Section 123. Is this basically the old 80C? Pure term policy, annual premium ₹18,420, tax year 2026–27, filing under old regime."
   - Gold: IT-MAP-80C, IT-DED-80C
   - Key facts: 123, 1,50,000
6. **Informal phrasing** (R001, r/IndiaTax, Feb 2025): "It says no tax until 12L and also says 5% tax for 4-8L. I am confused. What does it mean?"
   - Gold: IT-NEW-SLABS-FY2526, IT-NEW-REBATE-FY2526
   - Key facts: 60,000, rebate
   - The only genuine Hinglish question, R054 ("Bhai mujhe GST lena h… rent agreement pr GST mil jayega?"), is only partially covered, so it does not meet the demo rule. Use it to show partial coverage or escalation.
