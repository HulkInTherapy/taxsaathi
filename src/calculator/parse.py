"""
Turn a free-text calculation request into calculator inputs.

Example: "My salary is 18 lakh, 80C 1.5L, health insurance 30k, FY 2025-26, which regime is
better?" -> gross_salary=18,00,000, deductions_80c=1,50,000, deductions_80d=30,000,
tax_year=2025-26. Each amount found by entities.py is labelled by the nearest keyword before
(or just after) it. If no salary/income can be found we return a follow-up question instead.
"""
from __future__ import annotations

import re

from src.calculator.tax import RULES, format_inr, presumptive_limit
from src.nlp.dates import Period, fy_start_year
from src.nlp.entities import FX_AS_OF, FX_SOURCE, FX_SYMBOL, extract_entities

# Checked in this order (most specific first). Field name -> keyword regex.
FIELD_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("employer_nps", re.compile(r"employer'?s?\s*(nps|contribution)|80\s?ccd\s*\(?2\)?|company\s*nps", re.I)),
    ("nps_80ccd1b", re.compile(r"80\s?ccd\s*\(?1b\)?|\bnps\b", re.I)),
    ("deductions_80d_parents", re.compile(r"parent'?s?|mummy|papa|maa\b|mata\s*pita", re.I)),
    ("deductions_80d", re.compile(r"80\s?d\b|health\s*insurance|mediclaim|medical\s*insurance|health\s*policy|swasthya\s*bima", re.I)),
    ("deductions_80c", re.compile(r"80\s?c\b|\bppf\b|\belss\b|\blic\b|\bepf\b|life\s*insurance|tax\s*saving|sukanya|\bnsc\b|tuition", re.I)),
    ("hra_exemption", re.compile(r"\bhra\b|house\s*rent|rent\s*(allowance|exemption)|kiraya", re.I)),
    ("home_loan_interest", re.compile(r"home\s*loan|housing\s*loan|loan\s*interest|interest\s*on\s*(home|housing)|section\s*24|\b24\s?\(?b\)?", re.I)),
    ("other_deductions", re.compile(r"80\s?e\b|80\s?g\b|80\s?tta|80\s?ttb|donation|education\s*loan|other\s*deduction", re.I)),
    ("gross_salary", re.compile(r"salary|salry|salery|sallary|ctc|income|earn|kamai|kamata|kamati|tankhwah|package|\blpa\b|gross|"
                                r"pay\b|aamdani|annual|pension|receipts?|revenue|turnover|billing|invoice|fees\b|"
                                r"stipend|\bmake\b|\bmaking\b|\bget\b|\bgets\b|\bgetting\b|milti|milta", re.I)),
]

# ---------------------------------------------------------------- income type
# Professional / freelance income (presumptive scheme, s.58 of the 2025 Act / s.44ADA of 1961).
PROFESSIONAL_RE = re.compile(
    r"freelanc|free\s*lanc|consultan(t|cy)|self[- ]?employed|contractor|on\s+contract|contract\s+basis|"
    r"independent\s+contractor|gig\b|upwork|fiverr|toptal|youtube|youtuber|content\s+creator|influencer|"
    r"instagram|\bblogger|private\s+practice|my\s+(own\s+)?(clinic|practice)|doctor|lawyer|advocate|architect|"
    r"chartered\s+accountant|interior\s+design|professional\s+(income|receipts|fees|services)|"
    r"\b44\s?ada\b|presumptive|section\s+58\b|gross\s+receipts|receipts|invoic|"
    r"(foreign|us|uk|overseas|international|abroad|german|european)\s+clients?|\bclients?\b", re.I)
SALARY_RE = re.compile(
    r"salary|salry|salery|sallary|salaried|\bctc\b|\blpa\b|tankhwah|tankha|pagar|employer|employee|"
    r"payroll|on\s+the\s+rolls|in[- ]hand|take[- ]home|pension|\bjob\b.*\b(employee|payroll)|naukri|"
    r"\bhike\b|appraisal|\bpf\b|\bepf\b|form\s*16", re.I)
BUSINESS_RE = re.compile(r"business|vyapar|dukaan|\bshop\b|trader|trading|kirana|turnover|\b44\s?ad\b(?!a)", re.I)
REMOTE_RE = re.compile(r"\bremote(ly)?\b|work\s+from\s+home|\bwfh\b", re.I)


def detect_income_type(text: str, foreign: bool) -> tuple[str, str | None, bool]:
    """Return (income_type, reason, assumed).

    income_type: "salary" | "professional_presumptive" | "business". `assumed` = no clear cue,
    so we defaulted to salary and must say so.
    """
    t = re.sub(r"professional\s+tax|rent\s+receipts?", "", text, flags=re.I)  # "professional tax" is a salary deduction
    prof, sal, bus = PROFESSIONAL_RE.search(t), SALARY_RE.search(t), BUSINESS_RE.search(t)
    if sal and not prof:
        return "salary", None, False
    if prof and not sal:
        return "professional_presumptive", f"'{prof.group(0)}'", False
    if prof and sal:
        return "salary", "mixed", False
    if bus:
        return "business", None, False
    if REMOTE_RE.search(t) and foreign:
        return "professional_presumptive", "remote work paid in foreign currency", True
    return "salary", None, True


_CLAUSE_SEP = re.compile(r",|;|\band\b|\bplus\b|\baur\b|\bwith\b|\.\s", re.I)


def _nearest(window: str, from_end: bool) -> str | None:
    """Field whose keyword is closest to the amount inside `window` (None if no keyword)."""
    best = None
    for name, rx in FIELD_PATTERNS:
        for m in rx.finditer(window):
            dist = len(window) - m.end() if from_end else m.start()
            if best is None or dist < best[0]:
                best = (dist, name)
    return best[1] if best else None


def tax_year_for(period: Period | None) -> tuple[str, str | None]:
    """Map the query period to a calculator tax year (with a note if we had to clamp)."""
    years = sorted(RULES)
    if period is None or period.assumed_current:
        return years[-1], None
    key = f"{fy_start_year(period.start)}-{str(fy_start_year(period.start) + 1)[2:]}"
    if key in RULES:
        return key, None
    clamped = years[0] if key < years[0] else years[-1]
    return clamped, f"Calculator supports {', '.join(years)} only; used {clamped} for {key}."


_PERIOD_MULT = {"month": 12, "week": 52}


def _annual(a: dict) -> int:
    """Rupee value of an amount per year (monthly ×12, weekly ×52; foreign currency converted)."""
    mult = _PERIOD_MULT.get(a.get("period"), 1)
    if a.get("foreign_value") is not None:
        return int(round(a["foreign_value"] * mult * a["fx_rate"]))
    return a["value"] * mult


def _fx_note(a: dict) -> str:
    sym = FX_SYMBOL.get(a["currency"], a["currency"])
    mult = _PERIOD_MULT.get(a.get("period"), 1)
    fv = a["foreign_value"]
    how = f"{sym}{fv:,.0f}" + (f" a {a['period']} × {mult} = {sym}{fv * mult:,.0f} a year" if mult > 1 else "")
    return (f"{how}, converted at ₹{a['fx_rate']:g} per {sym} ({FX_SOURCE}, {FX_AS_OF}) = {format_inr(_annual(a))} — "
            f"change it in the calculator if yours differs.")


def _period_note(a: dict, value: int) -> str | None:
    if a.get("foreign_value") is not None:
        return None  # the currency note shows the whole conversion
    return f"{a['text']} × {_PERIOD_MULT[a['period']]} = {format_inr(value)} a year."


def parse_calc_query(text: str, period: Period | None = None, entities: dict | None = None) -> dict:
    """Return {"inputs": dict|None, "follow_up": str|None, "assigned": [[field, text, value]], "notes": [],
    "income_type", "assumed": {"income_type": bool, "annual": bool}, "escalate": bool}."""
    ents = entities or extract_entities(text)
    amounts = sorted(ents["amounts"], key=lambda a: a["start"])
    inputs: dict = {}
    assigned: list[list] = []
    notes: list[str] = []
    unlabelled = []
    used: list[dict] = []
    assumed = {"income_type": False, "annual": False}
    gross_amt = None
    prev_end = 0
    for n, a in enumerate(amounts):
        # Look ~45 chars before the amount (not past the previous amount) and ~30 chars
        # after it (not past the next amount); the keyword nearest to the amount wins.
        next_start = amounts[n + 1]["start"] if n + 1 < len(amounts) else len(text)
        before = text[max(prev_end, a["start"] - 45):a["start"]]
        after = text[a["end"]:min(next_start, a["end"] + 30)]
        # Prefer a keyword in the same clause: the part of `before` after the last
        # separator, then the part of `after` before the first separator.
        before_clause = _CLAUSE_SEP.split(before)[-1]
        after_clause = _CLAUSE_SEP.split(after)[0]
        best = (_nearest(before_clause, from_end=True) or _nearest(after_clause, from_end=False)
                or _nearest(a["text"], from_end=False)
                or _nearest(before, from_end=True) or _nearest(after, from_end=False))
        field = best
        prev_end = a["end"]
        if field is None:
            unlabelled.append(a)
            continue
        value = _annual(a)
        if a.get("period") in _PERIOD_MULT and _period_note(a, value):
            notes.append(_period_note(a, value))
        if field in inputs and field != "gross_salary":
            inputs[field] += value
        elif field not in inputs:
            inputs[field] = value
            if field == "gross_salary":
                gross_amt = a
        else:
            continue
        used.append(a)
        assigned.append([field, a["text"], value])

    if "gross_salary" not in inputs and unlabelled:
        # Fall back to the largest unlabelled amount as the income.
        a = gross_amt = max(unlabelled, key=_annual)
        value = _annual(a)
        inputs["gross_salary"] = value
        used.append(a)
        assigned.append(["gross_salary", a["text"], value])
        if a.get("period") in _PERIOD_MULT:
            if _period_note(a, value):
                notes.append(_period_note(a, value))
        else:
            assumed["annual"] = True
            notes.append(f"Assumed {a['text']} is your annual income (say \"per month\" if it is monthly).")
    elif gross_amt is not None and _looks_monthly(gross_amt):
        assumed["annual"] = True
        notes.append(f"Assumed {gross_amt['text']} is your annual income (say \"per month\" if it is monthly).")

    for a in used:
        if a.get("foreign_value") is not None:
            notes.append(_fx_note(a))

    if "gross_salary" not in inputs:
        return {"inputs": None, "assigned": assigned, "notes": notes, "income_type": None,
                "assumed": assumed, "escalate": False,
                "follow_up": ("To calculate your tax I need your annual gross salary or income. "
                              "For example: \"My salary is ₹14 lakh, 80C ₹1.5 lakh, FY 2025-26\".")}

    tax_year, note = tax_year_for(period)
    if note:
        notes.append(note)
    inputs["tax_year"] = tax_year
    inputs["age"] = ents.get("age_category") or "below60"

    foreign = any(a.get("foreign_value") is not None for a in used)
    income_type, reason, guessed = detect_income_type(text, foreign)
    assumed["income_type"] = guessed
    inputs["income_type"] = "professional_presumptive" if income_type == "professional_presumptive" else "salary"
    inputs["salaried"] = income_type == "salary"
    escalate = False
    if income_type == "professional_presumptive":
        if guessed:
            notes.append("I treated this as freelance/professional income from foreign clients (remote work paid in "
                         "foreign currency). If you are on a foreign employer's payroll, tell me and I'll recalculate as salary.")
        else:
            notes.append(f"Treated as professional/freelance income (because of {reason}), using the presumptive scheme.")
        if "hra_exemption" in inputs or "employer_nps" in inputs:
            notes.append("HRA exemption and employer NPS apply only to salary, so they were ignored.")
            inputs.pop("hra_exemption", None)
            inputs.pop("employer_nps", None)
        if re.search(r"(more\s+than|over|above)\s*5\s*%\s*(in\s+)?cash|mostly\s+cash|cash\s+receipts?\s+(above|over|more)", text, re.I):
            inputs["cash_receipts_over_5pct"] = True
        limit = presumptive_limit(bool(inputs.get("cash_receipts_over_5pct")))
        if inputs["gross_salary"] > limit:
            escalate = True
            return {"inputs": inputs, "assigned": assigned, "notes": notes, "income_type": inputs["income_type"],
                    "assumed": assumed, "escalate": True,
                    "follow_up": (f"Your professional receipts of {format_inr(inputs['gross_salary'])} a year are above the "
                                  f"{format_inr(limit)} limit of the presumptive scheme (section 58 of the Income-tax Act, 2025; "
                                  f"earlier section 44ADA), so 50% cannot simply be taken as profit. Above this limit you need "
                                  f"regular books of account and possibly a tax audit (section 63, earlier 44AB), and tax "
                                  f"depends on your actual expenses — please consult a Chartered Accountant.")}
    elif income_type == "business":
        notes.append("Looks like business income: no standard deduction applied (presumptive section 44AD / 58 "
                     "business rates are not modelled — treated the amount as your profit).")
    else:
        if reason == "mixed":
            notes.append("You mentioned both salary and freelance/professional income; I treated the amount as salary. "
                         "Freelance income is taxed differently (presumptive 50%) — ask about it separately.")
        elif guessed:
            notes.append("I assumed this is salary from an Indian employer. If you're a freelancer, tell me and I'll recalculate.")
        if foreign:
            notes.append("Foreign salary of a resident is taxable in India; if tax was also withheld abroad you may claim "
                         "foreign tax credit — check with a CA.")
    return {"inputs": inputs, "follow_up": None, "assigned": assigned, "notes": notes,
            "income_type": inputs["income_type"], "assumed": assumed, "escalate": escalate}


def _looks_monthly(a: dict) -> bool:
    """No period given and below ₹2 lakh a year: possibly a monthly figure, so flag the assumption."""
    return a.get("period") is None and _annual(a) < 200_000
