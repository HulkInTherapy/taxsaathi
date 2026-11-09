# TaxSaathi: Competitive UX Benchmark

**Date:** 2026-10-29
**Method:** All product claims below were checked by web search on 2026-10-29 (WebSearch, standard mode), and the key pages were opened with WebFetch. Each claim cites a URL from the Sources list. Where we could not confirm a claim, the cell says **not verified**. Absence of evidence is not evidence of absence: "not verified" means we could not confirm the feature, not that the product lacks it. Most Indian-tax product claims come from the vendors' own marketing pages or from press coverage, and we label them that way. We did not test any product hands-on.
**Scope:** This benchmark covers how each product handles the answer experience: citations, legal-period awareness, language, calculation, escalation, transparency, speed and first run. It does not compare filing features.

---

## 1. Comparison table

Legend: **Yes** = verified from a cited source; **Partial** = verified with caveats; **No** = a source states it is absent; **not verified** = no source found.

| Feature | Perplexity | ChatGPT / Claude | Google AI Overviews | ClearTax | TaxBuddy | Quicko | Kar Saathi (ITD) | TaxSaathi (ours) |
|---|---|---|---|---|---|---|---|---|
| **Citations to sources** | Yes. "Each answer includes numbered citations linking to the original sources" [S1] | Yes, when web search is used. Claude: "Every response includes citations" [S5]; ChatGPT: inline citations + Sources panel, per secondary sources only [S4] | Yes. Snapshot "with key information and links to dig deeper" [S6] | not verified (the AI page does not mention citations) [S10] | not verified (AI page does not mention citations) [S13] | n/a (calculator); the page cites sections of IT Act 2025 [S15] | not verified (press does not mention citations) [S18][S19] | Yes. Numbered source chips + chunk IDs for retrieved official passages |
| **Period / date awareness of law** | not verified | not verified | not verified | not verified | Partial. Regime article labelled "FY 2025-26" [S14] | Partial. Calculator slabs are labelled FY 2025-26 while the text cites IT Act 2025 sections [S15] | Partial. Launched for the IT Act 2025 transition and "Tax Year" terminology [S17][S18] | Yes. A period extractor + date filter applies only the law in force on the asked date (GST 2.0 from 22 Sep 2025; IT Act 1961 vs IT Act 2025 from 1 Apr 2026, "Tax Year 2026-27") |
| **Hinglish / Indian-language support** | not verified for answers (Hindi listed only in a language-learning feature) [S2] | not verified | Partial. English + Hindi in India since Aug 2024 [S8] | Yes. 7 languages incl. Hindi, Telugu, Tamil, Kannada, Marathi, Bangla (press) [S11] | not verified | not verified | Yes. Hindi and English, per one press source [S20] | Partial. Hinglish normalisation (romanised Hindi-English queries); no other Indian languages |
| **Deterministic calculator** | No (LLM answer engine) [S1] | not verified | not verified | Partial. Chat filing "fetches data and calculates your tax" (vendor) [S10]; the method is not described | Partial. "AI-driven income tax calculators" compare both regimes [S14]; whether the calculation is deterministic is not stated | Yes. Side-by-side old vs new comparison; formula published [S15] | not verified (ITD has a separate regime-comparison calculator, per press) [S22] | Yes. Old vs new regime computed by deterministic code, not the LLM (`[CALC]` lines) |
| **Refusal / escalation to a human expert (CA)** | not verified | not verified | Partial. Finance AIOs often show "consult a professional" (63.2% in a Sep 2024 third-party study) [S7] | Partial. Separate "Hire an Expert" offering; chatbot hand-off not described [S10] | Yes. "Complex cases can be routed to expert-assisted filing" [S13]; CA-reviewed assisted filing [S12] | Yes. "Book a Free Consultation" with an expert [S15] | No path described; press says complex cases need CAs/tax lawyers [S19][S20] | Yes. A safety gate refuses out-of-scope or low-confidence questions and suggests a CA |
| **Transparency of how the answer was produced** | Partial. Citations are the retrieved sources [S3]; mode labels (Search / Research) [S1] | Partial. A Sources button shows that search was used (secondary) [S4] | Partial. "AI responses may include mistakes"; supporting links [S6] | not verified | not verified | Yes for the calculation (formula + worked example) [S15] | not verified | Yes. The full step-by-step pipeline trace can be viewed |
| **Speed** | Fast for Search; Research takes "a few minutes" [S1] | not verified | not verified (shown inline in search results) | Vendor claims filing "in under three minutes" [S11] | not verified | not verified | not verified ("real time" claimed) [S19] | Worse. ~10-60 s per answer (small LLM on a CPU server) |
| **Simplicity of first run** | not verified | not verified | Yes. No setup; appears in normal Search [S6] | Partial. Chat filing needs an OTP login first [S10] | not verified (only a "Login" link seen) [S13] | not verified | Yes. General questions need no login; widget on incometax.gov.in [S20] | Yes. No account; type a question. (No filing, no accounts) |

**Coverage caveat (TaxSaathi):** answers are limited to a curated corpus of individual income tax + GST. General assistants and the ITD bot cover far more ground.

---

## 2. What each does best

**Perplexity**
- Answer-first layout with numbered inline citations mapped to retrieved sources [S1][S3].
- Suggests follow-up questions beneath the answer, and context carries across follow-ups [S1][S3].

**ChatGPT / Claude**
- Claude: web answers carry citations, and search can be toggled from the "+" menu or run automatically [S5].
- ChatGPT: thumbs-down under any response for feedback [S9]; a Sources button marks searched answers (secondary) [S4].
- Not verified from official pages: suggested starter prompts and copy buttons. We do not make claims about them here.

**Google AI Overviews**
- Zero-friction summary + supporting links inside the existing search page; thumbs up/down and "Report a problem" [S6].
- Visible caution on YMYL finance topics ("consult a professional") in many finance overviews [S7].
- Hindi and English in India, with a language toggle (press, 2024) [S8].

**ClearTax**
- Chat-based filing with OTP login, auto data fetch and a tax computation, with the user verifying the results (vendor) [S10].
- Broad Indian-language reach: 7 languages across WhatsApp, Slack, Teams and the web (press, Jul 2025) [S11].

**TaxBuddy**
- Clear AI-to-human route: "Route cases requiring deeper review to TaxBuddy's tax experts" [S13], plus CA-reviewed assisted filing [S12].
- Highlights whichever regime gives lower tax, along with switching conditions [S14].

**Quicko**
- Transparent regime comparison: a side-by-side worked example and a published formula ("Tax payable = Income tax at slab rates − Rebate (Section 156) + 4% Cess") [S15].
- Already uses IT Act 2025 section numbers (Sec 202, 202(4)) [S15]. Note the slab heading is still FY 2025-26.

**Kar Saathi (Income Tax Department)**
- Official, free, 24x7 assistant on the department's website; launched around 2 Apr 2026 with the IT Act 2025 transition (PRARAMBH outreach) [S17][S18][S19].
- Plain-language explanations, step-by-step ITR guidance, "2,000+ topics" of FAQs and guidance notes [S17]; no login needed for general questions [S20].
- Limitation: it cannot file an ITR for the user [S20].

**Design references**
- **Apple HIG:** the current "Design principles" page (reintroduced 8 Jun 2026) lists Purpose, Agency, Responsibility, Familiarity, Flexibility, Simplicity, Craft, Delight. The parts most relevant to us are "Be fully transparent about what your product does and why", "Provide clear feedback", "Be concise" and "Establish hierarchy" [S23]. The older trio of *clarity, deference, depth* is **not** on the current page. We saw it only in third-party summaries [S24], so we cite it as the historical framing.
- **Duolingo:** gradual engagement (lets users try before sign-up), progress bars that "set a user's expectations of effort", and encouraging mascot moments [S25]; immediate, recoverable feedback [S26].

---

## 3. What TaxSaathi adopts

| Pattern | Borrowed from | TaxSaathi implementation |
|---|---|---|
| Answer-first | Perplexity [S1], AI Overviews [S6] | A one-paragraph direct answer at the top; detail below |
| Numbered source chips | Perplexity [S1], Claude [S5] | `[1] [2]` chips inline; clicking one opens the official passage + chunk ID |
| Suggested example prompts in natural language | Common chat UX (not verified from official pages) | 4-6 starter cards on the empty state, mixing English and Hinglish, e.g. "80C limit kitna hai?" or "GST on hair oil after 22 Sep 2025" |
| Follow-up prompts | Perplexity [S3] | 2-3 follow-up chips after each answer |
| Thumbs / copy | AI Overviews [S6], ChatGPT [S9] | Thumbs up/down + copy answer (with citations) |
| Friendly progress narrative while waiting | Duolingo progress bars [S25]; HIG "Provide clear feedback" [S23] | Staged messages ("Finding the law in force for your date..." then "Reading 5 official passages..." then "Checking the numbers...") so the 10-60 s wait is legible |
| Regime calculator with one big result | Quicko side-by-side [S15], TaxBuddy "lower regime highlighted" [S14] | One large headline ("New regime saves you ₹X") over a two-column breakdown sourced from `[CALC]` lines |
| CA escalation card | TaxBuddy [S13], Quicko [S15] | When the safety gate fires: a polite card explaining why, plus "Consult a Chartered Accountant" |
| Progressive disclosure of technical detail | HIG "Include just what's necessary" / "Establish hierarchy" [S23] | Pipeline trace, chunk IDs and retrieval scores sit behind a collapsed "How this answer was made" panel |
| Visible caution on a YMYL topic | AI Overviews [S7] | A short footer: "Informational, not tax advice; verify with official text or a CA" |

---

## 4. Where TaxSaathi is genuinely better

- **Period-correct law.** We found no evidence that any benchmarked product filters retrieved law by the date in question. TaxSaathi applies only the provisions in force on that date: GST rates before vs after 22 Sep 2025, and IT Act 1961 vs IT Act 2025 / Tax Year 2026-27. Quicko's calculator page shows the risk: an FY 2025-26 slab heading sits next to IT Act 2025 section numbers [S15].
- **Calculation does not depend on the LLM.** Regime tax comes from deterministic code, and the `[CALC]` lines are shown. Quicko is also deterministic and transparent [S15], but it is a calculator, not a Q&A assistant. TaxBuddy and ClearTax do not describe how they compute [S10][S14].
- **Citations to official passages, at chunk level.** Perplexity and Claude cite web pages [S1][S5]. TaxSaathi cites the specific official passage. We did not find citations described for ClearTax AI, TaxBuddy AI or Kar Saathi.
- **Inspectable pipeline.** A full step-by-step trace is available. None of the products we examined documents an equivalent view. This matches the HIG "be fully transparent" principle [S23].
- **Explicit refusal plus a CA suggestion** for out-of-scope or low-confidence questions. Kar Saathi coverage describes no escalation path [S20].

## 5. Where TaxSaathi is honestly worse

- **Speed:** ~10-60 s per answer (small LLM on a CPU server). Perplexity's standard search and AI Overviews are effectively instant by comparison, and ClearTax claims sub-3-minute *filing* [S11].
- **Coverage:** only a curated corpus of individual income tax + GST. There is no capital gains depth, business income, notices or refunds. Kar Saathi claims "2,000+ topics" [S17], and general assistants cover the open web.
- **Languages:** we handle Hinglish normalisation only. ClearTax supports 7 languages [S11], and Kar Saathi supports Hindi + English [S20].
- **No accounts and no filing:** we cannot fetch AIS/26AS, file returns or check refunds. ClearTax [S10], TaxBuddy [S13] and Kar Saathi (with login) [S20] go further.
- **No human behind the CA card:** we suggest a CA but do not connect to one, unlike TaxBuddy [S12][S13] or Quicko [S15].
- **No authority:** Kar Saathi is the department's own channel [S18]. TaxSaathi is a university project and its answers are informational only.

---

## 6. Not verified (for transparency)

- Kar Saathi: its exact URL path, whether it cites sources, how it handles disclaimers, and any escalation to a human. Hindi support comes from a single secondary source [S20]. Business Standard's explainer returned HTTP 403. The incometax.gov.in home page we fetched did not mention Kar Saathi, although it does use "Tax Year 2026-27" [S21].
- ChatGPT: the official help article on search citations returned HTTP 403, so the layout is described from secondary sources only [S4]. We could not verify starter prompts or a copy button from an official page.
- Google: we found no official statement on YMYL-specific disclaimers. The 63.2% figure is a third-party study from Sep 2024 [S7].
- Perplexity: Hindi *answer* quality was not verified.
- Speed for all third-party products, except the vendor and Perplexity statements cited.

---

## Sources

- [S1] Perplexity Help Center, "How does Perplexity work?": https://www.perplexity.ai/help-center/en/articles/10352895-how-does-perplexity-work
- [S2] Free Press Journal, Perplexity language-learning feature: https://www.freepressjournal.in/tech/perplexity-takes-on-duolingo-with-new-language-learning-feature-on-ios-web-heres-how-to-use-it
- [S3] LLM Pulse, "How Does Perplexity Work?": https://llmpulse.ai/blog/how-perplexity-works/
- [S4] GEO Toolbox, "How ChatGPT Cites Sources" (secondary): https://geotoolbox.ai/blog/chatgpt-citations
- [S5] Claude Help Center, "Enabling and using web search": https://support.claude.com/en/articles/10684626-enabling-and-using-web-search
- [S6] Google Search Help, AI Overviews: https://support.google.com/websearch/answer/14901683
- [S7] SE Ranking, "AI Overviews and YMYL topics research" (data 15 Sep 2024): https://seranking.com/blog/ai-overviews-and-ymyl-topics-research/
- [S8] Inc42, AI Overviews in India with English and Hindi: https://inc42.com/buzz/google-search-to-expand-ai-overviews-to-india-with-english-and-hindi-languages-support
- [S9] OpenAI, Model behavior feedback form (deprecated; points to the thumbs-down icon): https://openai.com/form/model-behavior-feedback
- [S10] ClearTax, "ClearTax AI: Key Features, Benefits and Tax Filing Guide": https://cleartax.in/s/cleartax-ai-itr-filing-guide
- [S11] Deccan Chronicle, ClearTax AI in Telugu / 7 languages (9 Jul 2025): https://www.deccanchronicle.com/technology/cleartax-enables-income-tax-filing-in-telugu-via-ai-assistant-1890383
- [S12] TaxBuddy blog, Assisted filing with CA review: https://www.taxbuddy.com/blog/assisted-filing-ca-review
- [S13] TaxBuddy AI product page: https://www.taxbuddy.com/taxbuddy-ai
- [S14] TaxBuddy blog, old vs new regime evaluation: https://www.taxbuddy.com/blog/how-taxbuddy-evaluates-old-vs-new-tax-regime-for-different-income-profiles
- [S15] Quicko Income Tax Calculator: https://quicko.com/tools/income-tax-calculator
- [S16] ClearTax, AI Assisted Filing: https://cleartax.in/s/ai-assisted-filing
- [S17] Business Today, "BT Explainer: What is Kar Saathi" (12 Apr 2026): https://www.businesstoday.in/personal-finance/tax/story/bt-explainer-what-is-kar-saathi-income-tax-depts-ai-chatbot-to-simplify-itr-filing-525230-2026-04-12
- [S18] Free Press Journal, "AI-Powered 'Kar Saathi' Launched" (2 Apr 2026): https://www.freepressjournal.in/business/ai-powered-kar-saathi-launched-cbdt-simplifies-itr-filing-under-new-tax-regime
- [S19] Outlook Money, "New AI tax assistant Kar Saathi...": https://www.outlookmoney.com/tax/new-ai-tax-assistant-kar-saathi-signals-big-shift-in-how-indians-may-file-itrs
- [S20] Angel One, "How To Access and Use Kar Saathi": https://www.angelone.in/news/taxation/how-to-access-and-use-kar-saathi-the-it-department-s-ai-chatbot-for-simpler-itr-filing
- [S21] Income Tax e-filing portal home page: https://www.incometax.gov.in/iec/foportal/
- [S22] Outlook Business, ITD regime-comparison calculator: https://business.outlookindia.com/news/income-tax-calculator-now-you-can-easily-compare-old-new-tax-regimes-news-265051
- [S23] Apple HIG, "Design principles" (change log: reintroduced 8 Jun 2026): https://developer.apple.com/design/human-interface-guidelines/design-principles
- [S24] Netguru, iOS HIG summary (clarity / deference / depth, secondary): https://netguru.com/blog/ios-human-interface-guidelines
- [S25] Appcues GoodUX, "Duolingo's delightful user onboarding experience": https://goodux.appcues.com/blog/duolingo-user-onboarding
- [S26] UX Planet, "Analyzing Duolingo from Product Design Perspective": https://uxplanet.org/analyzing-duolingo-from-product-design-perspective-after-400-days-of-non-stop-practice-c4d4809bdb37
- Also consulted: Business Today launch report (2 Apr 2026): https://www.businesstoday.in/personal-finance/tax/story/income-tax-dept-launches-kar-saathi-ai-chatbot-with-new-website-ahead-of-itr-season-523728-2026-04-02 ; ClearTax Aaykar Setu guide: https://cleartax.in/s/aaykar-setu-app-income-tax
