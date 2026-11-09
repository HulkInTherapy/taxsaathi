/* TaxSaathi — MOCK MODE
 * Built-in sample responses that follow the API contract in SPEC.md exactly.
 * Used when the URL has ?mock=1 or when the backend is unreachable.
 * The facts are illustrative demo data, written to look like real pipeline output.
 */
(function () {
  "use strict";

  var DISCLAIMER =
    "TaxSaathi gives general information from official sources. It is not professional tax advice. Check with a Chartered Accountant before you file.";
  var LLM = "qwen2.5:3b";

  /* ------------------------------------------------------------------ */
  /* Knowledge-base passages (subset of chunks.jsonl)                     */
  /* ------------------------------------------------------------------ */
  var CHUNKS = {
    "IT-NEW-STDDED-TY2627": {
      title: "Standard deduction for salaried individuals: new tax regime (Tax Year 2026-27)",
      section: "202",
      law: "new_act",
      source_title: "Income-tax Act, 2025, Section 202 (new tax regime) as amended by Finance Act, 2026",
      source_url: "https://incometaxindia.gov.in/Pages/acts/income-tax-act-2025.aspx",
      effective_from: "2026-04-01",
      effective_to: null,
      text:
        "For Tax Year 2026-27, an individual taxed under the new tax regime in section 202 of the Income-tax Act, 2025 may deduct a flat standard deduction of ₹75,000 from income under the head 'Salaries'. A family pensioner may deduct ₹25,000 or one-third of the family pension, whichever is lower. The deduction is automatic and does not depend on any investment or proof of expenditure. The ₹75,000 limit continues the amount first allowed for FY 2024-25 by the Finance (No. 2) Act, 2024.",
    },
    "IT-NEW-SLABS-TY2627": {
      title: "New tax regime slab rates (Tax Year 2026-27)",
      section: "202",
      law: "new_act",
      source_title: "Income-tax Act, 2025, Section 202 (new tax regime) as amended by Finance Act, 2026",
      source_url: "https://incometaxindia.gov.in/Pages/acts/income-tax-act-2025.aspx",
      effective_from: "2026-04-01",
      effective_to: null,
      text:
        "Under section 202, the tax on total income for Tax Year 2026-27 is: up to ₹4,00,000 nil; ₹4,00,001–₹8,00,000 at 5%; ₹8,00,001–₹12,00,000 at 10%; ₹12,00,001–₹16,00,000 at 15%; ₹16,00,001–₹20,00,000 at 20%; ₹20,00,001–₹24,00,000 at 25%; above ₹24,00,000 at 30%. The new regime is the default; an individual without business income may opt out every year when filing the return. Health and education cess of 4% applies on top of the tax.",
    },
    "IT-NEW-87A-TY2627": {
      title: "Rebate for resident individuals: new regime (Tax Year 2026-27)",
      section: "156",
      law: "new_act",
      source_title: "Income-tax Act, 2025, Section 156 (rebate) read with Section 202",
      source_url: "https://incometaxindia.gov.in/Pages/acts/income-tax-act-2025.aspx",
      effective_from: "2026-04-01",
      effective_to: null,
      text:
        "A resident individual under the new tax regime whose total income does not exceed ₹12,00,000 gets a rebate equal to the tax payable, up to ₹60,000, so the tax payable is nil. If the income is slightly above ₹12,00,000, marginal relief caps the tax at the amount by which income exceeds ₹12,00,000. The rebate does not apply to tax on special-rate income such as capital gains under section 112A. This corresponds to section 87A of the Income-tax Act, 1961.",
    },
    "IT-OLD-STDDED-TY2627": {
      title: "Standard deduction: old (opt-out) regime (Tax Year 2026-27)",
      section: "19",
      law: "new_act",
      source_title: "Income-tax Act, 2025, Section 19 (deductions from salaries)",
      source_url: "https://incometaxindia.gov.in/Pages/acts/income-tax-act-2025.aspx",
      effective_from: "2026-04-01",
      effective_to: null,
      text:
        "An employee who opts out of the new tax regime may claim a standard deduction of ₹50,000 or the amount of salary, whichever is lower, from income under the head 'Salaries' for Tax Year 2026-27. Entertainment allowance and professional tax remain separately deductible under the old regime.",
    },
    "IT-OLD-SLABS-TY2627": {
      title: "Old regime slab rates for individuals below 60 (Tax Year 2026-27)",
      section: "First Schedule",
      law: "new_act",
      source_title: "Income-tax Act, 2025, rates for individuals not opting for section 202",
      source_url: "https://incometaxindia.gov.in/Pages/acts/income-tax-act-2025.aspx",
      effective_from: "2026-04-01",
      effective_to: null,
      text:
        "For an individual below 60 who opts out of the new regime, tax for Tax Year 2026-27 is: up to ₹2,50,000 nil; ₹2,50,001–₹5,00,000 at 5%; ₹5,00,001–₹10,00,000 at 20%; above ₹10,00,000 at 30%. The basic exemption is ₹3,00,000 for senior citizens (60–80) and ₹5,00,000 for super senior citizens (80+). A rebate of up to ₹12,500 applies if total income does not exceed ₹5,00,000.",
    },
    "IT61-115BAC-STDDED-FY2324": {
      title: "Standard deduction under section 115BAC (FY 2023-24)",
      section: "16(ia)",
      law: "old_act",
      source_title: "Income-tax Act, 1961, Section 16(ia) read with 115BAC (Finance Act, 2023)",
      source_url: "https://incometaxindia.gov.in/Pages/acts/income-tax-act.aspx",
      effective_from: "2023-04-01",
      effective_to: "2024-03-31",
      text:
        "For FY 2023-24, the Finance Act, 2023 extended the standard deduction of ₹50,000 to salaried taxpayers under the new tax regime of section 115BAC.",
    },
    "IT61-87A-FY2425": {
      title: "Section 87A rebate: new regime (FY 2024-25)",
      section: "87A",
      law: "old_act",
      source_title: "Income-tax Act, 1961, Section 87A",
      source_url: "https://incometaxindia.gov.in/Pages/acts/income-tax-act.aspx",
      effective_from: "2024-04-01",
      effective_to: "2025-03-31",
      text: "For FY 2024-25, a resident individual under section 115BAC with total income up to ₹7,00,000 gets a rebate of up to ₹25,000.",
    },
    "GST-RATE-AC-PRE20": {
      title: "Air-conditioning machines (HSN 8415): 28% GST before GST 2.0",
      section: "Sch. IV, S.No. 119",
      law: "gst",
      source_title: "Notification No. 1/2017-Central Tax (Rate), Schedule IV (28%)",
      source_url: "https://cbic-gst.gov.in/gst-goods-services-rates.html",
      effective_from: "2017-07-01",
      effective_to: "2025-09-21",
      text:
        "From 1 July 2017 until 21 September 2025, air-conditioning machines with a motor-driven fan and elements for changing temperature and humidity (HSN 8415) were in Schedule IV of Notification 1/2017-Central Tax (Rate), attracting 28% GST (14% CGST + 14% SGST). This was the highest GST slab, used for consumer durables and luxury goods.",
    },
    "GST-RATE-AC-GST20": {
      title: "Air-conditioners moved to 18% under GST 2.0",
      section: "Sch. II",
      law: "gst",
      source_title: "Notification No. 9/2025-Central Tax (Rate), GST 2.0 rate rationalisation",
      source_url: "https://cbic-gst.gov.in/gst-goods-services-rates.html",
      effective_from: "2025-09-22",
      effective_to: null,
      text:
        "With effect from 22 September 2025 (GST 2.0), air-conditioning machines of HSN 8415 moved from 28% to 18% GST (9% CGST + 9% SGST), following the recommendations of the 56th GST Council meeting. The same notification moved dishwashers and televisions above 32 inches to 18%.",
    },
    "GST-COUNCIL-56-RATES": {
      title: "56th GST Council: two-slab structure (5% and 18%) from 22 Sep 2025",
      section: "Press release",
      law: "gst",
      source_title: "PIB press release: Recommendations of the 56th GST Council meeting",
      source_url: "https://pib.gov.in/",
      effective_from: "2025-09-22",
      effective_to: null,
      text:
        "The 56th GST Council approved a simpler two-rate structure, a merit rate of 5% and a standard rate of 18%, with a special 40% rate for a small set of sin and luxury goods. The 12% and 28% slabs were largely removed, and most consumer durables, including air-conditioners, moved to 18%. The new rates apply from 22 September 2025.",
    },
    "GST-TRANSITION-INVOICE": {
      title: "Change in rate: which rate applies (time of supply)",
      section: "CGST s.14",
      law: "gst",
      source_title: "CGST Act, 2017, Section 14 (change in rate of tax)",
      source_url: "https://cbic-gst.gov.in/",
      effective_from: "2017-07-01",
      effective_to: null,
      text:
        "When the GST rate changes, section 14 of the CGST Act decides the rate. If goods were supplied, invoiced and paid for before the change, the old rate applies. If two of the three events happen after the change, the new rate applies. A purchase completed in August 2025 therefore carries the rate in force in August 2025.",
    },
    "MAP-80C-S123": {
      title: "Section 80C (1961 Act) maps to Section 123 (2025 Act)",
      section: "80C → 123",
      law: "mapping",
      source_title: "CBDT mapping table: Income-tax Act, 1961 to Income-tax Act, 2025",
      source_url: "https://incometaxindia.gov.in/",
      effective_from: "2026-04-01",
      effective_to: null,
      text:
        "The Income-tax Act, 2025 renumbers the deductions of Chapter VI-A. The deduction for life insurance premium, provident fund, PPF, ELSS, tuition fees and principal repayment of a housing loan, formerly section 80C of the Income-tax Act, 1961, is section 123 of the Income-tax Act, 2025 from Tax Year 2026-27. The conditions and the ₹1,50,000 aggregate limit are unchanged.",
    },
    "IT-NEW-S123-LIMIT": {
      title: "Section 123: deduction for LIC, PF, PPF, ELSS etc. (limit ₹1,50,000)",
      section: "123",
      law: "new_act",
      source_title: "Income-tax Act, 2025, Section 123",
      source_url: "https://incometaxindia.gov.in/Pages/acts/income-tax-act-2025.aspx",
      effective_from: "2026-04-01",
      effective_to: null,
      text:
        "Section 123 allows an individual or HUF a deduction for sums paid as life insurance premium, contribution to provident fund or PPF, subscription to ELSS, children's tuition fees and repayment of housing-loan principal. The aggregate deduction (with sections 124 and 125) may not exceed ₹1,50,000 in a tax year.",
    },
    "IT-NEW-202-NODED": {
      title: "Section 202: deductions not allowed in the new regime",
      section: "202(2)",
      law: "new_act",
      source_title: "Income-tax Act, 2025, Section 202",
      source_url: "https://incometaxindia.gov.in/Pages/acts/income-tax-act-2025.aspx",
      effective_from: "2026-04-01",
      effective_to: null,
      text:
        "A person whose income is taxed under section 202 cannot claim the deductions of Chapter VIII, including section 123 (formerly 80C) and the health-insurance deduction (formerly 80D), house-rent allowance exemption, or interest on a self-occupied house. The standard deduction and the employer's contribution to NPS remain available.",
    },
    "IT61-80C-FY2526": {
      title: "Section 80C deduction (FY 2025-26)",
      section: "80C",
      law: "old_act",
      source_title: "Income-tax Act, 1961, Section 80C",
      source_url: "https://incometaxindia.gov.in/Pages/acts/income-tax-act.aspx",
      effective_from: "2025-04-01",
      effective_to: "2026-03-31",
      text: "Section 80C allows a deduction of up to ₹1,50,000 for specified investments, available only under the old regime for FY 2025-26.",
    },
    "IT-NEW-VDA-30PCT": {
      title: "Income from virtual digital assets taxed at 30%",
      section: "194",
      law: "new_act",
      source_title: "Income-tax Act, 2025, Section 194 (VDA)",
      source_url: "https://incometaxindia.gov.in/",
      effective_from: "2026-04-01",
      effective_to: null,
      text: "Income from transferring a virtual digital asset is taxed at a flat 30%, with no deduction other than cost of acquisition, and losses cannot be set off.",
    },
  };

  // Titles for passages that show up in retrieval lists but are not cited
  var TITLES = {
    "IT-NEW-FAMPEN-TY2627": "Family pension deduction (Tax Year 2026-27)",
    "IT61-115BAC-SLABS-FY2425": "Section 115BAC slab rates (FY 2024-25)",
    "IT61-115BAC-SLABS-FY2526": "Section 115BAC slab rates (FY 2025-26)",
    "IT61-16IA-STDDED-FY2425": "Standard deduction raised to ₹75,000 (FY 2024-25)",
    "IT61-87A-FY2526": "Section 87A rebate up to ₹60,000 (FY 2025-26)",
    "IT-NEW-SALARY-PERQ": "Perquisites taxable as salary",
    "IT-NEW-HRA-OLDREG": "House rent allowance: old regime only",
    "IT-NEW-OPTOUT-202": "Opting out of the new regime every year",
    "IT-NEW-CESS-4PCT": "Health and education cess at 4%",
    "IT-NEW-SURCHARGE-202": "Surcharge rates: new regime (cap 25%)",
    "GST-RATE-TV-GST20": "Televisions above 32 inches: 18% from 22 Sep 2025",
    "GST-RATE-FRIDGE-PRE20": "Refrigerators (HSN 8418): 18% GST",
    "GST-HSN-8415-DESC": "HSN 8415: description of air-conditioning machines",
    "GST-COMP-CESS-END": "Compensation cess ends for most goods",
    "GST-RATE-SCHED-II-2025": "Schedule II (18%) goods list from 22 Sep 2025",
    "GST-TRANSITION-INVOICE": "Which rate applies: invoice date vs supply date",
    "MAP-80D-S126": "Section 80D (1961) maps to section 126 (2025)",
    "MAP-OVERVIEW-2025": "Overview: how sections are renumbered in the 2025 Act",
    "IT61-80CCD1B-FY2526": "Section 80CCD(1B): extra ₹50,000 for NPS",
    "IT-NEW-S124-NPS": "Section 124: NPS contributions",
    "IT-NEW-FOREIGN-FA": "Schedule FA: reporting foreign assets",
    "IT-NEW-DTAA-90": "Relief under tax treaties (DTAA)",
    "IT-NEW-VDA-TDS-1PCT": "1% TDS on transfer of crypto (VDA)",
    "IT-NEW-BLACKMONEY": "Undisclosed foreign income: penalty provisions",
    "GEN-FILING-DUE-DATES": "Return filing due dates",
    "GEN-ITR-FORMS": "Which ITR form to use",
    "IT-NEW-RESIDENCE-6": "Residential status: who is resident",
  };

  function titleOf(id) {
    return (CHUNKS[id] && CHUNKS[id].title) || TITLES[id] || id;
  }

  function citation(id) {
    var c = CHUNKS[id] || { title: titleOf(id), section: "", law: "general", source_title: "", source_url: "", effective_from: null, effective_to: null, text: "" };
    return {
      id: id,
      title: c.title,
      section: c.section,
      law: c.law,
      source_title: c.source_title,
      source_url: c.source_url,
      effective_from: c.effective_from,
      effective_to: c.effective_to,
      text: c.text,
    };
  }

  /* ------------------------------------------------------------------ */
  /* Deterministic tax calculator (mirrors src/calculator/tax.py rules)   */
  /* ------------------------------------------------------------------ */
  var INF = Infinity;
  function newSlabs(year) {
    if (year === "2024-25")
      return [[0, 300000, 0], [300000, 700000, 5], [700000, 1000000, 10], [1000000, 1200000, 15], [1200000, 1500000, 20], [1500000, INF, 30]];
    return [[0, 400000, 0], [400000, 800000, 5], [800000, 1200000, 10], [1200000, 1600000, 15], [1600000, 2000000, 20], [2000000, 2400000, 25], [2400000, INF, 30]];
  }
  function oldSlabs(age) {
    var start = age === "above80" ? 500000 : age === "60to80" ? 300000 : 250000;
    var s = [[0, start, 0]];
    if (start < 500000) s.push([start, 500000, 5]);
    s.push([500000, 1000000, 20]);
    s.push([1000000, INF, 30]);
    return s;
  }
  function n(v) {
    v = Number(v);
    return isFinite(v) && v > 0 ? Math.round(v) : 0;
  }
  function regime(inp, which) {
    var gross = n(inp.gross_salary);
    var salaried = inp.salaried !== false;
    var year = inp.tax_year || "2026-27";
    var std, ded = 0, notes = [];
    if (which === "old") {
      std = salaried ? Math.min(50000, gross) : 0;
      var c80 = Math.min(n(inp.deductions_80c), 150000);
      var d80 = Math.min(n(inp.deductions_80d), inp.age === "below60" ? 75000 : 100000);
      var hl = Math.min(n(inp.home_loan_interest), 200000);
      var nps = Math.min(n(inp.nps_80ccd1b), 50000);
      var emp = Math.min(n(inp.employer_nps), Math.round(gross * 0.1));
      ded = c80 + d80 + n(inp.hra_exemption) + hl + nps + emp + n(inp.other_deductions);
    } else {
      std = salaried ? Math.min(year === "2024-25" ? 75000 : 75000, gross) : 0;
      ded = Math.min(n(inp.employer_nps), Math.round(gross * 0.14));
    }
    var taxable = Math.max(0, gross - std - ded);
    var slabsDef = which === "old" ? oldSlabs(inp.age) : newSlabs(year);
    var slabs = [], slabTax = 0;
    slabsDef.forEach(function (s) {
      var portion = Math.max(0, Math.min(taxable, s[1]) - s[0]);
      var t = Math.round((portion * s[2]) / 100);
      slabTax += t;
      slabs.push({ from: s[0], to: s[1] === INF ? null : s[1], rate: s[2], tax: t });
    });
    var rebate = 0;
    if (which === "old") {
      if (taxable <= 500000) rebate = Math.min(slabTax, 12500);
    } else {
      var lim = year === "2024-25" ? 700000 : 1200000;
      var cap = year === "2024-25" ? 25000 : 60000;
      if (taxable <= lim) rebate = Math.min(slabTax, cap);
      else if (slabTax > taxable - lim) rebate = slabTax - (taxable - lim); // marginal relief
    }
    var afterRebate = slabTax - rebate;
    var sr = 0;
    if (taxable > 50000000) sr = which === "old" ? 37 : 25;
    else if (taxable > 20000000) sr = 25;
    else if (taxable > 10000000) sr = 15;
    else if (taxable > 5000000) sr = 10;
    var surcharge = Math.round((afterRebate * sr) / 100);
    var cess = Math.round(((afterRebate + surcharge) * 4) / 100);
    var total = Math.round((afterRebate + surcharge + cess) / 10) * 10;
    return {
      gross: gross, std_deduction: std, deductions: ded, taxable: taxable, slab_tax: slabTax,
      rebate: rebate, surcharge: surcharge, cess: cess, total: total, slabs: slabs,
    };
  }
  function fmt(v) {
    return "₹" + Math.round(v).toString().replace(/(\d)(?=(\d\d)+\d$)/g, "$1,");
  }
  function calculate(inp) {
    inp = inp || {};
    var year = inp.tax_year || "2026-27";
    var o = regime(inp, "old"), w = regime(inp, "new");
    var better = o.total < w.total ? "old" : w.total < o.total ? "new" : "same";
    var law =
      year === "2026-27"
        ? "Income-tax Act, 2025: s.202 (new regime) / opt-out rates (old regime)"
        : year === "2025-26"
        ? "Income-tax Act, 1961: s.115BAC as amended by Finance Act, 2025"
        : "Income-tax Act, 1961: s.115BAC as amended by Finance (No. 2) Act, 2024";
    var notes = [];
    notes.push("Standard deduction: " + fmt(w.std_deduction) + " in the new regime vs " + fmt(o.std_deduction) + " in the old regime.");
    if (w.rebate > 0)
      notes.push("The new-regime rebate (" + (year === "2026-27" ? "s.156, formerly 87A" : "s.87A") + ") removed " + fmt(w.rebate) + " of tax.");
    if (o.rebate > 0) notes.push("Old-regime rebate of " + fmt(o.rebate) + " applied (income up to ₹5,00,000).");
    if (n(inp.deductions_80c) > 150000) notes.push("80C/section 123 claims are capped at ₹1,50,000. The extra amount was ignored.");
    if (n(inp.home_loan_interest) > 200000) notes.push("Self-occupied home-loan interest is capped at ₹2,00,000 (old regime only).");
    if (o.deductions > 0) notes.push("Deductions of " + fmt(o.deductions) + " count only in the old regime. The new regime allows employer NPS only.");
    notes.push("Computed by a deterministic calculator. The LLM never does the arithmetic.");
    return {
      old: o, "new": w, better: better, saving: Math.abs(o.total - w.total), law: law, notes: notes,
      inputs: inp, tax_year: year,
    };
  }

  /* ------------------------------------------------------------------ */
  /* Question → scenario                                                  */
  /* ------------------------------------------------------------------ */
  var CURRENT = { start: "2026-04-01", end: "2027-03-31", reason: "No date in the question, so the current law applies (Tax Year 2026-27)", assumed_current: true };

  var HINGLISH_DICT = {
    naye: "new", naya: "new", nayi: "new", mein: "in", me: "in", kitna: "how much", kitni: "how much", hai: "is", hain: "are",
    kya: "what", kaise: "how", kab: "when", tha: "was", thi: "was", mera: "my", meri: "my", mujhe: "I", chahiye: "should",
    kaunsa: "which", konsa: "which", accha: "better", acha: "better", behtar: "better", purane: "old", purana: "old",
    lagta: "applies", lagega: "will apply", par: "on", pe: "on", ka: "of", ki: "of", ke: "of", aur: "and", ya: "or",
    "batao": "tell", bataiye: "tell", milta: "available", milega: "available", sakta: "can", saal: "year", wala: "",
    tax: "tax", salary: "salary", lakh: "lakh",
  };
  var HINGLISH_MARKERS = /\b(naye|naya|nayi|mein|kitna|kitni|hai|kya|kaise|tha|mera|meri|mujhe|kaunsa|konsa|accha|behtar|purane|lagega|batao|milta|chahiye)\b/i;

  function hinglishStep(q) {
    var isHi = HINGLISH_MARKERS.test(q);
    if (!isHi) return { original: q, normalised: q, language: "en", replaced: [] };
    var replaced = [];
    var words = q.split(/(\s+|[?,.!])/);
    var out = words.map(function (w) {
      var k = w.toLowerCase();
      if (HINGLISH_DICT.hasOwnProperty(k) && HINGLISH_DICT[k] !== k) {
        replaced.push([w, HINGLISH_DICT[k] || "∅"]);
        return HINGLISH_DICT[k];
      }
      return w;
    });
    var normalised = out.join("").replace(/\s+/g, " ").trim();
    if (/standard deduction/i.test(q)) normalised = "How much is the standard deduction in the new regime?";
    return { original: q, normalised: normalised, language: "hinglish", replaced: replaced };
  }

  function parseAmount(numStr, unit) {
    var v = parseFloat(numStr.replace(/,/g, ""));
    if (!isFinite(v)) return 0;
    unit = (unit || "").toLowerCase();
    if (/^(lakh|lakhs|lac|lacs|l|lpa)$/.test(unit)) v *= 100000;
    else if (/^(crore|crores|cr)$/.test(unit)) v *= 10000000;
    else if (/^(k|thousand)$/.test(unit)) v *= 1000;
    return Math.round(v);
  }

  function parseCalc(q) {
    var inp = { gross_salary: 0, deductions_80c: 0, deductions_80d: 0, hra_exemption: 0, home_loan_interest: 0, nps_80ccd1b: 0, other_deductions: 0, employer_nps: 0, age: "below60", tax_year: "2026-27", salaried: true };
    var amounts = [];
    var clauses = q.split(/,|;|\band\b|\baur\b/i);
    clauses.forEach(function (cl) {
      var clean = cl.replace(/\b80\s*[a-z]{1,4}(\(\w+\))*/gi, " ").replace(/\b(87a|115bac|section \d+)\b/gi, " ");
      var m = clean.match(/(\d[\d,]*(?:\.\d+)?)\s*(lakhs?|lacs?|lpa|l\b|crores?|cr\b|k\b|thousand)?/i);
      if (!m) return;
      var v = parseAmount(m[1], m[2]);
      if (v < 1000 && !m[2]) return; // "80C" etc
      var c = cl.toLowerCase();
      var key = "gross_salary";
      if (/80\s*d\b|health insurance|mediclaim/.test(c)) key = "deductions_80d";
      else if (/80\s*ccd|nps/.test(c)) key = /employer/.test(c) ? "employer_nps" : "nps_80ccd1b";
      else if (/80\s*c\b|ppf|elss|lic|section 123/.test(c)) key = "deductions_80c";
      else if (/hra|rent/.test(c)) key = "hra_exemption";
      else if (/home loan|housing loan|interest/.test(c)) key = "home_loan_interest";
      else if (/salary|ctc|income|earn|package|kamata|kamati/.test(c) || !inp.gross_salary) key = "gross_salary";
      else key = "other_deductions";
      // a clause like "1.5 lakh 80C" mentions 80C after the number
      inp[key] = v;
      amounts.push(v);
    });
    if (/2024-25|fy ?24/i.test(q)) inp.tax_year = "2024-25";
    else if (/2025-26|fy ?25/i.test(q)) inp.tax_year = "2025-26";
    if (/senior|60\+|above 60/i.test(q)) inp.age = "60to80";
    return { inputs: inp, amounts: amounts };
  }

  function pickScenario(q) {
    var s = q.toLowerCase();
    if (/crypto|bitcoin|avoid tax|evade|evasion|hide|black money|launder/.test(s)) return "oos";
    if (/(\bac\b|air[- ]?condition)/.test(s) && /(aug|august|jul|july|before gst 2|2024|sep(tember)? 2[01])/.test(s)) return "ac_past";
    if (/(\bac\b|air[- ]?condition)/.test(s)) return "ac_today";
    var hasAmount = /\d+(\.\d+)?\s*(lakh|lakhs|lac|lpa|l\b|crore|cr\b|k\b|,\d{3})|\d{5,}/i.test(s);
    if (hasAmount && /(salary|regime|tax|ctc|income|package|kamata)/.test(s)) return "calc";
    if (/(which|kaunsa|konsa).*(regime)|regime.*(better|behtar|accha|choose)/.test(s)) return "follow";
    if (/\b80 ?c\b|section 123/.test(s)) return "s80c";
    if (/87a|rebate|zero tax|tax[- ]free (income|limit)|12 lakh/.test(s)) return "rebate";
    if (/standard deduction|std deduction/.test(s)) return HINGLISH_MARKERS.test(q) ? "std_hi" : "std_en";
    if (/slab/.test(s)) return "slabs";
    return "fallback";
  }

  var S = {
    std_en: {
      intent: { question: 0.94, calculation: 0.04, out_of_scope: 0.02 },
      period: CURRENT,
      entities: { sections: [], amounts: [], regime: "new" },
      bm25: ["IT-NEW-STDDED-TY2627", "IT61-115BAC-STDDED-FY2324", "IT-OLD-STDDED-TY2627", "IT61-16IA-STDDED-FY2425", "IT-NEW-FAMPEN-TY2627", "IT-NEW-SLABS-TY2627", "IT-NEW-SALARY-PERQ", "IT-NEW-OPTOUT-202"],
      dense: ["IT-NEW-STDDED-TY2627", "IT61-16IA-STDDED-FY2425", "IT-NEW-SLABS-TY2627", "IT61-115BAC-STDDED-FY2324", "IT-OLD-STDDED-TY2627", "IT-NEW-OPTOUT-202", "IT61-115BAC-SLABS-FY2526", "IT-NEW-FAMPEN-TY2627"],
      removed: ["IT61-115BAC-STDDED-FY2324", "IT61-16IA-STDDED-FY2425", "IT61-115BAC-SLABS-FY2526", "IT61-115BAC-SLABS-FY2425", "IT61-87A-FY2526", "IT61-80CCD1B-FY2526"],
      rerank: [["IT-NEW-STDDED-TY2627", 7.42], ["IT-NEW-SLABS-TY2627", 3.18], ["IT-OLD-STDDED-TY2627", 2.65], ["IT-NEW-FAMPEN-TY2627", 1.12], ["IT-NEW-OPTOUT-202", -0.84]],
      answer:
        "Under the new tax regime, a salaried person gets a flat **standard deduction of ₹75,000** from salary income for Tax Year 2026-27 [IT-NEW-STDDED-TY2627]. It is automatic, so you don't need to invest anything or show proof [IT-NEW-STDDED-TY2627].\n\nThe new regime is the default, and its slab rates are applied after this deduction [IT-NEW-SLABS-TY2627]. If you opt out to the old regime, the standard deduction is lower at ₹50,000 [IT-OLD-STDDED-TY2627].",
      cites: ["IT-NEW-STDDED-TY2627", "IT-NEW-SLABS-TY2627", "IT-OLD-STDDED-TY2627"],
      invalid: ["IT-NEW-STDDED-2024"],
      tokens: [1312, 118],
      plain:
        "In the new tax regime, the standard deduction for salaried employees is ₹50,000. It was introduced in Budget 2023 to make the new regime more attractive, and it is deducted directly from your gross salary.",
    },
    ac_past: {
      intent: { question: 0.91, calculation: 0.05, out_of_scope: 0.04 },
      period: { start: "2025-08-01", end: "2025-08-31", reason: "Month and year found: 'August 2025'", assumed_current: false },
      entities: { sections: [], amounts: [], hsn: ["8415"], goods: ["air-conditioner"] },
      bm25: ["GST-RATE-AC-GST20", "GST-RATE-AC-PRE20", "GST-HSN-8415-DESC", "GST-COUNCIL-56-RATES", "GST-RATE-SCHED-II-2025", "GST-RATE-FRIDGE-PRE20", "GST-TRANSITION-INVOICE", "GST-RATE-TV-GST20"],
      dense: ["GST-RATE-AC-PRE20", "GST-RATE-AC-GST20", "GST-COUNCIL-56-RATES", "GST-TRANSITION-INVOICE", "GST-RATE-TV-GST20", "GST-HSN-8415-DESC", "GST-RATE-FRIDGE-PRE20", "GST-COMP-CESS-END"],
      removed: ["GST-RATE-AC-GST20", "GST-COUNCIL-56-RATES", "GST-RATE-SCHED-II-2025", "GST-RATE-TV-GST20", "GST-COMP-CESS-END"],
      rerank: [["GST-RATE-AC-PRE20", 6.91], ["GST-HSN-8415-DESC", 2.47], ["GST-TRANSITION-INVOICE", 1.36], ["GST-RATE-FRIDGE-PRE20", -0.42], ["IT-NEW-SALARY-PERQ", -6.1]],
      answer:
        "In **August 2025**, air-conditioners (HSN 8415) attracted **28% GST**, split as 14% CGST + 14% SGST [GST-RATE-AC-PRE20]. That was before GST 2.0, which only came into force on 22 September 2025 [GST-RATE-AC-PRE20].\n\nFor a purchase in August 2025, the rate on the invoice date applies, so 28% is correct even if you file the return later [GST-TRANSITION-INVOICE].",
      cites: ["GST-RATE-AC-PRE20", "GST-TRANSITION-INVOICE"],
      invalid: [],
      tokens: [1188, 97],
      // configs without the date filter (B1–C3) fall into the time trap:
      noFilter: {
        rerank: [["GST-RATE-AC-GST20", 6.12], ["GST-RATE-AC-PRE20", 5.87], ["GST-COUNCIL-56-RATES", 3.05], ["GST-HSN-8415-DESC", 2.2], ["GST-RATE-SCHED-II-2025", 0.9]],
        answer:
          "GST on air-conditioners is **18%** (9% CGST + 9% SGST) [GST-RATE-AC-GST20]. Air-conditioners were moved from the 28% slab to 18% after the 56th GST Council meeting [GST-COUNCIL-56-RATES].",
        cites: ["GST-RATE-AC-GST20", "GST-COUNCIL-56-RATES"],
      },
      plain:
        "Air conditioners are taxed at 28% GST in India because they fall under the luxury goods category, the highest GST slab. Some energy-efficient models may also attract compensation cess.",
    },
    ac_today: {
      intent: { question: 0.93, calculation: 0.04, out_of_scope: 0.03 },
      period: { start: "2026-10-29", end: "2026-10-29", reason: "No date in the question, so today's rates apply (29 Oct 2026)", assumed_current: true },
      entities: { sections: [], amounts: [], hsn: ["8415"], goods: ["air-conditioner"] },
      bm25: ["GST-RATE-AC-PRE20", "GST-RATE-AC-GST20", "GST-HSN-8415-DESC", "GST-COUNCIL-56-RATES", "GST-RATE-FRIDGE-PRE20", "GST-RATE-SCHED-II-2025", "GST-TRANSITION-INVOICE", "GST-RATE-TV-GST20"],
      dense: ["GST-RATE-AC-GST20", "GST-RATE-AC-PRE20", "GST-COUNCIL-56-RATES", "GST-RATE-TV-GST20", "GST-HSN-8415-DESC", "GST-RATE-SCHED-II-2025", "GST-TRANSITION-INVOICE", "GST-COMP-CESS-END"],
      removed: ["GST-RATE-AC-PRE20", "GST-RATE-FRIDGE-PRE20"],
      rerank: [["GST-RATE-AC-GST20", 7.08], ["GST-COUNCIL-56-RATES", 3.94], ["GST-HSN-8415-DESC", 2.31], ["GST-RATE-SCHED-II-2025", 1.77], ["GST-RATE-TV-GST20", -0.65]],
      answer:
        "Today, air-conditioners (HSN 8415) attract **18% GST**, split as 9% CGST + 9% SGST [GST-RATE-AC-GST20]. The rate was cut from 28% when GST 2.0 took effect on **22 September 2025** [GST-RATE-AC-GST20], as part of the 56th GST Council's move to a two-slab 5% / 18% structure [GST-COUNCIL-56-RATES].",
      cites: ["GST-RATE-AC-GST20", "GST-COUNCIL-56-RATES"],
      invalid: [],
      tokens: [1204, 92],
      plain:
        "Air conditioners attract 28% GST in India, which is the highest GST slab. This is because ACs are considered luxury items. The 28% is split into 14% CGST and 14% SGST.",
    },
    s80c: {
      intent: { question: 0.89, calculation: 0.08, out_of_scope: 0.03 },
      period: CURRENT,
      entities: { sections: ["80C"], amounts: [], mapping: { "80C": "123" }, boost: "MAP-80C-S123" },
      bm25: ["IT61-80C-FY2526", "MAP-80C-S123", "IT-NEW-S123-LIMIT", "MAP-OVERVIEW-2025", "IT61-80CCD1B-FY2526", "IT-NEW-202-NODED", "MAP-80D-S126", "IT-NEW-S124-NPS"],
      dense: ["MAP-80C-S123", "IT-NEW-202-NODED", "IT-NEW-S123-LIMIT", "IT61-80C-FY2526", "MAP-OVERVIEW-2025", "IT-NEW-OPTOUT-202", "MAP-80D-S126", "IT-NEW-S124-NPS"],
      removed: ["IT61-80C-FY2526", "IT61-80CCD1B-FY2526", "IT61-115BAC-SLABS-FY2526"],
      rerank: [["MAP-80C-S123", 8.03], ["IT-NEW-S123-LIMIT", 5.61], ["IT-NEW-202-NODED", 4.12], ["MAP-OVERVIEW-2025", 1.94], ["IT-NEW-S124-NPS", 0.31]],
      answer:
        "Not under that name. The Income-tax Act, 2025 has no \"section 80C\": the same deduction now sits in **section 123** from Tax Year 2026-27 [MAP-80C-S123]. It still covers LIC, PF/PPF, ELSS, tuition fees and home-loan principal, with the same **₹1,50,000** limit [IT-NEW-S123-LIMIT].\n\nThere is one catch. You can claim it only if you **opt out of the new regime**. The default regime under section 202 does not allow section 123 deductions [IT-NEW-202-NODED].",
      cites: ["MAP-80C-S123", "IT-NEW-S123-LIMIT", "IT-NEW-202-NODED"],
      invalid: [],
      tokens: [1420, 131],
      plain:
        "Yes, Section 80C is available and allows you to claim a deduction of up to ₹1.5 lakh for investments such as PPF, ELSS mutual funds, LIC premiums and EPF contributions. You can claim it while filing your ITR.",
    },
    rebate: {
      intent: { question: 0.9, calculation: 0.07, out_of_scope: 0.03 },
      period: CURRENT,
      entities: { sections: ["87A"], amounts: [], mapping: { "87A": "156" } },
      bm25: ["IT61-87A-FY2425", "IT61-87A-FY2526", "IT-NEW-87A-TY2627", "IT-NEW-SLABS-TY2627", "IT61-115BAC-SLABS-FY2425", "IT-NEW-CESS-4PCT", "IT-NEW-OPTOUT-202", "IT-OLD-SLABS-TY2627"],
      dense: ["IT-NEW-87A-TY2627", "IT61-87A-FY2526", "IT-NEW-SLABS-TY2627", "IT61-87A-FY2425", "IT-OLD-SLABS-TY2627", "IT-NEW-OPTOUT-202", "IT-NEW-CESS-4PCT", "IT61-115BAC-SLABS-FY2526"],
      removed: ["IT61-87A-FY2425", "IT61-87A-FY2526", "IT61-115BAC-SLABS-FY2425", "IT61-115BAC-SLABS-FY2526"],
      rerank: [["IT-NEW-87A-TY2627", 7.66], ["IT-NEW-SLABS-TY2627", 3.4], ["IT-OLD-SLABS-TY2627", 1.02], ["IT-NEW-CESS-4PCT", -0.3], ["IT-NEW-OPTOUT-202", -1.7]],
      answer:
        "For Tax Year 2026-27, a resident individual in the new regime pays **no tax if total income is up to ₹12,00,000**, because the rebate covers tax of up to ₹60,000 [IT-NEW-87A-TY2627]. Just above ₹12 lakh, marginal relief caps your tax at the amount by which income exceeds ₹12 lakh [IT-NEW-87A-TY2627].\n\nWith the ₹75,000 standard deduction, this works out to a salary of about ₹12,75,000 with zero tax [IT-NEW-SLABS-TY2627]. In the old regime the rebate is only up to ₹12,500, for income up to ₹5,00,000 [IT-OLD-SLABS-TY2627].",
      cites: ["IT-NEW-87A-TY2627", "IT-NEW-SLABS-TY2627", "IT-OLD-SLABS-TY2627"],
      invalid: [],
      tokens: [1350, 140],
      plain:
        "Under Section 87A, resident individuals with taxable income up to ₹7 lakh get a full tax rebate in the new regime (up to ₹25,000), so they pay zero tax. In the old regime, the limit is ₹5 lakh.",
    },
    slabs: {
      intent: { question: 0.95, calculation: 0.03, out_of_scope: 0.02 },
      period: CURRENT,
      entities: { sections: [], amounts: [] },
      bm25: ["IT-NEW-SLABS-TY2627", "IT61-115BAC-SLABS-FY2526", "IT61-115BAC-SLABS-FY2425", "IT-OLD-SLABS-TY2627", "IT-NEW-CESS-4PCT", "IT-NEW-87A-TY2627", "IT-NEW-SURCHARGE-202", "IT-NEW-OPTOUT-202"],
      dense: ["IT-NEW-SLABS-TY2627", "IT-OLD-SLABS-TY2627", "IT61-115BAC-SLABS-FY2526", "IT-NEW-87A-TY2627", "IT61-115BAC-SLABS-FY2425", "IT-NEW-SURCHARGE-202", "IT-NEW-CESS-4PCT", "IT-NEW-OPTOUT-202"],
      removed: ["IT61-115BAC-SLABS-FY2526", "IT61-115BAC-SLABS-FY2425", "IT61-87A-FY2526"],
      rerank: [["IT-NEW-SLABS-TY2627", 8.2], ["IT-NEW-87A-TY2627", 3.1], ["IT-OLD-SLABS-TY2627", 2.8], ["IT-NEW-SURCHARGE-202", 1.1], ["IT-NEW-CESS-4PCT", 0.6]],
      answer:
        "New-regime slabs for Tax Year 2026-27 [IT-NEW-SLABS-TY2627]:\n- Up to ₹4,00,000: nil\n- ₹4–8 lakh: 5%\n- ₹8–12 lakh: 10%\n- ₹12–16 lakh: 15%\n- ₹16–20 lakh: 20%\n- ₹20–24 lakh: 25%\n- Above ₹24 lakh: 30%\n\nThanks to the rebate, income up to ₹12 lakh is effectively tax-free [IT-NEW-87A-TY2627].",
      cites: ["IT-NEW-SLABS-TY2627", "IT-NEW-87A-TY2627"],
      invalid: [],
      tokens: [1290, 120],
      plain: "New regime slabs: 0–3 lakh nil, 3–7 lakh 5%, 7–10 lakh 10%, 10–12 lakh 15%, 12–15 lakh 20%, above 15 lakh 30%.",
    },
    calc: {
      intent: { question: 0.06, calculation: 0.92, out_of_scope: 0.02 },
      period: CURRENT,
      bm25: ["IT-NEW-SLABS-TY2627", "IT-OLD-SLABS-TY2627", "IT61-80C-FY2526", "IT-NEW-STDDED-TY2627", "IT-NEW-87A-TY2627", "IT-NEW-OPTOUT-202", "IT61-115BAC-SLABS-FY2526", "IT-NEW-S123-LIMIT"],
      dense: ["IT-NEW-OPTOUT-202", "IT-NEW-SLABS-TY2627", "IT-NEW-87A-TY2627", "IT-OLD-SLABS-TY2627", "IT-NEW-STDDED-TY2627", "IT-NEW-202-NODED", "IT61-80C-FY2526", "IT61-115BAC-SLABS-FY2526"],
      removed: ["IT61-80C-FY2526", "IT61-115BAC-SLABS-FY2526", "IT61-87A-FY2526", "IT61-16IA-STDDED-FY2425"],
      rerank: [["IT-NEW-87A-TY2627", 5.88], ["IT-NEW-SLABS-TY2627", 5.12], ["IT-OLD-SLABS-TY2627", 4.4], ["IT-NEW-STDDED-TY2627", 3.97], ["IT-NEW-202-NODED", 2.05]],
      cites: ["IT-NEW-STDDED-TY2627", "IT-NEW-87A-TY2627", "IT-OLD-SLABS-TY2627", "IT-NEW-202-NODED"],
      invalid: ["IT-CALC-RESULT"],
      tokens: [1610, 164],
      plain:
        "With a salary of ₹12 lakh and ₹1.5 lakh invested under 80C, the old regime is usually better because you can claim deductions. Your tax would be about ₹1,00,000 in the old regime and about ₹1,10,000 in the new regime, so choose the old regime.",
    },
    follow: {
      intent: { question: 0.21, calculation: 0.76, out_of_scope: 0.03 },
      period: CURRENT,
      entities: { sections: [], amounts: [] },
      follow_up:
        "Happy to compare both regimes for you. What is your **annual gross salary**? If you have 80C investments, health insurance (80D), HRA or home-loan interest, share those amounts too.",
      plain: "The new regime is generally better for most people because it has lower tax rates, but the old regime may be better if you have many deductions.",
    },
    oos: {
      intent: { question: 0.09, calculation: 0.03, out_of_scope: 0.88 },
      period: CURRENT,
      entities: { sections: [], amounts: [], flags: ["foreign income", "tax avoidance"] },
      bm25: ["IT-NEW-VDA-30PCT", "IT-NEW-VDA-TDS-1PCT", "IT-NEW-FOREIGN-FA", "IT-NEW-BLACKMONEY", "IT-NEW-DTAA-90", "IT-NEW-RESIDENCE-6", "GEN-ITR-FORMS", "GEN-FILING-DUE-DATES"],
      dense: ["IT-NEW-VDA-30PCT", "IT-NEW-FOREIGN-FA", "IT-NEW-DTAA-90", "IT-NEW-VDA-TDS-1PCT", "IT-NEW-BLACKMONEY", "IT-NEW-RESIDENCE-6", "GEN-ITR-FORMS", "GEN-FILING-DUE-DATES"],
      removed: [],
      rerank: [["IT-NEW-VDA-30PCT", 1.42], ["IT-NEW-FOREIGN-FA", 0.88], ["IT-NEW-DTAA-90", -0.21], ["IT-NEW-BLACKMONEY", -1.9], ["IT-NEW-VDA-TDS-1PCT", -2.4]],
      refused: true,
      gate_reason: "intent = out_of_scope (88%)",
      ungated: {
        answer: "Income from crypto (virtual digital assets) is taxed at a flat 30% with no deductions [IT-NEW-VDA-30PCT]. Foreign assets are reported in Schedule FA, and keeping holdings on a foreign exchange may reduce what shows up in India [IT-NEW-FOREIGN-FA].",
        cites: ["IT-NEW-VDA-30PCT"],
      },
      refusal_reason:
        "This asks how to avoid tax on foreign crypto income. TaxSaathi doesn't give tax-avoidance strategies, and foreign assets (Schedule FA reporting, tax treaties, crypto/VDA rules) need a qualified Chartered Accountant.",
      answer:
        "I can't help with ways to avoid tax. In general, Indian residents are taxed on their worldwide income and must report foreign assets in their return. A Chartered Accountant can help you report foreign crypto income correctly and claim any treaty relief you are entitled to.",
      plain:
        "To reduce tax on foreign crypto income, some people keep their gains on a foreign exchange and don't convert them to INR, since it may not be reported in India. You could also move to a country with no crypto tax, or gift the crypto to family members.",
    },
    fallback: {
      intent: { question: 0.71, calculation: 0.11, out_of_scope: 0.18 },
      period: CURRENT,
      entities: { sections: [], amounts: [] },
      bm25: ["GEN-ITR-FORMS", "GEN-FILING-DUE-DATES", "IT-NEW-RESIDENCE-6", "IT-NEW-SALARY-PERQ", "GST-TRANSITION-INVOICE", "IT-NEW-OPTOUT-202", "MAP-OVERVIEW-2025", "IT-NEW-CESS-4PCT"],
      dense: ["IT-NEW-OPTOUT-202", "GEN-ITR-FORMS", "MAP-OVERVIEW-2025", "GEN-FILING-DUE-DATES", "IT-NEW-SALARY-PERQ", "IT-NEW-RESIDENCE-6", "GST-TRANSITION-INVOICE", "IT-NEW-CESS-4PCT"],
      removed: ["IT61-115BAC-SLABS-FY2425"],
      rerank: [["GEN-ITR-FORMS", -1.84], ["MAP-OVERVIEW-2025", -2.3], ["IT-NEW-OPTOUT-202", -3.05], ["GEN-FILING-DUE-DATES", -3.6], ["IT-NEW-SALARY-PERQ", -4.4]],
      refused: true,
      gate_reason: "top rerank score -1.84 < threshold 0.00",
      ungated: {
        answer: "This generally depends on your situation. The new regime is the default for Tax Year 2026-27 [IT-NEW-SLABS-TY2627], so check the rules that apply to you.",
        cites: ["IT-NEW-SLABS-TY2627"],
      },
      refusal_reason:
        "Low confidence: the best matching passage scored -1.84, below the safety threshold of 0.0. Rather than guess, TaxSaathi hands this to a CA. (Mock mode only has sample answers for the example questions, so try one of the chips.)",
      answer: "",
      plain: "I'm not completely sure, but generally this depends on your specific situation and the latest rules. Please check the income tax website for details.",
    },
  };
  S.std_hi = Object.assign({}, S.std_en, {
    intent: { question: 0.9, calculation: 0.06, out_of_scope: 0.04 },
    answer:
      "Naye (new) regime mein salaried logon ko **₹75,000 ka standard deduction** milta hai, Tax Year 2026-27 ke liye [IT-NEW-STDDED-TY2627]. Yeh automatic hai, iske liye koi investment ya proof nahi chahiye [IT-NEW-STDDED-TY2627].\n\nIs deduction ke baad hi new regime ke slab rates lagte hain [IT-NEW-SLABS-TY2627]. Old regime mein yeh sirf ₹50,000 hai [IT-OLD-STDDED-TY2627].",
  });

  /* ------------------------------------------------------------------ */
  /* Trace builder                                                        */
  /* ------------------------------------------------------------------ */
  var CONFIG_STEPS = {
    B0: [],
    B1: ["bm25"],
    C1: ["dense"],
    C2: ["bm25", "dense", "fusion"],
    C3: ["bm25", "dense", "fusion", "rerank", "gate"],
    C4: ["bm25", "dense", "fusion", "date_filter", "rerank", "gate"],
    C5: ["hinglish", "bm25", "dense", "fusion", "date_filter", "rerank", "gate"],
    C6: ["hinglish", "bm25", "dense", "fusion", "date_filter", "rerank", "gate"],
  };

  function scored(ids, top, base, decay, digits) {
    return ids.slice(0, top).map(function (id, i) {
      var jitter = ((id.length * 7 + i * 13) % 10) / 100;
      return { id: id, title: titleOf(id), score: +(base - i * decay - jitter * decay).toFixed(digits) };
    });
  }

  function rrf(lists, k) {
    var acc = {};
    lists.forEach(function (list) {
      list.forEach(function (id, r) {
        acc[id] = (acc[id] || 0) + 1 / (k + r + 1);
      });
    });
    return Object.keys(acc)
      .sort(function (a, b) { return acc[b] - acc[a]; })
      .map(function (id) { return { id: id, title: titleOf(id), score: +acc[id].toFixed(4) }; });
  }

  function piiStep(q) {
    var found = [];
    var red = q.replace(/\b[A-Z]{5}[0-9]{4}[A-Z]\b/g, function (m) { found.push({ type: "PAN", value: m.slice(0, 3) + "XXXXX" + m.slice(-2) }); return "[PAN]"; })
      .replace(/\b\d{4}\s?\d{4}\s?\d{4}\b/g, function () { found.push({ type: "Aadhaar", value: "XXXX XXXX ····" }); return "[AADHAAR]"; })
      .replace(/(\+91[\s-]?)?\b[6-9]\d{9}\b/g, function () { found.push({ type: "Phone", value: "+91 XXXXX ·····" }); return "[PHONE]"; });
    return { found: found, redacted: red };
  }

  function ask(body) {
    body = body || {};
    var q = String(body.question || "").trim();
    var config = String(body.config || "C6").toUpperCase();
    if (!CONFIG_STEPS[config]) config = "C6";
    var key = pickScenario(q);
    var sc = S[key];
    var use = CONFIG_STEPS[config];
    var trace = [];
    var t = function (step, label, summary, ms, data) { trace.push({ step: step, label: label, summary: summary, ms: ms, data: data }); };

    var pii = piiStep(q);
    t("pii", "PII scrub", pii.found.length ? "Masked " + pii.found.length + " item(s)" : "No personal data found", 1, pii);

    if (config === "B0") {
      var lat0 = 4200 + (q.length * 37) % 2400;
      t("generate", "LLM answer (no retrieval)", "Answered from the model's memory, with no sources", lat0, { model: LLM, prompt_tokens: 96 + q.length, output_tokens: 88, passages: 0, temperature: 0.1 });
      return {
        answer: sc.plain, refused: false, refusal_reason: null, follow_up: null, citations: [], calculation: null,
        disclaimer: DISCLAIMER, latency_ms: lat0 + 12, config: config, trace: trace,
      };
    }

    var hi = hinglishStep(q);
    if (use.indexOf("hinglish") >= 0)
      t("hinglish", "Hinglish normalisation", hi.language === "hinglish" ? "Replaced " + hi.replaced.length + " Hinglish words" : "Already English", 2, hi);

    var intentLabel = Object.keys(sc.intent).sort(function (a, b) { return sc.intent[b] - sc.intent[a]; })[0];
    t("intent", "Intent classification", intentLabel + " (" + Math.round(sc.intent[intentLabel] * 100) + "%)", 3, { label: intentLabel, probs: sc.intent });
    t("period", "Period extraction", sc.period.reason, 1, sc.period);

    var calcRes = null, parsed = null, entities = sc.entities;
    if (key === "calc") {
      parsed = parseCalc(q);
      entities = { sections: /80\s*c/i.test(q) ? ["80C"] : [], amounts: parsed.amounts };
    }
    t("entities", "Entity recognition", (entities.sections || []).length ? "Sections: " + entities.sections.join(", ") : "No section numbers", 1, entities);

    // follow-up: calculation intent without salary
    if (key === "follow") {
      t("calculator", "Tax calculator", "Missing gross salary, so asking a follow-up question", 1, { status: "missing_inputs", missing: ["gross_salary"] });
      return {
        answer: "", refused: false, refusal_reason: null, follow_up: sc.follow_up, citations: [], calculation: null,
        disclaimer: DISCLAIMER, latency_ms: 38, config: config, trace: trace,
      };
    }

    var useFilter = use.indexOf("date_filter") >= 0;
    var variant = !useFilter && sc.noFilter ? sc.noFilter : sc;
    var hasRerank = use.indexOf("rerank") >= 0;

    if (use.indexOf("bm25") >= 0) t("bm25", "BM25 keyword search", "Top " + Math.min(5, sc.bm25.length) + " by keyword overlap", 6, { results: scored(sc.bm25, config === "B1" ? 5 : 8, 14.6, 1.35, 2) });
    if (use.indexOf("dense") >= 0) t("dense", "Dense retrieval (embeddings)", "Top 5 by meaning (multilingual-e5-small)", 46, { results: scored(sc.dense, config === "C1" ? 5 : 8, 0.893, 0.017, 3) });
    var fused = null;
    if (use.indexOf("fusion") >= 0) {
      fused = rrf([sc.bm25, sc.dense], 60);
      t("fusion", "Reciprocal rank fusion", "Merged BM25 + dense rankings (k=60)", 1, { k: 60, results: fused.slice(0, 10) });
    }
    if (useFilter) {
      var removed = sc.removed || [];
      t("date_filter", "Date filter", "Removed " + removed.length + " passages outside " + sc.period.start + " → " + sc.period.end, 1, {
        before: 20, after: 20 - removed.length, removed: removed, period: [sc.period.start, sc.period.end],
      });
    }
    var topScore = null;
    if (hasRerank) {
      var rr = variant.rerank.map(function (p) { return { id: p[0], title: titleOf(p[0]), score: p[1] }; });
      topScore = rr[0].score;
      t("rerank", "Cross-encoder rerank", "Re-read " + (useFilter ? 20 - (sc.removed || []).length : 20) + " passages, kept top 5 (bge-reranker-base)", 840 + (q.length % 7) * 31, {
        model: "BAAI/bge-reranker-base", candidates: useFilter ? 20 - (sc.removed || []).length : 20, results: rr,
      });
    }
    var refused = !!sc.refused;
    if (use.indexOf("gate") >= 0) {
      t("gate", "Guardrail gate", refused ? "Blocked: " + sc.gate_reason : "Passed (top score " + topScore.toFixed(2) + " ≥ 0.00)", 0, {
        passed: !refused, top_score: topScore, threshold: 0.0, reason: refused ? sc.gate_reason : "intent in scope and retrieval confident",
      });
    } else if (sc.refused) {
      // configs without a gate still answer (that's the point of the ablation)
      refused = false;
      variant = sc.ungated;
    }

    if (refused) {
      return {
        answer: sc.answer || "", refused: true, refusal_reason: sc.refusal_reason, follow_up: null, citations: [], calculation: null,
        disclaimer: DISCLAIMER, latency_ms: trace.reduce(function (a, s) { return a + s.ms; }, 0) + 24, config: config, trace: trace,
      };
    }

    var answer = variant.answer, cites = variant.cites || sc.cites;
    if (key === "calc") {
      calcRes = calculate(parsed.inputs);
      var o = calcRes.old, w = calcRes["new"];
      var winner = calcRes.better === "same" ? "Both regimes cost the same" : "The **" + calcRes.better + " regime is better**";
      t("calculator", "Tax calculator", winner.replace(/\*/g, "") + (calcRes.saving ? ", saving " + fmt(calcRes.saving) : ""), 2, {
        inputs: parsed.inputs, old_total: o.total, new_total: w.total, better: calcRes.better, saving: calcRes.saving,
      });
      answer =
        winner + " for a gross salary of " + fmt(o.gross) +
        (parsed.inputs.deductions_80c ? " with " + fmt(Math.min(parsed.inputs.deductions_80c, 150000)) + " in 80C (now section 123)" : "") +
        ": you'd pay **" + fmt(w.total) + "** under the new regime vs **" + fmt(o.total) + "** under the old regime" +
        (calcRes.saving ? ", a saving of " + fmt(calcRes.saving) : "") + ".\n\n" +
        "In the new regime, the ₹75,000 standard deduction brings taxable income to " + fmt(w.taxable) + " [IT-NEW-STDDED-TY2627]" +
        (w.rebate > 0 ? ", and the rebate removes " + fmt(w.rebate) + " of tax for income up to ₹12,00,000 [IT-NEW-87A-TY2627]" : "") +
        ". In the old regime, your deductions reduce taxable income to " + fmt(o.taxable) + ", taxed at 5%/20%/30% slabs [IT-OLD-SLABS-TY2627]. " +
        "Note that 80C counts only if you opt out of the new regime [IT-NEW-202-NODED].";
    }

    var genMs = 5200 + (q.length * 53) % 4200;
    var nCited = cites.length + (sc.invalid || []).length;
    t("generate", "Grounded generation", "Wrote the answer from " + (hasRerank ? 5 : 5) + " passages with [CHUNK-ID] tags", genMs, {
      model: LLM, prompt_tokens: (sc.tokens || [1300])[0], output_tokens: (sc.tokens || [0, 110])[1], passages: 5, temperature: 0.1,
    });
    t("citation_check", "Citation check", cites.length + " citations kept, " + (sc.invalid || []).length + " dropped", 3, {
      kept: cites.length, dropped: (sc.invalid || []).length, invalid_ids: sc.invalid || [], sentences_checked: nCited + 2,
    });

    return {
      answer: answer, refused: false, refusal_reason: null, follow_up: null,
      citations: cites.map(citation), calculation: calcRes,
      disclaimer: DISCLAIMER, latency_ms: trace.reduce(function (a, s) { return a + s.ms; }, 0) + 41, config: config, trace: trace,
    };
  }

  /* ------------------------------------------------------------------ */
  /* Experiments, KB stats, health                                       */
  /* ------------------------------------------------------------------ */
  function m(r5, mrr, ndcg, ref, per, kf, cit, faith, lat) {
    return { recall_at_5: r5, mrr: mrr, ndcg_at_5: ndcg, refusal_accuracy: ref, period_accuracy: per, key_fact_accuracy: kf, citation_validity: cit, faithfulness: faith, latency_p50_ms: lat };
  }
  function cat(it, gst, trap, calc, oos, hi) {
    return {
      income_tax: { key_fact_accuracy: it[0], recall_at_5: it[1] },
      gst: { key_fact_accuracy: gst[0], recall_at_5: gst[1] },
      time_trap: { key_fact_accuracy: trap[0], recall_at_5: trap[1] },
      calculation: { key_fact_accuracy: calc[0], recall_at_5: calc[1] },
      out_of_scope: { key_fact_accuracy: oos[0], recall_at_5: oos[1] },
      hinglish: { key_fact_accuracy: hi[0], recall_at_5: hi[1] },
    };
  }
  var EXPERIMENTS = {
    __sample: true,
    generated_at: "2026-10-27T18:42:00+05:30",
    split: "dev",
    dev_size: 36,
    test_size: 84,
    configs: [
      { name: "B0", description: "LLM alone (qwen2.5:3b), no retrieval", metrics: m(null, null, null, 0.42, 0.28, 0.36, null, 0.31, 5300), per_category: cat([0.43, null], [0.38, null], [0.12, null], [0.25, null], [0.4, null], [0.33, null]) },
      { name: "B1", description: "BM25 top-5 → LLM", metrics: m(0.61, 0.52, 0.55, 0.5, 0.47, 0.57, 0.81, 0.69, 6900), per_category: cat([0.66, 0.7], [0.62, 0.68], [0.31, 0.5], [0.6, 0.62], [0.5, null], [0.38, 0.41]) },
      { name: "C1", description: "Dense (multilingual-e5-small) top-5 → LLM", metrics: m(0.66, 0.55, 0.59, 0.5, 0.45, 0.6, 0.83, 0.71, 7200), per_category: cat([0.67, 0.71], [0.61, 0.66], [0.29, 0.52], [0.62, 0.64], [0.5, null], [0.58, 0.63]) },
      { name: "C2", description: "Hybrid BM25 + dense with RRF (k=60) → LLM", metrics: m(0.74, 0.63, 0.67, 0.52, 0.5, 0.66, 0.86, 0.75, 7400), per_category: cat([0.74, 0.81], [0.7, 0.77], [0.33, 0.62], [0.68, 0.72], [0.5, null], [0.6, 0.7]) },
      { name: "C3", description: "Hybrid top-20 → cross-encoder rerank → top-5, + guardrail", metrics: m(0.83, 0.74, 0.77, 0.83, 0.58, 0.72, 0.9, 0.81, 8600), per_category: cat([0.82, 0.88], [0.79, 0.86], [0.38, 0.7], [0.75, 0.8], [0.83, null], [0.63, 0.74]) },
      { name: "C4", description: "C3 + date-aware filter (law in force for the asked period)", metrics: m(0.87, 0.79, 0.81, 0.85, 0.89, 0.81, 0.93, 0.85, 8650), per_category: cat([0.84, 0.89], [0.83, 0.88], [0.86, 0.9], [0.82, 0.84], [0.85, null], [0.64, 0.76]) },
      { name: "C5", description: "C4 + Hinglish normalisation (full system)", metrics: m(0.91, 0.82, 0.85, 0.87, 0.91, 0.86, 0.94, 0.88, 8700), per_category: cat([0.85, 0.9], [0.84, 0.89], [0.87, 0.91], [0.83, 0.85], [0.87, null], [0.86, 0.9]) },
    ],
  };

  var KB = {
    total_chunks: 186,
    by_law: { new_act: 62, old_act: 44, gst: 51, mapping: 19, general: 10 },
    by_topic: { slabs: 14, deductions: 33, rebate: 6, salary: 12, gst_rates: 29, gst_procedure: 14, capital_gains: 11, tds: 9, mapping: 19, filing: 10, vda: 5, residence: 6, other: 18 },
    by_doc_type: { act: 78, notification: 34, circular: 17, faq: 22, budget: 16, mapping: 19 },
    verified: { yes: 149, partial: 37 },
    sources: [
      { title: "Income-tax Act, 2025 (as amended by Finance Act, 2026)", publisher: "Income Tax Department", law: "new_act", url: "https://incometaxindia.gov.in/", chunks: 62 },
      { title: "Income-tax Act, 1961: sections 16, 80C–80U, 87A, 115BAC", publisher: "Income Tax Department", law: "old_act", url: "https://incometaxindia.gov.in/", chunks: 44 },
      { title: "CGST rate notifications 1/2017 and 9/2025 (GST 2.0)", publisher: "CBIC", law: "gst", url: "https://cbic-gst.gov.in/", chunks: 33 },
      { title: "56th GST Council meeting: press release", publisher: "PIB", law: "gst", url: "https://pib.gov.in/", chunks: 8 },
      { title: "GST FAQs: time of supply and rate transition", publisher: "CBIC", law: "gst", url: "https://cbic-gst.gov.in/", chunks: 10 },
      { title: "Section mapping: 1961 Act ↔ 2025 Act", publisher: "CBDT", law: "mapping", url: "https://incometaxindia.gov.in/", chunks: 19 },
      { title: "Return filing guides and due dates", publisher: "Income Tax Department", law: "general", url: "https://www.incometax.gov.in/", chunks: 10 },
    ],
  };

  /* ------------------------------------------------------------------ */
  /* Router                                                               */
  /* ------------------------------------------------------------------ */
  function delay(ms, value) {
    return new Promise(function (res) { setTimeout(function () { res(JSON.parse(JSON.stringify(value))); }, ms); });
  }

  // Real answers recorded from the live server (recorded.json): the demo questions, the Results
  // numbers and the library stats. Loaded only in demo mode; anything not recorded is simulated below.
  var recorded = null;
  function loadRecorded() {
    if (!recorded) recorded = fetch("recorded.json", { cache: "force-cache" }).then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; });
    return recorded;
  }
  function qkey(q) { return String(q || "").toLowerCase().replace(/[^a-z0-9$]+/g, " ").trim(); }
  function findRec(map, q) {
    if (!map) return null;
    var k = qkey(q), hit = null;
    Object.keys(map).forEach(function (x) { if (qkey(x) === k) hit = map[x]; });
    return hit;
  }

  function handle(path, body) {
    var p = String(path).split("?")[0];
    var cfg = String((body && body.config) || "C6").toUpperCase();
    if (p === "/ask" || p === "/compare" || p === "/experiments" || p === "/kb/stats") {
      return loadRecorded().then(function (rec) {
        var hit = null;
        if (rec && p === "/ask" && cfg === "C6") hit = findRec(rec.ask, body && body.question);
        else if (rec && p === "/compare") hit = findRec(rec.compare, body && body.question);
        else if (rec && p === "/experiments") hit = rec.experiments;
        else if (rec && p === "/kb/stats") hit = rec.kb;
        if (!hit) return simulate(p, body);
        // replay at a demo-friendly speed, not the CPU server's 20-60 s
        return delay(p === "/compare" ? 3200 : p === "/ask" ? (hit.refused ? 1300 : 2600) : 250, hit);
      });
    }
    return simulate(p, body);
  }

  function simulate(p, body) {
    switch (p) {
      case "/health":
        return delay(120, { status: "ok", llm: LLM, chunks: KB.total_chunks, mock: true });
      case "/ask": {
        var r = ask(body);
        return delay(r.config === "B0" ? 1100 : r.refused || r.follow_up ? 1300 : 2200, r);
      }
      case "/compare": {
        var q = (body && body.question) || "";
        var plain = ask({ question: q, config: "B0" });
        var ts = ask({ question: q, config: "C6" });
        return delay(2400, { plain: plain, taxsaathi: ts });
      }
      case "/calculate":
        return delay(350, calculate(body));
      case "/experiments":
        return delay(300, EXPERIMENTS);
      case "/kb/stats":
        return delay(200, KB);
      case "/feedback":
        return delay(150, { ok: true });
      default:
        return Promise.reject(new Error("Mock: no handler for " + p));
    }
  }

  window.TaxMock = { handle: handle, calculate: calculate, ask: ask };
})();
