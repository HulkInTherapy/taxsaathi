# TaxSaathi demo cheat-sheet (one page)

**URL:** https://taxsaathi.taild58d86.ts.net · **Backup:** https://taxsaathi.taild58d86.ts.net/?mock=1

Before you start: open the site once (the dot top-right should say **Live**). Answers take **15–40 s**
(Compare **1–2 min**) because a 3B AI runs on a CPU server. **Fill the wait:** open "How this was found"
on the previous answer, or say what the pipeline is doing right now. Answers below were checked on the
live system on 29 Oct 2026.

| # | Where / type exactly | Point at on screen | Expected answer (one line) |
|---|---|---|---|
| 1 | **Compare** tab → trap pill **"GST on AC in Aug 2025"** (or type *What was GST on AC in August 2025?*) → Compare | Left card: red "No source · may be outdated". Right card: big **28%**, "Cited · law for August 2025", "8 outdated passages dropped". The timeline at the bottom: TaxSaathi sits on August 2025, before GST 2.0 | Plain AI: *"GST rates for AC were not set for August 2025 as it changes annually…"* (no number, no source). TaxSaathi: **28%** on ACs (HSN 8415) in Aug 2025, 1 source (≈26 s) |
| 2 | **Ask** tab: *Naye regime mein standard deduction kitna hai?* | "Law applied: Tax Year 2026-27 · Income-tax Act, 2025 · current law"; source card "IT Act 2025 · s. 19". Open **How this was found** → Hinglish fix (naye → new, kitna → how much), "no date mentioned, using current law" | **₹75,000** standard deduction in the new regime, section 19 of the Income-tax Act, 2025 (≈19 s) |
| 3 | *Is 80C still available in the new Income-tax Act?* | Source card **"Section map · s. 80C → 123"** | **Yes, as section 123**, up to **₹1,50,000** (PF, PPF, ELSS, LIC…); the new regime (s.202(2)) does not allow these deductions, so only if you opt for the old regime (≈19 s) |
| 4 | *how much tax do i have to pay if i am earning 5k us dollars per month remote* | The calculator card: "US$5,000 a month × 12… converted at ₹95.2278 per US$ (RBI/FBIL reference rate)", "section 58… 50% of gross receipts", "Calculated by exact code, not the AI" | **New regime ₹4,54,532 vs old ₹6,96,332 — new saves ₹2,41,800** (₹57,13,668 receipts, ₹28,56,834 taxable as a freelancer) (≈27 s) |
| 5 | *How do I avoid tax on foreign crypto income?* | Amber card "This needs a Chartered Accountant" + ICAI link | **Refused** and sent to a CA (out of scope / tax avoidance) (≈8 s) |

**Say while it works:** (1) "Same AI model on both sides; the only difference is retrieval + the date filter."
(2) "The translator is a 150-entry phrasebook, every swap is visible." (3) "80C was renumbered; our map
passages bridge the two Acts." (4) "Numbers and the verdict come only from the calculator; the AI just
explains." (5) "Saying no is a feature."

**Spare trap (if asked for another, or Q1's left card looks weak):** Compare → pill **"87A rebate limit now"**.
Plain AI: *"…Rs 50,000 for the financial year 2022-23"* (out of date). TaxSaathi: **₹60,000** if total income is up to
₹12 lakh, Tax Year 2026-27 (≈22 s). Avoid the "GST on an AC today" pill: both sides say 18%, so there is no contrast.

## 3 numbers to say out loud

1. **Recall@5 = 0.917**: the right passage is in the top 5 for 92% of dev questions.
2. **Key facts 10% → 69%**: the same AI from memory vs with retrieval (B0 → C6).
3. **Calculator 100% exact** (16/16 hand-worked cases, 99 tests). **4 of 5 targets met**; the miss is speed (16.8 s median on CPU).

## Backup plan

- **Slow (> 60 s) or error:** keep talking (open "How this was found" on an earlier answer), then retry once.
- **Server down or very slow:** go to **https://taxsaathi.taild58d86.ts.net/?mock=1** (or Advanced, the sliders icon
  top right → scroll down → "Switch to offline demo mode"). The 5 questions above (and the 87A trap) replay the real recorded
  answers in 1–3 s; the Results and library numbers are the real ones. Say "this is the recorded demo mode".
  Type the questions exactly as written here.
- **Nothing loads:** use the screenshots in the slides.
- **Don't** type other questions in demo mode: only the recorded ones are real.
